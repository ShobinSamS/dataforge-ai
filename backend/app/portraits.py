"""Local fictional illustrations, approved photo pools and opt-in provider imports."""
import hashlib
import io
import json
import socket
import ipaddress
import zipfile
import stat
from pathlib import PurePosixPath
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .db import uid
from .config import settings


def illustration(size: tuple[int,int], rng) -> Image.Image:
    image=Image.new("RGB",(300,400),rng.choice(["#dbe9ec","#e6e2d8","#dce4d9"]))
    d=ImageDraw.Draw(image);skin=rng.choice(["#f2d1ad","#d9a57e","#b67b53","#855739"])
    hair=rng.choice(["#352922","#161820","#675247","#a18b70"])
    d.ellipse((48,51,252,292),fill=hair)
    d.rounded_rectangle((118,228,182,322),radius=15,fill=skin)
    d.ellipse((22,281,278,480),fill=rng.choice(["#3f6080","#584b72","#527566","#755143"]))
    d.ellipse((72,79,228,274),fill=skin)
    d.pieslice((65,59,235,203),180,360,fill=hair)
    for x in [111,189]:
        d.ellipse((x-8,160,x+8,171),fill="white");d.ellipse((x-3,160,x+3,169),fill="#302c2c")
        d.line((x-12,149,x+10,147),fill=hair,width=4)
    d.line((148,172,140,199,154,200),fill="#986d55",width=3)
    d.arc((124,201,178,235),5,175,fill="#773f3f",width=3)
    return image.resize(size,Image.Resampling.LANCZOS)


def prepare_portrait(content: bytes) -> Image.Image:
    if len(content)>8*1024**2: raise ValueError("Portrait exceeds 8 MB")
    with Image.open(io.BytesIO(content)) as original:
        if original.width*original.height>8_000_000 or max(original.size)>10000 or getattr(original,"n_frames",1)!=1:
            raise ValueError("Portrait must be one image, at most 8 megapixels")
        image=ImageOps.exif_transpose(original).convert("RGBA")
        if image.getchannel("A").getextrema()[0]<255:
            background=image
        else:
            background=image.convert("RGB")
        background.thumbnail((1200,1200))
    return background


def portrait_background(image, options, seed=42):
    """Local approximate foreground cutout; existing PNG alpha takes priority."""
    import random
    import cv2
    import numpy as np
    from PIL import ImageFilter
    rgba=image.convert("RGBA")
    mode=options.portrait_background
    if mode=="preserve": return rgba
    alpha=rgba.getchannel("A")
    if alpha.getextrema()[0]==255:
        small=rgba.convert("RGB");small.thumbnail((720,720))
        pixels=np.asarray(small);h,w=pixels.shape[:2]
        border=max(1,round(min(w,h)*.025))
        corners=[pixels[:border,:border],pixels[:border,-border:],pixels[-border:,:border],pixels[-border:,-border:]]
        colors=np.array([np.median(p.reshape(-1,3),axis=0) for p in corners])
        distance=np.min(np.linalg.norm(pixels[:,:,None,:].astype(float)-colors[None,None,:,:],axis=3),axis=2)
        near=(distance<32).astype(np.uint8)
        _,labels=cv2.connectedComponents(near)
        boundary=np.unique(np.concatenate((labels[0],labels[-1],labels[:,0],labels[:,-1])))
        background=np.isin(labels,boundary[boundary!=0]) & (near>0)
        mask=np.where(background,cv2.GC_BGD,cv2.GC_PR_FGD).astype(np.uint8)
        # People often reach the lower photo edge. Forcing the entire border
        # to background removes their clothing. Seed only connected background
        # colors, plus a conservative interior foreground core.
        core=cv2.erode((~background).astype(np.uint8),np.ones((3,3),np.uint8))>0
        yy,xx=np.mgrid[:h,:w]
        core &= (xx>w*.25)&(xx<w*.75)&(yy>h*.12)&(yy<h*.95)
        mask[core]=cv2.GC_FGD
        if not np.any(np.isin(mask,(cv2.GC_PR_FGD,cv2.GC_FGD))):
            raise ValueError("No distinct foreground found. Use Keep background or upload a transparent PNG")
        cv2.setRNGSeed(42)
        try:
            cv2.grabCut(pixels.copy(),mask,None,np.zeros((1,65)),np.zeros((1,65)),3,cv2.GC_INIT_WITH_MASK)
            foreground=np.isin(mask,(cv2.GC_FGD,cv2.GC_PR_FGD)).astype(np.uint8)*255
        except cv2.error:
            foreground=(~background).astype(np.uint8)*255
        if np.count_nonzero(foreground)<w*h*.005:
            raise ValueError("Foreground cutout was empty. Use Keep background or upload a transparent PNG")
        alpha=Image.fromarray(foreground).filter(ImageFilter.GaussianBlur(.55)).resize(rgba.size,Image.Resampling.LANCZOS)
        rgba.putalpha(alpha)
    if mode=="transparent": return rgba
    color=(random.Random(f"{seed}:photo-background").choice(options.portrait_background_palette)
           if mode=="random" else options.portrait_background_color)
    backdrop=Image.new("RGBA",rgba.size,color);backdrop.alpha_composite(rgba)
    return backdrop


