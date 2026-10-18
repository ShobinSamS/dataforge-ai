"""Export only accepted samples; never include source files or original OCR strings."""
import json
import zipfile
from pathlib import Path
import numpy as np
import platform
from importlib.metadata import version
from PIL import Image
from .schemas import CLASS_NAMES


def rle(mask: Image.Image) -> dict:
    values = np.asarray(mask).flatten(order="F") > 0
    boundaries = np.flatnonzero(values[1:] != values[:-1]) + 1
    counts = np.diff(np.concatenate(([0],boundaries,[len(values)]))).tolist()
    if len(values) and values[0]:
        counts.insert(0,0)
    return {"size":[mask.height,mask.width],"counts":counts}


def export_zip(job, samples, format_: str, output: Path) -> Path:
    output.parent.mkdir(parents=True,exist_ok=True)
    categories = [{"id":i,"name":name} for i,name in enumerate(CLASS_NAMES)]
    coco = {"images":[],"annotations":[],"categories":categories}
    safe_config = dict(job.config)
    metadata = {"dataset":job.name,"synthetic":True,"version":job.id,"config":safe_config,"template_revision":job.template_snapshot["revision"],
                "template_profile":{k:v for k,v in job.template_snapshot.items() if k != "image_path"},
                "runtime":{"python":platform.python_version(),"pillow":version("pillow"),"numpy":version("numpy"),"faker":version("faker")},
                "classes":CLASS_NAMES,"metrics":job.metrics,"privacy_review":"human-confirmed",
                "training_ready":False,"validation_limitations":["Undetected PII may remain; review every source region",
                "No OCR round-trip check","Barcode decoding not implemented","Statistical utility not evaluated"],
                "count":len(samples),"split":"unsplit; create train/validation/test splits before training",
                "label_provenance":"procedural-mask","mask_semantics":"ideal object support before blur"}
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        archive.writestr("dataset.json",json.dumps(metadata,indent=2))
        archive.writestr("classes.json",json.dumps(CLASS_NAMES))
        archive.writestr("data.yaml","path: .\ntrain: images\nval: images\n# Demo only: split disjoint train/val before training.\nnames:\n"+"".join(f"  {i}: {n}\n" for i,n in enumerate(CLASS_NAMES)))
        for sample in samples:
            folder = Path(sample.path).parent
            name = f"{sample.index:06d}"
            archive.write(sample.path,f"images/{name}.png")
            record = json.loads((folder/"metadata.json").read_text(encoding="utf-8"))
            for annotation in record["annotations"]:
                archive_path = f"masks/{name}/{annotation['mask']}"
                archive.write(folder/annotation["mask"],archive_path)
                annotation["mask"] = archive_path
            archive.writestr(f"metadata/{name}.json",json.dumps(record,indent=2))
            if format_ == "yolo":
                archive.write(folder/"labels.txt",f"labels/{name}.txt")
            if format_ == "ocr":
                archive.writestr(f"ocr/{name}.json",json.dumps({"image":f"images/{name}.png","fields":record["annotations"]}))
            if format_ == "coco":
                with Image.open(sample.path) as img:
                    coco["images"].append({"id":sample.index,"file_name":f"images/{name}.png","width":img.width,"height":img.height})
                for a in sample.annotations:
                    with Image.open(folder/a["mask"]) as mask:
                        coco["annotations"].append({"id":len(coco["annotations"])+1,"image_id":sample.index,
                            "category_id":a["class_id"],"bbox":a["bbox"],"area":int(np.count_nonzero(np.asarray(mask))),
                            "segmentation":rle(mask),"iscrowd":0})
        if format_ == "coco":
            archive.writestr("annotations.json",json.dumps(coco))
    return output
