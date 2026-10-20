"""Offline synthetic streets joined to attributed postal-reference rows."""
import hashlib
import json
import random
import re
from functools import lru_cache
from pathlib import Path
from string import Formatter

COUNTRIES={"IN":"India","US":"United States","GB":"United Kingdom","CA":"Canada",
           "AU":"Australia","DE":"Germany","FR":"France","NZ":"New Zealand",
           "ES":"Spain","IT":"Italy","MY":"Malaysia","PK":"Pakistan"}
ALIASES={"indian":"IN","american":"US","usa":"US","united states of america":"US",
         "uk":"GB","british":"GB","great britain":"GB","canadian":"CA","australian":"AU",
         "german":"DE","french":"FR","new zealand":"NZ","spanish":"ES","italian":"IT",
         "malaysian":"MY","pakistani":"PK"}
FIELDS={"street","city","state","country","postal_code","street_name","house_number","state_code","country_code"}
DEFAULT_FORMAT="{street}, {city}, {state}, {country}, {postal_code}"
REFERENCE=Path(__file__).with_name('reference_data')/'postal.json'
COMPONENT_ALIASES={"pin":"postal_code","pin code":"postal_code","pincode":"postal_code","pin_code":"postal_code",
                   "postal code":"postal_code","postcode":"postal_code","postal_code":"postal_code",
                   "zip":"postal_code","zip code":"postal_code","zip_code":"postal_code","province":"state",
                   **{key:key for key in FIELDS}}


def normalize_country(value):
    value=value.strip()
    if not value:return ""
    if value.upper() in COUNTRIES:return value.upper()
    names={name.lower():code for code,name in COUNTRIES.items()}
    result={**names,**ALIASES}.get(value.lower())
    if not result:raise ValueError("Unsupported address country; choose one of: "+", ".join(COUNTRIES))
    return result


def validate_format(value):
    fields=[]
    try:
        for literal,key,spec,conversion in Formatter().parse(value):
            if key is None:continue
            if key not in FIELDS or spec or conversion:raise ValueError("Unsupported address component")
            fields.append(key)
    except ValueError as exc:
        raise ValueError("Address format supports simple placeholders: "+", ".join('{'+k+'}' for k in sorted(FIELDS))) from exc
    if not fields:raise ValueError("Address format needs at least one component placeholder")
    return value


@lru_cache(maxsize=1)
def reference():
    raw=REFERENCE.read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def country_catalog():
    data,_=reference()
    return [{"code":code,"name":name,"reference_rows":len(data['countries'][code]['records'])}
            for code,name in COUNTRIES.items()]


def generate_address(options,seed):
    code=normalize_country(options.address_country)
    if not code:raise ValueError("Choose an address country before generating a country-specific address")
    data,version=reference()
    rng=random.Random(f"address-v1:{seed}:{code}")
    row=rng.choice(data['countries'][code]['records'])
    number=str(rng.randrange(1,99999))
    root=rng.choice(('Sample','Fictional','Example','Demo','Test'))
    names={"IN":f"{root} Nagar Road","US":f"{root} Avenue","GB":f"{root} Lane",
           "CA":f"{root} Street","AU":f"{root} Road","NZ":f"{root} Terrace",
           "DE":"Musterweg","FR":"rue Exemple","ES":"Calle Ejemplo",
           "IT":"Via Esempio","MY":"Jalan Contoh","PK":f"{root} Road"}
    street_name=names[code]
    street=f"{street_name} {number}" if code in {'DE','ES','IT'} else f"{number} {street_name}"
    parts={**row,"street":street,"street_name":street_name,"house_number":number,
           "country":COUNTRIES[code],"country_code":code}
    value=options.address_format.format_map(parts)
    return {"text":value,"components":parts,"country_code":code,"format":options.address_format,
            "source":"GeoNames postal-reference subset","source_url":data['source_url'],
            "country_source_url":data['countries'][code]['source_url'],"reference_sha256":version,
            "license":"CC BY 4.0","license_url":data['license_url'],"synthetic_street":True,
            "deliverability_verified":False}


def address_request(kind,prompt):
    return kind=="address" or bool(re.search(r"\baddress(?:es)?\b|\bstreet\b.*\b(?:city|state|country)\b",prompt,re.I))


