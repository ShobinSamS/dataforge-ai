"""Authored fictional multi-page packs with explicit structure and grouped splits."""
import copy
import hashlib
import io
import json
import random
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
from pathlib import Path
from typing import Literal
import numpy as np
import psutil
from faker import Faker
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import Field,model_validator
from PIL import Image,ImageDraw
from .db import uid
from .schemas import Contract,RuleOptions,CLASS_NAMES
from .resources import CPU_LOCK
from .fonts import load_font
from .handwriting import handwritten
from .signatures import render_signature
from .seals import render_seal,plan_seal_content
from .qr_capacity import qr_code
from .capture import capture_plan,capture_image,warp_mask
from .sample_editing import SampleEdit
from .portraits import illustration

LAB_CLASSES=CLASS_NAMES+['checkbox','table_header','table_cell']


class LabConfig(Contract):
    name: str = Field(default='Fictional document packs',min_length=1,max_length=100)
    kind: Literal['invoice','application','mixed'] = 'mixed'
    count: int = Field(default=10,ge=1,le=100)
    pages: int = Field(default=2,ge=1,le=5)
    seed: int = Field(default=42,ge=0,le=2**31-1)
    layout_families: int = Field(default=5,ge=1,le=30)
    capture: Literal['none','phone','scanner','photocopy','cropped_scan','mixed'] = 'mixed'
    capture_strength: float = Field(default=.5,ge=0,le=1)
    capture_percent: int = Field(default=50,ge=0,le=100)
    handwritten_percent: int = Field(default=30,ge=0,le=100)
    faint_percent: int = Field(default=30,ge=0,le=100)
    signature_percent: int = Field(default=80,ge=0,le=100)
    seal_percent: int = Field(default=60,ge=0,le=100)
    negative_percent: int = Field(default=10,ge=0,le=100)
    train_percent: int = Field(default=80,ge=1,le=100)
    validation_percent: int = Field(default=10,ge=0,le=99)

    @model_validator(mode='after')
    def splits(self):
        if self.train_percent+self.validation_percent>100:raise ValueError('Train and validation percentages exceed 100')
        if self.count*self.pages>300:raise ValueError('At most 300 pages per run')
        return self


def atomic(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2),encoding='utf-8');temp.replace(path)


def plan_documents(config):
    """Exact per-document quotas (rounded), with negatives excluding both marks."""
    rng=random.Random(config.seed);n=config.count
    groups=list(range(min(n,config.layout_families)));rng.shuffle(groups)
    val=round(len(groups)*config.validation_percent/100)
    test=round(len(groups)*(100-config.train_percent-config.validation_percent)/100)
    if len(groups)>=3:
        val=max(int(config.validation_percent>0),val);test=max(int(config.train_percent+config.validation_percent<100),test)
    while val+test>=len(groups):
        if test:test-=1
        elif val:val-=1
    assignments={g:'validation' if i<val else 'test' if i<val+test else 'train' for i,g in enumerate(groups)}
    def select(rate,pool=None):
        ids=list(range(n)) if pool is None else list(pool);rng.shuffle(ids)
        return set(ids[:min(len(ids),round(n*rate/100))])
    negative=select(config.negative_percent);eligible=set(range(n))-negative
    rates={k:select(getattr(config,k+'_percent'),eligible if k in {'signature','seal'} else None)
           for k in ['capture','handwritten','signature','seal']}
    rates['faint']=select(config.faint_percent,rates['signature']|rates['seal'])
    return [{'index':i,'family':i%len(groups),'split':assignments[i%len(groups)],'negative':i in negative,
             **{k:i in selected for k,selected in rates.items()}} for i in range(n)]


