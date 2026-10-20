import base64
import io
import json
import random
import zipfile

import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.schemas import CLASS_NAMES, FieldType, RuleOptions, Region, GenerationConfig
from backend.app.stamps import plan_stamp, render_stamp, plan_rubber_stamp, render_rubber_stamp, stamp_artwork
from backend.app.document_rules import known_plan, apply_plan
from backend.app.render import optional_regions
from backend.app.main import create_app
from backend.app import ingest


def paper(options, seed=42, size=(180, 240)):
    return render_stamp(size, plan_stamp(options, seed), random.Random(seed), options)


def test_new_classes_append_without_moving_existing_ids():
    old=["text","name","address","date","email","phone","identifier","signature","seal","qr","barcode","portrait"]
    assert CLASS_NAMES[:12] == old
    assert CLASS_NAMES[12:14] == ["stamp","rubber_stamp"]
    assert CLASS_NAMES[14] == "drawing"
    assert FieldType.stamp != FieldType.seal != FieldType.rubber_stamp
    assert GenerationConfig(template_id="x").stamps and GenerationConfig(template_id="x").rubber_stamps


def test_default_black_no_pen_and_custom_print_controls():
    default=RuleOptions()
    image,mask,info=paper(default)
    assert info['palette']=='black' and info['ink_color']=='#000000'
    assert info['opacity']==1 and info['cancellation']=='none'
    assert np.any(np.max(np.asarray(image)[:,:,:3],axis=2)<30)
    custom=default.model_copy(update={'stamp_ink_mode':'custom','stamp_palette':'custom','stamp_color':'#19663a','ink_opacity_mode':'fixed','ink_opacity':.4})
    green,other,report=paper(custom)
    assert report['ink_color']=='#19663a' and report['opacity']==.4
    assert mask.tobytes()==other.tobytes() and image.tobytes()!=green.tobytes()
    from backend.app.jobs import snapshot_regions
    old=snapshot_regions({'regions':[{'id':'old','kind':'stamp','box':[0,0,100,100],'rule_options':{}}]})[0]
    assert old.rule_options.stamp_palette=='random' and old.rule_options.stamp_cancellation=='random' and old.rule_options.stamp_ink_mode=='custom'


@pytest.mark.parametrize("style", ["portrait","architecture","botanical","commemorative","revenue"])
def test_paper_stamps_have_opaque_paper_transparent_perforations_and_real_masks(style):
    options=RuleOptions(stamp_style=style,stamp_issuer="CEDAR POST",stamp_caption="HERITAGE SERIES",
                        stamp_denomination="15 P",stamp_cancellation="none")
    layer,mask,metadata=paper(options)
    assert layer.size == mask.size == (180,240)
    alpha=np.asarray(layer)[:,:,3]
    assert np.max(alpha)==255 and alpha[0,0]==0
    assert np.count_nonzero(alpha==0)>1500
    assert np.array_equal(np.asarray(mask)>0,alpha>0)
    assert metadata["style"]==style and metadata["text"]=="CEDAR POST\n15 P\nHERITAGE SERIES"
    assert "paper silhouette" in metadata["mask_semantics"]
    assert layer.tobytes()==paper(options)[0].tobytes()
    assert layer.tobytes()!=paper(options,seed=56)[0].tobytes()


def test_opacity_fades_print_not_paper_and_perforations_do_not_reshuffle_art():
    original=RuleOptions(stamp_style="portrait",stamp_palette="blue",stamp_cancellation="none",stamp_age=0,
                         ink_finish="clean",ink_opacity_mode="fixed",ink_opacity=1)
    a,mask,_=paper(original)
    faint,other,meta=paper(original.model_copy(update={"ink_opacity":.1}))
    assert np.array_equal(np.asarray(a)[:,:,3],np.asarray(faint)[:,:,3])
    assert mask.tobytes()==other.tobytes() and meta["opacity"]==.1
    assert a.getpixel((90,160))[3]==255 and faint.getpixel((90,160))[3]==255
    assert np.mean(np.abs(np.asarray(a).astype(float)-np.asarray(faint)))>2
    imperforate,solid,_=paper(original.model_copy(update={"stamp_perforated":False}))
    assert np.count_nonzero(np.asarray(solid))>np.count_nonzero(np.asarray(mask))
    assert np.array_equal(np.asarray(a)[35:-35,35:-35],np.asarray(imperforate)[35:-35,35:-35])


@pytest.mark.parametrize("cancellation",["postmark","waves","pen"])
def test_cancellation_changes_print_but_keeps_the_paper_mask(cancellation):
    options=RuleOptions(stamp_style="revenue",stamp_cancellation="none")
    blank,mask,_=paper(options)
    marked,other,meta=paper(options.model_copy(update={"stamp_cancellation":cancellation}))
    assert blank.tobytes()!=marked.tobytes()
    assert mask.tobytes()==other.tobytes()
    assert meta["cancellation"]==cancellation


@pytest.mark.parametrize("style",["boxed","text","round","dated","postmark","waves"])
def test_separate_rubber_marks_have_no_paper_and_seeded_ink(style):
    options=RuleOptions(rubber_stamp_style=style,rubber_stamp_mode="static",rubber_stamp_text="APPROVED")
    content=plan_rubber_stamp(options,42)
    a,mask,meta=render_rubber_stamp((300,180),content,random.Random(42),options)
    b,_,_=render_rubber_stamp((300,180),content,random.Random(42),options)
    assert a.tobytes()==b.tobytes()
    assert a.getpixel((0,0))[3]==0
    assert np.array_equal(np.asarray(mask)>0,np.asarray(a)[:,:,3]>0)
    assert np.count_nonzero(np.asarray(mask))<300*180*.65
    assert meta["engine"]=="rubber-stamp-v1"
    if style=="postmark": assert "POST OFFICE" in meta["text"] and content["date"] in meta["text"]
    elif style=="waves": assert not meta["text"]
    else: assert "APPROVED" in meta["text"]


