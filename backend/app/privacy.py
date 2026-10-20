"""Conservative suggestions, not an anonymization guarantee."""
import re
from .schemas import FieldType, Region, region_action

PATTERNS = [
    (FieldType.email, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    (FieldType.date, r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"),
    (FieldType.phone, r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)"),
    (FieldType.identifier, r"\b(?:ID|REG|CERT|SYN)[- :]*[A-Z0-9-]{4,}\b"),
]


def classify(text: str) -> FieldType:
    for kind, pattern in PATTERNS:
        if re.search(pattern, text, re.I):
            return kind
    return FieldType.text


def check_review(regions: list[Region], width: int, height: int, privacy_confirmed: bool, *, allow_overlap: bool=False) -> None:
    if not regions:
        raise ValueError("Select at least one replacement region")
    if len({r.id for r in regions}) != len(regions):
        raise ValueError("Region IDs must be unique")
    for r in regions:
        x, y, w, h = r.box
        if x + w > width or y + h > height:
            raise ValueError(f"Region {r.label} is outside the page")
        if r.sensitive and (region_action(r)=="keep" or not r.confirmed):
            raise ValueError(f"Sensitive region {r.label} must be confirmed and replaced or erased")
    selected = [r for r in regions if region_action(r)!="keep"]
    for i, a in enumerate(selected):
        x,y,w,h = a.box
        for b in selected[i+1:]:
            xx,yy,ww,hh = b.box
            if not allow_overlap and min(x+w,xx+ww) > max(x,xx) and min(y+h,yy+hh) > max(y,yy):
                raise ValueError(f"Replacement regions overlap: {a.label} / {b.label}; combine or resize them")
    if not privacy_confirmed:
        raise ValueError("Confirm that you reviewed the entire page for sensitive content")


def sanitize_regions(regions: list[dict]) -> list[dict]:
    # OCR suggestions are also used as display labels; remove both original strings.
    return [{**r, "text": "", "label":f"{r['kind']} {r['id']}","rule":"","rule_resolved_hash":"","pii_value":"","pii_reason":""} for r in regions]
