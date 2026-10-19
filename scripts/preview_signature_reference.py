"""Render the sign7 style test matrix using fictional names, plus ink opacity examples.

Run: python -m scripts.preview_signature_reference
The user reference is not copied or traced. Cell IDs refer to its 5 x 3 layout.
"""
import json
import random
import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from backend.app.schemas import RuleOptions
from backend.app.signatures import render_signature
from backend.app.seals import plan_seal_content, render_seal

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests/fixtures/sign7-cases.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-baseline", action="store_true", help="Replace the reviewed generated geometry fixture")
    args = parser.parse_args()
    out = ROOT / "artifacts/sign7-regression"
    out.mkdir(parents=True, exist_ok=True)
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    gallery = Image.new("RGB", (1440, 1100), "#eaf0f4")
    draw = ImageDraw.Draw(gallery)
    reports = []
    baseline = Image.new("L", (660, 375))
    for index, case in enumerate(cases):
        options = RuleOptions(signature_style=case["style"], text_color=("#713446", "#131e25", "#183776")[index % 3],
                              ink_opacity_mode="fixed", ink_opacity=1, font_weight="normal", font_id="arial")
        layer, mask, info = render_signature((440, 150), case["name"], random.Random(case["seed"]), options)
        thumbnail = mask.resize((220, 75), Image.Resampling.BOX).point(lambda p: 255 if p >= 128 else 0)
        baseline.paste(thumbnail, (index % 3 * 220, index // 3 * 75))
        layer.save(out / f'{case["cell"]}.png')
        x = index % 3 * 480 + 10
        y = index // 3 * 220 + 8
        draw.rounded_rectangle((x, y, x + 460, y + 204), radius=8, fill="white")
        gallery.paste(layer, (x + 10, y), layer)
        draw.text((x + 12, y + 155), f'{case["cell"]} / {case["style"]} / {info["text"]}', fill="#334155")
        # These descriptions describe a composition, not a copied person's signature.
        draw.text((x + 12, y + 179), case["feature"], fill="#64748b")
        reports.append({**case, "metadata": info})
    gallery.save(out / "reference-cases.png")
    (out / "reference-cases.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    if args.update_baseline:
        baseline.save(ROOT / "tests/fixtures/sign7-geometry.png")

    gallery = Image.new("RGB", (1440, 840), "#edf2f5")
    draw = ImageDraw.Draw(gallery)
    for row, kind in enumerate(("signature", "seal")):
        for col, opacity in enumerate((.25, .55, 1)):
            options = RuleOptions(signature_style="interwoven", seal_style="double_ring", seal_color="blue",
                                  ink_opacity_mode="fixed", ink_opacity=opacity, seal_wear=0)
            if kind == "signature":
                layer, _, info = render_signature((430, 200), "Mira Dev", random.Random(42), options)
            else:
                layer, _, info = render_seal((330, 330), plan_seal_content(options, 42), random.Random(42), options)
            layer.save(out / f"{kind}-opacity-{opacity}.png")
            x, y = col * 480 + 12, row * 420 + 12
            draw.rounded_rectangle((x, y, x + 450, y + 396), radius=8, fill="white")
            gallery.paste(layer, (x + (450 - layer.width) // 2, y + (350 - layer.height) // 2), layer)
            draw.text((x + 15, y + 370), f'{kind} / {info["opacity"]:.0%} opacity / same seed & geometry', fill="#334155")
    gallery.save(out / "opacity.png")
    print(out / "reference-cases.png")
    print(out / "opacity.png")


if __name__ == "__main__":
    main()
