"""Bundled public format facts. No document data is used in a web query."""
import re

PAN_REFERENCE = {
    "title": "Income Tax Department TRACES — PAN structure",
    "url": "https://traces61contents.tdscpc.gov.in/en/faq-general-pan.html",
    "verified_at": "2026-10-18",
    "pattern": "AAAAA9999A",
    "summary": "The broad character layout is five letters, four digits and a final letter. This layout alone does not establish a valid or issued PAN.",
}


def format_references(prompt: str) -> list[dict]:
    if re.search(r"\bpan(?:\s*card)?\b|\bpermanent\s+account\s+number\b", prompt, re.I):
        return [dict(PAN_REFERENCE)]
    return []
