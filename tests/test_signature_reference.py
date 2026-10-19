"""Reviewed raster regression cases for the user's sign7 composition sheet.

The fixture contains only generated fictional signatures, never reference crops.
Font selection is explicit: pen-path cases must work without system script fonts.
"""
import json
import random
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from backend.app.schemas import RuleOptions
from backend.app.signatures import render_signature

FIXTURES = Path(__file__).parent / "fixtures"
CASES = json.loads((FIXTURES / "sign7-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[case["cell"] for case in CASES])
def test_reference_compositions_retain_reviewed_geometry_and_connected_ink(case):
    index = CASES.index(case)
    options = RuleOptions(signature_style=case["style"], font_weight="normal", font_id="arial",
                          ink_opacity_mode="fixed", ink_opacity=1)
    layer, mask, info = render_signature((440, 150), case["name"], random.Random(case["seed"]), options)
    thumbnail = np.asarray(mask.resize((220, 75), Image.Resampling.BOX)) >= 128
    with Image.open(FIXTURES / "sign7-geometry.png") as baseline:
        x, y = index % 3 * 220, index // 3 * 75
        expected = np.asarray(baseline.crop((x, y, x + 220, y + 75))) > 0
    # Tolerance permits tiny rasterizer differences, but rejects altered loop,
    # spacing, composition, extent, or disconnected decoration.
    union = np.count_nonzero(thumbnail | expected)
    assert union > 100
    assert np.count_nonzero(thumbnail & expected) / union > .97, case["feature"]
    ink = (np.asarray(layer.getchannel("A")) > 100).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(ink)
    assert count >= 2 and stats[1:, 4].max() / ink.sum() > .7
    if case["style"] in {"enclosed", "interwoven"}:
        contours, hierarchy = cv2.findContours(ink, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        holes = [cv2.contourArea(c) for i, c in enumerate(contours) if hierarchy[0, i, 3] >= 0]
        assert sum(area > 12 for area in holes) >= (2 if case["style"] == "interwoven" else 1)
        assert .32 <= info["body_ratio"] <= .52 and .38 <= info["overlap"] <= .58
    assert info["text"] and info["engine"] == "pen-paths-v1"


def test_reference_matrix_covers_all_fifteen_compositions():
    assert {case["cell"] for case in CASES} == {f"r{r}c{c}" for r in range(1, 6) for c in range(1, 4)}
    assert len({(c["style"], c["name"], c["seed"]) for c in CASES}) == 15
