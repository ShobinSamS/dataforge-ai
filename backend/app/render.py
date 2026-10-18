"""Seeded fictional values, procedural assets and synchronized pixel/mask geometry."""
import hashlib
import io
import math
import random
from datetime import date
from pathlib import Path
import numpy as np
from faker import Faker
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
import qrcode
from .schemas import CLASS_NAMES, GenerationConfig, Region, region_action
from .portraits import illustration, portrait_metadata
from .patterns import generate_pattern, SETS
from .fonts import load_font, native_font_id, resolve_font_weight
from .restoration import restore_region


def font(size: int, font_id: str = "auto"):
    return load_font(size,font_id)


def fictional_values(regions: list[Region], seed: int, config: GenerationConfig | None = None) -> dict[str, str]:
    rng = random.Random(seed)
    fake = Faker("en_US")
    fake.seed_instance(seed)
    # One value per semantic key enforces relationships/repeated names across a page.
    shared = {"name": fake.name(), "email": f"person{seed % 1000000}@example.invalid",
              "phone": f"+1-202-555-{rng.randrange(100, 200):04d}",
              "date": fake.date_between(start_date=date(2015,1,1), end_date=date(2025,12,31)).isoformat(),
              "address": f"{rng.randrange(1,999)} Fictional Lane, Test City, ZZ 00000",
              "identifier": f"{seed:010d}", "text": f"Fictional record {seed % 1000000:06d}"}
    result = {}
    for region in regions:
        if region.rule_options.literal_text is not None:
            result[region.id]=region.rule_options.literal_text
        elif region.rule.startswith("literal:"):
            result[region.id] = region.rule[8:]
        elif region.rule_options.identifier_pattern:
            options=region.rule_options
            result[region.id]=generate_pattern(options.identifier_pattern,seed,options.date_start,options.date_end)
        elif region.rule_options.character_length is not None or region.kind in {"identifier","qr","barcode"}:
            options=region.rule_options
            length=options.character_length or (config.qr_payload_length if config and region.kind=="qr" else config.identifier_length if config else 10)
            charset=SETS[options.character_set]
            value_rng=random.Random(f"{seed}:{region.kind}:{length}:{options.character_set}")
            result[region.id]="".join(value_rng.choice(charset) for _ in range(length))
        elif region.kind=="portrait":
            result[region.id]="Fictional portrait illustration" if region.rule_options.portrait_source=="illustration" else "Approved portrait asset"
        elif region.kind=="date":
            options=region.rule_options
            # Same bounds share one date, including differently formatted repeated fields.
            date_rng=random.Random(f"{seed}:{options.date_start}:{options.date_end}")
            value=date.fromordinal(date_rng.randint(options.date_start.toordinal(),options.date_end.toordinal()))
            formats={"yyyy-mm-dd":"%Y-%m-%d","dd/mm/yyyy":"%d/%m/%Y","mm/dd/yyyy":"%m/%d/%Y","dd-mm-yyyy":"%d-%m-%Y","yyyy/mm/dd":"%Y/%m/%d"}
            result[region.id]=value.strftime(formats[options.date_format])
        elif region.kind in {"signature", "seal", "qr", "barcode"}:
            result[region.id] = f"{seed:010d}"
        else:
            result[region.id] = shared[region.kind.value]
    return result


