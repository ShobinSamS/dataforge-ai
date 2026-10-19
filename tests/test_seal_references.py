"""Seal6/seal8 layout regressions, using generated ink and supplied wording."""
import json
import random
import warnings
from pathlib import Path
import numpy as np
import pytest
from PIL import Image,ImageOps
from backend.app.schemas import RuleOptions,Region,GenerationConfig
from backend.app.seals import plan_seal_content,render_seal,seal_text
from backend.app.render import render_sample
from backend.app.fonts import resolve_font_weight
from scripts.preview_seal_references import reference_font_fingerprint

FIXTURES=Path(__file__).parent/'fixtures'
CASES=json.loads((FIXTURES/'seal-reference-cases.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case',CASES,ids=[case['id'] for case in CASES])
def test_reference_seal_geometry_wording_and_transparency(case):
    options=RuleOptions(font_id=resolve_font_weight('auto','normal'),ink_opacity_mode='fixed',ink_opacity=1,ink_finish='clean',**case['options'])
    content=plan_seal_content(options,case['seed'])
    layer,mask,info=render_seal(tuple(case['size']),content,random.Random(case['seed']),options)
    same,_,same_info=render_seal(tuple(case['size']),content,random.Random(case['seed']),options)
    assert layer.tobytes()==same.tobytes() and info==same_info
    assert layer.mode=='RGBA' and layer.getpixel((0,0))[3]==0
    assert np.array_equal(np.asarray(mask)>0,np.asarray(layer.getchannel('A'))>0)
    assert all(text in info['text'] for text in seal_text(content).splitlines())
    thumbnail=np.asarray(ImageOps.pad(mask,(220,220),method=Image.Resampling.BOX,color=0))>=128
    i=CASES.index(case);x,y=i%3*220,i//3*220
    with Image.open(FIXTURES/'seal-reference-geometry.png') as baseline:
        fingerprint=baseline.info['font_fingerprint']
        expected=np.asarray(baseline.crop((x,y,x+220,y+220)))>0
    if fingerprint==reference_font_fingerprint():
        assert np.count_nonzero(thumbnail & expected)/np.count_nonzero(thumbnail | expected)>.97
    else:
        warnings.warn('Installed fonts differ from the reviewed seal baseline; checking wording, bounds and transparency without pixel matching.',stacklevel=1)
    for text in info.get('text_boxes',[]):
        x,y,w,h=text['bbox']
        assert x>0 and y>0 and x+w<layer.width and y+h<layer.height
        assert text['font_size']>=6
    if info['shape']=='nameplate':assert not info['fields']


def test_attestation_fields_hierarchy_and_embedded_signature_are_explicit():
    case=CASES[0];options=RuleOptions(font_id=resolve_font_weight('auto','normal'),**case['options'])
    _,_,info=render_seal(tuple(case['size']),plan_seal_content(options,42),random.Random(42),options)
    assert [(f['label'],f['value'],f['writing']) for f in info['fields']]==[
        ('Dated','18-07-2014','cursive'),('C.No.','01404/NRI/2014','cursive')]
    signature=info['embedded_signature']
    assert signature['text']=='N V Ramana Reddy' and signature['text'] in info['text']
    assert signature['opacity']==1  # The composite gets opacity once at the end.
    boxes=info['text_boxes']
    heading=next(row for row in boxes if row['role']=='heading')
    body=next(row for row in boxes if row['role']=='body')
    assert heading['font_size']>body['font_size']


def test_direct_asset_call_can_embed_signature_without_a_content_planner():
    content={'top':'CEDAR OFFICE','lines':['RECORDS UNIT'],'bottom':'RIVERTON','mode':'static'}
    options=RuleOptions(seal_style='attestation',seal_embedded_signature=True)
    _,_,info=render_seal((400,300),content,random.Random(42),options)
    assert info['embedded_signature']['text']=='Alex Example'


def test_inner_arcs_resolve_templates_validate_repeats_and_never_drop_text():
    options=RuleOptions(seal_style='corporate',seal_text_mode='custom',seal_body_format='{name}',seal_inner_top_text='INCORPORATED {year}',seal_inner_bottom_text='REGISTER {reference}')
    content=plan_seal_content(options,42)
    assert '{' not in seal_text(content) and 'REGISTER 0000002A' in seal_text(content)
    _,_,info=render_seal((460,460),content,random.Random(42),options)
    assert content['inner_top'] in info['text'] and content['inner_bottom'] in info['text']
    with pytest.raises(ValueError,match='Repeated seal words'):
        RuleOptions(seal_text_mode='static',seal_text='CEDAR LAB',seal_inner_top_text='CEDAR')
    with pytest.raises(ValueError):RuleOptions(seal_inner_top_text='{name.__class__}')
    invalid=options.model_copy(update={'seal_inner_top_text':'ONE\nTWO'})
    with pytest.raises(ValueError,match='single lines'):plan_seal_content(invalid,42)
    # Changing the shape must not leave invisible text in its annotation.
    for shape in ('rectangle','attestation'):
        changed=options.model_copy(update={'seal_style':shape})
        _,_,info=render_seal((600,400),plan_seal_content(changed,42),random.Random(42),changed)
        assert content['inner_top'] in info['text']


def test_monogram_repetition_check_includes_inner_arc_words():
    options=RuleOptions(seal_style='corporate',seal_text_mode='static',seal_text='CEDAR OFFICE',seal_subtext='',
                        seal_inner_top_text='CO',seal_symbol='monogram')
    with pytest.raises(ValueError,match='Monogram repeats'):
        render_seal((400,400),plan_seal_content(options,42),random.Random(42),options)


def test_new_layout_job_records_fields_and_combined_signature_mask(tmp_path):
    source=tmp_path/'source.png';Image.new('RGB',(600,550),'#d9e7df').save(source)
    region=Region(id='stamp',kind='seal',box=[30,30,500,450],confirmed=True,rule_options=CASES[0]['options'])
    config=GenerationConfig(template_id='fixture',blur_probability=0,rotation_probability=0)
    result=render_sample(source,[region],config,0,tmp_path/'out')
    annotation=result['annotations'][0]
    assert annotation['class']=='seal' and annotation['text']==annotation['seal']['text']
    assert len(annotation['seal']['fields'])==2 and 'embedded_signature' in annotation['seal']
    assert result['image'].getpixel((31,31))==(217,231,223)


def test_random_shape_selection_includes_new_layouts():
    for size,expected in [((500,200),{'form_block','nameplate'}),((400,400),{'corporate','attestation'})]:
        seen=set()
        for seed in range(40):
            options=RuleOptions()
            _,_,info=render_seal(size,plan_seal_content(options,seed),random.Random(seed),options)
            seen.add(info['shape'])
        assert expected<=seen


def test_reference_layout_preview_validates_new_options_without_creating_jobs(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    app=create_app(f"sqlite:///{tmp_path/'preview.db'}",tmp_path,start_worker=False)
    with TestClient(app) as client:
        response=client.post('/api/seals/preview',json={'width':500,'height':450,'options':CASES[0]['options']})
        assert response.status_code==200,response.text
        metadata=response.json()['metadata']
        assert metadata['layout']=='attestation' and len(metadata['fields'])==2
        assert metadata['embedded_signature']['text']=='N V Ramana Reddy'
        assert client.post('/api/seals/preview',json={'options':{'seal_signer_name':'1234'}}).status_code==422
        assert client.post('/api/seals/preview',json={'options':{'seal_inner_top_text':'{unknown}'}}).status_code==422
        assert client.get('/api/jobs').json()==[]
