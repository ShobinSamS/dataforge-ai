"""Exercise real offline diffusion through the running API and save rendered examples."""
import argparse
import base64
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
import httpx

PROMPTS = {
    "portrait": "An adult South Asian woman, short dark hair, business casual clothing, neutral expression, realistic portrait",
    "seal_artwork": "A cedar tree above two small leaves, symmetrical botanical emblem",
    "stamp_artwork": "A coastal lighthouse with waves and seabirds, detailed vintage engraving",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--kind", choices=[*PROMPTS,"all"], default="all")
    parser.add_argument("--steps", type=int, choices=range(1,5), default=1)
    parser.add_argument("--directory", type=Path, default=Path("artifacts/diffusion-benchmark"))
    args = parser.parse_args()
    origin = urlsplit(args.api_url)
    if origin.scheme != 'http' or origin.hostname not in {'localhost','127.0.0.1'} or origin.username or origin.password or origin.path not in {'','/'} or origin.query or origin.fragment:
        parser.error("Use a plain local HTTP API origin")
    args.directory.mkdir(parents=True, exist_ok=True)
    results = []
    with httpx.Client(base_url=args.api_url, timeout=60, trust_env=False) as client:
        def call(method, path, **kwargs):
            response = client.request(method,path,**kwargs)
            response.raise_for_status(); return response
        for kind, prompt in PROMPTS.items():
            if args.kind not in {kind,'all'}: continue
            job = call('POST','/api/diffusion/jobs',json={'kind':kind,'prompt':prompt,'seed':42,'steps':args.steps}).json()
            print(f"{kind}: {job['id']} queued",flush=True)
            deadline = time.monotonic()+750; previous = None
            while job['status'] not in {'completed','failed','cancelled'}:
                if time.monotonic()>deadline: raise TimeoutError('Preview wait expired; inspect AI image studio')
                time.sleep(2)
                job = call('GET',f"/api/diffusion/jobs/{job['id']}").json()
                marker = (job['status'],job['step'])
                if marker != previous:
                    print(f"{kind}: {job['status']} step {job['step']}/{job['steps']}",flush=True); previous=marker
            (args.directory/f'{kind}.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
            if job['status']!='completed': raise RuntimeError(job.get('error') or job['status'])
            (args.directory/f'{kind}-original.png').write_bytes(call('GET',job['image_url']).content)
            asset = call('POST',f"/api/diffusion/jobs/{job['id']}/save").json()
            options = {'portrait_source':'asset_pool','portrait_asset_ids':[asset['id']]}
            target = 'portrait' if kind=='portrait' else 'seal' if kind=='seal_artwork' else 'stamp'
            if target=='seal': options={'seal_artwork_id':asset['id'],'seal_style':'corporate','seal_text_mode':'static','seal_text':'CEDAR RESEARCH','seal_subtext':'','seal_bottom_text':'SAMPLE DIVISION','seal_symbol':'none','ink_finish':'clean','seal_wear':.03}
            if target=='stamp': options.update(stamp_style='architecture',stamp_issuer='MAPLE POST',stamp_denomination='2.50',stamp_caption='COASTAL LIGHT',stamp_cancellation='none')
            rendered = call('POST','/api/assets/generate',json={'kind':target,'width':400,'height':400 if target=='seal' else 500,'options':options}).json()
            (args.directory/f'{kind}-rendered.png').write_bytes(base64.b64decode(rendered['image'].split(',',1)[1]))
            (args.directory/f'{kind}-rendered.json').write_text(json.dumps(rendered['metadata'],indent=2),encoding='utf-8')
            print(json.dumps({'kind':kind,'metrics':job['metrics'],'rendered':str(args.directory/f'{kind}-rendered.png')}),flush=True)
            results.append({'kind':kind,'job_id':job['id'],'metrics':job['metrics']})
    (args.directory/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')


if __name__ == '__main__': main()
