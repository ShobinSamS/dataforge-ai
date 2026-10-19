# DataForge AI — How-to Catalog

**Choose a recipe, follow the steps, then review and export.**
This catalog describes the features currently implemented in this workspace.

**App:** [Open DataForge](http://127.0.0.1:5173/) ·
**API:** [Interactive API documentation](http://127.0.0.1:8000/docs)

## Catalog index

| Catalog item | Use it when you want to… |
|---|---|
| [01 · Start and stop](#01--start-and-stop) | Open the local app or restart after an update |
| [02 · Find a feature](#02--find-a-feature) | Understand the sidebar and feature availability |
| [03 · Generate documents](#03--generate-documents) | Turn one certificate or form into annotated images |
| [04 · Classify text](#04--classify-text) | Generate labeled sentiment or custom-category examples |
| [05 · Generate NER data](#05--generate-ner-data) | Produce text with entity spans and BIO labels |
| [06 · Generate QA pairs](#06--generate-qa-pairs) | Create fictional contexts, questions and exact answer spans |
| [07 · Generate instruction–response data](#07--generate-instructionresponse-data) | Create instruction and response pairs |
| [08 · Generate conversations](#08--generate-conversations) | Create alternating user/assistant messages |
| [09 · Augment existing text](#09--augment-existing-text) | Make variations while retaining source lineage |
| [10 · Use multiple languages](#10--use-multiple-languages) | Generate English, Spanish, French, German or Hindi text |
| [11 · Monitor and recover jobs](#11--monitor-and-recover-jobs) | Check progress, cancel, resume or reuse a configuration |
| [12 · Review and export](#12--review-and-export) | Choose a format and download accepted records |
| [13 · Controls reference](#13--controls-reference) | Look up counts, seeds, batches and resource settings |
| [14 · Troubleshooting](#14--troubleshooting) | Resolve common errors |
| [15 · Samples and further reading](#15--samples-and-further-reading) | Open working examples and detailed specifications |

## 01 · Start and stop

If DataForge is already running, open or refresh the app. The launcher reuses
its existing servers and never starts a second API worker on the same port.

From PowerShell in the project folder:

```powershell
# First-time dependency setup only:
npm.cmd run setup

# Start the app:
npm.cmd start
```

The launcher starts the API on port **8000**, the interface on **5173**, and opens
the app. Keep the launcher running. Press **Ctrl+C in the launcher** to stop the
processes it started. If you launched the frontend/API in separate terminals,
stop each with Ctrl+C instead.

After a backend code or `.env` change, stop and restart your app processes.
Refreshing the browser alone does not reload backend routes or settings.

The procedural workflows need no AI model. For **Local Qwen · Ollama**, an Ollama
service and the configured local `qwen3:1.7b` model must already be available.
DataForge does not install/start Ollama or download model weights automatically.

## 02 · Find a feature

| Sidebar/page | What you can do | Availability |
|---|---|---|
| Dashboard | Open the fictional document demo and see document activity | Available |
| Template library | Upload/open a single-page template | Available |
| Template editor | Draw, move, resize and review replacement regions | Available after opening a template |
| Generation studio | Configure synthetic document images and assets | Available |
| Text datasets | Generate, inspect, validate and export text datasets | Available |
| Dataset gallery / Annotation preview | Inspect generated document images and boxes | Available; generated annotations are read-only |
| Quality dashboard | Inspect document validation and class counts | Available |
| Job monitor | Monitor document generation jobs | Available; text jobs appear inside Text datasets |
| Export & history | Export document datasets and retrieve previous ZIPs | Available; text exports have their own section |
| Settings | View runtime configuration and capability status | Available; edit `.env` to change server settings |
| AI image studio | Read diffusion integration status | Planned; diffusion is not enabled |
| Agent activity | Read agent integration status | Planned; Qwen text generation works independently |
| MCP tools | Read MCP integration status | Planned; no MCP server runs |

**Choose an engine for text:**

| Engine | Suitable starting point | Important limit |
|---|---|---|
| Procedural · authored templates, no model | Fast pipeline checks, reproducible fixtures, exact constructed labels | Small authored corpus; not open-domain writing |
| Local Qwen · Ollama | Topic-specific text, varied instructions/conversations, paraphrases | CPU inference takes longer; language, meaning and labels need review |

## 03 · Generate documents

**Goal:** Create 100 fictional certificate images with annotations.

1. On **Dashboard**, click **Try a fictional template**. Alternatively, use
   **New template** in the Template library to upload your own document.
2. In the editor, select each region that needs replacement. Set its **Field
   type**, boundaries, sensitivity and **Action** (replace, erase only, keep).
3. Check **I verified this region** for each sensitive replacement region.
   For the demo, review the name, ID, date, email, signature, seal and QR regions.
4. Inspect the whole page. If a sensitive area is missing, use **+** on the
   canvas to draw a region. Drag/resize boxes; use the hand tool to pan and the
   zoom buttons or mouse wheel to zoom.
5. Confirm the full-page privacy review, then click **Save review**.
6. Open **Generation studio**. Choose the reviewed template and set:

   | Control | Suggested first run |
   |---|---|
   | Dataset name | `Fictional certificates` |
   | Number of samples | `100` |
   | Random seed | `42` |
   | Blurry samples | `20%` |
   | Rotated samples | `15%` |
   | Maximum rotation | `3°` |
   | Noise | `0` initially |

7. Enable fictional signatures, seals and QR codes if matching reviewed regions
   exist. Click **Generate 100 samples**.
8. Follow the **Job monitor**, inspect **Dataset gallery**, then check the
   **Quality dashboard** and export using [item 12](#12--review-and-export).

**Delete a template:** In **Template library**, use **Delete** under the card and
confirm the named template. Unused templates lose their source image and saved
reviews. Templates linked to generation jobs are removed from the library, while
their source, jobs, samples and exports remain available for that history. They
cannot be selected for new generation. Cancelling the dialog changes nothing.
A stale revision is rejected; reload the library if another review was saved.

**Upload support:** PDF, PNG, JPG/JPEG and single-frame TIFF; one page/frame,
up to 20 MB and 16 megapixels for images. Split multi-page PDFs first. Native
PDF text extraction works without OCR. Raster text detection needs installed
local PaddleOCR/Tesseract, or the optional TrOCR models in the new analysis panel;
otherwise draw regions manually. English handwriting and visual identifiers need manual review.

**After upload:** Open **Find PII and extract tables** in Template editor. Choose existing
text or installed TrOCR recognition, then **Find PII and auto-label**. Pink dashed boxes
preview suggestions. The panel shows the actual **Extracted value**, **Why selected**
and original OCR line. Headings, empty labels and advertising text are not values.
Use **Correct extracted value** for transcription errors (OCR may confuse X/Y even
with a high score). Uncheck mistakes or correct labels/types, optionally confirm the
selected suggestions, then **Apply selected as erase regions**. Boxes remain editable
on the canvas; choose Replace if you want synthetic values instead. Source pixels stay
unchanged until generation. Untouched upload OCR suggestions are replaced; manual edits
are preserved and overlapping suggestions are skipped. Review the full page and save.

**Tables / handwriting:** **Extract ruled table** finds enclosed cells. Select English
handwriting for one handwritten line per cell. Correct transcription/rows/columns,
optionally **Structure cells with local Qwen**, then export CSV/JSON. Qwen rearranges
source IDs and never fills missing text. Borderless tables, merged cells and multi-line
cells need manual handling. Model setup, limits and trial results are in
[Document analysis](docs/document-analysis.md).

**Prompt rules:** Select a region, enter a **Rule prompt**, then click **Apply rule**.
Common instructions are interpreted immediately. Other prompts use the installed
local Qwen model; **Interpret with local Qwen** attempts model interpretation.
Review the resulting action, field type and options before checking **I verified
this region**. Applying a rule clears that confirmation. Changing explicit
controls clears the prompt. A rule is compiled once; generation runs the saved
plan without invoking the model for every image. Unsupported operations are
rejected. Drafts may retain unresolved prompts, but generation requires resolution.

For `pan card pattern`, `pancard format` and `permanent account number format`,
the planner supplies local Qwen with a bundled reference to the
[official TRACES PAN structure](https://traces61contents.tdscpc.gov.in/en/faq-general-pan.html).
The broad character pattern is `AAAAA9999A`; no prefix is added.
The editor displays the resolved pattern and source link. If local Qwen cannot
return a usable plan for a recognized rule, it applies the known rule and clearly
labels **Applied recognized rule fallback**. Unrecognized rules still fail without
changing the region. The format reference was checked on 2026-10-18 and is cached;
the application does not perform arbitrary live web scraping or send your prompt
or template to a search engine.

| Prompt / control | Result |
|---|---|
| Empty prompt | Automatic fictional values for the selected type |
| `literal:Fictional Training Program` | Exact fictional replacement text |
| `dd/mm/yyyy` | Random date formatted with day first; set earliest/latest dates |
| `DOB between 1980 and 2000 in dd/mm/yyyy` | Fictional birth date in that range |
| `PAN number` | Character pattern `AAAAA9999A`; no added prefix |
| `Invoice code INV- then 2 uppercase letters, a hyphen and 6 digits` | Qwen compiles `INV-{upper:2}-{digits:6}` |
| `4 lowercase letters followed by 8 digits` | Qwen compiles `{lower:4}{digits:8}` |
| `a human photo has to be placed` | Portrait field; select illustration or image pool |
| `remove this completely` | Erase only; no replacement and no object label |

For identifier patterns, **A** means uppercase letter, **9** means digit, **X**
means letter/digit, and **-** means a literal hyphen. Generic templates also accept
literal text with `{upper:N}`, `{lower:N}`, `{digits:N}`, `{alnum:N}`, `{year}`,
`{month}` and `{day}`. Date tokens share one generated date within the selected
bounds. Qwen compiles custom formats for invoice, employee, SKU and serial codes;
generation executes the validated pattern with seeded random values. Patterns
produce 1–128 characters for text/identifiers/barcodes, or up to 500 for QR payloads. Checksums, externally verified IDs and incrementing
sequences are outside this template grammar. The explicit
date controls support five formats and bounds within 1900–2100. Repeated semantic
types share generated values; date consistency uses matching bounds and identifier
consistency uses matching patterns.

**Lengths and QR controls:** In each text/identifier/QR/barcode field, set
**Generated character length** and **Character set**, or leave length automatic.
An explicit pattern controls the whole value; any configured length must match
its output including literal prefixes/separators. In **Generation studio →
Generated content**, choose default identifier length, QR payload characters,
QR padding (0–8 modules) and whether a reviewed QR region is required. Existing
QR/barcode switches still control whether reviewed regions are rendered. Defaults
are 10 characters and zero QR padding. QR length accepts 1–500 characters and
needs no custom pattern or model: leave **Optional custom pattern** empty and
the payload is generated automatically. Use Qwen only when you want a particular
format. Borderless QR output may need clear
surrounding space for scanners. Larger payloads require larger QR regions.

**QR size check:** Generation studio shows the effective payload and minimum pixel
size for every saved QR field before queueing. A per-field **Generated character
length** overrides the global QR payload setting, even if you lower the global
value. Use **Edit this QR field** to clear/change that override or enlarge W/H,
then save the reviewed template. Characters and pixels are different units: with
uppercase/digit payloads and zero padding, 500 characters require at least
219 × 219 pixels; a 128 × 122 box supports at most 122 characters under the
current three-pixels-per-module rule. Other character sets and padding change capacity.
The app does not silently shorten payloads or expand over neighboring fields.

Failed jobs keep their original template/config snapshot. **Fix QR settings** opens
their configuration for a corrected new job. Editing a template cannot repair an
old snapshot through Resume; incompatible QR resumes are rejected before queueing.

**Fonts:** Generation automatically preserves native PDF font hints, or compares
scanned source glyphs against installed font families and weights. It matches
source text color, keeps bold faces, and fits the actual glyph bounds rather
than incorrectly capping point size by the rectangle height. With no OCR text,
segmented letter shapes provide an estimate. For image sources, expand
**Font and appearance**, enter the
visible source text (or leave it empty to try configured local OCR), then click
**Match source font**. The app compares glyph shapes against installed fonts and
applies family, size and color; its similarity score is not a confidence guarantee.
Use **Font weight → Bold/Regular**, family/size controls and **Text color mode**
to correct a match. Images with textured
backgrounds or unavailable fonts can only be approximated. Replacement text is
shrunk only when its rendered glyphs exceed the region. Font matching stays local.

**Text background:** The default **Restore entire selected region** removes all selected
source pixels with local inpainting and draws new glyphs on a transparent layer.
**Remove detected ink only** is an optional texture-preserving mode that may leave
faint text; inspect carefully. Include complete source strokes inside the box.
It preserves surrounding color/texture instead of inserting a flat blue rectangle.
For a plain form, **Solid background color** lets you explicitly choose white or
another color. Inpainting estimates hidden pixels; textured regions and faint
source lettering still need visual review.

**Portrait recipe:** Draw a rectangle around the existing photo or placeholder,
select **portrait**, and choose **Replace with generated content**. The default
**Offline fictional illustration** draws seeded faces; these are not photographs.
For photographic output, use **Approved photo / image pool**, confirm permission,
and upload images you can use in the dataset (including externally generated
fictional faces). Add up to 20 images. Each sample selects from the pool using its
seed and crops the image to fill the rectangle. Upload limits are 8 MB, 8 MP and
one frame; images are normalized and metadata stripped. Source/permission notes
and hashes are recorded in annotations. Portrait masks cover the full photo
rectangle, not the person's silhouette. A small pool can repeat photos.
Portraits have no visible illustration caption. Synthetic provenance is retained
in dataset metadata rather than added to generated values or portrait pixels.

**Optional online import:** The LLM does not browse or scrape. To enable the
separate download button, an operator must set these in `.env` and restart the API:

```dotenv
DATAFORGE_ALLOW_ONLINE_PORTRAITS=true
DATAFORGE_PORTRAIT_PROVIDER_URL=https://your-approved-provider.example/portrait.png
```

Replace the example with an image URL whose usage terms permit your dataset.
There is no bundled provider. The endpoint must use public HTTPS, return PNG,
JPEG or WebP directly, and require no credentials, query string or redirects.
In **Optional online portrait import**, approve the download and usage rights,
then click **Fetch from configured provider**. Only that configured URL is fetched;
the template, OCR and rule prompt stay local. Downloaded images enter the local
pool; a provider may return the same image repeatedly. Downloads are off by default.

**Erase-only recipe:** Select/draw the area, choose **Erase only — no replacement**
or apply `remove this completely`, verify the region and save the review. The
renderer restores the region with local inpainting, or uses your explicit solid
background color. Hidden textures cannot be recovered exactly. Erased regions receive no YOLO/COCO object or OCR field.
Export metadata lists erased rectangles in original source-page coordinates;
augmentation information is stored separately. An erase-only dataset with no
variation can trigger duplicate rejection; start with one sample or add augmentations.

**Asset placement:** Asset switches draw only inside matching reviewed regions;
they do not place objects automatically. Disabling an asset still erases a region
selected for replacement. In **Rendering style and cleanup**, signatures can use a
**Mixed signature styles per sample** (the new default), or a specific full name,
first name, one letter, two letters, dotted initials, letter–wave–letter form,
overlapping monogram, or name with a connected finish. Plain lettering styles have
no mandatory underline or decoration. Finishing curves begin/end on actual letter
ink; they are not independent scribbles. Mixed mode varies script fonts when more
than one is installed, uses the dataset seed, and includes undecorated samples.
Existing fields that explicitly saved the old name/flourish style keep that selection;
choose Mixed to obtain all families. Signature annotation text records the actual
visible letters rather than always storing the full generated name. Seals support
15 shapes, six ink families, top/body/bottom text, configurable borders and ink wear.
Seal wording defaults to **Random per sample**. Choose **Static** for a fixed
heading and multiline body, or **Custom** for generated placeholders. Enable
**Allow repeated words** only when matching arc text or repeated phrases are
intentional. Use **Preview seal variation** to inspect both the pixels and the
actual generated wording. See the [seal format catalog](docs/seals.md) for examples.
Original seals are removed first using the selected full-region cleanup.
For the supplied attestation and corporate references, choose **attestation**,
**corporate**, **form block**, or **nameplate** in **Seal shape**. Form rows use
`Label: value`; an empty value leaves a blank dotted line. Attestation can include
a generated signature and cursive field values. Corporate supports inner arcs
and center motifs. See the [reference layout catalog](docs/seals.md#seal6-and-seal8-reference-layouts)
for the comparison gallery command and configuration examples.
For both signatures and seals, **Ink opacity → Random per sample** is enabled
by default (45–100%). Change the minimum/maximum sliders for a different range,
or select **Fixed opacity** to keep all impressions at a chosen strength.
This varies ink transparency independently of the existing random thickness.
**Ink finish → Natural imperfections** is now the default for both asset types.
Use the **Imperfection strength** slider for subtle or stronger flaws, **Worn /
dry ink** for more damage, or **Clean** to disable the new finish. Signatures
vary pressure, line smoothness and dry gaps; seals vary contact, pores and edge
wear. See the [ink finish guide](docs/ink-finish.md) and its comparison command.
Save and review the region, then generate a **new** dataset to see changes;
existing output images are retained. Generation studio signature previews use
the first signature region's saved finish and opacity settings.
Signature styles also include **broad enclosing return** and **overlapping
capitals and compact letters**, adapted from the supplied sign7 sheet. See the
[signature reference tests](docs/signature-research.md#sign7-regression-cases)
for the 15-case gallery command and geometry checks.
Choose **English cursive font** for synthetic handwriting; installed script fonts are
used without tracing a writer. QR and barcode light backgrounds are transparent by
default; white remains optional. Code masks cover the full logical rectangle. Dark
or textured templates can make transparent codes unreadable.

Do not delete a sensitive box merely to bypass its review. Source content outside
selected replacement regions remains in the result. To correct generated boxes,
edit source regions and create another job; sample-level annotation editing is
not implemented.

## 04 · Classify text

**Page:** Text datasets → **Dataset task: Text classification**.

1. Choose an engine, dataset name, sample count and languages.
2. For a first offline run, keep the labels `positive, negative, neutral`, choose
   **Procedural**, set **30** samples and seed **42**.
3. For Qwen, set a **Topic / domain**, optionally add **Content instructions**,
   and start with a small count such as **10** and batch size **1–2**.
4. Click **Generate text dataset**. Review the generated text and assigned labels.

**Custom procedural categories:** Set labels to `billing, delivery`, then expand
**Custom procedural class templates** and paste:

```json
{
  "billing": {
    "en": "I have a question about a charge on my fictional invoice."
  },
  "delivery": {
    "en": "Please check the delivery of my fictional parcel."
  }
}
```

Select **English** for that example. Provide a template for every custom label
and selected language. Optional `{record}` inside a template inserts a fictional
reference. Classification targets are assigned before generation; membership
checks do not prove the generated text agrees with its label.

**Output:** `text`, `label`, language, seed, provenance and validation.

## 05 · Generate NER data

**Page:** Text datasets → **Named entity recognition**.

1. Choose **Procedural** for a deterministic baseline or **Local Qwen** for
   model-written contexts.
2. Set a small sample count, seed and languages. No source document is needed.
3. Generate. Review highlighted entities and expand **Full record, labels &
   validation** to see spans and BIO tokens.

**Supported entities:** `PERSON`, `ORG`, `LOCATION`.

**Output:** `text`, `entities` (`label`, `text`, `start`, `end`) and `tokens`
with offsets and BIO tags. Offsets count Unicode code points, with an exclusive
end: `text[start:end]` in Python returns the entity. They are not UTF-16 or byte
offsets. BIO tokens use the application's regex tokenizer, not a model-specific
WordPiece tokenizer.

Values are inserted before final offsets are computed. Those offsets describe
the inserted entities exactly; they do not certify exhaustive recognition of
other entities the model might mention. See the [actual NER examples](samples/text/ner.jsonl).

## 06 · Generate QA pairs

**Page:** Text datasets → **Q&A pairs**.

1. Choose an engine, count and languages.
2. Leave **Q&A answer bank JSON** as `{}` for fictional score examples.
3. To create a different kind of answer, supply an answer bank and describe its
   type. For example, select English and Hindi, use the answer description
   `fictional service tier`, and paste:

```json
{
  "en": ["Fictional Gold Plan", "Fictional Silver Plan"],
  "hi": ["काल्पनिक गोल्ड योजना", "काल्पनिक सिल्वर योजना"]
}
```

4. In Qwen mode, set a topic such as `fictional customer support plans`.
   Generate, then review whether each question matches the context and answer.

The backend inserts the chosen answer into a context marker and calculates
`answer_start`. Custom-bank procedural Q&A uses a generic record-and-question
template. These are **extractive** pairs; open-domain factual correctness is not
automatically verified.

**Output:** `context`, `question`, `answer`, `answer_start`, plus metadata.

## 07 · Generate instruction–response data

**Page:** Text datasets → **Instruction–response**.

1. For the offline baseline, choose Procedural. It creates fictional reference
   code-copy instructions with known responses.
2. For varied content, choose Local Qwen, enter a topic and instructions such as:

   > Create short fictional customer-support tasks. Each instruction should ask
   > for a concise response. Avoid personal information and real credentials.

3. Set count, languages and batch size; generate and inspect both sides of each pair.

**Output:** `instruction`, `response`, language and metadata. Structural checks
ensure required fields exist; they do not grade response correctness.

## 08 · Generate conversations

**Page:** Text datasets → **Conversations**.

1. Choose Procedural for scripted exchanges or Local Qwen for topic-specific chats.
2. In Qwen mode, an example content instruction is:

   > Create a four-message conversation about a fictional delivery question.
   > Alternate user and assistant, and end with the assistant.

3. Generate and review each message, role and language.

**Output:** `messages`, each containing `role` and `content`. Accepted conversations
start with `user`, alternate `user`/`assistant`, and end with `assistant`.
The schema permits 2–12 messages; the current Qwen prompt requests a shorter
2–6-message exchange. This is a dataset generator, not a live chatbot session.

## 09 · Augment existing text

**Page:** Text datasets → **Text augmentation**.

1. Select the languages of your source texts.
2. Paste valid JSON into **Source texts JSON**. For English and Hindi:

```json
[
  {
    "text": "The helpful team resolved my fictional service request quickly and carefully.",
    "language": "en",
    "label": "positive"
  },
  {
    "text": "सहायक टीम ने मेरे काल्पनिक अनुरोध को जल्दी और सावधानी से पूरा किया।",
    "language": "hi",
    "label": "positive"
  }
]
```

3. Choose an engine:

   | Engine / operation | Variation |
   |---|---|
   | Procedural → whitespace | Varies spaces between words |
   | Procedural → punctuation | Changes terminal punctuation |
   | Procedural → typos | Swaps eligible adjacent Latin letters |
   | Local Qwen | Paraphrases in the source language |

4. Start with **10** samples. Generate and compare meaning against your source.

Supply at least one source for **every** selected language. Augmentation does
not translate. Source labels are optional; when supplied, they are copied into
the generated record and need review. Noise or paraphrasing can change meaning.
Unchanged/duplicate candidates are retried and then rejected. A short source may
not have enough unique procedural variants for a large requested count.

**Output:** generated `text`, inherited `label`, `source_id`, source hash,
augmentation method and provenance.

## 10 · Use multiple languages

Text datasets supports these selections:

| Language | Code |
|---|---|
| English | `en` |
| Spanish | `es` |
| French | `fr` |
| German | `de` |
| Hindi | `hi` |

Select more than one checkbox to distribute records among the selected
languages. Classification cycles across label/language combinations. For
example, 30 records with three labels and English/Hindi gives five examples
per label/language combination when all candidates pass.

For custom class templates, Q&A answer banks or augmentation sources, provide
the corresponding language entries as described above. The language code is
validated; automatic language identification and translation quality scoring
are not implemented. Inspect the actual generated text.

## 11 · Monitor and recover jobs

| Action | Documents | Text |
|---|---|---|
| Watch progress | Job monitor | Text datasets → Text generation jobs |
| Inspect outputs | Dataset gallery | Generated text & automatic labels |
| Stop work | Cancel | Cancel job |
| Continue saved work | Resume | Resume job |
| Try changed settings | Configure a new document job | Reuse configuration, edit, then Generate |
| Review quality | Quality dashboard | Validation report / per-record details |

**Status meanings:**

| Status | Meaning / next action |
|---|---|
| Queued | Waiting for the shared CPU worker |
| Running | Processing the current sample or batch |
| Cancelling | Finishing or reaching a safe cancellation boundary |
| Cancelled | Stopped; Resume can continue uncommitted work |
| Paused | Interrupted or below a memory threshold; resolve the cause, then Resume |
| Failed | Read the error, resolve configuration/service issues, then Resume |
| Completed | All requested items were processed without recorded rejections |
| Review required | Processing finished with rejected items; review reasons before exporting accepted items |

Document and text work share one CPU worker and an eight-active-job queue.
Processed count includes rejected items; exported count includes only accepted
items. Resume preserves committed records. To correct rejected completed output,
adjust inputs and generate a new dataset/job.

## 12 · Review and export

### Document export

Open **Export & history**, select the document dataset, inspect its quality and
samples, choose a format, confirm the review, then click **Build & download ZIP**.

| Format | Main use |
|---|---|
| YOLO | Normalized object-detection bounding boxes |
| COCO | Bounding boxes and segmentation RLE |
| OCR JSON | Generated text transcriptions and document fields |

The ZIP also includes images, masks, classes, configuration/version information
and per-sample metadata. The demo is unsplit: create disjoint train/validation/test
splits before training. Previous ZIPs are listed in Export history.

### Text export

Inside **Text datasets**, select a finished text job. Use **Revalidate records**
when needed; inspect generated text and its quality report. Choose a format,
check the review acknowledgment, then click **Download text dataset**.
Also download **configuration & quality manifest**.

| Format | Structure / handling |
|---|---|
| JSONL | One complete record per line; useful for streaming |
| JSON | One array of records |
| CSV | Fixed columns; text and nested content cells are JSON-encoded |

For CSV, decode the columns listed in the manifest's
`csv_json_encoded_columns` with `json.loads` after reading CSV. This preserves
exact Unicode/offsets and prevents content cells from starting as spreadsheet
formulas. A working reader is in the [sample catalog](samples/text/README.md).

Only accepted items are exported. Text file edits/corruption can block export;
revalidation identifies affected records. Fix generation inputs and create a
new job instead of editing saved JSON files in `data/`.

Passing checks does **not** establish privacy, semantic correctness, language
quality, lack of bias or training usefulness. Human review remains required;
reports intentionally retain `training_ready=false`.

## 13 · Controls reference

| Control | Applies to | Meaning / range |
|---|---|---|
| Dataset name | Both workflows | Human-readable name; each job has its own version ID |
| Sample count | Both | 1–2,000 per job, subject to configured server cap |
| Random seed | Both | Reproducible procedural choices; fresh LLM results can vary by runtime |
| Languages | Text | One or more of the five supported languages |
| Classification labels | Classification | 2–20 unique labels |
| Topic / domain | Qwen text | Context for model generation |
| Content instructions | Qwen text | Up to 2,000 characters; not supported by procedural mode |
| Batch size | Text | 1–8; use smaller batches for CPU models/long text |
| Validation retries | Text | 0–3 retries after the initial candidate |
| Rule prompt | Documents | Common shorthand or local Qwen interpretation; review plan before verification |
| Action | Documents | Replace, erase only (no object label), or keep original |
| Date format / range | Documents | Five formats; inclusive bounds within 1900–2100 |
| Character pattern | Documents | Legacy A/9/X/- or literal text with bounded template tokens; no automatic prefix |
| Generated character length / set | Documents | 1–128 for text/identifier/barcode; 1–500 for QR; no pattern required |
| QR padding / payload / required | Documents | 0–8 modules, 1–500 payload characters, optional required-region check |
| Font and appearance | Documents | Automatic source matching, family, bold/regular, pixel size, color and background cleanup |
| Portrait source | Documents | Offline illustration or approved image pool (up to 20) |
| Blur / rotation / noise | Documents | Appearance variation; geometric transforms also update masks |

Server settings live in `.env`; copy `.env.example` if needed and restart the
backend after changes. The most relevant settings are:

| Setting | Default / role |
|---|---|
| `DATAFORGE_DATA_DIR` | `./data`; local runtime storage |
| `DATAFORGE_DATABASE_URL` | Local SQLite; optional local PostgreSQL configuration |
| `DATAFORGE_MIN_AVAILABLE_MB` | `1500`; base free-RAM admission threshold |
| `DATAFORGE_LLM_MIN_AVAILABLE_MB` | `4000`; LLM allowance, adjusted for reusable resident model memory |
| `DATAFORGE_OLLAMA_URL` | `http://127.0.0.1:11434`; loopback only |
| `DATAFORGE_OLLAMA_MODEL` | `qwen3:1.7b`; locally provisioned GGUF |
| `DATAFORGE_LLM_TIMEOUT_SECONDS` | `180`; per inference request |
| `DATAFORGE_TEXT_MAX_SAMPLES` | `2000`; can impose a lower text-job limit |
| `DATAFORGE_ALLOW_ONLINE_PORTRAITS` | `false`; opt-in provider downloads |
| `DATAFORGE_PORTRAIT_PROVIDER_URL` | Empty; operator-approved direct public HTTPS image URL |

A seed alone is not a portable byte-for-byte guarantee: source files, fonts,
library versions and runtime matter. API-process RSS does not include the
separate Ollama process or all transient allocations.

## 14 · Troubleshooting

| Problem | What to do |
|---|---|
| App cannot connect | Confirm both frontend and API are running; open ports 5173/8000 above |
| Text datasets page or new API route missing | Restart the backend after the update, then refresh the app |
| Port already in use | Use the existing instance, or stop your earlier launcher before restarting |
| Local Qwen unavailable | Confirm Ollama is running and the configured local model is installed; DataForge does not auto-pull it |
| Low-memory pause | Close unnecessary workloads and Resume; use small text batches |
| Queue full | Wait for work to finish or cancel queued jobs |
| Input exceeds context budget | Shorten instructions/source text or reduce batch size |
| Custom classes rejected | Supply templates for every custom label and selected language, or use Qwen |
| Missing augmentation language | Add a source with that language code, or deselect the language |
| Invalid JSON | Use double quotes, matching brackets and no trailing commas; copy the examples above |
| Many duplicate augmentations | Add longer/more varied sources, request fewer samples, or use local Qwen |
| OCR unavailable | Install/configure a local engine, upload a native-text PDF, or draw regions manually |
| Document generation blocked by review | Resolve prompts, confirm sensitive replacement/erase regions, and save the full-page review |
| Unsupported rule / mismatched model plan | Shorten the prompt, select its field type and retry, or use explicit action/format controls |
| Photo field gives a drawing | Select the approved image pool and upload photographic images; offline portraits are illustrations |
| Online photo import unavailable | Configure an approved provider and restart the API, or upload portraits |
| Replacement text does not fit | Enlarge the region or use a shorter fictional literal value |
| QR unreadable | Enlarge the QR region and reduce blur, noise or rotation |
| Text record integrity changed | Revalidate; affected items are excluded. Regenerate corrected output rather than changing files |
| Export disabled | Wait for a finished job with accepted items, then complete the export review acknowledgment |

## 15 · Samples and further reading

| File / folder | Contents |
|---|---|
| [Fictional certificate](samples/fictional_certificate.pdf) | Safe source template for the document workflow |
| [100-image YOLO ZIP](samples/fictional_100_yolo.zip) | Verified fictional document demonstration |
| [Generated document preview](samples/generated_preview.png) | Example rendered result |
| [Text sample catalog](samples/text/README.md) | Six tasks, five languages, CSV/JSON/JSONL and manifests |
| [Local Qwen examples](samples/text/local_qwen_examples.jsonl) | Actual local-model outputs from verification runs |
| [Text feature audit](docs/text-datasets.md) | Detailed behavior, API endpoints and validation limits |
| [API reference](docs/api.md) | Document endpoint contracts and text API links |
| [Architecture](docs/architecture.md) | Components, data flow, schema and roadmap |
| [Model compatibility](docs/models-and-compatibility.md) | Engine setup, resources and upstream licensing sources |

Storage is local by default under `data/`. Keep the app bound to loopback; this
proof of concept does not provide network-facing authentication. Uploaded real
documents and pasted source texts remain sensitive even when generated outputs
are fictional. No automatic model downloads or cloud-inference fallback occur.

## Automatic visual boxes and rubber stamps

Uploads now propose QR, barcode and face-based photo boxes alongside OCR text.
Use **Find visual regions** to scan an older template. Select a proposed box to
change its label/type, resize it or use **Delete region**. Photo bounds are estimates
and photos without a detected face need manual boxes. Save after reviewing.

To add a stamp, draw a box, choose **seal / stamp**, then open **Rendering style
and cleanup → Rubber stamp preset**. Received, Paid, Approved, Rejected, Copy and
Confidential presets support random opacity and natural ink flaws. Edit wording
or use random/custom formats. See [visual box and stamp guide](docs/visual-regions.md).
