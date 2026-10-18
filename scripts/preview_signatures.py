"""Render a reproducible catalogue of fictional signature styles and PNG layers.

Run from the repository root: python -m scripts.preview_signatures
"""
import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw

from backend.app.schemas import RuleOptions
from backend.app.signatures import render_signature, STYLES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("artifacts/signature-references"))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    examples=[
        ("gestural",12,"Arun Kumar"),("stacked",42,"Mira Dev"),("initial_bridge",79,"Rohan Sen"),
        ("terminal_loop",25,"Nila Shah"),("crossed",34,"Dev Mehra"),("minimal",91,"Sara Das"),
        ("surname",42,"Arun Kumar"),("split",79,"Mira Dev"),("gestural",91,"Rohan Sen"),
        ("minimal",12,"Arun Kumar"),("terminal_loop",34,"Dev Mehra"),("crossed",79,"Sara Das"),
    ]
    gallery=Image.new("RGB",(1200,800),"#edf2f5");draw=ImageDraw.Draw(gallery)
    for index,(family,seed,name) in enumerate(examples):
        color=("#173574","#16191d","#633046")[index%3]
        layer,_,info=render_signature((360,140),name,random.Random(seed),RuleOptions(signature_style=family,text_color=color))
        layer.save(args.output/f"{family}-{seed}.png")
        x=index%3*400+20;y=index//3*200+10
        draw.rounded_rectangle((x,y,x+360,y+180),radius=8,fill="white")
        gallery.paste(layer,(x,y+5),layer)
        draw.text((x+12,y+156),family.replace("_"," ")+" / "+info["text"].replace("\n"," | "),fill="#475569")
    path=args.output/"signature-examples.png";gallery.save(path)
    print(path.resolve())
    rows=len(STYLES);catalogue=Image.new("RGB",(1400,rows*160),"#edf2f5");labels=ImageDraw.Draw(catalogue)
    for row,family in enumerate(STYLES):
        for col,seed in enumerate((12,42,79,91)):
            name=("Arun Kumar","Mira Dev","Rohan Sen","Nila Shah")[col]
            layer,_,info=render_signature((320,120),name,random.Random(seed),RuleOptions(signature_style=family,text_color="#173574"))
            layer.save(args.output/f"{family}-{seed}.png")
            x=col*350+15;y=row*160
            catalogue.paste(layer,(x,y),layer)
            labels.text((x,y+128),family+" / "+info["text"].replace("\n"," | "),fill="#475569")
    catalogue.save(args.output/"signature-catalogue.png")


if __name__=="__main__":main()
