# Seal wording and design catalog

Select a seal region and open **Rendering style and cleanup**. After editing,
verify the changed region and save the template review before creating a new
dataset. Previously generated images remain unchanged.

## Choose how wording varies

- **Random per sample** (default): choose fictional organization, department,
  person, role, location, date and reference combinations. A seed-specific
  reference makes the complete wording vary between samples. An individual word
  such as a common business term may occur in more than one sample; duplicate
  words within one seal are rejected by default. Equal numeric day/month parts
  in a date are allowed.
- **Static**: enter main text, up to six body lines, and optional bottom text.
  This wording stays the same across samples; design choices can still vary.
  Existing explicit literal rules also remain static. Jobs saved before the
  new wording controls retain static wording when resumed.
- **Custom**: place generated fields exactly where you want them using the
  top/body/bottom format controls. Fields resolve consistently within each seal
  and vary with the dataset seed and sample index. Supported placeholders are
  `{organization}`, `{department}`, `{name}`, `{title}`, `{city}`, `{state}`,
  `{year}`, `{date}`, `{reference}` and `{number}`. No expressions, attribute
  access, format specifiers or executable code are accepted.

An English professional-stamp example:

```text
Top format:    {organization}
Body format:  {name}
              {title}
              REG {reference}
Bottom format: {city} · {state}
```

A date-entry example (choose Form or Dated):

```text
Top format:    {organization}
Body format:  TO {name}
              DATE {date}
              BATCH {reference}
Bottom format: {city}
```

For intentional repeated arc wording, use `{organization}` in both the top and
bottom formats and enable **Allow repeated words**. Otherwise a duplicate-word
error explains which word needs changing. The repetition checkbox controls
words within a seal; Static mode controls repetition across dataset samples.

## Design choices

Shapes: ring, round, double ring, oval, badge, square, rectangle, professional,
form, dated, unframed text, attestation, corporate, form block and nameplate. Random shape selection respects the selected
region's aspect ratio. Borders include solid, double, dotted, dashed and toothed
(serrated) patterns, plus small circular rosettes. Ornaments include stars, diamonds, rosettes and monograms.
Ink may be red, blue, green, purple, black, brown or a mix, with seeded opacity,
weight and worn contact. Designs are rendered on transparent layers; no white
paper rectangle is pasted over the template. Full-region cleanup still removes
the original seal before replacement.

**Ink opacity** defaults to **Random per sample**, uniformly selecting 45–100%
opacity. Adjust its minimum and maximum, or select **Fixed opacity** and choose
5–100%. This changes the whole impression's alpha independently of layout,
wording, color, pen weight and local wear. The same seed and settings reproduce
the same result. Fading does not shrink binary annotation masks. `opacity` and
`opacity_mode` are included in preview metadata and each generated seal
annotation. Ink wear remains a separate control for uneven contact and holes.

Both arcs use measured glyph advances along the ellipse. Text is fitted in full
and never silently shortened; a format that cannot fit at the minimum font size
asks for a larger region or shorter wording. A 125×125 field can hold generated
compact examples, but long custom formats need more space. Preview uses the
current region size and shows its actual text. English lettering is the tested
scope; complex script shaping around arcs is not implemented.

## What the references contributed

| Reference | Adapted design characteristics |
| --- | --- |
| seal.jpeg | Paired arcs, double rings, stars and worn ink; repeated top/bottom text is optional |
| seal2.jpg | Compact professional heading, name, role and registration rows |
| seal3.jpg | Several text zones and uneven stamp contact |
| seal4.jpg | Outer arcs with an inner name/reference block and adjacent text-style stamps |
| seal5.png | Varied circular borders, colors, text densities and center blocks |
| seal6.webp | Multiline framed stamp, date/reference fields and uneven impressions |
| seal7.jpg | Toothed/dotted/dashed rings, center text and year/location placement |
| seal8.jpg | Paired corporate arcs, generic center motifs, double rectangular frames and form lines |

