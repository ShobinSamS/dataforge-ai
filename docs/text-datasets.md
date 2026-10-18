# Synthetic text datasets: audit and implementation

## Audit result

At the start of this change, synthetic text generation was **not implemented**.
`schemas.py` only described document/image generation; `main.py` had no text
routes; the ORM only held document templates/jobs/samples; and the frontend had
no text page. Qwen and text/NER synthesis were listed as later work in README.
Document OCR export was not a synthetic text-generation pipeline.

| Requested capability | Previous state | Current implementation |
|---|---|---|
| Text classification | Missing | Authored sentiment examples, custom class/language templates, or local Qwen conditioned on preassigned labels; class/language cross-product scheduling |
| NER | Missing | Entity-first PERSON/ORG/LOCATION values, deterministic Unicode character spans and BIO token labels; Qwen writes placeholder contexts, never numerical offsets |
| Q&A pairs | Missing | Extractive pairs with answer-first construction and exact answer_start; default fictional scores or configurable per-language answer banks and answer descriptions |
| Instruction–response | Missing | Offline code-copy instruction pairs or contextual local-model generation |
| Conversations | Missing | Offline scripted exchanges or local-model 2–12-message conversations; alternating user/assistant roles verified |
| Multilingual text | Missing | English, Spanish, French, German, Hindi; language selection and counts; authored offline strings and local-model language instructions |
| Text augmentation | Missing | Seeded whitespace/punctuation/Latin-letter typos or local-model paraphrasing; source language/label/lineage retained; unchanged/duplicate candidates rejected |
| Frontend | Missing | Text datasets navigation, form, local-model availability, job history, progress/cancel/resume, reusable configurations, pagination, NER highlighting, record JSON, quality report, revalidation, exports |
| FastAPI | Missing | Dedicated `/api/text/*` typed inputs and OpenAPI; endpoints below |
| Local LLM | Missing | Loopback Ollama Qwen3 1.7B GGUF, CPU options, JSON-schema output, bounded batches, retries, explicit failures; no downloads/cloud fallback |
| Sample counts | Missing | 1–2,000 records/job, configurable lower server cap, batch sizes 1–8, durable per-record checkpoints |
| Labeling | Missing | Planned classification targets, constructed entities/answers, inherited augmentation labels, conversation roles and task-specific fields |
| Validation | Missing | Schemas, membership, exact spans, BIO/token boundaries, answer offsets, roles, duplicate hashes, advisory sensitive patterns, persisted validation and file-integrity checks |
| CSV / JSON / JSONL | Missing | Accepted-only downloads, review acknowledgment, export history, metadata/quality manifest, Unicode-preserving round-trip tests |

## Use

Restart the backend after installing this change; the new SQL tables are created
without altering existing document tables. The frontend adds **Text datasets**
under Workspace. Existing document pages and endpoint payloads are preserved.

1. Choose a task, procedural or local Qwen engine, record count, seed and languages.
2. For custom procedural classes, supply JSON templates by class and language.
   For augmentation, supply source JSON with text, language and optional label.
   Every selected language needs a source; augmentation does not translate.
3. For Q&A you may supply `qa_answer_bank`, e.g.
   `{"en":["Fictional Gold Plan"],"hi":["काल्पनिक गोल्ड योजना"]}`,
   and an answer description such as "fictional service tier". Values are hidden
   from the LLM and substituted into `[[ANSWER]]` afterward. Offline custom-bank
   Q&A uses a generic record/what-does-it-state template.
4. Generate, monitor progress and inspect labels/quality. Cancel/resume from a
   saved boundary. Reuse a prior configuration to create another version/job.
5. Run **Revalidate records** when needed, inspect text/labels/language/privacy,
   check the export acknowledgment, and download CSV, JSON or JSONL plus manifest.

Procedural generation needs no models. Topic and free-form instructions apply
to Qwen; procedural content is intentionally a small authored baseline, not an
open-domain language generator. Custom templates are explicit and configurable.

## Local Qwen setup and controls

