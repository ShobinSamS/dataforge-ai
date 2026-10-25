"""Readable seeded handwriting from local cursive glyphs; text is known by construction."""
import math
import random
from PIL import Image,ImageDraw,ImageOps
from .fonts import load_font,cursive_font_id


def handwritten(size,text,color,seed,font_id='auto'):
    rng=random.Random(f'handwriting:{seed}:{text}');face=load_font(76,cursive_font_id() if font_id=='auto' else font_id)
    lines=text.splitlines() or [''];line_widths=[sum(face.getlength(c)*1.12+4 for c in line) for line in lines]
    large=Image.new('RGBA',(max(32,math.ceil(max(line_widths))+60),len(lines)*132+40));slope=rng.uniform(-.018,.018)
    for row,line in enumerate(lines):
        x=25.
        for char in line:
            advance=face.getlength(char)
            if char.isspace():x+=advance+5;continue
            bounds=face.getbbox(char);glyph=Image.new('RGBA',(max(1,bounds[2]-bounds[0])+16,max(1,bounds[3]-bounds[1])+16))
            ImageDraw.Draw(glyph).text((8-bounds[0],8-bounds[1]),char,font=face,fill=color)
            glyph=glyph.rotate(rng.uniform(-3,3),Image.Resampling.BICUBIC,expand=True)
            y=25+row*132+bounds[1]+slope*x+rng.uniform(-2.2,2.2)
            large.alpha_composite(glyph,(round(x),round(y)));x+=advance*rng.uniform(.98,1.13)+3
    bounds=large.getbbox()
    if not bounds:raise ValueError('Handwriting needs visible text')
    crop=ImageOps.contain(large.crop(bounds),(max(1,size[0]-8),max(1,size[1]-8)),Image.Resampling.LANCZOS)
    layer=Image.new('RGBA',size);layer.alpha_composite(crop,((size[0]-crop.width)//2,(size[1]-crop.height)//2))
    return layer,layer.getchannel('A').point(lambda p:255 if p else 0)
