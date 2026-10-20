# DataForge AI MCP server

Connect a standard MCP client to DataForge's signatures, seals, paper postage/revenue stamps, rubber stamps,
QR codes, Code128 barcodes, text/portrait assets, templates, document analysis,
document datasets and synthetic text datasets. Uses the
[official MCP Python SDK](https://py.sdk.modelcontextprotocol.io/v1/), with its
v1 compatibility line explicitly bounded to `<2` in `requirements-mcp.txt`.

The optional adapter calls the existing loopback FastAPI API. It does not start
another database or worker and has no SDK dependency in the normal web startup.
Run both processes on the same computer. Any MCP client with stdio or Streamable
HTTP support can use it; no Codex-specific connector is required. This is a local
service, not a deployed public endpoint or an authenticated multi-user service.

## Setup and start

From the project root (Windows PowerShell):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-mcp.txt
npm.cmd start
```

Keep the normal DataForge API running. The browser UI is optional for MCP calls.
For macOS/Linux use `.venv/bin/python` and `npm` instead.

### Streamable HTTP

In a second terminal:

```powershell
npm.cmd run mcp
```

The MCP endpoint is **http://127.0.0.1:8001/mcp**. This is a protocol endpoint;
use an MCP client rather than browsing to it. Customize the port or local API:

```powershell
npm.cmd run mcp -- --port 8002 --api-url http://127.0.0.1:8000
```

Print a client configuration with the selected HTTP URL:

```powershell
.\.venv\Scripts\python.exe scripts/mcp_config.py --transport http
```

The generated `mcpServers` format is common to several clients. Some clients use
different top-level settings keys; copy the `url` into that client's MCP settings.
Nothing is registered or written to your client automatically.

If port 8000 belongs to another application, run DataForge with
`npm.cmd start -- --api-port 8002`. The browser stays on port 5173. Start MCP
with `npm.cmd run mcp -- --api-url http://127.0.0.1:8002`, or generate the stdio
configuration using `scripts/mcp_config.py --api-url http://127.0.0.1:8002`.
The MCP setup page displays commands for the running DataForge API port.

### Stdio

Print configuration containing the exact absolute executable and entry point for
this checkout:

```powershell
.\.venv\Scripts\python.exe scripts/mcp_config.py
```

Copy the resulting `mcpServers.dataforge` entry into your client's MCP settings.
The client starts/stops its MCP process. Launches use `scripts/run_mcp.py`, which
sets the project directory so it works from any client working directory. The
entry point keeps protocol stdout clean. **Do not use `npm run mcp` as the stdio
client command**, because npm writes a startup banner. Stdio needs no port 8001.

## Tool catalog

| Area | MCP tools |
|---|---|
| Discovery | `get_capabilities`, `list_fonts`, `list_address_countries` |
| Standalone images | `generate_asset`, `generate_signature`, `generate_seal`, `generate_stamp`, `generate_rubber_stamp`, `generate_qr`, `generate_barcode`, `generate_address` |
| Templates | `list_templates`, `get_template`, `upload_template`, `create_demo_template`, `create_blank_template`, `preview_canvas`, `save_template_review`, `delete_template` |
| Analysis | `detect_visual_regions`, `analyze_pii`, `extract_table`, `structure_table`, `interpret_rule`, `match_font` |
| Photos/images | `import_portrait`, `import_portrait_batch`, `get_image` |
| Datasets | `list_jobs`, `preflight_document_dataset`, `create_document_dataset`, `create_text_dataset`, `get_job`, `get_samples`, `get_quality`, `cancel_job`, `resume_job`, `revalidate_document_dataset`, `delete_dataset` |
| Text validation | `get_text_manifest`, `validate_text_dataset` |
| Export | `export_dataset`, `list_exports`, `read_export_chunk` |

Resources: **dataforge://guide** (this guide), **dataforge://schemas** (complete
Pydantic schemas/options), **dataforge://templates** (current library).
Tool input schemas expose typed fields, bounds, enums and nested configuration.
Tools have MCP read/write/destructive hints. The hints do not grant consent.