def pack_record(config,index,family,revision=0):
    rng=random.Random(f'pack:{config.seed}:{index}:{revision}');fake=Faker('en_US');fake.seed_instance(rng.getrandbits(32))
    born=date(1960,1,1)+timedelta(days=rng.randrange(15000));issued=date(2026,1,1)+timedelta(days=rng.randrange(300))
    age=issued.year-born.year-((issued.month,issued.day)<(born.month,born.day))
    rows=[]
    for i in range(rng.randint(3,9)):
        quantity=rng.randint(1,8);unit_cents=rng.randint(125,9000)
        rows.append({'description':rng.choice(['Notebook set','Office supplies','Design service','Training session','Archive folder','Desk organizer'])+f' {i+1}',
                     'quantity':quantity,'unit_cents':unit_cents,'amount_cents':quantity*unit_cents})
    total=sum(r['amount_cents'] for r in rows)
    return {'name':fake.name(),'dob':born.isoformat(),'age':age,'issued':issued.isoformat(),
            'expires':(issued+timedelta(days=365)).isoformat(),'reference':f'DOC-{config.seed:04d}-{index+1:04d}',
            'address':f'{rng.randint(10,999)} Example Avenue\nTestville, ZZ 00000',
            'rows':rows,'total_cents':total,'family':family,'portrait_seed':config.seed+family*7919,
            'signer':f'Mira {chr(65+family%26)}','signature_seed':config.seed+family*6151,
            'kind':config.kind if config.kind!='mixed' else rng.choice(['invoice','application']),
            'checkbox':rng.choice([True,False]),'revision':revision}


