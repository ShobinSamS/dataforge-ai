"""Opt-in live local Qwen smoke tests. No downloads or external inference."""
import argparse
import json
import logging
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.app.main import create_app
logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('artifacts/text-llm'))
    parser.add_argument('--tasks',nargs='+',default=['classification','ner','qa','instruction','conversation','augmentation'])
    parser.add_argument('--count',type=int,default=1)
    parser.add_argument('--batch-size',type=int,default=1)
    args=parser.parse_args();root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    app=create_app(f"sqlite:///{root/'verification.db'}",root,False)
    reports=[]
    with TestClient(app) as client:
        capabilities=client.get('/api/text/capabilities').json()
        if not capabilities['llm']['installed']: raise SystemExit('Local configured Qwen GGUF is unavailable; no download performed')
        for task in args.tasks:
            config={'task':task,'backend':'ollama','count':args.count,'batch_size':args.batch_size,'seed':517,
                    'languages':['hi'] if task=='ner' else ['en']}
            if task=='augmentation': config['source_texts']=[{'text':'The helpful team resolved my fictional service request quickly.','language':'en','label':'positive'}]
            response=client.post('/api/text/jobs',json=config);response.raise_for_status();j=response.json()
            app.state.worker.run_text(j['id'])
            job=client.get(f"/api/text/jobs/{j['id']}").json()
            quality=client.get(f"/api/text/jobs/{j['id']}/quality").json()
            records=client.get(f"/api/text/jobs/{j['id']}/records").json()['items']
            report={'task':task,'status':job['status'],'quality':quality,'metrics':job['metrics'],'records':records}
            reports.append(report)
            (root/'report.json').write_text(json.dumps({'capabilities':capabilities,'runs':reports},ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'task':task,'status':job['status'],'accepted':quality['accepted'],'error':job['error']}),flush=True)
        if any(r['quality']['accepted']!=args.count for r in reports): raise SystemExit(1)


if __name__=='__main__':main()
