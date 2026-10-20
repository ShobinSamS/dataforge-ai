import base64
import io
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image,ImageDraw

from backend.app.main import create_app
from backend.app.canvas import CanvasRequest
from backend.app.schemas import RuleOptions
from backend.app.portraits import portrait_background,prepare_portrait


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)) as client:
        yield client


def png(response):
    return Image.open(io.BytesIO(base64.b64decode(response['image'].split(',')[1])))


def blank(client,**patch):
    response=client.post('/api/templates/blank',json={'paper':'custom','unit':'px','width':360,'height':480,'background':'transparent',**patch})
    assert response.status_code==201,response.text
    return response.json()


def test_paper_defaults_and_resource_limits(client):
    response=client.post('/api/templates/blank',json={})
    assert response.status_code==201,response.text
    t=response.json()
    assert (t['width'],t['height'])==(1240,1754) and t['canvas']['paper']=='a4'
    assert t['regions']==[] and t['engine']=='canvas' and not t['privacy_confirmed']
    assert Image.open(io.BytesIO(client.get(f"/api/templates/{t['id']}/image").content)).getpixel((0,0))==(255,255,255)
    assert CanvasRequest(paper='letter',orientation='landscape').pixels()==(1650,1275)
    for body in ({'paper':'custom','width':6000,'height':6000,'unit':'px'}, {'paper':'custom','width':1,'height':1,'unit':'px'}, {'dpi':301}):
        assert client.post('/api/templates/blank',json=body).status_code==422


def test_transparent_preview_generation_and_export_keep_alpha(client):
    t=blank(client,starter='signature')
    regions=t['regions'];regions[0]['rule_options'].update(signature_style='minimal',signature_content='alphabet',ink_opacity_mode='fixed',ink_finish='clean')
    response=client.post(f"/api/templates/{t['id']}/preview",json={'regions':regions,'seed':42})
    assert response.status_code==200,response.text
    image=png(response.json()); assert image.mode=='RGBA' and image.getpixel((0,0))[3]==0
    assert np.asarray(image.getchannel('A')).max()==255
    assert client.get(f"/api/templates/{t['id']}").json()['revision']==1
    for r in regions:r['confirmed']=True
    assert client.put(f"/api/templates/{t['id']}/review",json={'regions':regions,'privacy_confirmed':True,'revision':1}).status_code==200
    response=client.post('/api/jobs',json={'template_id':t['id'],'count':1,'blur_probability':0,'rotation_probability':0})
    assert response.status_code==201,response.text
    j=response.json();client.app.state.worker.run(j['id'])
    assert client.get(f"/api/jobs/{j['id']}/quality").json()['accepted']==1
    response=client.post(f"/api/jobs/{j['id']}/exports",json={'format':'coco','review_confirmed':True})
    assert response.status_code==201,response.text
    with zipfile.ZipFile(io.BytesIO(client.get(response.json()['download_url']).content)) as archive:
        image=Image.open(io.BytesIO(archive.read('images/000000.png')))
        assert image.mode=='RGBA' and image.getpixel((0,0))[3]==0
        assert image.info['dpi'][0]==pytest.approx(150,abs=.1)


def test_layers_drawing_and_colored_element_background(client):
    t=blank(client)
    draw={'id':'pen','kind':'drawing','box':[40,40,180,100],'sensitive':False,'confirmed':True,
          'rule_options':{'drawing_points':[[.1,.5],[.9,.5]],'drawing_width':8,'color_mode':'manual','text_color':'#ff0000'}}
    cover={'id':'cover','kind':'text','box':[50,45,140,80],'sensitive':False,'confirmed':True,
           'rule_options':{'literal_text':'Text','background_mode':'solid','background_color':'#004488','text_color':'#ffffff'}}
    response=client.post(f"/api/templates/{t['id']}/preview",json={'regions':[draw,cover]})
    assert response.status_code==200,response.text
    image=png(response.json());assert image.getpixel((51,46))==(0,68,136,255)
    response=client.post(f"/api/templates/{t['id']}/preview",json={'regions':[cover,draw]})
    assert response.status_code==200,response.text
    assert png(response.json()).getpixel((100,90))==(255,0,0,255)
    assert client.put(f"/api/templates/{t['id']}/review",json={'regions':[draw,cover],'privacy_confirmed':True,'revision':1}).status_code==200
    with pytest.raises(ValueError):RuleOptions(drawing_points=[(float('nan'),0)])
    with pytest.raises(ValueError):RuleOptions(drawing_points=[(0,2)])


def test_photo_transparency_and_background_colors():
    image=Image.new('RGB',(200,250),'white');draw=ImageDraw.Draw(image)
    draw.ellipse((55,40,145,220),fill='#cc2222')
    draw.rectangle((50,180,150,249),fill='#173574')
    options=RuleOptions(portrait_background='transparent')
    cutout=portrait_background(image,options)
    assert cutout.getpixel((0,0))[3]==0 and cutout.getpixel((100,130))[3]==255
    assert cutout.getpixel((100,249))[3]==255  # clothing touches the bottom edge
    recolored=portrait_background(image,options.model_copy(update={'portrait_background':'solid','portrait_background_color':'#004488'}))
    assert recolored.getpixel((0,0))==(0,68,136,255)
    assert recolored.getpixel((100,130))==(204,34,34,255)
    options=options.model_copy(update={'portrait_background':'random','portrait_background_palette':['#004488','#abcdef']})
    assert portrait_background(image,options,12).tobytes()==portrait_background(image,options,12).tobytes()
    raw=io.BytesIO();cutout.save(raw,format='PNG')
    loaded=prepare_portrait(raw.getvalue());assert loaded.mode=='RGBA' and loaded.getpixel((0,0))[3]==0


def test_qr_decoder_uses_white_matte_without_changing_png(client):
    t=blank(client,starter='qr')
    regions=t['regions'];regions[0]['confirmed']=True
    assert client.put(f"/api/templates/{t['id']}/review",json={'regions':regions,'privacy_confirmed':True,'revision':1}).status_code==200
    j=client.post('/api/jobs',json={'template_id':t['id'],'count':1,'blur_probability':0,'rotation_probability':0}).json()
    client.app.state.worker.run(j['id'])
    assert client.get(f"/api/jobs/{j['id']}/quality").json()['accepted']==1


def test_transparent_canvas_augmentation_retains_empty_corners(tmp_path):
    from backend.app.canvas import create_canvas
    from backend.app.render import render_sample
    from backend.app.schemas import Region,GenerationConfig
    path=tmp_path/'page.png';create_canvas(CanvasRequest(paper='custom',unit='px',width=300,height=400,background='transparent'),path)
    region=Region(id='text',kind='text',box=[40,130,220,70],rule_options={'literal_text':'Maple','text_color':'#173574'})
    config=GenerationConfig(template_id='canvas',count=1,rotation_probability=1,blur_probability=1,noise_sigma=2)
    result=render_sample(path,[region],config,0,tmp_path/'out')
    assert result['image'].mode=='RGBA' and result['image'].getpixel((0,0))[3]==0
    assert result['annotations'] and not result['errors']


def test_preview_requires_canvas_and_keeps_normal_template_overlap_checks(client):
    t=client.post('/api/templates/demo').json()
    assert client.post(f"/api/templates/{t['id']}/preview",json={'regions':[]}).status_code==422
    r={'id':'one','kind':'text','box':[40,40,80,40],'confirmed':True}
    assert client.put(f"/api/templates/{t['id']}/review",json={'regions':[r,{**r,'id':'two'}],'privacy_confirmed':True,'revision':1}).status_code==422
