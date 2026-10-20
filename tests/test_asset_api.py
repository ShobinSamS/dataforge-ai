import base64
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import create_app


@pytest.fixture
def assets(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path/'assets.db'}", tmp_path, start_worker=False)) as client:
        yield client


@pytest.mark.parametrize("kind,value,options", [
    ("signature", "Mira Dev", {"signature_style": "interwoven"}),
    ("seal", None, {"seal_style": "corporate"}),
    ("stamp", "REVENUE", {"stamp_style": "revenue", "stamp_palette": "red"}),
    ("rubber_stamp", "PAID", {"rubber_stamp_style": "boxed", "rubber_stamp_mode": "static"}),
    ("qr", "LOCAL-TEST", {}), ("barcode", "TEST-1234", {}),
    ("text", "Example text", {"font_weight": "bold"}), ("portrait", None, {}),
])
def test_standalone_assets_are_real_pngs_with_masks_and_no_saved_datasets(assets, kind, value, options):
    body = {"kind": kind, "width": 480, "height": 300, "seed": 42, "options": options}
    if value is not None: body["value"] = value
    first = assets.post("/api/assets/generate", json=body)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result == assets.post("/api/assets/generate", json=body).json()
    image = Image.open(io.BytesIO(base64.b64decode(result["image"].split(",", 1)[1])))
    mask = Image.open(io.BytesIO(base64.b64decode(result["mask"].split(",", 1)[1])))
    assert image.size == mask.size == (480, 300)
    assert image.mode == "RGBA" and mask.getbbox()
    assert result["metadata"]["kind"] == kind
    assert not result["metadata"]["saved"]
    if kind not in {"qr", "barcode", "portrait"}:
        assert np.array_equal(np.asarray(mask) > 0, np.asarray(image)[:, :, 3] > 0)
    assert assets.get("/api/templates").json() == []
    assert assets.get("/api/jobs").json() == []


@pytest.mark.parametrize("body", [
    {"kind": "bad"}, {"kind": "signature", "value": "1234"},
    {"kind": "signature", "value": "a"*101}, {"kind": "text", "width": 0},
    {"kind": "qr", "value": "a"*501}, {"kind": "qr", "value": "x"*500, "width": 16, "height": 16},
    {"kind": "barcode", "value": "हिन्दी"}, {"kind": "barcode", "value": "X"*129},
    {"kind": "signature", "options": {"character_length": 10}},
    {"kind": "portrait", "options": {"portrait_source": "asset_pool"}},
])
def test_invalid_asset_requests_fail_cleanly(assets, body):
    response = assets.post("/api/assets/generate", json=body)
    assert response.status_code == 422, response.text


def test_approved_portrait_pool_is_supported(assets):
    buffer = io.BytesIO(); Image.new("RGB", (100, 100), "#ca6633").save(buffer, format="PNG")
    imported = assets.post("/api/portraits", files={"file": ("photo.png", buffer.getvalue(), "image/png")},
                           data={"rights_confirmed": "true"})
    assert imported.status_code == 201
    response = assets.post("/api/assets/generate", json={"kind": "portrait", "options": {
        "portrait_source": "asset_pool", "portrait_asset_ids": [imported.json()["id"]]}})
    assert response.status_code == 200
    assert response.json()["metadata"]["details"]["source"] == "user_uploaded"
