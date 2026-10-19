"""Appearance tests: ink defects must be local, reproducible and label-aware."""
import io
import random
import numpy as np
import pytest
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient
from backend.app.schemas import RuleOptions
from backend.app.ink_finish import apply_ink_finish,transform_local_boxes
from backend.app.signatures import render_signature
from backend.app.seals import render_seal,plan_seal_content
from backend.app.main import create_app


def fixture():
    image=Image.new('RGBA',(400,180))
    draw=ImageDraw.Draw(image)
    draw.rectangle((40,30,360,150),fill=(25,60,140,255))
    return image


def test_clean_and_zero_strength_preserve_exact_bytes_without_advancing_rng():
    layer=fixture();rng=random.Random(42);before=rng.getstate()
    for options in (RuleOptions(ink_finish='clean'),RuleOptions(ink_irregularity=0)):
        result,mask,info=apply_ink_finish(layer.copy(),rng,options,'signature')
        assert result.tobytes()==layer.tobytes() and info['strength']==0
        assert mask.tobytes()==layer.getchannel('A').tobytes()
        assert rng.getstate()==before
    assert RuleOptions().ink_finish=='natural'


@pytest.mark.parametrize('kind',['signature','seal'])
def test_finish_has_nonuniform_ink_not_just_a_global_fade(kind):
    layer=fixture();options=RuleOptions(ink_finish='natural',ink_irregularity=.75)
    rng=random.Random(42);before=rng.getstate()
    result,mask,info=apply_ink_finish(layer,rng,options,kind)
    same,_,same_info=apply_ink_finish(layer,random.Random(42),options,kind)
    assert result.tobytes()==same.tobytes() and info==same_info
    assert rng.getstate()==before
    alpha=np.asarray(result.getchannel('A'))
    # Away from all original boundaries, a uniform opacity change has zero
    # variance. These pressure/contact defects must vary inside the ink itself.
    interior=alpha[55:125,75:325]/255
    assert interior.std()>.03 and interior.mean()<.98
    assert info['displacement_max_px']>0 and info['rotation_degrees']!=0
    assert np.array_equal(np.asarray(mask)>0,alpha>0)
    assert result.getpixel((0,0))[3]==0
    colors=np.asarray(result)[:,:,:3][alpha>0]
    assert np.max(abs(colors.astype(float)-[25,60,140]))<=1


@pytest.mark.parametrize('kind',['signature','seal'])
def test_seeded_breaks_remove_ink_and_worn_setting_increases_damage(kind):
    layer=fixture();seen=set();natural_mass=[];worn_mass=[];breaks=[]
    for seed in range(6):
        options=RuleOptions(ink_irregularity=.65)
        natural,_,info=apply_ink_finish(layer,random.Random(seed),options,kind)
        worn,_,heavy=apply_ink_finish(layer,random.Random(seed),options.model_copy(update={'ink_finish':'worn'}),kind)
        assert heavy['strength']>=info['strength']>0
        seen.add(natural.tobytes())
        natural_mass.append(np.asarray(natural.getchannel('A')).sum())
        worn_mass.append(np.asarray(worn.getchannel('A')).sum())
        for entry in heavy['breaks']:
            assert worn.getpixel((entry['x'],entry['y']))[3]==0
            breaks.append(entry)
    assert len(seen)==6 and breaks
    assert np.mean(worn_mass)<np.mean(natural_mass)


@pytest.mark.parametrize('kind,size,shape',[
    ('signature',(180,50),'minimal'),('signature',(440,150),'interwoven'),
    ('seal',(125,125),'ring'),('seal',(500,120),'nameplate')])
