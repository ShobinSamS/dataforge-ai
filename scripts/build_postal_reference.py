"""Explicit maintainer download; document generation never accesses the network.

GeoNames CC BY 4.0. Save a deterministic, geographically distributed subset of
each country's rows. Full GB/CA files retain complete postal codes.
"""
import argparse
import csv
import hashlib
import io
import json
import random
import re
import urllib.request
import zipfile
from datetime import datetime,timezone
from pathlib import Path

COUNTRIES={"IN":"India","US":"United States","GB":"United Kingdom","CA":"Canada",
           "AU":"Australia","DE":"Germany","FR":"France","NZ":"New Zealand",
           "ES":"Spain","IT":"Italy","MY":"Malaysia","PK":"Pakistan"}


def build(destination,limit=256):
    result={"source":"GeoNames","license":"CC BY 4.0","license_url":"https://creativecommons.org/licenses/by/4.0/",
            "source_url":"https://download.geonames.org/export/zip/","retrieved_at":datetime.now(timezone.utc).isoformat(),
            "notice":"Derived subset; street/house numbers are generated, not supplied by GeoNames. GB contains Royal Mail data, copyright and database right 2022.","countries":{}}
    cache=Path("artifacts/postal-downloads");cache.mkdir(parents=True,exist_ok=True)
    for code,name in COUNTRIES.items():
        filename=f"{code}_full.csv.zip" if code in {"GB","CA"} else f"{code}.zip"
        url=result["source_url"]+filename;path=cache/filename
        if not path.exists():
            with urllib.request.urlopen(url,timeout=90) as response:
                raw=response.read(40*1024**2+1)
            if len(raw)>40*1024**2:raise ValueError("Postal archive exceeds 40 MB")
            path.write_bytes(raw)
        raw=path.read_bytes();groups={};count=0;rng=random.Random(f"postal-subset-v1:{code}")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members=[n for n in archive.namelist() if n.lower().startswith(code.lower()) and n.lower().endswith(('.txt','.csv'))]
            if len(members)!=1:raise ValueError(f"Ambiguous country archive: {members}")
            with archive.open(members[0]) as source:
                for row in csv.reader(io.TextIOWrapper(source,encoding='utf-8-sig'),delimiter='\t'):
                    if len(row)<5 or row[0]!=code:continue
                    postal,city,state,state_code=(row[i].strip() for i in (1,2,3,4))
                    if not postal or not city or not state or not city[0].isalpha():continue
                    if re.search(r'\b(?:GmbH|Corporation|Ltd|Limited|University|Hospital|Company|Inc)\b',city,re.I):continue
                    if code=='GB' and ' ' not in postal:continue
                    if code=='CA' and len(postal.replace(' ',''))!=6:continue
                    record={"city":city,"state":state,"state_code":state_code,"postal_code":postal}
                    group=groups.setdefault(state,[]);count+=1
                    # Keep a small reservoir for every subdivision before the
                    # final round-robin selection, instead of selecting only cities.
                    if len(group)<limit:group.append(record)
                    else:
                        index=rng.randrange(count)
                        if index<limit:group[index]=record
        selected=[];states=sorted(groups)
        for state in states:rng.shuffle(groups[state])
        while len(selected)<limit and any(groups.values()):
            for state in states:
                if groups[state] and len(selected)<limit:selected.append(groups[state].pop())
        if not selected:raise ValueError(f"No full postal references found for {code}")
        selected=sorted({json.dumps(row,sort_keys=True,ensure_ascii=False) for row in selected})
        result['countries'][code]={"name":name,"source_url":url,"archive_sha256":hashlib.sha256(raw).hexdigest(),"records":[json.loads(row) for row in selected]}
        print(code,len(selected),flush=True)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=256)
    parser.add_argument('--output',type=Path,default=Path('backend/app/reference_data/postal.json'))
    args=parser.parse_args();build(args.output,args.limit)
