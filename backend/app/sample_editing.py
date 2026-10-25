"""Revisioned annotation correction and single-sample regeneration."""
import json
import hashlib
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import Field
from PIL import Image,ImageDraw
from sqlalchemy import select
from .schemas import Contract,CLASS_NAMES,GenerationConfig
from .db import Sample,Job
from .jobs import snapshot_regions,optional_regions
from .render import render_sample
from .validation import validate,yolo_line
from .resources import CPU_LOCK


class EditedAnnotation(Contract):
    region_id: str = Field(min_length=1,max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')
    kind: str = Field(min_length=1,max_length=40,pattern=r'^[a-z_]+$')
    text: str = Field(default='',max_length=4000)
    bbox: tuple[int,int,int,int]


class SampleEdit(Contract):
    revision: int = Field(default=0,ge=0)
    annotations: list[EditedAnnotation] = Field(max_length=200)
    rejected: bool = False
    note: str = Field(default='',max_length=500)


def edit_record(folder,body,classes):
    path=folder/'metadata.json';record=json.loads(path.read_text(encoding='utf-8'))
    revision=record.get('revision',0)
    if body.revision!=revision:raise HTTPException(409,'Annotations changed; reload this sample before saving')
    with Image.open(folder/'image.png') as image:w,h=image.size
    ids=[a.region_id for a in body.annotations]
    if len(set(ids))!=len(ids):raise ValueError('Annotation IDs must be unique')
    for a in body.annotations:
        x,y,bw,bh=a.bbox
        if a.kind not in classes:raise ValueError('Unsupported annotation class')
        if x<0 or y<0 or bw<1 or bh<1 or x+bw>w or y+bh>h:raise ValueError('Annotation box exceeds image bounds')
    backup=folder/'revisions';backup.mkdir(exist_ok=True)
    backup_path=backup/f'{revision:04d}.json'
    if not backup_path.exists():backup_path.write_text(json.dumps(record,indent=2),encoding='utf-8')
    old={a['region_id']:a for a in record['annotations']};annotations=[]
    for a in body.annotations:
        previous=old.get(a.region_id,{});same_box=list(a.bbox)==previous.get('bbox')
        item={**previous,'region_id':a.region_id,'class':a.kind,'text':a.text,'bbox':list(a.bbox),'reviewed':True}
        if classes==CLASS_NAMES:item['class_id']=classes.index(a.kind)
        if not same_box:
            mask=Image.new('L',(w,h));x,y,bw,bh=a.bbox
            ImageDraw.Draw(mask).rectangle((x,y,x+bw-1,y+bh-1),fill=255)
            item.update(mask=f'manual_{revision+1}_{a.region_id}.png',provenance='human-box',mask_semantics='rectangular reviewed box, not pixel segmentation')
            mask.save(folder/item['mask'])
        annotations.append(item)
    report=record.get('validation',{'passed':True,'errors':[],'warnings':[]})
    errors=[e for e in report.get('errors',[]) if e!='human_rejected']
    # Geometry is checked above; semantic corrections do not silently erase
    # unrelated capture/decoder errors from the original validation.
    geometry=('mask_alignment:','invalid_annotation:','mask_dimensions:','missing_fields','empty_mask:','edge_clipping:','visibility:')
    errors=[e for e in errors if not e.startswith(geometry)]
    if body.rejected:errors.append('human_rejected')
    report={**report,'passed':not errors,'errors':errors,'training_ready':False}
    current={a['region_id']:a for a in annotations}
    if 'table_cells' in record:
        record['table_cells']=[{**cell,'value':current[cell['region_id']]['text']} for cell in record['table_cells'] if cell['region_id'] in current]
    if 'relationships' in record:
        record['relationships']=[link for link in record['relationships'] if set(link.get('sources',[link.get('source')]))|{link.get('target')} <= set(current)]
    record.update(annotations=annotations,revision=revision+1,rejected=body.rejected,review_note=body.note,validation=report)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(record,indent=2),encoding='utf-8');temp.replace(path)
    return record


def editing_router(sessions,root,queue_lock):
    router=APIRouter(prefix='/api/samples',tags=['Sample correction'])
    def sample(db,id_):
        s=db.get(Sample,id_)
        if s is None:raise HTTPException(404,'Sample not found')
        j=db.get(Job,s.job_id)
        if j.status not in {'completed','review_required'}:raise HTTPException(409,'Wait for the dataset to finish before editing')
        return s,j
    @router.get('/{id_}/annotations')
    def get(id_:str):
        with sessions() as db:
            s,_=sample(db,id_);record=json.loads((Path(s.path).parent/'metadata.json').read_text(encoding='utf-8'))
            with Image.open(s.path) as image:record.update(width=image.width,height=image.height)
            return record
    @router.put('/{id_}/annotations')
    def update(id_:str,body:SampleEdit):
        with queue_lock,CPU_LOCK,sessions.begin() as db:
            s,j=sample(db,id_);folder=Path(s.path).parent;record=edit_record(folder,body,CLASS_NAMES)
            s.annotations=record['annotations'];s.validation=record['validation']
            with Image.open(s.path) as image:w,h=image.size
            (folder/'labels.txt').write_text('\n'.join(yolo_line(a,w,h) for a in s.annotations),encoding='utf-8')
            j.status='review_required' if any(not other.validation['passed'] for other in db.scalars(select(Sample).where(Sample.job_id==j.id))) else 'completed'
            return record
    @router.post('/{id_}/regenerate')
    def regenerate(id_:str):
        with queue_lock,CPU_LOCK,sessions.begin() as db:
            s,j=sample(db,id_);folder=Path(s.path).parent;before=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
            revision=before.get('revision',0)+1
            # Render to a new folder. Keep the old image/masks available for audit.
            target=folder.parent/f'{s.index:06d}-regenerated-{revision}'
            config=GenerationConfig.model_validate(j.config);regions=snapshot_regions(j.template_snapshot)
            result=render_sample(Path(j.template_snapshot['image_path']),regions,config,s.index,target,revision+config.max_retries+1,asset_root=root)
            expected=len(optional_regions(result['width'],result['height'],regions,config));report=validate(result,target,expected)
            metadata={'index':s.index,'seed':result['seed'],'transform':result['transform'],'annotations':result['annotations'],'validation':report,'revision':revision,'rejected':False,'erased_regions':result['erased_regions']}
            (target/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
            (target/'labels.txt').write_text('\n'.join(yolo_line(a,result['width'],result['height']) for a in result['annotations']),encoding='utf-8')
            s.path=str(target/'image.png');s.annotations=result['annotations'];s.validation=report;s.sha256=result['sha256']
            j.status='review_required' if any(not other.validation['passed'] for other in db.scalars(select(Sample).where(Sample.job_id==j.id))) else 'completed'
            return metadata
    return router
