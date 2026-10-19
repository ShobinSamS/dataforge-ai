# Compatibility and license review

Reviewed 2026-10-18. Source links document upstream capabilities and licenses;
they do not establish performance on the target laptop. No model weights are
bundled, downloaded on startup, or sent uploaded content. Installation may need
Internet access; runtime can remain offline after packages/models are provisioned.

| Component | Decision | Evidence / license | Verification here |
|---|---|---|---|
| Python / FastAPI / SQLAlchemy | Python 3.11+ source, tested on 3.12; local API, SQLite or psycopg/PostgreSQL | Python packages pinned in requirements.lock.txt | Core integration suite on Windows + SQLite |
| PostgreSQL | Optional local Compose service; same SQLAlchemy models | PostgreSQL license; official postgres:17 image | SQLAlchemy model compatibility by design; server not exercised here |
| PaddleOCR 3.x | Primary optional printed OCR; local det/rec directories, CPU, no orientation models | [Official CPU install](https://paddlepaddle.github.io/PaddleOCR/v3.0.0/en/quick_start.html), [Apache-2.0](https://github.com/PaddlePaddle/PaddleOCR) | Adapter implemented; weights not installed/tested |
| Tesseract | Optional printed fallback, subprocess timeout | [Official Apache-2.0 license](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE) | Executable not installed here; failure/manual path tested |
| PDFium / pypdfium2 | Native PDF text + canonical raster | [pypdfium2 license explanation](https://github.com/pypdfium2-team/pypdfium2#licensing) | Real fixture decoding and coordinates exercised |
| Qwen3-1.7B GGUF | Optional loopback Ollama text generation, bounded structured batches, CPU, no cloud fallback | [Official GGUF, Apache-2.0](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF), [Ollama tag](https://ollama.com/library/qwen3%3A1.7b) | Real local Q4_K_M inference exercised for text tasks; no general accuracy or latency guarantee |
| TrOCR-Small printed / handwritten | Optional local CPU recognition of English line/cell crops, not page layout or signatures | [Microsoft handwritten model card](https://huggingface.co/microsoft/trocr-small-handwritten), [printed model](https://huggingface.co/microsoft/trocr-small-printed) | Both installed and exercised on synthetic font lines; handwritten punctuation error observed. No Indian handwriting benchmark; see document-analysis.md |
| Presidio | Planned in addition to regex; local NLP model must also be provisioned | [Official analyzer docs](https://microsoft.github.io/presidio/analyzer/) | Not integrated; regex is not equivalent semantic coverage |
| SD 1.5 / LCM / OpenVINO | Disabled; isolated CPU process benchmark before integration | [OpenVINO model card](https://huggingface.co/OpenVINO/stable-diffusion-v1-5-fp16-ov): CreativeML Open RAIL-M, OpenVINO >=2025.0 and Optimum Intel >=1.22. [LCM-LoRA paper](https://arxiv.org/abs/2311.05556) | No hardware latency, RAM or quality claim; no diffusion backend shipped |
| LangGraph / MCP / FAISS | Documented phase-3 design | Recheck exact pinned dependencies and their transitive licenses during that phase | Not integrated |

The base workflow does not need PyTorch, PaddlePaddle, an LLM server, Redis or
diffusion. Installing all AI dependencies into one environment is deliberately
avoided. Paddle and optional generative environments need independent locked
dependencies and measured working sets before sharing memory with generation.

Faker names are invented samples, but may coincide with real names. Addresses
use a deliberately fictional locality, emails use example.invalid, identifiers
have configurable random formats without an automatic prefix, and phone values use
the reserved 202-555-01xx fictional range. Signatures combine synthetic letters and
optional flourishes; configurable seals use varied fictional wording by default,
with explicit static and custom formats available. Provenance remains
in metadata. No credential validity is implied.

Model/service admission plan: inspect available RAM, acquire the single resource
slot, load only one heavy model, execute a bounded task, release the model/process,
then hand the slot back. Python garbage collection does not guarantee native
allocator memory is returned; future inference isolation should use subprocesses.
Measure both process RSS and total system available memory. Never infer CPU
performance from upstream GPU benchmarks.

Third-party dependencies retain their licenses. The lockfiles are reproducibility
records, not a complete SBOM; release packaging should generate an SBOM and retain
all applicable library, model and PDFium notices. No proprietary assets or
real-world personal documents are included in the fixture.


## PII model choice (2026-10-18)

The currently installed and enabled model remains `qwen3:1.7b`. Real document
trials showed false positives on headings and advertising copy; TrOCR also
misread characters before Qwen received the text. Qwen's general reasoning is
useful for proposing contextual labels/rules, but it is not a validated standalone
PII detector. Literal-source evidence, category checks and human review remain
part of the implemented path.

For the next comparison, evaluate a dedicated span extractor such as
[GLiNER2-PII](https://arxiv.org/abs/2605.09973), then optionally
[Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
in a CPU quantization for contextual disambiguation. GLiNER2-PII is specialized
for PII spans; its authors also report over-prediction of names and limited
benchmark domains. Qwen's published general benchmarks do not establish PII
accuracy on these documents. Neither candidate was downloaded, benchmarked or
enabled by the template-delete change, and the current adapter still restricts
inference to the configured 1.7B model.

Use corrected OCR text and a representative held-out set of English/Indian
forms, public headings, empty Name labels, names, contact details and document
IDs. Measure value-span precision/recall and false positives separately from OCR
transcription errors. A larger text model cannot read the pixels that OCR got
wrong. Compare CPU latency and memory with the app/OCR loaded before adopting
another model; avoid selecting based on parameter count alone.
