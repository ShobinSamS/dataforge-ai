# Signature variation: reference analysis and implementation

The supplied sheets are style references, not training data or outlines to trace.
The renderer composes fictional names and abbreviated letters. Observations below
describe the visible sheets; they do not identify writers or infer personality.

## What differs in the seven references

| Reference | Distinctive visible characteristics | Renderer consequence |
| --- | --- | --- |
| sign1 | Oversized capitals, dense small bodies, long crossbars, uneven cap heights; both decorated and plain names | Vary capital/body ratio, compression, overlap, text length and finish independently |
| sign2 | More restrained, fine cursive; short initials mixed with legible names; oval terminals and compact writing | Include minimal and surname forms, fine strokes and optional returns |
| sign3 | Monograms and two-level compositions, large enclosing loops, extended horizontal strokes, dots, short hatching and occasional stars | Add stacked layout, interlocked initials, terminal loops and attached hatching; isolated stars are not yet implemented |
| sign4 | Short, angular, semi-legible marks; fewer large decorative loops; visible pen lifts and sometimes initials only | Add abbreviated gestural forms, sharp/rounded corners and letter-specific lifts rather than a mandatory oval |
| sign5 | Large entry capitals with smaller slanted bodies, long oblique returns and varied word spacing | Vary entry proportions, baseline rise, slant and understrike independently |
| sign6 | Tall ascenders, compressed names, crossing capitals, variable width and more elaborate terminals | Use crossed initials, separate cap/body advances and terminal shape choices |
| sign7 | Broad loops above the body, nested/intersecting capitals and varied underline directions | Separate letter allographs, overlap and terminal topology; do not apply the same bounding oval to every sample |

The old renderer sampled a script font, scaled capitals and appended one of a few
Bezier finishes. It retained too much of the same printed glyph structure.
Adding more style names alone would not address that limitation.

## Research checked

- [Ferrer et al., Modeling the Lexical Morphology of Western Handwritten Signatures,
  PLOS ONE (2015)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0123254)
  studies text structure, letter dimensions, slant, layout and text/flourish
  relationships. These motivate separate morphology axes rather than a font-only
  preset. Its measured populations are not an Indian English benchmark; no
  population distribution is claimed here.
- [Galbally et al., Synthetic on-line signature generation. Part I:
  Methodology and algorithms (2012)](https://www.sciencedirect.com/science/article/abs/pii/S0031320311005127)
  separates a synthetic identity's master form from variations of that form,
  including stroke/movement parameters. This supports distinguishing different
  signature designs from repeated samples of one signer.
- [O'Reilly and Plamondon, Development of a Sigma–Lognormal representation for
  on-line signatures (2009)](https://www.sciencedirect.com/science/article/abs/pii/S0031320308004470)
  models movement trajectories. A raster reference sheet does not provide pen
  timing or pressure. The present renderer does **not** implement this model or
  claim physically validated motion or biometric realism.

## Implemented morphology

Eight new English pen-path families supplement the previous thirteen forms:
gestural abbreviation, stacked words, initials/letter bridge, terminal loop,
crossed initials, minimal lettering, initial/surname and split letter clusters.
The alphabet is authored locally with separate pen movements, alternate capital
and lowercase letter constructions and smooth cardinal-spline joins. It does not
depend on script-font availability. Independent seeded parameters vary body/cap
ratio, compression, spacing/overlap, slant, baseline rise, corner tension and
terminal topology. Endings include no decoration, crossbar, understrike, upper
oval, lower oval and terminal spiral. Dots and letter crossbars retain pen lifts.
Metadata records these axes and `engine: pen-paths-v1`, `generator_version:
signature-v3`, together with the actual drawn letter sequence.

Mixed favors the new pen paths while keeping plain names and short forms.
Within-signer identity consistency, learned allographs, pressure acquisition,
stars, an Indian signature benchmark and a signature-verification benchmark are
not implemented. Semi-legible stylization is not reliable text transcription;
annotation text is the generator's intended letter sequence.

## Why an existing certificate could still use the old form

The inspected certificate template explicitly saved `signature_style: flourish`.
Its last three 10-sample datasets all recorded `flourish`. That is a fixed style;
changing the default or adding Mixed families does not override it. Existing
datasets contain saved images, and Resume continues the original configuration.

Generation studio now shows the saved region styles. Select **Signature variety
for this batch → Mixed**, then **Preview signature variations**, and create a
**new** generation job. New Generation studio batches default to Mixed. This
override applies to all enabled signature regions without editing the reviewed
template. Saved-style mode remains available; API clients that omit the override retain saved region styles for
compatibility. Dataset cards show the generated signature family.

Run `python -m scripts.preview_signatures` for a reproducible catalogue and
individual transparent PNGs. Use the live preview in Generation studio to check
the selected style before generating a dataset.
