"""Decode uploads, render PDFs, extract native text and optionally run local OCR."""
import gc
import io
import os
import shutil
import uuid
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
from .config import settings
from .privacy import classify
from .resources import CPU_LOCK
from .schemas import Region

MAX_PIXELS = 16_000_000
MAX_REGIONS = 200
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
NOTICE = "PII detection is incomplete. Inspect the full page, including handwriting, signatures, QR codes and seals."


def text_region(text: str, box, confidence: float) -> dict:
    return Region(id=uuid.uuid4().hex[:12], label=text[:60] or "Text", text=text,
                  kind=classify(text), box=tuple(int(v) for v in box),
                  confidence=max(0, min(1, confidence)),origin="ocr").model_dump(mode="json")


def decode(content: bytes, suffix: str) -> tuple[Image.Image, list[dict]]:
    """One page only: refuse additional pages instead of silently dropping them."""
    if suffix == ".pdf":
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(content) as pdf:
            if len(pdf) != 1:
                raise ValueError("Phase 1 accepts single-page PDFs only; split the document first")
            page = pdf[0]
            width, height = page.get_size()
            if width <= 0 or height <= 0 or max(width,height) > 10000:
                raise ValueError("Invalid or oversized PDF page dimensions")
            scale = min(1.5, (MAX_PIXELS / max(1, width * height)) ** .5)
            image = page.render(scale=scale).to_pil().convert("RGB")
            sx, sy = image.width / width, image.height / height
            regions = []
            tp = page.get_textpage()
            try:
                # PDFium rectangle groups follow actual text runs; labels are native text, not OCR.
                for i in range(min(MAX_REGIONS,tp.count_rects())):
                    l, b, r, t = tp.get_rect(i)
                    text = tp.get_text_bounded(l, b, r, t).strip()
                    x, y = max(0, int(l * sx) - 3), max(0, int((height - t) * sy) - 3)
                    w, h = min(image.width - x, int((r - l) * sx) + 6), min(image.height - y, int((t - b) * sy) + 6)
                    if text and w >= 4 and h >= 4:
                        region=text_region(text, (x, y, w, h), 1)
                        try:
                            char_index=tp.get_index(l+1,(b+t)/2,max(2,(r-l)/2),max(2,(t-b)/2))
                            obj=tp.get_textobj(char_index) if char_index is not None else None
                            if obj:
                                region["source_font"]=obj.get_font().get_base_name()[:150]
                                region["source_font_size"]=max(.1,min(1000,obj.get_font_size()*sy))
                        except Exception:
                            pass  # Native font metadata is optional; extraction/OCR still works.
                        regions.append(region)
            finally:
                tp.close()
                page.close()
            return image, regions
    if suffix not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        raise ValueError("Supported: PDF, PNG, JPEG, single-frame TIFF")
    with Image.open(io.BytesIO(content)) as source:
        if source.width * source.height > MAX_PIXELS or max(source.size) > 10000:
            raise ValueError("Image exceeds 16 megapixels")
        if getattr(source, "n_frames", 1) != 1:
            raise ValueError("Only single-frame images are supported")
        source.load()
        image = ImageOps.exif_transpose(source).convert("RGBA")
        background = Image.new("RGBA", image.size, "white")
        background.alpha_composite(image)
        return background.convert("RGB"), []


def ocr(image: Image.Image) -> tuple[list[dict], str, list[str]]:
    """No implicit network downloads. PaddleOCR 3.x needs local det/rec dirs."""
    warnings = [NOTICE]
    if settings.ocr_engine in {"auto", "paddle"} and settings.paddle_det_dir and settings.paddle_rec_dir:
        model = None
        try:
            from paddleocr import PaddleOCR
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
            with CPU_LOCK:
                model = PaddleOCR(
                    text_detection_model_dir=settings.paddle_det_dir,
                    text_recognition_model_dir=settings.paddle_rec_dir,
                    use_doc_orientation_classify=False, use_doc_unwarping=False,
                    use_textline_orientation=False, device="cpu", cpu_threads=2,
                )
                regions = []
                for result in model.predict(np.asarray(image)):
                    for text, score, polygon in zip(result["rec_texts"], result["rec_scores"], result["rec_polys"]):
                        points = np.asarray(polygon)
                        lo = np.maximum(0, np.floor(points.min(axis=0))).astype(int)
                        hi = np.minimum(image.size, np.ceil(points.max(axis=0))).astype(int)
                        if np.all(hi - lo >= 4):
                            if len(regions) < MAX_REGIONS:
                                regions.append(text_region(text, [*lo, *(hi-lo)], float(score)))
                return regions, "paddle-local", warnings
        except Exception as exc:
            warnings.append(f"PaddleOCR unavailable ({type(exc).__name__}); trying printed-text fallback")
        finally:
            del model
            gc.collect()
    if settings.ocr_engine != "manual":
        try:
            import pytesseract
            cmd = settings.tesseract_cmd or shutil.which("tesseract")
            if not cmd:
                raise RuntimeError("Tesseract executable not installed")
            pytesseract.pytesseract.tesseract_cmd = cmd
            with CPU_LOCK:
                data = pytesseract.image_to_data(ImageOps.autocontrast(image.convert("L")),
                    config="--psm 11", output_type=pytesseract.Output.DICT, timeout=90)
            groups: dict[tuple, list[int]] = {}
            for i, text in enumerate(data["text"]):
                if text.strip() and float(data["conf"][i]) >= 0:
                    key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                    groups.setdefault(key, []).append(i)
            regions = []
            for ids in list(groups.values())[:MAX_REGIONS]:
                x = max(0, min(data["left"][i] for i in ids)-3)
                y = max(0, min(data["top"][i] for i in ids)-3)
                r = min(image.width, max(data["left"][i]+data["width"][i] for i in ids)+3)
                b = min(image.height, max(data["top"][i]+data["height"][i] for i in ids)+3)
                if r-x >= 4 and b-y >= 4:
                    regions.append(text_region(" ".join(data["text"][i] for i in ids),
                        (x, y, r-x, b-y), np.mean([float(data["conf"][i]) for i in ids])/100))
            return regions, "tesseract-local", warnings
        except Exception as exc:
            warnings.append(f"Printed OCR unavailable ({type(exc).__name__}). Add regions manually or upload a text PDF.")
    return [], "manual", warnings


def ingest(content: bytes, suffix: str, dest: Path) -> tuple[int, int, list, str, list]:
    image, regions = decode(content, suffix)
    warnings = [NOTICE]
    engine = "pdf-native-text"
    if not regions:
        regions, engine, warnings = ocr(image)
    if len(regions) >= MAX_REGIONS:
        warnings.append("Analysis limited to 200 text groups. Inspect remaining content manually.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG")  # strips EXIF and source metadata
    return image.width, image.height, regions, engine, warnings
