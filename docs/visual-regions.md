# Visual boxes and synthetic stamps

On document upload, DataForge proposes **QR**, **barcode** and **portrait / photo**
regions in addition to OCR text. All boxes use the normalized page's pixel
coordinates, including rendered PDFs and EXIF-rotated images. They are unconfirmed
draft regions, with editable labels, types and coordinates. Nothing is erased from
the source image. Select a box and use **Delete region** if it is wrong.

For existing templates, use **Find visual regions** above the editor. This adds
new draft boxes and preserves your edits. It skips duplicate/overlapping regions;
only unchanged upload OCR boxes mostly contained by an accepted visual box are
removed to avoid duplicate text inside a code or photo. Save the draft/review as
usual. A rescan can propose a previously deleted box again.

The local detectors are independent of PaddleOCR and Qwen:

- QR: OpenCV geometry detection; payloads are not decoded or retained.
- Barcode: directional gradients and aligned stripe geometry, horizontal and
  vertical. This is a proposal heuristic, not symbology recognition or decode.
- Photo: bundled MIT-licensed OpenCV YuNet face model, then the smallest plausible
  enclosing rectangle or estimated head/shoulder bounds. Non-face images, very
  small faces, rotated faces and unframed photos can be missed or have wrong bounds.

Detection scores are heuristic. Inspect the full page for missed content. Automatic
type suggestions can be changed later. Uploads and generation never download model
weights or send images to a service. The bundled model's license, source commit and
hash are in `backend/assets/yunet/`. Missing/failing photo detection produces a
notice and preserves code proposals. A detector failure or busy CPU during upload
does not reject the upload: retry from the editor. Analysis is bounded to a 1800px
long side, 40 visual boxes and 200 combined regions. The demo certificate retains
its explicitly authored fixture regions.

## API

`POST /api/templates/{id}/detect-visual-regions` has no required body. It returns
`{candidates: Region[], engine: "opencv-local", warnings: string[]}`. Regions use
`origin: "visual"`, a stable ID based on kind/box, empty text, and
`confirmed: false`. This endpoint is read-only: it does not save a template,
change its revision, or erase pixels. Unknown/deleted template: 404; CPU busy: 409.
`GET /api/document-analysis/capabilities` describes the visual detectors.

## Rubber stamps

Draw a new box or select an existing one, set **Field type → Rubber stamp**, and
open **Rendering style and cleanup**. **Rubber stamp preset** offers Received,
Paid, Approved, Rejected, Copy and Confidential. Presets set static wording and a
double rectangular border. They preserve your ink color, random opacity and ink
imperfection settings. Edit wording or choose random/custom wording for variations.
Use a larger region for longer text. Preview with **Preview seal variation**.

Rubber stamp ink has a transparent background and its own `rubber_stamp` class.
Printed postage/revenue stamps are the separate **Postage / revenue stamp** field,
with opaque paper, perforations and artwork. They use the `stamp` class. These
classes are appended after the original class IDs. New datasets use the saved
region settings; old datasets retain their originals. See [stamps.md](stamps.md).
