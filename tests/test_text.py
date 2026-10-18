import csv
import io
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.db import Job, TextJob, TextSample
from backend.app.local_llm import LocalLLM, local_url
from backend.app.text_schemas import TextConfig
from backend.app.text_generation import plan_record, procedural, assemble, validate_record
from backend.app.text_exporting import CSV_JSON_FIELDS


@pytest.fixture
def client(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'text.db'}",tmp_path,False)
    with TestClient(app) as client: yield client


@pytest.mark.parametrize('task',['classification','ner','qa','instruction','conversation','augmentation'])
def test_all_tasks_multilingual_and_export_roundtrip(client,task):
    languages=['en','es','fr','de','hi']
    config={'task':task,'count':30,'seed':723,'languages':languages}
    if task=='augmentation':
        config['source_texts']=[{'text':f'{lang}: The fictional sample service team received this long request today.', 'language':lang,'label':'source-class'} for lang in languages]
    response=client.post('/api/text/jobs',json=config)
    assert response.status_code==201,response.text
    job=response.json();id_=job['id'];client.app.state.worker.run_text(id_)
    state=client.get(f'/api/text/jobs/{id_}').json()
    assert state['status']=='completed',state
    page=client.get(f'/api/text/jobs/{id_}/records?limit=100').json()
    rows=page['items'];assert page['total']==30 and len(rows)==30
    assert set(r['language'] for r in rows)==set(languages)
    assert all(r['validation']['passed'] and not r['validation']['training_ready'] for r in rows)
    if task=='ner':
        for row in rows:
            for e in row['entities']: assert row['text'][e['start']:e['end']]==e['text']
            assert sum(t['tag'].startswith('B-') for t in row['tokens'])==3
    if task=='qa':
        assert all(r['context'][r['answer_start']:r['answer_start']+len(r['answer'])]==r['answer'] for r in rows)
    if task=='classification':
        counts=client.get(f'/api/text/jobs/{id_}/quality').json()['labels']
        assert counts=={'positive':10,'negative':10,'neutral':10}
        for language in languages:
            assert {r['label'] for r in rows if r['language']==language}==set(counts)
    if task=='augmentation': assert all(r['label']=='source-class' for r in rows)
    assert client.post(f'/api/text/jobs/{id_}/exports',json={'format':'jsonl'}).status_code==422
    for format_ in ['csv','json','jsonl']:
        response=client.post(f'/api/text/jobs/{id_}/exports',json={'format':format_,'review_confirmed':True})
        assert response.status_code==201,response.text
        raw=client.get(response.json()['download_url']).content.decode('utf-8')
        if format_=='json': assert json.loads(raw)==rows
        elif format_=='jsonl': assert [json.loads(line) for line in raw.splitlines()]==rows
        else:
            csv_rows=list(csv.DictReader(io.StringIO(raw)));assert len(csv_rows)==30
            for before,after in zip(rows,csv_rows):
                for key in CSV_JSON_FIELDS:
                    assert json.loads(after[key])==before.get(key)
    manifest=client.get(f'/api/text/jobs/{id_}/manifest').json()
    assert 'source_texts' not in manifest['config']
    assert not manifest['training_ready']
    assert client.get(f'/api/text/jobs/{id_}/records?offset=28&limit=10').json()['items']==rows[28:]


def test_count_constraints_and_invalid_configs(client):
    for body in [{'count':0},{'count':2001},{'languages':[]},{'languages':['xx']},{'languages':['en','en']},
                 {'task':'augmentation'},{'task':'augmentation','languages':['hi'],'source_texts':[{'text':'A fictional source.','language':'en'}]},
                 {'labels':['custom-a','custom-b']},{'instructions':'not supported by procedural'}, {'unknown':True}]:
        assert client.post('/api/text/jobs',json=body).status_code==422,body
    body={'count':3,'languages':['en'],'labels':['finance','sports'],
          'class_templates':{'finance':{'en':'The fictional budget increased.'},'sports':{'en':'The fictional team won.'}}}
    assert client.post('/api/text/jobs',json=body).status_code==201


def test_synthetic_100_records_and_determinism(client):
    configs={'task':'ner','languages':['en','hi'],'count':100,'seed':515}
    results=[]
    for _ in range(2):
        j=client.post('/api/text/jobs',json=configs).json();client.app.state.worker.run_text(j['id'])
        rows=client.get(f"/api/text/jobs/{j['id']}/records?limit=100").json()['items']
        assert len(rows)==100 and all(r['validation']['passed'] for r in rows)
        results.append(rows)
    assert results[0]==results[1]


