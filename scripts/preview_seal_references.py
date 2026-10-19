"""Render supplied-wording seal6/seal8 comparison cases without copying image pixels.

Run: python -m scripts.preview_seal_references
Use --update-baseline only after reviewing a deliberate renderer change.
"""
import argparse
import json
import random
import hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps, PngImagePlugin
from backend.app.schemas import RuleOptions
from backend.app.seals import plan_seal_content, render_seal
from backend.app.fonts import load_font,resolve_font_weight,cursive_font_id

ROOT=Path(__file__).resolve().parents[1]
CASES=ROOT/'tests/fixtures/seal-reference-cases.json'


def reference_font_fingerprint():
    base=resolve_font_weight('auto','normal')
    glyphs=[]
    for face in (base,resolve_font_weight(base,'bold'),cursive_font_id()):
        font=load_font(32,face)
        glyphs.append(bytes(font.getmask('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')))
    return hashlib.sha256(b'|'.join(glyphs)).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-baseline',action='store_true')
    parser.add_argument('--finish',choices=('clean','natural','worn'),default='natural')
    args=parser.parse_args()
    out=ROOT/'artifacts/seal-reference-cases';out.mkdir(parents=True,exist_ok=True)
    cases=json.loads(CASES.read_text(encoding='utf-8'))
    gallery=Image.new('RGB',(1680,1860),'#eaf0f4');draw=ImageDraw.Draw(gallery)
    baseline=Image.new('L',(660,660));records=[]
    for i,case in enumerate(cases):
        options=RuleOptions(font_id=resolve_font_weight('auto','normal'),ink_opacity_mode='fixed',ink_opacity=1,ink_finish=args.finish,**case['options'])
        layer,mask,info=render_seal(tuple(case['size']),plan_seal_content(options,case['seed']),random.Random(case['seed']),options)
        layer.save(out/f"{case['id']}.png")
        if args.update_baseline:
            _,mask,_=render_seal(tuple(case['size']),plan_seal_content(options,case['seed']),random.Random(case['seed']),options.model_copy(update={'ink_finish':'clean'}))
        thumbnail=ImageOps.pad(mask,(220,220),method=Image.Resampling.BOX,color=0).point(lambda p:255 if p>=128 else 0)
        baseline.paste(thumbnail,(i%3*220,i//3*220))
        x,y=i%3*560+10,i//3*620+10
        draw.rounded_rectangle((x,y,x+540,y+600),radius=8,fill='white')
        gallery.paste(layer,(x+(540-layer.width)//2,y+20+(480-layer.height)//2),layer)
        draw.text((x+12,y+510),case['id'],font=load_font(18),fill='#172335')
        draw.text((x+12,y+540),case['reference'],font=load_font(14),fill='#334155')
        # Wrap the brief feature description to keep it inside the card.
        words=case['feature'].split();lines=['']
        for word in words:
            if len(lines[-1])+len(word)>66:lines.append('')
            lines[-1]+=(' ' if lines[-1] else '')+word
        draw.multiline_text((x+12,y+565),'\n'.join(lines),font=load_font(12),fill='#64748b')
        records.append({**case,'metadata':info})
    gallery.save(out/'comparison.png')
    (out/'metadata.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    if args.update_baseline:
        metadata=PngImagePlugin.PngInfo();metadata.add_text('font_fingerprint',reference_font_fingerprint())
        baseline.save(ROOT/'tests/fixtures/seal-reference-geometry.png',pnginfo=metadata)
    print(out/'comparison.png')


if __name__=='__main__':main()
