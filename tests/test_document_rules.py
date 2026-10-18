import io
import json
import re
import zipfile
from datetime import date, datetime
from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.app.config import settings
from backend.app.document_rules import RulePlan, apply_plan, known_plan, normalize_regions
from backend.app.main import create_app
from backend.app.portraits import fetch_configured_portrait, portrait_metadata
from backend.app.privacy import check_review
from backend.app.render import fictional_values, render_sample
from backend.app.schemas import CLASS_NAMES, GenerationConfig, Region, RuleOptions
from backend.app.validation import validate


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path/'test.db'}", tmp_path, start_worker=False)) as value:
        yield value


def region(**kw):
    return Region.model_validate({"id": "field", "box": [20, 20, 180, 130], **kw})


@pytest.mark.parametrize("prompt,kind,action", [
    ("dd/mm/yyyy", "date", "replace"),
    ("a human photo has to be placed", "portrait", "replace"),
    ("remove this completely", "text", "erase"),
    ("PAN number", "identifier", "replace"),
    ("pan card pattern", "identifier", "replace"),
    ("pancard format", "identifier", "replace"),
    ("permanent account number format", "identifier", "replace"),
    ("literal:Fictional school", "text", "replace"),
])
def test_original_error_prompts_and_shorthand(client, prompt, kind, action):
    r = region(rule=prompt, confirmed=True)
    response = client.post("/api/document-rules/interpret", json={"region": r.model_dump(mode="json")})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["engine"] == "deterministic"
    assert result["region"]["kind"] == kind and result["region"]["action"] == action
    assert not result["region"]["confirmed"]
    assert result["region"]["rule_resolved_hash"]


def test_date_pattern_and_legacy_literal_values():
    a = region(rule="DOB between 1980 and 2000 in dd/mm/yyyy")
    a = apply_plan(a, known_plan(a))
    b = Region.model_validate({**a.model_dump(), "id": "iso", "rule": "", "rule_options": {**a.rule_options.model_dump(), "date_format": "yyyy-mm-dd"}})
    pan = region(id="pan", rule="PAN format")
    pan = apply_plan(pan, known_plan(pan))
    legacy = region(id="old", kind="date", rule="literal:01/02/1990")
    for seed in [2, 42, 78]:
        values = fictional_values([a, b, pan, legacy], seed)
        parsed = datetime.strptime(values[a.id], "%d/%m/%Y").date()
        assert date(1980, 1, 1) <= parsed <= date(2000, 12, 31)
        assert parsed.isoformat() == values["iso"]
        assert re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", values["pan"])
        assert values["old"] == "01/02/1990"
        assert values == fictional_values([a, b, pan, legacy], seed)
    assert known_plan(region(rule="company name")) is None
    with pytest.raises(ValueError): RuleOptions(date_start="2000-01-01", date_end="1990-01-01")
    with pytest.raises(ValueError): RuleOptions(identifier_pattern="../evil")


def test_strict_review_preserves_draft_but_rejects_unresolved_rules():
    r = region(rule="Use a made up business tagline", confirmed=True)
    assert normalize_regions([r], strict=False)[0].rule == r.rule
    with pytest.raises(ValueError, match="Interpret the prompt"):
        normalize_regions([r], strict=True)
    erased = normalize_regions([region(rule="remove this completely", confirmed=True)], strict=True)[0]
    check_review([erased], 400, 300, True)
    with pytest.raises(ValueError, match="replaced or erased"):
        check_review([region(action="keep", confirmed=True)], 400, 300, True)


def test_local_plan_uses_existing_assets_only(client, monkeypatch):
    from backend.app import main
    from backend.app.local_llm import LocalLLM
    calls = []
    monkeypatch.setattr(main.psutil, "virtual_memory", lambda: SimpleNamespace(available=16*1024**3))
    monkeypatch.setattr(LocalLLM, "resident_cpu_mb", lambda self: 0)
    def mock_plan(r):
        calls.append(r.rule)
        return RulePlan(kind="date", options=RuleOptions(date_format="dd/mm/yyyy", date_start="1980-01-01", date_end="1999-12-31"), explanation="DOB plan")
    monkeypatch.setattr(main, "interpret_local", mock_plan)
    r = region(rule="Pick a date of birth for an adult")
    response = client.post("/api/document-rules/interpret", json={"region": r.model_dump(mode="json"), "engine": "local_llm"})
    assert response.status_code == 200, response.text
    assert response.json()["engine"] == "local_qwen" and calls == [r.rule]
    assert response.json()["region"]["rule_options"]["date_start"] == "1980-01-01"
    selected = "a"*32
    r = region(rule="use pool", rule_options={"portrait_asset_ids": [selected]})
    result = apply_plan(r, RulePlan(kind="portrait", options=RuleOptions(portrait_source="asset_pool", portrait_asset_ids=["b"*32])))
    assert result.rule_options.portrait_asset_ids == [selected]
    with pytest.raises(ValueError): apply_plan(r, RulePlan(supported=False, explanation="Unsupported operation"))


