import base64
import io
import random
import pytest
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.schemas import RuleOptions,Region,GenerationConfig
from backend.app.seals import SHAPES,plan_seal_content,render_seal,seal_text,duplicate_words
from backend.app.render import fictional_values,render_sample
from backend.app.jobs import snapshot_regions


def test_random_words_are_seeded_unique_and_not_static_defaults():
    style=RuleOptions();seen=set()
    for seed in range(100):
        content=plan_seal_content(style,seed)
        assert content==plan_seal_content(style,seed)
        text=seal_text(content)
        assert not duplicate_words([text])
        assert "SAMPLE OFFICE" not in text and len(content['lines'])>=2
        assert text not in seen;seen.add(text)
    assert plan_seal_content(style,42,'a')!=plan_seal_content(style,42,'b')
    assert not duplicate_words(['04-04-2020'])


def test_static_custom_and_explicit_repeated_text():
    style=RuleOptions(seal_text_mode='static',seal_text='CEDAR LAB',seal_subtext='MIRA DEV\nDIRECTOR',seal_bottom_text='RIVERTON')
    assert seal_text(plan_seal_content(style,1))==seal_text(plan_seal_content(style,1009))
    with pytest.raises(ValueError,match='Repeated seal words'):
        RuleOptions(seal_text_mode='static',seal_text='Cedar LAB',seal_subtext='CEDAR Lab')
    repeated=style.model_copy(update={'seal_text':'SAME WORDS','seal_subtext':'SAME WORDS','seal_allow_repeated_words':True})
    assert seal_text(plan_seal_content(repeated,1)).count('SAME WORDS')==2
    custom=RuleOptions(seal_text_mode='custom',seal_top_format='{organization}',seal_body_format='{department}\n{name}\nREF {reference}',seal_bottom_format='{city} {year}')
    text=seal_text(plan_seal_content(custom,42))
    assert '{' not in text and '0000002A' in text and not duplicate_words([text])
    assert text!=seal_text(plan_seal_content(custom,43))
    bad=custom.model_copy(update={'seal_body_format':'{organization}'})
    with pytest.raises(ValueError,match='Repeated seal words'):plan_seal_content(bad,42)
    assert plan_seal_content(bad.model_copy(update={'seal_allow_repeated_words':True}),42)['top']==plan_seal_content(bad.model_copy(update={'seal_allow_repeated_words':True}),42)['lines'][0]
    literal=plan_seal_content(style,42,literal='EXPLICIT HEADING')
    assert literal['top']=='EXPLICIT HEADING' and literal['mode']=='static'


def test_legacy_job_snapshots_keep_static_wording_without_mutating_saved_data():
    saved={'regions':[{'id':'s','kind':'seal','box':[0,0,200,200],'rule_options':{'seal_text':'CEDAR LAB','seal_subtext':'CEDAR LAB'}}]}
    region=snapshot_regions(saved)[0]
    assert region.rule_options.seal_text_mode=='static'
    assert seal_text(plan_seal_content(region.rule_options,1))=='CEDAR LAB\nCEDAR LAB'
    assert 'seal_text_mode' not in saved['regions'][0]['rule_options']


def test_monogram_respects_the_repeat_word_setting():
    options=RuleOptions(seal_text_mode='static',seal_text='TEST OFFICE',seal_subtext='TO',seal_style='ring',seal_symbol='monogram')
    with pytest.raises(ValueError,match='Monogram repeats'):
        render_seal((240,240),plan_seal_content(options,42),random.Random(42),options)
    allowed=options.model_copy(update={'seal_allow_repeated_words':True})
    _,_,info=render_seal((240,240),plan_seal_content(allowed,42),random.Random(42),allowed)
    assert info['text'].splitlines().count('TO')==2


@pytest.mark.parametrize('size',[125,300])
def test_double_ring_body_text_boxes_stay_inside_the_inner_border(monkeypatch,size):
    from PIL import ImageDraw
    original=ImageDraw.ImageDraw.text;boxes=[]
    def record(draw,xy,text,*args,**kwargs):
        if draw._image.size==(size*3,size*3):
            b=kwargs['font'].getbbox(text)
            boxes.append((xy[0]+b[0],xy[1]+b[1],xy[0]+b[2],xy[1]+b[3]))
        return original(draw,xy,text,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,'text',record)
    style=RuleOptions(seal_style='double_ring')
    render_seal((size,size),plan_seal_content(style,42),random.Random(42),style)
    center=size*3/2;radius=(center-max(9,size*3*.055))*.66
    assert boxes
    for left,top,right,bottom in boxes:
        assert all((x-center)**2+(y-center)**2<radius**2 for x in (left,right) for y in (top,bottom))


