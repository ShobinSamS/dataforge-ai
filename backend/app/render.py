"""Seeded fictional values, procedural assets and synchronized pixel/mask geometry."""
import hashlib
import io
import random
from datetime import date
from pathlib import Path
import numpy as np
from faker import Faker
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from .qr_capacity import qr_code, PIXELS_PER_MODULE
from .schemas import CLASS_NAMES, GenerationConfig, Region, region_action
from .portraits import illustration, portrait_metadata, portrait_background
from .patterns import generate_pattern, SETS
from .fonts import load_font, native_font_id, resolve_font_weight, cursive_font_id
from .restoration import restore_region
from .signatures import render_signature
from .seals import plan_seal_content,seal_text,render_seal
from .seal_artwork import load_emblem
from .stamps import plan_stamp, render_stamp, plan_rubber_stamp, render_rubber_stamp, stamp_artwork
from .colors import choose_color
from .addresses import generate_address


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
        if region.kind=="drawing":
            result[region.id]="Freehand drawing"
        elif region.kind=="stamp":
            result[region.id]=plan_stamp(region.rule_options,seed,region.id,region.rule[8:] if region.rule.startswith("literal:") else None)["caption"]
        elif region.kind=="rubber_stamp":
            result[region.id]=plan_rubber_stamp(region.rule_options,seed,region.id,region.rule[8:] if region.rule.startswith("literal:") else None)["text"]
        elif region.kind=="seal":
            literal=region.rule[8:] if region.rule.startswith("literal:") else None
            result[region.id]=seal_text(plan_seal_content(region.rule_options,seed,region.id,literal))
        elif region.rule_options.literal_text is not None:
            result[region.id]=region.rule_options.literal_text
        elif region.rule.startswith("literal:"):
            result[region.id] = region.rule[8:]
        elif region.kind=="address" and region.rule_options.address_country:
            result[region.id]=generate_address(region.rule_options,seed)["text"]
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
        elif region.kind=="signature":
            result[region.id] = shared["name"]
        else:
            result[region.id] = shared[region.kind.value]
    return result


def asset(kind: str, size: tuple[int, int], value: str, rng: random.Random, style=None, qr_padding: int = 0) -> tuple[Image.Image, Image.Image]:
    w, h = size
    layer = Image.new("RGBA", size)
    d = ImageDraw.Draw(layer)
    ink = choose_color(style,rng,"text") if style else (32, 60, 102, 255)
    if kind == "drawing":
        points=style.drawing_points if style else []
        if not points: raise ValueError("Draw at least one stroke before rendering")
        large=Image.new("RGBA",(w*3,h*3));draw=ImageDraw.Draw(large)
        coords=[(round(x*(w-1)*3),round(y*(h-1)*3)) for x,y in points]
        width=max(1,round(style.drawing_width*3));radius=width/2
        draw.line(coords,fill=ink,width=width,joint="curve")
        for x,y in (coords[0],coords[-1]):draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=ink)
        layer=large.resize(size,Image.Resampling.LANCZOS)
        return layer,layer.getchannel("A").point(lambda p:255 if p else 0)
    elif kind == "signature":
        from .schemas import RuleOptions
        layer,mask,_=render_signature(size,value,rng,style or RuleOptions())
        return layer,mask
    elif kind == "seal":
        from .schemas import RuleOptions
        seal_style=style or RuleOptions()
        texts=value.split(" / ",1) if " / " in value else value.splitlines()
        content={"top":texts[0] if texts else seal_style.seal_text,"bottom":seal_style.seal_bottom_text,"lines":"\n".join(texts[1:]).splitlines() if len(texts)>1 else seal_style.seal_subtext.splitlines(),"mode":"static"}
        layer,mask,_=render_seal(size,content,rng,seal_style)
        return layer,mask
    elif kind in {"stamp", "rubber_stamp"}:
        from .schemas import RuleOptions
        options=style or RuleOptions()
        seed=rng.randrange(2**31)
        if kind=="stamp": layer,mask,_=render_stamp(size,plan_stamp(options,seed,literal=value),rng,options)
        else: layer,mask,_=render_rubber_stamp(size,plan_rubber_stamp(options,seed,literal=value),rng,options)
        return layer,mask
    elif kind == "qr":
        code = qr_code(value,qr_padding)
        code.make(fit=True)
        qr = code.make_image(fill_color="black", back_color="white").convert("RGBA")
        if not style or style.code_background=="transparent":
            pixels=np.array(qr);pixels[pixels[:,:,0]>127,3]=0;qr=Image.fromarray(pixels)
        side = min(w,h)
        if side < len(code.get_matrix()) * PIXELS_PER_MODULE:
            raise ValueError(f"QR region too small for this payload: use at least {len(code.get_matrix())*PIXELS_PER_MODULE}x{len(code.get_matrix())*PIXELS_PER_MODULE} pixels or shorten the payload")
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
        if not style or style.code_background=="transparent":
            pixels=np.array(layer);pixels[pixels[:,:,0]>127,3]=0;layer=Image.fromarray(pixels)
        return layer, Image.new("L", size, 255)
    else:
        f = None
        for size_px in range(style.font_size if style and style.font_size else min(200,max(64,h*2)), 5, -1):
            face=cursive_font_id() if style and style.writing_style=="cursive" and style.font_id=="auto" else style.font_id if style else "auto"
            f = font(size_px,resolve_font_weight(face,style.font_weight) if style else "auto")
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
    enabled = {"signature": config.signatures, "seal": config.seals, "stamp": config.stamps, "rubber_stamp": config.rubber_stamps, "qr": config.qr_codes, "barcode": config.barcodes}
    # Disabled visual regions still erase the original, but do not add a replacement.
    return [r for r in regions if region_action(r)=="replace" and enabled.get(r.kind, True)]


