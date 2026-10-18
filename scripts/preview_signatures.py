"""Render a reproducible catalogue of fictional signature styles and PNG layers.

Run from the repository root: python -m scripts.preview_signatures
"""
import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw

from backend.app.schemas import RuleOptions
from backend.app.signatures import render_signature


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("artifacts/signature-references"))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    examples=[
        ("tall_initial",12,"Arun Kumar"),("looped",42,"Mira Dev"),("sweeping",79,"Rohan Sen"),
        ("compact",25,"Nila Shah"),("angular",34,"Dev Mehra"),("tall_initial",91,"Sara Das"),
        ("single_letter",42,"Arun Kumar"),("letter_wave",79,"Mira Dev"),("monogram",12,"Rohan Sen"),
        ("first_name",25,"Nila Shah"),("looped",34,"Dev Mehra"),("sweeping",91,"Sara Das"),
    ]
    gallery=Image.new("RGB",(1200,800),"#edf2f5");draw=ImageDraw.Draw(gallery)
    for index,(family,seed,name) in enumerate(examples):
        color=("#173574","#16191d","#633046")[index%3]
        layer,_,info=render_signature((360,140),name,random.Random(seed),RuleOptions(signature_style=family,text_color=color))
        layer.save(args.output/f"{family}-{seed}.png")
        x=index%3*400+20;y=index//3*200+10
        draw.rounded_rectangle((x,y,x+360,y+180),radius=8,fill="white")
        gallery.paste(layer,(x,y+5),layer)
        draw.text((x+12,y+156),family.replace("_"," ")+" / "+info["text"],fill="#475569")
    path=args.output/"signature-examples.png";gallery.save(path)
    print(path.resolve())


if __name__=="__main__":main()
