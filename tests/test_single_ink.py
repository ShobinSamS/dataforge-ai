import io
import json
import random
import time
import zipfile
import numpy as np
import pytest
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.signature_image import make_guide,isolate_signature
from backend.app import diffusion
from backend.app.seal_artwork import artwork_alpha
from backend.app.signatures import render_signature
from backend.app.seals import render_seal,plan_seal_content
from backend.app.schemas import RuleOptions


def wait(c,id_):
    for _ in range(500):
        job=c.get('/api/diffusion/jobs/'+id_).json()
        if job['status'] in diffusion.TERMINAL:return job
        time.sleep(.02)
    raise AssertionError('Image run did not finish')


def test_isolation_removes_other_rows_and_keeps_one_transparent_autograph(tmp_path):
    guide=make_guide(tmp_path,71,'Mira Dev','surname')
    with Image.open(tmp_path/'guide.png') as original:image=original.convert('RGB')
    draw=ImageDraw.Draw(image)
    for y in [35,80,415,455]:draw.line([(60,y),(150,y-18),(185,y+8),(350,y-10)],fill='black',width=3)
    out,metadata=isolate_signature(image,guide['guide_bbox'])
    assert out.mode=='RGBA' and out.getpixel((0,0))[3]==0
    assert metadata['signature_ink_groups']==1
    bbox=out.getchannel('A').getbbox();assert bbox[0]>0 and bbox[1]>80 and bbox[2]<512 and bbox[3]<432
    # A sheet's discarded rows never leak into the output's ink support.
    with Image.open(tmp_path/'guide.png') as single:
        clean,_=isolate_signature(single,guide['guide_bbox'])
    assert out.tobytes()==clean.tobytes()


def test_dense_and_clipped_ink_are_rejected_instead_of_returning_a_sheet():
    image=Image.new('RGB',(512,512),'white');ImageDraw.Draw(image).rectangle((80,190,430,320),fill='black')
    with pytest.raises(ValueError,match='dense|boundary'):isolate_signature(image,[90,200,420,310])
    with pytest.raises(ValueError,match='No isolated'):isolate_signature(Image.new('RGB',(512,512),'white'),[90,200,420,310])


def test_a_single_letter_guide_is_not_rejected_for_being_narrow(tmp_path):
    guide=make_guide(tmp_path,42,'M','single_letter')
    with Image.open(tmp_path/'guide.png') as image:out,metadata=isolate_signature(image,guide['guide_bbox'])
    assert out.getchannel('A').getbbox() and metadata['signature_ink_groups']==1


def test_clean_signatures_keep_uniform_paths_and_natural_ink_uses_pressure():
    for finish,model in [('clean','uniform-v1'),('natural','continuous-speed-v2')]:
        options=RuleOptions(signature_style='interwoven',font_weight='normal',ink_finish=finish)
        one,mask,info=render_signature((440,150),'Mira Dev',random.Random(42),options)
        two,_,_=render_signature((440,150),'Mira Dev',random.Random(42),options)
        assert one.tobytes()==two.tobytes() and mask.getbbox()
        assert info['pressure_model']==model


