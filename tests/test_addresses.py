import io
import json
import re
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.addresses import COUNTRIES,DEFAULT_FORMAT,generate_address,reference
from backend.app.document_rules import known_plan,apply_plan,interpret_local
from backend.app.main import create_app
from backend.app.render import fictional_values
from backend.app.schemas import Region,RuleOptions


@pytest.mark.parametrize('country',COUNTRIES)
def test_country_components_are_seeded_and_match_one_reference_row(country):
    options=RuleOptions(address_country=country,address_format='{street}\n{city}\n{state}\n{country}\n{postal_code}')
    a=generate_address(options,42);b=generate_address(options,42)
    assert a==b and a['text'].splitlines()[3]==COUNTRIES[country]
    row={key:a['components'][key] for key in ('city','state','state_code','postal_code')}
    assert row in reference()[0]['countries'][country]['records']
    assert a['synthetic_street'] and not a['deliverability_verified'] and a['license']=='CC BY 4.0'
    assert len({generate_address(options,seed)['text'] for seed in range(30)})==30
    postal=row['postal_code']
    if country=='IN':assert re.fullmatch(r'[1-9]\d{5}',postal)
    if country=='US':assert re.fullmatch(r'\d{5}',postal)
    if country=='CA':assert re.fullmatch(r'[A-Z]\d[A-Z] \d[A-Z]\d',postal)
    if country=='GB':assert re.fullmatch(r'[A-Z0-9]+ \d[A-Z]{2}',postal)


@pytest.mark.parametrize('rule,country,format_',[
    ('Generate a synthetic Indian address containing street, city, state, country and PIN code. Put each component on a separate line.','IN','{street}\n{city}\n{state}\n{country}\n{postal_code}'),
    ('Generate address from country India','IN',DEFAULT_FORMAT),
    ('Generate address from India on five lines with street, city, state, country and PIN code','IN','{street}\n{city}\n{state}\n{country}\n{postal_code}'),
    ('US address with street, city, state, ZIP code and country on one line','US','{street}, {city}, {state}, {postal_code}, {country}'),
    ('Generate an address in United Kingdom containing city, country','GB','{city}, {country}'),
    ('Generate address in Germany using format: Address: {street}\n{postal_code} {city}\n{country}','DE','Address: {street}\n{postal_code} {city}\n{country}'),
    ('put street, city, state, country, pin code on separate lines','IN','{street}\n{city}\n{state}\n{country}\n{postal_code}'),
    ('INDIAN ADDRESS WITH STREET CITY STATE COUNTRY PINCODE','IN',DEFAULT_FORMAT),
    ('Put country, city, state, street, PIN code in that order on five lines','IN','{country}\n{city}\n{state}\n{street}\n{postal_code}'),
    ('Generate an Indian address containing country, city, state, street, PIN code in that order','IN','{country}, {city}, {state}, {street}, {postal_code}'),
])
def test_common_prompts_keep_country_components_order_and_lines(rule,country,format_):
    r=Region(id='address',kind='address',box=[10,10,600,200],rule=rule,rule_options={'address_country':'IN'})
    plan=known_plan(r)
    assert plan is not None
    assert plan.options.address_country==country and plan.options.address_format==format_
    result=apply_plan(r,plan)
    assert result.kind=='address' and result.rule_options.literal_text is None
    assert fictional_values([result],42)['address']!=fictional_values([result],43)['address']


