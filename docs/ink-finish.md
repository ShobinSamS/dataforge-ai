# Natural pen and stamp imperfections

The supplied signature sheets show nonuniform pen pressure, small interruptions
and uneven returns. The seal references show local loss of contact, pores and
broken border sections. A uniform opacity change leaves ideal shapes intact.
The finish stage now changes ink locally, after composing the chosen design.

In **Template editor → Rendering style and cleanup** for a signature or seal:

| Control | Behavior |
| --- | --- |
| Ink finish: Natural imperfections | Default; small nonperiodic distortions, uneven pressure and sparse breaks |
| Ink finish: Worn / dry ink | Stronger contact loss, grain and interruptions |
| Ink finish: Clean | Disables the new finish stage |
| Imperfection strength | 0–100%; default 55%. Sample strength varies around this value with its seed; Worn increases it. Zero disables the new stage. |
| Ink opacity | Independent overall transparency, applied after the defects |
| Ink wear (seals) | Existing separate fine-grain stamp wear. Set it to zero as well for a pristine Clean stamp. |

Save/review the region and create a **new dataset**. Existing saved images are
retained. Signature previews use the first region's saved finish and opacity.
Seal previews use the current region's settings. The same seed and configuration
reproduce the same defects without reshuffling names, letters, styles or colors.

Signatures get local nib/flow variation, small smooth deviations and occasional
dry-ink gaps across the stroke direction. Seals get uneven pad contact, broad
faded patches, small pores, chipped edges and bounded deformation. Defects are
restricted to the ink footprint: no paper rectangle or unrelated marks are added.
Color interpolation uses premultiplied alpha to avoid dark edge halos.

Masks are recomputed from the resulting ink, including real holes and movement.
The subsequent opacity change preserves those masks. Seal field/signature local
boxes are conservatively moved by the affine transform and expanded for the
bounded paper warp. Main object boxes come from the final mask as before. The
annotation retains the intended lettering; the renderer does not validate OCR
legibility or biometric realism of damaged output.

Each asset annotation includes `ink_finish` metadata: profile, chosen strength,
rotation, affine matrix, maximum displacement, break locations, retained ink when applied
and `engine: ink-finish-v1`. API `rule_options` fields are `ink_finish`
(`clean`, `natural`, `worn`; default `natural`) and `ink_irregularity` (finite
0–1; default 0.55). Both signature preview endpoints accept the same query
parameters; the PNG response also reports `X-Ink-Finish`.

Run `python -m scripts.preview_ink_imperfections` for clean/natural/worn columns
using the supplied sign7 names and seal6/seal8 wording. Outputs are in
`artifacts/ink-imperfections/`, including separate signature/seal comparison
galleries, transparent PNGs and metadata. Its columns fix opacity at 100% and
seal wear at zero to isolate the new finish. The two reference catalogue scripts
also accept `--finish clean|natural|worn` and default to Natural. Their geometry
baselines deliberately use Clean, while separate tests check imperfections,
pressure variance, missing ink, determinism, bounds, masks and preview settings.
