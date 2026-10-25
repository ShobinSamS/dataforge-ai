import io
import json
import time
import zipfile
from datetime import date
from pathlib import Path
import numpy as np
import pytest
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.document_lab import LabConfig,plan_documents,pack_record,render_lab_page
from backend.app.consistency import apply_links
from backend.app.capture import capture_plan,capture_image,warp_mask
from backend.app.schemas import Region,GenerationConfig,FieldLink,RuleOptions
from backend.app.render import fictional_values,render_sample
from backend.app.signatures import render_signature
from backend.app.sample_editing import SampleEdit,edit_record
import random


def test_pack_quotas_and_grouped_splits_are_deterministic():
    config=LabConfig(count=50,layout_families=10,signature_percent=60,seal_percent=40,negative_percent=20)
    plans=plan_documents(config)
    assert plans==plan_documents(config)
    assert sum(p['negative'] for p in plans)==10
    assert sum(p['signature'] for p in plans)==30 and sum(p['seal'] for p in plans)==20
    assert all(not p['signature'] and not p['seal'] for p in plans if p['negative'])
    assert {p['split'] for p in plans}=={'train','validation','test'}
    for family in range(10):assert len({p['split'] for p in plans if p['family']==family})==1
    for p in plans:
        r=pack_record(config,p['index'],p['family'])
        assert r['total_cents']==sum(row['quantity']*row['unit_cents'] for row in r['rows'])
        assert date.fromisoformat(r['expires'])>date.fromisoformat(r['issued'])>date.fromisoformat(r['dob'])
    with pytest.raises(ValueError):LabConfig(count=100,pages=5)
    with pytest.raises(ValueError):LabConfig(train_percent=90,validation_percent=20)


def test_explicit_field_relationships_dates_sums_payloads_and_cycles():
    regions=[Region(id=id_,kind=kind,box=[10,10,300,50]) for id_,kind in [('dob','date'),('age','text'),('issue','date'),('expiry','date'),('a','text'),('b','text'),('total','text'),('qr','qr')]]
    values={'dob':'1988-12-30','age':'','issue':'2026-01-02','expiry':'','a':'12.25','b':'2.50','total':'','qr':''}
    links=[FieldLink(target='qr',sources=['total','expiry'],rule='copy'),FieldLink(target='age',sources=['dob'],rule='age',as_of=date(2026,1,1)),FieldLink(target='expiry',sources=['issue'],rule='after_date',days=365),FieldLink(target='total',sources=['a','b'],rule='sum')]
    result=apply_links(values,links,regions)
    assert result['age']=='37' and result['expiry']=='2027-01-02' and result['total']=='14.75'
    assert result['qr']=='14.75 | 2027-01-02'
    with pytest.raises(ValueError,match='cycle'):apply_links(values,[FieldLink(target='a',sources=['b']),FieldLink(target='b',sources=['a'])],regions)
    with pytest.raises(ValueError,match='unavailable'):apply_links(values,[FieldLink(target='a',sources=['missing'])],regions)


def test_camera_geometry_tracks_masks_and_default_is_unchanged(tmp_path):
    source=Image.new('RGB',(640,480),'white');source.save(tmp_path/'source.png')
    region=Region(id='name',kind='name',box=[100,100,350,80],confirmed=True)
    config=GenerationConfig(template_id='test',blur_probability=0,rotation_probability=0,capture_profile='phone',capture_strength=.8)
    result=render_sample(tmp_path/'source.png',[region],config,0,tmp_path/'sample')
    assert not result['errors']
    a=result['annotations'][0]
    with Image.open(tmp_path/'sample'/a['mask']) as mask:
        x,y,w,h=a['bbox'];assert mask.getbbox()==(x,y,x+w,y+h)
    plan=capture_plan(source.size,'phone',42,.8)
    assert plan==capture_plan(source.size,'phone',42,.8)
    assert capture_image(source,capture_plan(source.size,'none',42)).tobytes()==source.tobytes()


def test_lab_page_masks_tables_merged_headers_and_clean_pair(tmp_path):
    config=LabConfig(count=1,pages=2,kind='invoice',signature_percent=100,seal_percent=100,negative_percent=0,capture_percent=100,capture='phone')
    plan=plan_documents(config)[0];record=pack_record(config,0,0)
    first=render_lab_page(config,plan,record,0,tmp_path/'first');second=render_lab_page(config,plan,record,1,tmp_path/'second')
    assert first['record']==second['record']
    assert any(c['col_span']==2 for c in first['table_cells'])
    assert (tmp_path/'first'/'clean.png').exists()
    for a in first['annotations']:
        with Image.open(tmp_path/'first'/a['mask']) as mask:
            x,y,w,h=a['bbox'];assert mask.getbbox()==(x,y,x+w,y+h)
    qr=next(a for a in first['annotations'] if a['class']=='qr')
    assert json.loads(qr['text'])['name']==record['name']
    changed=SampleEdit(revision=0,annotations=[{'region_id':a['region_id'],'kind':a['class'],'text':a['text'],'bbox':a['bbox']} for a in first['annotations']])
    changed.annotations[0].bbox=(30,30,100,30)
    edited=edit_record(tmp_path/'first',changed,['text','name','identifier','address','date','qr','signature','seal','portrait','checkbox','table_header','table_cell'])
    assert edited['revision']==1 and edited['annotations'][0]['provenance']=='human-box'
    assert (tmp_path/'first'/'revisions'/'0000.json').exists()
    from fastapi import HTTPException
    with pytest.raises(HTTPException):edit_record(tmp_path/'first',changed,['text'])


