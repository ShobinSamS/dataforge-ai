# Local Stable Diffusion assets

Open **Template library → Generate images** or **AI image studio** for offline SD-Turbo runs. The same controls appear
under **Optional AI image generation** in photo, signature and paper stamp
regions. A seal field offers **Optional AI emblem · decoration only**; complete
text seals are configured under **Seal design and ink**. These controls retain
the existing procedural engine.

## Setup

Provision CPU PyTorch as described in [model setup](models-and-compatibility.md), then:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-vision.txt -r requirements-diffusion.txt
.\.venv\Scripts\python.exe scripts/setup_diffusion_model.py
npm.cmd start -- --api-port 8002
```

The explicit setup downloads approximately 2.5 GB of fp16 safetensors from
[stabilityai/sd-turbo](https://huggingface.co/stabilityai/sd-turbo). Large weights
use resumable 16 MB ranges and are checked against the upstream SHA256. The
local manifest records the immutable repository revision and file hashes. Models,
generated previews and saved assets live in ignored `data/`; they are not Git assets.
Review the model's license for your intended use. Installing packages or weights
never happens from an API call or an ordinary document-generation request.

## Generate, inspect, reuse

1. Select **Fictional person**, **Seal center artwork**, or **Stamp illustration**.
2. Choose **Qwen variation per image** (UI default) to give a brief, or
   **Exact/manual prompt** to use fixed text. The Qwen mode starts with a broad
   brief rather than the old fixed South Asian woman description. It writes a
   short, distinct description for each image, using seeded diversity hints and
   avoiding repeated prompts within a batch. Explicit constraints in your brief
   take precedence over suggested variations. Inspect model output; semantic
   constraint-following and visual diversity are not guaranteed.
   **Preview sample Qwen prompt** shows an illustrative description without
   generating an image; normal runs generate fresh prompts. Use the renderer's separate controls for exact
   company names, denomination, identifiers and borders.
3. Choose the **Number of images** (UI default 10), with 1/10/50/100 presets or
   a custom integer from 1 to 100. Choose a starting seed and 1–4 diffusion steps
   (default 2). Resolution is fixed at 512×512. Image index `i` uses
   `(starting_seed + i) % 2**31`, so each image gets a distinct seed.
   Qwen variation mode also chooses a fresh prompt variation seed per run, so
   repeating image seed 42 does not pin all runs to the same descriptions. Both
   image and prompt seeds are recorded. API clients can supply `prompt_seed` to
   fix prompt planning; exact reproduction still depends on model/library versions.
4. Generate the run. Status progresses through queued, running and completed,
   failed or cancelled. CPU generation may take minutes; cancel stops only the
   owned model process. The gallery retains previous previews across app restarts.
5. Inspect results as they finish. The run shows completed/total images, a progress
   bar and an estimate after the first image. Download individual PNGs or a ZIP
   containing all completed PNGs and per-image metadata. **Save all completed
   images** saves the batch at once. In a region, **Use completed images in this
   region** selects the whole completed pool; individual selection still works.
   Cancelling or a failure preserves completed images. **Resume remaining images**
   retries only unfinished indexes, including after restarting DataForge. Keep
   the local server/computer running for uninterrupted long batches; navigation
   away from the page does not cancel a run. Interrupted batches are not silently
   restarted at app startup.
6. Saved portraits/stamp illustrations populate the image pool. A dataset selects
   pool entries using its seed; it does not run diffusion once per sample.
   Portrait, stamp and seal artwork pools support up to 100 saved images. Uploaded
   photos/ZIPs retain a limit of 20 images per upload, with up to 100 in a region's
   pool. Saved seal artwork sets the center emblem/pool and selects a corporate circular
   layout. Circular and oval seals support center artwork; block seals do not.

The portrait/stamp background may be kept, approximately removed, or replaced
with a solid color. Background removal uses the existing local cutout method,
not a learned segmentation model, and needs inspection around hair and details.
Seal previews convert dark artwork on white into transparent monochrome ink;
the final renderer recolors that ink, places exact wording and applies wear.
Stamp illustrations are converted to engraved print, with existing print color,
paper, perforations and cancellation controls.

## Runtime and dataset labels

Each preview runs in a separate Python process using CPU float32 (loading fp16
weights), four PyTorch threads, attention slicing and VAE tiling. It shares
`CPU_LOCK` with OCR, Qwen and document rendering. At most three previews can be
pending. Each run may request up to 100 images; they are generated sequentially,
releasing model memory and the CPU lock between images. A job checks for at least 4.5 GB available memory before loading; this
is a guard, not a guarantee against memory pressure. Ten minutes is the hard
worker timeout. Exiting/cancelling releases the model process. No GPU acceleration
or latency guarantee is claimed. The UI reports measured inference/model-load
time and peak sampled worker RSS, excluding queue time and parent-app memory.
The displayed generation time includes subprocess startup/imports; the metrics
also retain model-load/inference time separately.
Memory monitoring and cancellation include the Windows Python redirector's
descendant process; peak RSS is summed across the owned worker process tree.

Runtime model loading uses local files, safetensors and the built-in
StableDiffusionPipeline; no remote/custom model code is loaded. The application
does not supply cloud inference or runtime downloads. The upstream SD-Turbo
pipeline ships without an image safety classifier; this adapter does not claim
content moderation. Use fictional asset descriptions and inspect all results.

Qwen planning uses the existing local `qwen3:1.7b` Ollama model, CPU structured
JSON output and the same CPU lock. It requests model unload and checks that Qwen
is no longer resident before loading Stable Diffusion. If Qwen is unavailable,
planning fails visibly; no manual or procedural prompt is silently substituted.
Cancellation during planning finishes/cancels at the current bounded Qwen call,
before image inference starts. Completed descriptions are checkpointed and
reused on resume. Per-image metadata and saved asset provenance include the
brief, generated/resolved prompt, variation seed, Qwen model and model digest.

Generated artwork can include artifacts, distorted faces and unwanted marks or
letter-like shapes. Artwork is not transcription ground truth. Exact labels
come from separately rendered text. Existing masks/bounding boxes are computed
after compositing. A saved asset records prompt, resolved prompt, seed, steps,
model revision, source/license links and image hash. That provenance travels
with portrait, stamp and seal annotations into exports. Reproducibility is best
effort within the same library/hardware versions, not cross-platform bit identity.

## API / MCP

- `GET /api/diffusion/capabilities`
- `POST /api/diffusion/prompts/preview` uses local Qwen and creates no image/job
- `POST /api/diffusion/jobs` with `kind`, `prompt`, `seed`, `steps`, `count` (1–100,
  API default 1 for existing clients),
  `background` (`preserve`, `transparent`, `solid`) and `background_color`
  plus `prompt_mode` (`manual` API default, or `qwen`) and optional `prompt_seed`.
- `GET /api/diffusion/jobs` and `GET /api/diffusion/jobs/{id}`
- `POST /api/diffusion/jobs/{id}/cancel`
- `POST /api/diffusion/jobs/{id}/resume` for an interrupted batch
- `GET /api/diffusion/jobs/{id}/download` for a ZIP of completed images
- `GET /api/diffusion/jobs/{id}/image` (`?raw=true` for the original)
- `POST /api/diffusion/jobs/{id}/save` returns an idempotently saved asset for a
  single image, or `{assets, saved_count, count, completed}` for a batch. Optional
  `?index=N` saves just that zero-based batch index. Partial batches can be saved.

MCP tools: `image_generation_status`, `generate_image`, `list_image_generations`,
`get_image_generation`, `cancel_image_generation`, `resume_image_generation`, `save_generated_image`, `preview_image_prompt`.
Use a saved ID in `RuleOptions.portrait_asset_ids` with `portrait_source=asset_pool`
for portraits or any paper-stamp style, or `RuleOptions.seal_artwork_ids` for a
seal emblem pool (`seal_artwork_id` still supports a single selected emblem).

To generate and render three real samples through the running API:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_diffusion.py --api-url http://127.0.0.1:8002 --steps 1
```

