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
    families={signatures.signature_plan("Arun Kumar",random.Random(seed),RuleOptions())["style"] for seed in range(150)}
    assert families==set(signatures.STYLES)
    source=tmp_path/"source.png";Image.new("RGB",(500,200),"white").save(source)
    region=Region(id="signature",kind="signature",box=[35,35,420,110],confirmed=True,rule_options={"signature_style":"single_letter","literal_text":"Arun Kumar"})
    result=render_sample(source,[region],GenerationConfig(template_id="fixture",blur_probability=0,rotation_probability=0),0,tmp_path/"out")
    annotation=result["annotations"][0]
    assert len(annotation["text"])==1 and annotation["text"]==annotation["signature"]["text"]
    assert annotation["signature"]["style"]=="single_letter"
    assert annotation["signature"]["lettering_only"]
