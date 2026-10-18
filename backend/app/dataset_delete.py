"""Delete terminal datasets and only their canonical, owned local artifacts."""
import re
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select
from .db import Job, Sample, Export, TextJob, TextSample, TextExport
from .resources import CPU_LOCK


def dataset_delete_router(sessions, root: Path, queue_lock):
    router=APIRouter(prefix="/api")
    root=root.resolve()

    def remove(id_,text):
        model,sample,export=(TextJob,TextSample,TextExport) if text else (Job,Sample,Export)
        warnings=[];paths=[]
        with queue_lock,CPU_LOCK:
            with sessions.begin() as db:
                job=db.get(model,id_)
                if job is None:raise HTTPException(404,"Dataset not found")
                if job.status in {"queued","running","cancelling"}:
                    raise HTTPException(409,"Cancel the job and wait for it to stop before deleting this dataset")
                for row in db.scalars(select(export).where(export.job_id==id_)):
                    extension=row.format if text else "zip"
                    expected=root/("text_exports" if text else "exports")/f"{row.id}.{extension}"
                    if re.fullmatch(r"[a-f0-9]{32}",row.id) and Path(row.path).absolute()==expected:
                        paths.append((expected,False))
                    else:warnings.append("An export outside canonical storage was retained.")
                db.execute(delete(export).where(export.job_id==id_))
                db.execute(delete(sample).where(sample.job_id==id_))
                db.delete(job)
            if re.fullmatch(r"[a-f0-9]{32}",id_):paths.append((root/("text" if text else "jobs")/id_,True))
            # Commit metadata first; cleanup failures are reported, never hidden.
            # Resolve every target before recursive deletion; do not follow links
            # or junctions out of the explicitly owned storage directory.
            for path,is_dir in paths:
                try:
                    base=root/("text" if text else "jobs") if is_dir else root/("text_exports" if text else "exports")
                    if base.resolve().parent!=root or path.is_symlink() or path.resolve().parent!=base.resolve():
                        warnings.append("A linked artifact outside canonical storage was retained.");continue
                    if not path.exists():continue
                    if is_dir:
                        if any(child.is_symlink() or not child.resolve().is_relative_to(path.resolve()) for child in path.rglob("*")):
                            warnings.append("An artifact folder containing links was retained.");continue
                        shutil.rmtree(path)
                    else:path.unlink()
                except OSError:warnings.append("Dataset deleted; some local artifacts could not be removed.")
        return {"id":id_,"deleted":True,"warnings":warnings}

    @router.delete("/jobs/{id_}")
    def delete_dataset(id_: str):return remove(id_,False)

    @router.delete("/text/jobs/{id_}")
    def delete_text_dataset(id_: str):return remove(id_,True)

    return router
