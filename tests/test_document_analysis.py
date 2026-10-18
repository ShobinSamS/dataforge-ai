import random
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image,ImageDraw
from backend.app import document_analysis as analysis
from backend.app.db import Template
from backend.app.main import create_app
from backend.app.schemas import Region, RuleOptions, GenerationConfig
from backend.app.render import asset, render_sample, fictional_values
from backend.app.fonts import cursive_font_id, load_font
from backend.app.vision_ocr import ruled_cells, detect_lines
from backend.app.privacy import sanitize_regions
from backend.app.pii_evidence import checked_value, rule_values


def grid():
    image=Image.new("RGB",(500,260),"white");draw=ImageDraw.Draw(image)
    for x in (20,230,480): draw.line((x,20,x,240),fill="black",width=2)
    for y in (20,90,165,240): draw.line((20,y,480,y),fill="black",width=2)
    return image


def test_grid_geometry_and_line_proposals():
    image=grid();cells=ruled_cells(image)
    assert len(cells)==6
    assert {(c["row"],c["column"]) for c in cells}=={(r,c) for r in range(3) for c in range(2)}
    assert all(20<c["box"][0]<480 and 20<c["box"][1]<240 for c in cells)
    blank=Image.new("RGB",(500,200),"white")
    assert detect_lines(blank)==[]
    ImageDraw.Draw(blank).text((25,30),"Arun Kumar",font=load_font(30,cursive_font_id()),fill="black")
    assert detect_lines(blank)
    # Long joined cursive strokes survive grid morphology as islands. They must
    # not make the enclosing cell disappear from the structural result.
    ImageDraw.Draw(image).text((35,175),"Arun Kumar",font=load_font(30,cursive_font_id()),fill="black")
    assert len(ruled_cells(image))==6


def test_pii_model_uses_only_trusted_source_geometry(monkeypatch):
    records=[Region(id="name",text="Applicant: Arun Kumar",box=[20,30,200,35]),Region(id="head",text="APPLICATION FORM",box=[20,5,250,20])]
    monkeypatch.setattr(analysis,"qwen_json",lambda *a,**kw:analysis.Findings(findings=[analysis.Finding(source_id="name",category="person",evidence="Arun Kumar",reason="Applicant name value")]))
    candidates,engine,warnings=analysis.find_pii(records,"local_qwen")
    assert engine=="local_qwen" and len(candidates)==1
    assert candidates[0]["box"]==[20,30,200,35] and candidates[0]["kind"]=="name"
    assert candidates[0]["action"]=="erase" and not candidates[0]["confirmed"]
    monkeypatch.setattr(analysis,"qwen_json",lambda *a,**kw:analysis.Findings(findings=[analysis.Finding(source_id="invented",category="person",evidence="Arun Kumar",reason="Applicant name value")]))
    candidates,engine,warnings=analysis.find_pii(records,"local_qwen")
    assert not candidates and engine=="regex_fallback" and warnings


def test_regex_evidence_wins_over_wrong_model_types_and_generic_titles(monkeypatch):
    records=[Region(id="email",text="Email: arun@example.invalid",box=[0,30,200,25]),Region(id="heading",text="APPLICATION FORM",box=[0,0,200,25])]
    monkeypatch.setattr(analysis,"qwen_json",lambda *a,**kw:analysis.Findings(findings=[analysis.Finding(source_id="email",category="address",evidence="arun@example.invalid",reason="Wrong type returned by model"),analysis.Finding(source_id="heading",category="other",evidence="APPLICATION FORM",reason="Wrong heading returned by model")]))
    candidates,_,_=analysis.find_pii(records,"local_qwen")
    assert len(candidates)==1 and candidates[0]["kind"]=="email"


def test_only_actual_identifier_and_date_values_survive_public_text(monkeypatch):
    texts=["AMOUNT:","ITEM","(RM)","INCOME TAX DEPARTMENT","GOVT. OF INDIA","e - Permanent Account Number Card","ABCDE1234Z","Name:","PAN CARD APPLY ONLINE","Date of Incorporation/Formation","19-04-2001","REFERENCE PURPOSE SAMPLE ONLY"]
    records=[Region(id=f"r{i}",text=t,box=[20,20+i*45,600,32],origin="ocr",confidence=.95) for i,t in enumerate(texts)]
    def wrong_model(*args,**kwargs):
        # Deliberately over-select everything. The validator must reject labels,
        # public text and invented quotes independently of model behavior.
        batch=args[1]["records"]
        return analysis.Findings(findings=[analysis.Finding(source_id=r["id"],category="identifier",evidence=r["text"],reason="Model over-selected") for r in batch])
    monkeypatch.setattr(analysis,"qwen_json",wrong_model)
    candidates,engine,_=analysis.find_pii(records,"local_qwen")
    assert engine=="local_qwen"
    assert {(r["pii_value"],r["kind"]) for r in candidates}=={("ABCDE1234Z","identifier"),("19-04-2001","date")}
    assert all(r["pii_reason"] and r["pii_value"] in r["text"] for r in candidates)
    snapshot=sanitize_regions(candidates)
    assert all(not r["pii_value"] and not r["pii_reason"] and not r["text"] for r in snapshot)
    assert not checked_value("Applicant: Arun Kumar","person","Made Up Person")
    assert not checked_value("PAN CARD APPLY ONLINE","person","PAN CARD APPLY ONLINE","Name")
    assert not checked_value("GOVT. OF INDIA","organization","GOVT. OF INDIA")
    assert not rule_values("31/02/2002")
    noise=Region(id="noise",text="ID: 87412954",box=[0,0,100,20],origin="ocr",confidence=.25)
    assert not analysis.find_pii([noise],"regex")[0]


