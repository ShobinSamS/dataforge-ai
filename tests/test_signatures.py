import random
import cv2
import numpy as np
import pytest
from PIL import Image
from backend.app import signatures
from backend.app.schemas import Region,RuleOptions,GenerationConfig
from backend.app.render import render_sample


@pytest.mark.parametrize("family",signatures.STYLES)
def test_signature_forms_are_seeded_transparent_and_record_visible_letters(family):
    options=RuleOptions(signature_style=family)
    first,mask,info=signatures.render_signature((360,110),"Arun Kumar",random.Random(42),options)
    second,_,same=signatures.render_signature((360,110),"Arun Kumar",random.Random(42),options)
    assert first.tobytes()==second.tobytes() and info==same
    assert first.mode=="RGBA" and first.getpixel((0,0))[3]==0
    left,top,right,bottom=mask.getbbox()
    assert 0<left<right<360 and 0<top<bottom<110
    letters="".join(c for c in info["text"] if c.isalpha())
    if family=="single_letter":assert len(letters)==1
    if family in {"two_letters","monogram"}:assert letters=="AK"
    if family=="letter_wave":assert 2<=len(letters)<=3 and info["has_wave"]
    if family=="first_name":assert info["text"]=="Arun"
    if family in {"name","first_name","single_letter","two_letters","initials"}:
        assert info["lettering_only"] and info["connection_count"]==0 and not info["has_flourish"]


@pytest.mark.parametrize("family",["letter_wave","monogram","flourish"])
def test_added_pen_designs_join_actual_letter_ink(monkeypatch,family):
    style=RuleOptions(signature_style=family)
    decorated,_,_=signatures.render_signature((430,112),"Arun Kumar",random.Random(42),style)
    monkeypatch.setattr(signatures,"_curve",lambda *args,**kwargs:None)
    lettering,_,_=signatures.render_signature((430,112),"Arun Kumar",random.Random(42),style)
    ink=np.asarray(decorated.getchannel("A"))>100
    original=np.asarray(lettering.getchannel("A"))>100
    added=ink & ~original
    assert np.count_nonzero(added)>15
    count,labels,stats,_=cv2.connectedComponentsWithStats(ink.astype(np.uint8))
    for index in range(1,count):
        if stats[index,4]<10:continue
        component=labels==index
        # No decorative loop/wave may float independently of the letters.
        if np.any(component & added):assert np.any(component & original)


def test_mixed_mode_covers_all_forms_and_job_labels_match_visible_letters(tmp_path):
    families={signatures.signature_plan("Arun Kumar",random.Random(seed),RuleOptions())["style"] for seed in range(600)}
    assert families==set(signatures.STYLES)
    source=tmp_path/"source.png";Image.new("RGB",(500,200),"white").save(source)
    region=Region(id="signature",kind="signature",box=[35,35,420,110],confirmed=True,rule_options={"signature_style":"single_letter","literal_text":"Arun Kumar"})
    result=render_sample(source,[region],GenerationConfig(template_id="fixture",blur_probability=0,rotation_probability=0),0,tmp_path/"out")
    annotation=result["annotations"][0]
    assert len(annotation["text"])==1 and annotation["text"]==annotation["signature"]["text"]
    assert annotation["signature"]["style"]=="single_letter"
    assert annotation["signature"]["lettering_only"]


@pytest.mark.parametrize("family",signatures.EXPRESSIVE)
def test_expressive_strokes_begin_on_existing_ink_and_fit_small_regions(monkeypatch,family):
    original=signatures._curve;calls=[]
    def connected(draw,points,ink,width):
        x,y=map(round,points[0])
        # Each stroke starts on a glyph or on the preceding pen continuation.
        alpha=np.asarray(draw._image.getchannel("A"))
        assert np.any(alpha[max(0,y-2):y+3,max(0,x-2):x+3]>60)
        calls.append(points)
        original(draw,points,ink,width)
    monkeypatch.setattr(signatures,"_curve",connected)
    for seed in (2,12,42,79):
        layer,mask,info=signatures.render_signature((180,50),"Mira Dev",random.Random(seed),RuleOptions(signature_style=family))
        assert calls and info["connection_count"]>0
        assert info["text"]==("M Dev" if family=="angular" else "Mira Dev")
        left,top,right,bottom=mask.getbbox()
        assert 0<left<right<180 and 0<top<bottom<50
        assert np.array_equal(np.asarray(mask)>0,np.asarray(layer.getchannel("A"))>0)


