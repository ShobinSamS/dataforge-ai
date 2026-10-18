"""Seeded fictional lettering with pen continuations anchored to the glyphs."""
import random
import re
import numpy as np
from PIL import Image,ImageDraw
from .fonts import installed_fonts,load_font,cursive_font_id,resolve_font_weight
from .schemas import RuleOptions

STYLES=("name","first_name","single_letter","two_letters","initials","letter_wave","monogram","flourish")


def signature_plan(value: str,rng:random.Random,style:RuleOptions) -> dict:
    words=re.findall(r"[^\W\d_]+",value,flags=re.UNICODE)
    if not words:raise ValueError("Signature text needs at least one alphabetic character")
    first,last=words[0],words[-1]
    initials=first[0].upper()+(last[0].upper() if len(words)>1 else first[min(1,len(first)-1)].upper())
    family=rng.choices(STYLES,weights=(2,2,2,3,1,3,2,2))[0] if style.signature_style=="mixed" else style.signature_style
    if family=="single_letter":chunks=[rng.choice(initials)]
    elif family in {"two_letters","monogram"}:chunks=[initials]
    elif family=="initials":chunks=[" ".join(w[0].upper()+"." for w in words[:3])]
    elif family=="first_name":chunks=[first]
    elif family=="letter_wave":
        prefix=initials if rng.random()<.6 else initials[0]
        suffix=last[min(1,len(last)-1)].lower() if len(prefix)==2 else initials[-1]
        chunks=[prefix,suffix]
    else:chunks=[value.strip()]
    fonts=installed_fonts()
    choices=[key for key in ("segoesc","freescpt","gabriola","brushsci","mistral","lhandw") if key in fonts]
    face=(rng.choice(choices) if choices else cursive_font_id()) if style.font_id=="auto" else style.font_id
    return {"style":family,"text":"".join(chunks),"chunks":chunks,"font_id":resolve_font_weight(face,style.font_weight),
        "finish":family in {"monogram","flourish"} or (family=="letter_wave" and rng.random()<.6)}


def _curve(draw,points,ink,width):
    a,b,c,d=points
    values=[]
    for t in np.linspace(0,1,65):
        values.append(tuple((1-t)**3*a[k]+3*(1-t)**2*t*b[k]+3*(1-t)*t*t*c[k]+t**3*d[k] for k in (0,1)))
    draw.line(values,fill=ink,width=width,joint="curve")


def _anchor(alpha,point,bounds=None):
    if bounds:
        left,top,right,bottom=map(int,bounds)
        yy,xx=np.where(alpha[top:bottom,left:right]>80);xx=xx+left;yy=yy+top
    else:yy,xx=np.where(alpha>80)
    if not len(xx):raise ValueError("No visible signature glyphs; choose a larger region or another font")
    index=np.argmin((xx-point[0])**2+(yy-point[1])**2)
    return float(xx[index]),float(yy[index])


def render_signature(size,value,rng:random.Random,style:RuleOptions):
    w,h=size;scale=3 if w*h<=400_000 else 1
    W,H=w*scale,h*scale
    plan=signature_plan(value,rng,style)
    ink=style.text_color
    layer=Image.new("RGBA",(W,H));draw=ImageDraw.Draw(layer)
    chunks=list(plan["chunks"])
    if plan["style"]=="monogram":chunks=list(chunks[0])
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
