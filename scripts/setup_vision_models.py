"""Explicit public model download; application inference never downloads models."""
import argparse
import hashlib
import json
from pathlib import Path
from huggingface_hub import snapshot_download

MODELS={
    "handwritten":("microsoft/trocr-small-handwritten","b4648cfa171985a6745f37ddd637e98c0da958ac","pytorch_model.bin"),
    "printed":("microsoft/trocr-small-printed","04e994ab854b0089d4929f48c2b4dbe2ce78a340","model.safetensors"),
}

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode",choices=[*MODELS,"both"],default="both")
    parser.add_argument("--directory",type=Path,default=Path("data/models"))
    args=parser.parse_args()
    for mode,(repo,revision,weight) in MODELS.items():
        if args.mode not in {mode,"both"}: continue
        dest=args.directory/f"trocr-small-{mode}"
        snapshot_download(repo,revision=revision,local_dir=dest,allow_patterns=[weight,"*.json","sentencepiece.bpe.model"])
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir() if p.is_file() and p.name!="manifest.json"}
        (dest/"manifest.json").write_text(json.dumps({"repository":repo,"revision":revision,"files":files},indent=2),encoding="utf-8")
        print(f"Installed {repo} at {dest}; runtime inference stays local.")
