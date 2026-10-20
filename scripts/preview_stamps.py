"""Reference-inspired paper stamps, cancellations and separate approval marks."""
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw
from backend.app.schemas import RuleOptions
from backend.app.stamps import plan_stamp, render_stamp, plan_rubber_stamp, render_rubber_stamp
from backend.app.fonts import load_font

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/"artifacts/postage-stamps";out.mkdir(parents=True,exist_ok=True)
    cases=[
        ("portrait / sepia", "portrait", "sepia", "none", (220,300)),
        ("portrait / blue", "portrait", "blue", "none", (220,300)),
        ("architecture / green", "architecture", "green", "none", (300,220)),
        ("architecture / multicolor", "architecture", "multicolor", "none", (300,220)),
        ("botanical / purple", "botanical", "purple", "none", (220,300)),
        ("commemorative / red", "commemorative", "red", "none", (300,220)),
        ("revenue / red / pen cancelled", "revenue", "red", "pen", (220,300)),
        ("revenue / purple / postmark", "revenue", "purple", "postmark", (220,300)),
        ("portrait / green / waves", "portrait", "green", "waves", (220,300)),
    ]
    records=[]
    gallery=Image.new("RGB",(1080,1155),"#e9edf0");draw=ImageDraw.Draw(gallery)
    draw.text((25,15),"Postage / revenue stamps · separate stamp class",font=load_font(24),fill="#243943")
    for i,(label,style,palette,cancellation,size) in enumerate(cases):
        options=RuleOptions(stamp_style=style,stamp_palette=palette,stamp_cancellation=cancellation,stamp_age=.45,
                            ink_opacity_min=.72,ink_opacity_max=.98)
        seed=71+i*13;layer,mask,meta=render_stamp(size,plan_stamp(options,seed),random.Random(seed),options)
        layer.save(out/f"paper-{i+1}.png");mask.save(out/f"paper-{i+1}-mask.png")
        x=360*(i%3);y=60+365*(i//3)
        gallery.paste(layer,(x+(360-size[0])//2,y+(305-size[1])//2),layer)
        draw.text((x+14,y+312),label,font=load_font(15),fill="#243943")
        records.append({"kind":"stamp","seed":seed,"options":options.model_dump(mode="json"),"metadata":meta})
    gallery.save(out/"paper-gallery.png")
    gallery=Image.new("RGB",(1080,660),"#f1f3f5");draw=ImageDraw.Draw(gallery)
    draw.text((25,15),"Rubber stamps · separate rubber_stamp class",font=load_font(24),fill="#243943")
    for i,(style,text,color) in enumerate((("boxed","APPROVED","red"),("text","RECEIVED","blue"),("dated","PAID","purple"),
                                          ("round","COPY","green"),("postmark","","black"),("waves","","black"))):
        options=RuleOptions(rubber_stamp_style=style,rubber_stamp_mode="static",rubber_stamp_text=text or "CANCELLED",rubber_stamp_color=color)
        seed=55+i*7;layer,mask,meta=render_rubber_stamp((310,220),plan_rubber_stamp(options,seed),random.Random(seed),options)
        layer.save(out/f"rubber-{i+1}.png");mask.save(out/f"rubber-{i+1}-mask.png")
        x=360*(i%3);y=60+295*(i//3);gallery.paste(layer,(x+25,y),layer)
        draw.text((x+20,y+235),f"{style} · {text or 'postal cancellation'}",font=load_font(15),fill="#243943")
        records.append({"kind":"rubber_stamp","seed":seed,"options":options.model_dump(mode="json"),"metadata":meta})
    gallery.save(out/"rubber-gallery.png")
    (out/"metadata.json").write_text(json.dumps(records,indent=2),encoding="utf-8")
    print(out)


if __name__=="__main__":main()