def test_lab_api_export_splits_correction_and_regeneration(tmp_path,monkeypatch):
    from backend.app import document_lab
    monkeypatch.setattr(document_lab.psutil,'virtual_memory',lambda:type('Memory',(),{'available':8*1024**3})())
    with TestClient(create_app(f"sqlite:///{tmp_path/'api.db'}",tmp_path,start_worker=False)) as c:
        r=c.post('/api/document-lab/jobs',json={'count':2,'pages':2,'kind':'application','capture':'none','layout_families':2,'negative_percent':100,'signature_percent':0,'seal_percent':0});assert r.status_code==201,r.text
        job=r.json()
        for _ in range(600):
            job=c.get('/api/document-lab/jobs/'+job['id']).json()
            if job['status'] in {'completed','failed','paused'}:break
            time.sleep(.05)
        assert job['status']=='completed',job
        endpoint=f'/api/document-lab/jobs/{job["id"]}/pages/0/0';record=c.get(endpoint).json()
        assert all(a['class'] not in {'signature','seal'} for a in record['annotations'])
        body={'revision':0,'rejected':True,'annotations':[{'region_id':a['region_id'],'kind':a['class'],'text':a['text'],'bbox':a['bbox']} for a in record['annotations']]}
        assert c.put(endpoint,json=body).status_code==200
        z=c.get(job['download_url']);assert z.status_code==200,z.text
        with zipfile.ZipFile(io.BytesIO(z.content)) as archive:
            dataset=json.loads(archive.read('dataset.json'));assert dataset['count']==3
            assert len([n for n in archive.namelist() if n.startswith('pdf/')])==2
            assert json.loads(archive.read('annotations.json'))['annotations'][0]['segmentation']
        r=c.post(f'/api/document-lab/jobs/{job["id"]}/documents/0/regenerate');assert r.status_code==200,r.text
        pages=[c.get(f'/api/document-lab/jobs/{job["id"]}/pages/0/{p}').json() for p in (0,1)]
        assert pages[0]['record']==pages[1]['record'] and pages[0]['revision']==2
        assert pages[0]['record']['reference']==record['record']['reference']
        assert pages[0]['record']!=record['record']


def test_handwriting_and_generated_signature_are_annotated_honestly(tmp_path):
    from backend.app.handwriting import handwritten
    one,mask=handwritten((400,100),'Mira 17/02/2026','#182336',42)
    two,_=handwritten((400,100),'Mira 17/02/2026','#182336',42)
    assert one.tobytes()==two.tobytes() and mask.getbbox()
    art=Image.new('RGBA',(300,100));ImageDraw.Draw(art).line((20,80,120,10,110,80,270,50),fill='black',width=3)
    layer,mask,info=render_signature((400,140),'Name must not be claimed',random.Random(42),RuleOptions(),art)
    assert info['text']=='' and info['transcription_verified'] is False and info['engine']=='image-pool'
    assert mask.getbbox()


def test_existing_gallery_edits_rejects_rechecks_and_regenerates_one_sample(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path/'edit.db'}",tmp_path,start_worker=False)) as c:
        template=c.post('/api/templates/blank',json={'paper':'custom','unit':'px','width':500,'height':300,'starter':'signature'}).json()
        regions=template['regions']
        for r in regions:r['confirmed']=True
        review=c.put(f'/api/templates/{template["id"]}/review',json={'revision':1,'regions':regions,'privacy_confirmed':True})
        assert review.status_code==200,review.text
        response=c.post('/api/jobs',json={'template_id':template['id'],'count':2,'rotation_probability':0,'blur_probability':0});assert response.status_code==201,response.text
        job=response.json();c.app.state.worker.run(job['id'])
        samples=c.get(f'/api/jobs/{job["id"]}/samples').json();assert len(samples)==2
        endpoint=f'/api/samples/{samples[0]["id"]}/annotations';record=c.get(endpoint).json()
        changed=[{'region_id':a['region_id'],'kind':a['class'],'text':a['text'],'bbox':a['bbox']} for a in record['annotations']]
        changed[0]['bbox']=[50,50,120,80];changed[0]['text']='Reviewed mark'
        body={'revision':0,'rejected':True,'annotations':changed}
        saved=c.put(endpoint,json=body);assert saved.status_code==200,saved.text
        assert saved.json()['annotations'][0]['provenance']=='human-box'
        assert c.put(endpoint,json=body).status_code==409
        assert c.post(f'/api/jobs/{job["id"]}/revalidate').json()['rejected']>=1
        regenerated=c.post(f'/api/samples/{samples[0]["id"]}/regenerate');assert regenerated.status_code==200,regenerated.text
        after=c.get(f'/api/jobs/{job["id"]}/samples').json()
        assert after[1]['sha256']==samples[1]['sha256']
        assert after[0]['sha256']!=samples[0]['sha256']
