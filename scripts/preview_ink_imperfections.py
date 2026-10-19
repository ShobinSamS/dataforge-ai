"""Compare clean, natural and worn output using the supplied sign7/seal6/seal8 cases."""
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw
from backend.app.fonts import load_font,resolve_font_weight
from backend.app.schemas import RuleOptions
from backend.app.signatures import render_signature
from backend.app.seals import render_seal,plan_seal_content

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'artifacts/ink-imperfections';out.mkdir(parents=True,exist_ok=True)
    signs=json.loads((ROOT/'tests/fixtures/sign7-cases.json').read_text(encoding='utf-8'))
    seals=json.loads((ROOT/'tests/fixtures/seal-reference-cases.json').read_text(encoding='utf-8'))
    rows=[('signature',case) for case in (signs[0],signs[4],signs[1])]+[('seal',case) for case in (seals[0],seals[3],seals[5])]
    row_heights=[220,220,220,520,520,360]
    gallery=Image.new('RGB',(1680,sum(row_heights)+70),'#edf2f5');draw=ImageDraw.Draw(gallery)
    font=load_font(17);small=load_font(13)
    for column,mode in enumerate(('clean','natural','worn')):
        draw.text((column*560+20,20),mode.upper()+' / same seed and lettering',font=font,fill='#172335')
    records=[];y=60
    for (kind,case),height in zip(rows,row_heights):
        for column,mode in enumerate(('clean','natural','worn')):
            options=RuleOptions(font_id=resolve_font_weight('auto','normal'),ink_opacity_mode='fixed',ink_opacity=1,
                                ink_finish=mode,ink_irregularity=.65,
                                **({'signature_style':case['style'],'text_color':'#173574','font_weight':'normal'} if kind=='signature' else {**case['options'],'seal_wear':0}))
            if kind=='signature':
                size=(500,145);layer,_,info=render_signature(size,case['name'],random.Random(case['seed']),options)
                title=case['name']
            else:
                size=tuple(case['size']);layer,_,info=render_seal(size,plan_seal_content(options,case['seed']),random.Random(case['seed']),options)
                title=case['id']
            x=column*560+10
            draw.rounded_rectangle((x,y,x+540,y+height-12),radius=8,fill='white')
            gallery.paste(layer,(x+(540-size[0])//2,y+8),layer)
            finish=info['ink_finish']
            draw.text((x+12,y+height-56),title,font=font,fill='#172335')
            draw.text((x+12,y+height-31),f"strength {finish['strength']:.0%} / breaks {len(finish['breaks'])} / opacity fixed 100%",font=small,fill='#475569')
            layer.save(out/f"{case.get('id',case.get('cell'))}-{mode}.png")
            records.append({'case':title,'kind':kind,'mode':mode,'metadata':info})
        y+=height
    gallery.save(out/'comparison.png')
    gallery.crop((0,0,1680,720)).save(out/'signature-comparison.png')
    seal_gallery=Image.new('RGB',(1680,gallery.height-720+60),'#edf2f5')
    seal_gallery.paste(gallery.crop((0,720,1680,gallery.height)),(0,60))
    labels=ImageDraw.Draw(seal_gallery)
    for column,mode in enumerate(('clean','natural','worn')):
        labels.text((column*560+20,20),mode.upper()+' / same seed and lettering',font=font,fill='#172335')
    seal_gallery.save(out/'seal-comparison.png')
    (out/'metadata.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(out/'comparison.png')


if __name__=='__main__':main()
