"""Standalone procedural assets, using the same renderers as document jobs."""
import base64
import hashlib
import io
import random
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import Field, model_validator

from .schemas import Contract, RuleOptions, Region
from .resources import CPU_LOCK
from .render import asset, fictional_values
from .signatures import render_signature
from .seals import plan_seal_content, render_seal
from .portraits import illustration, portrait_metadata, portrait_background
from .stamps import plan_stamp, render_stamp, plan_rubber_stamp, render_rubber_stamp, stamp_artwork
from .colors import choose_color
from .addresses import generate_address
from .seal_artwork import load_emblem
from PIL import Image, ImageOps


class AssetRequest(Contract):
    kind: Literal["signature", "seal", "stamp", "rubber_stamp", "qr", "barcode", "text", "portrait", "drawing", "address"]
    value: str | None = Field(default=None, min_length=1, max_length=1000)
    width: int = Field(default=480, ge=16, le=2048)
    height: int = Field(default=160, ge=16, le=2048)
    seed: int = Field(default=42, ge=0, le=2**31-1)
    options: RuleOptions = Field(default_factory=RuleOptions)
    qr_padding: int = Field(default=0, ge=0, le=8)

    @model_validator(mode="after")
    def valid_options(self):
        kind = self.kind
        Region(id="asset", kind=kind, box=(0, 0, self.width, self.height), rule_options=self.options)
        if kind == "signature" and self.value is not None and (len(self.value) > 100 or
            not any(c.isalpha() for c in self.value) or any(not(c.isascii() and (c.isalpha() or c in " .'-")) for c in self.value)):
            raise ValueError("Signing text must contain English letters, spaces, apostrophes, dots or hyphens, up to 100 characters")
        if kind == "qr" and self.value is not None and len(self.value) > 500:
            raise ValueError("QR payload is limited to 500 characters")
        if kind == "barcode" and self.value is not None and (len(self.value) > 128 or any(ord(c) > 127 for c in self.value)):
            raise ValueError("Code128 payload must be ASCII, at most 128 characters")
        if self.value is not None and self.options.character_length is not None and len(self.value) != self.options.character_length:
            raise ValueError("Value does not match configured character length")
        return self


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_asset(body: AssetRequest, root: Path):
    kind = body.kind
    region = Region(id="asset", kind=kind, box=(0, 0, body.width, body.height), rule_options=body.options)
    value = body.value if body.value is not None else fictional_values([region], body.seed)["asset"]
    options = body.options
    rng = random.Random(body.seed)
    details = {}
    if kind=="address" and body.value is None and options.address_country and options.literal_text is None:
        details=generate_address(options,body.seed)
    size = (body.width, body.height)
    with CPU_LOCK:
        if kind == "signature":
            layer, mask, details = render_signature(size, value, rng, options)
        elif kind == "seal":
            content = plan_seal_content(options, body.seed, "asset", literal=body.value)
            emblem,provenance=load_emblem(root,options.seal_artwork_id,options.seal_artwork_ids,body.seed)
            layer, mask, details = render_seal(size, content, rng, options,emblem)
            if provenance:details['asset_provenance']=provenance
        elif kind == "stamp":
            content=plan_stamp(options,body.seed,"asset",body.value)
            source,provenance=stamp_artwork(options,root,body.seed)
            layer,mask,details=render_stamp(size,content,rng,options,source)
            if provenance: details["asset_provenance"]=provenance
        elif kind == "rubber_stamp":
            content=plan_rubber_stamp(options,body.seed,"asset",body.value)
            layer,mask,details=render_rubber_stamp(size,content,rng,options)
        elif kind == "portrait":
            if options.portrait_source == "asset_pool":
                if not options.portrait_asset_ids:
                    raise ValueError("Select at least one approved portrait asset")
                id_ = rng.choice(options.portrait_asset_ids)
                details = portrait_metadata(root, id_)
                with Image.open(root/"portraits"/id_/"image.png") as opened:
                    layer = ImageOps.fit(opened.convert("RGBA"), size, method=Image.Resampling.LANCZOS)
            else:
                layer = illustration(size, rng).convert("RGBA")
                details = {"source": "fictional_procedural_illustration"}
            layer=portrait_background(layer,options,body.seed)
            details["background"]=options.portrait_background
            mask = layer.getchannel("A").point(lambda p: 255 if p else 0)
        else:
            if kind=="text":details["text_color"]=choose_color(options,rng,"text")
            layer, mask = asset(kind, size, value, rng, options, body.qr_padding)
    raw, mask_raw = png_bytes(layer), png_bytes(mask)
    box = mask.getbbox()
    return {"image": "data:image/png;base64,"+base64.b64encode(raw).decode(),
            "mask": "data:image/png;base64,"+base64.b64encode(mask_raw).decode(),
            "metadata": {"kind": kind, "requested_kind": body.kind, "width": body.width, "height": body.height,
                         "seed": body.seed, "value": details.get("text", value), "sha256": hashlib.sha256(raw).hexdigest(),
                         "mask_sha256": hashlib.sha256(mask_raw).hexdigest(),
                         "bbox": [box[0], box[1], box[2]-box[0], box[3]-box[1]] if box else None,
                         "details": details, "provenance": "synthetic_asset", "saved": False}}


def asset_router(root: Path):
    router = APIRouter(prefix="/api/assets", tags=["Standalone assets"])

    @router.post("/generate")
    def generate(body: AssetRequest):
        return generate_asset(body, root)

    return router
