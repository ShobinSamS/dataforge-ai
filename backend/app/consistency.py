"""Explicit field dependencies. Acyclic, formatted values with no model guessing."""
from datetime import datetime,date,timedelta
from decimal import Decimal,InvalidOperation

FORMATS={'yyyy-mm-dd':'%Y-%m-%d','dd/mm/yyyy':'%d/%m/%Y','mm/dd/yyyy':'%m/%d/%Y','dd-mm-yyyy':'%d-%m-%Y','yyyy/mm/dd':'%Y/%m/%d'}


def validate_links(links,regions):
    fields={r.id:r for r in regions};targets={link.target for link in links}
    if len(targets)!=len(links):raise ValueError('Each relationship target may have only one rule')
    for link in links:
        if link.target not in fields or any(s not in fields for s in link.sources):raise ValueError('Relationship references an unavailable replacement field')
        if link.target in link.sources:raise ValueError('A field cannot depend on itself')
        if link.rule in {'age','after_date'} and len(link.sources)!=1:raise ValueError('Age and date-offset rules require one source field')
        if link.rule=='after_date' and fields[link.target].kind!='date':raise ValueError('Date-offset targets must be date fields')
        if link.rule in {'age','after_date'} and fields[link.sources[0]].kind!='date':raise ValueError('Age and date-offset sources must be date fields')
        if fields[link.target].kind not in {'text','name','address','date','identifier','email','phone','qr','barcode'}:raise ValueError('Relationship targets must hold text or code data')
    pending={link.target:set(link.sources)&targets for link in links}
    while pending:
        ready={k for k,v in pending.items() if not v}
        if not ready:raise ValueError('Field relationships contain a cycle')
        pending={k:v-ready for k,v in pending.items() if k not in ready}


def apply_links(values,links,regions):
    if not links:return values
    validate_links(links,regions);fields={r.id:r for r in regions};remaining=list(links);completed=set(values)-{l.target for l in links}
    def parse(id_):return datetime.strptime(values[id_],FORMATS[fields[id_].rule_options.date_format]).date()
    while remaining:
        for link in remaining[:]:
            if not set(link.sources)<=completed:continue
            if link.rule=='copy':value=link.separator.join(values[s] for s in link.sources)
            elif link.rule=='sum':
                try:value=f'{sum(Decimal(values[s]) for s in link.sources):.2f}'
                except InvalidOperation as exc:raise ValueError('Sum sources must contain plain decimal numbers') from exc
            elif link.rule=='after_date':value=(parse(link.sources[0])+timedelta(days=link.days)).strftime(FORMATS[fields[link.target].rule_options.date_format])
            else:
                born=parse(link.sources[0]);reference=link.as_of
                if born>reference:raise ValueError('Birth date is after the age reference date')
                value=str(reference.year-born.year-((reference.month,reference.day)<(born.month,born.day)))
            values[link.target]=value;completed.add(link.target);remaining.remove(link)
    return values