Address generation: set `options.address_country` to a country returned by
`list_address_countries`, and `options.address_format` to a template such as
`{street}\n{city}\n{state}\n{country}\n{postal_code}`. `generate_address` produces
the PNG/mask and structured address/source metadata. The generic `generate_asset`
also accepts `kind: "address"`; saved address regions use the same settings in
document jobs. Countries: IN, US, GB, CA, AU, DE, FR, NZ, ES, IT, MY, PK.
GeoNames locality/state/postal rows are bundled; street/house number are synthetic.
Generation is offline and seeded. See [address controls and prompts](addresses.md).

`create_blank_template` accepts a `request` with `paper` (`a4` default, `a5`,
`letter`, `custom`), `dpi` (72–300, default 150), `orientation`, `background`
(`white`, `transparent`, `color`), `background_color` and optional `starter` element.
For custom sizes set `unit` to `mm` or `px` and supply `width` / `height`.
Canvases are limited to 12 megapixels and 64–6000 pixels per side.
`preview_canvas` takes the template ID plus `request: {regions, seed}` and returns
the PNG image and annotation metadata without saving a review or starting a job.
Later regions appear on top; overlap is supported only on authored canvases.
Transparent canvas alpha is retained through preview, dataset PNGs and ZIP export.
`drawing` is class 14; its `options.drawing_points` are 0–1 relative XY pairs
(maximum 4000 points), with `drawing_width` in pixels. Existing class IDs stay fixed.

Photos support `options.portrait_background`: `preserve` (default), `transparent`,
`solid` or `random`, plus `portrait_background_color` / `portrait_background_palette`.
Existing PNG alpha is preserved. Otherwise a local approximate foreground cutout
is used; inspect hair and complex scenes in the preview. Source image pools are
not modified. Select a transparent canvas to export cutouts without a page background.

`import_portrait_batch` accepts `uploads: [{file_name, content_base64}]` for multiple
PNG/JPEG/WebP images or ZIPs, `rights_confirmed`, permission/attribution notes and
`max_count` (remaining pool capacity, 1–20). MCP transfer bytes are limited to
20 MB combined; the web batch endpoint permits 40 MB. Each image is limited to
8 MB / 8 megapixels, with 40 MB total expanded image bytes and 20 selected images.
Validation failure imports nothing. Returned IDs can be appended to the region's
`portrait_asset_ids`. Existing IDs remain selected until explicitly removed.

Signature `options.signature_thickness` accepts 1–5. Default 1 preserves current
random pen weights. Higher values thicken strokes while retaining seeded lettering,
style and layout, and work in assets, document jobs and signature previews.

`options.signature_content` accepts `current` (legacy behavior, API default),
`name` (all name words), `alphabet` (1–3 initials/letters), or `mixed` (seeded mix).
Document batches can set `config.signature_content_override` to one of these,
or null to use saved per-region choices. The browser defaults new batches to mixed.
This setting is independent of `signature_style` and its batch override.

Ink colors use `color_mode` (`black` default, `manual`, `random`, `auto` for source
matching, or `mixed` for different seal border/text colors), `text_color` (`#RRGGBB`)
and `color_palette` (1–20 hex colors). Random colors use an independent seeded
stream. Legacy named `seal_color` settings remain supported. Signature previews
accept the same options as query parameters, with repeated `color_palette` keys.

### Signatures and stamps

`generate_signature` arguments:

```json
{
  "name": "Mira Dev",
  "width": 480,
  "height": 160,
  "seed": 42,
  "options": {
    "signature_style": "interwoven",
    "ink_opacity_mode": "random",
    "ink_opacity_min": 0.45,
    "ink_opacity_max": 1.0,
    "ink_finish": "natural",
    "ink_irregularity": 0.65
  }
}
```

`generate_stamp` creates a paper postage/revenue stamp, for example
`{"caption":"HERITAGE SERIES","seed":73,"options":{"stamp_style":"revenue","stamp_palette":"purple"}}`.
`generate_rubber_stamp` with `{"text":"PAID","seed":73}` creates a separate ink-only mark.
`generate_seal` accepts all existing RuleOptions: shape, random/static/custom
wording, placeholders, borders, ink color, embedded synthetic signing text, wear,
opacity and natural/worn imperfections. The three separate fields use classes
`seal`, `stamp` and `rubber_stamp`. The two new classes are appended so existing
class IDs stay stable. [Stamp controls, references and mask semantics](stamps.md).