Results, images and timings are written to ignored `artifacts/diffusion-benchmark`.

## Measured local trial · 2026-10-24

On this 16 GB Windows laptop (Intel UHD 620, inference on CPU), with one step,
512×512, seed 42, manual prompts and CPU float32 (excluding Qwen planning):

| Asset | Worker wall time, including imports/load | Peak owned worker-tree RSS |
|---|---:|---:|
| Fictional portrait | 60.23 s | 6276 MB |
| Seal emblem | 56.42 s | 6918 MB |
| Stamp illustration | 63.70 s | 6544 MB |

These are individual observed trials with other applications running, not
latency guarantees or quality benchmarks. All three were saved, rendered with
the document asset engine and visually inspected. The seal's wording and the
stamp's lettering/denomination came from the renderer. Tested libraries:
PyTorch 2.14.1+cpu, Diffusers 0.35.2 and Accelerate 1.12.0. The model revision was
`b261bac6fd2cf515557d5d0707481eafa0485ec2`.

Signature image generation is now available as `kind=signature_artwork` (experimental). It uses transparent monochrome artwork and never claims exact lettering. See [document realism and signature trials](document-lab.md#stable-diffusion-trials).


## Single signatures, text seals and recoloring

Signature generation now uses `StableDiffusionImg2ImgPipeline` with a seeded
procedural single-autograph guide and strength 0.5, rather than unconstrained
text-to-image. At least two scheduler steps are configured (one denoising step
at strength 0.5). Optional `signature_text` and `signature_style` control the
guide. The guide image, style, text and hash are recorded. The model may alter
lettering, so output transcription remains unverified.

Postprocessing searches the guide area, keeps one spatial ink group, centers
it on a transparent 512-square canvas and rejects dense or boundary-clipped
results. This is a geometric check, not proof that an overlapping group contains
one semantic autograph. Inspect the preview. Failed results are visible and no
procedural replacement is silently used. Old signature sheets remain historical
previews; generate a new run to use the guided path.

Select **Full text seal · exact lettering** for complete text-based seals like
the references. This uses the native seal renderer, never an image model. The
reference layouts offer circular office/company rings, professional nameplates
and attestation blocks. Random/static/custom wording, borders, symbols, ink
wear and black/custom/random/mixed colors use the existing seal controls. This
is distinct from **Seal emblem only · Stable Diffusion**, which supplies artwork
for the middle of a seal. No model installation is required for full text seals.
One complete seal is returned per transparent PNG, including in batches.

`DiffusionRequest.kind=text_seal` takes its wording/colors in `seal_options`.
API clients still supply a short `prompt` such as "Text seal"; it is only a
record label. Native seals ignore Qwen mode and use procedural content planning.
Their provenance records `rendering_engine=native-text-seal`; saved assets have
`source=local_text_seal`, rather than claiming Stable Diffusion inference.

For generated signature/emblem ink, request `ink` with `color_mode` equal to
`black` (default), `manual`, or `random`; use `text_color` as a hex code and
`color_palette` for seeded random choices. The same values can be applied later:

```json
{"color_mode":"manual","text_color":"#173574"}
```

POST this object to `/api/diffusion/jobs/{id}/recolor`. It creates a new completed
job for one image or all completed images of a stopped batch, preserving the
source job and saved assets. Alpha/shape stay identical; RGB changes to the
chosen color. A multi-color seal is flattened to the selected single ink color
when recolored. No model inference or new prompt is involved. The UI exposes
**Change ink color without regenerating** for these previews. The MCP tool
`recolor_generated_ink` uses the same contract; the catalog now has 64 tools.
Transparent colored artwork retains its original alpha when reused as a signature
or seal emblem in a document. Opaque scans still have their white background removed.


### Verified guided trial · 2026-10-25

A real two-image CPU run used the installed SD-Turbo revision, a surname-style
single-autograph guide, seeds 3030/3031, two scheduler steps and strength 0.5.
Both outputs passed geometric isolation and were visually inspected as one
signature each, with ink densities 0.0700 and 0.0774. This small trial does not
guarantee every seed or prompt. The resulting images were recolored from blue to
red; their alpha planes matched byte-for-byte, and no model was rerun. Circular,
professional and attestation text seals were also generated in two-image batches
and recolored. Older free text-to-image signature previews are labelled as older
generations in the gallery; new generation uses the guide automatically.

A subsequent three-image run used Qwen descriptions and seeds 4242–4244 with
mixed guides. All three completed, each with one isolated autograph on a
transparent PNG, and were visually inspected. All eight corporate seal presets
were checked through the live asset API in black and blue; their alpha planes
matched across colors. The four native signature content modes were also checked.

### Complete corporate seals and simpler controls

In a seal field, open **Seal design and ink** and choose a **Seal reference layout**. The same presets are available in AI image studio under **Company / office seal · complete design**: a crest, a dated circle, a quality seal, recipient/product/batch and date/status forms, a company nameplate, a professional nameplate and attestation. These create exact lettering and borders together on transparent PNGs. The optional AI emblem generator remains available for center decoration. Presets replace layout and wording settings while retaining color and opacity. Existing designs stay unchanged until a preset is chosen.

Normal content and appearance settings are shown first. Position, cleanup, custom patterns, handwriting designs, photo backgrounds, ink effects and natural-language rules are grouped in optional sections.

Qwen still retries a repeated description. If a valid description repeats again, the batch continues with its distinct image seed, records `prompt_reused` and `prompt_warning`, and shows that notice in the preview. Invalid or unavailable model responses still produce an error; there is no substituted prompt. Existing failed batches can use **Resume remaining images** after the backend restarts.
