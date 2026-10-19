"""Seeded asset opacity, independent of lettering, layout and ink wear."""
import random


def apply_ink_opacity(layer, rng, options, namespace):
    # Clone rather than advance the renderer's stream: changing opacity must
    # not change the name, shape, stroke weight, position or seal wear.
    independent = random.Random()
    independent.setstate(rng.getstate())
    independent.seed(f"{namespace}:{independent.getrandbits(128)}")
    opacity = (independent.uniform(options.ink_opacity_min, options.ink_opacity_max)
               if options.ink_opacity_mode == "random" else options.ink_opacity)
    if options.ink_opacity_mode == "random":
        opacity = max(options.ink_opacity_min, min(options.ink_opacity_max, round(opacity, 6)))
    # Preserve every nonzero antialias pixel, including at the faintest setting,
    # so opacity changes do not move the annotation's ink boundary.
    alpha = layer.getchannel("A").point([0] + [max(1, round(v * opacity)) for v in range(1, 256)])
    layer.putalpha(alpha)
    mask = alpha.point(lambda p: 255 if p else 0)
    return layer, mask, {"opacity": opacity, "opacity_mode": options.ink_opacity_mode}
