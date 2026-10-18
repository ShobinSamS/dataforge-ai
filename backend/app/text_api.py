"""Additive text dataset endpoints; existing document contracts are unchanged."""
import hashlib
import json
import threading
import platform
from importlib.metadata import version
from collections import Counter
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from .config import settings
from .db import Job, TextJob, TextSample, TextExport, uid
from .local_llm import LocalLLM
from .text_exporting import export_text, CSV_JSON_FIELDS
from .text_generation import LANGUAGES, validate_record, content_hash
from .text_schemas import TextConfig, TextExportRequest

ACTIVE=["queued","running","cancelling"]


def active_count(db) -> int:
    return sum(db.scalar(select(func.count()).select_from(model).where(model.status.in_(ACTIVE))) for model in (Job,TextJob))


def job_dict(job: TextJob) -> dict:
    return {"id":job.id,"name":job.name,"status":job.status,"config":job.config,"total":job.total,
            "completed":job.completed,"error":job.error,"metrics":job.metrics,"created_at":job.created_at.isoformat()}


def text_router(sessions, root: Path, queue_lock: threading.Lock) -> APIRouter:
    router=APIRouter(prefix="/api/text",tags=["Synthetic text datasets"])

    def require(db, model, id_):
        row=db.get(model,id_)
        if row is None: raise HTTPException(404,"Text dataset record not found")
        return row

    def verify_saved(row, config: TextConfig) -> dict:
        try:
            raw=Path(row.path).read_bytes()
            data=json.loads(raw)
            if not isinstance(data,dict): raise ValueError("Record must be an object")
            report=validate_record(data,config)
            if row.summary.get("file_sha256")!=hashlib.sha256(raw).hexdigest():
                report["errors"].append("record_integrity_changed")
            report["passed"]=not report["errors"]
            return report
        except (ValueError,KeyError,TypeError,OSError,AttributeError):
            return {"passed":False,"errors":["record_corrupt_or_missing"],"warnings":[],"training_ready":False}

    def read_record(row, backend: str) -> dict:
        try:
            raw=Path(row.path).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=row.summary.get("file_sha256"):
                raise ValueError("Record integrity changed")
            data=json.loads(raw)
            if not isinstance(data,dict): raise ValueError("Record must be an object")
            return {**data,"validation":row.validation}
        except (ValueError,OSError,TypeError):
            return {"id":row.id,"index":row.index,**row.summary,"provenance":{"engine":backend},
                    "validation":{"passed":False,"errors":["record_corrupt_or_missing"],"warnings":[]}}

    @router.get("/capabilities")
    def capabilities():
        llm=LocalLLM()
        try: status=llm.status()
        finally: llm.close()
        return {"tasks":["classification","ner","qa","instruction","conversation","augmentation"],
                "languages":LANGUAGES,"backends":["procedural","ollama"],"max_samples":min(2000,settings.text_max_samples),
                "exports":["csv","json","jsonl"],"llm":status,"worker_count":1,
                "limitations":["Semantic labels and generated language require review", "Procedural content uses a small authored template library",
                               "Ollama CPU memory is outside API RSS metrics", "No language translation during augmentation"]}

    @router.post("/jobs",status_code=201)
    def create(body: TextConfig):
        if body.count>settings.text_max_samples: raise HTTPException(422,"Text sample count exceeds configured maximum")
        if body.backend=="ollama":
            llm=LocalLLM()
            try: installed=llm.status()["installed"]
            finally: llm.close()
            if not installed: raise HTTPException(503,"Configured local Qwen model is unavailable; no download or remote fallback performed")
        with queue_lock,sessions.begin() as db:
            if active_count(db)>=8: raise HTTPException(429,"Shared CPU queue full")
            job=TextJob(name=body.name,config=body.model_dump(mode="json"),total=body.count)
            db.add(job); db.flush()
            return job_dict(job)

    @router.get("/jobs")
    def jobs():
        with sessions() as db:
            return [job_dict(j) for j in db.scalars(select(TextJob).order_by(TextJob.created_at.desc()))]

    @router.get("/jobs/{id_}")
    def job(id_: str):
        with sessions() as db: return job_dict(require(db,TextJob,id_))

    @router.post("/jobs/{id_}/cancel")
    def cancel(id_: str):
        with sessions.begin() as db:
            job=require(db,TextJob,id_)
            if job.status not in {"running","queued"}: raise HTTPException(409,"Text job is not active")
            job.status="cancelled" if job.status=="queued" else "cancelling"
            return job_dict(job)

    @router.post("/jobs/{id_}/resume")
    def resume(id_: str):
        with queue_lock,sessions.begin() as db:
            job=require(db,TextJob,id_)
            if job.status not in {"paused","failed","cancelled"}: raise HTTPException(409,"Text job cannot be resumed")
            if active_count(db)>=8: raise HTTPException(429,"Shared CPU queue full")
            job.status="queued";job.error=""
            return job_dict(job)

    @router.get("/jobs/{id_}/records")
    def records(id_: str, offset: int=Query(0,ge=0), limit: int=Query(20,ge=1,le=100)):
        with sessions() as db:
            job=require(db,TextJob,id_)
            rows=db.scalars(select(TextSample).where(TextSample.job_id==id_).order_by(TextSample.index).offset(offset).limit(limit))
            return {"items":[read_record(row,job.config["backend"]) for row in rows],
                    "total":job.completed,"offset":offset,"limit":limit}

    @router.get("/jobs/{id_}/quality")
    def quality(id_: str):
        with sessions() as db:
            job=require(db,TextJob,id_)
            rows=list(db.scalars(select(TextSample).where(TextSample.job_id==id_)))
            return {"requested":job.total,"total":len(rows),"accepted":sum(r.validation["passed"] for r in rows),
                    "rejected":sum(not r.validation["passed"] for r in rows),
                    "labels":dict(Counter(r.summary["label"] for r in rows if r.summary.get("label") is not None and r.validation["passed"])),
                    "languages":dict(Counter(r.summary["language"] for r in rows if r.validation["passed"])),
                    "errors":dict(Counter(e for r in rows for e in r.validation["errors"])),"training_ready":False,
                    "warnings":["Human review required for semantics, class meaning, language and remaining PII", "No statistical fidelity or utility claim"]}

    @router.get("/jobs/{id_}/manifest")
    def manifest(id_: str):
        with sessions() as db:
            job=require(db,TextJob,id_)
            config={k:v for k,v in job.config.items() if k not in {"source_texts","instructions"}}
            config["instructions_sha256"]=hashlib.sha256(job.config.get("instructions","").encode()).hexdigest()
            config["source_hashes"]=[hashlib.sha256(s["text"].encode()).hexdigest() for s in job.config.get("source_texts",[])]
            return {"dataset":job.name,"version":job.id,"config":config,"metrics":job.metrics,"generator_version":"text-v1",
                    "runtime":{"python":platform.python_version(),"faker":version("faker")},
                    "offset_unit":"Unicode code points; end-exclusive, not UTF-16 units or bytes",
                    "csv_json_encoded_columns":sorted(CSV_JSON_FIELDS),"training_ready":False,
                    "reproducibility":"Procedural: seed + config + runtime. Ollama: saved records are immutable; fresh inference may vary across runtimes.",
                    "validation":quality(id_)}

    @router.post("/jobs/{id_}/validate")
    def revalidate(id_: str):
        with sessions.begin() as db:
            job=require(db,TextJob,id_)
            if job.status not in {"completed","review_required"}: raise HTTPException(409,"Wait for generation to finish")
            config=TextConfig.model_validate(job.config);hashes=set();rejected=False
            for row in db.scalars(select(TextSample).where(TextSample.job_id==id_).order_by(TextSample.index)):
                # Rejected construction candidates stay rejected and are never promoted by a shallow recheck.
                if not row.validation["passed"]: rejected=True;continue
                report=verify_saved(row,config)
                if row.sha256 in hashes: report["errors"].append("duplicate_content");report["passed"]=False
                hashes.add(row.sha256);row.validation=report;rejected=rejected or not report["passed"]
            job.status="review_required" if rejected else "completed"
        return quality(id_)

    @router.post("/jobs/{id_}/exports",status_code=201)
    def export(id_: str, body: TextExportRequest):
        if not body.review_confirmed: raise HTTPException(422,"Review text, labels, language and privacy before export")
        with queue_lock,sessions.begin() as db:
            job=require(db,TextJob,id_)
            if job.status not in {"completed","review_required"}: raise HTTPException(409,"Wait for text generation to finish")
            if not any(r.validation["passed"] for r in db.scalars(select(TextSample).where(TextSample.job_id==id_))):
                raise HTTPException(422,"No accepted text records to export")
            config=TextConfig.model_validate(job.config)
            for row in db.scalars(select(TextSample).where(TextSample.job_id==id_)):
                if row.validation["passed"] and not verify_saved(row,config)["passed"]:
                    raise HTTPException(409,"Saved text changed or failed validation; run dataset validation before export")
            export_id=uid()
            rows=db.scalars(select(TextSample).where(TextSample.job_id==id_).order_by(TextSample.index)).yield_per(100)
            path=export_text(rows,body.format,root/"text_exports"/f"{export_id}.{body.format}")
            db.add(TextExport(id=export_id,job_id=id_,format=body.format,path=str(path)))
            return {"id":export_id,"download_url":f"/api/text/exports/{export_id}/download",
                    "manifest_url":f"/api/text/jobs/{id_}/manifest"}

    @router.get("/exports")
    def exports():
        with sessions() as db:
            return [{"id":e.id,"job_id":e.job_id,"format":e.format,"created_at":e.created_at.isoformat(),
                     "download_url":f"/api/text/exports/{e.id}/download"} for e in db.scalars(select(TextExport).order_by(TextExport.created_at.desc()))]

    @router.get("/exports/{id_}/download")
    def download(id_: str):
        with sessions() as db:
            row=require(db,TextExport,id_)
            media={"csv":"text/csv; charset=utf-8","json":"application/json","jsonl":"application/x-ndjson"}
            return FileResponse(row.path,filename=f"dataforge-text-{row.job_id[:8]}.{row.format}",media_type=media[row.format])

    return router
