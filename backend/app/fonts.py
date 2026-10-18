"""Installed-font selection and local raster shape matching, without font downloads."""
import os
import re
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .restoration import ink_mask


@lru_cache(maxsize=1)
def installed_fonts() -> dict:
    roots=[Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts",
           Path("/usr/share/fonts/truetype/dejavu"),Path("/usr/share/fonts/truetype/liberation2")]
    names=["arial","arialbd","ariali","arialbi","calibri","calibrib","cambria","cambriab",
           "times","timesbd","timesi","cour","courbd","verdana","verdanab","segoeui","segoeuib",
           "tahoma","tahomabd","trebuc","DejaVuSans","DejaVuSans-Bold","DejaVuSerif",
           "DejaVuSansMono","LiberationSans-Regular","LiberationSerif-Regular","LiberationMono-Regular"]
    result={}
    for root in roots:
        for name in names:
            path=root/(name+".ttf")
            if not path.is_file(): continue
            try:
                family,style=ImageFont.truetype(str(path),24).getname()
                result[name.lower()]={"id":name.lower(),"label":f"{family} {style}","family":family,"bold":"bold" in style.lower(),"italic":bool(re.search("italic|oblique",style,re.I)),"path":str(path)}
            except OSError: continue
    return result


@lru_cache(maxsize=512)
def load_font(size: int, font_id: str = "auto"):
    fonts=installed_fonts()
    if font_id!="auto" and font_id not in fonts: raise ValueError("Selected font is unavailable on this machine; choose an installed font")
    selected=fonts.get(font_id)
    if selected is None:
        selected=next((fonts[key] for key in ("arial","dejavusans","liberationsans-regular") if key in fonts),None)
    return ImageFont.truetype(selected["path"],size) if selected else ImageFont.load_default(size=size)


def native_font_id(name: str) -> str:
    fonts=installed_fonts();key=re.sub(r"[^a-z]","",name.lower().split("+")[-1])
    for id_,record in fonts.items():
        if key in {re.sub(r"[^a-z]","",id_),re.sub(r"[^a-z]","",record["label"].lower())}:
            return id_
    bold="bold" in key;italic="italic" in key or "oblique" in key
    family="arial" if "helvetica" in key or "arial" in key else "times" if "times" in key else "cour" if "courier" in key else ""
    suffix="bi" if bold and italic else "bd" if bold else "i" if italic else ""
    selected=family+suffix if family+suffix in fonts else "auto"
    if selected=="auto":
        selected=next((id_ for id_,record in fonts.items() if ("mono" in record["family"].lower())==("courier" in key) and record["bold"]==bold and record["italic"]==italic),"auto")
    return selected


def resolve_font_weight(font_id: str, weight: str) -> str:
    if weight=="auto": return font_id
    fonts=installed_fonts()
    if font_id=="auto": font_id=next((key for key in ("arial","dejavusans","liberationsans-regular") if key in fonts),"auto")
    selected=fonts.get(font_id)
    if not selected: return font_id
    return next((key for key,record in fonts.items() if record["family"]==selected["family"] and record["italic"]==selected["italic"] and record["bold"]==(weight=="bold")),font_id)


def foreground_pixels(crop: np.ndarray) -> np.ndarray:
    import cv2
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    _,binary=cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    border=np.concatenate([binary[0],binary[-1],binary[:,0],binary[:,-1]])
    return (binary==0 if np.median(border)>127 else binary>0).astype(np.uint8)*255


@lru_cache(maxsize=1)
def glyph_library():
    import string
    records=[];masks=[]
    for id_ in installed_fonts():
        f=load_font(100,id_)
        for char in string.ascii_letters+string.digits:
            bounds=f.getbbox(char);w,h=bounds[2]-bounds[0],bounds[3]-bounds[1]
            canvas=Image.new("L",(max(1,w),max(1,h)))
            ImageDraw.Draw(canvas).text((-bounds[0],-bounds[1]),char,font=f,fill=255)
            pixels=np.asarray(canvas)>127;yy,xx=np.where(pixels)
            if not len(xx): continue
            pixels=pixels[yy.min():yy.max()+1,xx.min():xx.max()+1]
            h,w=pixels.shape
            masks.append(np.asarray(Image.fromarray(pixels).resize((32,48),Image.Resampling.NEAREST)).reshape(-1)>0)
            records.append((id_,w/h,h))
    return records,np.asarray(masks,dtype=bool)