def render_lab_page(config,plan,record,page,folder):
    folder.mkdir(parents=True,exist_ok=True);w,h=1240,1754
    seed=config.seed+plan['index']*1009+page*31+record['revision']*100003
    rng=random.Random(seed);layout=random.Random(f'layout:{config.seed}:{plan["family"]}')
    image=Image.new('RGB',(w,h),'#fffefa');draw=ImageDraw.Draw(image)
    left=layout.randint(65,115)+rng.randint(-6,6);right=w-left
    accent=layout.choice(['#17334c','#393939','#3d4860','#4e4343']);annotations=[];cells=[];links=[]
    capture=capture_plan((w,h),config.capture if plan['capture'] else 'none',seed,config.capture_strength)
    def add_layer(id_,kind,text,layer,mask,x,y,extra=None):
        image.paste(layer,(x,y),layer)
        full=Image.new('L',(w,h));full.paste(mask,(x,y));full=warp_mask(full,capture)
        bounds=full.getbbox()
        if not bounds:raise ValueError('Empty generated label')
        x0,y0,x1,y1=bounds;mask_name=f'mask_{id_}.png';full.save(folder/mask_name)
        annotation={'region_id':id_,'class':kind,'text':str(text),'bbox':[x0,y0,x1-x0,y1-y0],
                    'mask':mask_name,'page':page,'synthetic':True,'provenance':'renderer-mask',**(extra or {})}
        annotations.append(annotation);return annotation
    def text(id_,value,x,y,size=25,kind='text',hand=False,box=None):
        value=str(value)
        if hand:
            layer,mask=handwritten(box or (520,70),value,'#182336',seed+len(annotations))
        else:
            face=load_font(size);bounds=ImageDraw.Draw(Image.new('L',(1,1))).multiline_textbbox((0,0),value,font=face,spacing=5)
            layer=Image.new('RGBA',(max(1,bounds[2]-bounds[0])+6,max(1,bounds[3]-bounds[1])+6))
            ImageDraw.Draw(layer).multiline_text((3-bounds[0],3-bounds[1]),value,font=face,fill='#17222f',spacing=5)
            mask=layer.getchannel('A').point(lambda p:255 if p else 0)
        if x+layer.width>w-20 or y+layer.height>h-20:raise ValueError('Generated content exceeds page bounds')
        return add_layer(id_,kind,value,layer,mask,x,y,{'writing_style':'handwritten' if hand else 'printed'})
    draw.rectangle((left,70,right,80),fill=accent)
    text('heading','NORTHSTAR DEMO SERVICES',left,106,38)
    text('document_type',('ITEMIZED INVOICE' if record['kind']=='invoice' else 'MEMBERSHIP APPLICATION'),left,175,29)
    text('reference',record['reference'],left,235,23,'identifier')
    text('page',f'Page {page+1} of {config.pages}',right-200,235,22)
    text('name_key','Name / customer',left,295,21)
    name=text('name',record['name'],left,328,30,'name',plan['handwritten'])
    text('address_key','Address',left,419,21);text('address',record['address'],left,451,25,'address')
    text('issued_key','Issue date',right-310,295,21);text('issued',record['issued'],right-310,330,25,'date')
    text('expiry_key','Expiry date',right-310,409,21);text('expiry',record['expires'],right-310,444,25,'date')
    links.append({'source':'issued','target':'expiry','relation':'plus_365_days'})
    payload=json.dumps({'reference':record['reference'],'name':record['name'],'issued':record['issued']},separators=(',',':'))
    encoded=qr_code(payload,4);encoded.make(fit=True)
    code=encoded.make_image(fill_color='black',back_color='white').convert('RGBA')
    side=len(encoded.get_matrix())*3;code=code.resize((side,side),Image.Resampling.NEAREST)
    add_layer('qr','qr',payload,code,Image.new('L',code.size,255),right-205,525,{'relationship':['reference','name','issued']})
    text('dob',record['dob'],left,565,25,'date',plan['handwritten'],(300,65))
    text('dob_key','Birth date',left,535,20)
    text('age',f'Age on issue date: {record["age"]}',left,652,24)
    links.append({'source':'dob','target':'age','relation':'age_on_issue_date'})
    y=790
    if record['kind']=='invoice':
        row_h=43;cols=[left,left+65,left+510,left+620,left+800,right];headers=['No.','Description','Qty','Pricing']
        draw.rectangle((left,y,right,y+row_h),fill='#e3e8ec')
        text('table_title','GOODS AND SERVICES',left,y-42,23)
        for col,header in enumerate(headers):
            a=text(f'header_{col}',header,cols[col]+8,y+10,21,kind='table_header')
            span=2 if col==3 else 1
            a.update(table_id='items',row=-2,column=col,row_span=1,col_span=span)
            cells.append({'region_id':a['region_id'],'row':-2,'column':col,'row_span':1,'col_span':span,'value':header})
        for col,header in [(3,'Unit'),(4,'Amount')]:
            a=text(f'subheader_{col}',header,cols[col]+8,y+row_h+10,21,'table_header')
            a.update(table_id='items',row=-1,column=col,row_span=1,col_span=1)
            cells.append({'region_id':a['region_id'],'row':-1,'column':col,'row_span':1,'col_span':1,'value':header})
        for row,item in enumerate(record['rows']):
            top=y+(row+2)*row_h
            vals=[str(row+1),item['description'],str(item['quantity']),f'{item["unit_cents"]/100:.2f}',f'{item["amount_cents"]/100:.2f}']
            for col,value in enumerate(vals):
                a=text(f'cell_{row}_{col}',value,cols[col]+8,top+12,21,'table_cell')
                a.update(table_id='items',row=row,column=col,row_span=1,col_span=1)
                cells.append({'region_id':a['region_id'],'row':row,'column':col,'row_span':1,'col_span':1,'value':value})
            draw.line((left,top,right,top),fill='#bdc5ca',width=1)
        bottom=y+(len(record['rows'])+2)*row_h
        for col,x in enumerate(cols):draw.line((x,y+(row_h if col==4 else 0),x,bottom),fill='#bdc5ca',width=1)
        draw.line((left,bottom,right,bottom),fill='#bdc5ca',width=1)
        text('total',f'TOTAL {record["total_cents"]/100:.2f}',right-340,bottom+24,30)
        links.append({'sources':[f'cell_{i}_4' for i in range(len(record['rows']))],'target':'total','relation':'sum_line_amounts'})
    else:
        for row,(label,value) in enumerate([('Membership category','Individual'),('Contact email',f'record{plan["index"]}@example.invalid'),('Requested service','Research access')]):
            top=y+row*100;draw.line((left,top+75,right,top+75),fill='#bdc5ca',width=1)
            text(f'key_{row}',label,left,top,23);text(f'value_{row}',value,left+380,top,26,hand=plan['handwritten'],box=(540,65))
            links.append({'source':f'key_{row}','target':f'value_{row}','relation':'key_value'})
        draw.rectangle((left,1140,left+30,1170),outline='#17222f',width=2)
        if record['checkbox']:draw.line((left+5,1154,left+13,1164,left+27,1144),fill='#182336',width=3)
        layer=Image.new('RGBA',(34,34));ImageDraw.Draw(layer).rectangle((0,0,32,32),outline='#17222f',width=2)
        add_layer('checkbox','checkbox',str(record['checkbox']).lower(),layer,Image.new('L',(34,34),255),left,1140,{'checked':record['checkbox']})
        text('checkbox_key','Include supporting material',left+48,1144,24)
        portrait=illustration((180,210),random.Random(record['portrait_seed'])).convert('RGBA')
        add_layer('portrait','portrait','Fictional portrait illustration',portrait,Image.new('L',portrait.size,255),right-220,1185,{'asset_group':f'portrait-family-{plan["family"]}'})
    if plan['signature']:
        options=RuleOptions(signature_style=random.Random(record['signature_seed']).choice(['enclosed','interwoven','terminal_loop','initial_bridge','minimal','surname']),
                            ink_opacity_mode='fixed',ink_opacity=.4 if plan['faint'] else .9,color_mode='manual',text_color='#18283d',font_weight='normal')
        layer,mask,details=render_signature((410,160),record['signer'],random.Random(record['signature_seed']),options)
        add_layer('signature','signature',details['text'],layer,mask,left,1450,{'signature':details,'asset_group':f'signature-family-{plan["family"]}'})
    if plan['seal']:
        options=RuleOptions(seal_style='corporate',seal_text_mode='static',seal_text='NORTHSTAR DEMO',seal_bottom_text='RESEARCH DIVISION',seal_subtext='RECEIVED',seal_color='blue',ink_opacity_mode='fixed',ink_opacity=.35 if plan['faint'] else .88)
        layer,mask,details=render_seal((225,225),plan_seal_content(options,seed,'seal'),random.Random(seed),options)
        add_layer('seal','seal',details['text'],layer,mask,right-230,1405,{'seal':details})
    text('footer',f'Fictional data | {record["reference"]} | page {page+1}/{config.pages}',left,1665,20)
    image.save(folder/'clean.png',dpi=(150,150))
    image=capture_image(image,capture);image.save(folder/'image.png',dpi=(150,150))
    # Also retain the capture-free image as a paired target for restoration work.
    result={'page':page,'width':w,'height':h,'paper':'A4','dpi':150,'annotations':annotations,'table_cells':cells,
            'relationships':links,'capture':capture,'record':record,'plan':plan,'revision':0,'rejected':False,
            'mask_semantics':'ideal ink before blur/compression','transcription_source':'renderer input',
            'sha256':hashlib.sha256((folder/'image.png').read_bytes()).hexdigest()}
    atomic(folder/'metadata.json',result);return result


