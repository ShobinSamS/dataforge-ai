import json
import io
import time
import zipfile
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.app import diffusion
from backend.app.main import create_app
from backend.app.portraits import portrait_metadata
from backend.app.resources import CPU_LOCK


def wait_job(client, id_):
    for _ in range(500):
        job = client.get(f"/api/diffusion/jobs/{id_}").json()
        if job['status'] in diffusion.TERMINAL: return job
        time.sleep(.02)
    raise AssertionError('Preview did not finish')


def test_signature_image_pool_keeps_transcription_unverified(runtime):
    response=runtime.post('/api/diffusion/jobs',json={'kind':'signature_artwork','prompt':'One invented handwritten autograph','seed':37})
    assert response.status_code==200,response.text
    job=wait_job(runtime,response.json()['id']);assert job['status']=='completed',job
    assert job['metrics']['transcription_verified'] is False
    asset=runtime.post(f'/api/diffusion/jobs/{job["id"]}/save').json()
    rendered=runtime.post('/api/assets/generate',json={'kind':'signature','value':'Do not claim this spelling','options':{'signature_artwork_ids':[asset['id']]}})
    assert rendered.status_code==200,rendered.text
    details=rendered.json()['metadata']['details']
    assert details['text']=='' and details['transcription_verified'] is False
    assert details['asset_provenance']['source']=='local_stable_diffusion'


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    model = tmp_path/'models'/'sd-turbo'; model.mkdir(parents=True)
    (model/'manifest.json').write_text(json.dumps({'repository':'stabilityai/sd-turbo','revision':'test-pinned-revision','source_url':'https://huggingface.co/stabilityai/sd-turbo','license_url':'https://huggingface.co/stabilityai/sd-turbo'}))
    monkeypatch.setattr(diffusion, 'capabilities', lambda root: {'ready':True,'model_url':'https://huggingface.co/stabilityai/sd-turbo'})
    monkeypatch.setattr(diffusion.psutil, 'virtual_memory', lambda: type('Memory', (), {'available':8*1024**3})())
    def fake(folder, model, request, cancelled, progress):
        image = Image.new('RGB',(512,512),'white'); draw = ImageDraw.Draw(image)
        if request['kind']=='signature_artwork':image=Image.open(folder/'guide.png').convert('RGB')
        else:draw.ellipse((130,70,380,440), fill='black')
        image.save(folder/'raw.png')
        progress(1)
        return {'elapsed_seconds':.1,'peak_worker_rss_mb':100,'width':512,'height':512}
    monkeypatch.setattr(diffusion, 'run_worker', fake)
    with TestClient(create_app(f"sqlite:///{tmp_path/'test.db'}", tmp_path, start_worker=False)) as client:
        yield client


@pytest.mark.parametrize('kind', ['portrait','seal_artwork','stamp_artwork'])
def test_generated_artwork_saves_reuses_and_preserves_provenance(runtime, tmp_path, kind):
    client = runtime
    start = client.post('/api/diffusion/jobs',json={'kind':kind,'prompt':'A fictional botanical design','seed':19,'steps':1})
    assert start.status_code == 200, start.text
    job = wait_job(client,start.json()['id']); assert job['status']=='completed',job
    assert job['resolved_prompt'].endswith('A fictional botanical design')
    assert job['revision']=='test-pinned-revision' and job['metrics']['peak_worker_rss_mb']==100
    assert client.get(job['image_url']).status_code==200
    asset = client.post(f"/api/diffusion/jobs/{job['id']}/save").json()
    assert client.post(f"/api/diffusion/jobs/{job['id']}/save").json()['id']==asset['id']
    provenance = portrait_metadata(tmp_path,asset['id'])
    assert provenance['source']=='local_stable_diffusion'
    assert json.loads(provenance['attribution'])['seed']==19
    options = {'portrait_source':'asset_pool','portrait_asset_ids':[asset['id']]}
    target = 'portrait' if kind=='portrait' else 'seal' if kind=='seal_artwork' else 'stamp'
    if target=='seal': options={'seal_artwork_id':asset['id'],'seal_style':'corporate','seal_symbol':'none'}
    if target=='stamp': options['stamp_style']='architecture'  # Pools must override every stamp style.
    rendered = client.post('/api/assets/generate',json={'kind':target,'width':400,'height':400,'options':options})
    assert rendered.status_code==200,rendered.text
    details=rendered.json()['metadata']['details']
    source=details if target=='portrait' else details['asset_provenance']
    assert source['source']=='local_stable_diffusion'
    if target=='seal':
        assert details['center_motif']=='artwork'
        with Image.open(tmp_path/'portraits'/asset['id']/'image.png') as image:
            assert image.getchannel('A').getextrema()==(0,255)
    canvas=client.post('/api/templates/blank',json={'paper':'custom','unit':'px','width':600,'height':600}).json()
    review=client.put(f"/api/templates/{canvas['id']}/review",json={'revision':1,'privacy_confirmed':True,'regions':[
        {'id':'generated','kind':target,'box':[100,100,400,400],'confirmed':True,'rule_options':options}]})
    assert review.status_code==200,review.text
    dataset=client.post('/api/jobs',json={'template_id':canvas['id'],'count':1,'blur_probability':0,'rotation_probability':0}).json()
    client.app.state.worker.run(dataset['id'])
    export=client.post(f"/api/jobs/{dataset['id']}/exports",json={'format':'coco','review_confirmed':True})
    assert export.status_code==201,export.text
    with zipfile.ZipFile(io.BytesIO(client.get(export.json()['download_url']).content)) as archive:
        annotation=json.loads(archive.read('metadata/000000.json'))['annotations'][0]
        assert annotation['asset_provenance']['source']=='local_stable_diffusion'


