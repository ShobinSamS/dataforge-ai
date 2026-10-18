import io
import random
import re
from datetime import date

import numpy as np
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from backend.app.db import Template
from backend.app.fonts import installed_fonts, load_font, match_font, prepare_typography, resolve_font_weight
from backend.app.ingest import decode
from backend.app.demo import certificate
from backend.app.main import create_app
from backend.app.patterns import generate_pattern, pattern_length
from backend.app.portraits import illustration
from backend.app.render import asset, fictional_values, render_sample
from backend.app.schemas import Region, RuleOptions, GenerationConfig
from backend.app.validation import validate


def test_generic_patterns_and_length_bounds():
    pattern="INV-{upper:2}-{digits:6}-{lower:3}"
    value=generate_pattern(pattern,42,date(2020,1,1),date(2024,12,31))
    assert re.fullmatch(r"INV-[A-Z]{2}-[0-9]{6}-[a-z]{3}",value)
    assert len(value)==pattern_length(pattern)
    assert value==generate_pattern(pattern,42,date(2020,1,1),date(2024,12,31))
    assert value!=generate_pattern(pattern,43,date(2020,1,1),date(2024,12,31))
    assert generate_pattern("{year}/{month}/{day}",1,date(2000,2,29),date(2000,2,29))=="2000/02/29"
    for invalid in ["{digits:501}","{digits:0}","{eval:4}","{upper:500}{digits:1}","{upper:3", "x}"]:
        with pytest.raises(ValueError): RuleOptions(identifier_pattern=invalid)
    with pytest.raises(ValueError): RuleOptions(identifier_pattern="{digits:8}",character_length=9)
    with pytest.raises(ValueError): Region(id="date",kind="date",box=[0,0,100,30],rule_options={"character_length":10})
    with pytest.raises(ValueError): Region(id="longtext",kind="text",box=[0,0,100,30],rule_options={"identifier_pattern":"{upper:129}"})


def test_character_counts_and_no_automatic_prefix():
    regions=[Region(id=kind,kind=kind,box=[0,0,200,40]) for kind in ["identifier","qr","barcode"]]
    config=GenerationConfig(template_id="fixture",identifier_length=14,qr_payload_length=24)
    values=fictional_values(regions,42,config)
    assert len(values["identifier"])==14 and len(values["qr"])==24 and len(values["barcode"])==14
    assert all("SYN-" not in value for value in values.values())
    r=Region(id="custom",kind="qr",box=[0,0,200,200],rule_options={"character_length":18,"character_set":"digits"})
    assert re.fullmatch(r"[0-9]{18}",fictional_values([r],42,config)[r.id])
    r=Region(id="custom",kind="identifier",box=[0,0,200,40],rule_options={"identifier_pattern":"SKU-{lower:4}{digits:5}"})
    assert re.fullmatch(r"SKU-[a-z]{4}[0-9]{5}",fictional_values([r],42,config)[r.id])


def test_qr_padding_and_borderless_validation(tmp_path):
    zero,_=asset("qr",(180,180),"ABC123",random.Random(1),qr_padding=0)
    padded,_=asset("qr",(180,180),"ABC123",random.Random(1),qr_padding=4)
    assert zero.getpixel((0,0))[:3]==(0,0,0)
    assert padded.getpixel((0,0))[:3]==(255,255,255)
    source=tmp_path/"source.png";Image.new("RGB",(300,300),"white").save(source)
    r=Region(id="qr",kind="qr",box=[40,40,180,180],confirmed=True)
    result=render_sample(source,[r],GenerationConfig(template_id="test",qr_padding=0,qr_payload_length=24,blur_probability=0,rotation_probability=0),0,tmp_path/"out")
    assert len(result["annotations"][0]["text"])==24
    assert validate(result,tmp_path/"out",1)["passed"]


def test_500_character_qr_needs_no_pattern_or_model(tmp_path):
    source=tmp_path/"source.png";Image.new("RGB",(500,500),"white").save(source)
    r=Region(id="qr",kind="qr",box=[40,40,420,420],confirmed=True)
    config=GenerationConfig(template_id="qr500",qr_payload_length=500,rotation_probability=0,blur_probability=0)
    result=render_sample(source,[r],config,0,tmp_path/"qr500")
    assert r.rule_options.identifier_pattern==""
    assert len(result["annotations"][0]["text"])==500
    assert validate(result,tmp_path/"qr500",1)["passed"]
    assert len(fictional_values([Region(id="qr",kind="qr",box=[40,40,420,420],rule_options={"character_length":500})],42)["qr"])==500
    with pytest.raises(ValueError): GenerationConfig(template_id="fixture",qr_payload_length=501)
    with pytest.raises(ValueError): Region(id="text",kind="text",box=[0,0,100,30],rule_options={"character_length":129})


def test_matched_size_and_bold_are_preserved_in_short_boxes():
    regular=next(id_ for id_,record in installed_fonts().items() if not record["bold"] and not record["italic"])
    bold=resolve_font_weight(regular,"bold")
    assert installed_fonts()[bold]["bold"]
    text="TEST123";f=load_font(32,bold);bounds=f.getbbox(text)
    height=bounds[3]-bounds[1]+6
    _,mask=asset("text",(240,height),text,random.Random(1),RuleOptions(font_id=regular,font_weight="bold",font_size=32))
    box=mask.getbbox()
    assert box[3]-box[1]==bounds[3]-bounds[1]
    _,normal=asset("text",(240,height),text,random.Random(1),RuleOptions(font_id=regular,font_weight="normal",font_size=32))
    assert np.count_nonzero(np.asarray(mask))>np.count_nonzero(np.asarray(normal))


