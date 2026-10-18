"""Real procedural benchmark, with a fictional 100-document demonstration by default."""
import argparse
import json
import platform
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.app.main import create_app


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--count',type=int,default=100)
    parser.add_argument('--output',type=Path,default=Path('artifacts/benchmark'))
    args=parser.parse_args()
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    app=create_app(f"sqlite:///{root/'benchmark.db'}",root,start_worker=False)
    with TestClient(app) as client:
        t=client.post('/api/templates/demo').json()
        for r in t['regions']:
            r['confirmed']=True
        response=client.put(f"/api/templates/{t['id']}/review",json={'regions':t['regions'],'privacy_confirmed':True,'revision':1})
        response.raise_for_status()
        response=client.post('/api/jobs',json={'template_id':t['id'],'count':args.count,'seed':42,'name':'Fictional certificate benchmark'})
        response.raise_for_status();j=response.json()
        start=time.perf_counter();app.state.worker.run(j['id']);elapsed=time.perf_counter()-start
        job=client.get(f"/api/jobs/{j['id']}").json()
        quality=client.get(f"/api/jobs/{j['id']}/quality").json()
        report={'platform':platform.platform(),'processor':platform.processor(),'python':platform.python_version(),
                'engine':'procedural; no model inference','job':job,'quality':quality,'wall_seconds':round(elapsed,3),
                'samples_per_second':round(job['completed']/elapsed,3),
                'scope':'Measured on this execution host, not a claim about another laptop. Process RSS is not total system RAM.'}
        if quality['accepted']:
            result=client.post(f"/api/jobs/{j['id']}/exports",json={'format':'yolo','review_confirmed':True})
            result.raise_for_status()
            (root/f'fictional_{args.count}_yolo.zip').write_bytes(client.get(result.json()['download_url']).content)
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
        if job['status']!='completed':
            raise SystemExit(1)


if __name__=='__main__':
    main()