These are layout references. Default generated entities and ornaments are
fictional; the comparison cases below use the supplied English wording. The
code does not trace supplied emblems or signature pixels.

Run `python -m scripts.preview_seals` from the repository root for a catalogue
under `artifacts/seal-variations/`, including individual transparent PNGs and
their metadata. Exports record the exact drawn seal text, shape, border,
ornament, colors and content mode in each seal annotation (`engine: seal-v2`).

`POST /api/seals/preview` accepts `options` (RuleOptions), `seed`, `region_id`,
`width`, `height` and an optional explicit `literal`. It returns a transparent
PNG data URL and metadata without creating or changing a template or dataset.

## Seal6 and seal8 reference layouts

The supplied wording appears in eight generated comparison cases in
`tests/fixtures/seal-reference-cases.json`. Run
`python -m scripts.preview_seal_references` for the gallery, individual
transparent PNGs and full metadata under `artifacts/seal-reference-cases/`.
The original files are not copied into the repository. Golden mask comparisons
and separate checks cover readable text boxes, seeded output, inner arcs, field
values, embedded signature metadata and compositing without a paper rectangle.
Only deliberately reviewed changes should use `--update-baseline`.
Pixel matching requires the recorded font fingerprint; machines with different
installed fonts still run wording, bounds and transparency checks without
claiming an identical raster. No font files are bundled or downloaded.

In **Rendering style and cleanup → Seal shape**:

| Layout | Use and configuration |
| --- | --- |
| `attestation` | Large heading, bold name row, multiline body and date/reference fields. Enable **Add a generated signature inside the stamp** for a name-based mark in its own row. |
| `corporate` | Paired outer arcs, optional inner top/bottom arcs and central text. Add a geometric shield, rosette or rays motif and a rosette border. |
| `form_block` | Company heading, a centered `REG NO:` row, left-aligned fields, an optional status such as `GRANTED`, and a footer. |
| `nameplate` | Compact company heading and registration text within a single or double frame. |

Use `Label: value` in the body (or bottom row) of attestation/form-block layouts.
`TO:` creates a labeled blank dotted line; `Dated: 18-07-2014` adds a value.
**Field value writing → English cursive** changes values while retaining printed
labels. In Custom mode, `Dated: {date}` and `C.No.: {reference}` vary per sample.
Inner arcs also support the existing placeholders in Random/Custom mode;
Static preserves their literal wording. Intentional repeated source words such
as `COMPANY NAME`/`COMPANY ADDRESS NAME` require **Allow repeated words**.

New `rule_options` fields are `seal_inner_top_text`, `seal_inner_bottom_text`,
`seal_center_motif` (`none`, `shield`, `rosette`, `rays`), `seal_field_writing`
(`printed`, `cursive`), `seal_embedded_signature` and `seal_signer_name` (blank
generates a name). Signature ink gets the whole stamp's opacity once. Fields
record labels, values, font choices and local bounding boxes; the optional
signature records its generated lettering and local box. The composite has
one seal annotation/mask; use separate regions for separate object labels.

The trading-circle comparison is an English layout adaptation. Arabic arc
shaping and the supplied emblem/mascot artwork are not replicated. The shield
and ray motifs and optional signature are generated geometry. Seal6's printed
wording is used as provided, with newly generated handwriting and date/reference
values for comparison; default datasets still use random entities and wording.

**Ink finish → Natural imperfections** now adds patchy pad contact, pores,
chipped outlines and slight deformation to these layouts. Worn is stronger;
Clean disables the new stage. These controls remain separate from Ink wear
and overall opacity. The [ink finish guide](ink-finish.md) describes masks,
local field boxes and the clean/natural/worn comparison gallery.

Postage/revenue stamps and rubber status marks now have separate field types and
controls. Select **Postage / revenue stamp** for printed paper stamps, or **Rubber
stamp** for Approved, Received, Paid and postal cancellation marks. These use
`stamp` and `rubber_stamp` classes. Existing seal templates remain `seal` and are
not automatically relabeled. See the [stamp guide](stamps.md).