def test_busy_queue_cancellation_validation_and_missing_paths(runtime):
    client=runtime
    assert client.post('/api/diffusion/jobs',json={'prompt':' ','steps':1}).status_code==422
    assert client.post('/api/diffusion/jobs',json={'prompt':'a person','steps':5}).status_code==422
    assert client.post('/api/diffusion/jobs',json={'prompt':'a person','background_color':'red'}).status_code==422
    assert client.get('/api/diffusion/jobs/not-a-job/image').status_code==404
    assert CPU_LOCK.acquire(timeout=2)
    try:
        ids=[client.post('/api/diffusion/jobs',json={'prompt':'a tree'}).json()['id'] for _ in range(3)]
        assert client.post('/api/diffusion/jobs',json={'prompt':'a tree'}).status_code==409
        assert client.post(f'/api/diffusion/jobs/{ids[0]}/save').status_code==409
        assert client.get(f'/api/diffusion/jobs/{ids[0]}/image').status_code==409
        for id_ in ids: assert client.post(f'/api/diffusion/jobs/{id_}/cancel').status_code==200
    finally: CPU_LOCK.release()
    assert all(wait_job(client,id_)['status']=='cancelled' for id_ in ids)


def test_memory_guard_and_worker_failure_are_visible(runtime, monkeypatch):
    monkeypatch.setattr(diffusion.psutil, 'virtual_memory', lambda: type('Memory', (), {'available':2*1024**3})())
    job=runtime.post('/api/diffusion/jobs',json={'prompt':'a person'}).json()
    result=wait_job(runtime,job['id'])
    assert result['status']=='failed' and '4.5 GB' in result['error'] and result['image_url'] is None
    monkeypatch.setattr(diffusion.psutil, 'virtual_memory', lambda: type('Memory', (), {'available':8*1024**3})())
    def broken(*args): raise ValueError('Worker test failure')
    monkeypatch.setattr(diffusion,'run_worker',broken)
    result=wait_job(runtime,runtime.post('/api/diffusion/jobs',json={'prompt':'a tree'}).json()['id'])
    assert result['status']=='failed' and 'Worker test failure' in result['error']
    assert CPU_LOCK.acquire(timeout=1); CPU_LOCK.release()


def test_missing_model_is_reported_without_download_and_restart_recovers(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)) as client:
        caps=client.get('/api/diffusion/capabilities').json()
        assert not caps['model_installed'] and not caps['runtime_downloads']
        assert client.post('/api/diffusion/jobs',json={'prompt':'a tree'}).status_code==409
    folder=tmp_path/'diffusion'/('a'*32); folder.mkdir()
    (folder/'job.json').write_text(json.dumps({'id':'a'*32,'status':'running','created_at':0}))
    jobs=diffusion.DiffusionJobs(tmp_path)
    try: assert jobs.get('a'*32)['status']=='failed'
    finally: jobs.close()


