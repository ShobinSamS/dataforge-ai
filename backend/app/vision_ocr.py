"""Optional, offline English line recognition and conservative ruled-table geometry."""
import gc
import importlib.util
from pathlib import Path
import cv2
import numpy as np
import psutil
from PIL import Image
from .resources import CPU_LOCK
from .config import settings

MAX_CROPS=80


def model_path(mode: str) -> Path:
    return settings.data_dir/"models"/f"trocr-small-{mode}"


def capabilities() -> dict:
    runtime=all(importlib.util.find_spec(name) is not None for name in ("torch","transformers","sentencepiece"))
    return {"runtime":runtime,"models":{mode:runtime and (model_path(mode)/"config.json").is_file() and
        any((model_path(mode)/weight).is_file() for weight in ("model.safetensors","pytorch_model.bin")) for mode in ("printed","handwritten")},
        "language":"English","page_detector":"OpenCV line proposals; inspect missed/merged lines",
        "tables":"Ruled rectangular grids; merged/borderless tables require manual review",
        "runtime_downloads":False,"max_crops":MAX_CROPS}


def binary_ink(image: Image.Image):
    gray=cv2.cvtColor(np.asarray(image.convert("RGB")),cv2.COLOR_RGB2GRAY)
    return cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]


def grid_masks(image):
    ink=binary_ink(image);h,w=ink.shape
    horizontal=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(24,w//25)),np.uint8))
    vertical=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(24,h//25),1),np.uint8))
    return ink,horizontal,vertical


def detect_lines(image: Image.Image) -> list[tuple]:
    gray=cv2.cvtColor(np.asarray(image.convert("RGB")),cv2.COLOR_RGB2GRAY)
    # Global Otsu can turn a colored/gradient document background into "ink".
    # Use local stroke contrast, then discard large graphics before joining text.
    side=max(15,min(51,min(image.size)//2*2-1))
    contrast=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(side,side)))
    ink=((gray<150)&(contrast>30)).astype(np.uint8)*255
    # Connect characters into line proposals without inventing coordinates with an LLM.
    n,labels,stats,_=cv2.connectedComponentsWithStats(ink)
    keep=[i for i,s in enumerate(stats) if i and s[4]>=8 and 4<=s[3]<=max(80,image.height*.12) and s[2]<image.width*.6]
    ink=np.isin(labels,keep).astype(np.uint8)*255
    heights=[stats[i][3] for i in keep if stats[i][4]>=40 and stats[i][3]>=8 and stats[i][2]<stats[i][3]*4]
    height=int(np.median(heights)) if heights else 12
    connected=cv2.dilate(ink,np.ones((max(2,height//5),max(10,height)),np.uint8))
    contours,_=cv2.findContours(connected,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    boxes=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if w<max(10,h*1.15) or h<max(8,height*.5) or h>image.height*.25 or w*h<60: continue
        x0,y0=max(0,x-3),max(0,y-3)
        boxes.append((x0,y0,min(image.width,x+w+3)-x0,min(image.height,y+h+3)-y0))
    return sorted(boxes,key=lambda box:(box[1],box[0]))


def recognize(image: Image.Image, boxes: list, mode: str) -> list[dict]:
    if len(boxes)>MAX_CROPS: raise ValueError(f"OCR supports at most {MAX_CROPS} crops per request; select fewer lines/cells")
    if not capabilities()["models"].get(mode):
        raise ValueError(f"Local TrOCR {mode} model is not installed. Run scripts/setup_vision_models.py explicitly.")
    if psutil.virtual_memory().available/1024**2<max(1800,settings.min_available_mb):
        raise ValueError("Free at least 1.8 GB memory before transformer OCR")
    if not CPU_LOCK.acquire(blocking=False): raise ValueError("CPU worker is busy; retry OCR after the current workload")
    model=processor=None
    try:
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        torch.set_num_threads(4)
        processor=TrOCRProcessor.from_pretrained(str(model_path(mode)),local_files_only=True,use_fast=False)
        model=VisionEncoderDecoderModel.from_pretrained(str(model_path(mode)),local_files_only=True).eval()
        results=[]
        with torch.inference_mode():
            for x,y,w,h in boxes:
                crop=image.crop((x,y,x+w,y+h)).convert("RGB")
                # Blank cells must stay blank; language models can hallucinate on empty crops.
                if np.count_nonzero(binary_ink(crop))<8 or np.std(np.asarray(crop))<2:
                    results.append({"text":"","confidence":0.0});continue
                pixels=processor(images=crop,return_tensors="pt").pixel_values
                output=model.generate(pixels,max_new_tokens=128,num_beams=1,return_dict_in_generate=True,output_scores=True)
                text=processor.batch_decode(output.sequences,skip_special_tokens=True)[0].strip()
                scores=model.compute_transition_scores(output.sequences,output.scores,normalize_logits=True)
                score=float(torch.exp(scores.mean()).item()) if scores.numel() else 0.0
                results.append({"text":text[:1000],"confidence":round(min(1,max(0,score)),4)})
        return results
    finally:
        del model,processor
        gc.collect()
        CPU_LOCK.release()


def ruled_cells(image: Image.Image) -> list[dict]:
    _,horizontal,vertical=grid_masks(image)
    grid=cv2.bitwise_or(horizontal,vertical)
    contours,hierarchy=cv2.findContours(grid,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    boxes=[]
    if hierarchy is None: return []
    for index,contour in enumerate(contours):
        x,y,w,h=cv2.boundingRect(contour)
        # First-level holes are cells. Pen strokes can create child islands inside
        # a cell: requiring a leaf contour would incorrectly discard that cell.
        parent=hierarchy[0][index][3]
        if parent<0 or hierarchy[0][parent][3]>=0 or w<20 or h<14: continue
        if cv2.contourArea(contour)<w*h*.8: continue
        boxes.append((x+2,y+2,w-4,h-4))
    boxes.sort(key=lambda b:(b[1],b[0]))
    # Separate disconnected tables, then cluster row/column origins within each grid.
    count,labels,_,_=cv2.connectedComponentsWithStats(grid)
    groups={}
    for box in boxes:
        x,y,w,h=box
        neighborhood=labels[max(0,y-4):y+2,max(0,x-4):x+w+4]
        ids=neighborhood[neighborhood>0]
        if not ids.size: continue
        group=int(np.bincount(ids).argmax());groups.setdefault(group,[]).append(box)
    cells=[]
    for table,group in enumerate(groups.values()):
        rows=[];cols=[]
        for axis,dest in ((1,rows),(0,cols)):
            for value in sorted(b[axis] for b in group):
                if not dest or value-dest[-1]>8: dest.append(value)
        for box in group:
            cells.append({"id":f"cell_{len(cells)}","table":table,"row":min(range(len(rows)),key=lambda i:abs(rows[i]-box[1])),
                "column":min(range(len(cols)),key=lambda i:abs(cols[i]-box[0])),"box":list(box),"text":"","confidence":0.0})
    return cells
