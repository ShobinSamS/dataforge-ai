# DataForge AI

A working local CPU proof of concept for synthetic document engineering. Review
a template, replace selected regions with seeded fictional values and assets,
generate images and mask-derived annotations, inspect validation, export a ZIP.
This repository includes the document proof of concept and a synthetic text
workflow. The full agent/diffusion platform remains later work.

**New here? Open the [How-to Catalog](HOW_TO_USE.md)** for feature-by-feature
recipes, copyable inputs, controls, exports and troubleshooting.

## Start on Windows

Prerequisites: Python 3.11 or newer, Node.js 20.19+ or 22.12+, and npm. This
implementation was built/tested here with Python 3.12 and Node.js 24.

```powershell
# From the project folder, start both servers with one command:
npm.cmd start

# First installation only (Python/npm packages use the Internet):
npm.cmd run setup
```

The UI is at **http://127.0.0.1:5173** and OpenAPI at
**http://127.0.0.1:8000/docs**. Keep the launcher running. Ctrl+C stops only its own
server processes. Already-running DataForge services are reused; unrelated port
occupants are never stopped. Use `npm.cmd start -- --no-browser` to skip opening a
browser. Existing PowerShell scripts remain compatible but are no longer required.
Dependency installation uses the Internet; the application does not
need network inference or API keys. No model downloads happen during startup.
Keep Ollama running when using local Qwen. See [seal formats and references](docs/seals.md)
for random/static wording, custom placeholders and repetition controls.
The default database is SQLite. No Docker or OCR installation is required for
the included native-text PDF demonstration.

Or use two terminals, both starting from this repository:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# In the other terminal:
cd frontend
npm.cmd run dev
```

Run only **one** API process/worker. Do not use `--workers` or expose the POC to
a network. Authentication is not implemented. Uploaded documents remain local
in `data/`; PostgreSQL stores metadata when configured. Source images may still
contain real PII and should be handled with your normal local disk controls.

## Try the complete workflow

1. On Dashboard, choose **Try a fictional template**. It creates a certificate
   from `backend/app/demo.py`; text fields come from real PDF extraction.
   Signature, seal and QR regions are authored fixture boxes, not detections.
2. In the editor, select each replacement field and check **I verified this
   region**. Inspect the full document; draw/resize boxes with the canvas tools.
   Keep static text only after deciding it is safe. Select type, sensitivity,
   action (replace/erase/keep) and optional prompt rule per field. **Apply rule**
   interprets common rules or uses local Qwen; review the resulting plan. Date
   format/bounds, fictional ID patterns and portrait image pools have explicit
   controls. See the [document recipes](HOW_TO_USE.md#03--generate-documents).
3. Check the full-page privacy acknowledgment and **Save review**. Unconfirmed
   sensitive fields, invalid coordinates and overlapping replacement boxes are
   rejected. Draft saving is available without the final acknowledgment.
4. Open Generation studio, choose **100 samples**, seed 42, optional signature,
   seal and QR, and augmentation rates. Generate; watch the Job monitor.
5. Inspect Dataset gallery previews and Quality dashboard. Cancel/resume jobs
   at sample boundaries if needed. Current sample previews are read-only;
   fix source fields and regenerate to correct annotations.
6. In Export & history, choose YOLO, COCO or OCR JSON, review the results and
   acknowledge privacy limits, then **Build & download ZIP**.

`samples/fictional_certificate.pdf` is a standalone source fixture. The included
`samples/fictional_100_yolo.zip` contains the verified 100-image demonstration;
`samples/generated_preview.png` shows one result and `samples/verification.json`
records the observed run. These artifacts contain fictional data only.
All generated images are streamed to disk; the UI paginates samples.

## Implemented

- **Synthetic text datasets:** classification, NER, Q&A, instruction–response,
  conversations and augmentation in English, Spanish, French, German and Hindi.
  Procedural or local Qwen/Ollama generation, configurable counts/batches/seeds,
  labels, quality/revalidation, checkpoint jobs and CSV/JSON/JSONL exports.
  See the [text feature audit and guide](docs/text-datasets.md).

- Single-page PDF/PNG/JPEG/TIFF upload, decoder checks and 20 MB / 16 MP limits.
- Native PDF text extraction, lazy optional PaddleOCR 3.x and Tesseract fallback;
  confidence, conservative regex field suggestions and explicit manual fallback.
- OCR + local Qwen PII suggestions with editable, auto-labeled erase regions; optional
  offline TrOCR-Small English line OCR and ruled-table cell extraction/CSV/JSON.
  See [document analysis and rendering](docs/document-analysis.md) for setup and limits.
- Konva region editor: draw, move, resize, zoom, pan; types/rules; review versions.
- Prompt-to-plan rules via deterministic aliases/local Qwen; explicit erase-only
  actions, configurable date formats/bounds and generic custom code patterns.
  Qwen compiles literal prefixes, digit groups, mixed-case letters and date tokens;
  generated values have no mandatory visible prefix or portrait caption.
- Portrait regions with seeded fictional illustrations, approved uploaded photo
  pools and optional explicit imports from an operator-configured image provider.
  Default operation stays offline; no automatic web scraping or photoreal generation.
- Faker names, configurable dates, reserved fictional contact values and random IDs;
  repeated field consistency and font fitting with overflow rejection.
- Exact field character lengths, automatic QR payloads up to 500 characters, optional
  required QR regions and configurable QR padding (zero by default).
- Native PDF font hints and automatic local glyph/font matching, including bold
  faces, actual glyph-size fitting and source color. Manual family/weight/size
  controls remain available; scanned fonts are estimated, not guaranteed.
- Local background inpainting with transparent text rendering and optional
  explicit solid colors; generated fictional
  signatures/seals, QR and Code 128 assets in reviewed regions.
- Seeded rotation, blur and noise. Image/mask geometry transforms together;
  per-instance PNG masks, YOLO boxes, COCO RLE and OCR field JSON.
- Durable SQL job queue, one CPU worker, memory admission check, cancellation,
  checkpoint resume, bounded validation retries and measured process RSS/time.
- Per-sample bounds/mask/coverage/integrity/QR checks; duplicate rejection;
  gallery, quality counts/class chart, accepted-only ZIP export and export history.
- Local Host/origin restrictions, input validation, structured job logs,
  OpenAPI, Windows scripts, tests and a reproducible benchmark utility.

## Explicit limits / later milestones

This is a POC, **not a production-complete or privacy-certified platform**.
Automatic PII discovery is incomplete; names/addresses and visual identifiers
may be missed. Region restoration is suitable for plain backgrounds and may
need manual correction on textures or faint text. Confirm entire-page content and generated results.
Automated validation does not establish training readiness or statistical utility.
Faker names can coincide with real names.

Presidio, general layout/borderless-table/signature detection, neural restoration,
sample annotation editing, LangGraph, FAISS/RAG, MCP server, tabular synthesis,
AI image ingestion and diffusion are **not implemented**.
Their navigation pages state this explicitly. No agent/model activity is faked.
Local Qwen is implemented for text generation through an existing Ollama service;
it is optional and never downloads weights or silently falls back to a cloud model.
PaddleOCR/Tesseract adapters need separately installed local engines/models and
have not been exercised with weights on this machine. PDF-native extraction and
manual correction work without them. PostgreSQL configuration is provided but
was not integration-tested against a running PostgreSQL server here.

## OCR and database configuration

Copy `.env.example` to `.env` and restart the backend after changes. For raster
OCR install a local Tesseract build and English traineddata; set
`DATAFORGE_TESSERACT_CMD` to its executable if it is outside PATH. Alternatively
install compatible PaddlePaddle CPU and PaddleOCR 3.x packages in an isolated
evaluation environment, provision det/rec models locally, and set both model
directory variables. Do not point to untrusted model files. No automatic model
acquisition is performed. See `docs/models-and-compatibility.md`.

For local PostgreSQL: `docker compose up -d`, set the connection string shown
in `.env.example`, restart. Compose credentials are for local development only.
SQLite and PostgreSQL are independent databases; changing the URL does not migrate
existing records. POC tables are created automatically; production migrations,
retention, multi-user auth, audit logs and worker isolation are later work.

## Tests, build, benchmark

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=artifacts/pytest-local
.\.venv\Scripts\python.exe .\scripts\benchmark.py --count 100
cd frontend
npm.cmd run build
```

