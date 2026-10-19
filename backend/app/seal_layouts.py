"""Hierarchical stamp lettering and ruled form rows on transparent layers."""
import random
from PIL import ImageDraw
from .fonts import load_font, resolve_font_weight, cursive_font_id


def block_layout(layer, rect, content, style, ink, text_ink, face, stroke, scale, rng):
    draw = ImageDraw.Draw(layer)
    left, top, right, bottom = rect
    width, height = right-left, bottom-top
    left += width*.045; right -= width*.045
    top += height*.04; bottom -= height*.04
    rows = []
    if content['top']:rows.append(('heading', content['top'], 1.25))
    if content.get('inner_top'):rows.append(('registration',content['inner_top'],.7))
    if style.seal_style == 'attestation' and style.seal_embedded_signature:
        rows.append(('signature', content.get('signer_name') or style.seal_signer_name or 'Alex Example', 1.25))
    for i, text in enumerate(content['lines']):
        registration = text.upper().startswith(('REG ', 'REG.', 'REGISTRATION'))
        role = ('registration' if registration else 'field' if ':' in text and style.seal_style!='nameplate'
                else 'name' if style.seal_style == 'attestation' and i == 0
                else 'status' if style.seal_style=='form_block' and text.isupper() and len(text)<25 else 'body')
        rows.append((role, text, .7 if registration else 1 if role in {'name','field'} else .85))
    if content.get('inner_bottom'):rows.append(('footer',content['inner_bottom'],.7))
    if content['bottom']:
        rows.append(('field' if ':' in content['bottom'] and style.seal_style!='nameplate' else 'footer', content['bottom'], .9))
    total = sum(weight for _,_,weight in rows)
    cursor = top
    report = {'layout':style.seal_style, 'fields':[], 'text_boxes':[]}

    def text_at(text, bounds, font_id, align='center', maximum=None, role='body'):
        if not text:return None
        x0,y0,x1,y1 = bounds
        ceiling = min(round((y1-y0)*1.5), maximum) if maximum else round((y1-y0)*1.5)
        for px in range(max(6*scale,ceiling),6*scale-1,-1):
            font=load_font(px,font_id);b=font.getbbox(text)
            if b[2]-b[0]<=x1-x0 and b[3]-b[1]<=y1-y0:break
        else:raise ValueError('Seal row cannot fit at a readable size; enlarge the region or shorten its text')
        x=x0-b[0] if align=='left' else (x0+x1-b[0]-b[2])/2
        y=(y0+y1-b[1]-b[3])/2
        draw.text((x,y),text,font=font,fill=text_ink)
        box=[(x+b[0])/scale,(y+b[1])/scale,(b[2]-b[0])/scale,(b[3]-b[1])/scale]
        report['text_boxes'].append({'role':role,'text':text,'bbox':box,'font_size':px/scale,'font_id':font_id})
        return box

    for role,text,weight in rows:
        step=(bottom-top)*weight/total
        y0,y1=cursor+step*.13,cursor+step*.87
        if role=='signature':
            # A procedural name-based mark; the supplied signature is never traced.
            from .signatures import render_signature
            independent=random.Random();independent.setstate(rng.getstate())
            options=style.model_copy(update={'signature_style':'interwoven','text_color':'#%02x%02x%02x'%text_ink[:3],
                                            'font_weight':'bold','ink_opacity_mode':'fixed','ink_opacity':1})
            size=(max(1,round(right-left)),max(1,round(step)))
            signature,_,details=render_signature(size,text,independent,options)
            layer.alpha_composite(signature,(round(left),round(cursor)))
            report['embedded_signature']={**details,'bbox':[left/scale,cursor/scale,size[0]/scale,size[1]/scale]}
        elif role=='field':
            label,value=(part.strip() for part in text.split(':',1))
            label_width=min((right-left)*.4,max((right-left)*.15,len(label)*(y1-y0)*.5))
            label_box=text_at(label+':',(left,y0,left+label_width,y1),resolve_font_weight(face,'normal'),'left',maximum=round(step*.55),role='field_label')
            start=left+label_width+(right-left)*.015
            # Dots continue underneath an optional handwritten value, just as
            # an unfilled stamp form remains visible after someone writes on it.
            baseline=cursor+step*.82
            for x in range(round(start),round(right),max(scale*3,stroke*2)):
                draw.ellipse((x,baseline,x+scale,baseline+scale),fill=ink)
            value_face=cursive_font_id() if style.seal_field_writing=='cursive' else resolve_font_weight(face,'normal')
            value_box=text_at(value,(start,y0,right,y1),value_face,'left',maximum=round(step*.8),role='field_value')
            report['fields'].append({'label':label,'value':value,'writing':style.seal_field_writing,
                                     'bbox':[left/scale,cursor/scale,(right-left)/scale,step/scale],
                                     'label_bbox':label_box,'value_bbox':value_box})
        else:
            weight='bold' if role in {'heading','name','status'} or style.font_weight=='bold' else 'normal'
            maximum=round(step*(1.1 if role=='heading' else 1))
            text_at(text,(left,y0,right,y1),resolve_font_weight(face,weight),maximum=maximum,role=role)
            if style.seal_style=='form_block' and role=='registration':
                draw.line((left,cursor+step*.98,right,cursor+step*.98),fill=ink,width=max(scale,stroke//2))
        cursor+=step
    return report
