"""Only fictional data. No model weights or remote services required."""
import io
from pathlib import Path


def certificate() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer,pagesize=(900,640),pageCompression=1)
    c.setTitle("Fictional DataForge certificate")
    c.setFillColor(HexColor("#faf8f2")); c.rect(0,0,900,640,fill=1,stroke=0)
    c.setStrokeColor(HexColor("#c6b78c")); c.setLineWidth(2); c.rect(30,30,840,580)
    c.setLineWidth(.6); c.rect(38,38,824,564)
    def text(x,y,value,size=16,color="#243a40"):
        c.setFillColor(HexColor(color)); c.setFont("Helvetica",size); c.drawString(x,y,value)
    text(70,550,"NORTHSTAR  /  FICTIONAL LEARNING INSTITUTE",12)
    text(70,479,"Certificate of completion",36)
    text(70,432,"This sample certifies that",14)
    text(70,378,"Alex Example",30)
    text(70,335,"completed the synthetic data engineering program.",16)
    text(70,275,"Record ID",11); text(70,247,"SYN-DEMO-0042",18)
    text(410,275,"Date",11); text(410,247,"2025-06-15",18)
    text(70,193,"Contact",11); text(70,166,"alex@example.invalid",16)
    text(70,76,"Fictional signature",10); text(382,76,"Fictional seal",10); text(715,76,"Sample QR",10)
    text(70,43,"FICTIONAL SAMPLE - NOT A VALID CREDENTIAL",9,"#8a7861")
    c.save()
    return buffer.getvalue()


def demo_regions(regions: list[dict]) -> list[dict]:
    mapping = {"Alex Example":"name","SYN-DEMO-0042":"identifier","2025-06-15":"date","alex@example.invalid":"email"}
    for r in regions:
        kind = mapping.get(r["text"])
        r.update(kind=kind or "text",sensitive=bool(kind),replace=bool(kind),confirmed=False)
    # Coordinates explicitly authored for the fictional fixture, not detected visual objects.
    for id_,kind,box in [("demo_signature","signature",[105,755,340,65]),
                         ("demo_seal","seal",[570,700,125,125]),
                         ("demo_qr","qr",[1065,650,165,165])]:
        regions.append({"id":id_,"label":f"Fictional {kind} (fixture region)","kind":kind,"box":box,
                        "text":"","confidence":1,"sensitive":True,"replace":True,"confirmed":False,"page":0,"rule":""})
    return regions
