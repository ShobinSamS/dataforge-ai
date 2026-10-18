import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend.app.main import create_app
from backend.app.db import Template,Job
from backend.app.schemas import Region,GenerationConfig
from backend.app.qr_capacity import qr_preflight,required_side,payload_bound
from backend.app.render import fictional_values


def test_effective_override_and_supported_payload_capacity():
    region=Region(id="qr",kind="qr",label="QR code",box=[20,20,128,122],confirmed=True,rule_options={"character_length":500})
    for default in (10,219):
        report=qr_preflight([region],GenerationConfig(template_id="fixture",qr_payload_length=default))
        qr=report["qr_regions"][0]
        assert not report["valid"] and qr["payload_characters"]==500 and qr["payload_source"]=="field length override"
        assert qr["required_size"]==219 and qr["max_automatic_characters"]<500
        assert "generation default does not override" in qr["error"]
    region=region.model_copy(update={"box":(20,20,219,219)})
    assert qr_preflight([region],GenerationConfig(template_id="fixture"))["valid"]
    assert qr_preflight([region],GenerationConfig(template_id="fixture",qr_codes=False))["valid"]
    assert not qr_preflight([],GenerationConfig(template_id="fixture",qr_required=True))["valid"]


@pytest.mark.parametrize("options",[
    {"character_length":500,"character_set":"alnum"},
    {"character_length":500,"character_set":"digits"},
    {"character_length":300,"character_set":"lower"},
    {"identifier_pattern":"INV-{upper:3}{digits:40}{lower:20}{alnum:70}-{year}"},
    {"literal_text":"Test αβγ / data"},
])
def test_capacity_bound_covers_seeded_values_and_padding(options):
    region=Region(id="qr",kind="qr",box=[20,20,500,500],rule_options=options)
    config=GenerationConfig(template_id="fixture",qr_padding=4)
    bound,_=payload_bound(region,config);required=required_side(bound,4)
    for seed in range(80):
        actual=fictional_values([region],seed,config)["qr"]
        assert required_side(actual,4)<=required
    assert required_side(bound,4)==required_side(bound,0)+24


def test_preflight_prevents_failed_job_and_checks_original_resume_snapshot(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'db.sqlite'}",tmp_path,start_worker=False)
    source=tmp_path/"source.png";Image.new("RGB",(500,500),"white").save(source)
    region=Region(id="qr",kind="qr",label="QR code",box=[20,20,128,122],confirmed=True,rule_options={"character_length":500})
    with app.state.sessions.begin() as db:
        db.add(Template(id="fixture",name="fixture",image_path=str(source),width=500,height=500,regions=[region.model_dump(mode="json")],privacy_confirmed=True))
    config={"template_id":"fixture","count":10,"qr_payload_length":219}
    with TestClient(app) as client:
        r=client.post("/api/jobs/preflight",json=config)
        assert r.status_code==200 and not r.json()["valid"]
        assert r.json()["qr_regions"][0]["payload_characters"]==500
        r=client.post("/api/jobs",json=config)
        assert r.status_code==422 and "219×219" in r.json()["detail"]
        assert client.get("/api/jobs").json()==[]
        with app.state.sessions.begin() as db:
            db.add(Job(id="old",template_id="fixture",name="Old failed job",status="failed",config=config,total=10,
                template_snapshot={"regions":[region.model_dump(mode="json")]}))
            t=db.get(Template,"fixture")
            t.regions=[region.model_copy(update={"box":(20,20,230,230)}).model_dump(mode="json")]
            t.revision+=1
        assert client.post("/api/jobs/preflight",json=config).json()["valid"]
        assert client.post("/api/jobs",json=config).status_code==201
        r=client.post("/api/jobs/old/resume")
        assert r.status_code==422 and "original QR settings" in r.json()["detail"]
        assert client.get("/api/jobs/old").json()["status"]=="failed"
