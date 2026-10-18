import io
import json
import time
import zipfile
import numpy as np
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend.app.main import create_app
from backend.app.schemas import Region, GenerationConfig
from backend.app.privacy import check_review
from backend.app.render import fictional_values, render_sample
from backend.app.validation import yolo_line, validate
from backend.app.ingest import decode
from backend.app.demo import certificate


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)
    with TestClient(app) as client:
        yield client


def reviewed(client):
    response = client.post('/api/templates/demo')
    assert response.status_code == 201,response.text
    t = response.json()
    assert t['engine'] == 'pdf-native-text'
    assert any(r['text'] == 'Alex Example' for r in t['regions'])
    for r in t['regions']:
        r['confirmed'] = True
    response = client.put(f"/api/templates/{t['id']}/review",json={"regions":t['regions'],"privacy_confirmed":True,"revision":1})
    assert response.status_code == 200,response.text
    return response.json()


def test_100_document_end_to_end(client):
    """Real decoder, HTTP contracts, renderer, validation, all three exports."""
    t = reviewed(client)
    response = client.post('/api/jobs',json={"template_id":t['id'],"name":"100 fictional certificates","count":100,"seed":917})
    assert response.status_code == 201,response.text
    job = response.json(); id_ = job['id']
    client.app.state.worker.run(id_)
    final = client.get(f'/api/jobs/{id_}').json()
    assert final['status'] == 'completed',final
    assert final['completed'] == 100
    quality = client.get(f'/api/jobs/{id_}/quality').json()
    assert quality['accepted'] == 100 and quality['rejected'] == 0,quality
    assert not quality['training_ready']
    samples = client.get(f'/api/jobs/{id_}/samples?limit=100').json()
    assert len(set(s['sha256'] for s in samples)) == 100
    assert client.post(f'/api/jobs/{id_}/exports',json={"format":"yolo"}).status_code == 422
    for format_ in ['yolo','coco','ocr']:
        response = client.post(f'/api/jobs/{id_}/exports',json={"format":format_,"review_confirmed":True})
        assert response.status_code == 201,response.text
        assert response.json()['count'] == 100
        archive_bytes = client.get(response.json()['download_url']).content
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
            assert len([n for n in z.namelist() if n.startswith('images/')]) == 100
            assert 'dataset.json' in z.namelist()
            record = json.loads(z.read('metadata/000000.json'))
            assert all(a['mask'] in z.namelist() for a in record['annotations'])
            # Search all exported JSON/labels, not binary compressed image content.
            for name in z.namelist():
                if name.endswith(('.json','.txt')):
                    raw = z.read(name)
                    assert b'Alex Example' not in raw
                    assert b'alex@example.invalid' not in raw
            if format_ == 'yolo':
                for name in [n for n in z.namelist() if n.startswith('labels/')]:
                    for line in z.read(name).decode().splitlines():
                        cls,*coords = line.split()
                        assert len(coords) == 4 and all(0 <= float(v) <= 1 for v in coords)
            if format_ == 'coco':
                coco = json.loads(z.read('annotations.json'))
                assert len(coco['images']) == 100 and len(coco['annotations']) == 700
                assert all(sum(a['segmentation']['counts']) == 1350*960 for a in coco['annotations'])
                # Decode the exported COCO representation and compare actual mask pixels.
                for a,field in zip(coco['annotations'][:7],record['annotations']):
                    counts=a['segmentation']['counts']
                    decoded=np.repeat(np.arange(len(counts))%2,counts).reshape((960,1350),order='F')
                    mask=np.asarray(Image.open(io.BytesIO(z.read(field['mask']))))>0
                    assert np.array_equal(decoded,mask)
            if format_ == 'ocr':
                assert len(json.loads(z.read('ocr/000000.json'))['fields']) == 7
    # Re-running a committed job skips its samples instead of duplicating them.
    client.app.state.worker.run(id_)
    assert len(client.get(f'/api/jobs/{id_}/samples?limit=100').json()) == 100


def test_privacy_gates_and_version_conflicts(client):
    t = client.post('/api/templates/demo').json()
    assert client.post('/api/jobs',json={"template_id":t['id'],"count":1}).status_code == 422
    body={"regions":t['regions'],"privacy_confirmed":True,"revision":1}
    assert client.put(f"/api/templates/{t['id']}/review",json=body).status_code == 422
    for r in body['regions']:
        r['confirmed'] = True
    assert client.put(f"/api/templates/{t['id']}/review",json=body).status_code == 200
    assert client.put(f"/api/templates/{t['id']}/review",json=body).status_code == 409
    t = client.get(f"/api/templates/{t['id']}").json()
    t['regions'][0]['box'] = [1349,0,100,40]
    assert client.put(f"/api/templates/{t['id']}/review",json={"regions":t['regions'],"privacy_confirmed":False,"revision":2}).status_code == 422