def test_invalid_custom_repetition_is_rejected_before_a_job_is_created(tmp_path):
    from backend.app.db import Template
    app=create_app(f"sqlite:///{tmp_path/'job.db'}",tmp_path,start_worker=False)
    source=tmp_path/'source.png';Image.new('RGB',(300,300),'white').save(source)
    region=Region(id='s',kind='seal',box=[20,20,240,240],confirmed=True,rule_options={'seal_text_mode':'custom','seal_body_format':'{organization}'})
    with app.state.sessions.begin() as db:
        db.add(Template(id='fixture',name='Fixture',image_path=str(source),width=300,height=300,regions=[region.model_dump(mode='json')],privacy_confirmed=True))
    with TestClient(app) as client:
        response=client.post('/api/jobs',json={'template_id':'fixture','count':1})
        assert response.status_code==422 and 'Repeated seal words' in response.json()['detail']
        assert client.get('/api/jobs').json()==[]


@pytest.mark.parametrize('template',['{unknown}','{name.__class__}','{name!r}','{number:06d}','{','{}'])
def test_custom_formats_cannot_execute_expressions_or_unknown_fields(template):
    with pytest.raises(ValueError):RuleOptions(seal_top_format=template)


@pytest.mark.parametrize('shape',SHAPES)
def test_all_shapes_fit_seeded_text_without_background_or_truncation(shape):
    for seed in (14,42):
        style=RuleOptions(seal_style=shape)
        size=(125,125) if shape in {'ring','round','double_ring','badge','oval','square'} else (340,160)
        content=plan_seal_content(style,seed)
        layer,mask,info=render_seal(size,content,random.Random(seed),style)
        same,_,same_info=render_seal(size,content,random.Random(seed),style)
        assert layer.tobytes()==same.tobytes() and info==same_info
        assert layer.mode=='RGBA' and layer.getpixel((0,0))[3]==0
        assert all(line in info['text'] for line in [content['top'],*content['lines'],content['bottom']])
        assert not duplicate_words([info['text']])
        left,top,right,bottom=mask.getbbox()
        assert 0<left<right<size[0] and 0<top<bottom<size[1]
        assert np.array_equal(np.asarray(mask)>0,np.asarray(layer.getchannel('A'))>0)


def test_seal_annotations_record_actual_wording_and_export_metadata(tmp_path):
    source=tmp_path/'source.png';Image.new('RGB',(600,300),'#eff4f0').save(source)
    region=Region(id='seal',kind='seal',box=[30,30,500,220],confirmed=True,rule_options={'seal_style':'professional'})
    config=GenerationConfig(template_id='fixture',blur_probability=0,rotation_probability=0)
    result=render_sample(source,[region],config,0,tmp_path/'out')
    annotation=result['annotations'][0]
    assert annotation['text']==annotation['seal']['text']==fictional_values([region],42,config)['seal']
    assert annotation['seal']['engine']=='seal-v2' and annotation['seal']['content_mode']=='random'
    assert result['image'].getpixel((0,0))==(239,244,240)


def test_preview_validates_repeat_and_size_without_creating_dataset(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'preview.db'}",tmp_path,start_worker=False)
    with TestClient(app) as client:
        response=client.post('/api/seals/preview',json={'width':300,'height':300,'seed':42})
        assert response.status_code==200,response.text
        data=response.json();layer=Image.open(io.BytesIO(base64.b64decode(data['image'].split(',',1)[1])))
        assert layer.mode=='RGBA' and layer.size==(300,300)
        assert data['metadata']['engine']=='seal-v2'
        assert client.post('/api/seals/preview',json={'options':{'seal_text_mode':'custom','seal_body_format':'{organization}'}}).status_code==422
        assert client.post('/api/seals/preview',json={'width':4}).status_code==422
        assert client.get('/api/jobs').json()==[]
