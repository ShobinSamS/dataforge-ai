# Document analysis, handwriting and asset rendering

In Template editor, immediately after upload, use **Find PII and extract tables**.

1. Choose existing PDF/OCR text, **English printed · TrOCR**, or **English handwriting · TrOCR**.
2. Click **Find PII and auto-label**. Existing text is classified by local Qwen plus
   rules. With TrOCR, existing boxes are single-line crops; if there are no boxes,
   OpenCV proposes lines across the page. Up to 80 groups are analyzed per request.
3. Pink dashed rectangles show suggestions. Correct the labels/types, uncheck false
   positives, and optionally check that you verified the selected boxes. Apply them
   as erase regions. Untouched upload OCR proposals are replaced; edited/manual
   regions are kept. Conflicting boxes are skipped with a count. Move/resize/delete
   the resulting regions as usual. Choose Replace if synthetic values are wanted.
4. Review the entire page and save the review before generation. Analysis does not
   modify source pixels, save a template version, or confirm the whole page for you.

Qwen returns source IDs, semantic categories, a literal evidence quote and a short
reason. A validator rejects quotes absent from the source, labels without values,
public organization/promotional text, and identifiers without an actual code or
number. The review panel prominently shows the extracted value, reason and source
OCR line, and permits correcting transcription before applying it. Coordinates always come from
OCR or user-authored crops. It cannot invent locations or execute document text.
Names, addresses, email, phone, dates, generic document/account IDs, financial
and contextual medical values are supported categories. Public organization names
and untyped "other" model guesses are not automatically selected. This is not restricted
to one document type. Complete OCR line boxes are used; labels on the same line
may also be erased. Recognition omissions, false positives, photos, signatures,
seals and encoded codes still require inspection. A failed model request is
explicitly labeled as partial/rule fallback. Rules alone do not find every name.

## English transformer OCR setup

The base app works without these dependencies. Both small models are installed
locally in the development workspace used for this change. For a fresh checkout:

```powershell
.\.venv\Scripts\python.exe -m pip install "torch>=2.6,<3" --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-vision.txt
.\.venv\Scripts\python.exe scripts/setup_vision_models.py --mode both
```

