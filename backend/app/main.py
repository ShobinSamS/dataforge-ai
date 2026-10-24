"""Loopback-only API. Run a single Uvicorn process; see README security boundary."""
import asyncio
import json
import io
import base64
import random
import logging
import threading
import tempfile
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode
import psutil
from fastapi import FastAPI, UploadFile, HTTPException, Request, Query, Form, Depends
from pydantic import Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select, func, delete
from .config import settings
from .db import Template, TemplateVersion, DeletedTemplate, Job, Sample, Export, connect, uid
from .demo import certificate, demo_regions
from .ingest import ingest
from .jobs import Worker, next_hash
from .privacy import check_review, sanitize_regions
from .schemas import Review, GenerationConfig, ExportRequest, Region, CLASS_NAMES, Contract, region_action
from .exporting import export_zip
from .resources import CPU_LOCK
from .text_api import text_router, active_count
from .document_rules import InterpretRuleRequest, known_plan, interpret_local, apply_plan, normalize_regions
from .format_references import format_references
from .fonts import installed_fonts, load_font, match_font, prepare_typography
from PIL import Image
from .portraits import save_portrait, save_portrait_batch, MAX_BATCH_BYTES, portrait_metadata, fetch_configured_portrait
from .document_analysis import analysis_router
from .qr_capacity import qr_preflight, check_qr_capacity
from .dataset_delete import dataset_delete_router
from .signatures import signature_plan,render_signature
from .schemas import RuleOptions,SignatureStyle
from .seals import plan_seal_content,render_seal
from .asset_api import asset_router
from .stamps import plan_stamp, plan_rubber_stamp
from .canvas import CanvasRequest, CanvasPreview, create_canvas, canvas_info
from .addresses import country_catalog,generate_address
from .diffusion import DiffusionJobs, diffusion_router, capabilities as diffusion_capabilities
from .seal_artwork import load_emblem


class OnlinePortraitRequest(Contract):
    confirm_online: bool = False
    rights_confirmed: bool = False
    license_note: str = Field(default="User confirmed provider image permission for dataset use",min_length=1,max_length=1000)
    attribution: str = Field(default="",max_length=1000)


class FontMatchRequest(Contract):
    region: Region


class SealPreviewRequest(Contract):
    options: RuleOptions = Field(default_factory=RuleOptions)
    seed: int = Field(default=42,ge=0,le=2**31-1)
    width: int = Field(default=400,ge=16,le=2048)
    height: int = Field(default=240,ge=16,le=2048)
    literal: str | None = Field(default=None,max_length=1000)
    region_id: str = Field(default="seal",min_length=1,max_length=80)


class AddressPreviewRequest(Contract):
    options: RuleOptions = Field(default_factory=RuleOptions)
    seed: int = Field(default=42,ge=0,le=2**31-1)

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
queue_lock = threading.Lock()


def template_json(t: Template) -> dict:
    return {"id":t.id,"name":t.name,"width":t.width,"height":t.height,"regions":t.regions,
            "warnings":t.warnings,"engine":t.engine,"revision":t.revision,
            "privacy_confirmed":t.privacy_confirmed,"created_at":t.created_at.isoformat(),
            "canvas":canvas_info(t.image_path) if t.engine=="canvas" else None}


def job_json(j: Job) -> dict:
    return {"id":j.id,"template_id":j.template_id,"name":j.name,"status":j.status,
            "config":j.config,"total":j.total,"completed":j.completed,"error":j.error,
            "metrics":j.metrics,"created_at":j.created_at.isoformat()}