def asset(kind: str, size: tuple[int, int], value: str, rng: random.Random, style=None, qr_padding: int = 0) -> tuple[Image.Image, Image.Image]:
    w, h = size
    layer = Image.new("RGBA", size)
    d = ImageDraw.Draw(layer)
    ink = style.text_color if style else (32, 60, 102, 255)
    if kind == "signature":
        # Random cubic Bezier strokes, never fitted to an uploaded person's signature.
        for j in range(4):
            p = [(rng.uniform(.05,.2)*w, rng.uniform(.3,.8)*h),
                 (rng.uniform(.2,.4)*w, rng.uniform(-.1,1.1)*h),
                 (rng.uniform(.4,.8)*w, rng.uniform(-.1,1.1)*h),
                 (rng.uniform(.8,.95)*w, rng.uniform(.3,.7)*h)]
            pts = []
            for t in np.linspace(0, 1, 70):
                pts.append(tuple((1-t)**3*p[0][k]+3*(1-t)**2*t*p[1][k]+3*(1-t)*t*t*p[2][k]+t**3*p[3][k] for k in [0,1]))
            d.line(pts, fill=ink, width=max(1, h//30))
        d.line((w*.08, h*.86, w*.9, h*.77), fill=ink, width=max(1, h//40))
    elif kind == "seal":
        ink = (153, 64, 72, 220)
        d.ellipse((3,3,w-4,h-4), outline=ink, width=max(1,min(w,h)//30))
        d.ellipse((8,8,w-9,h-9), outline=ink, width=1)
        for txt, yy in [("FICTIONAL", .31), ("SAMPLE", .53)]:
            f = font(max(7, min(w//10,h//8)))
            d.text((w/2, h*yy), txt, font=f, fill=ink, anchor="mm")
    elif kind == "qr":
        code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=qr_padding)
        code.add_data(value)
        code.make(fit=True)
        qr = code.make_image(fill_color="black", back_color="white").convert("RGBA")
        side = min(w,h)
        if side < len(code.get_matrix()) * 3:
            raise ValueError(f"QR region too small for this payload: use at least {len(code.get_matrix())*3}x{len(code.get_matrix())*3} pixels or shorten the payload")
        layer.alpha_composite(qr.resize((side,side), Image.Resampling.NEAREST), ((w-side)//2,(h-side)//2))
        mask = Image.new("L", size)
        ImageDraw.Draw(mask).rectangle(((w-side)//2,(h-side)//2,(w+side)//2-1,(h+side)//2-1),fill=255)
        return layer, mask
    elif kind == "barcode":
        from barcode import Code128
        from barcode.writer import ImageWriter
        buffer = io.BytesIO()
        Code128(value, writer=ImageWriter()).write(buffer, {"write_text": False, "module_height": 12, "quiet_zone": 3})
        with Image.open(buffer) as barcode:
            layer = barcode.convert("RGBA").resize(size, Image.Resampling.NEAREST)
        return layer, Image.new("L", size, 255)
    else:
        f = None
        for size_px in range(style.font_size if style and style.font_size else min(200,max(64,h*2)), 5, -1):
            f = font(size_px,resolve_font_weight(style.font_id,style.font_weight) if style else "auto")
            box = d.textbbox((0,0), value, font=f)
            if box[2]-box[0] <= w-6 and box[3]-box[1] <= h-6:
                break
        else:
            raise ValueError("Replacement text cannot fit region; enlarge it or shorten its rule")
        box = d.textbbox((0,0), value, font=f)
        d.text((3-box[0], (h-(box[3]-box[1]))//2-box[1]), value, font=f, fill=ink)
    return layer, layer.getchannel("A").point(lambda p: 255 if p else 0)


def optional_regions(width: int, height: int, regions: list[Region], config: GenerationConfig) -> list[Region]:
    """Assets use dedicated reviewed regions. Never paste over unreviewed locations."""
    enabled = {"signature": config.signatures, "seal": config.seals, "qr": config.qr_codes, "barcode": config.barcodes}
    # Disabled visual regions still erase the original, but do not add a replacement.
    return [r for r in regions if region_action(r)=="replace" and enabled.get(r.kind, True)]


def render_sample(source: Path, regions: list[Region], config: GenerationConfig, index: int, dest: Path, attempt: int = 0, asset_root: Path | None = None) -> dict:
    seed = config.seed + index * 1009 + attempt * 10000019
    rng = random.Random(seed)
    with Image.open(source) as original:
        image = original.convert("RGB")
    width, height = image.size
    for r in regions:
        if r.replace:
            restore_region(image,r.box,glyphs_only=region_action(r)=="replace" and r.kind not in {"signature","seal","qr","barcode","portrait"},mode=r.rule_options.background_mode,color=r.rule_options.background_color)
    enabled = optional_regions(width,height,regions,config)
    values = fictional_values(enabled, seed,config)
    # Build/transforms one mask at a time; do not retain full-page masks per region.
    angle = rng.uniform(-config.rotation_degrees,config.rotation_degrees) if rng.random() < config.rotation_probability else 0
    dest.mkdir(parents=True,exist_ok=True)
    rendered = []
    asset_provenance={}
    typography={}
    for r in enabled:
        x,y,w,h = r.box
        if r.kind=="portrait":
            if r.rule_options.portrait_source=="asset_pool":
                if not asset_root or not r.rule_options.portrait_asset_ids: raise ValueError("Select portrait images for the asset pool")
                selected=random.Random(f"{seed}:portrait").choice(r.rule_options.portrait_asset_ids)
                provenance=portrait_metadata(asset_root,selected)
                with Image.open(asset_root/"portraits"/selected/"image.png") as photo:
                    layer=ImageOps.fit(photo.convert("RGBA"),(w,h),method=Image.Resampling.LANCZOS)
                asset_provenance[r.id]={k:v for k,v in provenance.items() if k!="preview_url"}
            else:
                layer=illustration((w,h),rng).convert("RGBA")
                asset_provenance[r.id]={"source":"fictional_procedural_illustration"}
            mask=Image.new("L",(w,h),255)
        else:
            style=r.rule_options.model_copy(deep=True)
            if style.font_id=="auto" and r.source_font: style.font_id=native_font_id(r.source_font)
            style.font_id=resolve_font_weight(style.font_id,style.font_weight)
            if style.font_size is None and r.source_font_size: style.font_size=max(6,min(200,round(r.source_font_size)))
            typography[r.id]={"font_id":style.font_id,"preferred_size":style.font_size,"text_color":style.text_color}
            layer, mask = asset(r.kind, (w,h), values[r.id], rng,style,config.qr_padding)
        image.paste(layer, (x,y), layer)
        local_path = dest/f"local_{r.id}.png"
        mask.save(local_path)
        rendered.append((r,local_path))
    if angle:
        image = image.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor="white")
    blurred = rng.random() < config.blur_probability
    if blurred:
        image = image.filter(ImageFilter.GaussianBlur(rng.uniform(.35,.8)))
    if config.noise_sigma:
        pixels = np.asarray(image).astype(np.float32)
        noise = np.random.default_rng(seed).normal(0,config.noise_sigma,pixels.shape).astype(np.float32)
        image = Image.fromarray(np.clip(pixels+noise,0,255).astype(np.uint8))
    dest.mkdir(parents=True,exist_ok=True)
    annotations = []
    errors = []
    for r, local_path in rendered:
        x,y,w,h = r.box
        full = Image.new("L", (width,height))
        with Image.open(local_path) as local_mask:
            full.paste(local_mask,(x,y))
        local_path.unlink()
        original_area = int(np.count_nonzero(np.asarray(full)))
        if angle:
            full = full.rotate(angle,resample=Image.Resampling.NEAREST)
        bounds = full.getbbox()
        if bounds is None:
            errors.append(f"empty_mask:{r.id}")
            continue
        x0,y0,x1,y1 = bounds
        if x0 == 0 or y0 == 0 or x1 == width or y1 == height:
            errors.append(f"edge_clipping:{r.id}")
        visible = int(np.count_nonzero(np.asarray(full))) / max(1,original_area)
        if visible < .95:
            errors.append(f"visibility:{r.id}")
        mask_name = f"mask_{r.id}.png"
        full.save(dest/mask_name)
        annotations.append({"region_id":r.id,"class_id":CLASS_NAMES.index(r.kind.value),"class":r.kind.value,
            "bbox":[x0,y0,x1-x0,y1-y0],"text": values[r.id],"mask":mask_name,
            "provenance":"procedural-mask","visibility":round(min(1,visible),4)})
        annotations[-1]["synthetic"]=True
        if r.kind not in {"portrait","signature","seal","qr","barcode"}:
            annotations[-1]["typography"]=typography[r.id]
        if r.id in asset_provenance: annotations[-1]["asset_provenance"]=asset_provenance[r.id]
    image_path = dest/"image.png"
    image.save(image_path)
    return {"image":image,"annotations":annotations,"errors":errors,"width":width,"height":height,
            "sha256":hashlib.sha256(image_path.read_bytes()).hexdigest(),"seed":seed,
            "transform":{"rotation":angle,"blur":blurred,"noise_sigma":config.noise_sigma},
            "erased_regions":[{"region_id":r.id,"box":list(r.box),"coordinate_space":"source_page"} for r in regions if region_action(r)=="erase"]}
