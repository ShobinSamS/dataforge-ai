"""Recheck completed document images without changing pixels or generation settings."""
import json
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from .db import Job,Sample
from .jobs import snapshot_regions,next_hash
from .render import optional_regions
from .schemas import GenerationConfig
from .validation import validate


def revalidate_job(sessions,id_):
    with sessions.begin() as db:
        job=db.get(Job,id_)
        if job.status not in {"completed","review_required"}:
            raise ValueError("Recheck is available after all samples have finished")
        config=GenerationConfig.model_validate(job.config)
        snapshot=job.template_snapshot
        expected=len(optional_regions(snapshot["width"],snapshot["height"],snapshot_regions(snapshot),config))
        samples=list(db.scalars(select(Sample).where(Sample.job_id==id_).order_by(Sample.index)))
        prepared=[];hashes=set()
        for sample in samples:
            path=Path(sample.path);folder=path.parent
            metadata=json.loads((folder/"metadata.json").read_text(encoding="utf-8"))
            # Retain generation-time failures such as clipped geometry. QR decode
            # and duplicate/integrity checks are performed again on actual pixels.
            errors=[e for e in sample.validation.get("errors",[]) if not e.startswith("qr_unreadable:") and e not in {"duplicate_image","image_hash_mismatch"}]
            sha=next_hash(path)
            if sha!=sample.sha256:errors.append("image_hash_mismatch")
            if sha in hashes:errors.append("duplicate_image")
            hashes.add(sha)
            with Image.open(path) as opened:
                image=opened.convert("RGBA" if opened.mode=="RGBA" else "RGB")
            result={"image":image,"width":image.width,"height":image.height,"annotations":sample.annotations,"errors":errors}
            report=validate(result,folder,expected)
            metadata["validation"]=report
            prepared.append((sample,report,folder/"metadata.json",json.dumps(metadata,indent=2)))
        # Do all image/mask checks before committing any updated reports.
        for sample,report,path,content in prepared:
            temporary=path.with_suffix(".recheck.tmp")
            temporary.write_text(content,encoding="utf-8");temporary.replace(path)
            sample.validation=report
        accepted=sum(report["passed"] for _,report,_,_ in prepared)
        job.status="completed" if accepted==len(samples) else "review_required"
        return {"total":len(samples),"accepted":accepted,"rejected":len(samples)-accepted,
                "status":job.status,"images_changed":False}