def test_strong_defects_fit_regions_keep_lettering_and_export_the_actual_mask(kind,size,shape):
    for seed in (1,42,79):
        options=RuleOptions(ink_finish='worn',ink_irregularity=1,ink_opacity_mode='fixed',
                            signature_style=shape if kind=='signature' else 'mixed',
                            seal_style=shape if kind=='seal' else 'ring',seal_wear=0)
        if kind=='signature':
            image,mask,info=render_signature(size,'Abdul Qadeer',random.Random(seed),options)
        else:
            image,mask,info=render_seal(size,plan_seal_content(options,seed),random.Random(seed),options)
        left,top,right,bottom=mask.getbbox()
        assert 0<left<right<size[0] and 0<top<bottom<size[1]
        assert np.array_equal(np.asarray(mask)>0,np.asarray(image.getchannel('A'))>0)
        assert info['text'] and info['ink_finish']['mode']=='worn'


def test_local_field_boxes_follow_the_stamp_transform_without_mutating_source():
    options=RuleOptions(seal_style='form_block',seal_text_mode='static',seal_text='CEDAR OFFICE',
                        seal_subtext='TO: MIRA DEV\nDATE: 18-07-2024',seal_wear=0,ink_irregularity=.8)
    content=plan_seal_content(options,42)
    _,_,clean=render_seal((500,250),content,random.Random(42),options.model_copy(update={'ink_finish':'clean'}))
    image,_,natural=render_seal((500,250),content,random.Random(42),options)
    assert natural['fields']!=clean['fields']
    assert [(f['label'],f['value']) for f in natural['fields']]==[(f['label'],f['value']) for f in clean['fields']]
    for field in natural['fields']:
        for key in ('bbox','label_bbox','value_bbox'):
            x,y,w,h=field[key]
            assert 0<=x<x+w<=500 and 0<=y<y+h<=250
            assert np.asarray(image.getchannel('A'))[int(y):int(y+h)+1,int(x):int(x+w)+1].max()>0
    # Independent raster oracle: the reported transformed box must contain
    # all ink from one known rectangle, including interpolation and warp.
    result,mask,finish=apply_ink_finish(fixture(),random.Random(42),options,'seal')
    source={'fields':[{'value_bbox':[40,30,321,121]}]}
    mapped=transform_local_boxes(source,finish,(400,180))['fields'][0]['value_bbox']
    x,y,w,h=mapped;left,top,right,bottom=mask.getbbox()
    assert x<=left<right<=x+w and y<=top<bottom<=y+h
    assert source['fields'][0]['value_bbox']==[40,30,321,121]


@pytest.mark.parametrize('kind',['signature','seal'])
def test_finishing_preserves_selected_letters_design_and_weight(kind):
    options=RuleOptions()
    reports=[]
    for mode in ('clean','natural','worn'):
        style=options.model_copy(update={'ink_finish':mode})
        if kind=='signature':
            _,_,info=render_signature((440,150),'Talha Ali',random.Random(42),style)
            reports.append((info['text'],info['style'],info['stroke_weight'],info['font_id']))
        else:
            _,_,info=render_seal((300,300),plan_seal_content(style,42),random.Random(42),style)
            reports.append((info['text'],info['shape'],info['ink'],info['border']))
    assert reports[0]==reports[1]==reports[2]


@pytest.mark.parametrize('patch',[{'ink_finish':'unknown'},{'ink_irregularity':-1},{'ink_irregularity':1.01},{'ink_irregularity':float('nan')}])
def test_invalid_finish_options_are_rejected(patch):
    with pytest.raises(ValueError):RuleOptions(**patch)


def test_previews_use_finish_settings_and_create_no_dataset(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'preview.db'}",tmp_path,start_worker=False)
    with TestClient(app) as client:
        previews=client.get('/api/signatures/previews?style=interwoven&ink_finish=worn&ink_irregularity=0.8').json()
        response=client.get(previews[0]['url'])
        assert response.status_code==200 and response.headers['X-Ink-Finish']=='worn'
        assert Image.open(io.BytesIO(response.content)).mode=='RGBA'
        response=client.post('/api/seals/preview',json={'options':{'ink_finish':'worn','ink_irregularity':.8}})
        assert response.status_code==200 and response.json()['metadata']['ink_finish']['mode']=='worn'
        assert client.get('/api/signatures/preview?ink_irregularity=2').status_code==422
        assert client.get('/api/jobs').json()==[]
