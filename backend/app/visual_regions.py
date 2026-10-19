"""Local, reviewable visual proposals. No payload decoding or network/model downloads."""
import hashlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .schemas import Region

MAX_SIDE = 1800
MAX_OBJECTS = 40
FACE_MODEL = Path(__file__).resolve().parents[1]/"assets/yunet/face_detection_yunet_2023mar.onnx"
NOTICE = ("Visual boxes are suggestions, not verified labels. QR detection uses OpenCV; "
          "barcodes use stripe geometry; photos use a local face detector and estimated photo bounds. "
          "Missed, rotated, damaged codes and photos without a detectable face need manual boxes. "
          "Resize, relabel or delete incorrect suggestions. Code payloads are not read.")


def coverage(a, b):
    """Fraction of a contained in b (x, y, width, height)."""
    x, y, w, h = a
    xx, yy, ww, hh = b
    return max(0, min(x+w, xx+ww)-max(x, xx))*max(0, min(y+h, yy+hh)-max(y, yy))/max(1, w*h)


def _barcode_boxes(gray):
    """Both orientations; many parallel bars must share aligned top/bottom edges."""
    found = []
    for transpose in (False, True):
        page = gray.T.copy() if transpose else gray
        dx = np.abs(cv2.Sobel(page, cv2.CV_32F, 1, 0, ksize=3))
        dy = np.abs(cv2.Sobel(page, cv2.CV_32F, 0, 1, ksize=3))
        directional = np.uint8(np.clip(dx-dy, 0, 255))
        directional = cv2.blur(directional, (5, 3))
        _, ink = cv2.threshold(directional, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        joined = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((7, 25), np.uint8))
        for contour in cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, w, h = cv2.boundingRect(contour)
            if w < 45 or h < 20 or not 1.25 < w/h < 12:
                continue
            crop = page[y:y+h, x:x+w]
            _, bw = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
            rows = bw[int(h*.2):max(int(h*.8), int(h*.2)+1)] > 0
            profile = rows.mean(axis=0)
            transitions = np.count_nonzero(np.diff((profile > .5).astype(np.int8)))
            # Text rows and tables do not have sustained aligned bar/gap columns.
            coherent = np.mean((profile < .15) | (profile > .85))
            dark = rows.mean()
            if transitions < 22 or coherent < .75 or not .15 < dark < .8:
                continue
            box = (y, x, h, w) if transpose else (x, y, w, h)
            found.append(box)
    return found


def _detect_faces(bgr):
    if not FACE_MODEL.is_file():
        raise ValueError("Bundled YuNet model is missing")
    height, width = bgr.shape[:2]
    ratio = min(640/width, 640/height)
    scaled = cv2.resize(bgr, (max(1, round(width*ratio)), max(1, round(height*ratio))))
    canvas = np.full((640, 640, 3), 255, dtype=np.uint8)
    canvas[:scaled.shape[0], :scaled.shape[1]] = scaled
    detector = cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (640, 640), .8, .3, 5000)
    _, detections = detector.detect(canvas)
    return [] if detections is None else [tuple(float(v/ratio) for v in d[:4]) for d in detections]


def _photo_boxes(bgr):
    try:
        faces = _detect_faces(bgr)
    except Exception:
        return [], ["Local YuNet face detector is unavailable; add photo boxes manually."]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    # Prefer a nearby enclosing rectangular panel over a face-only box.
    edges = cv2.Canny(gray, 50, 150)
    panels = []
    for contour in cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]:
        perimeter = cv2.arcLength(contour, True)
        if len(cv2.approxPolyDP(contour, .025*perimeter, True)) != 4:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w >= 35 and h >= 40 and .4 < w/h < 2 and w*h < gray.size*.6:
            panels.append((x, y, w, h))
    boxes = []
    for x, y, w, h in faces:
        face = (int(x), int(y), int(w), int(h))
        candidates = [p for p in panels if coverage(face, p) > .98 and 1.8 < p[2]*p[3]/(w*h) < 55]
        if candidates:
            boxes.append(min(candidates, key=lambda p: p[2]*p[3]))
        else:
            # Head/shoulder estimate; explicitly labelled as approximate for correction.
            boxes.append((x-w*.45, y-h*.35, w*1.9, h*2.35))
    return boxes, []


def detect_visual_regions(image: Image.Image):
    width, height = image.size
    scale = min(1, MAX_SIDE/max(width, height))
    small = image.convert("RGB").resize((max(1, round(width*scale)), max(1, round(height*scale))))
    gray = cv2.cvtColor(np.asarray(small), cv2.COLOR_RGB2GRAY)
    warnings = [NOTICE]
    raw = []
    detector = cv2.QRCodeDetector()
    ok, points = detector.detectMulti(gray)
    if ok and points is not None:
        for polygon in points:
            lo = polygon.min(axis=0)
            hi = polygon.max(axis=0)
            raw.append(("qr", (*lo, *(hi-lo)), .9, "QR code (proposal)"))
    for box in _barcode_boxes(gray):
        raw.append(("barcode", box, .65, "Barcode (proposal)"))
    photos, notices = _photo_boxes(cv2.cvtColor(np.asarray(small), cv2.COLOR_RGB2BGR))
    warnings.extend(notices)
    raw.extend(("portrait", box, .55, "Photo (estimated bounds)") for box in photos)
    result = []
    for kind, box, confidence, label in raw:
        x, y, w, h = box
        left, top = max(0, int(np.floor(x/scale))-2), max(0, int(np.floor(y/scale))-2)
        right, bottom = min(width, int(np.ceil((x+w)/scale))+2), min(height, int(np.ceil((y+h)/scale))+2)
        bounded = (left, top, right-left, bottom-top)
        if min(bounded[2:]) < 4:
            continue
        if any(max(coverage(bounded, r["box"]), coverage(r["box"], bounded)) > .55 for r in result):
            continue
        digest = hashlib.sha256(f"{kind}:{bounded}".encode()).hexdigest()[:16]
        result.append(Region(id="visual_"+digest, label=label, kind=kind, box=bounded,
                             confidence=confidence, origin="visual", confirmed=False).model_dump(mode="json"))
        if len(result) >= MAX_OBJECTS:
            warnings.append("Visual proposals limited to 40 objects. Inspect the remaining page manually.")
            break
    return result, warnings


def merge_upload_regions(text_regions, visual_regions, limit=200):
    # Text inside QR/barcode/photo is owned by that visual region, not duplicated OCR.
    texts = [r for r in text_regions if not any(coverage(r["box"], v["box"]) >= .75 for v in visual_regions)]
    return (visual_regions+texts)[:limit]
