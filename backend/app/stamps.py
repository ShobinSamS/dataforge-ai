"""Paper postage/revenue stamps and separate ink-only rubber stamps.

Reference-inspired composition, not scans/crops of supplied collectible stamps.
Default issuers, people, captions and places are fictional. No model downloads.
"""
import math
import random
from datetime import date

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops

from .fonts import load_font, resolve_font_weight
from .ink import apply_ink_opacity
from .ink_finish import apply_ink_finish
from .seals import render_seal, PALETTE
from .portraits import portrait_metadata

STYLES = ("portrait", "architecture", "botanical", "commemorative", "revenue")
WORDS = ("RECEIVED", "PAID", "APPROVED", "REJECTED", "COPY", "CONFIDENTIAL", "CANCELLED", "DISPATCHED")
COLORS = {"black":(0,0,0),"sepia": (112, 78, 42), "red": (157, 43, 52), "blue": (29, 84, 125),
          "green": (61, 100, 72), "purple": (111, 66, 123), "monochrome": (54, 54, 50)}


def plan_rubber_stamp(options, seed, region_id="rubber_stamp", literal=None):
    rng = random.Random(f"rubber-content:{seed}:{region_id}")
    city = rng.choice(("CEDAR BAY", "NORTHSTAR", "MAPLE TOWN", "ORBIT CITY"))
    day = date.fromordinal(rng.randint(options.date_start.toordinal(), options.date_end.toordinal()))
    context = {"organization": rng.choice(("CEDAR WORKS", "NORTHSTAR LAB", "MAPLE STUDIO")),
               "department": rng.choice(("RECORDS DESK", "ACCOUNTS", "DISPATCH UNIT")),
               "name": rng.choice(("MIRA DEV", "ARUN SEN", "NILA SHAH")), "title": "CLERK",
               "city": city, "state": "WEST DISTRICT", "year": str(day.year), "date": day.strftime("%d %b %Y").upper(),
               "reference": str(rng.randrange(1000, 9999)), "number": str(rng.randrange(10, 999))}
    if literal is not None or options.literal_text is not None:
        text = literal if literal is not None else options.literal_text
    elif options.rubber_stamp_mode == "random": text = rng.choice(WORDS)
    elif options.rubber_stamp_mode == "custom": text = options.rubber_stamp_format.format_map(context)
    else: text = options.rubber_stamp_text
    if not text.strip() or len(text.splitlines()) > 6:
        raise ValueError("Rubber stamps need non-empty text and at most six lines")
    return {"text": text, "city": city, "date": context["date"], "mode": options.rubber_stamp_mode}


def render_rubber_stamp(size, content, rng, options):
    style = options.rubber_stamp_style
    if style == "random": style = rng.choice(("boxed", "text", "round", "dated"))
    color = options.rubber_stamp_color
    if color == "random": color = rng.choice(tuple(PALETTE))
    if style == "waves":
        w, h = size; layer = Image.new("RGBA", size); draw = ImageDraw.Draw(layer)
        for row in range(5):
            points = [(x, h*(.18+row*.15)+math.sin(x/max(12, w)*math.tau*2.5)*h*.045) for x in range(round(w*.05), round(w*.95))]
            draw.line(points, fill=(*PALETTE[color], 255), width=max(1, round(h/55)))
        layer, _, finish = apply_ink_finish(layer, rng, options, "rubber_stamp")
        layer, mask, opacity = apply_ink_opacity(layer, rng, options, "rubber_stamp")
        return layer, mask, {"engine": "rubber-stamp-v1", "style": style, "text": "", "ink_color": color, "content_mode": content["mode"], "ink_finish": finish, **opacity}
    lines = content["text"].splitlines()
    top, body, bottom = lines[0], lines[1:], ""
    if style == "postmark": top, body, bottom = "POST OFFICE", [content["date"]], content["city"]
    elif style == "dated": body = [*body, content["date"]]
    shape = {"boxed": "rectangle", "text": "text", "round": "double_ring", "dated": "form", "postmark": "double_ring"}[style]
    adjusted = options.model_copy(update={"seal_style": shape, "seal_color": color, "seal_border": "double" if style != "text" else "solid",
                                          "seal_symbol": "none", "seal_center_motif": "none", "seal_inner_top_text": "", "seal_inner_bottom_text": "",
                                          "seal_embedded_signature": False})
    layer, mask, details = render_seal(size, {"top": top, "bottom": bottom, "lines": body, "mode": content["mode"]}, rng, adjusted)
    return layer, mask, {**details, "engine": "rubber-stamp-v1", "style": style, "ink_color": color}