The integration suite generates **100 real images**, verifies their unique
hashes, privacy gates, mask/coordinate validity and exports in all three formats.
Other tests cover invalid uploads, single-page limits, local Host/origin checks,
queue bounds, revisions, deterministic output, cancellation/resume and the actual
background worker. Benchmark output is in `artifacts/benchmark/report.json` and
includes a fictional YOLO ZIP. Measurements describe only the execution host,
not a guaranteed speed or peak system RAM on another machine.
RSS is sampled at sample boundaries; the reported maximum can miss short-lived
allocation peaks inside a rendering step.
Byte-identical reproduction requires the same source image, dependency versions,
font availability and runtime; changing system fonts can change rendered pixels.

Pinned `requirements.lock.txt` records the tested Windows/Python environment;
`requirements.txt` gives compatible installation ranges for other Python versions.
`frontend/package-lock.json` pins npm inputs. Use the lock on matching platforms;
wheel availability and optional model stacks should be verified independently.

## Design and specifications

- [Architecture, data flow, database diagram, algorithms and roadmap](docs/architecture.md)
- [API endpoint and schema reference](docs/api.md)
- [Synthetic text audit, supported tasks, labels, API and exports](docs/text-datasets.md)
- [Model compatibility, resources and upstream license sources](docs/models-and-compatibility.md)

Frontend: `frontend/src/App.tsx` contains the workflow screens and live queries;
`pages/Dashboard.tsx` owns the overview, `components/ui.tsx` contains shared UI,
`RegionEditor.tsx` owns the canvas, and `types.ts` defines frontend contracts.
Backend modules separate ingestion, privacy, rendering, geometry validation,
job scheduling, SQL metadata and export. No cloud connector is part of runtime.