An installed Ollama service and a locally provisioned `qwen3:1.7b` GGUF are
required only for model inference. Provision weights separately; DataForge
never pulls models. The installed local Q4_K_M model was available during the
live integration checks. Configuration is in `.env.example`:

```dotenv
DATAFORGE_OLLAMA_URL=http://127.0.0.1:11434
DATAFORGE_OLLAMA_MODEL=qwen3:1.7b
DATAFORGE_LLM_TIMEOUT_SECONDS=180
DATAFORGE_TEXT_MAX_SAMPLES=2000
DATAFORGE_LLM_MIN_AVAILABLE_MB=4000
```

Requests use `/api/chat`, structured schema output, `think=false`, CPU-only
inference, an 8,192-token context ceiling and a bounded output budget. A UTF-8
input-size admission check rejects overlong source/instructions rather than
silently truncating. Reduce batch size or source length when this check fails.
Model identity/digest/quantization are recorded when supplied by Ollama.

Only numeric loopback HTTP addresses or localhost are allowed. Environment
proxies and redirects are disabled, and model status rejects cloud/remote
entries. Unsupported/unavailable models return 503 before queueing; interrupted
inference fails the job with a recoverable error. Invalid output gets bounded
retries, then a rejected record. Procedural fallback is never silently substituted.

Document and text jobs share the existing **one-worker FIFO queue** and the
eight-active-job cap. OCR/rendering/inference share the process resource lock.
LLM requests use `keep_alive=0`, requesting model release after each batch. Admission
requires the configured free-memory allowance; already-loaded CPU memory for the
same model/context can count toward that allowance, while retaining at least the
base 1,500 MB free-memory threshold. Other applications/clients can still consume
resources. API RSS metrics exclude Ollama; they are not total-system peak RAM.