def plan_stamp(options, seed, region_id="stamp", literal=None):
    rng = random.Random(f"paper-stamp:{seed}:{region_id}")
    style = rng.choice(STYLES) if options.stamp_style == "random" else options.stamp_style
    captions = {"portrait": ("MIRA DEV", "ARUN SEN", "NILA SHAH", "KIRAN DAS"),
                "architecture": ("HERITAGE HALL", "RIVER PAVILION", "CEDAR ARCHIVE"),
                "botanical": ("WILD FLOWERS", "FOREST STUDY", "GARDEN SERIES"),
                "commemorative": ("RAIL CENTENARY", "SCIENCE WEEK", "SPORTS MEET", "NATURE STUDY"),
                "revenue": ("REVENUE", "DUTY", "FISCAL STAMP")}
    caption=literal or options.literal_text or options.stamp_caption or rng.choice(captions[style])
    motif={"RAIL CENTENARY":"rail","SCIENCE WEEK":"science","SPORTS MEET":"sport","NATURE STUDY":"science"}.get(caption,rng.choice(("rail","science","sport")))
    return {"style": style, "motif":motif,
            "issuer": options.stamp_issuer or rng.choice(("NORTHSTAR POST", "CEDAR ISLANDS", "MAPLE POST", "ORBIT POST")),
            "caption": caption,
            "denomination": options.stamp_denomination or rng.choice(("0.15", "15 P", "1.00", "2.50", "5", "10", "20", "50")),
            "year": str(rng.randrange(1900, 2026)), "mode": "custom" if options.stamp_issuer or options.stamp_caption or options.stamp_denomination or options.literal_text or literal else "random"}


def stamp_artwork(options, root, seed):
    if options.portrait_source != "asset_pool": return None, {}
    if root is None or not options.portrait_asset_ids: raise ValueError("Select approved portrait assets for stamp artwork")
    id_ = random.Random(f"stamp-artwork:{seed}").choice(options.portrait_asset_ids)
    provenance = portrait_metadata(root, id_)
    with Image.open(root/"portraits"/id_/"image.png") as source:
        # Transparent image pools retain alpha for canvas photos. Printed stamp
        # engraving still uses the same white paper matte as opaque uploads.
        rgba=source.convert("RGBA");matte=Image.new("RGBA",rgba.size,"white")
        matte.alpha_composite(rgba);image=matte.convert("RGB")
    return image, {k:v for k,v in provenance.items() if k != "preview_url"}


def _letter(draw, box, text, color, preferred, *, bold=False):
    x, y, w, h = box
    for size in range(max(6, int(preferred)), 5, -1):
        font = load_font(size, resolve_font_weight("auto", "bold" if bold else "normal"))
        bounds = draw.textbbox((0, 0), text, font=font)
        if bounds[2]-bounds[0] <= w and bounds[3]-bounds[1] <= h: break
    else: raise ValueError("Stamp lettering cannot fit; enlarge the region or shorten its text")
    draw.text((x+(w-bounds[2]+bounds[0])/2-bounds[0], y+(h-bounds[3]+bounds[1])/2-bounds[1]), text, font=font, fill=color)


