"""Fictional stamp content and transparent, seeded reference-inspired layouts."""
import math
import random
import re
from string import Formatter
import numpy as np
from PIL import Image,ImageDraw
from .fonts import load_font,resolve_font_weight
from .colors import choose_color,rgb,restore_ink_colors

SHAPES=("ring","round","double_ring","oval","badge","square","rectangle","professional","form","dated","text","attestation","corporate","form_block","nameplate")
FIELDS={"organization","department","name","title","city","state","year","date","reference","number"}
PALETTE={"red":(161,32,48),"blue":(27,61,145),"green":(25,110,68),"purple":(99,48,133),"black":(0,0,0),"brown":(139,76,41)}


def validate_seal_format(value):
    for _,key,spec,conversion in Formatter().parse(value):
        if key is not None and (key not in FIELDS or spec or conversion):
            raise ValueError("Seal format supports only simple {"+"}, {".join(sorted(FIELDS))+"} placeholders; no expressions or format specifiers")
    return value


def duplicate_words(lines):
    words=re.findall(r"\b[\w]+\b"," ".join(lines).casefold())
    seen=set();duplicates=set()
    for word in words:
        if word.isdecimal():continue  # Equal day/month digits are not repeated words.
        if word in seen:duplicates.add(word)
        seen.add(word)
    return sorted(duplicates)


def seal_text(content):return "\n".join(line for line in [content["top"],content.get("inner_top",""),*content["lines"],content.get("inner_bottom",""),content["bottom"]] if line)


def plan_seal_content(style,seed,region_id="seal",literal=None):
    rng=random.Random(f"seal-content:{seed}:{region_id}")
    context={
        "organization":f"{rng.choice(('NORTHSTAR','CEDAR','HORIZON','MAPLE','ORBIT','SUMMIT','AURORA','SILVERLEAF'))} {rng.choice(('LABORATORIES','LOGISTICS','STUDIOS','INDUSTRIES','VENTURES','WORKSHOPS','RESEARCH','ENTERPRISES'))}",
        "department":rng.choice(("RECORDS UNIT","QUALITY DESK","ADMIN SECTION","CONTROL ROOM","DISPATCH","FINANCE","OPERATIONS")),
        "name":f"{rng.choice(('ARUN','MIRA','NILA','DEV','SARA','ROHAN','TARA','ISHA'))} {rng.choice(('MEHRA','SEN','DAS','SHAH','KUMAR','VALE','RAO','VERMA'))}",
        "title":rng.choice(("PROJECT LEAD","SUPERVISOR","COORDINATOR","DIRECTOR","SENIOR OFFICER")),
        "city":rng.choice(("RIVERTON","LAKEHAVEN","BROOKDALE","PINECREST","MEADOWRIDGE","FAIRHAVEN","ASHFORD","STONEBRIDGE")),
        "state":rng.choice(("EASTLAND","WESTFIELD","NORTHVALE","SOUTHRIDGE")),
        "year":str(2015+rng.randrange(16)),"reference":f"{seed:08X}","number":str(seed),
    }
    context["date"]=f"{rng.randrange(1,29):02d}-{rng.randrange(1,13):02d}-{context['year']}"
    mode=style.seal_text_mode
    if literal is not None or style.literal_text is not None:
        mode="static";top=literal if literal is not None else style.literal_text
        content={"top":top,"bottom":style.seal_bottom_text,"lines":style.seal_subtext.splitlines()}
    elif mode=="static":content={"top":style.seal_text,"bottom":style.seal_bottom_text,"lines":style.seal_subtext.splitlines()}
    elif mode=="custom":
        content={"top":style.seal_top_format.format_map(context),"bottom":style.seal_bottom_format.format_map(context),"lines":style.seal_body_format.format_map(context).splitlines()}
    else:
        # Disjoint vocabularies avoid repeating the same heading as body text.
        candidates=[context['department'],context['name'],context['title'],f"REF {context['reference']}",context['date']]
        rng.shuffle(candidates)
        content={"top":context['organization'],"bottom":f"{context['city']} · {context['state']}","lines":candidates[:rng.randint(2,4)]}
        # Always include a seed-specific reference so independently generated
        # sample content varies even when two random organization names coincide.
        if not any(context['reference'] in line for line in content['lines']):content['lines'][-1]=f"REF {context['reference']}"
    content={"top":content['top'].strip(),"bottom":content['bottom'].strip(),"lines":[s.strip() for s in content['lines'] if s.strip()]}
    for key,value in (("inner_top",style.seal_inner_top_text),("inner_bottom",style.seal_inner_bottom_text)):
        content[key]=(value if mode=="static" else value.format_map(context)).strip()
        if '\n' in content[key] or '\r' in content[key]:raise ValueError("Inner seal arcs must be single lines")
    content['signer_name']=style.seal_signer_name.strip() or context['name']
    if any('\n' in content[key] or '\r' in content[key] for key in ('top','bottom')):raise ValueError("Seal top and bottom must be single lines; put multiline text in the body")
    if len(content['lines'])>6:raise ValueError("Seal body supports at most six lines")
    if not seal_text(content):raise ValueError("Seal needs at least one line of text")
    duplicates=duplicate_words([seal_text(content)])
    if duplicates and not style.seal_allow_repeated_words:raise ValueError("Repeated seal words: "+", ".join(duplicates)+". Enable repeated words if this is intentional.")
    content['mode']=mode
    return content


