import io
import hashlib
import json

import cv2
import numpy as np
import pytest
import qrcode
from barcode import Code128
from barcode.writer import ImageWriter
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.app import visual_regions as visual
from backend.app import ingest as ingestion
from backend.app.main import create_app
from backend.app.resources import CPU_LOCK


def fixture_page():
    qr = qrcode.make("https://example.invalid/local-fixture").convert("RGB").resize((210, 210))
    output = io.BytesIO()
    Code128("TEST123456789", writer=ImageWriter()).write(output, options={
        "write_text": False, "module_height": 18, "module_width": .35, "quiet_zone": 3})
    bar = Image.open(output).convert("RGB").resize((400, 110))
    page = Image.new("RGB", (900, 650), "white")
    page.paste(qr, (50, 50))
    page.paste(bar, (350, 100))
    page.paste(bar.rotate(90, expand=True), (600, 230))
    return page


def test_real_codes_have_bounded_distinct_editable_proposals_and_no_payloads():
    page = fixture_page()
    first, warnings = visual.detect_visual_regions(page)
    second, _ = visual.detect_visual_regions(page)
    assert first == second
    assert [r["kind"] for r in first].count("qr") == 1
    assert [r["kind"] for r in first].count("barcode") == 2
    expected = [(50, 50, 210, 210), (350, 100, 400, 110), (600, 230, 110, 400)]
    for r, area in zip(first, expected):
        assert visual.coverage(r["box"], area) > .97
        assert not r["confirmed"] and r["origin"] == "visual"
        assert r["text"] == "" and r["replace"]
        assert r["box"][0]+r["box"][2] <= page.width
        assert r["box"][1]+r["box"][3] <= page.height
    assert warnings
    scaled = page.resize((2700, 1950))
    big, _ = visual.detect_visual_regions(scaled)
    assert {r["kind"] for r in big} == {"qr", "barcode"}
    assert all(r["box"][0]+r["box"][2] <= scaled.width for r in big)
    assert all(r["box"][1]+r["box"][3] <= scaled.height for r in big)


def test_text_table_and_blank_are_not_barcodes():
    page = Image.new("RGB", (800, 600), "white")
    assert visual.detect_visual_regions(page)[0] == []
    draw = ImageDraw.Draw(page)
    for y in range(30, 550, 30):
        draw.text((30, y), "Name Amount Item Invoice ABCDE1234Z 1234567890", fill="black")
        draw.line((400, y, 780, y), fill="black", width=2)
    for x in range(400, 780, 35):
        draw.line((x, 30, x, 550), fill="black", width=2)
    assert visual._barcode_boxes(np.asarray(page.convert("L"))) == []


def test_photo_prefers_enclosing_panel_and_clips_face_estimate(monkeypatch):
    monkeypatch.setattr(visual, "_detect_faces", lambda image: [(70, 60, 50, 50), (1, 220, 35, 40)])
    page = Image.new("RGB", (400, 300), "white")
    ImageDraw.Draw(page).rectangle((45, 35, 150, 185), outline="black", width=2)
    regions, _ = visual.detect_visual_regions(page)
    photos = [r for r in regions if r["kind"] == "portrait"]
    assert len(photos) == 2
    first = photos[0]["box"]
    assert 40 <= first[0] <= 47 and 29 <= first[1] <= 37
    assert first[2] > 100 and first[3] > 145
    assert photos[1]["box"][0] == 0
    assert photos[1]["box"][1]+photos[1]["box"][3] == 300
    assert all("estimated" in r["label"] for r in photos)


def test_upload_and_rescan_are_reviewable_without_mutating_saved_regions(tmp_path, monkeypatch):
    monkeypatch.setattr(ingestion, "ocr", lambda image: ([], "manual", []))
    app = create_app(f"sqlite:///{tmp_path/'visual.db'}", tmp_path, start_worker=False)
    output = io.BytesIO()
    fixture_page().save(output, format="PNG")
    with TestClient(app) as client:
        uploaded = client.post("/api/templates", files={"file": ("codes.png", output.getvalue(), "image/png")})
        assert uploaded.status_code == 201, uploaded.text
        template = uploaded.json()
        assert len(template["regions"]) == 3
        assert not template["privacy_confirmed"]
        url = f"/api/templates/{template['id']}"
        before = client.get(url).json()
        found = client.post(url+"/detect-visual-regions")
        assert found.status_code == 200
        assert found.json()["candidates"] == template["regions"]
        assert client.get(url).json() == before
        # Incorrect boxes are deletable; the resulting draft remains editable.
        kept = template["regions"][1:]
        kept[0].update(label="Custom barcode", kind="barcode")
        saved = client.put(url+"/review", json={"revision": 1, "regions": kept, "privacy_confirmed": False})
        assert saved.status_code == 200, saved.text
        assert len(saved.json()["regions"]) == 2
        with CPU_LOCK:
            assert client.post(url+"/detect-visual-regions").status_code == 409
        assert client.post("/api/templates/missing/detect-visual-regions").status_code == 404
        assert client.delete(url+"?revision=2").status_code == 200
        assert client.post(url+"/detect-visual-regions").status_code == 404


def test_upload_detector_failure_keeps_ocr_and_upload(tmp_path, monkeypatch):
    text = {"id": "ocr", "box": [5, 5, 30, 10], "text": "Heading"}
    monkeypatch.setattr(ingestion, "ocr", lambda image: ([text], "test", []))
    def fail(image): raise RuntimeError("unavailable")
    monkeypatch.setattr(ingestion, "detect_visual_regions", fail)
    content = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(content, format="PNG")
    result = ingestion.ingest(content.getvalue(), ".png", tmp_path/"page.png")
    assert result[2] == [text]
    assert any("could not finish" in w for w in result[4])
    with CPU_LOCK:
        result = ingestion.ingest(content.getvalue(), ".png", tmp_path/"page2.png")
    assert result[2] == [text]
    assert any("busy" in w for w in result[4])


def test_upload_merge_removes_only_text_owned_by_visual_box():
    inside = {"id": "inside", "box": [15, 15, 40, 15]}
    outside = {"id": "outside", "box": [180, 15, 40, 15]}
    code = {"id": "code", "box": [10, 10, 100, 100]}
    assert visual.merge_upload_regions([inside, outside], [code]) == [code, outside]


def test_bundled_face_model_integrity_and_runtime():
    provenance = json.loads((visual.FACE_MODEL.parent/"source.json").read_text())
    assert hashlib.sha256(visual.FACE_MODEL.read_bytes()).hexdigest() == provenance["sha256"]
    assert visual._detect_faces(np.full((300, 400, 3), 255, dtype=np.uint8)) == []


@pytest.mark.parametrize("word", ["RECEIVED", "PAID", "APPROVED", "REJECTED", "COPY", "CONFIDENTIAL"])
def test_stamp_presets_render_in_existing_seal_class(word):
    import random
    from backend.app.schemas import RuleOptions
    from backend.app.seals import plan_seal_content, render_seal
    options = RuleOptions(seal_text_mode="static", seal_text=word, seal_subtext="",
                          seal_style="rectangle", seal_border="double", seal_symbol="none",
                          ink_opacity_mode="fixed")
    content = plan_seal_content(options, 42, "stamp")
    layer, mask, info = render_seal((300, 110), content, random.Random(42), options)
    assert word in info["text"]
    assert layer.getpixel((0, 0))[3] == 0
    assert np.any(np.asarray(mask) > 0)