class DocumentLab:
    def __init__(self,root):
        self.root=root/'document-lab';self.root.mkdir(exist_ok=True,parents=True)
        self.lock=threading.RLock();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='document-lab');self.jobs={};self.cancels={}
        for path in self.root.glob('*/job.json'):
            try:
                job=json.loads(path.read_text(encoding='utf-8'))
                if job['status'] in {'queued','running','cancelling'}:job.update(status='paused',error='App restarted; resume remaining packs')
                self.jobs[job['id']]=job;self.cancels[job['id']]=threading.Event()
            except (OSError,ValueError,KeyError):continue
    def write(self,job):atomic(self.root/job['id']/'job.json',job)
    def get(self,id_):
        with self.lock:
            if id_ not in self.jobs:raise HTTPException(404,'Document lab run not found')
            return copy.deepcopy(self.jobs[id_])
    def update(self,id_,**patch):
        with self.lock:self.jobs[id_].update(patch);self.write(self.jobs[id_])
    def submit(self,config):
        with self.lock:
            if sum(j['status'] in {'queued','running','cancelling'} for j in self.jobs.values())>=3:raise HTTPException(429,'Document lab queue is full')
            id_=uid();(self.root/id_).mkdir();plans=plan_documents(config)
            job={'id':id_,'config':config.model_dump(),'plans':plans,'status':'queued','completed':0,'total':config.count*config.pages,'error':'','created_at':time.time(),'pages':[],
                 'download_url':f'/api/document-lab/jobs/{id_}/download'}
            self.jobs[id_]=job;self.cancels[id_]=threading.Event();self.write(job);self.pool.submit(self.run,id_)
            return self.get(id_)
    def run(self,id_):
        try:
            job=self.get(id_);config=LabConfig.model_validate(job['config']);self.update(id_,status='running',error='')
            existing={(p['document'],p['page']) for p in job['pages']}
            for plan in job['plans']:
                record=pack_record(config,plan['index'],plan['family'])
                for page in range(config.pages):
                    if (plan['index'],page) in existing:continue
                    cancel=self.cancels[id_]
                    if cancel.is_set():self.update(id_,status='cancelled');return
                    if psutil.virtual_memory().available/1024**2<1500:self.update(id_,status='paused',error='Available RAM below 1.5 GB; free memory and resume');return
                    while not CPU_LOCK.acquire(timeout=.3):
                        if cancel.is_set():self.update(id_,status='cancelled');return
                    try:
                        folder=self.root/id_/f'{plan["index"]:04d}-{page:02d}'
                        result=render_lab_page(config,plan,record,page,folder)
                    finally:CPU_LOCK.release()
                    item={'document':plan['index'],'page':page,'split':plan['split'],'family':plan['family'],'revision':0,
                          'image_url':f'/api/document-lab/jobs/{id_}/pages/{plan["index"]}/{page}/image','rejected':False,'annotation_count':len(result['annotations'])}
                    with self.lock:
                        self.jobs[id_]['pages'].append(item);self.jobs[id_]['completed']+=1;self.write(self.jobs[id_])
            self.update(id_,status='completed')
        except Exception as exc:self.update(id_,status='failed',error=str(exc)[:600])
    def folder(self,id_,document,page):
        job=self.get(id_)
        item=next((p for p in job['pages'] if p['document']==document and p['page']==page),None)
        if item is None:raise HTTPException(404,'Page not found')
        return self.root/id_/item.get('storage_folder',f'{document:04d}-{page:02d}')
    def resume(self,id_):
        with self.lock:
            if self.get(id_)['status'] not in {'failed','paused','cancelled'}:raise HTTPException(409,'This run cannot be resumed')
            if sum(j['status'] in {'queued','running','cancelling'} for j in self.jobs.values())>=3:raise HTTPException(429,'Document lab queue is full')
            self.cancels[id_].clear();self.update(id_,status='queued',error='');self.pool.submit(self.run,id_);return self.get(id_)
    def close(self):
        for cancel in self.cancels.values():cancel.set()
        self.pool.shutdown(wait=True,cancel_futures=True)


