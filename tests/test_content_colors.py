import random

import numpy as np
import pytest
from PIL import Image

from backend.app.schemas import RuleOptions,Region,GenerationConfig
from backend.app.signatures import render_signature,STYLES
from backend.app.colors import choose_color
from backend.app.seals import render_seal
from backend.app.render import render_sample


@pytest.mark.parametrize('family',STYLES)
def test_content_modes_are_independent_of_style(family):
    for mode in ('name','alphabet'):
        options=RuleOptions(signature_style=family,signature_content=mode,ink_finish='clean',ink_opacity_mode='fixed')
        layer,mask,info=render_signature((480,160),'Mira Dev',random.Random(42),options)
        assert info['style']==family and info['content_mode']==mode
        if mode=='name':assert info['text'].split()==['Mira','Dev']
        else:assert 1<=len(info['text'])<=3 and set(info['text'])<=set('MD')
        assert mask.getbbox() and layer.getpixel((0,0))[3]==0


def test_mixed_is_seeded_and_boldness_is_visibly_stronger():
    options=RuleOptions(signature_style='minimal',signature_content='mixed',ink_finish='clean',ink_opacity_mode='fixed')
    modes=set()
    for seed in range(12):
        a,_,info=render_signature((340,100),'Mira Dev',random.Random(seed),options)
        b,_,other=render_signature((340,100),'Mira Dev',random.Random(seed),options)
        assert a.tobytes()==b.tobytes() and info==other
        modes.add(info['content_mode'])
    assert modes=={'current','name','alphabet'}
    options=options.model_copy(update={'signature_content':'alphabet','font_weight':'normal'})
    base,_,_=render_signature((340,100),'Mira Dev',random.Random(42),options)
    bold,mask,info=render_signature((340,100),'Mira Dev',random.Random(42),options.model_copy(update={'signature_thickness':2.5}))
    assert np.asarray(bold.getchannel('A')).sum()>np.asarray(base.getchannel('A')).sum()*1.6
    assert np.array_equal(np.asarray(mask)>0,np.asarray(bold.getchannel('A'))>0)


def test_colors_are_seeded_do_not_change_geometry_and_validate():
    options=RuleOptions(signature_style='enclosed',signature_content='name',color_mode='random',color_palette=['#123456','#a80000'],ink_finish='clean',ink_opacity_mode='fixed')
    seen=set()
    for seed in range(8):
        layer,mask,info=render_signature((340,100),'Mira Dev',random.Random(seed),options)
        seen.add(info['text_color'])
        fixed,other,meta=render_signature((340,100),'Mira Dev',random.Random(seed),options.model_copy(update={'color_mode':'manual','text_color':'#336699'}))
        assert mask.tobytes()==other.tobytes() and info['text']==meta['text'] and info['style']==meta['style']
        pixels=np.asarray(layer);visible=pixels[:,:,3]>0
        assert np.all(pixels[visible,:3]==tuple(bytes.fromhex(info['text_color'][1:])))
    assert seen=={'#123456','#a80000'}
    assert RuleOptions().text_color=='#000000' and RuleOptions().color_mode=='black'
    for palette in ([],['red'],['#abcdef']*21):
        with pytest.raises(ValueError):RuleOptions(color_palette=palette)


def test_seal_custom_and_mixed_palette_apply_to_all_ink():
    content={'top':'SAMPLE OFFICE','bottom':'TEST CITY','lines':['RECORDS'],'mode':'static'}
    options=RuleOptions(seal_style='ring',color_mode='manual',text_color='#004488',seal_wear=0,ink_finish='clean',ink_opacity_mode='fixed')
    image,mask,info=render_seal((300,300),content,random.Random(42),options)
    assert info['ink_color']==info['text_ink_color']=='#004488'
    pixels=np.asarray(image);assert np.all(pixels[pixels[:,:,3]>0,:3]==(0,68,136))
    layer,_,mixed=render_seal((300,300),content,random.Random(42),options.model_copy(update={'color_mode':'mixed','color_palette':['#004488','#a00000']}))
    assert mixed['ink_color']!=mixed['text_ink_color']
    pixels=np.asarray(layer)
    assert {tuple(c) for c in pixels[pixels[:,:,3]>0,:3]}=={(0,68,136),(160,0,0)}


def test_batch_content_and_random_text_colors_reach_annotations(tmp_path):
    source=tmp_path/'page.png';Image.new('RGB',(800,500),'white').save(source)
    fields=[Region(id='s',kind='signature',box=[30,30,480,140],rule_options={'signature_style':'enclosed'}),
            Region(id='d',kind='date',box=[30,230,250,50],rule_options={'color_mode':'random','color_palette':['#7b0011']}),
            Region(id='i',kind='identifier',box=[30,330,250,50],rule_options={'color_mode':'manual','text_color':'#123456'})]
    config=GenerationConfig(template_id='x',signature_content_override='alphabet',rotation_probability=0,blur_probability=0)
    result=render_sample(source,fields,config,0,tmp_path/'out')
    sign,date,identifier=result['annotations']
    assert sign['signature']['content_mode']=='alphabet' and len(sign['text'])<=3
    assert date['typography']['text_color']=='#7b0011'
    assert identifier['typography']['text_color']=='#123456'
    assert fields[0].rule_options.signature_content=='current'
