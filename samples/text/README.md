# Fictional text dataset examples

Each task has **15 records across English, Spanish, French, German and Hindi**:
classification, NER, Q&A, instruction–response, conversations and augmentation.
The `.json`, `.jsonl` and `.csv` files were generated/exported through the real
API with procedural seed 119. The matching `.manifest.json` contains config,
quality counts, runtime and format conventions. Recreate with:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/generate_text_demo.py
```

`local_qwen_examples.jsonl` contains **10 actual local Qwen outputs** from
several live verification runs, including three-record classification and Q&A
batches and Hindi NER. `verification.json` records their scope and model identity.
These are separate from the deterministic procedural examples.

CSV content/nested columns are JSON encoded. Use the manifest's column list:

```python
import csv, json
with open("ner.manifest.json", encoding="utf-8") as f:
    manifest = json.load(f)
with open("ner.csv", encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
for row in rows:
    for key in manifest["csv_json_encoded_columns"]:
        row[key] = json.loads(row[key])
```

NER/answer offsets are Unicode code points, end-exclusive. Faker names are
invented samples and can coincide with real names. No personal source documents
were used. Structural validation passing does **not** certify semantic accuracy,
privacy or training readiness. Labels, language quality and utility need review.