@pytest.mark.parametrize("family",signatures.EXPRESSIVE)
def test_expressive_jobs_export_the_actual_abbreviated_text(tmp_path,family):
    source=tmp_path/"source.png";Image.new("RGB",(500,180),"#e8f2f3").save(source)
    region=Region(id="sign",kind="signature",box=[20,20,450,120],confirmed=True,
        rule_options={"signature_style":family,"literal_text":"Arun Kumar"})
    result=render_sample(source,[region],GenerationConfig(template_id="fixture",blur_probability=0,rotation_probability=0),0,tmp_path/family)
    annotation=result["annotations"][0]
    assert annotation["text"]==annotation["signature"]["text"]==("A Kumar" if family=="angular" else "Arun Kumar")
    assert annotation["signature"]["style"]==family


@pytest.mark.parametrize("family",signatures.PEN_STYLES)
def test_pen_morphology_is_seeded_and_varies_beyond_the_style_name(family):
    settings=RuleOptions(signature_style=family)
    reports=[];hashes=set()
    for seed in (1,12,42):
        layer,mask,info=signatures.render_signature((340,100),"Mira Dev",random.Random(seed),settings)
        assert info["engine"]=="pen-paths-v1" and info["generator_version"]=="signature-v3"
        assert info["stroke_count"]>0 and layer.getpixel((0,0))[3]==0
        left,top,right,bottom=mask.getbbox()
        assert 0<left<right<340 and 0<top<bottom<100
        reports.append((info["body_ratio"],info["compression"],info["slant"],info["baseline_rise"],info["allograph_variant"]))
        hashes.add(layer.tobytes())
    assert len(set(reports))==3 and len(hashes)==3
    if family=="stacked":assert info["layout"]=="stacked" and "\n" in info["text"]
    if family=="minimal":assert info["terminal"]=="none" and info["lettering_only"]


def test_batch_mixed_override_applies_to_fixed_saved_style_without_mutating_template(tmp_path):
    source=tmp_path/"source.png";Image.new("RGB",(500,180),"white").save(source)
    region=Region(id="sign",kind="signature",box=[20,20,450,120],confirmed=True,
        rule_options={"signature_style":"flourish","literal_text":"Arun Kumar"})
    fixed=GenerationConfig(template_id="fixture",seed=42,blur_probability=0,rotation_probability=0)
    varied=fixed.model_copy(update={"signature_style_override":"mixed"})
    before=region.model_dump()
    original=render_sample(source,[region],fixed,0,tmp_path/"fixed")["annotations"][0]["signature"]
    reports=[render_sample(source,[region],varied,i,tmp_path/f"mixed-{i}")["annotations"][0]["signature"] for i in range(5)]
    assert original["style"]=="flourish" and len({r["style"] for r in reports})>1
    assert any(r.get("engine")=="pen-paths-v1" for r in reports)
    assert region.model_dump()==before


def test_live_previews_validate_inputs_and_create_no_dataset(tmp_path):
    import io
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    app=create_app(f"sqlite:///{tmp_path/'preview.db'}",tmp_path,start_worker=False)
    with TestClient(app) as client:
        previews=client.get("/api/signatures/previews?style=mixed&seed=42").json()
        assert len(previews)==6
        response=client.get(previews[0]["url"])
        assert response.status_code==200 and response.headers["X-Signature-Style"]==previews[0]["style"]
        image=Image.open(io.BytesIO(response.content))
        assert image.mode=="RGBA" and image.size==(480,160) and image.getpixel((0,0))[3]==0
        assert client.get("/api/signatures/preview?style=unknown").status_code==422
        assert client.get("/api/signatures/preview?seed=-1").status_code==422
        assert client.get("/api/jobs").json()==[]


@pytest.mark.parametrize("family",["minimal","tall_initial","name"])
def test_random_pen_weight_is_seeded_thicker_and_keeps_lettering(family):
    options=RuleOptions(signature_style=family,text_color="#173574",ink_opacity_mode="fixed",ink_opacity=1)
    # Compare with the unweighted rendering using exactly the same RNG state.
    seen=set()
    for seed in range(20):
        layer,mask,info=signatures.render_signature((340,100),"Mira Dev",random.Random(seed),options)
        original,_,base=signatures._render_signature((340,100),"Mira Dev",random.Random(seed),options)
        seen.add(info["stroke_weight"])
        assert info["style"]==base["style"] and info["text"]==base["text"]
        if info["thickness_scale"]>1:
            assert np.asarray(layer.getchannel("A")).sum()>np.asarray(original.getchannel("A")).sum()*1.1
            assert layer.getpixel((0,0))[3]==0
            assert np.array_equal(np.asarray(mask)>0,np.asarray(layer.getchannel("A"))>0)
        else:assert layer.tobytes()==original.tobytes()
    assert seen=={"normal","medium","bold"}
    for weight in ("normal","bold"):
        fixed=options.model_copy(update={"font_weight":weight})
        layer,_,info=signatures.render_signature((340,100),"Mira Dev",random.Random(42),fixed)
        original,_,_=signatures._render_signature((340,100),"Mira Dev",random.Random(42),fixed)
        assert info["stroke_weight"]==weight and layer.tobytes()==original.tobytes()
