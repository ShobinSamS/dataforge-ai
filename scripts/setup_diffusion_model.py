"""Explicit SD-Turbo download. Generation itself never accesses the network."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx
from huggingface_hub import model_info, snapshot_download, get_hf_file_metadata, hf_hub_url

REPOSITORY = "stabilityai/sd-turbo"
WEIGHTS = ["text_encoder/model.fp16.safetensors", "unet/diffusion_pytorch_model.fp16.safetensors",
           "vae/diffusion_pytorch_model.fp16.safetensors"]


def download_weight(directory, revision, name):
    url = hf_hub_url(REPOSITORY, name, revision=revision)
    metadata = get_hf_file_metadata(url)
    dest = directory/name; dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix+".part")
    if dest.is_file() and dest.stat().st_size == metadata.size:
        candidate = dest
    else:
        # Explicit bounded Range requests avoid proxies buffering multi-GB bodies.
        offset = partial.stat().st_size if partial.exists() else 0
        with httpx.Client(follow_redirects=True, timeout=120) as client, partial.open("ab") as stream, ThreadPoolExecutor(max_workers=3) as chunks:
            def fetch(start):
                end = min(metadata.size-1, start+16*1024**2-1)
                response = client.get(url, headers={"Range":f"bytes={start}-{end}"})
                response.raise_for_status()
                if response.status_code != 206 or response.headers.get("content-range") != f"bytes {start}-{end}/{metadata.size}" or len(response.content) != end-start+1:
                    raise ValueError("Model server did not return the requested byte range; retry setup")
                return response.content
            while offset < metadata.size:
                starts = range(offset, min(metadata.size, offset+3*16*1024**2),16*1024**2)
                for content in chunks.map(fetch, starts):
                    stream.write(content); stream.flush(); offset += len(content)
                    print(f"{name}: {offset//1024**2}/{metadata.size//1024**2} MB", flush=True)
        candidate = partial
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024), b""): digest.update(block)
    if digest.hexdigest() != metadata.etag:
        raise ValueError(f"SHA256 mismatch for {name}; remove the partial weight and rerun setup")
    if candidate == partial: partial.replace(dest)


def install(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    revision = model_info(REPOSITORY).sha
    snapshot_download(REPOSITORY, revision=revision, local_dir=directory,
        allow_patterns=["model_index.json", "scheduler/*.json", "tokenizer/*",
                        "text_encoder/config.json", "unet/config.json", "vae/config.json",
                        "README.md", "LICENSE*"], max_workers=2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda name:download_weight(directory,revision,name), WEIGHTS))
    files = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or ".cache" in path.parts or path.name == "manifest.json":
            continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024*1024), b""):
                digest.update(block)
        files[path.relative_to(directory).as_posix()] = digest.hexdigest()
    manifest = {"repository": REPOSITORY, "revision": revision, "variant": "fp16",
                "source_url": f"https://huggingface.co/{REPOSITORY}/tree/{revision}",
                "license_url": "https://huggingface.co/stabilityai/sd-turbo",
                "files": files}
    (directory/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Installed {REPOSITORY}@{revision} in {directory}. Runtime stays offline.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/models/sd-turbo"))
    install(parser.parse_args().directory)
