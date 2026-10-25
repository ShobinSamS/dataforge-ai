"""Original English pen-path alphabet and compositional fictional signatures.

These are authored curves, not traces of the supplied signatures. Smooth stroke
paths allow letter-form, joining and layout changes independently of font files.
This is a geometric renderer, not a trained or Sigma–Lognormal handwriting model.
"""
from PIL import Image, ImageDraw
from math import cos, sin, pi

PEN_STYLES=("gestural","stacked","initial_bridge","terminal_loop","crossed","minimal","surname","split","enclosed","interwoven")

# Each tuple is one continuous pen movement. Coordinates use a baseline of 1.
UPPER={
 "A":[[(0,1),(.2,.5),(.65,0),(.6,1.1)],[(.05,.7),(.55,.6),(1,.55)]],
 "B":[[(.1,1),(.3,0),(.8,.05),(.7,.38),(.25,.5),(.9,.5),(.8,.92),(.1,1)]],
 "C":[[(.95,.12),(.6,0),(.15,.25),(0,.75),(.3,1),(.9,.8)]],
 "D":[[(.1,1),(.32,0),(.8,.03),(1,.4),(.7,.9),(.1,1)]],
 "E":[[(.9,.08),(.45,0),(.15,.3),(.55,.43),(.15,.55),(0,.87),(.35,1),(.9,.8)]],
 "F":[[(.1,1),(.3,.05),(1,0)],[(.1,.53),(.6,.45),(.9,.4)]],
 "G":[[(1,.12),(.5,0),(0,.5),(.15,.95),(.7,.9),(.85,.55),(.45,.62),(1,.58)]],
 "H":[[(0,1),(.25,0)],[(.7,0),(.55,.6),(.6,1)],[(.1,.6),(.8,.48)]],
 "I":[[(.1,.1),(.65,0),(.4,.55),(.3,1),(.8,.9)]],
 "J":[[(.05,.1),(.85,0),(.6,.7),(.3,1.2),(0,.95)]],
 "K":[[(0,1),(.25,0)],[(1,.02),(.25,.55),(.8,1.05)]],
 "L":[[(.5,0),(.3,.1),(.15,.8),(0,1),(.8,.95),(1,.8)]],
 "M":[[(0,1),(.2,0),(.5,.65),(.85,0),(.8,1),(1,.85)]],
 "N":[[(0,1),(.2,0),(.75,1),(.9,0)]],
 "O":[[(.7,0),(.2,.08),(0,.7),(.35,1),(.9,.65),(.9,.2),(.7,0),(.55,.25)]],
 "P":[[(.05,1),(.3,0),(.95,.05),(.8,.45),(.2,.48)]],
 "Q":[[(.7,0),(.15,.12),(0,.7),(.35,1),(.9,.65),(.9,.15),(.7,0)],[(.35,.7),(.8,1.1),(1.2,.95)]],
 "R":[[(0,1),(.25,0),(.9,0),(.8,.42),(.2,.5),(.85,1.05)]],
 "S":[[(.95,.1),(.6,0),(.1,.28),(.5,.55),(.8,.8),(.35,1),(0,.85)]],
 "T":[[(0,.1),(.55,0),(1.1,.05)],[(.65,0),(.45,.7),(.4,1.1)]],
 "U":[[(.1,0),(0,.8),(.3,1),(.7,.75),(.9,0),(.8,1),(1,.85)]],
 "V":[[(0,0),(.2,1),(.8,.2),(1,0)]],
 "W":[[(0,0),(.15,1),(.5,.4),(.6,1),(1,0)]],
 "X":[[(.1,0),(.8,1)],[(1,0),(.5,.6),(0,1)]],
 "Y":[[(0,0),(.2,.65),(.65,.45),(.9,0),(.6,1),(.15,1.4)]],
 "Z":[[(0,.1),(.85,0),(.15,.9),(.9,.95)],[(.2,.55),(.8,.5)]],
}
LOWER={
 "a":[[(0,.85),(.25,.45),(.65,.5),(.45,.95),(.1,1),(.05,.75),(.65,.5),(.6,1),(.9,.8)]],
 "b":[[(0,.95),(.3,0),(.45,.05),(.15,.8),(.5,.5),(.7,.7),(.45,1),(.15,.95),(.85,.8)]],
 "c":[[(.7,.55),(.35,.48),(0,.8),(.2,1),(.8,.8)]],
 "d":[[(0,.8),(.25,.5),(.6,.55),(.35,1),(0,.9),(.25,.55),(.8,0),(.55,.85),(.6,1),(.9,.8)]],
 "e":[[(0,.85),(.6,.6),(.4,.45),(.05,.7),(.2,1),(.85,.8)]],
 "f":[[(0,.85),(.55,0),(.8,.1),(.25,1.35),(.1,1.1),(.4,.65),(.85,.65)]],
 "g":[[(0,.8),(.25,.5),(.65,.5),(.4,.95),(.05,.95),(.1,.65),(.65,.5),(.35,1.4),(.05,1.5),(.25,1.1),(.9,.8)]],
 "h":[[(0,1),(.35,0),(.5,.1),(.1,.95),(.5,.5),(.7,.6),(.6,1),(.9,.8)]],
 "i":[[(0,.85),(.3,.55),(.2,.95),(.4,1),(.7,.8)],[(.35,.3),(.37,.28)]],
 "j":[[(0,.8),(.4,.55),(.2,1.4),(-.1,1.45),(0,1.1),(.8,.8)],[(.45,.28),(.46,.26)]],
 "k":[[(0,1),(.35,0),(.45,.1),(.15,.9),(.7,.48),(.3,.7),(.65,1),(.9,.8)]],
 "l":[[(0,.85),(.4,0),(.6,.1),(.15,.8),(.25,1),(.8,.8)]],
 "m":[[(0,.9),(.25,.5),(.15,1),(.55,.5),(.7,.6),(.55,1),(.95,.5),(1.1,.65),(1,1),(1.3,.8)]],
 "n":[[(0,.9),(.25,.5),(.15,1),(.6,.5),(.8,.65),(.65,1),(1,.8)]],
 "o":[[(.65,.55),(.25,.5),(0,.8),(.2,1),(.65,.85),(.65,.55),(.5,.65),(.9,.8)]],
 "p":[[(0,.85),(.3,.5),(.05,1.4),(.35,.6),(.65,.5),(.8,.8),(.45,1),(.25,.9),(.95,.8)]],
 "q":[[(0,.8),(.3,.5),(.65,.55),(.35,1),(.05,.9),(.1,.6),(.65,.55),(.4,1.4),(.65,1.2),(.9,.8)]],
 "r":[[(0,.9),(.3,.5),(.35,.75),(.65,.5),(.75,.65),(.55,1),(.9,.8)]],
 "s":[[(0,.85),(.5,.48),(.4,.7),(.6,.95),(.2,1),(.1,.85),(.9,.8)]],
 "t":[[(.5,.1),(.2,.9),(.35,1),(.8,.8)],[(0,.5),(.8,.45)]],
 "u":[[(0,.55),(.05,.95),(.3,1),(.65,.55),(.5,.95),(.7,1),(1,.8)]],
 "v":[[(0,.55),(.2,1),(.6,.6),(.7,.5),(.9,.8)]],
 "w":[[(0,.55),(.15,1),(.5,.6),(.6,1),(.95,.5),(1.1,.8)]],
 "x":[[(0,.55),(.6,1),(.9,.8)],[(.65,.5),(0,1)]],
 "y":[[(0,.55),(.1,1),(.55,.55),(.3,1.4),(0,1.5),(.2,1.1),(.9,.8)]],
 "z":[[(0,.6),(.6,.5),(.1,.95),(.65,1),(.3,1.4),(0,1.4),(.85,.8)]],
}
ALTERNATES={
 "A":[[(0,1),(.5,0),(.85,1)],[(0,.75),(.95,.5)]],
 "M":[[(0,1),(0,0),(.45,.8),(.9,0),(1,1)]],
 "R":[[(0,1),(.2,0),(.85,.2),(.2,.55),(.9,1)]],
 "S":[[(.9,0),(.1,.2),(.7,.65),(.6,1),(0,1)]],
 "K":[[(.1,1),(.1,0)],[(.95,0),(.1,.6),(1,1)]],
 "D":[[(.1,1),(.15,0),(.8,.1),(1,.55),(.5,1),(-.15,.9)]],
 "B":[[(.1,1),(.2,0)],[(0,.05),(.8,0),(.65,.45),(.1,.5),(.9,.6),(.7,1),(.1,1)]],
 "T":[[(-.2,.2),(1.2,0)],[(.6,.05),(.3,1),(.65,.9)]],
}
LOWER_ALTERNATES={
 "a":[[(0,.85),(.3,.52),(.6,.55),(.5,.95),(.15,1),(.1,.75),(.65,.5),(.6,1),(.95,.8)]],
 "r":[[(0,.9),(.25,.48),(.5,.48),(.35,.75),(.75,.62),(.65,1),(.95,.8)]],
 "s":[[(0,.85),(.55,.5),(.25,.62),(.6,.9),(.35,1),(.05,.95),(.9,.8)]],
 "m":[[(0,1),(.3,.5),(.2,1),(.65,.52),(.5,1),(.95,.55),(1.1,1),(1.3,.8)]],
 "n":[[(0,1),(.3,.5),(.2,1),(.7,.55),(.8,1),(1,.8)]],
 "l":[[(0,1),(.4,.08),(.25,.8),(.45,1),(.8,.8)]],
 "t":[[(.4,.1),(.3,.7),(.4,1),(.8,.8)],[(0,.48),(.85,.48)]],
 "e":[[(0,.9),(.6,.68),(.45,.48),(.15,.55),(.1,.9),(.35,1),(.9,.8)]],
}

