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
form, dated, and unframed text. Random shape selection respects the selected
region's aspect ratio. Borders include solid, double, dotted, dashed and toothed
(serrated) patterns. Ornaments include stars, diamonds, rosettes and monograms.
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

These are layout references. Generated entities and ornaments are fictional;
the code does not trace supplied government emblems, signatures or named seals.

Run `python -m scripts.preview_seals` from the repository root for a catalogue
under `artifacts/seal-variations/`, including individual transparent PNGs and
their metadata. Exports record the exact drawn seal text, shape, border,
ornament, colors and content mode in each seal annotation (`engine: seal-v2`).

`POST /api/seals/preview` accepts `options` (RuleOptions), `seed`, `region_id`,
`width`, `height` and an optional explicit `literal`. It returns a transparent
PNG data URL and metadata without creating or changing a template or dataset.
