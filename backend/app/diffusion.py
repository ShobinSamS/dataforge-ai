"""Optional offline SD-Turbo previews, serialized with the app's CPU workloads."""
import hashlib
import zipfile
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import psutil
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from PIL import Image
from pydantic import Field, field_validator

from .db import uid
from .portraits import store_portrait, portrait_background, portrait_metadata
from .resources import CPU_LOCK
from .schemas import Contract, RuleOptions
from .image_prompts import generate_prompt, model_status

Kind = Literal["portrait", "seal_artwork", "stamp_artwork"]
PREFIXES = {
    "portrait": "Studio photograph of a fictional adult, centered head and shoulders, full head visible, plain light gray background, soft lighting. ",
    "seal_artwork": "Simple black line-art emblem on pure white, centered isolated monochrome engraving, without lettering or borders. ",
    "stamp_artwork": "Vintage stamp illustration, centered fine engraving, artwork only without lettering, numbers or borders. ",
}
REQUIRED = ("model_index.json", "unet/config.json", "unet/diffusion_pytorch_model.fp16.safetensors",
            "vae/config.json", "vae/diffusion_pytorch_model.fp16.safetensors", "text_encoder/config.json",
            "text_encoder/model.fp16.safetensors", "tokenizer/vocab.json", "tokenizer/merges.txt", "scheduler/scheduler_config.json", "manifest.json")
TERMINAL = {"completed", "failed", "cancelled"}


def worker_processes(pid):
    """Windows venv python.exe is a redirector: include its real Python child."""
    try:
        parent = psutil.Process(pid)
        return [parent, *parent.children(recursive=True)]
    except psutil.NoSuchProcess: return []


def terminate_worker(child):
    for process in reversed(worker_processes(child.pid)):
        try: process.kill()
        except psutil.NoSuchProcess: pass
    if child.poll() is None:
        child.kill()
    child.wait(timeout=10)


class DiffusionRequest(Contract):
    kind: Kind = "portrait"
    prompt: str = Field(min_length=3, max_length=600)
    seed: int = Field(default=42, ge=0, le=2**31-1)
    steps: int = Field(default=2, ge=1, le=4)
    count: int = Field(default=1, ge=1, le=100)
    prompt_mode: Literal['manual','qwen'] = 'manual'
    prompt_seed: int | None = Field(default=None,ge=0,le=2**31-1)
    background: Literal["preserve", "transparent", "solid"] = "preserve"
    background_color: str = "#ffffff"

    @field_validator("prompt")
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if len(value) < 3: raise ValueError("Describe the image in at least three characters")
        return value

    @field_validator("background_color")
    @classmethod
    def color(cls, value):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value): raise ValueError("Use a #RRGGBB background color")
        return value.lower()


def capabilities(root: Path):
    model = root/"models"/"sd-turbo"
    runtime = all(importlib.util.find_spec(name) is not None for name in ("torch", "transformers", "diffusers", "accelerate"))
    installed = all((model/name).is_file() for name in REQUIRED)
    return {"runtime": runtime, "model_installed": installed, "ready": runtime and installed,
            "model": "stabilityai/sd-turbo", "device": "cpu", "width": 512, "height": 512,
            "available_ram_mb": round(psutil.virtual_memory().available/1024**2),
            "minimum_available_ram_mb": 4500, "runtime_downloads": False,
            "setup_commands": [r".\.venv\Scripts\python.exe -m pip install -r requirements-vision.txt -r requirements-diffusion.txt",
                               r".\.venv\Scripts\python.exe scripts/setup_diffusion_model.py"],
            "model_url": "https://huggingface.co/stabilityai/sd-turbo"}