def test_address_validation_and_legacy_behavior():
    for country in ('Japan','ZZ'):
        with pytest.raises(ValueError):RuleOptions(address_country=country)
    for format_ in ('plain text','{city.__class__}','{city!r}','{postal_code:06d}','{street'):
        with pytest.raises(ValueError):RuleOptions(address_format=format_)
    assert RuleOptions(address_country='India').address_country=='IN'
    legacy=Region(id='a',kind='address',box=[0,0,500,100])
    assert 'Fictional Lane, Test City, ZZ 00000' in fictional_values([legacy],42)['a']
    with pytest.raises(ValueError):known_plan(legacy.model_copy(update={'rule':'Generate a Japanese address'}))
    with pytest.raises(ValueError):known_plan(legacy.model_copy(update={'rule':'Generate address from Japan'}))
    same=[Region(id='a',kind='address',box=[0,0,100,100],rule_options={'address_country':'IN','address_format':'{city}'}),
          Region(id='b',kind='address',box=[0,100,100,100],rule_options={'address_country':'IN','address_format':'{state}'})]
    values=fictional_values(same,12);parts=generate_address(same[0].rule_options,12)['components']
    assert values=={'a':parts['city'],'b':parts['state']}


def test_qwen_address_schema_does_not_treat_postal_code_as_identifier(monkeypatch):
    from backend.app import document_rules
    sent=[]
    rule='Indian address with street, city, state, country, PIN code on separate lines'
    r=Region(id='a',kind='address',box=[0,0,600,200],rule=rule)
    expected=known_plan(r)
    class MockLLM:
        def __init__(self):self.client=self
        def status(self):return {'installed':True}
        def close(self):pass
        def post(self,path,json):
            sent.append(json)
            return httpx.Response(200,request=httpx.Request('POST','http://127.0.0.1:11434/api/chat'),json={'message':{'content':expected.model_dump_json()}})
    monkeypatch.setattr(document_rules,'LocalLLM',MockLLM)
    plan=interpret_local(r)
    props=sent[0]['format']['$defs']['RuleOptions']['properties']
    assert set(props)=={'address_country','address_format'}
    assert sent[0]['format']['properties']['kind']['const']=='address'
    assert plan.options.address_format=='{street}\n{city}\n{state}\n{country}\n{postal_code}'


def test_address_preview_jobs_export_and_literal_override(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)) as client:
        countries=client.get('/api/addresses/countries').json();assert {r['code'] for r in countries}==set(COUNTRIES)
        options={'address_country':'IN','address_format':'{street}\n{city}, {state}\n{country} {postal_code}'}
        preview=client.post('/api/addresses/preview',json={'options':options,'seed':42})
        assert preview.status_code==200 and preview.json()['country_code']=='IN'
        asset=client.post('/api/assets/generate',json={'kind':'address','width':640,'height':220,'options':options}).json()
        assert asset['metadata']['value']==preview.json()['text']
        assert asset['metadata']['details']['components']==preview.json()['components']
        t=client.post('/api/templates/blank',json={'paper':'custom','unit':'px','width':800,'height':500,'orientation':'landscape'}).json()
        region={'id':'a','kind':'address','box':[40,100,700,240],'confirmed':True,'rule_options':options}
        review=client.put(f"/api/templates/{t['id']}/review",json={'regions':[region],'revision':1,'privacy_confirmed':True})
        assert review.status_code==200,review.text
        j=client.post('/api/jobs',json={'template_id':t['id'],'count':3,'blur_probability':0,'rotation_probability':0}).json()
        client.app.state.worker.run(j['id'])
        assert client.get(f"/api/jobs/{j['id']}/quality").json()['accepted']==3
        export=client.post(f"/api/jobs/{j['id']}/exports",json={'format':'ocr','review_confirmed':True}).json()
        with zipfile.ZipFile(io.BytesIO(client.get(export['download_url']).content)) as z:
            rows=[json.loads(z.read(f'metadata/{i:06d}.json'))['annotations'][0] for i in range(3)]
            assert len({r['text'] for r in rows})==3
            assert all(r['address']['country_code']=='IN' and r['address']['license']=='CC BY 4.0' for r in rows)
        literal=Region(id='x',kind='address',box=[0,0,100,100],rule_options={**options,'literal_text':'My exact text'})
        assert fictional_values([literal],42)['x']=='My exact text'