def test_custom_rubber_wording_and_literal_plans_preserve_asset_controls():
    options=RuleOptions(rubber_stamp_mode="custom",rubber_stamp_format="{department}\n{date}\nREF {reference}")
    content=plan_rubber_stamp(options,42)
    assert "REF " in content["text"] and content["date"] in content["text"]
    with pytest.raises(ValueError): RuleOptions(rubber_stamp_format="{name.__class__}")
    for kind in ("stamp","rubber_stamp"):
        region=Region(id="new",kind=kind,box=(0,0,200,240),rule="literal:CUSTOM",
                      rule_options=RuleOptions(stamp_style="revenue",rubber_stamp_style="dated",ink_finish="worn"))
        planned=apply_plan(region,known_plan(region))
        assert planned.kind==kind and planned.rule_options.literal_text=="CUSTOM"
        assert planned.rule_options.stamp_style=="revenue" and planned.rule_options.rubber_stamp_style=="dated"
        assert planned.rule_options.ink_finish=="worn"


def test_independent_generation_toggles():
    regions=[Region(id=k,kind=k,box=(0,0,100,100)) for k in ("seal","stamp","rubber_stamp")]
    config=GenerationConfig(template_id="template",stamps=False,rubber_stamps=True,seals=False)
    assert [r.kind.value for r in optional_regions(500,500,regions,config)]==["rubber_stamp"]


def test_document_jobs_and_all_exports_keep_three_distinct_classes(tmp_path,monkeypatch):
    monkeypatch.setattr(ingest,"ocr",lambda image:([],"manual",[]))
    app=create_app(f"sqlite:///{tmp_path/'stamps.db'}",tmp_path,start_worker=False)
    with TestClient(app) as client:
        buffer=io.BytesIO();Image.new("RGB",(1000,600),"#e3e8e9").save(buffer,format="PNG")
        template=client.post("/api/templates",files={"file":("page.png",buffer.getvalue(),"image/png")}).json()
        regions=[Region(id="seal",kind="seal",box=(30,30,200,200),confirmed=True),
                 Region(id="postage",kind="stamp",box=(280,30,180,240),confirmed=True,
                        rule_options=RuleOptions(stamp_style="revenue",stamp_cancellation="pen")),
                 Region(id="rubber",kind="rubber_stamp",box=(500,30,300,180),confirmed=True,
                        rule_options=RuleOptions(rubber_stamp_mode="static",rubber_stamp_text="PAID"))]
        review=client.put(f"/api/templates/{template['id']}/review",json={"revision":1,"privacy_confirmed":True,
            "regions":[r.model_dump(mode="json") for r in regions]})
        assert review.status_code==200,review.text
        response=client.post("/api/jobs",json={"template_id":template["id"],"count":2,"seed":42,"blur_probability":0,"rotation_probability":0})
        assert response.status_code==201,response.text
        job=response.json();client.app.state.worker.run(job["id"])
        final=client.get(f"/api/jobs/{job['id']}").json()
        assert final["status"]=="completed",final
        sample=client.get(f"/api/jobs/{job['id']}/samples").json()[0]
        annotations=sample["annotations"]
        assert {(a["class"],a["class_id"]) for a in annotations}=={("seal",8),("stamp",12),("rubber_stamp",13)}
        for a in annotations:
            assert a["class"] in a
            if a["class"]!="seal": assert "seal" not in a and "typography" not in a
        for format_ in ("yolo","coco","ocr"):
            exported=client.post(f"/api/jobs/{job['id']}/exports",json={"format":format_,"review_confirmed":True})
            assert exported.status_code==201,exported.text
            raw=client.get(exported.json()["download_url"]).content
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                assert json.loads(archive.read("classes.json"))[12:14]==["stamp","rubber_stamp"]
                if format_=="yolo": assert {int(line.split()[0]) for line in archive.read("labels/000000.txt").decode().splitlines()}=={8,12,13}
                if format_=="coco": assert {a["category_id"] for a in json.loads(archive.read("annotations.json"))["annotations"]}=={8,12,13}


def test_standalone_stamp_artwork_pool_and_small_region_errors(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'pool.db'}",tmp_path,start_worker=False)
    with TestClient(app) as client:
        buffer=io.BytesIO();Image.new("RGB",(100,100),"#254162").save(buffer,format="PNG")
        upload=client.post("/api/portraits",files={"file":("photo.png",buffer.getvalue(),"image/png")},data={"rights_confirmed":"true"}).json()
        options=RuleOptions(stamp_style="portrait",portrait_source="asset_pool",portrait_asset_ids=[upload["id"]])
        response=client.post("/api/assets/generate",json={"kind":"stamp","width":180,"height":240,"options":options.model_dump(mode="json")})
        assert response.status_code==200,response.text
        metadata=response.json()["metadata"]
        assert metadata["kind"]=="stamp" and metadata["details"]["artwork_source"]=="approved_asset"
        assert metadata["details"]["asset_provenance"]["source"]=="user_uploaded"
        assert client.post("/api/assets/generate",json={"kind":"stamp","width":40,"height":40}).status_code==422
        assert client.post("/api/assets/generate",json={"kind":"rubber_stamp","options":{"rubber_stamp_mode":"static","rubber_stamp_text":""}}).status_code==422
