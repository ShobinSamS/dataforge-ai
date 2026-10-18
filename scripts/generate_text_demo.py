"""Generate a small fictional, multilingual text sample pack through the actual API."""
import argparse
import json
import logging
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.app.main import create_app
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("dataforge.text").setLevel(logging.WARNING)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('samples/text'))
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    storage=Path('artifacts/text-demo').resolve();storage.mkdir(parents=True,exist_ok=True)
    app=create_app(f"sqlite:///{storage/'demo.db'}",storage,False)
    with TestClient(app) as client:
        for task in ['classification','ner','qa','instruction','conversation','augmentation']:
            languages=['en','es','fr','de','hi']
            config={'name':f'Fictional {task} examples','task':task,'count':15,'languages':languages,'seed':119}
            if task=='augmentation':
                texts={'en':'The helpful team handled my fictional request quickly and carefully.',
                       'es':'El amable equipo atendió mi solicitud ficticia con rapidez y cuidado.',
                       'fr':"L'équipe serviable a traité ma demande fictive rapidement et soigneusement.",
                       'de':'Das hilfsbereite Team bearbeitete meine fiktive Anfrage schnell und sorgfältig.',
                       'hi':'सहायक टीम ने मेरे काल्पनिक अनुरोध को जल्दी और सावधानी से पूरा किया।'}
                config['source_texts']=[{'text':text,'language':language,'label':'positive'} for language,text in texts.items()]
            response=client.post('/api/text/jobs',json=config);response.raise_for_status();job=response.json()
            app.state.worker.run_text(job['id'])
            quality=client.get(f"/api/text/jobs/{job['id']}/quality").json()
            if quality['accepted']!=15:raise RuntimeError(f'Demo validation failed: {task}: {quality}')
            for format_ in ['csv','json','jsonl']:
                response=client.post(f"/api/text/jobs/{job['id']}/exports",json={'format':format_,'review_confirmed':True})
                response.raise_for_status()
                (output/f'{task}.{format_}').write_bytes(client.get(response.json()['download_url']).content)
            manifest=client.get(f"/api/text/jobs/{job['id']}/manifest").json()
            (output/f'{task}.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'{task}: {quality["accepted"]} validated fictional records',flush=True)


if __name__=='__main__':main()
