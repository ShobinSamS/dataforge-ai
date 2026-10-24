"""Saved artwork for a seal center; metadata follows the asset into exports."""
from PIL import Image
from .portraits import portrait_metadata
import random


def load_emblem(root, id_, ids=(), seed=42):
    if ids:id_=random.Random(f'seal-artwork:{seed}').choice(ids)
    if not id_: return None, {}
    if root is None: raise ValueError("A saved asset root is required for seal artwork")
    provenance = portrait_metadata(root, id_)
    with Image.open(root/"portraits"/id_/"image.png") as opened:
        image = opened.convert("RGBA")
    return image, {k:v for k,v in provenance.items() if k != "preview_url"}