def run_worker(folder, model, request, cancelled, progress):
    (folder/'progress.json').unlink(missing_ok=True)
    script = Path(__file__).resolve().parents[2]/"scripts"/"diffusion_worker.py"
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
    started = time.monotonic(); peak = 0
    with (folder/"worker.log").open("w", encoding="utf-8") as log:
        child = subprocess.Popen([sys.executable, "-X", "utf8", str(script), "--folder", str(folder), "--model", str(model)],
            stdout=log, stderr=log, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            while child.poll() is None:
                if cancelled.wait(.4): raise InterruptedError("Generation cancelled")
                if time.monotonic()-started > 600: raise TimeoutError("Generation exceeded the 10-minute CPU limit; try one step")
                try: peak = max(peak, sum(p.memory_info().rss for p in worker_processes(child.pid)))
                except psutil.Error: pass
                try: progress(json.loads((folder/"progress.json").read_text(encoding="utf-8"))["step"])
                except (OSError, ValueError, KeyError): pass
            if cancelled.is_set(): raise InterruptedError("Generation cancelled")
            if child.returncode:
                raise ValueError("Stable Diffusion worker failed. Check the job's worker.log in the local data folder; no image was accepted")
        finally:
            if child.poll() is None:
                terminate_worker(child)
    result = json.loads((folder/"result.json").read_text(encoding="utf-8"))
    result["peak_worker_rss_mb"] = round(peak/1024**2)
    result["worker_wall_seconds"] = round(time.monotonic()-started, 2)
    return result


class DiffusionJobs:
    def __init__(self, root: Path):
        self.root = root
        self.folder = root/"diffusion"; self.folder.mkdir(exist_ok=True, parents=True)
        self.lock = threading.RLock(); self.jobs = {}; self.cancels = {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dataforge-diffusion")
        for path in self.folder.glob("*/job.json"):
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
                if job["status"] not in TERMINAL:
                    job.update(status="failed", error="App restarted before this preview finished; generate again")
                self.jobs[job["id"]] = job
            except (OSError, ValueError, KeyError): continue

    def write(self, job):
        path = self.folder/job["id"]/"job.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(job, indent=2), encoding="utf-8"); temp.replace(path)

    def get(self, id_):
        with self.lock:
            if id_ not in self.jobs: raise HTTPException(404, "Image generation job not found")
            job = dict(self.jobs[id_])
            if job.get('count',1)>1:
                items=[dict(self.jobs[child]) for child in job.get('child_ids',[]) if child in self.jobs]
                completed=[item for item in items if item['status']=='completed']
                job.update(items=items,completed=len(completed),saved_count=sum(bool(item.get('asset')) for item in completed),
                           download_url=f'/api/diffusion/jobs/{id_}/download' if completed else None)
                if completed:job['image_url']=completed[0]['image_url']
                active=next((item for item in items if item['status'] in {'running','cancelling'}),None)
                job['step']=active['step'] if active else 0
                job['active_index']=active.get('batch_index') if active else None
                job['stage']=active.get('stage') if active else None
            else:
                job['completed']=int(job['status']=='completed')
                job['count']=1
            return job

    def create_job(self, body, manifest, **extra):
        id_ = uid(); folder = self.folder/id_; folder.mkdir()
        request = {**body.model_dump(), "resolved_prompt": PREFIXES[body.kind]+body.prompt}
        if body.prompt_mode=='qwen' and body.prompt_seed is None:request['prompt_seed']=secrets.randbelow(2**31)
        (folder/"request.json").write_text(json.dumps(request), encoding="utf-8")
        job = {"id": id_, "status": "queued", "created_at": time.time(), **request,
               "model": manifest["repository"], "revision": manifest["revision"],
               "source_url": manifest.get("source_url", "https://huggingface.co/stabilityai/sd-turbo"),
               "license_url": manifest.get("license_url"), "step": 0, "error": None,
               "image_url": None, "asset": None, **extra}
        self.jobs[id_] = job; self.cancels[id_] = threading.Event(); self.write(job)
        return job

    def submit(self, body):
        caps = capabilities(self.root)
        if not caps["ready"]: raise HTTPException(409, "Install the optional Stable Diffusion runtime and model using the setup commands shown in AI image studio")
        with self.lock:
            if sum(j["status"] not in TERMINAL and not j.get('batch_id') for j in self.jobs.values()) >= 3:
                raise HTTPException(409, "Three image runs are already queued; wait or cancel one")
            manifest = json.loads((self.root/"models"/"sd-turbo"/"manifest.json").read_text(encoding="utf-8"))
            job = self.create_job(body,manifest,child_ids=[] if body.count>1 else None)
            self.pool.submit(self.run_batch if body.count>1 else self.run, job['id'])
            return self.get(job['id'])

    def run_batch(self, id_):
        cancel=self.cancels[id_]
        try:
            if cancel.is_set():raise InterruptedError()
            self.update(id_,status='running',error=None)
            for index in range(self.jobs[id_]['count']):
                if cancel.is_set():raise InterruptedError()
                with self.lock:
                    parent=self.jobs[id_]
                    child=next((self.jobs[c] for c in parent['child_ids'] if self.jobs[c]['batch_index']==index),None)
                    if child and child['status']=='completed':continue
                    if child:
                        self.cancels[child['id']]=threading.Event()
                        self.update(child['id'],status='queued',error=None,step=0)
                    else:
                        body=DiffusionRequest.model_validate({k:parent[k] for k in DiffusionRequest.model_fields if k in parent})
                        body=body.model_copy(update={'count':1,'seed':(body.seed+index)%(2**31),
                            'prompt_seed':(body.prompt_seed+index)%(2**31) if body.prompt_seed is not None else None})
                        manifest={'repository':parent['model'],'revision':parent['revision'],'source_url':parent['source_url'],'license_url':parent.get('license_url')}
                        child=self.create_job(body,manifest,batch_id=id_,batch_index=index)
                        parent['child_ids'].append(child['id']);self.write(parent)
                    if cancel.is_set():self.cancels[child['id']].set()
                self.run(child['id'])
                if cancel.is_set():raise InterruptedError()
                if self.jobs[child['id']]['status']!='completed':
                    raise ValueError(f"Image {index+1} failed: {self.jobs[child['id']].get('error') or 'generation stopped'}. Completed images are kept; resume to retry.")
            self.update(id_,status='completed')
        except InterruptedError:self.update(id_,status='cancelled',error=None)
        except Exception as exc:self.update(id_,status='failed',error=str(exc)[:1000])

    def resume(self, id_):
        with self.lock:
            job=self.get(id_)
            if job['count']<=1 or job['status'] not in {'cancelled','failed'}:
                raise HTTPException(409,'Resume is available for interrupted image batches')
            if job['completed']==job['count']:raise HTTPException(409,'All images are already complete')
            if not capabilities(self.root)['ready']:raise HTTPException(409,'Install the Stable Diffusion runtime and model first')
            if sum(j['status'] not in TERMINAL and not j.get('batch_id') for j in self.jobs.values())>=3:
                raise HTTPException(409,'Three image runs are already queued; wait or cancel one')
            self.cancels[id_]=threading.Event();self.update(id_,status='queued',error=None)
            self.pool.submit(self.run_batch,id_)
            return self.get(id_)

    def update(self, id_, **patch):
        with self.lock:
            self.jobs[id_].update(patch); self.write(self.jobs[id_])

    def run(self, id_):
        cancel = self.cancels[id_]; acquired = False; folder = self.folder/id_
        try:
            while not cancel.is_set():
                acquired = CPU_LOCK.acquire(timeout=.2)
                if acquired: break
            if cancel.is_set(): raise InterruptedError()
            image_started=time.monotonic()
            if psutil.virtual_memory().available/1024**2 < 4500:
                raise ValueError("Free at least 4.5 GB RAM before image generation; close other heavy apps and retry")
            self.update(id_, status="running")
            job = self.get(id_)
            if job.get('prompt_mode')=='qwen' and not job.get('generated_prompt'):
                self.update(id_,stage='planning_prompt')
                previous=[]
                if job.get('batch_id'):
                    with self.lock:
                        previous=[self.jobs[c].get('generated_prompt','') for c in self.jobs[job['batch_id']]['child_ids'] if c!=id_ and self.jobs[c].get('generated_prompt')]
                planning_started=time.monotonic()
                plan=generate_prompt(job['kind'],job['prompt'],job['prompt_seed'],previous,cancel)
                if cancel.is_set():raise InterruptedError()
                self.update(id_,**plan,prompt_planning_seconds=round(time.monotonic()-planning_started,2),resolved_prompt=PREFIXES[job['kind']]+plan['generated_prompt'])
                job=self.get(id_)
                (folder/'request.json').write_text(json.dumps(job),encoding='utf-8')
            if psutil.virtual_memory().available/1024**2<4500:
                raise ValueError('Free at least 4.5 GB RAM before image generation; the generated prompt is kept for resume')
            self.update(id_,stage='generating_image')
            metrics = run_worker(folder, self.root/"models"/"sd-turbo", job, cancel,
                                 lambda step: self.update(id_, step=min(step, job["steps"])))
            if cancel.is_set(): raise InterruptedError()
            with Image.open(folder/"raw.png") as opened:
                if opened.size != (512, 512): raise ValueError("Worker returned an unexpected image size")
                image = opened.convert("RGBA")
            # Emblem transparency comes from the dark ink, retaining antialiasing.
            if job["kind"] == "seal_artwork":
                from PIL import ImageOps
                alpha = ImageOps.invert(ImageOps.grayscale(image)).point(lambda p: max(0, min(255, (p-30)*255//190)))
                if alpha.getbbox() is None: raise ValueError("Generated emblem has no visible ink; try another prompt or seed")
                image = Image.new("RGBA", image.size, "black"); image.putalpha(alpha)
            elif job["background"] != "preserve":
                image = portrait_background(image, RuleOptions(portrait_background=job["background"], portrait_background_color=job["background_color"]), job["seed"])
            image.save(folder/"image.png")
            digest = hashlib.sha256((folder/"image.png").read_bytes()).hexdigest()
            metrics['image_wall_seconds']=round(time.monotonic()-image_started,2)
            metrics['prompt_planning_seconds']=job.get('prompt_planning_seconds',0)
            self.update(id_, status="completed", step=job["steps"], metrics=metrics, sha256=digest,
                        image_url=f"/api/diffusion/jobs/{id_}/image", raw_image_url=f"/api/diffusion/jobs/{id_}/image?raw=true")
        except InterruptedError: self.update(id_, status="cancelled", error=None)
        except Exception as exc: self.update(id_, status="failed", error=str(exc)[:1000])
        finally:
            if acquired: CPU_LOCK.release()

    def cancel(self, id_):
        with self.lock:
            job = self.get(id_)
            if job["status"] not in TERMINAL:
                self.cancels[id_].set()
                for child_id in job.get('child_ids') or []:
                    if self.jobs[child_id]['status'] not in TERMINAL:self.cancels[child_id].set()
                self.update(id_, status="cancelling")
            return self.get(id_)

    def save(self, id_, index=None):
        with self.lock:
            job = self.get(id_)
            if job['count']>1:
                if index is not None:
                    child=next((c for c in job['items'] if c['batch_index']==index),None)
                    if child is None:raise HTTPException(409,'This image has not been generated yet')
                    return self.save(child['id'])
                completed=[c for c in job['items'] if c['status']=='completed']
                if not completed:raise HTTPException(409,'No completed images to save yet')
                assets=[self.save(c['id']) for c in completed]
                return {'assets':assets,'saved_count':len(assets),'count':job['count'],'completed':len(completed)}
            if index not in (None,0):raise HTTPException(404,'Image index is outside this run')
            if job["status"] != "completed": raise HTTPException(409, "Only completed previews can be saved")
            if job["asset"]:
                try: return portrait_metadata(self.root, job["asset"]["id"])
                except (ValueError, HTTPException, FileNotFoundError): pass
            with Image.open(self.folder/id_/"image.png") as image:
                asset = store_portrait(image.copy(), self.root, source="local_stable_diffusion",
                    license_note="SD-Turbo generated image; see the model license for permitted use",
                    attribution=json.dumps({k:job[k] for k in ("model", "revision", "source_url", "license_url", "kind", "prompt", "resolved_prompt", "seed", "steps", "sha256",'prompt_mode','generated_prompt','prompt_seed','prompt_engine','prompt_model','prompt_model_digest') if k in job}))
            self.update(id_, asset=asset)
            return asset

    def download(self,id_):
        with self.lock:
            job=self.get(id_)
            items=job.get('items',[job]);completed=[item for item in items if item['status']=='completed']
            if not completed:raise HTTPException(409,'No completed images to download yet')
            path=self.folder/id_/f'images-{uid()}.zip'
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED) as archive:
                for item in completed:
                    index=item.get('batch_index',0)
                    archive.write(self.folder/item['id']/'image.png',f'{index+1:03d}.png')
                    archive.writestr(f'{index+1:03d}.json',json.dumps(item,indent=2))
                archive.writestr('batch.json',json.dumps({k:job[k] for k in ('id','kind','prompt','seed','steps','count','completed','status','prompt_mode','prompt_seed') if k in job},indent=2))
            return path

    def close(self):
        for event in self.cancels.values(): event.set()
        self.pool.shutdown(wait=True, cancel_futures=True)


def diffusion_router(jobs):
    router = APIRouter(prefix="/api/diffusion", tags=["Local image generation"])
    @router.get("/capabilities")
    def status(): return {**capabilities(jobs.root),'prompt_llm':model_status()}
    @router.post('/prompts/preview')
    def preview_prompt(body:DiffusionRequest):
        if not CPU_LOCK.acquire(blocking=False):raise HTTPException(409,'CPU worker is busy; try a prompt preview after the current image finishes')
        try:
            seed=body.prompt_seed if body.prompt_seed is not None else secrets.randbelow(2**31)
            plan=generate_prompt(body.kind,body.prompt,seed)
            return {**plan,'resolved_prompt':PREFIXES[body.kind]+plan['generated_prompt']}
        finally:CPU_LOCK.release()
    @router.post("/jobs")
    def generate(body: DiffusionRequest): return jobs.submit(body)
    @router.get("/jobs")
    def list_jobs():
        with jobs.lock: return [jobs.get(j['id']) for j in sorted((j for j in jobs.jobs.values() if not j.get('batch_id')),key=lambda j:j['created_at'],reverse=True)[:100]]
    @router.get("/jobs/{id_}")
    def get_job(id_: str): return jobs.get(id_)
    @router.post("/jobs/{id_}/cancel")
    def cancel(id_: str): return jobs.cancel(id_)
    @router.post("/jobs/{id_}/save")
    def save(id_: str, index: int | None = Query(default=None,ge=0,le=99)): return jobs.save(id_,index)
    @router.post('/jobs/{id_}/resume')
    def resume(id_: str):return jobs.resume(id_)
    @router.get('/jobs/{id_}/download')
    def download(id_: str):
        path=jobs.download(id_)
        return FileResponse(path,media_type='application/zip',filename=f'generated-images-{id_}.zip',background=BackgroundTask(path.unlink,missing_ok=True))
    @router.get("/jobs/{id_}/image")
    def image(id_: str, raw: bool = False):
        job = jobs.get(id_)
        if job["status"] != "completed": raise HTTPException(409, "Preview image is not ready")
        return FileResponse(jobs.folder/id_/("raw.png" if raw else "image.png"), media_type="image/png")
    return router