def test_text_seals_batch_exact_words_without_models_and_recolor_is_non_destructive(tmp_path,monkeypatch):
    monkeypatch.setattr(diffusion,'capabilities',lambda root:{'ready':False})
    def no_model(*args):raise AssertionError('A text seal or color edit must not run diffusion')
    monkeypatch.setattr(diffusion,'run_worker',no_model)
    with TestClient(create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)) as c:
        options={'seal_style':'professional','seal_text_mode':'static','seal_text':'DR. MIRA DEV','seal_subtext':'CONSULTANT\nCEDAR CLINIC','seal_bottom_text':'TESTVILLE','seal_color':'black','color_mode':'manual','text_color':'#173574','ink_finish':'clean','ink_opacity_mode':'fixed','ink_opacity':1}
        r=c.post('/api/diffusion/jobs',json={'kind':'text_seal','prompt':'Text seal','count':3,'seed':400,'seal_options':options});assert r.status_code==200,r.text
        source=wait(c,r.json()['id']);assert source['status']=='completed',source
        assert all(i['rendering_engine']=='native-text-seal' for i in source['items'])
        assert all('MIRA DEV' in i['seal']['text'] and 'CEDAR CLINIC' in i['seal']['text'] for i in source['items'])
        original=Image.open(io.BytesIO(c.get(source['items'][0]['image_url']).content)).convert('RGBA')
        variant=c.post(f'/api/diffusion/jobs/{source["id"]}/recolor',json={'color_mode':'manual','text_color':'#c42035'});assert variant.status_code==200,variant.text
        changed=variant.json();assert changed['id']!=source['id'] and changed['count']==3 and changed['completed']==3
        output=Image.open(io.BytesIO(c.get(changed['items'][0]['image_url']).content)).convert('RGBA')
        assert np.array_equal(np.asarray(original)[:,:,3],np.asarray(output)[:,:,3])
        rgba=np.asarray(output);assert np.all(rgba[rgba[:,:,3]>0,:3]==[196,32,53])
        again=c.get(f'/api/diffusion/jobs/{source["id"]}').json();assert again['items'][0]['sha256']==source['items'][0]['sha256']
        saved=c.post(f'/api/diffusion/jobs/{changed["id"]}/save').json()
        assert saved['assets'][0]['source']=='local_text_seal'
        provenance=json.loads(saved['assets'][0]['attribution']);assert provenance['ink']['text_color']=='#c42035'
        archive=c.get(changed['download_url']);assert archive.status_code==200
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:assert len([n for n in z.namelist() if n.endswith('.png')])==3
        invalid=c.post(f'/api/diffusion/jobs/{source["id"]}/recolor',json={'color_mode':'random','color_palette':['invalid']});assert invalid.status_code==422


def test_random_ink_colors_are_seeded_without_changing_mask():
    mask=Image.new('L',(100,50));ImageDraw.Draw(mask).line((10,40,35,5,60,42,90,20),fill=255,width=3)
    image=Image.new('RGBA',mask.size,'black');image.putalpha(mask)
    options=diffusion.InkAppearance(color_mode='random',color_palette=['#173574','#c42035','#216e39'])
    colors=[]
    for seed in range(15):
        one,color=diffusion.colorize(image,options,seed);two,same=diffusion.colorize(image,options,seed)
        assert one.tobytes()==two.tobytes() and same==color
        assert one.getchannel('A').tobytes()==mask.tobytes();colors.append(color)
    assert len(set(colors))>1


def test_recolored_ink_keeps_coverage_when_used_in_signatures_and_seals():
    alpha=Image.new('L',(160,80));ImageDraw.Draw(alpha).line((12,60,45,10,78,62,145,25),fill=170,width=4)
    black=Image.new('RGBA',alpha.size,'black');black.putalpha(alpha)
    blue=Image.new('RGBA',alpha.size,'#173574');blue.putalpha(alpha)
    assert artwork_alpha(blue).tobytes()==alpha.tobytes()
    options=RuleOptions(font_weight='normal',color_mode='black',ink_finish='clean',ink_opacity_mode='fixed',ink_opacity=1,seal_wear=0,seal_style='corporate',seal_symbol='none')
    outputs=[render_signature((300,130),'Mira Dev',random.Random(42),options,image)[0] for image in [black,blue]]
    assert outputs[0].tobytes()==outputs[1].tobytes()
    content=plan_seal_content(options,42)
    outputs=[render_seal((400,400),content,random.Random(42),options,image)[0] for image in [black,blue]]
    assert outputs[0].tobytes()==outputs[1].tobytes()
    scan=Image.new('RGB',(80,40),'white');ImageDraw.Draw(scan).line((10,30,65,10),fill='black',width=3)
    mask=artwork_alpha(scan)
    assert mask.getpixel((0,0))==0 and mask.getpixel((10,30))==255
