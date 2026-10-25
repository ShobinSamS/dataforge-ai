"""Seeded capture effects; the same homography is applied to every label mask."""
import io
import random
import cv2
import numpy as np
from PIL import Image,ImageEnhance,ImageFilter


def capture_plan(size,profile,seed,strength=.5):
    rng=random.Random(f'capture:{seed}');w,h=size
    if profile=='mixed':profile=rng.choice(['phone','scanner','photocopy','cropped_scan'])
    matrix=np.eye(3,dtype=np.float64)
    if profile=='phone':
        inset=min(w,h)*(.015+.07*strength)
        src=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
        dst=np.float32([[rng.uniform(0,inset),rng.uniform(0,inset)],
                        [w-1-rng.uniform(0,inset),rng.uniform(0,inset)],
                        [w-1-rng.uniform(0,inset),h-1-rng.uniform(0,inset)],
                        [rng.uniform(0,inset),h-1-rng.uniform(0,inset)]])
        matrix=cv2.getPerspectiveTransform(src,dst)
    elif profile=='cropped_scan':
        # Crop only narrow page margins, then rescale to canonical dimensions.
        cx=w*(.005+.02*strength);cy=h*(.005+.02*strength)
        matrix=cv2.getPerspectiveTransform(np.float32([[cx,cy],[w-1-cx,cy],[w-1-cx,h-1-cy],[cx,h-1-cy]]),
                                          np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]]))
    return {'profile':profile,'strength':strength,'seed':seed,'homography':matrix.tolist(),
            'mask_semantics':'ideal ink support before optical effects'}


def warp_mask(mask,plan):
    if plan['profile'] not in {'phone','cropped_scan'}:return mask.copy()
    return Image.fromarray(cv2.warpPerspective(np.asarray(mask),np.array(plan['homography']),mask.size,
                                              flags=cv2.INTER_NEAREST,borderValue=0))


def capture_image(image,plan):
    profile=plan['profile'];s=plan['strength']
    if profile=='none':return image
    original_mode=image.mode
    # A scanner/camera captures paper. Transparent canvases must opt in to this.
    paper=Image.new('RGB',image.size,'white')
    if image.mode=='RGBA':paper.paste(image,mask=image.getchannel('A'))
    else:paper=image.convert('RGB')
    pixels=np.asarray(paper).astype(np.float32);h,w=pixels.shape[:2]
    rng=np.random.default_rng(plan['seed']);yy,xx=np.mgrid[:h,:w]
    if profile in {'phone','cropped_scan'}:
        pixels=cv2.warpPerspective(pixels,np.array(plan['homography']),(w,h),flags=cv2.INTER_CUBIC,borderValue=(185,180,171))
    if profile=='phone':
        light=1-s*(.08+.28*xx/max(1,w)+.1*yy/max(1,h))
        fold=np.exp(-((xx/w-(.35+(plan['seed']%20)/100))/.014)**2)*s*.14
        pixels*=np.clip(light-fold,.4,1.1)[:,:,None]
    elif profile=='scanner':
        pixels=(pixels-128)*(1+.12*s)+128
        pixels*=1-.055*s*np.cos(xx/max(1,w)*np.pi*5)[:,:,None]
    elif profile=='photocopy':
        gray=cv2.cvtColor(pixels,cv2.COLOR_RGB2GRAY)
        gray=np.clip((gray-145)*(1.3+s)+176,0,255)
        gray+=rng.normal(0,1.5+3*s,(h,w))
        pixels=np.repeat(gray[:,:,None],3,axis=2)
    pixels+=rng.normal(0,1+2*s,pixels.shape)
    result=Image.fromarray(np.clip(pixels,0,255).astype(np.uint8))
    result=result.filter(ImageFilter.GaussianBlur(.15+.45*s))
    encoded=io.BytesIO();result.save(encoded,format='JPEG',quality=round(94-30*s))
    encoded.seek(0)
    with Image.open(encoded) as decoded:result=decoded.convert('RGB')
    return result.convert('RGBA') if original_mode=='RGBA' else result