def test_general_values_are_not_limited_to_one_document_type():
    for value,text,category,context in [
        ("AB1234567","Passport number: AB1234567","identifier",""),
        ("EMP-74219","Employee ID: EMP-74219","identifier",""),
        ("Arun Kumar","Applicant: Arun Kumar","person",""),
        ("24 Sample Road","24 Sample Road","address",""),
        ("arun@example.invalid","Email: arun@example.invalid","email",""),
    ]:
        assert checked_value(text,category,value,context)==value


def test_analysis_routes_draft_only_tables_and_model_failure(tmp_path,monkeypatch):
    app=create_app(f"sqlite:///{tmp_path/'db.sqlite'}",tmp_path,start_worker=False)
    image=grid();path=tmp_path/"page.png";image.save(path)
    records=[Region(id="email",text="arun@example.invalid",box=[35,40,170,25],origin="ocr",confidence=.95)]
    with app.state.sessions.begin() as db:
        db.add(Template(id="fixture",name="fixture",image_path=str(path),width=image.width,height=image.height,regions=[r.model_dump(mode="json") for r in records]))
    body={"regions":[r.model_dump(mode="json") for r in records],"engine":"regex"}
    with TestClient(app) as client:
        response=client.post("/api/templates/fixture/analyze-pii",json=body)
        assert response.status_code==200,response.text
        assert response.json()["candidates"][0]["kind"]=="email"
        saved=client.get("/api/templates/fixture").json()
        assert saved["revision"]==1 and saved["regions"][0]["id"]=="email" and not saved["privacy_confirmed"]
        response=client.post("/api/templates/fixture/extract-table",json=body)
        assert response.status_code==200,response.text
        cells=response.json()["cells"]
        assert len(cells)==6 and sum(bool(c["text"]) for c in cells)==1
        assert cells[0]["text"]=="arun@example.invalid"
        invalid={**body,"regions":[{**body["regions"][0],"box":[490,0,50,50]}]}
        assert client.post("/api/templates/fixture/analyze-pii",json=invalid).status_code==422
        monkeypatch.setattr(analysis,"qwen_json",lambda *a,**kw:analysis.TableLayout(cells=[analysis.TableCell(source_id="fake",row=0,column=0)]))
        assert client.post("/api/document-analysis/structure-table",json={"cells":[{"id":"a","text":"source only","row":0,"column":0}]}).status_code==422
        monkeypatch.setattr(analysis,"qwen_json",lambda *a,**kw:analysis.TableLayout(cells=[analysis.TableCell(source_id="a",row=0,column=0)]))
        result=client.post("/api/document-analysis/structure-table",json={"cells":[{"id":"a","text":"source only","row":1,"column":1}]}).json()
        assert result["cells"][0]["text"]=="source only" and result["cells"][0]["row"]==0


def test_transparent_codes_and_complete_cleanup(tmp_path):
    for kind,size in (("qr",(220,220)),("barcode",(400,100))):
        layer,mask=asset(kind,size,"SAMPLE123",random.Random(42),RuleOptions())
        alpha=np.asarray(layer)[:,:,3]
        assert np.any(alpha==0) and np.any(alpha==255)
        base=Image.new("RGB",size,"#bdd5dd");base.paste(layer,(0,0),layer)
        assert np.all(np.asarray(base)[alpha==0]==(189,213,221))
        assert mask.getbbox()==(0,0,*size)
    image=Image.new("RGB",(500,180),"#d4e3ef");ImageDraw.Draw(image).text((40,55),"PRIVATE ORIGINAL",font=load_font(28),fill="black")
    path=tmp_path/"source.png";image.save(path)
    region=Region(id="erase",box=[25,35,350,80],action="erase",confirmed=True)
    result=render_sample(path,[region],GenerationConfig(template_id="test",rotation_probability=0,blur_probability=0),0,tmp_path/"out")
    crop=np.asarray(result["image"])[35:115,25:375]
    assert np.all(crop==(212,227,239))
    assert result["erased_regions"][0]["box"]==[25,35,350,80]


def test_signature_has_alphabets_and_seal_variants(monkeypatch):
    texts=[];original=ImageDraw.ImageDraw.text
    def record(self,xy,text,*a,**kw): texts.append(text);return original(self,xy,text,*a,**kw)
    monkeypatch.setattr(ImageDraw.ImageDraw,"text",record)
    regions=[Region(id="person",kind="name",box=[0,0,300,60]),Region(id="sign",kind="signature",box=[0,0,300,80])]
    values=fictional_values(regions,42)
    assert values["person"]==values["sign"]
    layer,mask=asset("signature",(300,90),values["sign"],random.Random(42),RuleOptions(signature_style="initials"))
    assert any("." in text and any(c.isalpha() for c in text) for text in texts) and mask.getbbox()
    hashes=set()
    for shape in ("ring","round","rectangle","text"):
        for color in ("red","green","blue","mixed"):
            layer,mask=asset("seal",(240,180),"SAMPLE",random.Random(42),RuleOptions(seal_style=shape,seal_color=color))
            assert mask.getbbox() and layer.getpixel((0,0))[3]==0
            hashes.add(layer.tobytes())
    assert len(hashes)==16