The current app does not own or configure the Ollama daemon or guarantee exclusivity
against other Ollama clients. Avoid parallel model workloads on the target laptop.
Structured outputs and release options follow the [official Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md).
The local model tag is documented on [Ollama's Qwen3 1.7B page](https://ollama.com/library/qwen3%3A1.7b).

## Record and export semantics

- Classification labels are assigned before text generation. Authored defaults
  use known sentiment phrases; custom templates/model-conditioned text require
  semantic review. A syntactically valid label does not prove text/label agreement.
- NER offsets use **Unicode code points**, `[start,end)`. JS highlights use
  `Array.from(text)` rather than UTF-16 indices. BIO labels include token offsets.
  Exactness covers inserted entity geometry, not exhaustive recognition of any
  additional entity a model may invent elsewhere in its text.
- Q&A answers are inserted into a single marker and their exact offsets computed.
  This validates extraction geometry; question relevance still requires review.
- Augmentation labels are copied from the source. Paraphrases, typos and
  punctuation can change meaning. Whitespace variations are finite, so requesting
  more distinct variants than available can reject samples instead of duplicating.
  Typos only target eligible adjacent Latin letters; Hindi supports whitespace,
  punctuation and model paraphrasing.
- The five selected language codes are validated, but automatic language
  identification is **not** claimed. Native-language and factual review remain
  necessary. No semantic-quality score or training-readiness badge is fabricated.
- JSON is an array; JSONL is one complete record per line. CSV has a fixed header;
  text, labels and nested content columns are **JSON encoded inside CSV cells**.
  This preserves Unicode, exact offsets and nested structures and keeps content
  cells from beginning with spreadsheet formulas. Decode the manifest's
  `csv_json_encoded_columns` with `json.loads` after `csv.DictReader`/Pandas.
- Every record includes task, language, seed, provenance, validation and attempts.
  Download the manifest for job version/configuration, runtime, model identity,
  source hashes and quality counts. Raw augmentation sources and free-form
  instructions are omitted from the export manifest; local job configuration
  retains them for reuse. Source labels/templates may themselves be sensitive;
  review them before using real input.
- Exports include only accepted records. Stored record checksums and task
  validation are checked again before export. Corruption/edits block export until
  revalidation excludes the affected rows. Rejected rows are never promoted by
  a shallow recheck. To correct data, adjust inputs and create a new job.

All datasets remain `training_ready=false`. PII checks only catch selected
patterns; they do not certify anonymization, semantics, bias or downstream utility.
Procedural reproduction requires the same config/seed/runtime; fresh model
inference is not guaranteed byte-identical across runtimes. Saved records and
checkpoints preserve completed output.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/text/capabilities` | Supported tasks/languages/caps and actual local model availability |
| POST | `/api/text/jobs` | Validated `TextConfig`, 201 queued job; 503 unavailable model, 429 full shared queue |
| GET | `/api/text/jobs` | Text job/version history |
| GET | `/api/text/jobs/{id}` | Status/progress/configuration/metrics |
| POST | `/api/text/jobs/{id}/cancel` | Queued cancellation or request cancellation at record boundary |
| POST | `/api/text/jobs/{id}/resume` | Resume paused/cancelled/failed work; committed records skipped |
| GET | `/api/text/jobs/{id}/records?offset=0&limit=20` | Paginated previews, max page size 100 |
| GET | `/api/text/jobs/{id}/quality` | Accepted/rejected, labels/languages, validation reasons and limitations |
| POST | `/api/text/jobs/{id}/validate` | Revalidate immutable saved records and integrity |
| GET | `/api/text/jobs/{id}/manifest` | Configuration/version/provenance/quality metadata |
| POST | `/api/text/jobs/{id}/exports` | `{format:csv/json/jsonl,review_confirmed:true}` |
| GET | `/api/text/exports` | Text export history |
| GET | `/api/text/exports/{id}/download` | Download selected text file |

New modules: `text_schemas.py`, `text_generation.py`, `local_llm.py`,
`text_jobs.py`, `text_api.py`, `text_exporting.py`; additive SQL tables
`text_jobs`, `text_samples`, `text_exports`. The existing `Worker` dispatches the
old document runner or the new text runner; document generation/export contracts
are unchanged. Frontend: `pages/TextStudio.tsx` and `textTypes.ts`.

## Verification

Final check on 2026-10-18: **28 backend tests passed**, including the original
100-document pipeline; **4 frontend component tests passed**; TypeScript/Vite
production build passed. One upstream TestClient deprecation warning remains.
Live local Qwen runs passed for all six tasks, including Hindi NER and actual
three-record classification/Q&A batches. Browser visual QA was not performed;
component tests and build checks were used without bypassing the prior browser
tool policy denial. See `samples/text/verification.json` for saved evidence.

`tests/test_text.py` covers all tasks and languages, 100-record generation,
Unicode spans, class balance, each export round trip, rejected/duplicate records,
shared queue bounds, checkpoint resume, memory pauses, recovery, invalid configs,
cloud/remote blocking, malformed model output, integrity and revalidation.
Frontend component tests exercise every task/language option, requested counts
and seeds, model controls, invalid augmentation JSON and export review gating.
The full backend regression includes the original 100-document YOLO/COCO/OCR test.

Real local Qwen tests run separately so unit tests do not require model weights:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q --basetemp=artifacts/pytest-local
.\.venv\Scripts\python.exe -X utf8 scripts/verify_text_llm.py
cd frontend
npm.cmd test
npm.cmd run build
```

Live checks use only fictional content and save their actual records, statuses
and metrics under `artifacts/text-llm/`. Large-scale LLM quality and all
task/language combinations have not been benchmarked. Browser visual QA remains
separate from the passing component/type/build checks.

Delivered examples are in [`samples/text`](../samples/text/README.md): 90
procedural records across all tasks/five languages in all three formats, plus 10
actual local Qwen examples. Real checks included all six tasks, Hindi NER and
three-record classification/Q&A batches. During implementation, live checks
caught unchanged paraphrases and model substitution of Q&A markers; stricter
paraphrase prompting and withholding answer values resolved those cases.

To exercise batched local inference separately:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/verify_text_llm.py --tasks classification qa --count 3 --batch-size 3
```