def store_portrait(image: Image.Image, root: Path, *, source: str, license_note: str, attribution: str = "") -> dict:
    id_=uid();folder=root/"portraits"/id_;folder.mkdir(parents=True)
    try:
        path=folder/"image.png";image.save(path)
        record={"id":id_,"source":source,"license_note":license_note,"attribution":attribution,
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"preview_url":f"/api/portraits/{id_}/image"}
        (folder/"metadata.json").write_text(json.dumps(record,ensure_ascii=False),encoding="utf-8")
    except Exception:
        (folder/"image.png").unlink(missing_ok=True)
        (folder/"metadata.json").unlink(missing_ok=True)
        folder.rmdir()
        raise
    return record


def save_portrait(content: bytes, root: Path, *, source: str, license_note: str, attribution: str = "") -> dict:
    return store_portrait(prepare_portrait(content),root,source=source,license_note=license_note,attribution=attribution)


MAX_BATCH_BYTES=40*1024**2
IMAGE_EXTENSIONS={".png",".jpg",".jpeg",".webp"}


def save_portrait_batch(files: list[tuple[str,bytes]], root: Path, *, max_count: int=20,
                        license_note: str, attribution: str="") -> list[dict]:
    """Validate the complete batch before saving. Read ZIP members without extraction."""
    if not 1<=max_count<=20: raise ValueError("Pool capacity must be between 1 and 20")
    if not files or len(files)>20: raise ValueError("Select 1 to 20 images or ZIP files")
    if sum(len(content) for _,content in files)>MAX_BATCH_BYTES: raise ValueError("Batch upload exceeds 40 MB")
    images=[];expanded=0
    def add(name,content):
        nonlocal expanded
        if len(images)>=max_count: raise ValueError(f"Batch exceeds the {max_count} remaining image slots; no images imported")
        expanded+=len(content)
        if expanded>MAX_BATCH_BYTES: raise ValueError("Uncompressed images exceed 40 MB")
        if PurePosixPath(name).suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError("Pool uploads support PNG, JPEG and WebP images only")
        try: images.append(prepare_portrait(content))
        except Exception as exc: raise ValueError("Batch contains an invalid image; each image must be at most 8 MB / 8 megapixels") from exc
    for name,content in files:
        if Path(name).suffix.lower()!=".zip":
            add(name,content);continue
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                members=archive.infolist()
                if len(members)>100: raise ValueError("ZIP has more than 100 entries")
                for member in members:
                    path=PurePosixPath(member.filename.replace("\\","/"))
                    if path.is_absolute() or ".." in path.parts or ":" in str(path) or stat.S_ISLNK(member.external_attr>>16):
                        raise ValueError("ZIP contains an unsafe path or symbolic link")
                    if member.is_dir() or "__MACOSX" in path.parts or path.name.startswith("."): continue
                    if member.flag_bits&1: raise ValueError("Encrypted ZIP files are not supported")
                    if member.file_size>8*1024**2: raise ValueError("An image in the ZIP exceeds 8 MB")
                    if expanded+member.file_size>MAX_BATCH_BYTES: raise ValueError("Uncompressed images exceed 40 MB")
                    if len(images)>=max_count: raise ValueError(f"Batch exceeds the {max_count} remaining image slots; no images imported")
                    with archive.open(member) as stream: raw=stream.read(8*1024**2+1)
                    add(str(path),raw)
        except (zipfile.BadZipFile,NotImplementedError,RuntimeError) as exc:
            raise ValueError("Cannot read ZIP; upload an unencrypted ZIP containing PNG, JPEG or WebP images") from exc
    if not images: raise ValueError("No supported images found in the upload")
    records=[]
    try:
        for image in images:
            records.append(store_portrait(image,root,source="user_uploaded",license_note=license_note,attribution=attribution))
    except Exception:
        # Only this request's new assets are eligible for cleanup.
        for record in records:
            folder=root/"portraits"/record["id"]
            (folder/"image.png").unlink(missing_ok=True)
            (folder/"metadata.json").unlink(missing_ok=True)
            folder.rmdir()
        raise
    return records


def portrait_metadata(root: Path, id_: str) -> dict:
    import re
    if not re.fullmatch(r"[a-f0-9]{32}",id_): raise ValueError("Invalid portrait ID")
    folder=root/"portraits"/id_
    try:
        metadata=json.loads((folder/"metadata.json").read_text(encoding="utf-8"))
        if hashlib.sha256((folder/"image.png").read_bytes()).hexdigest()!=metadata["sha256"]:
            raise ValueError("Portrait integrity check failed; import the image again")
        return metadata
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Portrait asset is missing; upload/select it again") from exc


def fetch_configured_portrait() -> tuple[bytes,str]:
    if not settings.allow_online_portraits or not settings.portrait_provider_url:
        raise ValueError("No approved online portrait provider is configured; use upload or offline illustration")
    parsed=urlsplit(settings.portrait_provider_url)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query or parsed.port not in {None,443}:
        raise ValueError("Portrait provider must be a public HTTPS URL without credentials, query or redirects")
    addresses=socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Portrait provider must resolve to public internet addresses")
    # The administrator supplies the fixed provider. The model/user request cannot supply URLs.
    chunks=[];total=0
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=30) as client:
        with client.stream("GET",settings.portrait_provider_url,headers={"Accept":"image/png,image/jpeg,image/webp"}) as response:
            response.raise_for_status()
            if response.headers.get("content-type","").split(";")[0] not in {"image/png","image/jpeg","image/webp"}:
                raise ValueError("Configured provider did not return a supported image")
            for chunk in response.iter_bytes():
                total+=len(chunk)
                if total>8*1024**2: raise ValueError("Portrait download exceeds 8 MB")
                chunks.append(chunk)
    return b"".join(chunks),settings.portrait_provider_url
