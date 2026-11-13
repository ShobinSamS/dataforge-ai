"""Single-autograph guides and geometric isolation of generated ink."""
import hashlib
import random
import cv2
import numpy as np
from PIL import Image,ImageOps
from .schemas import RuleOptions
from .signatures import render_signature


class SignatureQualityError(ValueError):
    """A generated image can be retried with another image seed."""


def make_guide(folder,seed,text='',style='mixed'):
    rng=random.Random(f'signature-guide:{seed}')
    text=text or rng.choice(['Mira Dev','Arun Sen','Nila Rao','Rohan Das','Sara Mehra'])
    family=rng.choice(['enclosed','interwoven','surname','terminal_loop','initial_bridge','minimal']) if style=='mixed' else style
    options=RuleOptions(signature_style=family,signature_content='current',font_weight='normal',
                        ink_finish='clean',ink_opacity_mode='fixed',ink_opacity=1)
    ink,mask,_=render_signature((460,190),text,random.Random(seed),options)
    guide=Image.new('RGB',(512,512),'white');guide.paste(ink,(26,161),ink)
    bounds=mask.getbbox();roi=[bounds[0]+26,bounds[1]+161,bounds[2]+26,bounds[3]+161]
    guide.save(folder/'guide.png')
    return {'engine':'single-signature-img2img','guide_text':text,'guide_style':family,
            'guide_bbox':roi,'guide_sha256':hashlib.sha256((folder/'guide.png').read_bytes()).hexdigest(),
            'transcription_verified':False}


def isolate_signature(image,guide_bbox):
    """Select one spatial ink group, rejecting dense or clipped ambiguities.

    This is a geometry check, not recognition of handwriting semantics. No
    procedural substitute is returned if a diffusion result fails the gate.
    """
    w,h=image.size;x0,y0,x1,y1=guide_bbox
    roi=(max(8,x0-35),max(8,y0-35),min(w-8,x1+35),min(h-8,y1+35))
    # The guide window selects the autograph. It must not cut the selected
    # stroke: diffusion can extend a return or descender beyond that window.
    gray=np.asarray(image.convert('L'));dark=(gray<165).astype(np.uint8)
    count,labels,stats,_=cv2.connectedComponentsWithStats(dark)
    for label in range(1,count):
        if stats[label,cv2.CC_STAT_AREA]<5:dark[labels==label]=0
    groups=cv2.dilate(dark,cv2.getStructuringElement(cv2.MORPH_RECT,(25,9)))
    count,labels,stats,_=cv2.connectedComponentsWithStats(groups)
    candidates=[]
    for label in range(1,count):
        inside=(labels[roi[1]:roi[3],roi[0]:roi[2]]==label)&(dark[roi[1]:roi[3],roi[0]:roi[2]]>0)
        yy,xx=np.where(inside);amount=len(xx)
        if not amount:continue
        bw,bh=int(xx.max()-xx.min()+1),int(yy.max()-yy.min()+1)
        if amount<50 or bw<35 or bh<6:continue
        height=roi[3]-roi[1]
        score=amount*min(1,bw/150)/(1+abs((float(yy.mean()))-height/2)/height)
        candidates.append((score,label,amount))
    if not candidates:raise SignatureQualityError('No isolated signature found. Retry another seed or a simpler guide style.')
    _,label,_=max(candidates);support=(labels==label)&(dark>0);amount=int(support.sum())
    ys,xs=np.where(support);left,top,right,bottom=int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)
    if left<=8 or top<=8 or right>=w-8 or bottom>=h-8:
        raise SignatureQualityError('Generated ink touches the image boundary. No clipped signature was accepted.')
    if left<x0-105 or top<y0-105 or right>x1+105 or bottom>y1+105:
        raise SignatureQualityError('Generated ink extends too far beyond the signature guide. No ambiguous signature was accepted.')
    density=amount/max(1,(right-left)*(bottom-top))
    # A single-letter guide may legitimately be tall/narrow. Compare its
    # proportions instead of rejecting every non-horizontal autograph.
    expected_aspect=(x1-x0)/max(1,y1-y0)
    if density>.42 or right-left<min(65,(x1-x0)*.65) or (right-left)/max(1,bottom-top)<min(1.25,expected_aspect*.6):
        raise SignatureQualityError('Generated ink is too dense or ambiguous for one signature. Retry another seed or use procedural signatures.')
    gate=cv2.dilate(support.astype(np.uint8),np.ones((3,3),np.uint8))>0
    alpha=np.clip((255-gray.astype(float)-25)*255/190,0,255).astype(np.uint8);alpha[~gate]=0
    crop=Image.fromarray(alpha).crop((max(0,left-3),max(0,top-3),min(gray.shape[1],right+3),min(gray.shape[0],bottom+3)))
    crop=ImageOps.contain(crop,(460,220),Image.Resampling.LANCZOS)
    out=Image.new('RGBA',(512,512));ink=Image.new('RGBA',crop.size,'black');ink.putalpha(crop)
    out.alpha_composite(ink,((512-crop.width)//2,(512-crop.height)//2))
    return out,{'signature_ink_groups':1,'detected_groups':len(candidates),'discarded_groups':len(candidates)-1,
                'source_crop':[left,top,right-left,bottom-top],'ink_density':round(density,4),
                'guide_window_expanded':left<roi[0] or top<roi[1] or right>roi[2] or bottom>roi[3],
                'single_signature_check':'one isolated ink group; semantic review still required'}
