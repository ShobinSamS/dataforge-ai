"""Seeded fictional lettering with pen continuations anchored to the glyphs."""
import random
import re
from functools import lru_cache
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from .fonts import installed_fonts,load_font,cursive_font_id,resolve_font_weight
from .schemas import RuleOptions
from .signature_strokes import PEN_STYLES,render_pen_signature
from .ink import apply_ink_opacity
from .ink_finish import apply_ink_finish
from .colors import choose_color,restore_ink_colors,rgb

EXPRESSIVE=("tall_initial","compact","angular","looped","sweeping")
STYLES=("name","first_name","single_letter","two_letters","initials","letter_wave","monogram","flourish")+EXPRESSIVE+PEN_STYLES


def content_mode(style,rng):
    if style.signature_content!="mixed":return style.signature_content
    independent=random.Random();independent.setstate(rng.getstate())
    return random.Random(independent.getrandbits(64)^0x434F4E54).choice(("current","name","alphabet"))


def signature_plan(value: str,rng:random.Random,style:RuleOptions) -> dict:
    mode=content_mode(style,rng)
    content_rng=random.Random();content_rng.setstate(rng.getstate())
    content_rng=random.Random(content_rng.getrandbits(64)^0x414C5048)
    words=re.findall(r"[^\W\d_]+",value,flags=re.UNICODE)
    if not words:raise ValueError("Signature text needs at least one alphabetic character")
    first,last=words[0],words[-1]
    initials=first[0].upper()+(last[0].upper() if len(words)>1 else first[min(1,len(first)-1)].upper())
    family=rng.choices(STYLES,weights=(1,1,1,1,1,1,1,1,2,2,2,2,2,5,4,4,4,4,3,4,4,5,5))[0] if style.signature_style=="mixed" else style.signature_style
    if family=="single_letter":chunks=[rng.choice(initials)]
    elif family in {"two_letters","monogram"}:chunks=[initials]
    elif family=="initials":chunks=[" ".join(w[0].upper()+"." for w in words[:3])]
    elif family=="first_name":chunks=[first]
    elif family=="letter_wave":
        prefix=initials if rng.random()<.6 else initials[0]
        suffix=last[min(1,len(last)-1)].lower() if len(prefix)==2 else initials[-1]
        chunks=[prefix,suffix]
    elif family=="angular":chunks=[initials[0]+" "+last] if len(words)>1 else [first]
    elif family in EXPRESSIVE:chunks=[" ".join(words)]
    elif family=="gestural":chunks=[first[:rng.randint(1,min(4,len(first)))]+initials[-1]+last[-rng.randint(1,min(2,len(last))):]]
    elif family=="stacked":chunks=[first+"\n"+last] if len(words)>1 else [first]
    elif family=="initial_bridge":chunks=[initials+" "+last[-1].lower()]
    elif family=="minimal":chunks=[rng.choice((initials,first[0].upper(),first))]
    elif family=="surname":chunks=[first[0].upper()+" "+last] if len(words)>1 else [first]
    elif family=="split":chunks=[initials+" "+last[1:3].lower()]
    elif family=="crossed":chunks=[initials if rng.random()<.5 else first[:2]+last[:2]]
    elif family=="terminal_loop":chunks=[rng.choice((first,last,first+" "+last))]
    elif family in {"enclosed","interwoven"}:chunks=[" ".join(words)]
    else:chunks=[value.strip()]
    if mode=="name":
        chunks=[" ".join(words)]
        if family=="stacked" and len(words)>1:chunks=[" ".join(words[:-1])+"\n"+words[-1]]
        elif family=="letter_wave" and len(words)>1:chunks=[" ".join(words[:-1])+" ",words[-1]]
    elif mode=="alphabet":
        letters="".join(word[0].upper() for word in words) if len(words)>1 else first[:3].upper()
        minimum=2 if family=="letter_wave" and len(letters)>1 else 1
        letters=letters[:content_rng.randint(minimum,min(3,len(letters)))]
        chunks=[letters[:-1],letters[-1]] if family=="letter_wave" and len(letters)>1 else [letters]
    fonts=installed_fonts()
    choices=[key for key in ("segoesc","freescpt","gabriola","brushsci","mistral","lhandw") if key in fonts]
    face=(rng.choice(choices) if choices else cursive_font_id()) if style.font_id=="auto" else style.font_id
    return {"style":family,"text":"".join(chunks),"chunks":chunks,"content_mode":mode,"font_id":resolve_font_weight(face,style.font_weight),
        "finish":family in {"monogram","flourish","looped","sweeping"} or
                 (family in {"letter_wave","tall_initial"} and rng.random()<.6)}