def render_sample(source: Path, regions: list[Region], config: GenerationConfig, index: int, dest: Path, attempt: int = 0, asset_root: Path | None = None) -> dict:
    seed = config.seed + index * 1009 + attempt * 10000019
    rng = random.Random(seed)
    with Image.open(source) as original:
        canvas=bool(original.info.get("dataforge_canvas"))
        dpi=original.info.get("dpi")
        image = original.convert("RGBA" if canvas and original.mode=="RGBA" else "RGB")
    width, height = image.size
    # Authored canvases start blank. Per-element backgrounds are composed in
    # layer order below, rather than erasing earlier elements.
    for r in regions:
        if r.replace and not canvas:
            restore_region(image,r.box,glyphs_only=r.rule_options.cleanup_mode=="ink_only" and region_action(r)=="replace" and r.kind not in {"signature","seal","stamp","rubber_stamp","qr","barcode","portrait","drawing"},mode=r.rule_options.background_mode,color=r.rule_options.background_color)
    enabled = optional_regions(width,height,regions,config)
    values = fictional_values(enabled, seed,config)
    # Build/transforms one mask at a time; do not retain full-page masks per region.
    angle = rng.uniform(-config.rotation_degrees,config.rotation_degrees) if rng.random() < config.rotation_probability else 0
    dest.mkdir(parents=True,exist_ok=True)
    rendered = []
    asset_provenance={}
    typography={}
    signature_details={}
    seal_details={}
    stamp_details={}
    address_details={}
    for r in enabled:
        x,y,w,h = r.box
        if r.kind=="address" and r.rule_options.address_country and r.rule_options.literal_text is None and not r.rule.startswith("literal:"):
            address_details[r.id]=generate_address(r.rule_options,seed)
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
            layer=portrait_background(layer,r.rule_options,seed)
            asset_provenance[r.id]["background"]=r.rule_options.portrait_background
            mask=layer.getchannel("A").point(lambda p:255 if p else 0)
        else:
            style=r.rule_options.model_copy(deep=True)
            if r.kind!="signature" and style.font_id=="auto" and style.writing_style=="cursive": style.font_id=cursive_font_id()
            if r.kind!="signature" and style.font_id=="auto" and r.source_font: style.font_id=native_font_id(r.source_font)
            if r.kind!="signature":style.font_id=resolve_font_weight(style.font_id,style.font_weight)
            if r.kind!="signature" and style.font_size is None and r.source_font_size: style.font_size=max(6,min(200,round(r.source_font_size)))
            if r.kind not in {"signature","seal","stamp","rubber_stamp","qr","barcode"}:
                style.text_color=choose_color(style,rng,"text")
            typography[r.id]={"font_id":style.font_id,"preferred_size":style.font_size,"text_color":style.text_color}
            if r.kind=="signature":
                if config.signature_style_override:style.signature_style=config.signature_style_override
                if config.signature_content_override:style.signature_content=config.signature_content_override
                layer,mask,signature_details[r.id]=render_signature((w,h),values[r.id],rng,style)
                values[r.id]=signature_details[r.id]["text"]
            elif r.kind in {"stamp", "rubber_stamp"}:
                literal=r.rule[8:] if r.rule.startswith("literal:") else None
                if r.kind=="stamp":
                    content=plan_stamp(style,seed,r.id,literal)
                    source,provenance=stamp_artwork(style,asset_root,seed)
                    layer,mask,stamp_details[r.id]=render_stamp((w,h),content,rng,style,source)
                    if provenance: asset_provenance[r.id]=provenance
                else:
                    content=plan_rubber_stamp(style,seed,r.id,literal)
                    layer,mask,stamp_details[r.id]=render_rubber_stamp((w,h),content,rng,style)
                values[r.id]=stamp_details[r.id]["text"]
            elif r.kind=="seal":
                literal=r.rule[8:] if r.rule.startswith("literal:") else None
                content=plan_seal_content(style,seed,r.id,literal)
                emblem,provenance=load_emblem(asset_root,style.seal_artwork_id,style.seal_artwork_ids,seed)
                layer,mask,seal_details[r.id]=render_seal((w,h),content,rng,style,emblem)
                if provenance:asset_provenance[r.id]=provenance
                values[r.id]=seal_details[r.id]["text"]
            else:
                layer, mask = asset(r.kind, (w,h), values[r.id], rng,style,config.qr_padding)
        if canvas and r.rule_options.background_mode=="solid":
            backdrop=Image.new("RGBA",layer.size,r.rule_options.background_color)
            backdrop.alpha_composite(layer);layer=backdrop
        if image.mode=="RGBA":image.alpha_composite(layer,(x,y))
        else:image.paste(layer, (x,y), layer)
        local_path = dest/f"local_{r.id}.png"
        mask.save(local_path)
        rendered.append((r,local_path))
    if angle:
        image = image.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=(0,0,0,0) if image.mode=="RGBA" else "white")
    blurred = rng.random() < config.blur_probability
    if blurred:
        radius=rng.uniform(.35,.8)
        image = (image.convert("RGBa").filter(ImageFilter.GaussianBlur(radius)).convert("RGBA") if image.mode=="RGBA"
                 else image.filter(ImageFilter.GaussianBlur(radius)))
    if config.noise_sigma:
        pixels = np.asarray(image).astype(np.float32)
        noise = np.random.default_rng(seed).normal(0,config.noise_sigma,pixels[:,:,:3].shape).astype(np.float32)
        pixels[:,:,:3]=np.clip(pixels[:,:,:3]+noise,0,255)
        image = Image.fromarray(pixels.astype(np.uint8))
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
        if r.id in signature_details:annotations[-1]["signature"]=signature_details[r.id]
        if r.id in seal_details:annotations[-1]["seal"]=seal_details[r.id]
        if r.id in stamp_details:annotations[-1][r.kind.value]=stamp_details[r.id]
        if r.id in address_details:annotations[-1]["address"]=address_details[r.id]
        if r.kind not in {"portrait","signature","seal","stamp","rubber_stamp","qr","barcode"}:
            annotations[-1]["typography"]=typography[r.id]
        if r.id in asset_provenance: annotations[-1]["asset_provenance"]=asset_provenance[r.id]
    image_path = dest/"image.png"
    image.save(image_path,**({"dpi":dpi} if canvas and dpi else {}))
    return {"image":image,"annotations":annotations,"errors":errors,"width":width,"height":height,
            "sha256":hashlib.sha256(image_path.read_bytes()).hexdigest(),"seed":seed,
            "transform":{"rotation":angle,"blur":blurred,"noise_sigma":config.noise_sigma},
            "erased_regions":[{"region_id":r.id,"box":list(r.box),"coordinate_space":"source_page"} for r in regions if region_action(r)=="erase"]}