def test_cancel_resume_and_queue_bound(client):
    t = reviewed(client)
    j = client.post('/api/jobs',json={"template_id":t['id'],"count":2}).json()
    assert client.post(f"/api/jobs/{j['id']}/cancel").json()['status'] == 'cancelled'
    assert client.post(f"/api/jobs/{j['id']}/resume").json()['status'] == 'queued'
    client.app.state.worker.run(j['id'])
    assert client.get(f"/api/jobs/{j['id']}").json()['completed'] == 2
    for _ in range(8):
        assert client.post('/api/jobs',json={"template_id":t['id'],"count":1}).status_code == 201
    assert client.post('/api/jobs',json={"template_id":t['id'],"count":1}).status_code == 429


def test_bad_upload_and_host_origin(client):
    assert client.post('/api/templates',files={'file':('bad.png',b'bad data','image/png')}).status_code == 422
    assert client.post('/api/templates',files={'file':('bad.txt',b'text','text/plain')}).status_code == 422
    assert client.post('/api/templates',files={'file':('empty.png',b'','image/png')}).status_code == 422
    assert client.get('/api/templates',headers={'Host':'attacker.example'}).status_code == 400
    assert client.post('/api/templates/demo',headers={'Origin':'https://attacker.example'}).status_code == 403


def test_single_page_limit():
    from reportlab.pdfgen import canvas
    b=io.BytesIO();c=canvas.Canvas(b);c.drawString(50,50,'First');c.showPage();c.drawString(50,50,'Second');c.save()
    with pytest.raises(ValueError,match='single-page'):
        decode(b.getvalue(),'.pdf')


def test_masks_rotation_reproducibility(tmp_path):
    image,detected=decode(certificate(),'.pdf');source=tmp_path/'source.png';image.save(source)
    from backend.app.demo import demo_regions
    regions=[Region.model_validate(r) for r in demo_regions(detected)]
    conf=GenerationConfig(template_id='test',count=1,rotation_probability=1,blur_probability=1,noise_sigma=2)
    a=render_sample(source,regions,conf,0,tmp_path/'a')
    b=render_sample(source,regions,conf,0,tmp_path/'b')
    assert a['sha256']==b['sha256']
    assert a['annotations']==b['annotations']
    assert validate(a,tmp_path/'a',7)['passed']
    for annotation in a['annotations']:
        assert annotation['provenance']=='procedural-mask'
        assert len(yolo_line(annotation,1350,960).split())==5


def test_values_and_bounds():
    regions=[Region(id='a',kind='name',box=(10,10,250,40)),Region(id='b',kind='name',box=(10,60,250,40)),Region(id='c',kind='email',box=(10,110,250,40))]
    values=fictional_values(regions,42)
    assert values['a']==values['b']
    assert values['c'].endswith('@example.invalid')
    with pytest.raises(ValueError):
        yolo_line({'bbox':[-2,10,40,20],'class_id':0},100,100)
    with pytest.raises(ValueError):
        check_review(regions,100,100,True)


def test_background_worker_async(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'async.db'}",tmp_path,start_worker=True)
    with TestClient(app) as client:
        t=reviewed(client)
        j=client.post('/api/jobs',json={'template_id':t['id'],'count':2}).json()
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            state=client.get(f"/api/jobs/{j['id']}").json()
            if state['status'] not in {'queued','running'}:
                break
            time.sleep(.1)
        assert state['status']=='completed',state


def test_checkpoint_resume_keeps_committed_samples(client,monkeypatch):
    import backend.app.jobs as job_module
    from backend.app.db import Job
    t=reviewed(client)
    j=client.post('/api/jobs',json={'template_id':t['id'],'count':3,'seed':718}).json()
    real_render=job_module.render_sample
    def interrupt_after_render(*args,**kwargs):
        result=real_render(*args,**kwargs)
        with client.app.state.sessions.begin() as db:
            db.get(Job,j['id']).status='cancelling'
        return result
    monkeypatch.setattr(job_module,'render_sample',interrupt_after_render)
    client.app.state.worker.run(j['id'])
    state=client.get(f"/api/jobs/{j['id']}").json()
    assert state['status']=='cancelled' and state['completed']==1
    first=client.get(f"/api/jobs/{j['id']}/samples").json()[0]
    monkeypatch.setattr(job_module,'render_sample',real_render)
    assert client.post(f"/api/jobs/{j['id']}/resume").status_code==200
    client.app.state.worker.run(j['id'])
    samples=client.get(f"/api/jobs/{j['id']}/samples").json()
    assert len(samples)==3 and samples[0]['sha256']==first['sha256'] and samples[0]['id']==first['id']