# Rounded entry/return allographs for looped signing, with the loop belonging
# to the capital's pen movement. These are reusable letters, not named traces.
LOOPED_CAPITALS={
 "A":[[(-.15,.8),(.15,.25),(.7,-.08),(1,.04),(.78,.4),(.15,.62),(-.35,.48),(-.38,.18),(.1,-.02),(.65,.02),(.5,.65),(.4,1.05)],
      [(-.05,.72),(.55,.6),(1.15,.45)]],
 "I":[[(-.55,.68),(-.6,.3),(-.1,-.06),(.65,-.12),(.9,.05),(.65,.3),(.05,.65),(-.1,1),(.55,.88)]],
 "J":[[(-.4,.45),(-.35,.08),(.25,-.1),(.95,-.02),(.65,.35),(.38,.9),(-.1,1.25),(-.3,1.08),(.1,.8)]],
 "M":[[(.1,.85),(.3,.05),(-.05,-.1),(-.4,.1),(-.45,.55),(-.1,.8),(.1,.85),
       (.7,.15),(.95,-.06),(1.2,.1),(1.18,.5),(.9,.83),(.5,.85),(.7,.15),(.9,0),(.8,1),(1.3,.85)]],
 "N":[[(-.25,.8),(-.35,.18),(.02,-.06),(.28,.05),(.02,.95),(.48,.28),(.9,.02),(1.12,.16),(.78,.9),(1.15,.8)]],
 "P":[[(.05,1),(.22,.18),(.65,-.05),(1,.05),(1.08,.32),(.7,.62),(.08,.6),(-.25,.4),(-.18,.1),(.4,-.04)]],
 "Q":[[(.7,.04),(.15,-.05),(-.28,.25),(-.2,.75),(.18,.95),(.78,.66),(1,.2),(.7,.04),(.2,.65),(-.15,1.15),(1.1,.88)]],
 "R":[[(0,1),(.2,.2),(.6,-.05),(1,.05),(1.05,.3),(.7,.58),(.08,.55),(-.2,.35),(-.1,.08),(.4,-.04)],
      [(.4,.55),(.65,.85),(1.15,1)]],
 "T":[[(-.5,.48),(-.55,.12),(.02,-.08),(.85,-.12),(1.1,.02),(.9,.2),(.15,.45)],
      [(.78,.05),(.4,.65),(.35,1.05),(.8,.9)]],
 "W":[[(-.2,.15),(-.35,.78),(-.12,1),(.25,.45),(.35,.02),(.48,.15),(.3,.85),(.55,1),(.95,.4),(1.15,.05)]],
}


