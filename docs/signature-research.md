# Signature variation: reference analysis and implementation

The supplied sheets are style references, not training data or outlines to trace.
Dataset generation composes random names and abbreviated letters. The sign7 test
gallery uses the names printed in the supplied sheet for direct comparison. Observations below
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

Ten English pen-path families supplement the previous thirteen forms:
gestural abbreviation, stacked words, initials/letter bridge, terminal loop,
crossed initials, minimal lettering, initial/surname, split letter clusters,
enclosing returns and interwoven capitals. The latter two adapt sign7's broad
rounded loops, overlapping capital bowls and dense small letter bodies. The
looped families now have dedicated rounded capital allographs for A, I, J, M,
N, P, Q, R, T and W. Interwoven capitals use their own letter bowls instead of
adding a circular frame around every capital. Enclosing returns focus on the
entry capital so the remaining name can extend beyond it. Returns
are attached to lettering and sampled as rounded paths rather than polygonal
frames. Mixed includes all 23 forms.
The alphabet is authored locally with separate pen movements, alternate capital
and lowercase letter constructions and smooth cardinal-spline joins. It does not
depend on script-font availability. Independent seeded parameters vary body/cap
ratio, compression, spacing/overlap, slant, baseline rise, corner tension and
terminal topology. Endings include no decoration, crossbar, understrike, upper
oval, lower oval and terminal spiral. Dots and letter crossbars retain pen lifts.

Auto pen weight also samples normal (60%), medium (25%) and bold (15%) ink.
Weight uses a separate seeded stream and smooth alpha expansion, preserving the
letter sequence, layout, ink color and transparent background. Explicit normal
or bold choices stay fixed. Metadata records `stroke_weight` and `thickness_scale`.
Opacity varies independently: the default is a seeded uniform range of 45–100%.
In **Template editor → Rendering style and cleanup → Ink opacity**, adjust the
minimum/maximum or choose **Fixed opacity** (5–100%). The same controls apply to
seals. Opacity changes alpha only; lettering, color, thickness, geometry and
binary masks remain identical at the same seed. Per-sample metadata records
`opacity` and `opacity_mode`. Seal wear additionally varies local stamp contact.
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

## sign7 regression cases

`tests/fixtures/sign7-cases.json` maps all 15 reference positions (five rows,
three columns) to observed composition features, a selected style, the supplied
name and a reproducible seed. It covers enclosing loops, overlapping capital
bowls, initial/letter bridges, crossed initials, compact surnames and abbreviated
forms. The gallery labels both the reference name and actual drawn letters, so
abbreviation is visible. Enclosed and interwoven styles keep the complete input
name, including single-word names; other styles retain their intentional short
forms. These are generated style adaptations, not exact replicas of the reference.
The named test cases do not replace the dataset's random name generator.

Run `python -m scripts.preview_signature_reference` for the 15-case gallery,
individual transparent PNGs, intended letter metadata and a signature/seal
opacity comparison. This command does not change the checked-in baseline.
`tests/fixtures/sign7-geometry.png` contains only generated binary mask
thumbnails. Regression tests compare geometry against these reviewed images,
check connected ink, and require closed loops in the new ornamental families.
Explicit font and normal weight isolate composition from platform font choice,
random thickness and opacity. Separate opacity tests check reproducibility,
alpha scaling, unchanged masks/labels, transparent compositing and API validation.

To deliberately replace the visual baseline after reviewing a renderer change,
run `python -m scripts.preview_signature_reference --update-baseline`, inspect
the gallery and review the fixture diff. Do not update it just to silence a
failing geometry test. The supplied JPEG remains outside the repository.

Natural ink finishing is now enabled by default: local pressure/nib variation,
small irregular deviations and dry gaps soften the ideal pen paths. Choose
Clean to inspect the underlying letter geometry. Reference geometry tests use
Clean, and the [ink finish tests and comparison](ink-finish.md) check the damaged
output separately without replacing the supplied names or intended letters.
