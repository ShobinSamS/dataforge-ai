"""Text work executes on the existing single CPU queue and commits each record."""
import json
import hashlib
import logging
import time
from pathlib import Path
import httpx
import psutil
from sqlalchemy import select
from .config import settings
from .db import TextJob, TextSample
from .local_llm import LocalLLM
from .resources import CPU_LOCK
from .text_schemas import TextConfig
from .text_generation import plan_record, procedural, assemble, validate_record, content_hash

logger=logging.getLogger("dataforge.text")


def run_text(worker, id_: str) -> None:
    started=time.perf_counter(); llm=None;identity={}
    try:
        with worker.sessions() as db:
            job=db.get(TextJob,id_); config=TextConfig.model_validate(job.config)
            committed=set(db.scalars(select(TextSample.index).where(TextSample.job_id==id_)))
            hashes=set(db.scalars(select(TextSample.sha256).where(TextSample.job_id==id_)))
            previous=job.metrics.get("elapsed_seconds",0)
        if config.backend=="ollama":
            llm=LocalLLM()
            identity=llm.status()
            if not identity["installed"]:
                raise RuntimeError("Configured Qwen model is not available in local Ollama; no fallback or download performed")
        missing=[i for i in range(config.count) if i not in committed]
        for offset in range(0,len(missing),config.batch_size):
            resident=llm.resident_cpu_mb() if llm else 0
            threshold=max(settings.min_available_mb,settings.llm_min_available_mb-resident if llm else 0)
            available=psutil.virtual_memory().available/1024**2
            with worker.sessions.begin() as db:
                job=db.get(TextJob,id_)
                if worker.stop.is_set() or job.status=="cancelling":
                    job.status="paused" if worker.stop.is_set() else "cancelled"; return
                if available<threshold:
                    job.status="paused"; job.error=f"Available RAM {available:.0f} MB below admission threshold {threshold:.0f} MB; resume after freeing memory"; return
            plans=[plan_record(config,i) for i in missing[offset:offset+config.batch_size]]
            pending=plans[:]; results={}
            with CPU_LOCK:
                for attempt in range(config.max_retries+1):
                    drafts=None; batch_error=""
                    if llm:
                        try:
                            drafts=llm.generate(config,pending,config.seed+pending[0]["index"]*1009+attempt*10000019)
                        except httpx.HTTPError as exc:
                            raise RuntimeError("Local Ollama request failed; check model availability, timeout and server logs") from exc
                        except (ValueError, KeyError, TypeError):
                            batch_error="invalid_model_batch_schema"
                    retry=[]
                    for position,plan in enumerate(pending):
                        index=plan["index"]; seed=config.seed+index*1009+attempt*10000019
                        try:
                            if batch_error: raise ValueError(batch_error)
                            draft=drafts[position] if llm else procedural(config,plan,seed)
                            row=assemble(config,plan,draft,seed)
                            report=validate_record(row,config)
                            digest=content_hash(row)
                            if digest in hashes:
                                report["passed"]=False; report["errors"].append("duplicate_content")
                        except (ValueError,KeyError,TypeError) as exc:
                            # Do not log potentially sensitive model/source strings in error messages.
                            row={"id":f"text-{config.seed}-{index:06d}","index":index,"task":config.task,
                                 "language":plan["language"],"seed":seed,"provenance":{"engine":config.backend}}
                            report={"passed":False,"errors":[batch_error or "invalid_generated_record"],
                                    "warnings":["Generated record failed schema or task invariants"],"training_ready":False}
                            digest=f"rejected-{index}"
                        if report["passed"]:
                            hashes.add(digest)
                            results[index]=(row,report,digest,attempt)
                        elif attempt<config.max_retries:
                            retry.append(plan)
                        else:
                            results[index]=(row,report,digest,attempt)
                    pending=retry
                    if not pending: break
            for plan in plans:
                # Check at each record boundary, including a cancellation arriving during inference.
                with worker.sessions.begin() as db:
                    job=db.get(TextJob,id_)
                    if worker.stop.is_set() or job.status=="cancelling":
                        job.status="paused" if worker.stop.is_set() else "cancelled"; return
                    index=plan["index"]; row,report,digest,attempt=results[index]
                    row["validation"]=report; row["attempt"]=attempt
                    folder=worker.root/"text"/id_; folder.mkdir(parents=True,exist_ok=True)
                    path=folder/f"{index:06d}.json"; temporary=path.with_suffix(".tmp")
                    temporary.write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding="utf-8")
                    temporary.replace(path)
                    db.add(TextSample(job_id=id_,index=index,path=str(path),summary={"language":row["language"],
                        "label":row.get("label"),"task":config.task,"file_sha256":hashlib.sha256(path.read_bytes()).hexdigest()},validation=report,sha256=digest))
                    job.completed+=1
                    job.metrics={"elapsed_seconds":round(previous+time.perf_counter()-started,2),
                        "peak_process_rss_mb":round(max(psutil.Process().memory_info().rss/1024**2,job.metrics.get("peak_process_rss_mb",0)),1),
                        "worker_count":1,"model_inference":bool(llm),"model":settings.ollama_model if llm else None,
                        "model_digest":identity.get("digest"),"quantization":identity.get("quantization"),
                        "rss_scope":"API process sampled at record boundaries; excludes Ollama process memory"}
                logger.info(json.dumps({"event":"text_record_completed","job_id":id_,"index":index,"passed":report["passed"]}))
        with worker.sessions.begin() as db:
            job=db.get(TextJob,id_)
            rejected=any(not r.validation["passed"] for r in db.scalars(select(TextSample).where(TextSample.job_id==id_)))
            job.status="review_required" if rejected else "completed"
    except Exception as exc:
        logger.error(json.dumps({"event":"text_job_failed","job_id":id_,"error_type":type(exc).__name__}))
        with worker.sessions.begin() as db:
            job=db.get(TextJob,id_); job.status="failed"
            job.error=str(exc)[:300] if isinstance(exc,RuntimeError) else "Text generation failed; inspect local runtime configuration"
    finally:
        if llm: llm.close()