def _portrait(size, rng):
    """Tonal bust with varied hair, coat and spectacles, converted to engraved lines."""
    w, h = size; gray = Image.new("L", size, 255); d = ImageDraw.Draw(gray)
    cx = w*rng.uniform(.46, .54)
    d.polygon([(w*.08,h*.99),(w*.21,h*.75),(cx-w*.12,h*.65),(cx+w*.12,h*.65),(w*.79,h*.75),(w*.94,h*.99)], fill=85)
    d.polygon([(cx-w*.09,h*.65),(cx,h*.91),(cx+w*.09,h*.65)], fill=228)
    d.polygon([(cx,h*.78),(cx-w*.035,h*.98),(cx+w*.045,h*.98)], fill=35)
    d.rectangle((cx-w*.09,h*.5,cx+w*.09,h*.73), fill=173)
    d.ellipse((cx-w*.24,h*.08,cx+w*.24,h*.65), fill=187)
    d.ellipse((cx-w*.24,h*.12,cx+w*.16,h*.63), fill=220)
    d.ellipse((cx-w*.25,h*.04,cx+w*.25,h*.39), fill=48)
    d.ellipse((cx-w*.21,h*.19,cx+w*.21,h*.62), fill=219)
    d.pieslice((cx-w*.25,h*.02,cx+w*.27,h*.42), 170, 305, fill=rng.choice((30,65,105)))
    for side in (-1, 1):
        ex = cx+side*w*.11
        d.line((ex-w*.06,h*.32,ex+w*.05,h*.31), fill=65, width=max(1,w//100))
        d.arc((ex-w*.055,h*.35,ex+w*.055,h*.39), 185, 355, fill=35, width=max(1,w//110))
        d.ellipse((ex-w*.014,h*.355,ex+w*.014,h*.383), fill=25)
    d.line([(cx,h*.36),(cx-w*.04,h*.47),(cx+w*.03,h*.48)], fill=100, width=max(1,w//120))
    d.arc((cx-w*.09,h*.49,cx+w*.09,h*.55), 0, 170, fill=75, width=max(1,w//100))
    if rng.random() < .5:
        for side in (-1,1):
            ex=cx+side*w*.11;d.ellipse((ex-w*.09,h*.32,ex+w*.09,h*.415), outline=35, width=max(1,w//90))
        d.line((cx-w*.02,h*.36,cx+w*.02,h*.36), fill=35, width=max(1,w//90))
    return gray


def _art(size, style, rng, source=None, motif=None):
    w, h = size
    if style in {"portrait", "revenue"}:
        if source is not None:
            gray = ImageOps.autocontrast(ImageOps.fit(source.convert("L"), size, method=Image.Resampling.LANCZOS))
        else: gray = _portrait(size, rng)
    else:
        gray = Image.new("L", size, 247); d = ImageDraw.Draw(gray)
        if style == "architecture":
            d.rectangle((w*.08,h*.44,w*.92,h*.92), fill=180, outline=55, width=max(1,w//90))
            d.polygon([(w*.03,h*.46),(w*.5,h*.21),(w*.97,h*.46)], fill=136, outline=45)
            d.ellipse((w*.34,h*.05,w*.66,h*.4), fill=180, outline=60, width=max(1,w//100))
            d.rectangle((w*.33,h*.23,w*.67,h*.36),fill=180)
            for i in range(7):
                x=w*(.13+i*.115)
                d.rounded_rectangle((x,h*.53,x+w*.06,h*.85),radius=max(2,w//50),fill=50)
                d.line((x-w*.015,h*.49,x-w*.015,h*.9),fill=235,width=max(1,w//80))
            for i in range(4): d.line((w*.04,h*(.91+i*.02),w*.96,h*(.91+i*.02)),fill=85,width=max(1,w//140))
        elif style == "botanical":
            for i in range(3):
                x=w*(.25+i*.24);cy=h*rng.uniform(.22,.42)
                d.line((x,cy,x+w*.12,h*.95),fill=85,width=max(1,w//65))
                for side in (-1,1):
                    d.ellipse((x+side*w*.07-w*.1,h*.57,x+side*w*.07+w*.1,h*.72),fill=130,outline=65)
                for a in range(0,360,60):
                    px=x+math.cos(math.radians(a))*w*.085;py=cy+math.sin(math.radians(a))*w*.085
                    d.ellipse((px-w*.07,py-w*.07,px+w*.07,py+w*.07),fill=170,outline=50)
                d.ellipse((x-w*.035,cy-w*.035,x+w*.035,cy+w*.035),fill=60)
        else:
            motif=motif or rng.choice(("rail", "science", "sport"))
            if motif == "rail":
                d.rectangle((w*.12,h*.45,w*.88,h*.78),fill=145,outline=40,width=max(1,w//80))
                d.rectangle((w*.2,h*.27,w*.49,h*.48),fill=180,outline=50,width=max(1,w//80))
                for i in range(4):
                    x=w*(.23+i*.17);d.ellipse((x-w*.08,h*.69,x+w*.08,h*.92),fill=70,outline=40)
                d.line((0,h*.93,w,h*.93),fill=40,width=max(1,h//60))
            elif motif == "science":
                d.ellipse((w*.28,h*.2,w*.72,h*.8),fill=175,outline=50,width=max(1,w//70))
                for a in (0,60,120):
                    orbit=Image.new("L",size,255);o=ImageDraw.Draw(orbit)
                    o.ellipse((w*.05,h*.36,w*.95,h*.64),outline=60,width=max(1,w//60))
                    orbit=orbit.rotate(a,resample=Image.Resampling.BICUBIC,fillcolor=255)
                    gray=ImageChops.darker(gray,orbit)
            else:
                d.ellipse((w*.16,h*.16,w*.84,h*.84),fill=223,outline=65,width=max(1,w//55))
                d.polygon([(w*.5,h*.35),(w*.65,h*.46),(w*.59,h*.64),(w*.41,h*.64),(w*.35,h*.46)],fill=80)
                for a in range(0,360,72):
                    d.line((w*.5,h*.5,w*(.5+.33*math.cos(math.radians(a))),h*(.5+.33*math.sin(math.radians(a)))),fill=80,width=max(1,w//90))
    # Contours plus density-dependent etched lines create printed tonal artwork.
    pixels=np.asarray(gray).astype(np.float32)
    yy,xx=np.mgrid[:h,:w]
    period=max(3,w//75)
    hatch=((yy+.22*xx) % period) < (255-pixels)/255*period*.9
    cross=((yy-.65*xx) % (period*1.45)) < .7
    density=np.where(hatch | ((pixels<100)&cross),220, (255-pixels)*.20)
    edges=gray.filter(ImageFilter.FIND_EDGES)
    edge=np.asarray(edges)
    density=np.maximum(density,np.where((edge>45)&(pixels<245),145,0))
    density[[0,-1],:]=0;density[:,[0,-1]]=0
    return Image.fromarray(np.uint8(np.clip(density,0,235)))


def render_stamp(size, content, rng, options, source=None):
    w,h=size
    if min(size)<64: raise ValueError("Paper stamp regions need at least 64×64 pixels for the artwork and lettering")
    scale=2 if max(size)<=800 else 1
    W,H=w*scale,h*scale; margin=max(5,round(min(W,H)*.045))
    paper_mask=Image.new("L",(W,H));pd=ImageDraw.Draw(paper_mask)
    pd.rectangle((margin,margin,W-margin-1,H-margin-1),fill=255)
    if options.stamp_perforated:
        edge_rng=random.Random();edge_rng.setstate(rng.getstate())
        spacing=max(10,round(min(W,H)/15));radius=spacing*.24
        for horizontal in (True,False):
            length=W if horizontal else H
            count=max(3,round((length-2*margin)/spacing))
            for i in range(count+1):
                p=margin+(length-2*margin)*i/count+edge_rng.uniform(-.5,.5)
                for fixed in (margin,H-margin if horizontal else W-margin):
                    x,y=(p,fixed) if horizontal else (fixed,p)
                    pd.ellipse((x-radius,y-radius,x+radius,y+radius),fill=0)
    age=options.stamp_age
    noise=np.random.default_rng(rng.getrandbits(64))
    yy,xx=np.mgrid[:H,:W]
    texture=noise.normal(0,1.5+age*3,(H,W))
    edge=np.minimum.reduce([xx,yy,W-xx-1,H-yy-1])/max(1,min(W,H)*.2)
    stain=np.maximum(0,1-edge)*age*18
    base=np.array((249-age*21,246-age*29,231-age*45))
    paper=Image.fromarray(np.uint8(np.clip(base+texture[:,:,None]-stain[:,:,None],0,255))).convert("RGBA")
    paper.putalpha(paper_mask)
    palette=options.stamp_palette
    if palette=="random":palette=rng.choice(tuple(COLORS))
    color=tuple(bytes.fromhex(options.stamp_color[1:])) if palette=="custom" else COLORS.get(palette,(80,79,118))
    default_black=options.stamp_ink_mode=="default" and options.stamp_palette=="black"
    print_options=options.model_copy(update={"ink_opacity_mode":"fixed","ink_opacity":1,"ink_finish":"clean"}) if default_black else options
    rgba=(*color,255)
    ink=Image.new("RGBA",(W,H));d=ImageDraw.Draw(ink)
    inset=margin+max(6,round(min(W,H)*.04));iw=W-2*inset;ih=H-2*inset
    d.rectangle((inset,inset,W-inset,H-inset),outline=rgba,width=max(1,scale))
    if content["style"]=="revenue":
        for k in range(3):
            pad=(k+2)*scale
            d.rounded_rectangle((inset+pad,inset+pad,W-inset-pad,H-inset-pad),radius=12*scale,outline=rgba,width=scale)
    top_h=ih*.11;bottom_h=ih*.10
    artbox=(round(inset+iw*.06),round(inset+top_h+ih*.035),round(iw*.88),round(ih*.67))
    ax,ay,aw,ah=artbox
    artalpha=_art((aw,ah),content["style"],rng,source,content.get("motif"))
    if content["style"]=="revenue":
        vignette=Image.new("L",(aw,ah));ImageDraw.Draw(vignette).ellipse((aw*.08,0,aw*.92,ah),fill=255)
        artalpha=ImageChops.multiply(artalpha,vignette)
    artlayer=Image.new("RGBA",(aw,ah),rgba)
    if palette=="multicolor":
        tones=np.array([(45,94,114),(125,75,94),(152,108,43),(62,115,72)],dtype=np.uint8)
        strips=tones[np.minimum(3,np.arange(ah)*4//ah)]
        rgb=np.broadcast_to(strips[:,None,:],(ah,aw,3)).copy()
        artlayer=Image.fromarray(rgb).convert("RGBA")
    artlayer.putalpha(artalpha);ink.alpha_composite(artlayer,(ax,ay));d=ImageDraw.Draw(ink)
    if content["style"]=="revenue":
        for k in range(3):
            d.ellipse((ax+aw*.06-k*2*scale,ay-k*scale,ax+aw*.94+k*2*scale,ay+ah+k*scale),outline=rgba,width=scale)
        for cx,cy in ((inset+iw*.08,inset+ih*.16),(W-inset-iw*.08,inset+ih*.16),(inset+iw*.08,H-inset-ih*.18),(W-inset-iw*.08,H-inset-ih*.18)):
            radius=min(iw,ih)*.045
            d.line([(cx+math.cos(a*.1)*radius*(1+.27*math.sin(a*.7)),cy+math.sin(a*.1)*radius*(1+.27*math.sin(a*.7))) for a in range(64)],fill=rgba,width=scale)
    _letter(d,(inset+iw*.04,inset+ih*.01,iw*.92,top_h),content["issuer"],rgba,ih*.072,bold=True)
    _letter(d,(inset+iw*.03,H-inset-ih*.13,iw*.94,bottom_h),content["caption"],rgba,ih*.058,bold=True)
    # Denomination is a separate strong visual element, as in the references.
    denomfont=max(6,round(min(iw*.23,ih*.15)))
    denom_box=(inset+iw*.02,inset+top_h+ih*.025,iw*.33,ih*.15)
    # Clear artwork behind the value; the paper itself remains on its own layer.
    ImageDraw.Draw(ink).rectangle((denom_box[0],denom_box[1],denom_box[0]+denom_box[2],denom_box[1]+denom_box[3]),fill=(0,0,0,0))
    _letter(ImageDraw.Draw(ink),denom_box,content["denomination"],rgba,denomfont,bold=True)
    # Printed ink fades and chips, while the physical paper remains present.
    alpha=np.array(ink.getchannel("A")).astype(np.float32)
    alpha*=np.clip(1-noise.random((H,W))*age*.35,.5,1)
    ink.putalpha(Image.fromarray(np.uint8(alpha)))
    ink,_,finish=apply_ink_finish(ink,rng,print_options,"paper_stamp")
    cancellation=options.stamp_cancellation
    if cancellation=="random":cancellation=rng.choice(("none","none","postmark","waves","pen"))
    if cancellation in {"postmark","waves"}:
        cancel_options=options.model_copy(update={"rubber_stamp_style":cancellation,"rubber_stamp_color":"black",
            "ink_opacity_mode":"fixed","ink_opacity":.75})
        c=plan_rubber_stamp(cancel_options,rng.randrange(2**31))
        cw,ch=(round(W*.93),round(H*.68)) if cancellation=="postmark" else (round(W*.98),round(H*.45))
        cancel,_,_=render_rubber_stamp((cw,ch),c,rng,cancel_options)
        cancel=cancel.rotate(rng.uniform(-17,17),resample=Image.Resampling.BICUBIC,expand=False)
        ink.alpha_composite(cancel,(round(W*.01),round(H*.21)))
    elif cancellation=="pen":
        d=ImageDraw.Draw(ink)
        for i in range(rng.randrange(2,4)):
            points=[(W*(.16+j*.027),H*(.3+i*.12)+math.sin(j*.5+i)*H*.12) for j in range(25)]
            d.line(points,fill=(37,35,43,195),width=max(1,scale*2))
    ink,_,opacity=apply_ink_opacity(ink,rng,print_options,"paper_stamp")
    ink.putalpha(ImageChops.multiply(ink.getchannel("A"),paper_mask))
    paper.alpha_composite(ink)
    if scale!=1:paper=paper.resize(size,Image.Resampling.LANCZOS)
    mask=paper.getchannel("A").point(lambda p:255 if p else 0)
    text="\n".join((content["issuer"],content["denomination"],content["caption"]))
    return paper,mask,{"engine":"paper-stamp-v1","style":content["style"],"palette":palette,"text":text,
                       "issuer":content["issuer"],"caption":content["caption"],"denomination":content["denomination"],
                       "content_mode":content["mode"],"perforated":options.stamp_perforated,"paper_age":age,
                       "ink_mode":"default" if default_black else "custom","ink_color":"#%02x%02x%02x"%color,
                       "cancellation":cancellation,"ink_finish":finish,"artwork_source":"approved_asset" if source is not None else "procedural_engraving",
                       "mask_semantics":"paper silhouette including perforations",**opacity}