def render_pen_signature(size,text,family,rng,ink,curve,bold=False,pressure=True):
    """Return transparent layer plus morphology metadata, using only local paths."""
    stacked=family=="stacked"
    cap=rng.uniform(95,155);body=rng.uniform(.38,.82)
    compression=rng.uniform(.55,1.0);slant=rng.uniform(-.05,.6)
    angle=rng.uniform(-.15,.12);overlap=rng.uniform(.64,.98)
    ornamental=family in {"enclosed","interwoven"} or (pressure and family in {'terminal_loop','initial_bridge'} and rng.random()<.65)
    if ornamental:
        body=rng.uniform(.32,.52);compression=rng.uniform(.55,.78)
        overlap=rng.uniform(.38,.58);slant=rng.uniform(.22,.6)
    angular=family in {"gestural","crossed"} and rng.random()<.5
    alternate=rng.randrange(2);width=rng.uniform(2.1,3.4)*(1.6 if bold else 1)
    # A writer has one coherent rhythm. Curvature and pen speed vary the nib
    # within that rhythm, without injecting disconnected scribble strokes.
    rhythm=rng.uniform(.7,1.3) if pressure else 1
    phase=rng.uniform(0,2*pi) if pressure else 0
    movement=0
    resolution=3
    canvas=Image.new("RGBA",(max(1600,len(text)*150+600)*resolution,850*resolution));draw=ImageDraw.Draw(canvas)
    strokes=[];first_ends=[];capital_boxes=[];last=None;lift_count=0

    def move(points,ox,oy,sx,sy):
        result=[]
        for px,py in points:
            xx=ox+(px+slant*(1-py))*sx
            yy=oy+py*sy-angle*(xx-300)
            result.append((xx,yy))
        return result

    def pen(points):
        nonlocal movement
        def paint(controls):
            nonlocal movement
            if not pressure:
                curve(draw,tuple((p[0]*resolution,p[1]*resolution) for p in controls),ink,max(2,round(width*resolution)))
                return
            import math
            # Continuous pressure across spline segments, lighter fast returns
            # and a slight rounded ink dwell at tight bends.
            a,b,c,d=controls
            prev=None
            length=max(1,sum(math.dist(controls[i],controls[i+1]) for i in range(3)))
            steps=max(12,min(120,round(length*resolution/2)))
            for i in range(steps+1):
                t=i/steps
                point=tuple(((1-t)**3*a[k]+3*(1-t)**2*t*b[k]+3*(1-t)*t*t*c[k]+t**3*d[k])*resolution for k in (0,1))
                dx=3*((1-t)**2*(b[0]-a[0])+2*(1-t)*t*(c[0]-b[0])+t*t*(d[0]-c[0]))
                dy=3*((1-t)**2*(b[1]-a[1])+2*(1-t)*t*(c[1]-b[1])+t*t*(d[1]-c[1]))
                speed=math.hypot(dx,dy)/length
                nib_pressure=.85+.22*sin(phase+movement*rhythm)+.18*(1-min(1.7,speed))
                nib=max(1,round(width*resolution*nib_pressure))
                if prev is not None:draw.line((prev,point),fill=ink,width=nib)
                prev=point;movement+=length/steps*.008
        if len(points)==2:
            a,b=points;points=[a,(a[0]+(b[0]-a[0])/3,a[1]+(b[1]-a[1])/3),(a[0]+2*(b[0]-a[0])/3,a[1]+2*(b[1]-a[1])/3),b]
            paint(points);strokes.append(points);return
        # Cardinal splines retain the authored letter topology. Angular variants
        # shorten tangents, giving sharper turns without independent scribbles.
        tension=.12 if angular else .17
        for i in range(len(points)-1):
            before=points[max(0,i-1)];a=points[i];b=points[i+1];after=points[min(len(points)-1,i+2)]
            controls=(a,(a[0]+(b[0]-before[0])*tension,a[1]+(b[1]-before[1])*tension),
                (b[0]-(after[0]-a[0])*tension,b[1]-(after[1]-a[1])*tension),b)
            paint(controls);strokes.append(controls)

    x=300.;line=0
    for char in text:
        if char.isspace():
            if stacked:
                line+=1;x=330.;last=None
            else:x+=rng.uniform(15,35)
            continue
        is_cap=char.isupper()
        key=char.upper() if is_cap else char.lower()
        forms=UPPER if is_cap else LOWER
        paths=(ALTERNATES if is_cap else LOWER_ALTERNATES).get(key,forms[key]) if alternate else forms[key]
        if ornamental and is_cap:paths=LOOPED_CAPITALS.get(key,paths)
        sy=cap*rng.uniform(.85,1.15) if is_cap else cap*body*rng.uniform(.85,1.15)
        sx=sy*(rng.uniform(1.15,1.6) if is_cap and ornamental else rng.uniform(.8,1.25) if is_cap else compression)
        baseline=355+line*145+rng.uniform(-3,3)
        oy=baseline-sy
        transformed=[move(p,x,oy,sx,sy) for p in paths]
        if last is not None:
            start=transformed[0][0]
            # Join consecutive written units; pen lifts are retained for dots
            # and crossbars and between the two lines of a stacked signature.
            pen([last,((last[0]+start[0])/2,last[1]-rng.uniform(1,10)),start])
        for points in transformed:pen(points)
        lift_count+=len(paths)-1
        if is_cap:
            first_ends.append((transformed[0][0],transformed[0][-1]))
            points=[p for path in transformed for p in path]
            capital_boxes.append((min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)))
        last=transformed[0][-1]
        x+=max(12,max(p[0] for p in paths[0])*sx*overlap)
    left,top,right,bottom=(v/resolution for v in canvas.getbbox())
    ornament="none"
    if family=="enclosed":ornament="enclosing_return"
    elif family=="interwoven":ornament="interwoven_capitals"
    elif family=="terminal_loop":
        ornament=rng.choice(("upper_oval","lower_oval","terminal_spiral"))
    elif family=="crossed":ornament="crossbar"
    elif family=="initial_bridge":ornament="bridge"
    elif family=="split":ornament=rng.choice(("understrike","upper_oval","none"))
    elif family in {"gestural","surname","stacked"}:ornament=rng.choice(("none","understrike","lower_oval","crossbar"))
    if ornament!="none" and last:
        start=last;end=first_ends[0][-1];span=max(80,right-left)
        if ornament=="enclosing_return":
            # Sample a broad rounded return rather than connecting a few
            # corner points (which makes a triangular frame at small sizes).
            x0,y0,x1,y1=capital_boxes[0]
            cx=(x0+x1)/2;cy=(y0+y1)/2-cap*.05
            rx=max(cap*.85,(x1-x0)*rng.uniform(.7,.9));ry=max(cap*.6,(y1-y0)*.65)
            loop=[(cx+rx*cos(.65+i*2*pi/24),cy+ry*sin(.65+i*2*pi/24)) for i in range(25)]
            pen([start,((start[0]+loop[0][0])/2,start[1]+cap*.12),loop[0]])
            pen(loop)
            pen([loop[-1],(left+span*.35,bottom+cap*.2),(right+span*.16,bottom-cap*.2)])
        elif ornament=="interwoven_capitals":
            # Capitals already contain their own bowls. Adding another oval
            # to each would turn the letters into repeated circular frames.
            pen([start,(right+span*.12,bottom+cap*.06),(left-span*.12,bottom+cap*.22)])
        elif ornament=="crossbar":
            pen([start,(right+75,top+40),(left-60,bottom-20),end])
        elif ornament=="bridge":
            pen([start,(right+50,start[1]-25),(left+span*.45,top-30),end])
        elif ornament in {"upper_oval","terminal_spiral"}:
            pen([start,(right+90,top+30),(left+span*.4,top-65),(left-35,top+45),end])
            if ornament=="terminal_spiral":pen([end,(left+55,top+15),(left+110,top+70),(left+35,top+90),end])
        elif ornament=="lower_oval":
            pen([start,(right+75,bottom+40),(left+span*.3,bottom+90),(left-50,bottom+15),end])
        else:pen([start,(right+90,start[1]-25),(left-80,bottom+40),end])
    if family=="gestural" and rng.random()<.4:
        # Short repeat strokes/hatching attached to the final letter, seen in
        # the references, rather than independent random line segments.
        for i in range(rng.randint(1,3)):
            pen([last,(last[0]+15+i*8,last[1]-25),(last[0]+25+i*8,last[1]+3),last])
    cropped=canvas.crop(canvas.getbbox())
    ratio=min(size[0]*.88/cropped.width,size[1]*.80/cropped.height)
    cropped=cropped.resize((max(1,round(cropped.width*ratio)),max(1,round(cropped.height*ratio))),Image.Resampling.LANCZOS)
    layer=Image.new("RGBA",size);layer.alpha_composite(cropped,((size[0]-cropped.width)//2,(size[1]-cropped.height)//2))
    return layer,{"engine":"pen-paths-v1","layout":"stacked" if stacked else "inline",
        "capital_scale":round(cap,3),"body_ratio":round(body,3),"compression":round(compression,3),
        "slant":round(slant,3),"baseline_rise":round(angle,3),"overlap":round(overlap,3),
        "allograph_variant":alternate,"corner_style":"angular" if angular else "rounded",
        "capital_form":"looped" if ornamental else "standard",
        "terminal":ornament,"pen_lifts":lift_count+line,"stroke_count":len(strokes),
        "pressure_model":"continuous-speed-v2" if pressure else "uniform-v1","rhythm":round(rhythm,3),
        "has_flourish":ornament!="none","has_wave":family=="initial_bridge","lettering_only":ornament=="none"}
