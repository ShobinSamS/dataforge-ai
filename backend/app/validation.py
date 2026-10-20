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


def qr_matches(gray, annotation, detector):
    """Decode rendered pixels, including transparent codes on colored paper."""
    import cv2
    x,y,w,h=annotation["bbox"]
    expected=annotation["text"]
    crop=gray[y:y+h,x:x+w]
    if not crop.size:return False
    nearby=gray[max(0,y-8):y+h+8,max(0,x-8):x+w+8]
    if detector.detectAndDecode(nearby)[0]==expected:return True
    # A quiet zone is decoder-only; output images retain their chosen background
    # and padding. Thresholding separates black modules from textured blue paper.
    binary=cv2.threshold(crop,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    for candidate in (crop,binary):
        padded=cv2.copyMakeBorder(candidate,40,40,40,40,cv2.BORDER_CONSTANT,value=255)
        if detector.detectAndDecode(padded)[0]==expected:return True
    if min(crop.shape)>=350:
        reduced=cv2.resize(binary,None,fx=.5,fy=.5,interpolation=cv2.INTER_NEAREST)
        reduced=cv2.copyMakeBorder(reduced,40,40,40,40,cv2.BORDER_CONSTANT,value=255)
        if detector.detectAndDecode(reduced)[0]==expected:return True
    # The alternate local detector handles some dense version/mask combinations
    # that the standard detector misses, even with correctly rendered modules.
    if hasattr(cv2,"QRCodeDetectorAruco"):
        alternate=cv2.QRCodeDetectorAruco()
        for scale in (1,.5,1.5):
            candidate=binary if scale==1 else cv2.resize(binary,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
            candidate=cv2.copyMakeBorder(candidate,40,40,40,40,cv2.BORDER_CONSTANT,value=255)
            if alternate.detectAndDecode(candidate)[0]==expected:return True
    return False


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
    image=result["image"]
    if image.mode=="RGBA":
        # Decoder-only white matte; PNG exports retain their alpha channel.
        matte=Image.new("RGBA",image.size,"white");matte.alpha_composite(image);image=matte.convert("RGB")
    gray = cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2GRAY)
    qr_values = [a["text"] for a in annotations if a["class"] == "qr"]
    if qr_values:
        detector = cv2.QRCodeDetector()
        # Decode each cropped QR independently: handles multiple QR fields per page.
        for a in [a for a in annotations if a["class"] == "qr"]:
            if not qr_matches(gray,a,detector):
                errors.append(f"qr_unreadable:{a['region_id']}")
    with Image.open(folder/"image.png") as check:
        check.verify()
    return {"passed":not errors,"errors":errors,"warnings":warnings,
            "laplacian_variance":round(float(cv2.Laplacian(gray,cv2.CV_64F).var()),3),
            "privacy_status":"human-review-required","training_ready":False,"validator_version":"contrast-qr-v2",
            "checked":["coordinate_bounds","mask_alignment","field_coverage","image_integrity","qr_decode"],
            "not_checked":["undetected_pii","ocr_transcription_match","barcode_decode","statistical_fidelity"]}