@pytest.mark.parametrize("kind,valid", [("text", False), ("date", True)])
def test_local_plan_schema_and_type_coherence(monkeypatch, kind, valid):
    from backend.app import document_rules
    sent = []
    class MockLLM:
        def __init__(self): self.client = self
        def status(self): return {"installed": True}
        def close(self): pass
        def post(self, path, json):
            sent.append(json)
            plan = RulePlan(kind=kind, options=RuleOptions(date_format="dd/mm/yyyy", date_start="1980-01-01", date_end="2000-12-31"))
            return httpx.Response(200, request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"), json={"message": {"content": plan.model_dump_json()}})
    monkeypatch.setattr(document_rules, "LocalLLM", MockLLM)
    if valid:
        assert document_rules.interpret_local(region(rule="Create a birth date")).kind == "date"
    else:
        with pytest.raises(ValueError, match="Date options require"):
            document_rules.interpret_local(region(rule="Create a birth date"))
    assert "kind" in sent[0]["format"]["required"]
    assert sent[0]["options"]["num_gpu"] == 0
    assert "box" not in sent[0]["messages"][1]["content"]


def test_pan_qwen_discards_invented_assets_and_literal_options(monkeypatch):
    from backend.app import document_rules
    sent = []
    class MockLLM:
        def __init__(self): self.client = self
        def status(self): return {"installed": True}
        def close(self): pass
        def post(self, path, json):
            sent.append(json)
            payload = {"supported": True, "action": "replace", "kind": "identifier", "options": {
                "identifier_pattern": "AAAAA9999A", "portrait_asset_ids": ["asset_pool_123456789"],
                "literal_text": "PAN", "date_start": "irrelevant-invalid-date"}, "explanation": "Use the referenced format"}
            return httpx.Response(200, request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"), json={"message": {"content": __import__('json').dumps(payload)}})
    monkeypatch.setattr(document_rules, "LocalLLM", MockLLM)
    r = region(rule="pan card pattern")
    plan = document_rules.interpret_local(r)
    result = apply_plan(r, plan)
    assert re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", fictional_values([result], 42)[r.id])
    properties = sent[0]["format"]["$defs"]["RuleOptions"]["properties"]
    assert set(properties) == {"identifier_pattern"}
    assert "verified_format_references" in sent[0]["messages"][1]["content"]


def test_generic_qwen_repairs_unrequested_prefix(monkeypatch):
    from backend.app import document_rules
    calls=[]
    class MockLLM:
        def __init__(self): self.client=self
        def status(self): return {"installed":True}
        def close(self): pass
        def post(self,path,json):
            calls.append(json)
            pattern="INV-{lower:4}-{digits:8}" if len(calls)==1 else "{lower:4}{digits:8}"
            plan=RulePlan(kind="identifier",options=RuleOptions(identifier_pattern=pattern))
            return httpx.Response(200,request=httpx.Request("POST","http://127.0.0.1:11434/api/chat"),json={"message":{"content":plan.model_dump_json()}})
    monkeypatch.setattr(document_rules,"LocalLLM",MockLLM)
    r=region(rule="Generate a serial number with 4 lowercase letters followed by 8 digits")
    result=apply_plan(r,document_rules.interpret_local(r))
    assert len(calls)==2
    assert re.fullmatch(r"[a-z]{4}[0-9]{8}",fictional_values([result],42)[r.id])


@pytest.mark.parametrize("failure", [ValueError("invalid model output"), RuntimeError("local model unavailable")])
def test_forced_qwen_known_format_falls_back_transparently(client, monkeypatch, failure):
    from backend.app import main
    from backend.app.local_llm import LocalLLM
    monkeypatch.setattr(main.psutil, "virtual_memory", lambda: SimpleNamespace(available=16*1024**3))
    monkeypatch.setattr(LocalLLM, "resident_cpu_mb", lambda self: 0)
    def fail(r): raise failure
    monkeypatch.setattr(main, "interpret_local", fail)
    response = client.post("/api/document-rules/interpret", json={"region": region(rule="pan card pattern").model_dump(mode="json"), "engine": "local_llm"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["engine"] == "known_rule_fallback"
    assert result["region"]["rule_options"]["identifier_pattern"] == "AAAAA9999A"
    assert result["references"][0]["url"].startswith("https://traces61contents.tdscpc.gov.in/")
    assert "Local Qwen did not return" in result["warnings"][0]
    response = client.post("/api/document-rules/interpret", json={"region": region(rule="Unrecognized complex operation").model_dump(mode="json"), "engine": "local_llm"})
    assert response.status_code == 422
    assert "No rule was applied" in response.json()["detail"]


def test_erase_and_portrait_rendering(tmp_path):
    source = tmp_path/"source.png"
    image = Image.new("RGB", (500, 300), "white")
    ImageDraw.Draw(image).rectangle((30, 30, 150, 100), fill="red")
    image.save(source)
    regions = [region(id="erase", box=[20, 20, 150, 100], action="erase", confirmed=True),
               region(id="face", kind="portrait", box=[250, 30, 150, 200], confirmed=True)]
    config = GenerationConfig(template_id="test", rotation_probability=0, blur_probability=0)
    result = render_sample(source, regions, config, 0, tmp_path/"render")
    assert np.all(np.asarray(result["image"])[30:100, 30:150] == 255)
    assert len(result["annotations"]) == 1
    annotation = result["annotations"][0]
    assert annotation["class"] == "portrait" and annotation["bbox"] == [250, 30, 150, 200]
    assert annotation["asset_provenance"]["source"] == "fictional_procedural_illustration"
    assert result["erased_regions"][0]["coordinate_space"] == "source_page"
    assert validate(result, tmp_path/"render", 1)["passed"]
    repeated = render_sample(source, regions, config, 0, tmp_path/"repeated")
    assert result["sha256"] == repeated["sha256"]
    another = render_sample(source, regions, config, 1, tmp_path/"another")
    assert result["sha256"] != another["sha256"]
    assert CLASS_NAMES[:11] == ["text", "name", "address", "date", "email", "phone", "identifier", "signature", "seal", "qr", "barcode"]


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (80, 100), "#345678").save(buffer, format="PNG")
    return buffer.getvalue()


def test_portrait_pool_upload_and_integrity(client, tmp_path):
    files = {"file": ("face.png", png_bytes(), "image/png")}
    assert client.post("/api/portraits", files=files).status_code == 422
    assert client.post("/api/portraits", files={"file": ("bad.png", b"bad", "image/png")}, data={"rights_confirmed": "true"}).status_code == 422
    response = client.post("/api/portraits", files=files, data={"rights_confirmed": "true", "license_note": "Fixture authored here"})
    assert response.status_code == 201, response.text
    record = response.json()
    assert client.get(record["preview_url"]).status_code == 200
    source = tmp_path/"source.png"
    Image.new("RGB", (500, 300), "white").save(source)
    r = region(kind="portrait", rule_options={"portrait_source": "asset_pool", "portrait_asset_ids": [record["id"]]})
    result = render_sample(source, [r], GenerationConfig(template_id="test", rotation_probability=0, blur_probability=0), 0, tmp_path/"render", asset_root=tmp_path)
    assert result["image"].getpixel((40, 40)) == (0x34, 0x56, 0x78)
    assert result["annotations"][0]["asset_provenance"]["sha256"] == record["sha256"]
    with pytest.raises(ValueError): portrait_metadata(tmp_path, "../escape")
    (tmp_path/"portraits"/record["id"]/"image.png").write_bytes(b"corrupted")
    assert client.get(record["preview_url"]).status_code == 422


def test_portrait_network_is_explicit_and_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_online_portraits", False)
    monkeypatch.setattr(settings, "portrait_provider_url", "")
    assert not client.get("/api/portraits/capabilities").json()["online_configured"]
    assert client.post("/api/portraits/fetch", json={}).status_code == 422
    assert client.post("/api/portraits/fetch", json={"confirm_online": True, "rights_confirmed": True}).status_code == 422
    with pytest.raises(ValueError, match="No approved"):
        fetch_configured_portrait()
    monkeypatch.setattr(settings, "allow_online_portraits", True)
    monkeypatch.setattr(settings, "portrait_provider_url", "https://provider.example/portrait.png")
    import backend.app.portraits as portraits
    monkeypatch.setattr(portraits.socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("8.8.8.8", 443))])
    real_client = httpx.Client
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, headers={"Content-Type": "image/png"}, content=png_bytes())
    monkeypatch.setattr(portraits.httpx, "Client", lambda **kw: real_client(**kw, transport=httpx.MockTransport(handle)))
    content, url = fetch_configured_portrait()
    assert content == png_bytes() and url.endswith("portrait.png")
    assert len(requests) == 1 and requests[0].method == "GET" and not requests[0].content
    monkeypatch.setattr(portraits.socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="public internet"):
        fetch_configured_portrait()