def _curve(draw,points,ink,width):
    a,b,c,d=points
    values=[]
    for t in np.linspace(0,1,65):
        values.append(tuple((1-t)**3*a[k]+3*(1-t)**2*t*b[k]+3*(1-t)*t*t*c[k]+t**3*d[k] for k in (0,1)))
    # Continuous pressure changes along the gesture, rather than uniform wire.
    for index in range(1,len(values)):
        pressure=.65+.45*np.sin(np.pi*index/(len(values)-1))
        draw.line(values[index-1:index+1],fill=ink,width=max(1,round(width*pressure)))


def _anchor(alpha,point,bounds=None):
    if bounds:
        left,top,right,bottom=map(int,bounds)
        yy,xx=np.where(alpha[top:bottom,left:right]>80);xx=xx+left;yy=yy+top
    else:yy,xx=np.where(alpha>80)
    if not len(xx):raise ValueError("No visible signature glyphs; choose a larger region or another font")
    index=np.argmin((xx-point[0])**2+(yy-point[1])**2)
    return float(xx[index]),float(yy[index])


@lru_cache(maxsize=256)
def _pen_glyph(font_id,char):
    """Thin local font outlines into a ballpoint-like centre line, preserving joins.

    Zhang–Suen thinning uses the eight-neighbour topology; unlike erosion alone
    it preserves thin connecting strokes. Cache individual font glyphs only.
    """
    face=load_font(100,font_id);bounds=face.getbbox(char,anchor="ls")
    glyph=Image.new("L",(max(1,bounds[2]-bounds[0])+4,max(1,bounds[3]-bounds[1])+4))
    ImageDraw.Draw(glyph).text((2-bounds[0],2-bounds[1]),char,font=face,fill=255,anchor="ls")
    pixels=np.asarray(glyph)>100
    for _ in range(min(glyph.size)):
        changed=False
        for step in (0,1):
            p=np.pad(pixels,1)
            n=[p[:-2,1:-1],p[:-2,2:],p[1:-1,2:],p[2:,2:],p[2:,1:-1],p[2:,:-2],p[1:-1,:-2],p[:-2,:-2]]
            neighbours=sum(item.astype(np.uint8) for item in n)
            transitions=sum((~n[i]&n[(i+1)%8]).astype(np.uint8) for i in range(8))
            if step==0:clear=~(n[0]&n[2]&n[4]) & ~(n[2]&n[4]&n[6])
            else:clear=~(n[0]&n[2]&n[6]) & ~(n[0]&n[4]&n[6])
            remove=pixels & (neighbours>=2) & (neighbours<=6) & (transitions==1) & clear
            if np.any(remove):pixels=pixels & ~remove;changed=True
        if not changed:break
    return Image.fromarray(pixels.astype(np.uint8)*255),bounds


