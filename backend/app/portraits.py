"""Local fictional illustrations, approved photo pools and opt-in provider imports."""
import hashlib
import io
import json
import socket
import ipaddress
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


def save_portrait(content: bytes, root: Path, *, source: str, license_note: str, attribution: str = "") -> dict:
    if len(content)>8*1024**2: raise ValueError("Portrait exceeds 8 MB")
    with Image.open(io.BytesIO(content)) as original:
        if original.width*original.height>8_000_000 or max(original.size)>10000 or getattr(original,"n_frames",1)!=1:
            raise ValueError("Portrait must be one image, at most 8 megapixels")
        image=ImageOps.exif_transpose(original).convert("RGBA")
        background=Image.new("RGBA",image.size,"white");background.alpha_composite(image)
        background=background.convert("RGB");background.thumbnail((1200,1200))
    id_=uid();folder=root/"portraits"/id_;folder.mkdir(parents=True)
    path=folder/"image.png";background.save(path)
    record={"id":id_,"source":source,"license_note":license_note,"attribution":attribution,
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"preview_url":f"/api/portraits/{id_}/image"}
    (folder/"metadata.json").write_text(json.dumps(record,ensure_ascii=False),encoding="utf-8")
    return record


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
