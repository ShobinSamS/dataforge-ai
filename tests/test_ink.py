"""Opacity must affect compositing, never lettering, labels or masks."""
import io
import base64
import random

import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.ink import apply_ink_opacity
from backend.app.main import create_app
from backend.app.schemas import RuleOptions, Region, GenerationConfig
from backend.app.signatures import render_signature
from backend.app.seals import plan_seal_content, render_seal
from backend.app.render import render_sample


def render(kind, options, seed=42):
    if kind == "signature":
        return render_signature((360, 120), "Mira Dev", random.Random(seed), options)
    return render_seal((240, 240), plan_seal_content(options, seed), random.Random(seed), options)


@pytest.mark.parametrize("kind", ["signature", "seal"])
def test_fixed_opacity_changes_only_alpha_and_preserves_every_mask_pixel(kind):
    options = RuleOptions(signature_style="interwoven", seal_style="double_ring", ink_opacity_mode="fixed")
    strong, strong_mask, strong_info = render(kind, options)
    for opacity in (.05, .25, .55, 1):
        layer, mask, info = render(kind, options.model_copy(update={"ink_opacity": opacity}))
        expected = np.asarray(strong.getchannel("A"))
        expected = np.where(expected == 0, 0, np.maximum(1, np.rint(expected * opacity))).astype(np.uint8)
        assert np.array_equal(np.asarray(layer.getchannel("A")), expected)
        assert np.array_equal(np.asarray(layer)[:, :, :3], np.asarray(strong)[:, :, :3])
        assert mask.tobytes() == strong_mask.tobytes()
        assert {k: v for k, v in info.items() if k != "opacity"} == {k: v for k, v in strong_info.items() if k != "opacity"}
        assert info["opacity"] == opacity and info["opacity_mode"] == "fixed"
        assert layer.getpixel((0, 0))[3] == 0


@pytest.mark.parametrize("kind", ["signature", "seal"])
def test_random_opacity_is_reproducible_varied_bounded_and_independent_of_design(kind):
    options = RuleOptions(ink_opacity_min=.2, ink_opacity_max=.8)
    seen = set()
    for seed in range(12):
        layer, mask, info = render(kind, options, seed)
        same, _, same_info = render(kind, options, seed)
        solid, solid_mask, solid_info = render(kind, options.model_copy(update={"ink_opacity_mode": "fixed"}), seed)
        assert layer.tobytes() == same.tobytes() and info == same_info
        assert .2 <= info["opacity"] <= .8 and info["opacity_mode"] == "random"
        assert mask.tobytes() == solid_mask.tobytes()
        assert {k: v for k, v in info.items() if not k.startswith("opacity")} == {k: v for k, v in solid_info.items() if not k.startswith("opacity")}
        assert np.asarray(layer.getchannel("A")).sum() < np.asarray(solid.getchannel("A")).sum()
        seen.add(info["opacity"])
    assert len(seen) == 12 and min(seen) < .4 and max(seen) > .6


def test_opacity_does_not_advance_rng_and_handles_narrow_valid_ranges():
    rng = random.Random(42)
    before = rng.getstate()
    layer = Image.new("RGBA", (4, 4), (20, 60, 150, 255))
    _, _, info = apply_ink_opacity(layer, rng, RuleOptions(ink_opacity_min=.05123, ink_opacity_max=.05124), "fixture")
    assert rng.getstate() == before
    assert .05123 <= info["opacity"] <= .05124
    assert RuleOptions().ink_opacity_mode == "random"
    assert (RuleOptions().ink_opacity_min, RuleOptions().ink_opacity_max) == (.45, 1)


@pytest.mark.parametrize("patch", [
    {"ink_opacity": 0}, {"ink_opacity": 1.01}, {"ink_opacity": float("nan")},
    {"ink_opacity_min": -.1}, {"ink_opacity_max": 2},
    {"ink_opacity_min": .8, "ink_opacity_max": .4}, {"ink_opacity_mode": "unknown"},
])
def test_invalid_opacity_is_rejected(patch):
    with pytest.raises(ValueError):
        RuleOptions(**patch)


def test_previews_respect_opacity_settings_and_reject_invalid_ranges(tmp_path):
    app = create_app(f"sqlite:///{tmp_path/'preview.db'}", tmp_path, start_worker=False)
    with TestClient(app) as client:
        previews = client.get("/api/signatures/previews?style=enclosed&ink_opacity_mode=fixed&ink_opacity=0.25").json()
        response = client.get(previews[0]["url"])
        assert response.status_code == 200 and response.headers["X-Ink-Opacity"] == "0.25"
        layer = Image.open(io.BytesIO(response.content))
        assert 0 < layer.getchannel("A").getextrema()[1] <= 64
        response = client.post("/api/seals/preview", json={"options": {"ink_opacity_mode": "fixed", "ink_opacity": .25}})
        data = response.json()
        assert response.status_code == 200 and data["metadata"]["opacity"] == .25
        layer = Image.open(io.BytesIO(base64.b64decode(data["image"].split(",", 1)[1])))
        assert 0 < layer.getchannel("A").getextrema()[1] <= 64
        assert client.get("/api/signatures/preview?ink_opacity=0").status_code == 422
        assert client.get("/api/signatures/previews?ink_opacity_min=0.9&ink_opacity_max=0.2").status_code == 422
        assert client.post("/api/seals/preview", json={"options": {"ink_opacity": 2}}).status_code == 422
        assert client.get("/api/jobs").json() == []


def test_faded_ink_composites_without_paper_rectangle_and_exports_opacity(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (620, 280), "#b7d7d5").save(source)
    regions = [Region(id=kind, kind=kind, box=box, confirmed=True,
                      rule_options={"signature_style": "interwoven", "seal_style": "ring", "ink_opacity_mode": "fixed", "ink_opacity": .25})
               for kind, box in [("signature", [20, 40, 300, 120]), ("seal", [350, 30, 240, 240])]]
    config = GenerationConfig(template_id="fixture", blur_probability=0, rotation_probability=0)
    result = render_sample(source, regions, config, 0, tmp_path / "out")
    for annotation in result["annotations"]:
        assert annotation[annotation["class"]]["opacity"] == .25
        assert annotation[annotation["class"]]["opacity_mode"] == "fixed"
        assert annotation["text"] == annotation[annotation["class"]]["text"]
    assert result["image"].getpixel((21, 41)) == (183, 215, 213)
    assert result["image"].getpixel((351, 31)) == (183, 215, 213)