def create_app(database_url: str | None = None, root: Path | None = None, start_worker: bool = True) -> FastAPI:
    root = (root or settings.data_dir).resolve()
    root.mkdir(parents=True,exist_ok=True)
    engine, sessions = connect(database_url or settings.database_url)
    worker = Worker(sessions,root)
    image_jobs = DiffusionJobs(root)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            worker.start()
        yield
        image_jobs.close()
        if start_worker:
            worker.close()
        engine.dispose()

    app = FastAPI(title="DataForge AI",version="0.1.0",lifespan=lifespan,
                  description="Local CPU dataset workspace. No cloud inference.")
    app.state.sessions = sessions
    app.state.worker = worker
    app.state.image_jobs = image_jobs
    app.include_router(text_router(sessions,root,queue_lock))
    app.include_router(dataset_delete_router(sessions,root,queue_lock))
    app.include_router(analysis_router(sessions,root))
    app.include_router(asset_router(root))
    app.include_router(diffusion_router(image_jobs))
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=["localhost","127.0.0.1","testserver"])
    origins = ["http://localhost:5173","http://127.0.0.1:5173","http://localhost:8000","http://127.0.0.1:8000"]
    origins.extend([f"http://localhost:{settings.api_port}",f"http://127.0.0.1:{settings.api_port}"])
    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=["GET","POST","PUT","DELETE"],allow_headers=["Content-Type"])

    @app.middleware("http")
    async def origin_guard(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return JSONResponse({"detail":"Only the local DataForge UI can access this API"},status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail":"Cross-site requests are disabled"},status_code=403)
        try:
            content_length = int(request.headers.get("content-length","0"))
        except ValueError:
            return JSONResponse({"detail":"Invalid Content-Length"},status_code=400)
        if content_length > 21*1024**2:
            return JSONResponse({"detail":"Request exceeds 20 MB upload limit"},status_code=413)
        if request.method == "POST" and request.url.path == "/api/templates" and "content-length" not in request.headers:
            return JSONResponse({"detail":"Upload requires a bounded Content-Length"},status_code=411)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail":str(exc)},status_code=422)

    def require(db, model, id_):
        row = db.get(model,id_)
        if row is None or (model is Template and db.get(DeletedTemplate,id_) is not None):
            raise HTTPException(404,"Record not found")
        return row

    def check_assets(regions):
        for r in regions:
            if region_action(r)=="replace" and r.kind=="seal" and r.rule_options.seal_artwork_id:
                portrait_metadata(root,r.rule_options.seal_artwork_id)
            if region_action(r)=="replace" and r.kind=="seal":
                for id_ in r.rule_options.seal_artwork_ids:portrait_metadata(root,id_)
            if region_action(r)=="replace" and r.kind not in {"portrait","signature","seal","stamp","rubber_stamp","qr","barcode","drawing"}:
                load_font(12,r.rule_options.font_id)
            if region_action(r)=="replace" and r.kind in {"portrait","stamp"} and r.rule_options.portrait_source=="asset_pool":
                if not r.rule_options.portrait_asset_ids: raise ValueError("Select at least one approved portrait image")
                for id_ in r.rule_options.portrait_asset_ids: portrait_metadata(root,id_)

    @app.post("/api/document-rules/interpret")
    def interpret_rule(body: InterpretRuleRequest):
        plan=known_plan(body.region) if body.engine=="auto" else None
        engine_name="deterministic"
        warnings=["Review the interpreted action, type and options before confirming", "Portraits require approved assets for photographic output; offline portraits are illustrations", "Synthetic provenance is recorded in dataset metadata"]
        if plan is None:
            from .local_llm import LocalLLM
            llm=LocalLLM()
            try: resident=llm.resident_cpu_mb()
            finally: llm.close()
            if psutil.virtual_memory().available/1024**2<max(settings.min_available_mb,settings.llm_min_available_mb-resident):
                raise HTTPException(409,"Not enough free memory for rule interpretation; use explicit controls or free memory first")
            if not CPU_LOCK.acquire(blocking=False): raise HTTPException(409,"CPU worker is busy; retry interpretation after the current workload")
            try:
                plan=interpret_local(body.region)
                # Unsupported/malformed model output must not prevent a known
                # format from working. Label the fallback explicitly in the UI.
                if not plan.supported: raise ValueError("The local model marked this instruction unsupported")
                apply_plan(body.region,plan)
                engine_name="local_qwen"
            except Exception as exc:
                fallback=known_plan(body.region)
                if fallback is None:
                    if isinstance(exc,ValueError):
                        reason="The model returned an invalid or unsupported plan."
                    else:
                        reason="The local model could not complete the request."
                    raise HTTPException(422,f"{reason} No rule was applied. Try an explicit pattern such as AAAAA9999A, or choose the action/type controls.") from exc
                plan=fallback;engine_name="known_rule_fallback"
                warnings.insert(0,"Local Qwen did not return an executable plan; the recognized rule was applied using the bundled format/reference instead.")
            finally: CPU_LOCK.release()
        region=apply_plan(body.region,plan)
        return {"region":region.model_dump(mode="json"),"engine":engine_name,"explanation":plan.explanation,
                "warnings":warnings,"references":format_references(body.region.rule)}

    @app.get("/api/portraits/capabilities")
    def portrait_capabilities():
        return {"offline_illustration":True,"upload":True,"online_configured":bool(settings.allow_online_portraits and settings.portrait_provider_url),
                "automatic_scraping":False,"max_pool_size":20,"max_upload_mb":8,"batch_upload":True,"zip_upload":True,"max_batch_mb":40}

    @app.get("/api/fonts")
    def fonts():
        return [{k:v for k,v in record.items() if k!="path"} for record in installed_fonts().values()]

    @app.get("/api/addresses/countries")
    def address_countries():
        return country_catalog()

    @app.post("/api/addresses/preview")
    def address_preview(body: AddressPreviewRequest):
        return generate_address(body.options,body.seed)

    @app.post("/api/templates/{id_}/font-match")
    def template_font_match(id_: str, body: FontMatchRequest):
        r=body.region
        with sessions() as db:
            t=require(db,Template,id_)
            path=t.image_path
        with Image.open(path) as image:
            if r.box[0]+r.box[2]>image.width or r.box[1]+r.box[3]>image.height or r.box[2]*r.box[3]>2_000_000:
                raise ValueError("Font sample must be inside the page and at most 2 megapixels")
            text=r.text
            if not text.strip():
                from .ingest import ocr
                x,y,w,h=r.box
                suggestions,_,_=ocr(image.crop((x,y,x+w,y+h)))
                text=" ".join(value["text"] for value in suggestions)
            result=match_font(image,r.box,text,r.rule_options.font_weight)
        updated=Region.model_validate({**r.model_dump(),"confirmed":False,"text":text,
            "rule_options":{**r.rule_options.model_dump(),**{k:result[k] for k in ("font_id","font_size","text_color")}}})
        return {"region":updated.model_dump(mode="json"),"match":result}

    @app.post("/api/portraits",status_code=201)
    def upload_portrait(file: UploadFile, rights_confirmed: bool = Form(False), license_note: str = Form("User-approved image"), attribution: str = Form("")):
        if not rights_confirmed: raise HTTPException(422,"Confirm permission to use this portrait for the dataset")
        if len(license_note)>1000 or len(attribution)>1000: raise ValueError("Portrait attribution/permission note exceeds limit")
        try:
            return save_portrait(file.file.read(8*1024**2+1),root,source="user_uploaded",license_note=license_note,attribution=attribution)
        except Exception as exc:
            raise HTTPException(422,"Portrait must be a valid single image of at most 8 MB / 8 megapixels") from exc

    @app.post("/api/portraits/batch",status_code=201)
    def upload_portraits(files: list[UploadFile], rights_confirmed: bool=Form(False),
                         license_note: str=Form("User-approved images"), attribution: str=Form(""),
                         max_count: int=Form(20,ge=1,le=20)):
        if not rights_confirmed: raise HTTPException(422,"Confirm permission to use these images for the dataset")
        if len(license_note)>1000 or len(attribution)>1000: raise ValueError("Portrait attribution/permission note exceeds limit")
        if not files or len(files)>20: raise ValueError("Select 1 to 20 images or ZIP files")
        uploads=[];total=0
        for file in files:
            content=file.file.read(MAX_BATCH_BYTES-total+1);total+=len(content)
            if total>MAX_BATCH_BYTES: raise ValueError("Batch upload exceeds 40 MB")
            uploads.append((file.filename or "image.png",content))
        records=save_portrait_batch(uploads,root,max_count=max_count,license_note=license_note,attribution=attribution)
        return {"portraits":records,"count":len(records)}

    @app.post("/api/portraits/fetch",status_code=201)
    def fetch_portrait(body: OnlinePortraitRequest):
        if not body.confirm_online or not body.rights_confirmed: raise HTTPException(422,"Explicitly confirm the download and image usage rights")
        try:
            content,source=fetch_configured_portrait()
            return save_portrait(content,root,source=source,license_note=body.license_note,attribution=body.attribution)
        except Exception as exc:
            raise HTTPException(422,"Portrait fetch failed. Configure a permitted public HTTPS image provider, or upload a photo. No template content was transmitted.") from exc

    @app.get("/api/portraits/{id_}/image")
    def portrait_image(id_: str):
        portrait_metadata(root,id_)
        return FileResponse(root/"portraits"/id_/"image.png",media_type="image/png")

    def store_template(content: bytes, suffix: str, name: str, demo: bool = False):
        id_ = uid()
        dest = root/"templates"/id_/"page.png"
        try:
            w,h,regions,ocr_engine,warnings = ingest(content,suffix,dest)
        except Exception as exc:
            raise HTTPException(422,f"Cannot analyze upload: {str(exc)[:250]}") from exc
        if demo:
            regions = demo_regions(regions)
            warnings.append("Demo visual-object boxes are authored fixture regions, not automatic detections.")
        with sessions.begin() as db:
            t = Template(id=id_,name=name[:200],image_path=str(dest),width=w,height=h,
                         regions=regions,engine=ocr_engine,warnings=warnings)
            db.add(t)
            db.flush()
            result = template_json(t)
            db.add(TemplateVersion(template_id=t.id,revision=1,snapshot=result))
            return result

    @app.get("/api/system")
    def system():
        from .vision_ocr import capabilities as vision_capabilities
        import shutil
        return {"version":"0.1.0","mode":"local-cpu","worker_count":1,"api_port":settings.api_port,
                "available_ram_mb":round(psutil.virtual_memory().available/1024**2),
                "process_rss_mb":round(psutil.Process().memory_info().rss/1024**2),
                "ocr":{"configured":settings.ocr_engine,"paddle_local_models":bool(settings.paddle_det_dir and settings.paddle_rec_dir),
                       "tesseract":bool(settings.tesseract_cmd or shutil.which("tesseract"))},
                "capabilities":{"procedural":True,"pdf_text":True,"yolo":True,"coco":True,"ocr_export":True,
                                "blank_canvas":True,"transparent_canvas":True,"freehand_drawing":True,"photo_backgrounds":True,
                                "country_addresses":True,
                                "visual_region_proposals":True,"synthetic_stamps":True,
                                "text_datasets":True,"llm":True,"local_llm_adapter":True,"document_rule_planner":True,"portrait_fields":True,"erase_regions":True,"font_matching":True,"custom_pattern_templates":True,"qr_controls":True,"pii_suggestions":True,"ruled_table_extraction":True,"transparent_codes":True,"trocr":any(vision_capabilities()["models"].values()),"diffusion":diffusion_capabilities(root)["ready"],"diffusion_adapter":True,"presidio":False,"mcp":True,"rag":False},
                "privacy":"Template images and OCR stay local. Only explicit provider portrait downloads use the internet. Detection requires manual review."}

    @app.get("/api/templates")
    def templates():
        with sessions() as db:
            return [template_json(t) for t in db.scalars(select(Template).where(~Template.id.in_(select(DeletedTemplate.template_id))).order_by(Template.created_at.desc()))]

    @app.delete("/api/templates/{id_}")
    def delete_template(id_: str, revision: int = Query(ge=1)):
        # Serialize with job submission: a source cannot disappear between the
        # dependency check and creation of a new job snapshot.
        with queue_lock, sessions.begin() as db:
            t=require(db,Template,id_)
            if t.revision!=revision:
                raise HTTPException(409,"Template changed; reload the library before deleting")
            jobs_count=db.scalar(select(func.count()).select_from(Job).where(Job.template_id==id_))
            source=Path(t.image_path).resolve()
            if jobs_count:
                db.add(DeletedTemplate(template_id=id_))
            else:
                db.execute(delete(TemplateVersion).where(TemplateVersion.template_id==id_))
                db.delete(t)
        removed=False;warnings=[]
        if not jobs_count:
            # Never recursively delete or follow an arbitrary stored file path.
            storage=(root/"templates").resolve()
            expected=(storage/id_/"page.png").resolve()
            if source==expected and source.is_relative_to(storage) and expected.parent.parent==storage:
                try:
                    source.unlink(missing_ok=True)
                    removed=True
                    try: source.parent.rmdir()  # only an empty, verified template directory
                    except OSError: pass
                except OSError:
                    warnings.append("Template removed from the library, but its local source image could not be removed.")
            else:
                warnings.append("Template removed from the library; its source was outside canonical template storage and was retained.")
        return {"id":id_,"deleted":True,"retained_for_jobs":bool(jobs_count),"job_count":jobs_count,"source_removed":removed,"warnings":warnings}

    @app.post("/api/templates",status_code=201)
    def upload(file: UploadFile):
        content = file.file.read(20*1024**2+1)
        if len(content) > 20*1024**2:
            raise HTTPException(413,"Upload exceeds 20 MB")
        if not content:
            raise HTTPException(422,"Empty upload")
        return store_template(content,Path(file.filename or "").suffix.lower(),Path(file.filename or "Template").name)

    @app.post("/api/templates/demo",status_code=201)
    def demo():
        return store_template(certificate(),".pdf","Northstar · fictional certificate",True)

    @app.post("/api/templates/blank",status_code=201)
    def blank_template(body: CanvasRequest):
        id_=uid(); path=root/"templates"/id_/"page.png"
        (w,h),regions=create_canvas(body,path)
        with sessions.begin() as db:
            t=Template(id=id_,name=body.name,image_path=str(path),width=w,height=h,
                       regions=regions,engine="canvas",warnings=[])
            db.add(t);db.flush();result=template_json(t)
            db.add(TemplateVersion(template_id=id_,revision=1,snapshot=result))
        return result

    @app.post("/api/templates/{id_}/preview")
    def canvas_preview(id_: str, body: CanvasPreview):
        from .render import render_sample
        with sessions() as db:
            t=require(db,Template,id_)
            if t.engine!="canvas": raise HTTPException(422,"Preview from scratch is available for blank canvases")
            path=Path(t.image_path); w,h=t.width,t.height
        if sum(r.box[2]*r.box[3] for r in body.regions)>4*w*h:
            raise ValueError("Combined region area exceeds resource limit")
        if body.regions:
            check_review([r.model_copy(update={"sensitive":False}) for r in body.regions],w,h,True,allow_overlap=True)
        check_assets(body.regions)
        config=GenerationConfig(template_id=id_,count=1,seed=body.seed,blur_probability=0,rotation_probability=0,barcodes=True)
        with CPU_LOCK, tempfile.TemporaryDirectory(prefix="dataforge-canvas-") as folder:
            result=render_sample(path,body.regions,config,0,Path(folder),asset_root=root)
            buffer=io.BytesIO();result["image"].save(buffer,format="PNG",dpi=(canvas_info(path)["dpi"],)*2)
        return {"image":"data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode(),
                "width":w,"height":h,"annotations":result["annotations"],"errors":result["errors"]}

    @app.get("/api/templates/{id_}")
    def template(id_: str):
        with sessions() as db:
            return template_json(require(db,Template,id_))

    @app.get("/api/templates/{id_}/image")
    def template_image(id_: str):
        with sessions() as db:
            return FileResponse(require(db,Template,id_).image_path,media_type="image/png")

    @app.put("/api/templates/{id_}/review")
    def review(id_: str, body: Review):
        reviewed_regions=normalize_regions(body.regions,strict=body.privacy_confirmed)
        check_assets(reviewed_regions)
        with sessions.begin() as db:
            t = require(db,Template,id_)
            if t.revision != body.revision:
                raise HTTPException(409,"Template changed; reload before saving")
            if body.privacy_confirmed:
                check_review(reviewed_regions,t.width,t.height,True,allow_overlap=t.engine=="canvas")
            else:
                # Drafts allow unconfirmed fields, but still enforce geometry and unique IDs.
                sanitized = [r.model_copy(update={"sensitive":False}) for r in reviewed_regions]
                check_review(sanitized,t.width,t.height,True,allow_overlap=t.engine=="canvas")
            if sum(r.box[2]*r.box[3] for r in body.regions) > 4*t.width*t.height:
                raise ValueError("Combined region area exceeds resource limit")
            t.regions = [r.model_dump(mode="json") for r in reviewed_regions]
            t.privacy_confirmed = body.privacy_confirmed
            t.revision += 1
            result = template_json(t)
            db.add(TemplateVersion(template_id=t.id,revision=t.revision,snapshot=result))
            return result

    @app.post("/api/jobs/preflight")
    def preflight_job(body: GenerationConfig):
        with sessions() as db:
            t=require(db,Template,body.template_id)
            reviewed_regions=normalize_regions([Region.model_validate(r) for r in t.regions],strict=True)
            return {**qr_preflight(reviewed_regions,body),"template_revision":t.revision}

    def signature_ink_options(ink_opacity_mode: Literal["random","fixed"]="random",
                              ink_opacity: float=Query(1,ge=.05,le=1,allow_inf_nan=False),
                              ink_opacity_min: float=Query(.45,ge=.05,le=1,allow_inf_nan=False),
                              ink_opacity_max: float=Query(1,ge=.05,le=1,allow_inf_nan=False),
                              ink_finish: Literal["clean","natural","worn"]="natural",
                              ink_irregularity: float=Query(.55,ge=0,le=1,allow_inf_nan=False),
                              signature_thickness: float=Query(1,ge=1,le=5,allow_inf_nan=False),
                              signature_content: Literal["current","name","alphabet","mixed"]="current",
                              color_mode: Literal["black","auto","manual","random","mixed"]="black",
                              text_color: str=Query("#000000",pattern=r"^#[0-9a-fA-F]{6}$"),
                              color_palette: list[str]=Query(["#000000","#173574","#a61c32","#216e39","#6a338e"]),
                              font_weight: Literal["auto","normal","bold"]="auto"):
        return RuleOptions(ink_opacity_mode=ink_opacity_mode,ink_opacity=ink_opacity,
                           ink_opacity_min=ink_opacity_min,ink_opacity_max=ink_opacity_max,
                           ink_finish=ink_finish,ink_irregularity=ink_irregularity,
                           signature_thickness=signature_thickness,font_weight=font_weight,signature_content=signature_content,
                           color_mode=color_mode,text_color=text_color,color_palette=color_palette)

    @app.get("/api/signatures/previews")
    def signature_previews(style: SignatureStyle="mixed",seed: int=Query(42,ge=0,le=2**31-1),
                           ink: RuleOptions=Depends(signature_ink_options)):
        names=("Arun Kumar","Mira Dev","Rohan Sen","Nila Shah","Dev Mehra","Sara Das")
        opacity_query=urlencode({key:value for key,value in ink.model_dump().items() if key.startswith("ink_") or key in {"signature_thickness","signature_content","font_weight","color_mode","text_color","color_palette"}},doseq=True)
        return [{"style":signature_plan(name,random.Random((seed+i)%(2**31)),RuleOptions(signature_style=style))["style"],
                 "url":f"/api/signatures/preview?style={style}&seed={(seed+i)%(2**31)}&name_index={i}&v=5&{opacity_query}"} for i,name in enumerate(names)]

    @app.post("/api/seals/preview")
    def seal_preview(body: SealPreviewRequest):
        content=plan_seal_content(body.options,body.seed,body.region_id,literal=body.literal)
        emblem,provenance=load_emblem(root,body.options.seal_artwork_id,body.options.seal_artwork_ids,body.seed)
        with CPU_LOCK:
            layer,_,metadata=render_seal((body.width,body.height),content,random.Random(body.seed),body.options,emblem)
            if provenance: metadata['asset_provenance']=provenance
            buffer=io.BytesIO();layer.save(buffer,format="PNG")
        return {"image":"data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode(),"metadata":metadata}

    @app.get("/api/signatures/preview")
    def signature_preview(style: SignatureStyle="mixed",seed: int=Query(42,ge=0,le=2**31-1),name_index: int=Query(0,ge=0,le=5),
                          ink: RuleOptions=Depends(signature_ink_options)):
        names=("Arun Kumar","Mira Dev","Rohan Sen","Nila Shah","Dev Mehra","Sara Das")
        with CPU_LOCK:
            options=ink.model_copy(update={"signature_style":style})
            layer,_,info=render_signature((480,160),names[name_index],random.Random(seed),options)
            buffer=io.BytesIO();layer.save(buffer,format="PNG")
        return Response(buffer.getvalue(),media_type="image/png",headers={"Cache-Control":"no-store","X-Signature-Style":info["style"],"X-Ink-Opacity":str(info["opacity"]),"X-Ink-Finish":info['ink_finish']['mode']})

    @app.post("/api/jobs",status_code=201)
    def generate(body: GenerationConfig):
        if body.count > settings.max_samples:
            raise ValueError(f"Maximum configured samples is {settings.max_samples}")
        with queue_lock, sessions.begin() as db:
            if active_count(db) >= 8:
                raise HTTPException(429,"Queue full; wait for a job to finish")
            t = require(db,Template,body.template_id)
            reviewed_regions=normalize_regions([Region.model_validate(r) for r in t.regions],strict=True)
            check_review(reviewed_regions,t.width,t.height,t.privacy_confirmed,allow_overlap=t.engine=="canvas")
            check_qr_capacity(reviewed_regions,body)
            if body.seals:
                for region in reviewed_regions:
                    if region.kind=="seal" and region_action(region)=="replace":
                        literal=region.rule[8:] if region.rule.startswith("literal:") else None
                        plan_seal_content(region.rule_options,body.seed,region.id,literal)
            for region in reviewed_regions:
                if region_action(region)!="replace": continue
                literal=region.rule[8:] if region.rule.startswith("literal:") else None
                if region.kind=="stamp" and body.stamps:
                    if min(region.box[2:])<64: raise ValueError("Paper stamp regions need at least 64×64 pixels")
                    plan_stamp(region.rule_options,body.seed,region.id,literal)
                if region.kind=="rubber_stamp" and body.rubber_stamps:
                    plan_rubber_stamp(region.rule_options,body.seed,region.id,literal)
            if t.engine!="canvas": reviewed_regions=prepare_typography(Path(t.image_path),reviewed_regions)
            check_assets(reviewed_regions)
            if body.qr_required and not any(region_action(r)=="replace" and r.kind=="qr" for r in reviewed_regions):
                raise ValueError("QR is required: add and verify a QR replacement region in this template")
            snapshot = {"width":t.width,"height":t.height,"image_path":t.image_path,
                        "regions":sanitize_regions([r.model_dump(mode="json") for r in reviewed_regions]),"revision":t.revision,"privacy_confirmed":True,
                        "source_sha256":next_hash(Path(t.image_path)),"engine":t.engine,
                        "canvas":canvas_info(t.image_path) if t.engine=="canvas" else None}
            j = Job(template_id=t.id,name=body.name,config=body.model_dump(mode="json"),template_snapshot=snapshot,total=body.count)
            db.add(j); db.flush()
            return job_json(j)

    @app.get("/api/jobs")
    def jobs():
        with sessions() as db:
            return [job_json(j) for j in db.scalars(select(Job).order_by(Job.created_at.desc()))]

    @app.get("/api/jobs/{id_}")
    def job(id_: str):
        with sessions() as db:
            return job_json(require(db,Job,id_))

    @app.post("/api/jobs/{id_}/cancel")
    def cancel(id_: str):
        with sessions.begin() as db:
            j = require(db,Job,id_)
            if j.status == "queued":
                j.status = "cancelled"
            elif j.status == "running":
                j.status = "cancelling"
            else:
                raise HTTPException(409,"Job is not active")
            return job_json(j)

    @app.post("/api/jobs/{id_}/resume")
    def resume(id_: str):
        with queue_lock, sessions.begin() as db:
            j = require(db,Job,id_)
            if j.status not in {"cancelled","paused","failed"}:
                raise HTTPException(409,"Job cannot be resumed in its current state")
            if active_count(db) >= 8:
                raise HTTPException(429,"Queue full")
            snapshot_regions=[Region.model_validate(r) for r in j.template_snapshot["regions"]]
            try:check_qr_capacity(snapshot_regions,GenerationConfig.model_validate(j.config))
            except ValueError as exc:
                raise HTTPException(422,f"This job keeps its original QR settings. {exc} Edit the template/settings and create a new job; resuming cannot apply those edits.") from exc
            j.status = "queued"; j.error = ""
            return job_json(j)

    @app.get("/api/jobs/{id_}/events")
    async def events(id_: str, request: Request):
        with sessions() as db:
            require(db,Job,id_)
        async def stream():
            while not await request.is_disconnected():
                with sessions() as db:
                    j = db.get(Job,id_)
                    if j is None:return
                    data = job_json(j)
                yield f"data: {json.dumps(data)}\n\n"
                if data["status"] not in {"queued","running","cancelling"}:
                    break
                await asyncio.sleep(1)
        return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache"})

    @app.get("/api/jobs/{id_}/samples")
    def samples(id_: str, offset: int = Query(0,ge=0), limit: int = Query(24,ge=1,le=100)):
        with sessions() as db:
            require(db,Job,id_)
            return [{"id":s.id,"index":s.index,"annotations":s.annotations,"validation":s.validation,"sha256":s.sha256}
                    for s in db.scalars(select(Sample).where(Sample.job_id == id_).order_by(Sample.index).offset(offset).limit(limit))]

    @app.get("/api/samples/{id_}/image")
    def sample_image(id_: str):
        with sessions() as db:
            return FileResponse(require(db,Sample,id_).path,media_type="image/png")

    @app.get("/api/jobs/{id_}/quality")
    def quality(id_: str):
        with sessions() as db:
            j = require(db,Job,id_)
            rows = list(db.scalars(select(Sample).where(Sample.job_id == id_)))
            classes = Counter(a["class"] for s in rows for a in s.annotations)
            return {"total":len(rows),"accepted":sum(s.validation["passed"] for s in rows),
                    "rejected":sum(not s.validation["passed"] for s in rows),"classes":dict(classes),
                    "errors":dict(Counter(e for s in rows for e in s.validation["errors"])),
                    "training_ready":False,"privacy_status":"manual-review-required","metrics":j.metrics,
                    "not_checked":["Undetected PII","OCR transcription accuracy","Barcode decode","Statistical utility"]}

    @app.post("/api/jobs/{id_}/revalidate")
    def recheck_job(id_:str):
        from .revalidation import revalidate_job
        with queue_lock:
            with sessions() as db:
                j=require(db,Job,id_)
                if j.status not in {"completed","review_required"}:raise HTTPException(409,"Wait for generation to finish before rechecking samples")
            if not CPU_LOCK.acquire(blocking=False):raise HTTPException(409,"CPU worker is busy; retry after the current workload")
            try:return revalidate_job(sessions,id_)
            finally:CPU_LOCK.release()

    @app.post("/api/jobs/{id_}/exports",status_code=201)
    def export(id_: str, body: ExportRequest):
        if not body.review_confirmed:
            raise ValueError("Review generated samples and confirm privacy before export")
        with queue_lock,sessions.begin() as db:
            j = require(db,Job,id_)
            if j.status not in {"completed","review_required"}:
                raise HTTPException(409,"Wait for generation to finish before export")
            rows = [s for s in db.scalars(select(Sample).where(Sample.job_id == id_).order_by(Sample.index)) if s.validation["passed"]]
            if not rows:
                raise ValueError("No accepted samples to export")
            id_export = uid()
            with CPU_LOCK:
                path = export_zip(j,rows,body.format,root/"exports"/f"{id_export}.zip")
            db.add(Export(id=id_export,job_id=id_,format=body.format,path=str(path)))
            return {"id":id_export,"count":len(rows),"format":body.format,"download_url":f"/api/exports/{id_export}/download"}

    @app.get("/api/exports")
    def exports():
        with sessions() as db:
            return [{"id":e.id,"job_id":e.job_id,"format":e.format,"created_at":e.created_at.isoformat(),
                     "download_url":f"/api/exports/{e.id}/download"} for e in db.scalars(select(Export).order_by(Export.created_at.desc()))]

    @app.get("/api/exports/{id_}/download")
    def download(id_: str):
        with sessions() as db:
            e = require(db,Export,id_)
            return FileResponse(e.path,filename=f"dataforge-{e.job_id[:8]}-{e.format}.zip",media_type="application/zip")

    return app


app = create_app()
