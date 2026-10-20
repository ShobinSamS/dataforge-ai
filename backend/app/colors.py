"""Seeded ink selection, independent of lettering/layout random streams."""
import random

DEFAULT_PALETTE=["#000000","#173574","#a61c32","#216e39","#6a338e"]


def choose_color(options,rng,salt="ink"):
    # Explicit text_color remains compatible with older clients. The black UI
    # preset resets text_color to #000000, which is also the schema default.
    if options.color_mode=="black":return options.text_color
    if options.color_mode in {"random","mixed"}:
        independent=random.Random();independent.setstate(rng.getstate())
        independent=random.Random(f"{independent.getrandbits(64)}:{salt}")
        return independent.choice(options.color_palette)
    return options.text_color


def rgb(value):
    return tuple(bytes.fromhex(value[1:]))


def restore_ink_colors(layer, colors):
    """Keep chosen RGB exact after RGBA resampling; coverage stays in alpha."""
    import numpy as np
    from PIL import Image

    palette = list(dict.fromkeys(tuple(color[:3]) for color in colors))
    alpha = layer.getchannel("A")
    if len(palette) == 1:
        result = Image.new("RGBA", layer.size, (*palette[0], 255))
        result.putalpha(alpha)
        return result
    pixels = np.array(layer)
    visible = pixels[:, :, 3] > 0
    values = pixels[visible, :3].astype(np.int32)
    choices = np.asarray(palette, dtype=np.int32)
    distances = ((values[:, None, :] - choices[None, :, :]) ** 2).sum(axis=2)
    pixels[visible, :3] = choices[distances.argmin(axis=1)]
    return Image.fromarray(pixels)