def _expressive_layer(plan,rng,ink,weight):
    """Compose fictional lettering with separate capital/body proportions.

    Work in pen coordinates before fitting the complete design into its region.
    Font outlines supply the letters; proportions, joins and returns are seeded
    gestures. No source-signature pixels or reference-name traces are used.
    """
    family=plan["style"];text=plan["text"]
    if len(text)>128:raise ValueError("Expressive signatures support up to 128 signing characters; shorten the text or choose a simple lettering style")
    canvas=Image.new("RGBA",(max(1400,len(text)*150+800),650))
    x=220.;baseline=370.;letters=[];capitals=[];joins=[];previous=None
    rise=min(rng.uniform(.04,.12) if family!="compact" else rng.uniform(.01,.06),85/max(1,len(text)*65))
    compression=rng.uniform(.48,.7) if family in {"compact","angular"} else rng.uniform(.6,.85)
    new_word=True
    for char in text:
        if char.isspace():
            x+=rng.uniform(12,24);new_word=True;previous=None;continue
        capital=new_word;new_word=False
        centre,bounds=_pen_glyph(plan["font_id"],char)
        if capital:
            sy=rng.uniform(2.15,2.65) if family!="compact" else rng.uniform(1.25,1.6)
            sx=rng.uniform(1.15,1.65) if family in {"looped","sweeping"} else rng.uniform(.8,1.15)
        else:
            sy=rng.uniform(.60,.88) if family!="angular" else rng.uniform(.9,1.15)
            sx=compression*rng.uniform(.88,1.1)
        import cv2
        line=np.asarray(centre.resize((max(2,round(centre.width*sx)),max(2,round(centre.height*sy))),Image.Resampling.BICUBIC))
        # Preserve opaque pen ink when shrinking a one-pixel centre line; direct
        # dilation of fractional alpha would leave pale gaps in narrow letters.
        line=(line>35).astype(np.uint8)*255
        line=cv2.dilate(line,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7) if weight=="bold" else (5,5)))
        line=cv2.GaussianBlur(line,(3,3),.5)
        glyph=Image.new("RGBA",(line.shape[1],line.shape[0]),ink);glyph.putalpha(Image.fromarray(line))
        yy=baseline+bounds[1]*sy-rise*(x-220)+rng.uniform(-2,2)
        xx=round(x);yy=round(yy)
        canvas.alpha_composite(glyph,(xx,yy))
        box=(xx,yy,xx+glyph.width,yy+glyph.height)
        letters.append(box)
        if capital:capitals.append(box)
        # Joins start/end on ink in each glyph; no arbitrary disconnected scribble.
        if previous:
            # Read only the two glyph crops, not a page-sized alpha per letter.
            def at(rect,point):
                alpha=np.asarray(canvas.crop(rect).getchannel("A"))
                local=_anchor(alpha,(point[0]-rect[0],point[1]-rect[1]))
                return local[0]+rect[0],local[1]+rect[1]
            a=at(previous,(previous[2]-2,baseline-rise*(previous[2]-220)-5))
            b=at(box,(box[0]+2,baseline-rise*(box[0]-220)-6))
            dx=b[0]-a[0]
            joins.append((a,(a[0]+dx*.4,a[1]-5),(b[0]-dx*.35,b[1]+5),b))
        previous=box
        # Capitals overlap the small body; lowercase letters stay tightly joined.
        x+=glyph.width*(rng.uniform(.46,.65) if capital else rng.uniform(.78,.9))
    draw=ImageDraw.Draw(canvas)
    alpha=np.asarray(canvas.getchannel("A"))
    import cv2
    core=(alpha>127).astype(np.uint8)
    distances=cv2.distanceTransform(core,cv2.DIST_L2,3)
    pen=max(2,min(5,round(2*float(np.percentile(distances[core>0],60)))))
    for points in joins:_curve(draw,points,ink,pen)
    connection_count=len(joins)
    left,top,right,bottom=canvas.getbbox();width=right-left;height=bottom-top
    if family=="looped":
        # A large oval grows out of an initial and returns into that same letter.
        cap=rng.choice(capitals);ch=cap[3]-cap[1];cw=cap[2]-cap[0]
        start=_anchor(alpha,(cap[0]+cw*.35,cap[1]+ch*.75),cap)
        end=_anchor(alpha,(cap[0]+cw*.65,cap[1]+ch*.50),cap)
        turn=(cap[0]+cw*.45,cap[1]-35)
        _curve(draw,(start,(cap[0]-100,cap[1]-5),(turn[0]-85,turn[1]-20),turn),ink,pen)
        _curve(draw,(turn,(turn[0]+140,turn[1]+10),(cap[2]+70,cap[3]+45),end),ink,pen)
        connection_count+=1
    if plan["finish"]:
        last=letters[-1];cap=capitals[0]
        start=_anchor(alpha,(last[2],last[1]+(last[3]-last[1])*.65),last)
        end=_anchor(alpha,(cap[0]+(cap[2]-cap[0])*.6,cap[1]+(cap[3]-cap[1])*.55),cap)
        if family=="sweeping":
            # Terminal-to-leading-capital return: broad rising crossbar, then a
            # tapered underline which reconnects with the initial.
            turn=(left-80,bottom+35)
            _curve(draw,(start,(right+170,start[1]-90),(turn[0]+width*.5,turn[1]-35),turn),ink,pen)
            _curve(draw,(turn,(turn[0]-65,turn[1]+15),(end[0]-40,end[1]+35),end),ink,pen)
        else:
            turn=(left+width*.50,top-35)
            _curve(draw,(start,(right+130,start[1]-30),(turn[0]+width*.25,turn[1]-15),turn),ink,pen)
            _curve(draw,(turn,(turn[0]-width*.25,turn[1]+15),(end[0]-50,end[1]-10),end),ink,pen)
        connection_count+=1
    # Apply a stronger signing slant to the complete pen design; generous source
    # margins and a final ink crop keep all connected curves inside the output.
    shear=rng.uniform(.12,.28) if family!="angular" else rng.uniform(.25,.42)
    canvas=canvas.transform(canvas.size,Image.Transform.AFFINE,(1,shear,-shear*325,0,1,0),resample=Image.Resampling.BICUBIC)
    return canvas.crop(canvas.getbbox()),connection_count