def lab_router(lab):
    router=APIRouter(prefix='/api/document-lab',tags=['Document lab'])
    @router.post('/jobs',status_code=201)
    def create(body:LabConfig):return lab.submit(body)
    @router.get('/jobs')
    def jobs():
        with lab.lock:return [lab.get(j['id']) for j in sorted(lab.jobs.values(),key=lambda j:j['created_at'],reverse=True)[:100]]
    @router.get('/jobs/{id_}')
    def get(id_:str):return lab.get(id_)
    @router.post('/jobs/{id_}/cancel')
    def cancel(id_:str):
        with lab.lock:
            if lab.get(id_)['status'] not in {'queued','running'}:raise HTTPException(409,'Run is not active')
            lab.cancels[id_].set();lab.update(id_,status='cancelling');return lab.get(id_)
    @router.post('/jobs/{id_}/resume')
    def resume(id_:str):return lab.resume(id_)
    @router.get('/jobs/{id_}/pages/{document}/{page}')
    def metadata(id_:str,document:int,page:int):return json.loads((lab.folder(id_,document,page)/'metadata.json').read_text(encoding='utf-8'))
    @router.get('/jobs/{id_}/pages/{document}/{page}/image')
    def image(id_:str,document:int,page:int):return FileResponse(lab.folder(id_,document,page)/'image.png',media_type='image/png')
    @router.put('/jobs/{id_}/pages/{document}/{page}')
    def edit_page(id_:str,document:int,page:int,body:SampleEdit):
        from .sample_editing import edit_record
        with lab.lock,CPU_LOCK:
            job=lab.get(id_)
            if job['status'] in {'running','queued','cancelling'}:raise HTTPException(409,'Wait for generation to stop before editing')
            folder=lab.folder(id_,document,page)
            classes=LAB_CLASSES
            result=edit_record(folder,body,classes)
            for p in lab.jobs[id_]['pages']:
                if p['document']==document and p['page']==page:p.update(rejected=result['rejected'],revision=result['revision'],annotation_count=len(result['annotations']))
            lab.write(lab.jobs[id_]);return result
    @router.post('/jobs/{id_}/documents/{document}/regenerate')
    def regenerate(id_:str,document:int):
        with lab.lock,CPU_LOCK:
            job=lab.get(id_)
            if job['status'] in {'running','queued','cancelling'}:raise HTTPException(409,'Wait for generation to stop before regenerating')
            config=LabConfig.model_validate(job['config'])
            if not 0<=document<config.count:raise HTTPException(404,'Document not found')
            plan=job['plans'][document]
            revision=max((p['revision'] for p in job['pages'] if p['document']==document),default=0)+1
            record=pack_record(config,document,plan['family'],revision)
            replacements={}
            for page in range(config.pages):
                name=f'{document:04d}-{page:02d}-generation-{revision}-{uid()[:8]}'
                folder=lab.root/id_/name
                result=render_lab_page(config,plan,record,page,folder);result['revision']=revision;atomic(folder/'metadata.json',result)
                replacements[page]={'storage_folder':name,'revision':revision,'rejected':False,'annotation_count':len(result['annotations'])}
            # Switch every page together only after the full pack succeeded;
            # previous image/mask folders remain recoverable on disk.
            for p in lab.jobs[id_]['pages']:
                if p['document']==document:p.update(replacements[p['page']])
            lab.write(lab.jobs[id_]);return lab.get(id_)
    @router.get('/jobs/{id_}/download')
    def download(id_:str):
        from starlette.background import BackgroundTask
        with lab.lock,CPU_LOCK:
            job=lab.get(id_)
            if job['status'] in {'running','queued','cancelling'}:raise HTTPException(409,'Wait for generation to stop before exporting')
            accepted=[p for p in job['pages'] if not p['rejected']]
            if not accepted:raise HTTPException(409,'No accepted pages to export')
            path=lab.root/id_/f'export-{uid()}.zip'
            classes=LAB_CLASSES
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
                z.writestr('dataset.json',json.dumps({'config':job['config'],'plans':job['plans'],'count':len(accepted),'classes':classes,'split_policy':'layout family, signer and portrait identity stay in one split','training_ready':False,'synthetic':True},indent=2))
                z.writestr('data.yaml','path: .\ntrain: images/train\nval: images/validation\ntest: images/test\nnames:\n'+''.join(f'  {i}: {name}\n' for i,name in enumerate(classes)))
                coco={'images':[],'annotations':[],'categories':[{'id':i,'name':name} for i,name in enumerate(classes)]}
                for p in accepted:
                    folder=lab.folder(id_,p['document'],p['page']);record=json.loads((folder/'metadata.json').read_text(encoding='utf-8'));base=f'{p["document"]:04d}-{p["page"]:02d}';split=p['split']
                    z.write(folder/'image.png',f'images/{split}/{base}.png');labels=[]
                    z.write(folder/'clean.png',f'clean/{split}/{base}.png')
                    image_id=len(coco['images']);coco['images'].append({'id':image_id,'file_name':f'images/{split}/{base}.png','width':record['width'],'height':record['height']})
                    for a in record['annotations']:
                        x,y,w,h=a['bbox'];cls=classes.index(a['class']);labels.append(f'{cls} {(x+w/2)/1240:.8f} {(y+h/2)/1754:.8f} {w/1240:.8f} {h/1754:.8f}')
                        from .exporting import rle
                        with Image.open(folder/a['mask']) as mask:
                            segmentation=rle(mask);area=int(np.count_nonzero(np.asarray(mask)))
                        coco['annotations'].append({'id':len(coco['annotations']),'image_id':image_id,'category_id':cls,'bbox':a['bbox'],'iscrowd':0,'area':area,'segmentation':segmentation})
                        z.write(folder/a['mask'],f'masks/{base}/{a["mask"]}');a['mask']=f'masks/{base}/{a["mask"]}'
                    z.writestr(f'labels/{split}/{base}.txt','\n'.join(labels));z.writestr(f'metadata/{base}.json',json.dumps(record));z.writestr(f'ocr/{base}.json',json.dumps(record['annotations']))
                z.writestr('annotations.json',json.dumps(coco))
                for document in sorted({p['document'] for p in accepted}):
                    pages=[]
                    try:
                        for p in sorted((p for p in accepted if p['document']==document),key=lambda p:p['page']):
                            with Image.open(lab.folder(id_,document,p['page'])/'image.png') as im:pages.append(im.convert('RGB'))
                        buffer=io.BytesIO();pages[0].save(buffer,format='PDF',save_all=True,append_images=pages[1:],resolution=150)
                        z.writestr(f'pdf/{document:04d}.pdf',buffer.getvalue())
                    finally:
                        for im in pages:im.close()
        return FileResponse(path,filename=f'document-packs-{id_[:8]}.zip',media_type='application/zip',background=BackgroundTask(path.unlink,missing_ok=True))
    return router