def parse_address_prompt(prompt,current_country="",current_format=DEFAULT_FORMAT):
    """Recognize common country/component requests without model inference.

    None leaves a more complex instruction to the constrained local planner.
    """
    country=current_country
    ignored={"order","each","every","the","a","an","one","single","separate","multiple","following","same","this","that","requested","desired","given","new","synthetic","fictional","random","generate","generated","populate","different","postal","mailing","sample","full","complete","formatted","create","country","aware","specific","fake","test","valid"}
    for candidate in re.findall(r'\b(?:from|in|for)\s+(?:the\s+)?([A-Za-z]+(?:\s+[A-Za-z]+){0,3}?)(?=\s+(?:address|with|using|containing|include|format)\b|[,.;]|$)',prompt,re.I):
        candidate=re.sub(r'^country\s+','',candidate,flags=re.I)
        aliases=[*COUNTRIES,*COUNTRIES.values(),*ALIASES]
        recognized=any(re.match(re.escape(alias)+r'\b',candidate,re.I) for alias in aliases)
        if not recognized and candidate.lower().split()[0] not in ignored:normalize_country(candidate)
    for candidate in re.findall(r'\b([A-Za-z]+)\s+address\b',prompt,re.I):
        if candidate.lower() not in ignored:normalize_country(candidate)
    matches=set()
    for alias,code in {**{name.lower():code for code,name in COUNTRIES.items()},**ALIASES}.items():
        if re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',prompt,re.I):matches.add(code)
    for code in (*COUNTRIES,'UK','USA'):
        if code=='IN':
            found=re.search(r'\bcountry\s*[:=]\s*IN\b|\b(?:from|for) IN\b|\bIN address\b',prompt)
        else:found=re.search(r'(?<!\w)'+code+r'(?!\w)',prompt)
        if found:matches.add(normalize_country(code))
    if len(matches)>1:raise ValueError("Choose one country per address field")
    if matches:country=matches.pop()
    if not country:return None
    # Preserve explicit punctuation and line breaks in an address template.
    placeholder=re.search(r'\{(?:'+ '|'.join(re.escape(k) for k in COMPONENT_ALIASES)+r')\}',prompt,re.I)
    if placeholder:
        start=prompt.find('{');end=prompt.rfind('}')+1
        template=prompt[start:end]
        explicit=re.search(r'\b(?:format|template)\s*:\s*',prompt,re.I)
        if explicit:template=prompt[explicit.end():end].strip(' \t\r\n\"`')
        template=template.replace('\\n','\n')
        template=re.sub(r'\{([^{}]+)\}',lambda m:'{'+COMPONENT_ALIASES.get(m[1].lower(),m[1])+'}',template)
        validate_format(template)
        return country,template
    # Restrict recognition to a straightforward generation request. Filters,
    # translations and other constraints must not be silently dropped.
    if re.search(r'\b(?:only in|from the state|from state|from the city|from city|translate|language|district|latitude|longitude|real|deliverable|verified)\b',prompt,re.I):return None
    pattern=r'\b(?:postal[ _-]?code|zip[ _-]?code|pin[ _-]?code|pincode|postcode|street_name|house_number|state_code|country_code|street|city|state|province|country|zip|pin)\b'
    marker=re.search(r'\b(?:containing|include|including|components|fields|format(?:ted)?(?: as)?)\s*:?\s*',prompt,re.I)
    if marker is None:marker=re.search(r'\bwith\s+',prompt,re.I)
    section=prompt[marker.end():] if marker else prompt
    if not re.search(pattern,section,re.I):section=prompt
    components=[]
    for match in re.finditer(pattern,section,re.I):
        key=COMPONENT_ALIASES.get(match[0].lower().replace('-',' '),match[0].lower())
        if key not in components:components.append(key)
    if components and not (components==['country'] and not re.search(r'\b(?:only|with|include|fields|components)\b',prompt,re.I)):
        separator='\n' if re.search(r'\b(?:each|separate|new|different|multiple|two|three|four|five|six|seven|eight|nine|[2-9])\s+lines?\b|\bmultiline\b|line\s*break',prompt,re.I) else ', '
        if re.search(r'\bsingle\s+line\b|\bone\s+line\b',prompt,re.I):separator=', '
        if re.search(r'\bpipe[- ]separated\b',prompt,re.I):separator=' | '
        return country,separator.join('{'+key+'}' for key in components)
    return country,current_format
