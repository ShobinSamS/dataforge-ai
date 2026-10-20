import json
import random

import cv2
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.render import asset,render_sample
from backend.app.schemas import RuleOptions,Region,GenerationConfig
from backend.app.validation import qr_matches
from backend.app.main import create_app
from backend.app.db import Template,Job,Sample
from backend.app.jobs import next_hash


def test_dense_transparent_codes_decode_on_colored_background_and_wrong_payload_does_not():
    yy,xx=np.mgrid[:600,:600]
    pixels=np.empty((600,600,3),dtype=np.uint8)
    pixels[:,:,0]=80+xx//10;pixels[:,:,1]=150+yy//15;pixels[:,:,2]=210+xx//20
    detector=cv2.QRCodeDetector()
    for seed in range(10):
        rng=random.Random(seed)
        value=''.join(rng.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',k=500))
        layer,_=asset('qr',(600,600),value,rng,RuleOptions())
        page=Image.fromarray(pixels.copy());page.paste(layer,(0,0),layer)
        gray=cv2.cvtColor(np.asarray(page),cv2.COLOR_RGB2GRAY)
        annotation={'bbox':[0,0,600,600],'text':value}
        assert qr_matches(gray,annotation,detector),seed
    assert not qr_matches(gray,{**annotation,'text':'WRONG VALUE'},detector)
    assert not qr_matches(np.full((600,600),160,np.uint8),annotation,detector)


def test_recheck_updates_reports_only_and_does_not_accept_genuinely_wrong_code(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'db.sqlite'}",tmp_path,start_worker=False)
    source=tmp_path/'source.png';Image.new('RGB',(800,800),'#75b5df').save(source)
    region=Region(id='qr',kind='qr',box=[100,100,600,600],confirmed=True,rule_options={'character_length':500})
    config=GenerationConfig(template_id='template',count=2,blur_probability=0,rotation_probability=0)
    snapshot={'width':800,'height':800,'regions':[region.model_dump(mode='json')],'image_path':str(source)}
    hashes=[]
    with app.state.sessions.begin() as db:
        db.add(Template(id='template',name='test',image_path=str(source),width=800,height=800,regions=snapshot['regions']))
        db.flush()
        db.add(Job(id='job',template_id='template',name='test',config=config.model_dump(mode='json'),template_snapshot=snapshot,total=2,completed=2,status='review_required'))
        db.flush()
        for index in range(2):
            folder=tmp_path/'jobs'/'job'/f'{index:06d}'
            result=render_sample(source,[region],config,index,folder)
            annotations=result['annotations']
            if index==1:annotations[0]['text']='WRONG VALUE'
            report={'passed':False,'errors':['qr_unreadable:qr']}
            (folder/'metadata.json').write_text(json.dumps({'annotations':annotations,'validation':report}),encoding='utf-8')
            sha=next_hash(folder/'image.png');hashes.append(sha)
            db.add(Sample(id=f's{index}',job_id='job',index=index,path=str(folder/'image.png'),annotations=annotations,validation=report,sha256=sha))
    with TestClient(app) as client:
        response=client.post('/api/jobs/job/revalidate')
        assert response.status_code==200,response.text
        assert response.json()=={'total':2,'accepted':1,'rejected':1,'status':'review_required','images_changed':False}
        rows=client.get('/api/jobs/job/samples').json()
        assert rows[0]['validation']['passed'] and not rows[1]['validation']['passed']
        for index,row in enumerate(rows):
            folder=tmp_path/'jobs'/'job'/f'{index:06d}'
            assert next_hash(folder/'image.png')==hashes[index]
            assert json.loads((folder/'metadata.json').read_text())['validation']==row['validation']
        with app.state.sessions.begin() as db:db.get(Job,'job').status='running'
        assert client.post('/api/jobs/job/revalidate').status_code==409
        assert client.post('/api/jobs/missing/revalidate').status_code==404
