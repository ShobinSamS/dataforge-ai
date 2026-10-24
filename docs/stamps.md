# Postage/revenue stamps, rubber stamps and seals

These are three separate field types with independent dataset toggles:

| Field | Appearance and controls | Annotation class |
|---|---|---|
| Seal | Existing office/corporate/attestation layouts | `seal`, existing ID 8 |
| Postage / revenue stamp | Printed paper, artwork, value, perforations and cancellations | `stamp`, ID 12 |
| Rubber stamp | Approved/Received/Paid marks, dates, postal circles and cancellation waves | `rubber_stamp`, ID 13 |

The new classes are appended after the original twelve, so all original class IDs
remain stable. Old saved templates, dataset snapshots and exported archives are
not migrated or relabeled. If an old seal region should now be a rubber stamp,
change its field type, choose the new controls and create a new dataset.

## Paper stamps from the supplied references

The references show portrait/architecture commemoratives and denominations
(`stamps1.jpg`, `stamp2.jpg`), revenue medallions with handwritten cancellations
(`stamp3.jpg`), mixed envelope/postage arrangements (`stamp4.jpg`) and circular
postal cancellations (`stamps5.jpg`). The renderer implements those composition
families with newly drawn artwork and fictional default issuers/people/places.
The supplied images are not cropped or copied into generated stamps. Original
scans, real portraits, official emblems and source lettering are not reproduced.

1. In the template editor, draw/select a region and choose **Postage / revenue stamp**.
2. Open **Rendering style and cleanup**. Select portrait, architecture, botanical,
   commemorative, revenue or random artwork. Choose a palette and optional issuer,
   caption and denomination; empty values vary by seed.
3. Configure perforations, paper age, cancellation (none/postmark/waves/pen/random),
   print opacity and ink finish. **Preview paper stamp** renders the actual options.
4. For portrait/revenue artwork, the approved portrait image pool below the controls
   can provide a photo converted to an engraving. Otherwise the artwork is drawn
   procedurally. Other artwork families do not use the pool.
5. Save the reviewed regions, enable **Postage / revenue stamps** in Generation
   studio and create a new dataset. Minimum region size is 64×64 pixels; long
   lettering may need a larger region. Text is fitted or rejected, never truncated.

The **paper is intentionally opaque** inside its cut/perforated silhouette.
Outside is transparent. Opacity fades the printed design, not the physical paper.
The stamp mask covers the paper silhouette, with perforation holes excluded.
An integrated cancellation is part of that stamp's pixels and mask. To label a
postmark separately, use a separate **Rubber stamp** region. The existing editor
requires replacement rectangles not to overlap; arbitrary layered overlapping
annotations are not introduced by this change.

These are procedural reference-inspired assets, not photorealistic stamp replicas.
No new model, internet scrape or image-generation service is used. Wax seals in
the envelope reference are not a new wax/material renderer.

## Rubber stamps and postal cancellations

Choose the separate **Rubber stamp (Approved / Received / postmark)** field.
Presets include Approved, Received, Paid, Rejected, Copy, Confidential, Cancelled
and Dispatched. Choose boxed, text-only, round, dated, postmark, waves or random
layout; wording can be random, static or a custom format. Postmark and waves
provide their own postal wording/lines instead of a status label.

Custom formats support `{organization}`, `{department}`, `{name}`, `{title}`,
`{city}`, `{state}`, `{year}`, `{date}`, `{reference}` and `{number}`. No code,
attribute access or expressions are executed. Ink color, natural/worn finish and
random/fixed opacity vary independently of the wording. There is no paper or
white rectangle behind these marks. Their mask follows the visible ink.

## REST and MCP

`POST /api/assets/generate` accepts `kind:"stamp"` or `kind:"rubber_stamp"` and
returns PNG, mask and metadata. It no longer interprets `stamp` as a seal alias.

```json
{"kind":"stamp","width":240,"height":320,"seed":73,"options":{"stamp_style":"revenue","stamp_palette":"red","stamp_denomination":"15 P","stamp_cancellation":"pen"}}
```

```json
{"kind":"rubber_stamp","width":400,"height":160,"seed":73,"value":"APPROVED","options":{"rubber_stamp_style":"boxed","rubber_stamp_color":"red"}}
```

MCP `generate_stamp` now generates a paper stamp (optional `caption`, options,
width, height, seed). `generate_rubber_stamp` generates the separate ink-only
mark (optional `text`, options, dimensions, seed). `generate_seal` remains the
existing seal tool. There are now 52 tools, including image-pool batch imports, blank canvases and addresses;
[MCP setup](mcp.md).

Relevant RuleOptions fields are `stamp_style`, `stamp_palette`, `stamp_issuer`,
`stamp_caption`, `stamp_denomination`, `stamp_perforated`, `stamp_age`,
`stamp_cancellation`, `rubber_stamp_style`, `rubber_stamp_mode`, `rubber_stamp_text`,
`rubber_stamp_format`, `rubber_stamp_color`, and shared `ink_*` controls.
GenerationConfig adds independent `stamps` and `rubber_stamps` booleans, both
default true. Existing `seals` controls only seals.

Generate comparison PNGs and metadata locally:

```powershell
.\.venv\Scripts\python.exe -m scripts.preview_stamps
```

Outputs: `artifacts/postage-stamps/paper-gallery.png`, `rubber-gallery.png`,
individual transparent PNGs, masks and metadata.