def _star(draw,cx,cy,radius,ink,points=5):
    vertices=[]
    for i in range(points*2):
        a=-math.pi/2+i*math.pi/points;r=radius if i%2==0 else radius*.42
        vertices.append((cx+math.cos(a)*r,cy+math.sin(a)*r))
    draw.polygon(vertices,fill=ink)


def render_seal(size,content,rng,style,emblem=None):
    w,h=size;scale=3 if w*h<400_000 else 1;W,H=w*scale,h*scale
    layer=Image.new('RGBA',(W,H));draw=ImageDraw.Draw(layer)
    shape=style.seal_style
    if emblem is not None:
        if shape not in {'random','ring','round','double_ring','oval','badge','corporate'}:
            raise ValueError('Center artwork requires a circular or oval seal shape')
        if shape=='random':shape='corporate'
    if shape=='random':
        choices=('rectangle','professional','form','dated','text','oval','form_block','nameplate') if w/h>1.5 else ('ring','round','double_ring','badge','square','oval','corporate','attestation')
        shape='corporate' if content.get('inner_top') or content.get('inner_bottom') else rng.choice(choices)
    border=style.seal_border
    if border=='random':border=rng.choice(('solid','double','dotted','dashed','serrated'))
    if shape=='badge' and style.seal_border=='random':border='serrated'
    color=rng.choice(list(PALETTE)) if style.seal_color in {'random','mixed'} else style.seal_color
    rng.randint(190,240)  # Retain the established layout/color RNG sequence.
    ink=(*PALETTE[color],255)
    other=rng.choice([key for key in PALETTE if key!=color]) if style.seal_color=='mixed' else color
    text_ink=(*PALETTE[other],255)
    if style.color_mode in {"manual","random","mixed"}:
        ink=(*rgb(choose_color(style,rng,"seal-border")),255)
        text_ink=(*rgb(choose_color(style,rng,"seal-text")),255) if style.color_mode=="mixed" else ink
        if style.color_mode=="mixed" and text_ink==ink and len(style.color_palette)>1:
            text_ink=(*rgb(next(value for value in style.color_palette if rgb(value)!=ink[:3])),255)
    bold=style.font_weight=='bold' or (style.font_weight=='auto' and rng.random()<.65)
    face=resolve_font_weight(style.font_id,'bold' if bold else 'normal')
    stroke=max(scale,round(min(W,H)*rng.uniform(.007,.014)))
    circular=shape in {'ring','round','double_ring','oval','badge','corporate'}
    pad=max(scale*3,min(W,H)*.055);cx,cy=W/2,H/2;rx,ry=W/2-pad,H/2-pad
    if shape not in {'oval','rectangle','professional','form','dated','text','attestation','form_block','nameplate'}:rx=ry=min(rx,ry)
    if shape=='oval' and w/h<1.4:ry*=.72
    rect=(cx-rx,cy-ry,cx+rx,cy+ry)
    if shape!='text':
        if circular:
            if border in {'dotted','dashed','serrated','rosettes'}:
                count=rng.choice((48,60,72))
                for i in range(count):
                    a=i*2*math.pi/count
                    if border=='rosettes':
                        x=cx+rx*math.cos(a);y=cy+ry*math.sin(a);r=stroke*1.2
                        draw.ellipse((x-r,y-r,x+r,y+r),outline=ink,width=max(scale,stroke//2))
                        draw.ellipse((x-scale/2,y-scale/2,x+scale/2,y+scale/2),fill=ink)
                    elif border=='dotted':
                        x=cx+rx*math.cos(a);y=cy+ry*math.sin(a);r=stroke*.65
                        draw.ellipse((x-r,y-r,x+r,y+r),fill=ink)
                    elif border=='dashed':
                        draw.line((cx+rx*.97*math.cos(a),cy+ry*.97*math.sin(a),cx+rx*1.02*math.cos(a),cy+ry*1.02*math.sin(a)),fill=ink,width=stroke)
                    else:
                        da=math.pi/count*.6
                        draw.polygon(((cx+rx*.97*math.cos(a-da),cy+ry*.97*math.sin(a-da)),(cx+rx*1.045*math.cos(a),cy+ry*1.045*math.sin(a)),(cx+rx*.97*math.cos(a+da),cy+ry*.97*math.sin(a+da))),fill=ink)
            else:draw.ellipse(rect,outline=ink,width=stroke)
            if border=='double' or shape in {'ring','double_ring','badge','corporate'}:
                gap=min(rx,ry)*.07;draw.ellipse((rect[0]+gap,rect[1]+gap,rect[2]-gap,rect[3]-gap),outline=ink,width=max(scale,stroke//2))
            if shape in {'ring','double_ring','badge','corporate'}:
                inner_border=.70 if shape=='double_ring' else .65
                draw.ellipse((cx-rx*inner_border,cy-ry*inner_border,cx+rx*inner_border,cy+ry*inner_border),outline=ink,width=max(scale,stroke//2))
            if shape=='double_ring':draw.ellipse((cx-rx*.66,cy-ry*.66,cx+rx*.66,cy+ry*.66),outline=ink,width=max(scale,stroke//2))
        else:
            if border in {'dotted','dashed','serrated','rosettes'}:
                step=max(scale*4,stroke*4)
                for xx in np.arange(rect[0],rect[2],step):
                    for yy in (rect[1],rect[3]):
                        if border in {'dotted','rosettes'}:draw.ellipse((xx-stroke*.5,yy-stroke*.5,xx+stroke*.5,yy+stroke*.5),fill=ink)
                        elif border=='serrated':
                            direction=-1 if yy==rect[1] else 1
                            draw.polygon(((xx,yy),(min(xx+step*.5,rect[2]),yy+direction*stroke*2),(min(xx+step,rect[2]),yy)),fill=ink)
                        else:draw.line((xx,yy,min(xx+step*.5,rect[2]),yy),fill=ink,width=stroke)
                for yy in np.arange(rect[1],rect[3],step):
                    for xx in (rect[0],rect[2]):
                        if border in {'dotted','rosettes'}:draw.ellipse((xx-stroke*.5,yy-stroke*.5,xx+stroke*.5,yy+stroke*.5),fill=ink)
                        elif border=='serrated':
                            direction=-1 if xx==rect[0] else 1
                            draw.polygon(((xx,yy),(xx+direction*stroke*2,min(yy+step*.5,rect[3])),(xx,min(yy+step,rect[3]))),fill=ink)
                        else:draw.line((xx,yy,xx,min(yy+step*.5,rect[3])),fill=ink,width=stroke)
            else:draw.rectangle(rect,outline=ink,width=stroke)
            if border=='double' or shape=='form':
                gap=min(rx,ry)*.07;draw.rectangle((rect[0]+gap,rect[1]+gap,rect[2]-gap,rect[3]-gap),outline=ink,width=max(scale,stroke//2))

    def fitted(text,max_width,max_height):
        for px in range(max(6*scale,round(max_height*1.5)),6*scale-1,-1):
            f=load_font(px,face);b=f.getbbox(text)
            if b[2]-b[0]<=max_width and b[3]-b[1]<=max_height:return f,b
        raise ValueError('Seal text cannot fit at a readable size; enlarge the region or shorten its text')

    def line(text,x,y,max_width,max_height):
        if not text:return
        f,b=fitted(text,max_width,max_height)
        draw.text((x-(b[2]+b[0])/2,y-(b[3]+b[1])/2),text,font=f,fill=text_ink)

    def arc(text,lower=False,radius=.80,font_ratio=.095):
        if not text:return
        ax,ay=rx*radius,ry*radius;span=math.radians(148)
        positions=np.linspace(-span/2,span/2,401)
        angles=math.pi/2-positions if lower else -math.pi/2+positions
        xx=ax*np.cos(angles);yy=ay*np.sin(angles)
        lengths=np.concatenate(([0],np.cumsum(np.hypot(np.diff(xx),np.diff(yy)))))
        # Fit the whole string using measured advances; never truncate content.
        for px in range(max(6*scale,round(min(W,H)*font_ratio)),6*scale-1,-1):
            f=load_font(px,face);advances=[max(f.getlength(c),px*.12) for c in text]
            if sum(advances)<=lengths[-1]*.98:break
        else:raise ValueError('Seal arc text is too long for this region; enlarge it or shorten the arc')
        total=sum(advances);cursor=(lengths[-1]-total)/2
        for char,advance in zip(text,advances):
            theta=float(np.interp(cursor+advance/2,lengths,positions));cursor+=advance
            angle=math.pi/2-theta if lower else -math.pi/2+theta
            b=f.getbbox(char);tile=Image.new('RGBA',(px*3,px*3))
            ImageDraw.Draw(tile).text((tile.width/2-(b[0]+b[2])/2,tile.height/2-(b[1]+b[3])/2),char,font=f,fill=text_ink)
            tangent=math.atan2(-ay*math.cos(angle),ax*math.sin(angle)) if lower else math.atan2(ay*math.cos(angle),-ax*math.sin(angle))
            tile=tile.rotate(-math.degrees(tangent),resample=Image.Resampling.BICUBIC,expand=True)
            layer.alpha_composite(tile,(round(cx+ax*math.cos(angle)-tile.width/2),round(cy+ay*math.sin(angle)-tile.height/2)))

    lines=list(content['lines']);symbol=style.seal_symbol
    if symbol=='random':symbol=rng.choice(('none','star','diamond','rosette','monogram'))
    layout_info={}
    if shape in {'attestation','form_block','nameplate'}:
        from .seal_layouts import block_layout
        layout_info=block_layout(layer,rect,content,style,ink,text_ink,face,stroke,scale,rng)
    elif circular:
        arc(content['top']);arc(content['bottom'],True)
        inner_arcs=bool(content.get('inner_top') or content.get('inner_bottom'))
        if inner_arcs:
            arc(content.get('inner_top',''),radius=.53,font_ratio=.065)
            arc(content.get('inner_bottom',''),True,radius=.53,font_ratio=.065)
        for xx in (cx-rx*.79,cx+rx*.79):
            if symbol in {'star','rosette'}:_star(draw,xx,cy,min(rx,ry)*.055,ink,5 if symbol=='star' else 8)
            elif symbol=='diamond':draw.polygon(((xx,cy-ry*.05),(xx+rx*.035,cy),(xx,cy+ry*.05),(xx-rx*.035,cy)),fill=ink)
        if symbol=='monogram':
            monogram=''.join(word[0] for word in content['top'].split()[:2])
            repeated=duplicate_words([seal_text({**content,'lines':lines}),monogram])
            if style.seal_symbol=='random' and len(lines)>=4 and ry/scale<50:
                symbol='none'  # Reserve room for readable body text on small ovals.
            elif repeated and not style.seal_allow_repeated_words:
                if style.seal_symbol=='random':symbol='none'
                else:raise ValueError('Monogram repeats seal words; change the ornament or enable repeated words')
            elif monogram:lines.insert(0,monogram)
        count=len(lines);step=ry*(.52 if inner_arcs else .68)/max(1,count)
        motif=style.seal_center_motif if shape=='corporate' else 'none'
        if emblem is not None:motif='artwork'
        if motif!='none':
            step=ry*.23/max(1,count)
            mx,my=cx,cy-ry*.16;r=min(rx,ry)*.18
            if motif=='artwork':
                from PIL import ImageOps,ImageChops
                tile=ImageOps.contain(emblem.convert('RGBA'),(max(1,round(r*2.5)),max(1,round(r*2))))
                alpha=ImageChops.multiply(ImageOps.invert(ImageOps.grayscale(tile)),tile.getchannel('A'))
                colored=Image.new('RGBA',tile.size,ink);colored.putalpha(alpha)
                layer.alpha_composite(colored,(round(mx-tile.width/2),round(my-tile.height/2)))
            elif motif=='shield':
                draw.line([(mx-r,my-r),(mx+r,my-r),(mx+r*.9,my+r*.3),(mx,my+r),(mx-r*.9,my+r*.3),(mx-r,my-r)],fill=ink,width=max(scale,stroke//2))
                for dx,dy in ((0,-.45),(-.35,.1),(.35,.1)):_star(draw,mx+r*dx,my+r*dy,r*.18,ink)
            elif motif=='rosette':_star(draw,mx,my,r,ink,12)
            else:
                for a in np.linspace(0,2*math.pi,32,endpoint=False):
                    draw.line((mx+r*.45*math.cos(a),my+r*.45*math.sin(a),mx+r*math.cos(a),my+r*math.sin(a)),fill=ink,width=max(scale,stroke//2))
                draw.ellipse((mx-r*.3,my-r*.3,mx+r*.3,my+r*.3),outline=ink,width=max(scale,stroke//2))
            layout_info['center_motif']=motif
        for i,text in enumerate(lines):
            yy=cy+(i-(count-1)/2)*step+(ry*.27 if motif!='none' else 0)
            inner=.43 if inner_arcs else .63 if shape=='double_ring' else .62 if shape in {'ring','badge','corporate'} else .68
            # The entire text rectangle must fit the inner ellipse, including
            # its upper/lower corners; measuring at its center clips the edges.
            fraction=(abs(yy-cy)+step*.36+stroke*1.5)/(ry*inner)
            available=rx*2*inner*.95*math.sqrt(max(.05,1-fraction*fraction))
            line(text,cx,yy,available,step*.72)
    else:
        all_lines=[s for s in [content['top'],content.get('inner_top',''),*lines,content.get('inner_bottom',''),content['bottom']] if s]
        usable_height=ry*1.7;step=usable_height/max(1,len(all_lines))
        for i,text in enumerate(all_lines):
            yy=cy+(i-(len(all_lines)-1)/2)*step
            line(text,cx,yy,rx*1.78,step*(.76 if i else .82))
            if shape in {'form','dated'} and i==0:draw.line((cx-rx*.86,yy+step*.5,cx+rx*.86,yy+step*.5),fill=ink,width=max(scale,stroke//2))
            if shape=='form' and 0<i<len(all_lines)-1:
                for xx in np.arange(cx-rx*.82,cx+rx*.82,max(scale*3,stroke*3)):
                    draw.ellipse((xx,yy+step*.42,xx+scale,yy+step*.42+scale),fill=ink)
            if shape=='professional' and i==len(all_lines)-2:
                draw.line((cx-rx*.8,yy+step*.5,cx+rx*.8,yy+step*.5),fill=ink,width=max(scale,stroke//2))
    # Ink-only wear: speckle, softened edges and uneven contact, never a paper box.
    pixels=np.array(layer)
    if style.seal_wear:
        noise=np.random.default_rng(rng.randrange(2**31))
        pixels[noise.random((H,W))<style.seal_wear,3]=0
        pixels[:,:,3]=(pixels[:,:,3].astype(float)*noise.uniform(.72,1,(H,1))).astype(np.uint8)
        layer=Image.fromarray(pixels)
    if scale>1:layer=layer.resize(size,Image.Resampling.LANCZOS)
    info={'shape':shape,'border':border,'symbol':symbol,'ink':color,'text_ink':other,'content_mode':content.get('mode','static'),
          'top':content['top'],'bottom':content['bottom'],'inner_top':content.get('inner_top',''),'inner_bottom':content.get('inner_bottom',''),
          'lines':lines,'text':seal_text({**content,'lines':lines}),'engine':'seal-v2',
          'ink_color':'#%02x%02x%02x'%ink[:3],'text_ink_color':'#%02x%02x%02x'%text_ink[:3],**layout_info}
    if 'embedded_signature' in layout_info:info['text']+='\n'+layout_info['embedded_signature']['text']
    from .ink import apply_ink_opacity
    from .ink_finish import apply_ink_finish,transform_local_boxes
    layer,mask,finish=apply_ink_finish(layer,rng,style,"seal")
    if style.color_mode in {"manual","random","mixed"}:
        layer=restore_ink_colors(layer,[ink,text_ink])
    info=transform_local_boxes(info,finish,size)
    info['ink_finish']=finish
    layer,mask,opacity_info=apply_ink_opacity(layer,rng,style,"seal")
    info.update(opacity_info)
    return layer,mask,info