def test_automatic_bold_and_background_restoration(tmp_path):
    regular=next(id_ for id_,record in installed_fonts().items() if not record["bold"] and not record["italic"])
    bold=resolve_font_weight(regular,"bold")
    pixels=np.zeros((110,500,3),np.uint8)
    pixels[:,:,0]=np.linspace(150,190,500,dtype=np.uint8);pixels[:,:,1]=180;pixels[:,:,2]=225
    source=Image.fromarray(pixels);text="ABCDEFG1234567"
    ImageDraw.Draw(source).text((15,20),text,font=load_font(32,bold),fill="black")
    path=tmp_path/"source.png";source.save(path)
    region=Region(id="replace",kind="text",text=text,box=[10,10,400,70],rule_options={"literal_text":"REPLACED"})
    prepared=prepare_typography(path,[region])[0]
    assert installed_fonts()[prepared.rule_options.font_id]["bold"]
    assert prepared.rule_options.text_color=="#000000"
    result=render_sample(path,[prepared],GenerationConfig(template_id="test",blur_probability=0,rotation_probability=0),0,tmp_path/"restored")
    rendered=np.asarray(result["image"])
    # These source-background rows must retain their gradient, not become a flat rectangle.
    assert np.array_equal(rendered[70:78,20:390],pixels[70:78,20:390])
    assert result["annotations"][0]["typography"]["font_id"]==prepared.rule_options.font_id
    unknown=prepare_typography(path,[region.model_copy(update={"text":""})])[0]
    assert installed_fonts()[unknown.rule_options.font_id]["bold"]


def test_solid_cleanup_is_explicit_and_text_layer_is_transparent(tmp_path):
    path=tmp_path/"source.png";Image.new("RGB",(300,100),"blue").save(path)
    r=Region(id="text",kind="text",box=[20,20,220,50],rule_options={"literal_text":"TEST","background_mode":"solid","background_color":"#ffffff","font_size":20})
    result=render_sample(path,[r],GenerationConfig(template_id="test",blur_probability=0,rotation_probability=0),0,tmp_path/"out")
    assert result["image"].getpixel((230,65))==(255,255,255)
    assert result["image"].getpixel((10,10))==(0,0,255)
    layer,_=asset("text",(220,50),"TEST",random.Random(42),r.rule_options)
    assert layer.getpixel((210,45))[3]==0


def test_portrait_has_no_caption(monkeypatch):
    original=ImageDraw.ImageDraw.text
    labels=[]
    def track(self,xy,text,*args,**kwargs):
        labels.append(text)
        return original(self,xy,text,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,"text",track)
    portrait=illustration((300,400),random.Random(42))
    assert portrait.size==(300,400) and labels==[]
    assert np.unique(np.asarray(portrait)[375:],axis=0).size>3


def test_local_font_comparison_and_pdf_font_metadata():
    fonts=installed_fonts()
    assert fonts
    id_=next(iter(fonts));text="ABCDEFG1234567"
    image=Image.new("RGB",(500,100),"white")
    ImageDraw.Draw(image).text((15,15),text,font=load_font(32,id_),fill="#202020")
    result=match_font(image,[0,0,480,90],text)
    assert result["font_id"]==id_ and abs(result["font_size"]-32)<=1
    assert result["similarity"]>.85
    _,regions=decode(certificate(),".pdf")
    assert any(r.get("source_font") and r.get("source_font_size",0)>0 for r in regions)
    with pytest.raises(ValueError): load_font(20,"../../other")


def test_font_endpoint_and_required_qr(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)
    source=tmp_path/"source.png";image=Image.new("RGB",(500,200),"white")
    text="ABCDEFG1234567";font_id=next(iter(installed_fonts()))
    ImageDraw.Draw(image).text((15,15),text,font=load_font(32,font_id),fill="#202020");image.save(source)
    r=Region(id="field",kind="identifier",text=text,box=[5,5,450,80],confirmed=True)
    with app.state.sessions.begin() as db:
        db.add(Template(id="fixture",name="Font fixture",image_path=str(source),width=500,height=200,regions=[r.model_dump(mode="json")],privacy_confirmed=True))
    with TestClient(app) as client:
        fonts=client.get("/api/fonts").json()
        assert fonts and all("path" not in f for f in fonts)
        response=client.post("/api/templates/fixture/font-match",json={"region":r.model_dump(mode="json")})
        assert response.status_code==200,response.text
        assert response.json()["region"]["rule_options"]["font_id"]==font_id
        assert not response.json()["region"]["confirmed"]
        response=client.post("/api/jobs",json={"template_id":"fixture","count":1,"qr_required":True})
        assert response.status_code==422 and "QR is required" in response.json()["detail"]
        assert client.post("/api/jobs",json={"template_id":"fixture","count":1,"qr_required":False,"identifier_length":16,"qr_padding":0}).status_code==201
        assert client.post("/api/jobs",json={"template_id":"fixture","qr_codes":False,"qr_required":True}).status_code==422
