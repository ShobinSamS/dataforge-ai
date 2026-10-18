"""Local glyph removal that preserves background outside detected source ink."""
import numpy as np
import cv2
from PIL import Image, ImageColor


def ink_mask(crop: np.ndarray) -> np.ndarray:
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    side=max(3,min(51,min(gray.shape)//2*2-1))
    # Closing estimates the background behind dark strokes; opening does the
    # same for light lettering. Neither introduces a solid-color rectangle.
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(side,side))
    border=np.concatenate([gray[0],gray[-1],gray[:,0],gray[:,-1]])
    op=cv2.MORPH_BLACKHAT if np.median(border)>=127 else cv2.MORPH_TOPHAT
    contrast=cv2.morphologyEx(gray,op,kernel)
    threshold,_=cv2.threshold(contrast,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    mask=(contrast>max(6,threshold*.65)).astype(np.uint8)*255
    return mask


def restore_region(image: Image.Image, box, *, glyphs_only: bool, mode: str="auto", color: str="#ffffff") -> None:
    x,y,w,h=box
    if mode=="solid":
        image.paste(ImageColor.getrgb(color),(x,y,x+w,y+h))
        return
    pad=max(12,min(48,h))
    x0,y0,x1,y1=max(0,x-pad),max(0,y-pad),min(image.width,x+w+pad),min(image.height,y+h+pad)
    pixels=np.array(image.crop((x0,y0,x1,y1)))
    xx,yy=x-x0,y-y0
    mask=np.zeros(pixels.shape[:2],dtype=np.uint8)
    if glyphs_only:
        mask[yy:yy+h,xx:xx+w]=ink_mask(pixels[yy:yy+h,xx:xx+w])
        mask=cv2.dilate(mask,np.ones((3,3),np.uint8))
        # Keep the operation inside the user's selected rectangle.
        bounds=np.zeros_like(mask);bounds[yy:yy+h,xx:xx+w]=255;mask &= bounds
    else:
        mask[yy:yy+h,xx:xx+w]=255
    if not np.any(mask): return
    if np.all(mask):
        image.paste(ImageColor.getrgb(color),(x,y,x+w,y+h))
        return
    known=pixels[mask==0]
    if len(known) and np.max(np.std(known,axis=0))<.6:
        restored=pixels.copy();restored[mask>0]=np.median(known,axis=0).astype(np.uint8)
    else:
        restored=cv2.inpaint(pixels,mask,3,cv2.INPAINT_TELEA)
    image.paste(Image.fromarray(restored),(x0,y0))