def test_erase_only_review_job_and_exports(client):
    t = client.post("/api/templates/demo").json()
    for r in t["regions"]:
        r.update(rule="remove this completely", confirmed=True)
    response = client.put(f"/api/templates/{t['id']}/review", json={"regions": t["regions"], "privacy_confirmed": True, "revision": t["revision"]})
    assert response.status_code == 200, response.text
    assert all(r["action"] == "erase" for r in response.json()["regions"])
    response = client.post("/api/jobs", json={"template_id": t["id"], "count": 1, "rotation_probability": 0, "blur_probability": 0})
    assert response.status_code == 201, response.text
    job = response.json()["id"]
    client.app.state.worker.run(job)
    assert client.get(f"/api/jobs/{job}").json()["status"] == "completed"
    assert client.get(f"/api/jobs/{job}/samples").json()[0]["annotations"] == []
    export = client.post(f"/api/jobs/{job}/exports", json={"format": "yolo", "review_confirmed": True})
    assert export.status_code == 201, export.text
    with zipfile.ZipFile(io.BytesIO(client.get(export.json()["download_url"]).content)) as z:
        assert z.read("labels/000000.txt") == b""
        meta = json.loads(z.read("metadata/000000.json"))
        assert meta["annotations"] == [] and len(meta["erased_regions"]) == len(t["regions"])
        assert b"remove this completely" not in z.read("dataset.json")