def _fit_expressive(size,plan,rng,style,scale):
    W,H=size
    design,connections=_expressive_layer(plan,rng,style.text_color,style.font_weight)
    ratio=min(W*.88/design.width,H*.80/design.height)
    if style.font_size:ratio=min(ratio,style.font_size*scale/100)
    design=design.resize((max(1,round(design.width*ratio)),max(1,round(design.height*ratio))),Image.Resampling.LANCZOS)
    layer=Image.new("RGBA",(W,H))
    layer.alpha_composite(design,((W-design.width)//2,(H-design.height)//2))
    return layer,connections


def render_signature(size,value,rng:random.Random,style:RuleOptions,artwork=None):
    requested=style.signature_content
    resolved=content_mode(style,rng)
    style=style.model_copy(update={"signature_content":resolved,"text_color":choose_color(style,rng,"signature")})
    # Use an independent seeded stream so pen weight cannot change the chosen
    # letters, layout or ornaments, and explicit weight choices remain fixed.
    weight_rng=random.Random();weight_rng.setstate(rng.getstate())
    weight_rng=random.Random(weight_rng.getrandbits(64)^0x5349474E)
    weight,factor=weight_rng.choices((("normal",1.0),("medium",1.65),("bold",2.4)),weights=(60,25,15))[0] if style.font_weight=="auto" else (style.font_weight,1.0)
    if artwork is None:
        layer,mask,info=_render_signature(size,value,rng,style)
    else:
        from PIL import ImageOps
        from .seal_artwork import artwork_alpha
        tile=artwork.convert('RGBA')
        alpha=artwork_alpha(tile)
        if not alpha.getbbox():raise ValueError('Signature artwork has no visible ink')
        alpha=alpha.crop(alpha.getbbox());alpha=ImageOps.contain(alpha,(max(1,int(size[0]*.9)),max(1,int(size[1]*.8))))
        layer=Image.new('RGBA',size);ink=Image.new('RGBA',alpha.size,style.text_color);ink.putalpha(alpha)
        layer.alpha_composite(ink,((size[0]-alpha.width)//2,(size[1]-alpha.height)//2));mask=layer.getchannel('A')
        info={'style':'generated_artwork','text':'','engine':'image-pool','transcription_verified':False,'lettering_only':False}
    if factor>1:
        import cv2
        alpha=layer.getchannel("A")
        core=(np.asarray(alpha)>100).astype(np.uint8)
        distances=cv2.distanceTransform(core,cv2.DIST_L2,3)
        nib=float(np.percentile(distances[core>0],70)) if np.any(core) else 1
        radius=max(1,round(3*min(size[1]*.015,max(.6,nib))*(factor-1)))
        # Grow ink at 3x resolution, then antialias back into the same region.
        alpha=alpha.resize((size[0]*3,size[1]*3),Image.Resampling.BICUBIC).filter(ImageFilter.MaxFilter(radius*2+1)).resize(size,Image.Resampling.LANCZOS)
        layer=Image.new("RGBA",size,style.text_color);layer.putalpha(alpha)
        mask=alpha.point(lambda p:255 if p else 0)
    if style.signature_thickness>1:
        # Add a rounded nib to the current pen weight. A square max-filter at
        # the multiplied random weight can fill small letters into solid blocks.
        import cv2
        alpha=layer.getchannel("A")
        core=(np.asarray(alpha)>100).astype(np.uint8)
        distances=cv2.distanceTransform(core,cv2.DIST_L2,3)
        nib=float(np.percentile(distances[core>0],70)) if np.any(core) else 1
        radius=max(1,min(round(min(size)*.055*3),round(3*max(.8,nib,size[1]*.008)*(style.signature_thickness-1))))
        large=np.asarray(alpha.resize((size[0]*3,size[1]*3),Image.Resampling.BICUBIC))
        kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,radius*2+1))
        alpha=Image.fromarray(cv2.dilate(large,kernel)).resize(size,Image.Resampling.LANCZOS)
        layer=Image.new("RGBA",size,style.text_color);layer.putalpha(alpha)
        mask=alpha.point(lambda p:255 if p else 0)
    layer,mask,finish=apply_ink_finish(layer,rng,style,"signature")
    if style.color_mode in {"manual","random","mixed"}:
        layer=restore_ink_colors(layer,[rgb(style.text_color)])
    layer,mask,opacity_info=apply_ink_opacity(layer,rng,style,"signature")
    info.update(stroke_weight=weight,thickness_scale=factor,thickness_multiplier=style.signature_thickness,
                content_mode=resolved,requested_content=requested,text_color=style.text_color,ink_finish=finish,**opacity_info)
    return layer,mask,info


def _render_signature(size,value,rng:random.Random,style:RuleOptions):
    w,h=size;scale=3 if w*h<=400_000 else 1
    W,H=w*scale,h*scale
    plan=signature_plan(value,rng,style)
    if plan["style"] in PEN_STYLES and all(c.isascii() for c in plan["text"]):
        if len(plan["text"])>128:raise ValueError("Pen signatures support up to 128 signing characters")
        layer,info=render_pen_signature((W,H),plan["text"],plan["style"],rng,style.text_color,_curve,style.font_weight=="bold",pressure=style.ink_finish!='clean')
        if scale>1:layer=layer.resize((w,h),Image.Resampling.LANCZOS)
        mask=layer.getchannel("A").point(lambda p:255 if p else 0)
        info.update(style=plan["style"],text=plan["text"],font_id="pen-paths",connection_count=info["stroke_count"],generator_version="signature-v3")
        return layer,mask,info
    if plan["style"] in EXPRESSIVE:
        layer,count=_fit_expressive((W,H),plan,rng,style,scale)
        if scale>1:layer=layer.resize((w,h),Image.Resampling.LANCZOS)
        mask=layer.getchannel("A").point(lambda p:255 if p else 0)
        return layer,mask,{"style":plan["style"],"text":plan["text"],"font_id":plan["font_id"],
            "has_flourish":plan["finish"],"has_wave":False,"connection_count":count,"lettering_only":not count,
            "letter_proportions":"compressed" if plan["style"]=="compact" else "oversized_initials"}
    ink=style.text_color
    layer=Image.new("RGBA",(W,H));draw=ImageDraw.Draw(layer)
    chunks=list(plan["chunks"])
    if plan["style"]=="monogram" and plan["content_mode"]!="name":chunks=list(chunks[0])
    max_size=style.font_size or min(200,max(12,round(h*1.6)))
    for pixels in range(max_size,5,-1):
        face=load_font(pixels*scale,plan["font_id"])
        bounds=[draw.textbbox((0,0),text,font=face) for text in chunks]
        widths=[b[2]-b[0] for b in bounds]
        top=min(b[1] for b in bounds);bottom=max(b[3] for b in bounds);height=bottom-top
        gap=max(pixels*scale*.28,height*.5) if plan["style"]=="letter_wave" else 0
        advance=widths[0]*.45 if plan["style"]=="monogram" else widths[0]+gap
        width=advance+widths[-1] if len(chunks)>1 else widths[0]
        if width<=W*.80 and height<=H*.60:break
    else:raise ValueError("Signature cannot fit this region; enlarge it or shorten the signing text")
    x=(W-width)/2;y=(H-height)/2
    boxes=[]
    for index,(text,b) in enumerate(zip(chunks,bounds)):
        xx=x+index*advance
        draw.text((xx-b[0],y-top),text,font=face,fill=ink)
        boxes.append((xx,y+b[1]-top,xx+widths[index],y+b[3]-top))
    alpha=np.asarray(layer.getchannel("A"))
    import cv2
    core=(alpha>127).astype(np.uint8)
    distances=cv2.distanceTransform(core,cv2.DIST_L2,3)
    pen=2*float(np.percentile(distances[core>0],65)) if np.any(core) else scale
    stroke=max(scale,min(round(H*.03),round(pen)));connections=[]
    if plan["style"]=="letter_wave":
        a=boxes[0];b=boxes[-1]
        start=_anchor(alpha,(a[2],a[1]+(a[3]-a[1])*.72),a)
        end=_anchor(alpha,(b[0],b[1]+(b[3]-b[1])*.72),b)
        dx=end[0]-start[0];mid=((start[0]+end[0])/2,(start[1]+end[1])/2)
        amplitude=min(height*.11,max(scale*2,dx*.2))
        _curve(draw,(start,(start[0]+dx*.18,start[1]-amplitude),(mid[0]-dx*.12,mid[1]+amplitude),mid),ink,stroke)
        _curve(draw,(mid,(mid[0]+dx*.12,mid[1]-amplitude),(end[0]-dx*.18,end[1]+amplitude),end),ink,stroke)
        connections.append({"kind":"letter_wave","start":start,"end":end})
    if plan["finish"]:
        last=boxes[-1];first=boxes[0]
        start=_anchor(alpha,(last[2],last[1]+(last[3]-last[1])*.72),last)
        # Return into the lettering, not to a far-left corner: that would frame
        # the name like a box rather than continue a signing gesture.
        end=_anchor(alpha,(x+width*rng.uniform(.3,.62),y+height*rng.uniform(.22,.65)))
        left=max(W*.06,x-width*.08);right=min(W*.94,x+width+max(width*.12,H*.15))
        if rng.random()<.65:
            # One pen continuation travels around the terminal, over the upper
            # lettering and back into a real glyph, with a shared tangent.
            turn=(start[0]-width*rng.uniform(.12,.25),max(H*.13,y-height*rng.uniform(.04,.18)))
            tangent=(max(scale*3,width*.12),height*rng.uniform(.04,.16))
            _curve(draw,(start,(right,start[1]-height*.12),(turn[0]+tangent[0],turn[1]-tangent[1]),turn),ink,stroke)
            _curve(draw,(turn,(turn[0]-tangent[0],turn[1]+tangent[1]),(end[0]-height*.25,end[1]-height*.20),end),ink,stroke)
        else:
            # An attached lower return, rather than an unrelated straight line.
            turn=(max(left,x+width*rng.uniform(.28,.45)),min(H*.87,y+height+H*rng.uniform(.03,.08)))
            _curve(draw,(start,(right,start[1]+height*.10),(turn[0]+width*.18,turn[1]+height*.08),turn),ink,stroke)
            _curve(draw,(turn,(turn[0]-width*.18,turn[1]-height*.08),(end[0]-height*.25,end[1]+height*.12),end),ink,stroke)
        connections.append({"kind":"connected_finish","start":start,"end":end})
    # Small seeded slant differences keep short letter forms from all looking
    # identical. Padding bounds the shear so letters/curves stay inside the box.
    shear=rng.uniform(-1,1)*min(.12,W*.06/max(1,H))
    layer=layer.transform((W,H),Image.Transform.AFFINE,(1,shear,-shear*H/2,0,1,0),resample=Image.Resampling.BICUBIC)
    if scale>1:layer=layer.resize((w,h),Image.Resampling.LANCZOS)
    mask=layer.getchannel("A").point(lambda p:255 if p else 0)
    info={"style":plan["style"],"text":plan["text"],"font_id":plan["font_id"],"has_flourish":plan["finish"],
        "has_wave":plan["style"]=="letter_wave","connection_count":len(connections),"lettering_only":not connections}
    return layer,mask,info
