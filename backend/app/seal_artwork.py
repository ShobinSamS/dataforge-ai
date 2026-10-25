"""Saved artwork for a seal center; metadata follows the asset into exports."""
from PIL import Image,ImageOps
from .portraits import portrait_metadata
import random


def artwork_alpha(image):
    """Transparent ink already has coverage; opaque scans need white removed.

    Recomputing darkness on a colored transparent PNG would attenuate its ink
    a second time whenever a saved signature or emblem enters a document.
    """
    rgba=image.convert('RGBA');alpha=rgba.getchannel('A')
    return alpha if alpha.getextrema()[0]<255 else ImageOps.invert(ImageOps.grayscale(rgba))


def load_emblem(root, id_, ids=(), seed=42):
    if ids:id_=random.Random(f'seal-artwork:{seed}').choice(ids)
    if not id_: return None, {}
    if root is None: raise ValueError("A saved asset root is required for seal artwork")
    provenance = portrait_metadata(root, id_)
    with Image.open(root/"portraits"/id_/"image.png") as opened:
        image = opened.convert("RGBA")
    return image, {k:v for k,v in provenance.items() if k != "preview_url"}
