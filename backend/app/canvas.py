"""Blank page creation and bounded previews using the document renderer."""
import json
from typing import Literal

from PIL import Image
from PIL.PngImagePlugin import PngInfo
from pydantic import Field, model_validator

from .schemas import Contract, Region

PAPERS = {"a4": (210, 297), "a5": (148, 210), "letter": (215.9, 279.4)}


class CanvasRequest(Contract):
    name: str = Field(default="Untitled canvas", min_length=1, max_length=200)
    paper: Literal["a4", "a5", "letter", "custom"] = "a4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    unit: Literal["mm", "px"] = "mm"
    width: float = Field(default=210, gt=0, le=6000, allow_inf_nan=False)
    height: float = Field(default=297, gt=0, le=6000, allow_inf_nan=False)
    dpi: int = Field(default=150, ge=72, le=300)
    background: Literal["white", "transparent", "color"] = "white"
    background_color: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    starter: Literal["blank", "signature", "seal", "text", "portrait", "stamp", "rubber_stamp", "qr", "barcode"] = "blank"

    def pixels(self):
        w, h = PAPERS.get(self.paper, (self.width, self.height))
        if self.paper != "custom" or self.unit == "mm":
            w, h = w*self.dpi/25.4, h*self.dpi/25.4
        w, h = round(w), round(h)
        return (min(w,h), max(w,h)) if self.orientation == "portrait" else (max(w,h), min(w,h))

    @model_validator(mode="after")
    def bounded(self):
        w,h = self.pixels()
        if min(w,h)<64 or max(w,h)>6000 or w*h>12_000_000:
            raise ValueError("Canvas must be 64–6000 pixels per side and at most 12 megapixels; reduce size or DPI")
        return self


class CanvasPreview(Contract):
    regions: list[Region] = Field(max_length=200)
    seed: int = Field(default=42, ge=0, le=2**31-1)


def create_canvas(body, path):
    size = body.pixels()
    mode, color = ("RGBA", (0,0,0,0)) if body.background == "transparent" else ("RGB", body.background_color if body.background == "color" else "white")
    image = Image.new(mode, size, color)
    metadata = PngInfo()
    metadata.add_text("dataforge_canvas", json.dumps(body.model_dump()))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, pnginfo=metadata, dpi=(body.dpi,body.dpi))
    w,h = size
    if body.starter == "blank": return size, []
    bw,bh = max(32,round(w*.8)), max(32,round(h*.65))
    if body.starter in {"signature","text","barcode","rubber_stamp"}: bh = max(32,min(bh,round(bw*.3)))
    elif body.starter in {"seal","qr"}: bw=bh=min(bw,bh)
    elif body.starter in {"portrait","stamp"}: bw=min(bw,round(bh*.75))
    region=Region(id="element_1",label=body.starter.replace("_"," ").title(),kind=body.starter,
                  box=((w-bw)//2,(h-bh)//2,bw,bh),sensitive=False,
                  rule_options={"literal_text":"Your text"} if body.starter=="text" else {})
    return size, [region.model_dump(mode="json")]


def canvas_info(path):
    with Image.open(path) as image:
        return json.loads(image.info.get("dataforge_canvas", "null"))
