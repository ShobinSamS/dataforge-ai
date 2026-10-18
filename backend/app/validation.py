"""Measurable checks, with explicit limitations and no training-ready assertion."""
from pathlib import Path
import math
import numpy as np
from PIL import Image


def yolo_line(annotation: dict, width: int, height: int) -> str:
    x,y,w,h = annotation["bbox"]
    values = [(x+w/2)/width,(y+h/2)/height,w/width,h/height]
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in values) or w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > width or y+h > height:
        raise ValueError("Invalid YOLO coordinates")
    return str(annotation["class_id"])+" "+" ".join(f"{v:.8f}" for v in values)


def validate(result: dict, folder: Path, expected: int) -> dict:
    errors = list(result["errors"])
    warnings = ["Background and undetected PII require human inspection", "OCR round-trip and barcode decoding are not implemented"]
    annotations = result["annotations"]
    if len(annotations) != expected:
        errors.append("missing_fields")
    for a in annotations:
        try:
            yolo_line(a,result["width"],result["height"])
            with Image.open(folder/a["mask"]) as mask:
                if mask.size != (result["width"],result["height"]):
                    errors.append(f"mask_dimensions:{a['region_id']}")
                bounds = mask.getbbox()
                x,y,w,h = a["bbox"]
                if bounds != (x,y,x+w,y+h):
                    errors.append(f"mask_alignment:{a['region_id']}")
        except (ValueError,OSError):
            errors.append(f"invalid_annotation:{a['region_id']}")
    import cv2
    gray = cv2.cvtColor(np.asarray(result["image"]),cv2.COLOR_RGB2GRAY)
    qr_values = [a["text"] for a in annotations if a["class"] == "qr"]
    if qr_values:
        detector = cv2.QRCodeDetector()
        # Decode each cropped QR independently: handles multiple QR fields per page.
        for a in [a for a in annotations if a["class"] == "qr"]:
            x,y,w,h = a["bbox"]
            value,_,_ = detector.detectAndDecode(gray[max(0,y-8):y+h+8,max(0,x-8):x+w+8])
            if value != a["text"]:
                # Borderless output stays borderless. Add a decoder-only quiet
                # zone to the crop when its surrounding template is textured.
                crop=gray[y:y+h,x:x+w]
                crop=cv2.copyMakeBorder(crop,16,16,16,16,cv2.BORDER_CONSTANT,value=255)
                value,_,_=detector.detectAndDecode(crop)
            if value != a["text"]:
                errors.append(f"qr_unreadable:{a['region_id']}")
    with Image.open(folder/"image.png") as check:
        check.verify()
    return {"passed":not errors,"errors":errors,"warnings":warnings,
            "laplacian_variance":round(float(cv2.Laplacian(gray,cv2.CV_64F).var()),3),
            "privacy_status":"human-review-required","training_ready":False,
            "checked":["coordinate_bounds","mask_alignment","field_coverage","image_integrity","qr_decode"],
            "not_checked":["undetected_pii","ocr_transcription_match","barcode_decode","statistical_fidelity"]}
