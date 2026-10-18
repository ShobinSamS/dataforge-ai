"""One durable SQL queue, one CPU worker, deterministic recovery at sample boundaries."""
import json
import logging
import threading
import time
from pathlib import Path
import psutil
from sqlalchemy import select, func
from .config import settings
from .db import Job, Sample, TextJob
from .schemas import GenerationConfig, Region
from .render import render_sample, optional_regions
from .resources import CPU_LOCK
from .validation import validate, yolo_line
from .text_jobs import run_text

logger = logging.getLogger("dataforge.jobs")


class Worker:
    def __init__(self, sessions, root: Path):
        self.sessions = sessions
        self.root = root
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop,name="dataforge-cpu",daemon=True)

    def start(self):
        with self.sessions.begin() as db:
            for model in (Job,TextJob):
                for job in db.scalars(select(model).where(model.status.in_(["running","cancelling"]))):
                    job.status = "paused"
                    job.error = "Process interrupted; resume to continue from committed samples"
        self.thread.start()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=10)

    def loop(self):
        while not self.stop.wait(.2):
            with self.sessions.begin() as db:
                job = db.scalar(select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1))
                text_job = db.scalar(select(TextJob).where(TextJob.status == "queued").order_by(TextJob.created_at).limit(1))
                use_text = bool(text_job and (not job or text_job.created_at < job.created_at))
                current = text_job if use_text else job
                if not current:
                    continue
                current.status = "running"
                id_ = current.id
            if use_text:
                self.run_text(id_)
            else:
                self.run(id_)

    def run_text(self, id_: str) -> None:
        run_text(self,id_)

    def run(self, id_: str):
        started = time.perf_counter()
        peak = 0.0
        try:
            with self.sessions() as db:
                job = db.get(Job,id_)
                config = GenerationConfig.model_validate(job.config)
                snapshot = job.template_snapshot
                indices = set(db.scalars(select(Sample.index).where(Sample.job_id == id_)))
                hashes = set(db.scalars(select(Sample.sha256).where(Sample.job_id == id_)))
                previous_seconds = job.metrics.get("elapsed_seconds",0)
            regions = [Region.model_validate(r) for r in snapshot["regions"]]
            expected = len(optional_regions(snapshot["width"],snapshot["height"],regions,config))
            if expected == 0 and not any(r.action=="erase" for r in regions):
                raise ValueError("Enable at least one replacement or erase-only region")
            for index in range(config.count):
                if index in indices:
                    continue
                with self.sessions.begin() as db:
                    job = db.get(Job,id_)
                    if self.stop.is_set() or job.status == "cancelling":
                        job.status = "cancelled" if not self.stop.is_set() else "paused"
                        return
                if psutil.virtual_memory().available / 1024**2 < settings.min_available_mb:
                    with self.sessions.begin() as db:
                        job = db.get(Job,id_); job.status = "paused"; job.error = "Available RAM below configured safety threshold"
                    return
                folder = self.root/"jobs"/id_/f"{index:06d}"
                with CPU_LOCK:
                    for attempt in range(config.max_retries+1):
                        result = render_sample(Path(snapshot["image_path"]),regions,config,index,folder,attempt,asset_root=self.root)
                        report = validate(result,folder,expected)
                        if result["sha256"] in hashes:
                            report["errors"].append("duplicate_image")
                            report["passed"] = False
                        if report["passed"]:
                            break
                    (folder/"labels.txt").write_text("\n".join(yolo_line(a,result["width"],result["height"]) for a in result["annotations"])+("\n" if result["annotations"] else ""),encoding="utf-8")
                    metadata = {"index":index,"seed":result["seed"],"transform":result["transform"],
                                "annotations":result["annotations"],"validation":report,"attempt":attempt,
                                "erased_regions":result["erased_regions"]}
                    (folder/"metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
                    hashes.add(result["sha256"])
                    peak = max(peak,psutil.Process().memory_info().rss/1024**2)
                    del result
                with self.sessions.begin() as db:
                    sample = Sample(job_id=id_,index=index,path=str(folder/"image.png"),annotations=metadata["annotations"],
                                    validation=report,sha256=next_hash(folder/"image.png"))
                    db.add(sample)
                    job = db.get(Job,id_)
                    job.completed += 1
                    job.metrics = {"elapsed_seconds":round(previous_seconds+time.perf_counter()-started,2),
                                   "peak_process_rss_mb":round(max(peak,job.metrics.get("peak_process_rss_mb",0)),1),
                                   "worker_count":1,"model_inference":False}
                logger.info(json.dumps({"event":"sample_completed","job_id":id_,"sample":index,"passed":report["passed"]}))
            with self.sessions.begin() as db:
                job = db.get(Job,id_)
                rejected = sum(not s.validation["passed"] for s in db.scalars(select(Sample).where(Sample.job_id == id_)))
                job.status = "completed" if not rejected else "review_required"
        except Exception as exc:
            logger.exception("job_failed",extra={"job_id":id_})
            with self.sessions.begin() as db:
                job = db.get(Job,id_)
                job.status = "failed"
                job.error = str(exc)[:1000]


def next_hash(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()
