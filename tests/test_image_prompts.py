import json
import threading

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import image_prompts, diffusion
from backend.app.config import settings
from backend.app.local_llm import LocalLLM
from backend.app.main import create_app
from backend.app.resources import CPU_LOCK


def install_mock(monkeypatch,outputs,installed=True):
    calls=[]
    def handle(request):
        payload=json.loads(request.content) if request.content else None
        calls.append((request.url.path,payload))
        if request.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':settings.ollama_model,'digest':'tested-digest','details':{'format':'gguf'}}] if installed else []})
        if request.url.path=='/api/chat':
            value=outputs.pop(0)
            return httpx.Response(200,json={'message':{'content':value if isinstance(value,str) else json.dumps(value)},'done_reason':'stop'})
        if request.url.path=='/api/generate':return httpx.Response(200,json={'done':True})
        if request.url.path=='/api/ps':return httpx.Response(200,json={'models':[]})
        raise AssertionError(request.url.path)
    monkeypatch.setattr(image_prompts,'LocalLLM',lambda:LocalLLM(transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(image_prompts.psutil,'virtual_memory',lambda:type('Memory',(),{'available':8*1024**3})())
    return calls


def test_local_qwen_schema_constraints_seed_and_memory_release(monkeypatch):
    prompt='A South Asian woman with short dark hair and a navy blazer, neutral expression, natural adult portrait.'
    calls=install_mock(monkeypatch,[{'prompt':prompt}])
    with CPU_LOCK:result=image_prompts.generate_prompt('portrait','South Asian woman, short dark hair',900)
    assert result['generated_prompt']==prompt and result['prompt_seed']==900
    assert result['prompt_engine']=='local_qwen' and result['prompt_model_digest']=='tested-digest'
    request=next(payload for path,payload in calls if path=='/api/chat')
    assert request['options']['seed']==900 and request['options']['num_gpu']==0
    assert request['keep_alive']==0 and request['think'] is False
    assert request['format']['properties']['prompt']['maxLength']==240
    context=json.loads(request['messages'][1]['content'])
    assert context['user_brief']=='South Asian woman, short dark hair'
    assert not {'gender','appearance','hair'} & set(context['optional_diversity_hints'])
    assert 'MUST NOT override' in request['messages'][0]['content']
    assert [path for path,_ in calls][-2:]==['/api/generate','/api/ps']


def test_duplicate_prompt_is_retried_and_unavailable_qwen_has_no_fallback(monkeypatch):
    old='A fictional older man with curly gray hair wearing a burgundy shirt and a relaxed expression.'
    new='A fictional young woman with tied-back black hair wearing a cream sweater and a subtle smile.'
    calls=install_mock(monkeypatch,[{'prompt':old},{'prompt':new}])
    result=image_prompts.generate_prompt('portrait','Varied fictional adults',11,[old])
    assert result['generated_prompt']==new
    assert len([p for p,_ in calls if p=='/api/chat'])==2
    calls=install_mock(monkeypatch,[],installed=False)
    with pytest.raises(ValueError,match='No prompt fallback'):image_prompts.generate_prompt('portrait','A fictional adult',1)
    assert all(path!='/api/chat' for path,_ in calls)


def test_invalid_and_cancelled_prompt_requests_never_produce_a_description(monkeypatch):
    install_mock(monkeypatch,['not JSON',{'prompt':'Too short'}])
    with pytest.raises(ValueError,match='valid varied'):image_prompts.generate_prompt('portrait','A fictional adult',1)
    cancelled=threading.Event();cancelled.set()
    with pytest.raises(InterruptedError):image_prompts.generate_prompt('portrait','A fictional adult',1,cancelled=cancelled)


def test_portrait_group_description_is_retried_as_one_person(monkeypatch):
    prompt='One fictional adult woman with wavy dark hair, navy collared shirt and relaxed expression, realistic head and shoulders portrait.'
    calls=install_mock(monkeypatch,[{'prompt':'A diverse group of anonymous fictional adults in their twenties, wearing navy collared shirts, realistic portraits.'},{'prompt':prompt}])
    result=image_prompts.generate_prompt('portrait','Varied fictional adults',12)
    assert result['generated_prompt']==prompt
    requests=[payload for path,payload in calls if path=='/api/chat']
    assert len(requests)==2
    assert 'exactly one adult person' in requests[1]['messages'][-1]['content']


def test_prompt_preview_is_local_and_does_not_generate_an_image(tmp_path,monkeypatch):
    install_mock(monkeypatch,[{'prompt':'A fictional adult woman with curly hair, green blouse and warm natural expression, realistic portrait.'}])
    with TestClient(create_app(f"sqlite:///{tmp_path/'preview.db'}",tmp_path,start_worker=False)) as client:
        result=client.post('/api/diffusion/prompts/preview',json={'prompt':'Varied fictional adults','kind':'portrait','prompt_seed':77})
        assert result.status_code==200,result.text
        assert result.json()['prompt_seed']==77 and result.json()['prompt_engine']=='local_qwen'
        assert client.get('/api/diffusion/jobs').json()==[]
        assert client.get('/api/diffusion/capabilities').json()['prompt_llm']['installed']
        assert CPU_LOCK.acquire(timeout=1)
        try:assert client.post('/api/diffusion/prompts/preview',json={'prompt':'A fictional adult'}).status_code==409
        finally:CPU_LOCK.release()


def test_batch_uses_distinct_qwen_prompts_and_caches_them_on_resume(tmp_path,monkeypatch):
    import time
    model=tmp_path/'models'/'sd-turbo';model.mkdir(parents=True)
    (model/'manifest.json').write_text(json.dumps({'repository':'stabilityai/sd-turbo','revision':'test'}))
    monkeypatch.setattr(diffusion,'capabilities',lambda root:{'ready':True,'model_url':'https://huggingface.co/stabilityai/sd-turbo'})
    monkeypatch.setattr(diffusion.psutil,'virtual_memory',lambda:type('Memory',(),{'available':8*1024**3})())
    prompt_calls=[];worker_calls=[];fail=True
    def plan(kind,brief,seed,previous,cancel):
        prompt_calls.append((seed,list(previous)))
        return {'generated_prompt':f'Fictional adult portrait variant {seed}, wavy hair, neutral expression and a blue shirt.',
                'prompt_seed':seed,'prompt_engine':'local_qwen','prompt_model':'qwen3:1.7b','prompt_model_digest':'test-digest'}
    def worker(folder,model,request,cancel,progress):
        worker_calls.append(request)
        assert request['generated_prompt'] in request['resolved_prompt']
        assert request['prompt_mode']=='qwen'
        assert json.loads((folder/'request.json').read_text())['resolved_prompt']==request['resolved_prompt']
        if fail and request['seed']==42:raise ValueError('Test image failure after prompt planning')
        Image.new('RGB',(512,512),'gray').save(folder/'raw.png')
        return {'elapsed_seconds':.1,'peak_worker_rss_mb':100}
    monkeypatch.setattr(diffusion,'generate_prompt',plan);monkeypatch.setattr(diffusion,'run_worker',worker)
    def wait(client,id_):
        for _ in range(200):
            job=client.get(f'/api/diffusion/jobs/{id_}').json()
            if job['status'] in diffusion.TERMINAL:return job
            time.sleep(.01)
        raise AssertionError('Job did not finish')
    with TestClient(create_app(f"sqlite:///{tmp_path/'jobs.db'}",tmp_path,start_worker=False)) as client:
        job=client.post('/api/diffusion/jobs',json={'prompt':'Varied fictional adults','prompt_mode':'qwen','prompt_seed':500,'count':2}).json()
        assert wait(client,job['id'])['status']=='failed'
        fail=False
        assert client.post(f"/api/diffusion/jobs/{job['id']}/resume").status_code==200
        result=wait(client,job['id'])
        assert result['completed']==2 and [seed for seed,_ in prompt_calls]==[500,501]
        assert prompt_calls[1][1]==[result['items'][0]['generated_prompt']]
        assets=client.post(f"/api/diffusion/jobs/{job['id']}/save").json()['assets']
        for item,asset in zip(result['items'],assets):
            provenance=json.loads(asset['attribution'])
            assert provenance['generated_prompt']==item['generated_prompt']
            assert provenance['prompt_model_digest']=='test-digest'
        assert [call['seed'] for call in worker_calls]==[42,42,43]


def test_new_runs_get_new_prompt_variation_seeds_and_missing_qwen_does_not_render(tmp_path,monkeypatch):
    import time
    model=tmp_path/'models'/'sd-turbo';model.mkdir(parents=True)
    (model/'manifest.json').write_text(json.dumps({'repository':'stabilityai/sd-turbo','revision':'test'}))
    monkeypatch.setattr(diffusion,'capabilities',lambda root:{'ready':True})
    seeds=iter([1000,2000]);monkeypatch.setattr(diffusion.secrets,'randbelow',lambda n:next(seeds))
    monkeypatch.setattr(diffusion.psutil,'virtual_memory',lambda:type('Memory',(),{'available':8*1024**3})())
    def unavailable(*args):raise ValueError('Local Qwen unavailable; no fallback')
    monkeypatch.setattr(diffusion,'generate_prompt',unavailable)
    def should_not_render(*args):raise AssertionError('Image generation must not run without a Qwen prompt')
    monkeypatch.setattr(diffusion,'run_worker',should_not_render)
    with TestClient(create_app(f"sqlite:///{tmp_path/'seed.db'}",tmp_path,start_worker=False)) as client:
        rows=[client.post('/api/diffusion/jobs',json={'prompt':'Varied fictional adults','prompt_mode':'qwen'}).json() for _ in range(2)]
        assert [j['prompt_seed'] for j in rows]==[1000,2000]
        for job in rows:
            for _ in range(100):
                row=client.get(f"/api/diffusion/jobs/{job['id']}").json()
                if row['status']=='failed':break
                time.sleep(.01)
            assert row['status']=='failed' and 'Local Qwen unavailable' in row['error']