def test_validation_rejects_bad_spans_roles_and_privacy():
    c=TextConfig(task='ner',languages=['hi']);p=plan_record(c,0)
    row=assemble(c,p,procedural(c,p,11),11)
    row['entities'][0]['end']+=1
    assert not validate_record(row,c)['passed']
    c=TextConfig(task='conversation');p=plan_record(c,0)
    row=assemble(c,p,{'messages':[{'role':'assistant','content':'Hi'},{'role':'user','content':'Hello'}]},11)
    assert 'invalid_conversation_roles' in validate_record(row,c)['errors']
    c=TextConfig(task='classification');p=plan_record(c,0)
    row=assemble(c,p,{'text':'Contact fictional-user@private-company.net'},11)
    assert 'suspected_sensitive_pattern' in validate_record(row,c)['errors']
    with pytest.raises(ValueError): assemble(TextConfig(task='qa'),{'index':0,'language':'en'}, {'context':'A fictional fact.','question':'What?','answer':'missing'},11)


def test_duplicate_rejection_and_export_excludes_rejected(client):
    body={'task':'augmentation','count':8,'augmentations':['punctuation'],'source_texts':[{'text':'A fictional source.','language':'en'}]}
    job=client.post('/api/text/jobs',json=body).json();id_=job['id'];client.app.state.worker.run_text(id_)
    quality=client.get(f'/api/text/jobs/{id_}/quality').json()
    assert 0<quality['accepted']<8 and quality['rejected']>0
    export=client.post(f'/api/text/jobs/{id_}/exports',json={'format':'json','review_confirmed':True}).json()
    rows=client.get(export['download_url']).json()
    assert len(rows)==quality['accepted'] and all(r['validation']['passed'] for r in rows)


def test_csv_formula_safety_and_unicode_offsets(client):
    body={'count':1,'labels':['formula','normal'],'class_templates':{'formula':{'en':'=SUM(1,2) 😀 fictional'},'normal':{'en':'A normal fictional example'}}}
    j=client.post('/api/text/jobs',json=body).json();client.app.state.worker.run_text(j['id'])
    exported=client.post(f"/api/text/jobs/{j['id']}/exports",json={'format':'csv','review_confirmed':True}).json()
    row=next(csv.DictReader(io.StringIO(client.get(exported['download_url']).text)))
    assert row['text'].startswith('"') and json.loads(row['text']).startswith('=SUM(1,2) 😀')


def test_cancel_checkpoint_resume_and_shared_queue(client,monkeypatch):
    import backend.app.text_jobs as module
    job=client.post('/api/text/jobs',json={'count':6,'batch_size':2}).json();id_=job['id']
    real=module.assemble
    def cancel_during_second_batch(*args,**kwargs):
        result=real(*args,**kwargs)
        if result['index']==2:
            with client.app.state.sessions.begin() as db: db.get(TextJob,id_).status='cancelling'
        return result
    monkeypatch.setattr(module,'assemble',cancel_during_second_batch)
    client.app.state.worker.run_text(id_)
    state=client.get(f'/api/text/jobs/{id_}').json()
    assert state['status']=='cancelled' and state['completed']==2
    first=client.get(f'/api/text/jobs/{id_}/records').json()['items']
    monkeypatch.setattr(module,'assemble',real)
    assert client.post(f'/api/text/jobs/{id_}/resume').status_code==200
    client.app.state.worker.run_text(id_)
    assert client.get(f'/api/text/jobs/{id_}/records').json()['items'][:2]==first
    for _ in range(8): assert client.post('/api/text/jobs',json={'count':1}).status_code==201
    assert client.post('/api/text/jobs',json={'count':1}).status_code==429
    # Existing document endpoint sees the same bounded queue.
    assert client.post('/api/jobs',json={'template_id':'unused','count':1}).status_code==429


def test_llm_loopback_schema_and_no_remote_fallback(client,monkeypatch):
    for url in ['https://api.example.com','http://192.168.1.1:11434','http://127.0.0.1/api','http://user@127.0.0.1','http://127.0.0.1?x=1']:
        with pytest.raises(ValueError): local_url(url)
    seen=[]
    def handler(request):
        seen.append(request)
        if request.url.path=='/api/tags': return httpx.Response(200,json={'models':[{'name':'qwen3:1.7b','details':{'format':'gguf'}}]})
        body=json.loads(request.content)
        assert body['format']['properties']['records']['minItems']==2
        assert body['stream'] is False and body['think'] is False and body['keep_alive']==0
        assert body['options']['num_gpu']==0 and body['options']['num_ctx']==8192
        return httpx.Response(200,json={'message':{'content':json.dumps({'records':[{'text':'Fictional excellent service A.'},{'text':'Fictional poor service B.'}]})}})
    llm=LocalLLM(transport=httpx.MockTransport(handler))
    assert llm.status()['installed']
    c=TextConfig(backend='ollama',count=2)
    assert len(llm.generate(c,[plan_record(c,0),plan_record(c,1)],42))==2
    llm.close();assert all(r.url.host=='127.0.0.1' for r in seen)
    monkeypatch.setattr(LocalLLM,'status',lambda self:{'installed':False,'reachable':False})
    assert client.post('/api/text/jobs',json={'backend':'ollama','count':1}).status_code==503


