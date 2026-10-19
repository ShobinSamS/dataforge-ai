"""Run python -m scripts.preview_seals for fictional transparent seal examples."""
import json
import random
from pathlib import Path
from PIL import Image,ImageDraw
from backend.app.schemas import RuleOptions
from backend.app.seals import SHAPES,plan_seal_content,render_seal


def main():
    out=Path('artifacts/seal-variations');out.mkdir(parents=True,exist_ok=True)
    gallery=Image.new('RGB',(1440,1480),'#edf2f5');draw=ImageDraw.Draw(gallery)
    for i,shape in enumerate((*SHAPES,'random')):
        seed=42+i*1009;style=RuleOptions(seal_style=shape)
        size=(410,210) if shape in {'rectangle','professional','form','dated','text'} else (300,300)
        layer,_,info=render_seal(size,plan_seal_content(style,seed),random.Random(seed),style)
        layer.save(out/f'{shape}.png');(out/f'{shape}.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
        x=i%3*480+15;y=i//3*370+10
        draw.rounded_rectangle((x,y,x+450,y+350),radius=8,fill='white')
        gallery.paste(layer,(x+(450-size[0])//2,y+10+(300-size[1])//2),layer)
        draw.text((x+12,y+325),info['shape']+' / '+info['border']+' / '+info['ink'],fill='#475569')
    gallery.save(out/'preview.png');print((out/'preview.png').resolve())


if __name__=='__main__':main()
