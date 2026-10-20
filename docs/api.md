# Local API contracts

Synthetic text endpoints are additive under `/api/text/*`; see the complete
[text API and record/export contracts](text-datasets.md#api). Existing document
contracts below remain backward compatible; document rules add optional fields.

Interactive OpenAPI and schemas: `http://127.0.0.1:8000/docs`.
Optional [MCP server and tool catalog](mcp.md): stdio or Streamable HTTP at
`http://127.0.0.1:8001/mcp`, using the same API/worker.
Coordinates are canonical page pixels, never CSS display pixels. `Region.box`
is `[x, y, width, height]`, integer, inside the page. One page per template.

| Method | Endpoint | Purpose / contract |
|---|---|---|
| GET | `/api/system` | Real RAM, OCR configuration and feature availability |
| GET | `/api/addresses/countries` | Supported offline postal-reference countries, country names and subset row counts |
| POST | `/api/addresses/preview` | `{options, seed}` → address text, structured components, country/format and GeoNames attribution/version. No dataset saved; no network request. |
| POST | `/api/templates/blank` | Create an authored canvas: A4/150 DPI default, A5/Letter/custom size, portrait/landscape, white/color/transparent background and optional starter element. [Canvas guide](canvas.md) |
| POST | `/api/templates/{id}/preview` | Canvas-only `{regions, seed}` → PNG data URL and annotations. Renders unsaved layers without saving a review or queueing a job. Later layers appear on top; alpha retained. |
| POST | `/api/jobs/{id}/revalidate` | Recheck completed document images/masks and update acceptance reports. Pixels, labels and generation settings stay unchanged. Returns total/accepted/rejected/status; busy or active jobs return 409. |
| POST | `/api/portraits/batch` | Multipart `files` (multiple PNG/JPEG/WebP or ZIP), `rights_confirmed`, `license_note`, `attribution`, `max_count` (remaining slots, 1–20). Returns `{portraits, count}`; validates the complete batch before saving. Maximum 40 MB uploaded/expanded, 8 MB / 8 megapixels per image; 100 ZIP entries. Archives are read without extraction; unsafe paths, encrypted files and non-images are rejected. Existing `/api/portraits` single-image upload remains supported. |
| GET | `/api/fonts` | Installed font IDs/labels; no filesystem paths |
| POST | `/api/assets/generate` | Standalone signature/seal/stamp/QR/barcode/text/portrait; returns PNG and mask data URLs plus metadata, without saving a dataset. [Contract/examples](mcp.md#http-api-addition) |
| POST | `/api/templates/{id}/font-match` | `{region}` → region with local font/size/color selection and similarity metadata; optional configured local OCR if source text empty |
| POST | `/api/templates/{id}/detect-visual-regions` | Read-only local QR/barcode/photo proposals; `{candidates, engine, warnings}`, unconfirmed `origin:"visual"` boxes. CPU busy: 409. See [visual regions](visual-regions.md) |
| POST | `/api/document-rules/interpret` | `{region, engine:"auto"\|"local_llm"}` → validated region, explanation, engine, warnings and format references; clears confirmation |
| GET | `/api/portraits/capabilities` | Offline/upload support and online-provider configuration status |
| POST | `/api/portraits` | Multipart `file`, `rights_confirmed=true`, optional `license_note`/`attribution`; approved local image pool asset |
| POST | `/api/portraits/fetch` | `{confirm_online:true, rights_confirmed:true, license_note, attribution}`; fixed configured provider only; disabled by default |
| GET | `/api/portraits/{id}/image` | Integrity-checked normalized image |
| GET | `/api/templates` | Local templates and current revisions |
| POST | `/api/templates` | Multipart `file`, <=20 MB, decoded/verified content |
| POST | `/api/templates/demo` | Fictional PDF fixture, native text extraction, authored visual regions |
| GET | `/api/templates/{id}` | Template fields, confidence, engine, warnings |
| GET | `/api/templates/{id}/image` | Canonical PNG, source metadata removed |
| PUT | `/api/templates/{id}/review` | `{regions, privacy_confirmed, revision}`; optimistic revision check, drafts supported |
| POST | `/api/jobs` | `GenerationConfig`; confirmed regions and privacy required, 8-job bounded queue |
| GET | `/api/jobs` | Job/dataset-version history, snapshots, status and metrics |
| GET | `/api/jobs/{id}` | Progress and errors |
| POST | `/api/jobs/{id}/cancel` | Cancel queued or request cancellation after current sample |
| POST | `/api/jobs/{id}/resume` | Resume paused, cancelled or failed job using unchanged snapshot |
| GET | `/api/jobs/{id}/events` | SSE `data: Job` once/second, ends when inactive |
| GET | `/api/jobs/{id}/samples?offset=0&limit=24` | Paginated sample records; max page size 100 |
| GET | `/api/samples/{id}/image` | Generated PNG |
| GET | `/api/jobs/{id}/quality` | Counts, class histogram, rejection reasons, metrics, unchecked criteria |
| POST | `/api/jobs/{id}/exports` | `{format:"yolo"|"coco"|"ocr", review_confirmed:true}`; accepted samples only |
| GET | `/api/exports` | Local export history |
| GET | `/api/exports/{id}/download` | ZIP artifact |

Example job:

```json
{
  "template_id": "returned template UUID",
  "name": "Fictional certificate v1",
  "count": 100,
  "seed": 42,
  "blur_probability": 0.2,
  "rotation_probability": 0.15,
  "rotation_degrees": 3,
  "noise_sigma": 0,
  "signatures": true,
  "seals": true,
  "qr_codes": true,
  "barcodes": false,
  "max_retries": 2
}
```

Supported field types: text, name, address, date, email, phone, identifier,
signature, seal, qr, barcode, portrait. Portrait is appended to preserve existing
class IDs. Repeated semantic text types share values on a page; seal wording
uses its own sample/region seed. Seal content modes and the transparent preview
endpoint are documented in the [seal catalog](seals.md).
Signature and seal `rule_options` accept `ink_opacity_mode` (`random`, default;
or `fixed`), `ink_opacity` (default 1), `ink_opacity_min` (default 0.45) and
`ink_opacity_max` (default 1). Values must be finite, between 0.05 and 1, with
minimum ≤ maximum. Opacity is seeded independently and recorded in annotations;
binary masks retain every nonzero ink pixel. Other field types ignore these
options. `GET /api/signatures/previews` and `/api/signatures/preview` accept the
same four query parameters; returned preview URLs retain them. The PNG endpoint
reports the chosen strength in `X-Ink-Opacity`. Seal preview accepts them under
`options`. Neither preview creates a dataset.
These assets also accept `ink_finish` (`clean`, `natural`, `worn`; default
`natural`) and `ink_irregularity` (finite 0–1; default 0.55). Signature preview
query parameters retain both settings. The PNG response reports `X-Ink-Finish`.
Finish metadata records defects and transforms; masks reflect the resulting ink.
See the [ink finish guide](ink-finish.md) for profiles and geometry behavior.
`rule="literal:Your fictional text"` overrides generated text; empty uses Faker
or the fictional generator. Natural-language rules are compiled to bounded plans
by shorthand recognition or local Qwen. Unknown draft rules may be saved, but
final review/generation requires interpretation. No model inference occurs per
rendered image. Review the returned plan; it cannot execute arbitrary code,
fetch a model-proposed URL or access a model-proposed file.

`engine` in the response is `deterministic`, `local_qwen` or
`known_rule_fallback`. A failed/unsupported local plan may fall back to a recognized
rule, with an explicit warning; unknown rules still return 422. PAN format requests
are grounded in a bundled official TRACES reference (verified 2026-10-18).
`references` contains source title, URL, verification date, pattern and summary;
no live web search is performed by this endpoint. Model output excludes local
asset IDs; only user-selected approved assets can enter the executable region.

`Region.action` is optional `replace|erase|keep`; legacy `replace` booleans still
work when action is absent. Explicit actions synchronize that boolean.
`rule_options` supports `date_format`, ISO `date_start`/`date_end`,
`identifier_pattern` (A/9/X/- or literal text plus `{upper:N}`, `{lower:N}`,
`{digits:N}`, `{alnum:N}`, `{year}`, `{month}`, `{day}`; no automatic prefix), optional
`literal_text`, `portrait_source` (`illustration|asset_pool`) and
`portrait_asset_ids` (up to 20 local approved asset IDs). Dates must be ordered
and within 1900–2100. `rule_resolved_hash` records the interpreted prompt.
`character_length` (optional 1–128, or 1–500 for QR) and `character_set` (alnum/digits/upper/lower)
control unpatterned values in text/identifier/QR/barcode fields. Patterns produce
at most 128 characters (500 for QR) and must match any explicit length. `font_id`, optional
`font_size` (6–200 px) and hex `text_color` select installed typography. Font and
asset selection remain user-owned; Qwen cannot invent font paths or local asset IDs.
Native PDF regions may also carry `source_font` and `source_font_size` hints.
`font_weight=auto|normal|bold`, `color_mode=auto|manual`,
`background_mode=auto|solid` and `background_color` control source appearance.
Before OCR strings are sanitized from a job, automatic typography resolves PDF
metadata or local font/glyph shape comparisons and source ink color. Auto background
cleanup inpaints source lettering and renders transparent replacement glyphs;
solid fill is explicit rather than a sampled-color rectangle.

Generation config adds `identifier_length=10`, `qr_payload_length=10`,
`qr_padding=0` (0–8 modules) and `qr_required=false`. QR payload length accepts
1–500 with automatic generation; a pattern/Qwen call is optional. Required QR rejects a job
without a reviewed QR replacement region, or with QR disabled. Field patterns
and lengths override these job defaults. Borderless QR decoding is checked with
a decoder-only quiet zone when needed; no padding is added to exported pixels.
Generated values/captions contain no automatic SYN- or illustration marker;
dataset/annotation metadata records `synthetic=true` instead.
Sensitive erase-only regions must be confirmed and produce no object annotation;
`erased_regions` metadata records their original source-page coordinates.

Portrait uploads/downloads are limited to 8 MB and 8 MP, one frame, normalized
to PNG with metadata stripped and a maximum 1200-pixel side. The render selects
a pool member deterministically and crops to fill; the mask covers the photo
rectangle. Asset source, permission note and checksum enter annotation metadata.
Offline illustrations are drawings, not photorealistic faces. Online fetching
requires the explicit `.env` opt-in and both request confirmations. Provider URLs
must be public HTTPS without credentials, query, fragment or redirects. Template
content, OCR and rules are never sent to that provider. No provider is bundled.

Visual toggles control rendering in matching reviewed regions; disabled visual
regions are still erased. They do not auto-place assets into arbitrary backgrounds.

Statuses: queued → running → completed / review_required / failed. Running jobs
may transition cancelling → cancelled. Process interruption / low memory pauses
a job. The UI polls SQL-backed status; SSE is also available for clients.

Errors: 404 unknown record, 409 conflicting version/state, 413 size limit,
422 invalid schema/geometry/privacy/decoder, 429 full queue. No bulk raw SQL,
filesystem paths or arbitrary code execution endpoints are exposed. Original
recognized strings stay local in template metadata and never enter export JSON.

Review is an explicit user assertion, not evidence that all PII was detected.
The server cannot verify the honesty or completeness of an acknowledgment.


Document PII/table analysis endpoints and rendering options are documented in
[document-analysis.md](document-analysis.md#api-additions). These create editable
drafts without saving template changes. English TrOCR inference requires explicitly
installed local models; see capabilities for availability.


### Delete from the template library

`DELETE /api/templates/{id}?revision={current_revision}` returns JSON with
`deleted`, `retained_for_jobs`, `job_count`, `source_removed` and `warnings`.
A stale revision returns 409; missing/already removed templates return 404.
Unused templates and their versions are deleted from SQL. Only their verified
canonical `data/templates/{id}/page.png` is unlinked; arbitrary stored paths are
never deleted. Source cleanup failures are reported explicitly.

When generation jobs reference the template, a `deleted_templates` tombstone
removes it from library queries and blocks template reads, edits, analysis and
new jobs. Existing job snapshots and source files stay available to workers,
resume, samples and exports. The new tombstone table is created automatically
for existing SQLite/PostgreSQL databases; no existing column changes are needed.
Job submission and deletion share the queue lock to protect their source dependency.


### QR capacity preflight

`POST /api/jobs/preflight` accepts GenerationConfig and inspects the saved template
without creating a job. It returns `valid`, `errors`, `template_revision`,
`pixels_per_module` and `qr_regions`. Each QR report includes region ID/dimensions,
effective payload character count/source (literal, pattern, field length override,
or generation default), required square pixel size, whether it fits, and the
maximum automatic character count for that box/current character set/padding.
It does not return generated payload contents or alter the template.

`POST /api/jobs` enforces the same bound before adding a queue row. Resume checks
the original snapshot and rejects incompatible QR settings with 422, directing the
user to create a corrected new job. The worker retains a defensive capacity check.
The shared QR encoder uses M error correction and a minimum of three pixels per
module. Template patterns are assessed using a conservative encoding-mode bound;
random numeric runs may require less space. Actual QR decode validation remains
necessary after compositing, noise, blur and rotation.