def test_bad_model_schema_has_bounded_retries(client,monkeypatch):
    from backend.app.config import settings
    monkeypatch.setattr(settings,'llm_min_available_mb',0)
    monkeypatch.setattr(LocalLLM,'resident_cpu_mb',lambda self:0)
    calls=[]
    monkeypatch.setattr(LocalLLM,'status',lambda self:{'installed':True})
    def bad(*args):calls.append(1);raise ValueError('bad schema')
    monkeypatch.setattr(LocalLLM,'generate',bad)
    j=client.post('/api/text/jobs',json={'backend':'ollama','count':2,'batch_size':2,'max_retries':1}).json()
    client.app.state.worker.run_text(j['id'])
    assert len(calls)==2
    quality=client.get(f"/api/text/jobs/{j['id']}/quality").json()
    assert quality['accepted']==0 and quality['rejected']==2
    assert client.post(f"/api/text/jobs/{j['id']}/exports",json={'format':'json','review_confirmed':True}).status_code==422


def test_revalidation_and_export_block_modified_records(client):
    j=client.post('/api/text/jobs',json={'task':'ner','count':2}).json();id_=j['id']
    client.app.state.worker.run_text(id_)
    with client.app.state.sessions() as db:
        record=db.query(TextSample).filter(TextSample.job_id==id_).first()
        path=Path(record.path)
    body=json.loads(path.read_text(encoding='utf-8'));body['entities'][0]['end']+=1
    path.write_text(json.dumps(body,ensure_ascii=False),encoding='utf-8')
    assert client.post(f'/api/text/jobs/{id_}/exports',json={'format':'jsonl','review_confirmed':True}).status_code==409
    quality=client.post(f'/api/text/jobs/{id_}/validate').json()
    assert quality['rejected']==1 and quality['accepted']==1
    assert 'record_integrity_changed' in quality['errors']
    assert not client.get(f'/api/text/jobs/{id_}/records').json()['items'][0]['validation']['passed']
    exported=client.post(f'/api/text/jobs/{id_}/exports',json={'format':'json','review_confirmed':True}).json()
    assert len(client.get(exported['download_url']).json())==1


def test_memory_admission_pauses_without_committing(client,monkeypatch):
    from types import SimpleNamespace
    import backend.app.text_jobs as module
    monkeypatch.setattr(module.psutil,'virtual_memory',lambda:SimpleNamespace(available=512*1024**2))
    j=client.post('/api/text/jobs',json={'count':2}).json();client.app.state.worker.run_text(j['id'])
    state=client.get(f"/api/text/jobs/{j['id']}").json()
    assert state['status']=='paused' and state['completed']==0


def test_shared_worker_dispatches_text_and_recovers_cancelling(tmp_path):
    import time
    url=f"sqlite:///{tmp_path/'async-text.db'}"
    initial=create_app(url,tmp_path,False)
    with TestClient(initial) as client:
        cancelled=client.post('/api/text/jobs',json={'count':1}).json()
        with initial.state.sessions.begin() as db: db.get(TextJob,cancelled['id']).status='cancelling'
    app=create_app(url,tmp_path,True)
    with TestClient(app) as client:
        assert client.get(f"/api/text/jobs/{cancelled['id']}").json()['status']=='paused'
        j=client.post('/api/text/jobs',json={'task':'qa','count':3}).json()
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            state=client.get(f"/api/text/jobs/{j['id']}").json()
            if state['status'] not in {'queued','running'}:break
            time.sleep(.1)
        assert state['status']=='completed',state


def test_custom_qa_answer_bank_and_marker_boundary():
    config=TextConfig(task='qa',languages=['en','hi'],qa_answer_bank={'en':['Fictional Gold Plan'],'hi':['काल्पनिक गोल्ड योजना']},qa_answer_hint='fictional service tier')
    for index in range(2):
        plan=plan_record(config,index)
        row=assemble(config,plan,procedural(config,plan,42),42)
        assert row['answer'] in config.qa_answer_bank[row['language']]
        assert validate_record(row,config)['passed']
    config=TextConfig(task='ner');plan=plan_record(config,0)
    row=assemble(config,plan,{'template':'prefix[[PERSON]] at [[ORG]] in [[LOCATION]].'},42)
    assert 'entity_token_boundary' in validate_record(row,config)['errors']
