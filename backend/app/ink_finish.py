"""Seeded pen/stamp imperfections on ink, with no paper background or extra marks."""
import copy
import math
import random
import cv2
import numpy as np
from PIL import Image


def _field(rng, size, grid):
    values=rng.uniform(-1,1,grid).astype(np.float32)
    return np.clip(cv2.resize(values,size,interpolation=cv2.INTER_CUBIC),-1,1)


def _notch(alpha, x, y, along, across, angle):
    radius=math.ceil(max(along,across)*2+2)
    x0,x1=max(0,x-radius),min(alpha.shape[1],x+radius+1)
    y0,y1=max(0,y-radius),min(alpha.shape[0],y+radius+1)
    yy,xx=np.mgrid[y0:y1,x0:x1];xx=xx-x;yy=yy-y
    u=xx*math.cos(angle)+yy*math.sin(angle)
    v=-xx*math.sin(angle)+yy*math.cos(angle)
    distance=(u/along)**2+(v/across)**2
    alpha[y0:y1,x0:x1]*=np.clip((distance-.35)/.8,0,1)


def apply_ink_finish(layer, rng, options, namespace):
    """Return an RGBA layer, exact binary ink mask and local geometry metadata.

    Fields use independent RNG state. Opacity is applied afterwards, so a change
    in opacity cannot reshuffle pressure, wear, lettering or shape.
    """
    mode=options.ink_finish
    clean={'mode':mode,'strength':0,'rotation_degrees':0,'displacement_max_px':0,
           'affine':[[1,0,0],[0,1,0]],'breaks':[],'engine':'ink-finish-v1'}
    if mode=='clean' or options.ink_irregularity==0:
        return layer,layer.getchannel('A').point(lambda p:255 if p else 0),clean
    independent=random.Random();independent.setstate(rng.getstate())
    independent.seed(f'finish:{namespace}:{independent.getrandbits(128)}')
    noise=np.random.default_rng(independent.getrandbits(64))
    strength=min(1,options.ink_irregularity*independent.uniform(.75,1.25)*(1.6 if mode=='worn' else 1))
    w,h=layer.size
    rgba=np.asarray(layer,dtype=np.float32)/255
    original=rgba[:,:,3]
    points=cv2.findNonZero((original>0).astype(np.uint8))
    if points is None:return layer,layer.getchannel('A'),clean
    x,y,bw,bh=cv2.boundingRect(points)
    margin=max(0,min(x,y,w-x-bw,h-y-bh)-1)
    # Bound all movement by the existing blank padding; no clipped characters.
    angle_limit=min(2.5*strength,math.degrees(math.atan2(margin*.28,max(w,h)/2)))
    angle=independent.uniform(-angle_limit,angle_limit)
    affine=cv2.getRotationMatrix2D((w/2,h/2),angle,1)
    shear=independent.uniform(-1,1)*min(.018*strength,margin*.12/max(1,h))
    affine[0,1]+=shear;affine[0,2]-=shear*h/2
    inverse=cv2.invertAffineTransform(affine)
    amplitude=min(margin*.24,(.2+h*.009 if namespace=='signature' else min(w,h)*.008))*strength
    dx=_field(noise,(w,h),(3,14 if namespace=='signature' else 6))*amplitude
    dy=_field(noise,(w,h),(2,18 if namespace=='signature' else 6))*amplitude
    # Small, irregular deviations instead of a repeating sine-wave wobble.
    if namespace=='signature':dy+=_field(noise,(w,h),(3,max(8,w//7)))*amplitude*.25
    gx,gy=np.meshgrid(np.arange(w,dtype=np.float32),np.arange(h,dtype=np.float32))
    sx=(inverse[0,0]*gx+inverse[0,1]*gy+inverse[0,2]+dx).astype(np.float32)
    sy=(inverse[1,0]*gx+inverse[1,1]*gy+inverse[1,2]+dy).astype(np.float32)
    # Premultiplied sampling avoids dark/color fringes on transparent edges.
    rgba[:,:,:3]*=original[:,:,None]
    warped=cv2.remap(rgba,sx,sy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
    alpha=warped[:,:,3].copy()
    colors=np.divide(warped[:,:,:3],alpha[:,:,None],out=np.zeros_like(warped[:,:,:3]),where=alpha[:,:,None]>0)
    before=float(alpha.sum())
    contact=_field(noise,(w,h),(3,independent.randint(12,22)) if namespace=='signature' else (5,6))
    if namespace=='signature':
        pressure=_field(noise,(w,h),(2,18))*strength*.55
        raised=cv2.dilate(alpha,np.ones((3,3),np.uint8))
        lowered=cv2.erode(alpha,np.ones((3,3),np.uint8))
        alpha=np.where(pressure>=0,alpha+(raised-alpha)*pressure,alpha+(alpha-lowered)*pressure)
        alpha[warped[:,:,3]==0]=0
        alpha*=1-strength*(.13+.45*(contact+1)/2)
    else:
        # Uneven pad contact and broad low-pressure patches, not uniform fade.
        alpha*=np.clip(1-strength*(.12+.55*(contact+1)/2),.12,1)
        for _ in range(independent.randint(2,5)):
            cx,cy=independent.uniform(0,w),independent.uniform(0,h)
            rx,ry=independent.uniform(.09,.25)*w,independent.uniform(.08,.25)*h
            patch=np.exp(-(((gx-cx)/rx)**2+((gy-cy)/ry)**2)*1.8)
            alpha*=np.clip(1-patch*strength*independent.uniform(.5,1.25),0,1)
        pores=cv2.resize(noise.random((max(2,h//2),max(2,w//2))).astype(np.float32),(w,h),interpolation=cv2.INTER_CUBIC)
        alpha*=np.where(pores>.94-strength*.15,max(0,1-strength*1.8),1)
    alpha*=np.clip(1+noise.normal(0,.08*strength,(h,w)),.65,1)
    candidates=alpha>max(.08,float(alpha.max())*.45)
    if namespace=='seal':
        perimeter=(np.maximum(abs(gx-w/2)/(w/2),abs(gy-h/2)/(h/2))>.7)
        edge=candidates & perimeter
        if np.any(edge):candidates=edge
    yy,xx=np.nonzero(candidates)
    breaks=[]
    distance=cv2.distanceTransform((alpha>.12).astype(np.uint8),cv2.DIST_L2,3)
    count=independent.randint(0,math.ceil(1+strength*(5 if namespace=='signature' else 13)))
    for _ in range(count):
        if not len(xx):break
        i=independent.randrange(len(xx));px,py=int(xx[i]),int(yy[i])
        if any((px-b['x'])**2+(py-b['y'])**2<36 for b in breaks):continue
        if namespace=='signature':
            # PCA estimates the local stroke direction; a dry gap crosses it.
            py0,px0=max(0,py-5),max(0,px-5)
            local=np.argwhere(alpha[py0:py+6,px0:px+6]>.1)
            if len(local)>2:
                _,vectors=np.linalg.eigh(np.cov(local[:,::-1].T))
                direction=math.atan2(vectors[1,-1],vectors[0,-1])
            else:direction=independent.uniform(-math.pi,math.pi)
            along=.35+strength*independent.uniform(.4,1.3)
            across=max(1,float(distance[py,px])*1.8)
        else:
            direction=independent.uniform(-math.pi,math.pi)
            along=.4+strength*independent.uniform(.7,3.5)
            across=.4+strength*independent.uniform(.6,2.5)
        _notch(alpha,px,py,along,across,direction)
        breaks.append({'x':px,'y':py,'length_px':round(along*2,3),'width_px':round(across*2,3)})
    # Strong wear may be requested, but it must not silently erase the asset.
    retained=float(alpha.sum())/max(before,1e-6)
    if 0<retained<.38:alpha=np.clip(alpha*(.38/retained),0,1)
    output=np.dstack((np.clip(colors,0,1),np.clip(alpha,0,1)))
    output=Image.fromarray(np.rint(output*255).astype(np.uint8),'RGBA')
    info={'mode':mode,'strength':round(strength,5),'rotation_degrees':round(angle,4),
          'displacement_max_px':round(float(max(abs(dx).max(),abs(dy).max())),4),
          'affine':affine.tolist(),'breaks':breaks,'retained_ink':round(float(alpha.sum())/max(before,1e-6),4),
          'engine':'ink-finish-v1'}
    return output,output.getchannel('A').point(lambda p:255 if p else 0),info


def transform_local_boxes(info, finish, size):
    """Conservative local boxes after affine movement and bounded paper warp."""
    if not finish['strength']:return info
    result=copy.deepcopy(info);matrix=np.array(finish['affine']);pad=finish['displacement_max_px']+1
    def walk(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key in {'bbox','label_bbox','value_bbox'} and isinstance(child,list) and len(child)==4:
                    x,y,w,h=child;corners=np.array([[x,y,1],[x+w,y,1],[x,y+h,1],[x+w,y+h,1]])@matrix.T
                    low=np.maximum(0,corners.min(axis=0)-pad);high=np.minimum(size,corners.max(axis=0)+pad)
                    value[key]=[float(low[0]),float(low[1]),float(max(0,high[0]-low[0])),float(max(0,high[1]-low[1]))]
                else:walk(child)
        elif isinstance(value,list):
            for child in value:walk(child)
    walk(result)
    return result