Image generation returns native MCP image blocks in this order: **asset PNG**,
then **mask PNG**, plus structured metadata (dimensions, seed, value, hashes,
bounding box and renderer details). No dataset or server file is saved. A client
can decode the image blocks to save the PNGs. Same seed/options/runtime reproduce
procedural output. Rubber-stamp ink remains transparent; paper postage/revenue
stamps have opaque paper and transparent perforations/outside edges. Portraits are opaque.

For text and portrait assets, use the general tool:

```json
{"request":{"kind":"text","value":"Example text","width":500,"height":120,"seed":42}}
```

```json
{"request":{"kind":"portrait","width":240,"height":320,"seed":42}}
```

The default portrait is a procedural illustration. For photographic output,
`import_portrait` requires approved image bytes and `rights_confirmed:true`; use
the returned ID in `options.portrait_asset_ids` with `portrait_source:"asset_pool"`.
MCP does not scrape photographs or download new models. Local Qwen/TrOCR/Paddle
still require their existing local setup. Check `get_capabilities` first.

### Upload, label and create a document dataset

1. Call `upload_template` with `file_name` and plain `content_base64` (no data URL).
   Supported: one-page PDF, PNG, JPEG, TIFF, up to 20 MB. Photo imports allow 8 MB.
2. Inspect `get_template` and `get_image` with `image_type:"template"` and its ID.
   Uploads include OCR and QR/barcode/photo proposals. `detect_visual_regions`
   rescans without changing the saved template. `analyze_pii` proposes grounded
   sensitive values. Photo bounds and OCR can be wrong; edit/delete suggestions.
3. `save_template_review` takes the current `revision`, edited `regions`, and
   `privacy_confirmed`. Save drafts with false. Set confirmation flags only after
   review. Normal geometry, overlap, source/font/portrait and privacy checks stay
   in place; the adapter cannot bypass them.
4. Call `preflight_document_dataset` and `create_document_dataset` with a
   `GenerationConfig`, for example `{"config":{"template_id":"ID","count":10,"seed":42}}`.
5. Poll `get_job`, then inspect `get_samples`, sample `get_image` and `get_quality`.
6. `export_dataset` with `dataset:"document"`, `format:"yolo"`, `"coco"` or `"ocr"`
   and an actual `review_confirmed:true`. Returns a ZIP export ID and URL.

Template reviews use optimistic revisions. Deletion tools require
`confirm_delete:true`; active jobs must be stopped before dataset deletion.
Deleted library templates remain available to existing dataset snapshots when
needed. Resume keeps the original job settings; create a new job to apply edits.

### Synthetic text datasets

Example `create_text_dataset` call:

```json
{"config":{"name":"Customer feedback","task":"classification","count":20,"seed":42,"languages":["en","hi"],"backend":"procedural"}}
```

Tasks: classification, NER, Q&A, instruction-response, conversation, augmentation.
Languages: English, Hindi, Spanish, French, German. Use `backend:"ollama"` for the
configured local LLM, or procedural templates. Augmentation requires source text;
custom procedural labels require class templates, as in the web API. Use
`dataset:"text"` in polling/sample/quality/export tools. Available exports are CSV,
JSON and JSONL. Existing validation/review gates and sample limits remain intact.

### Transfer exports through MCP

`read_export_chunk` accepts `export_id`, `dataset`, `offset` (default 0) and
`max_bytes` (default 262144, maximum 1048576). Base64-decode `data_base64`, append
bytes locally, and repeat with `next_offset` until `eof:true`. Each response
includes total size and a chunk SHA-256. The adapter validates HTTP byte ranges
and does not read/write arbitrary filesystem paths. Returned download URLs are
absolute loopback URLs, usable on the API's computer. Image reads are limited to
16 MB; general JSON responses to 32 MB. Use pagination and chunks for large data.

## HTTP API addition

`POST /api/assets/generate` accepts `AssetRequest` (same `request` object as
`generate_asset`). Returns base64 PNG data URLs in `image` and `mask`, plus
`metadata`. Kinds: signature, seal, stamp, rubber_stamp, qr, barcode, text, portrait. Width/height
16–2048, seed 0–2147483647. Explicit QR payloads max 500 characters, barcode max
128 ASCII characters. Normal QR pixel-capacity checks are enforced. This endpoint
is additive; existing signature/seal previews and document rendering are unchanged.

MCP is served on its own port/process. `/api/assets/generate` is a REST endpoint;
it is not itself the MCP transport. Tool calls use the running backend's data
directory and single worker, and failed mutating calls are never auto-retried.
