# Document lab and realistic capture

Open **Document lab** in the sidebar to create fictional A4 invoices or application
packs without uploading a source. This is a new authored-document workflow; the
existing template uploader remains single-page. A run supports 1–100 packs,
1–5 pages per pack, and at most 300 pages. Pages are 1240×1754 at 150 DPI.

## Content and relationships

Every pack shares its generated name, reference, birth date, age, issue/expiry
dates and line items across pages. Invoice totals use integer cents. Application
forms include filled/empty checkboxes and fictional procedural portraits.
Invoices have variable row counts, a merged pricing header and explicit cell
row/column/span metadata. These are authored invoices/applications, not arbitrary
uploaded-table reconstruction or a general page-design agent.

Names and record values are fictional. Addresses use example street names and
test postal data. QR payloads contain the generated reference, name and date.
Text and table labels come from renderer inputs, not an OCR model guessing them.

In **Generation studio**, the new field-relationship controls also work on uploaded
templates: copy/join source fields (including QR/barcode payloads), calculate age
at a selected date, offset a date, or sum numeric fields. Select source and target
fields explicitly. Date formats come from field settings. Cycles, unknown fields
and invalid numeric/date inputs are rejected. Rules override target generated
values; choose compatible lengths and code sizes for the resulting payload.

## Capture and handwriting

Phone capture adds a bounded perspective homography, uneven lighting, a fold
shadow, blur/noise and JPEG compression. Scanner, photocopy and narrow-margin
cropped-scan presets are available, individually or mixed. Masks undergo exactly
the same geometry; they describe ideal ink support before optical effects.
Capture simulates opaque paper; opting into it on a transparent canvas gives an
opaque photographed/scanned result. The default existing-template preset is None.

Document lab exports paired clean and captured images. Handwritten fields use
local cursive glyphs with seeded spacing, rotation and baseline drift. This is
font-based synthesis, not a trained handwriting model. The original text remains
known ground truth. Uploaded-template text fields can select **Handwritten** in
Writing style. Procedural pen signatures use connected letter paths, original
large-initial/open-loop compositions and continuous speed-dependent pressure.
The supplied examples inform structure, not pixel tracing or named replicas.

## Controlled composition and splits

Capture, handwriting, faint ink, signature, seal and negative rates are planned
per document, not per page. Rates round to whole packs. Negatives omit both
signatures and seals; mark quotas are capped by eligible packs. Faint quotas are
capped by packs that have a mark. The exported plans record actual membership;
some categories intentionally overlap.

Layout families are assigned wholly to train/validation/test. A family's signer
and procedural portrait identity stay in the same split. Actual percentages
can differ from requested percentages because groups are indivisible. At least
three families are needed for three non-empty splits. This guards the generated
families; it does not establish independence from external training datasets.

## Review, correction and regeneration

Completed pages have an editable class, text and box list, plus an exclusion
checkbox. Existing dataset gallery samples have the same controls. Saves use
optimistic revision checks and retain previous annotation JSON. An unchanged box
keeps its ink mask; a moved/new box receives a rectangular mask explicitly marked
as a human box, not pixel-level segmentation. Removed labels disappear from new
exports. Existing downloaded/exported ZIPs remain snapshots.

Regenerate one template sample or one entire authored pack. A pack regenerates
all its pages with consistent new values before switching to the new output;
its layout family, reference and split stay fixed. Previous image/mask folders
remain on disk. Completed lab runs can export accepted pages as PNGs, per-pack
raster PDFs, YOLO labels, COCO boxes/RLE masks, OCR JSON, tables and relationships.
Excluding a page can leave a partial PDF; the manifest retains original page IDs.
Resume interrupted generation without redoing completed pages. Keep DataForge
running for long batches; memory guards pause work when RAM is low.

## Stable Diffusion trials

AI image studio and signature regions now offer **Single signature · guided Stable Diffusion**, using the already-installed offline SD-Turbo. Results are converted
to transparent monochrome artwork and may be selected as a signature image pool.
Color, thickness, finish and opacity still apply in the renderer. Annotation text
is empty for these assets: the model's spelling is unverified. Remove the pool to
return to procedural signatures.

Two real two-step CPU trials on 2026-10-24 produced a sheet of multiple autographs
and dense/cropped abstract strokes. Neither was automatically saved to an asset
pool. The mode is exposed for experimentation, not claimed to outperform the
procedural renderer. A separate real oak-wreath seal-emblem trial was usable as
artwork; exact seal wording remains native rendering. No new model download or
fine-tuning is needed for these options. SD-Turbo's model card documents its
[inability to render legible text](https://huggingface.co/stabilityai/sd-turbo#limitations-and-bias).

## API and MCP

- `/api/document-lab/jobs`: POST configuration, GET runs.
- `/api/document-lab/jobs/{id}`: GET progress, plans, pages and download URL.
- `/api/document-lab/jobs/{id}/cancel` and `/resume`: POST job control.
- `/api/document-lab/jobs/{id}/pages/{document}/{page}`: GET metadata, PUT labels.
- The page `/image` route serves the current PNG.
- `/api/document-lab/jobs/{id}/documents/{document}/regenerate`: POST one pack.
- `/api/document-lab/jobs/{id}/download`: accepted-page ZIP, with grouped splits.
- `/api/samples/{id}/annotations`: GET metadata, PUT label corrections.
- `/api/samples/{id}/regenerate`: POST one existing template-generated sample.
- `DiffusionRequest.kind=signature_artwork` supports existing image job tools.

MCP adds 11 tools for pack runs, review and regeneration, for 64 tools total.
See the live schemas (`LabConfig`, `SampleEdit`, `GenerationConfig`, `RuleOptions`)
for bounds and defaults. All processing remains local and serialized by the CPU
lock. Structural checks and visual inspection do not prove training utility.

The earlier free text-to-image signature trials above describe the original experiment. The current signature path uses a single-autograph image-to-image guide and geometric isolation, with optional recoloring. Full text-based seal batches now have a separate native-rendering choice. See [current ink workflow](image-generation.md#single-signatures-text-seals-and-recoloring).