def match_unknown_text(crop: np.ndarray, weight: str="auto") -> dict:
    """Compare segmented letter shapes to local fonts without requiring OCR text."""
    import cv2
    foreground=foreground_pixels(crop)
    count,labels,stats,_=cv2.connectedComponentsWithStats(foreground)
    pieces=[tuple(map(int,row))+(i,) for i,row in enumerate(stats[1:],1) if row[4]>=8 and row[3]>=5 and row[2]<row[3]*2]
    if not pieces: raise ValueError("No separate source glyphs found")
    height=float(np.median([row[3] for row in sorted(pieces,key=lambda row:row[4],reverse=True)[:12]]))
    pieces=[row for row in pieces if row[3]>=height*.65 and row[3]<=height*1.5]
    pieces=sorted(pieces,key=lambda row:row[4],reverse=True)[:12]
    if len(pieces)<2: raise ValueError("Font estimation needs at least two source glyphs")
    records,templates=glyph_library()
    if not records: raise ValueError("No installed glyph templates")
    areas=templates.sum(axis=1);aspects=np.array([row[1] for row in records]);font_ids=[row[0] for row in records]
    allowed=[id_ for id_,record in installed_fonts().items() if weight=="auto" or record["bold"]==(weight=="bold")]
    scores={id_:[] for id_ in allowed};sizes={id_:[] for id_ in allowed}
    for x,y,w,h,area,label in pieces:
        glyph=labels[y:y+h,x:x+w]==label
        target=np.asarray(Image.fromarray(glyph).resize((32,48),Image.Resampling.NEAREST)).reshape(-1)>0
        intersection=np.count_nonzero(templates & target,axis=1)
        overlap=intersection/np.maximum(1,areas+target.sum()-intersection)
        aspect=np.minimum(aspects,w/h)/np.maximum(aspects,w/h)
        similarity=.75*overlap+.25*aspect
        for id_ in allowed:
            indices=np.array([i for i,key in enumerate(font_ids) if key==id_])
            index=int(indices[np.argmax(similarity[indices])])
            scores[id_].append(float(similarity[index]));sizes[id_].append(100*h/records[index][2])
    selected=max(allowed,key=lambda id_:np.mean(scores[id_]))
    return {"font_id":selected,"font_size":max(6,min(200,round(float(np.median(sizes[selected]))))),
            "similarity":round(float(np.mean(scores[selected])),4),"method":"segmented-glyph-shape-estimate"}