def test_mixed_rule_job_with_portrait_date_id_and_erase(client):
    t = client.post("/api/templates/demo").json()
    regions = [
        region(id="dob", box=[50, 50, 300, 60], rule="DOB between 1980 and 2000 in dd/mm/yyyy", confirmed=True),
        region(id="pan", box=[50, 150, 300, 60], rule="PAN number", confirmed=True),
        region(id="portrait", box=[550, 50, 150, 200], rule="a human photo has to be placed", confirmed=True),
        region(id="erase", box=[50, 300, 300, 60], rule="remove this completely", confirmed=True),
    ]
    response = client.put(f"/api/templates/{t['id']}/review", json={"regions": [r.model_dump(mode="json") for r in regions], "privacy_confirmed": True, "revision": 1})
    assert response.status_code == 200, response.text
    job = client.post("/api/jobs", json={"template_id": t["id"], "count": 2, "blur_probability": 0, "rotation_probability": 0}).json()["id"]
    client.app.state.worker.run(job)
    assert client.get(f"/api/jobs/{job}").json()["status"] == "completed"
    samples = client.get(f"/api/jobs/{job}/samples").json()
    for sample in samples:
        annotations = {a["class"]: a for a in sample["annotations"]}
        assert set(annotations) == {"date", "identifier", "portrait"}
        assert re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", annotations["identifier"]["text"])
        assert 1980 <= datetime.strptime(annotations["date"]["text"], "%d/%m/%Y").year <= 2000
    for format_ in ["yolo", "coco", "ocr"]:
        export = client.post(f"/api/jobs/{job}/exports", json={"format": format_, "review_confirmed": True})
        assert export.status_code == 201, export.text
        with zipfile.ZipFile(io.BytesIO(client.get(export.json()["download_url"]).content)) as z:
            record = json.loads(z.read("metadata/000000.json"))
            assert len(record["annotations"]) == 3 and len(record["erased_regions"]) == 1
            assert next(a for a in record["annotations"] if a["class"] == "portrait")["asset_provenance"]["source"] == "fictional_procedural_illustration"