The setup script explicitly downloads public Microsoft model files at pinned
revisions into ignored `data/models/` folders and records SHA-256 manifests.
Application inference uses `local_files_only=True`, CPU inference mode, no
remote code and a shared CPU lock. Models are released between OCR and Qwen.
Runtime inference never downloads or sends document data to a provider.
The model directory follows `DATAFORGE_DATA_DIR` (the setup script's `--directory`
can target that directory's `models/` subfolder). At least 1.8 GB free RAM is required.
The models are optional, with installation status exposed through capabilities.

The [Microsoft handwritten model](https://huggingface.co/microsoft/trocr-small-handwritten)
is a transformer encoder/decoder fine-tuned on IAM. It recognizes single text-line
crops; it does not locate page text or identify a writer. The
[printed variant](https://huggingface.co/microsoft/trocr-small-printed) is separate.
Colored-background line proposals use local contrast and glyph-size checks rather
than a page-wide brightness threshold. Low-likelihood OCR groups (below 0.5) are
excluded from automatic PII selection with a warning to inspect those areas. The
likelihood threshold is not an accuracy guarantee.

OpenCV line proposals are a practical initial detector, not a trained handwriting
layout model. Joined lines, skew, faint ink, overlaps and ruled grids can defeat it.
Use corrected single-line boxes. No Indian English handwriting accuracy claim is
made without a representative, consented evaluation set. Scores are token
likelihoods, not calibrated accuracy. Blank low-contrast crops remain blank.

Local trials on 2026-10-18:

| Input | Actual result | Implication |
|---|---|---|
| Synthetic Segoe Script line `Name: Arun Kumar` | `Namei Arun Kumar` | Loaded and ran locally; punctuation error, human correction required |
| Synthetic printed `Invoice number: DEMO7842` | `INVOICE NUMBER: DEMO7842` | Correct words/numbers with case normalization |
| Public IAM example linked by the model card | Download connection failed | Real handwriting evaluation not completed; font trial is not a handwriting benchmark |
| Four-cell synthetic cursive table (`Name`, `City`, `Arun Kumar`, `Delhi`) | All four cells detected; `Name ...`, `city .`, `Arun Kumar .`, `Delhi .` | Punctuation/case errors require correction; Qwen preserved the exact source transcriptions when structuring |

A fictional six-line local Qwen trial initially over-selected a form heading and
mislabeled an email. The pipeline now preserves stronger email/identifier rule
evidence and excludes common empty headings. A repeat returned name, email,
address, document number and birth date correctly, omitting the form title. This
small fixture is an integration check, not a PII recall benchmark.

An HTTP upload → printed TrOCR → local Qwen → reviewed erase → generation trial
also completed successfully on a fictional two-field image. Both fields were
removed and the generic heading/background remained. The generated sample passed
the existing bounds, masks, coverage and image-integrity validation. Backend tests
(66), frontend tests (17) and the frontend production build passed. These checks
do not establish general OCR or PII accuracy.

Synthetic handwriting uses installed English script fonts (Segoe Script preferred,
then other available script/italic faces). It does not clone an uploaded person's
handwriting. Font binaries are not bundled. Choose **English cursive font** under
Rendering style; use Font and appearance to override family, weight, size and ink.

## Structured tables

**Extract ruled table** detects enclosed rectangular grid cells using OpenCV and
retains source-page coordinates, table ID, row, column, text and OCR score. Up to
80 cells are accepted. Existing OCR boxes must fit inside a cell; spanning text
is left unassigned. Choose TrOCR printed/handwritten to recognize one line per
cell instead. Inspect/correct transcriptions and layout in the editable cell list.

**Structure cells with local Qwen** proposes row/column assignments using cell IDs.
The backend checks complete ID coverage, unique positions and bounds. All text
is copied from source cells; the LLM cannot complete blanks or rewrite values.
Oversized requests are rejected with a context-budget explanation. Failed or
invalid structure leaves the current table intact. Multiple grids are processed
separately. JSON includes cell coordinates; CSV emits a matrix per table, separated
by a blank row, quotes values and escapes spreadsheet formula prefixes. These
exports contain source transcriptions, not anonymized synthetic text.

Borderless tables, merged cells, nested layouts and multi-line handwritten cells
are not reliably supported. A layout transformer such as
[Microsoft Table Transformer](https://huggingface.co/microsoft/table-transformer-structure-recognition)
would be a separate evaluated detector; it is not enabled or downloaded here.
Qwen cannot recover text that OCR did not read correctly. The editor flags this
as experimental rather than claiming arbitrary handwritten-table accuracy.

## Removing original ink and rendering assets

- **Restore entire selected region** is the default: source pixels are inpainted
  before rendering text, signatures, seals, QR or barcode assets. Include all old
  strokes inside the selection. Surrounding pixels remain outside the operation.
  Textures are estimates; hidden background cannot be recovered exactly. An explicit
  solid fill remains available. **Remove detected ink only** preserves more texture
  but can leave faint original strokes and should be inspected closely.
- Text layers have transparent backgrounds. Automatic weight/color matching and
  manual font controls remain available; exact unavailable fonts cannot be inferred.
- QR and Code 128 white/light cells are transparent by default. Optional white
  backgrounds remain available. Detection masks cover the full logical code
  rectangle, including transparent modules. QR padding is still configurable and
  zero by default; payloads can reach 500 characters without patterns or an LLM.
  Dark/textured backgrounds may fail QR decoding; generation validation reports
  unreadable QR codes. Barcode decoding is not implemented.
- Signatures render a seeded fictional person's name or initials in a script font,
  optionally adding overlaid curves and an underline. A literal rule can provide
  fictional signing text. Source signatures are never traced.
- Seals support randomized or fixed ring, round, rectangle and text styles,
  red/blue/green/mixed ink, configurable main/inner text and seeded wear. Ring text
  follows an oval. The old seal is removed first by full-region cleanup; it is not
  pasted over. Synthetic provenance stays in exported metadata.

## API additions

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/document-analysis/capabilities` | Runtime/model status and limits |
| POST | `/api/templates/{id}/analyze-pii` | Draft PII suggestions; no template mutation |
| POST | `/api/templates/{id}/extract-table` | Ruled-grid cells with text/coordinates |
| POST | `/api/document-analysis/structure-table` | Validated cell-ID layout from local Qwen |

Analysis requests accept `regions`, `ocr_mode` (`existing`, `printed`, `handwritten`)
and `engine` (`local_qwen`, `regex`). Regions are validated against canonical page
dimensions. Existing review and generation endpoints remain the commit boundary.
The original field-type class order is unchanged, keeping existing YOLO IDs stable.


## Value-versus-label regression check

The supplied PAN-services sample was used locally to reproduce over-selection.
The updated run selected only the displayed identifier and date rectangles, without
a person-name candidate. Government/department headings, Name labels and
"PAN CARD APPLY ONLINE" advertising text stayed unselected. No user image was
added to the repository. TrOCR misread one identifier character (X as Y) even after contrast/binarization
trials, while reading the displayed date correctly.
The editable extracted-value field makes this error visible; no guessed character
correction is silently applied. The date label in the source is incorporation/formation,
so it must not be described automatically as a birth date.

Extracted-value and reason strings are stripped along with original OCR text before
a generation job snapshot/export; they remain local review metadata only.