def test_memory_and_cancellation_include_owned_descendant_processes(tmp_path):
    ready=tmp_path/'ready.txt'
    leaf=f"import os,time; from pathlib import Path; buffer=bytearray(b'x')*(25*1024*1024); Path({str(ready)!r}).write_text(str(os.getpid())); time.sleep(60)"
    parent=f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{leaf!r}]); time.sleep(60)"
    child=subprocess.Popen([sys.executable,'-c',parent],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        deadline=time.monotonic()+20
        while not ready.exists() and time.monotonic()<deadline: time.sleep(.05)
        assert ready.exists()
        leaf_pid=int(ready.read_text())
        tree=diffusion.worker_processes(child.pid)
        assert leaf_pid in {p.pid for p in tree}
        assert sum(p.memory_info().rss for p in tree)>25*1024**2
        diffusion.terminate_worker(child)
        deadline=time.monotonic()+5
        while diffusion.psutil.pid_exists(leaf_pid) and time.monotonic()<deadline: time.sleep(.05)
        assert not diffusion.psutil.pid_exists(leaf_pid)
    finally:
        if child.poll() is None: diffusion.terminate_worker(child)


def test_hundred_image_batch_distinct_seeds_bulk_save_zip_and_pool_limit(runtime):
    from backend.app.schemas import RuleOptions
    job=runtime.post('/api/diffusion/jobs',json={'prompt':'a botanical emblem','kind':'seal_artwork','count':100,'seed':2147483647,'steps':1}).json()
    result=wait_job(runtime,job['id'])
    assert result['status']=='completed',result
    assert result['completed']==100 and len(result['items'])==100
    assert [item['seed'] for item in result['items']]==[2147483647,*range(99)]
    assert len(runtime.get('/api/diffusion/jobs').json())==1  # Hide internal child runs.
    saved=runtime.post(f"/api/diffusion/jobs/{job['id']}/save").json()
    assert saved['saved_count']==100 and len(saved['assets'])==100
    again=runtime.post(f"/api/diffusion/jobs/{job['id']}/save").json()
    assert [a['id'] for a in again['assets']]==[a['id'] for a in saved['assets']]
    selected=runtime.post(f"/api/diffusion/jobs/{job['id']}/save?index=99").json()
    assert selected['id']==saved['assets'][99]['id']
    with zipfile.ZipFile(io.BytesIO(runtime.get(result['download_url']).content)) as z:
        assert len([name for name in z.namelist() if name.endswith('.png')])==100
        assert json.loads(z.read('100.json'))['seed']==98
    ids=[a['id'] for a in saved['assets']]
    assert len(RuleOptions(portrait_asset_ids=ids).portrait_asset_ids)==100
    assert len(RuleOptions(seal_artwork_ids=ids).seal_artwork_ids)==100
    with pytest.raises(ValueError):RuleOptions(portrait_asset_ids=ids+[ids[0]])
    assert runtime.post('/api/diffusion/jobs',json={'prompt':'a person','count':101}).status_code==422
    assert runtime.post('/api/diffusion/jobs',json={'prompt':'a person','count':0}).status_code==422
    for seed in (1,2):
        rendered=runtime.post('/api/assets/generate',json={'kind':'seal','width':400,'height':400,'seed':seed,'options':{'seal_artwork_ids':ids,'seal_style':'corporate'}})
        assert rendered.status_code==200,rendered.text
        assert rendered.json()['metadata']['details']['asset_provenance']['id'] in ids


def test_partial_batch_retains_images_and_resumes_after_app_restart(runtime,tmp_path,monkeypatch):
    original=diffusion.run_worker;calls=[];fail=True
    def sometimes_fails(folder,model,request,cancelled,progress):
        calls.append(request['seed'])
        if request['seed']==43 and fail:raise ValueError('Temporary test failure')
        return original(folder,model,request,cancelled,progress)
    monkeypatch.setattr(diffusion,'run_worker',sometimes_fails)
    job=runtime.post('/api/diffusion/jobs',json={'prompt':'a fictional person','count':3,'seed':42}).json()
    partial=wait_job(runtime,job['id'])
    assert partial['status']=='failed' and partial['completed']==1
    assert 'Temporary test failure' in partial['error'],partial
    assert len(runtime.post(f"/api/diffusion/jobs/{job['id']}/save").json()['assets'])==1
    fail=False
    with TestClient(create_app(f"sqlite:///{tmp_path/'restart.db'}",tmp_path,start_worker=False)) as restarted:
        resumed=restarted.post(f"/api/diffusion/jobs/{job['id']}/resume")
        assert resumed.status_code==200,resumed.text
        result=wait_job(restarted,job['id'])
        assert result['status']=='completed' and result['completed']==3
        assert calls==[42,43,43,44]
        assert result['items'][0]['id']==partial['items'][0]['id']


def test_cancel_batch_retains_completed_images_and_resumes(runtime,monkeypatch):
    original=diffusion.run_worker;started=threading.Event()
    def block_second(folder,model,request,cancelled,progress):
        if request['seed']==43:
            started.set()
            assert cancelled.wait(5),'Cancellation did not reach the active image worker'
            raise InterruptedError()
        return original(folder,model,request,cancelled,progress)
    monkeypatch.setattr(diffusion,'run_worker',block_second)
    job=runtime.post('/api/diffusion/jobs',json={'prompt':'a fictional person','count':3}).json()
    assert started.wait(4)
    assert runtime.post(f"/api/diffusion/jobs/{job['id']}/cancel").status_code==200
    partial=wait_job(runtime,job['id'])
    assert partial['status']=='cancelled' and partial['completed']==1
    assert partial['items'][1]['status']=='cancelled'
    monkeypatch.setattr(diffusion,'run_worker',original)
    assert runtime.post(f"/api/diffusion/jobs/{job['id']}/resume").status_code==200
    result=wait_job(runtime,job['id'])
    assert result['status']=='completed' and result['completed']==3
    assert result['items'][0]['id']==partial['items'][0]['id']