def match_font(image: Image.Image, box, text: str, weight: str = "auto") -> dict:
    import cv2
    if not text.strip() or len(text)>200 or "\n" in text: raise ValueError("Enter the visible single-line source text (1–200 characters) for font matching")
    x,y,w,h=box
    if x+w>image.width or y+h>image.height or w*h>2_000_000: raise ValueError("Font sample must be inside the page and at most 2 megapixels")
    crop=np.asarray(image.convert("RGB").crop((x,y,x+w,y+h)))
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    _,binary=cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    border=np.concatenate([binary[0],binary[-1],binary[:,0],binary[:,-1]])
    foreground=binary==0 if np.median(border)>127 else binary>0
    yy,xx=np.where(foreground)
    if len(xx)<5: raise ValueError("No text pixels found; tighten the sample rectangle around visible text")
    target=foreground[yy.min():yy.max()+1,xx.min():xx.max()+1]
    target_w,target_h=target.shape[1],target.shape[0]
    normalized=np.asarray(Image.fromarray(target).resize((320,64),Image.Resampling.NEAREST))>0
    best=None
    for id_,record in installed_fonts().items():
        if weight!="auto" and record["bold"]!=(weight=="bold"): continue
        probe=load_font(100,id_);bounds=probe.getbbox(text)
        estimate=max(6,min(200,round(100*target_h/max(1,bounds[3]-bounds[1]))))
        for px in range(max(6,estimate-2),min(200,estimate+2)+1):
            chosen=load_font(px,id_);bounds=chosen.getbbox(text)
            width,height=bounds[2]-bounds[0],bounds[3]-bounds[1]
            if width<1 or height<1 or width*height>4_000_000: continue
            candidate=Image.new("L",(width,height));ImageDraw.Draw(candidate).text((-bounds[0],-bounds[1]),text,font=chosen,fill=255)
            pixels=np.asarray(candidate)>127
            cy,cx=np.where(pixels)
            if len(cx)<1: continue
            pixels=pixels[cy.min():cy.max()+1,cx.min():cx.max()+1]
            height,width=pixels.shape
            mask=np.asarray(Image.fromarray(pixels).resize((320,64),Image.Resampling.NEAREST))>0
            overlap=np.count_nonzero(mask & normalized)/max(1,np.count_nonzero(mask | normalized))
            aspect=min(width/height,target_w/target_h)/max(width/height,target_w/target_h)
            score=.7*overlap+.3*aspect
            if best is None or score>best["similarity"]:
                color=np.median(crop[foreground],axis=0).astype(int)
                best={"font_id":id_,"font_size":px,"text_color":"#"+"".join(f"{c:02x}" for c in color),
                      "label":record["label"],"similarity":float(score),"method":"installed-font-shape-comparison"}
    if best is None: raise ValueError("No candidate fonts installed; select the fallback font manually")
    best["similarity"]=round(best["similarity"],4)
    best["warning"]="Estimated closest installed font; scans, background texture and unavailable fonts limit accuracy."
    return best


def prepare_typography(source: Path, regions: list) -> list:
    """Resolve source style once before original OCR strings are stripped from jobs."""
    import cv2
    with Image.open(source) as opened:
        image=opened.convert("RGB")
    prepared=[]
    for region in regions:
        if not region.replace or region.kind in {"signature","seal","qr","barcode","portrait"}:
            prepared.append(region);continue
        style=region.rule_options.model_copy(deep=True)
        x,y,w,h=region.box
        crop=np.asarray(image.crop((x,y,x+w,y+h)))
        mask=foreground_pixels(crop)
        pixels=crop[mask>0]
        if style.color_mode=="auto" and len(pixels):
            brightness=np.mean(pixels,axis=1)
            border=np.concatenate([crop[0],crop[-1],crop[:,0],crop[:,-1]])
            core=pixels[brightness<=np.percentile(brightness,35)] if np.mean(border)>=127 else pixels[brightness>=np.percentile(brightness,65)]
            color=np.median(core,axis=0).astype(int)
            style.text_color="#"+"".join(f"{value:02x}" for value in color)
        if style.font_id=="auto":
            native=native_font_id(region.source_font) if region.source_font else "auto"
            if native!="auto":
                style.font_id=native
                if style.font_size is None and region.source_font_size: style.font_size=max(6,min(200,round(region.source_font_size)))
            elif region.text.strip() and len(region.text)<=200 and "\n" not in region.text and w*h<=2_000_000:
                try:
                    match=match_font(image,region.box,region.text,style.font_weight)
                    style.font_id=match["font_id"]
                    if style.font_size is None: style.font_size=match["font_size"]
                except ValueError:
                    pass
            if style.font_id=="auto" and np.any(mask):
                try:
                    match=match_unknown_text(crop,style.font_weight)
                    style.font_id=match["font_id"]
                    if style.font_size is None: style.font_size=match["font_size"]
                except ValueError:
                    yy,xx=np.where(mask)
                    ink_height=int(yy.max()-yy.min()+1)
                    if style.font_size is None: style.font_size=max(6,min(200,round(ink_height*1.4)))
                    style.font_id=resolve_font_weight("auto",style.font_weight)
        style.font_id=resolve_font_weight(style.font_id,style.font_weight)
        prepared.append(region.model_copy(update={"rule_options":style}))
    return prepared
