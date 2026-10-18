"""Streaming Unicode CSV/JSON/JSONL exports; exact strings and offsets preserved."""
import csv
import json
from pathlib import Path

CSV_FIELDS=["id","index","task","language","seed","text","label","entities","tokens","context","question",
            "answer","answer_start","instruction","response","messages","source_id","source_sha256",
            "augmentation","provenance","validation","attempt"]
CSV_JSON_FIELDS=set(CSV_FIELDS)-{"id","index","task","language","seed","answer_start","source_id","source_sha256","attempt"}


def export_text(rows, format_: str, path: Path) -> Path:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".tmp")
    with temp.open("w",encoding="utf-8",newline="") as output:
        writer=csv.DictWriter(output,fieldnames=CSV_FIELDS) if format_=="csv" else None
        if writer: writer.writeheader()
        if format_=="json": output.write("[\n")
        first=True
        for sample in rows:
            if not sample.validation["passed"]: continue
            row=json.loads(Path(sample.path).read_text(encoding="utf-8"))
            if writer:
                writer.writerow({k:json.dumps(row.get(k),ensure_ascii=False) if k in CSV_JSON_FIELDS else row.get(k,"") for k in CSV_FIELDS})
            else:
                if format_=="json" and not first: output.write(",\n")
                output.write(json.dumps(row,ensure_ascii=False))
                if format_=="jsonl": output.write("\n")
            first=False
        if format_=="json": output.write("\n]\n")
    temp.replace(path)
    return path
