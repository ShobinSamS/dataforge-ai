"""Interpret once, validate and review; deterministic tools execute per sample."""
import hashlib
import json
import re
from datetime import date
from typing import Literal
from pydantic import Field
from .schemas import Contract, Region, RuleOptions, FieldType, region_action
from .local_llm import LocalLLM
from .config import settings
from .format_references import format_references
from .patterns import pattern_parts
from .addresses import address_request,parse_address_prompt,COUNTRIES,FIELDS,DEFAULT_FORMAT


class RulePlan(Contract):
    supported: bool = True
    action: Literal["replace","erase","keep"] = "replace"
    kind: FieldType = FieldType.text
    options: RuleOptions = Field(default_factory=RuleOptions)
    explanation: str = Field(default="",max_length=1000)


class InterpretRuleRequest(Contract):
    region: Region
    engine: Literal["auto","local_llm"] = "auto"


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


def known_plan(region: Region) -> RulePlan | None:
    prompt=region.rule.strip(); low=prompt.lower()
    plan=RulePlan(kind=region.kind,action=region_action(region),options=region.rule_options.model_copy(deep=True))
    if not prompt: return plan
    if not low.startswith("literal:"): plan.options.literal_text=None
    if low.startswith("literal:"):
        if not prompt[8:].strip(): raise ValueError("Enter fictional text after literal:")
        plan.options.literal_text=prompt[8:];plan.action="replace";plan.explanation="Render this exact fictional text."
    elif re.fullmatch(r"(?:please\s+)?(?:remove|erase|delete|clear|blank)(?:\s+(?:this|it|region|completely|entirely|only|and|leave|empty|no|replacement|without|replace|nothing|the|area|content))*[.!]?",low):
        plan.action="erase";plan.explanation="Erase the original region. Render no replacement and emit no object label."
    elif low in {"keep","preserve","leave unchanged"}:
        plan.action="keep";plan.explanation="Preserve the original pixels; sensitive regions cannot be kept."
    elif any(word in low for word in ("photo","portrait","human image","human face","person image")):
        plan.kind=FieldType.portrait;plan.action="replace"
        plan.explanation="Insert a fictional offline portrait illustration, or select an approved photo pool. No web request is made by interpreting this prompt."
    elif address_request(region.kind,prompt):
        parsed=parse_address_prompt(prompt,region.rule_options.address_country,region.rule_options.address_format)
        if parsed is None:return None
        plan.kind=FieldType.address;plan.action="replace"
        plan.options.address_country,plan.options.address_format=parsed
        plan.options.identifier_pattern="";plan.options.character_length=None
        plan.explanation=f"Generate a fresh synthetic {COUNTRIES[parsed[0]]} address per sample, using the displayed component format and bundled postal-reference rows. Street and house number are synthetic; deliverability is not verified."
    elif re.fullmatch(r"(?:please\s+)?(?:pan(?:\s*card)?|permanent\s+account\s+number)(?:\s+(?:number|pattern|format))*",prompt,re.I) or re.fullmatch(r"[A9X-]{2,128}",prompt) or ("{" in prompt and not re.search(r"\s",prompt) and _valid_template(prompt)):
        plan.kind=region.kind if region.kind in {"qr","barcode"} else FieldType.identifier;plan.action="replace"
        plan.options.identifier_pattern="AAAAA9999A" if format_references(prompt) else prompt
        plan.options.character_length=None
        plan.explanation="Generate random values using the displayed pattern, with no added prefix."
    elif any(fmt in low for fmt in ("dd/mm/yyyy","mm/dd/yyyy","dd-mm-yyyy","yyyy-mm-dd","yyyy/mm/dd")) or re.search(r"\b(?:dob|date of birth|birth date)\b",low):
        plan.kind=FieldType.date;plan.action="replace"
        fmt=next((f for f in ("dd/mm/yyyy","mm/dd/yyyy","dd-mm-yyyy","yyyy-mm-dd","yyyy/mm/dd") if f in low),None)
        if fmt: plan.options.date_format=fmt
        if re.search(r"\b(?:dob|date of birth|birth date)\b",low):
            plan.options.date_start=date(1970,1,1);plan.options.date_end=date(2006,12,31)
        dates=re.findall(r"\b\d{4}-\d{2}-\d{2}\b",prompt)
        if len(dates)==2:
            plan.options.date_start=date.fromisoformat(dates[0]);plan.options.date_end=date.fromisoformat(dates[1])
        elif len(dates)>0: return None  # Ambiguous bounds need explicit controls or local interpretation.
        years=re.search(r"(?:between|from)\s+(19\d{2}|20\d{2})\s+(?:and|to|-)\s+(19\d{2}|20\d{2})",low)
        if years:
            plan.options.date_start=date(int(years[1]),1,1);plan.options.date_end=date(int(years[2]),12,31)
        plan.explanation="Generate a fictional date inside the displayed bounds using the selected date format."
    else:
        return None
    # Do not pretend a partial match interpreted additional unrelated instructions.
    if re.search(r"\b(?:upload|scrape|internet|download|web)\b",low):
        plan.explanation+=" Online portraits require a separate explicit fetch from a configured provider, or upload your own images."
    return RulePlan.model_validate(plan.model_dump())


def _valid_template(value: str) -> bool:
    try:
        pattern_parts(value)
        return True
    except ValueError:
        return False


def apply_plan(region: Region, plan: RulePlan, preserve_confirmation: bool = False) -> Region:
    if not plan.supported: raise ValueError(plan.explanation or "This prompt cannot be executed by the available tools")
    options=plan.options.model_copy(deep=True)
    # A model cannot invent asset IDs or select files; only the user's current approved pool is retained.
    options.portrait_asset_ids=region.rule_options.portrait_asset_ids[:]
    if plan.kind=="stamp": options.portrait_source=region.rule_options.portrait_source
    # Typography is selected from the local source/UI, never invented by a model.
    for key in ("font_id","font_size","text_color","color_mode","color_palette","font_weight","background_mode","background_color","cleanup_mode","writing_style","code_background","signature_style","signature_content","signature_thickness",*(key for key in RuleOptions.model_fields if key.startswith(("seal_","stamp_","rubber_stamp_","ink_","drawing_","portrait_background")))):
        setattr(options,key,getattr(region.rule_options,key))
    if plan.kind not in {"text","identifier","qr","barcode"}:
        options.identifier_pattern="";options.character_length=None
    if plan.action=="replace" and plan.kind=="portrait" and options.portrait_source=="asset_pool" and not options.portrait_asset_ids:
        raise ValueError("Select/upload portrait assets before choosing the photo pool")
    return Region.model_validate({**region.model_dump(),"kind":plan.kind,"action":plan.action,
        "replace":plan.action!="keep","rule_options":options.model_dump(),
        "rule_resolved_hash":prompt_hash(region.rule),"confirmed":region.confirmed if preserve_confirmation else False})


def normalize_regions(regions: list[Region], strict: bool) -> list[Region]:
    normalized=[]
    for region in regions:
        if region.rule.strip() and region.rule_resolved_hash!=prompt_hash(region.rule):
            plan=known_plan(region)
            if plan: region=apply_plan(region,plan,preserve_confirmation=True)
            elif strict: raise ValueError(f"Interpret the prompt for region {region.id} using Apply rule / local Qwen before confirming review")
        normalized.append(region)
    return normalized


def _model_plan(payload: dict, properties: dict, region: Region, pattern_request: bool) -> RulePlan:
    if isinstance(payload,dict) and isinstance(payload.get("options"),dict):
        for key in RuleOptions.model_fields:
            if key not in properties: payload["options"].pop(key,None)
    plan=RulePlan.model_validate(payload)
    if plan.supported and plan.action=="replace" and not region.rule.lower().startswith("literal:") and address_request(region.kind,region.rule):
        if plan.kind!="address" or not plan.options.address_country or plan.options.literal_text is not None:
            raise ValueError("Address generation needs kind=address, a supported country, and a component format, never a literal sample")
        expected=parse_address_prompt(region.rule,region.rule_options.address_country,region.rule_options.address_format)
        if expected and (plan.options.address_country,plan.options.address_format)!=expected:
            raise ValueError("Address country, components, order and line breaks must match the requested address rule")
    defaults=RuleOptions()
    if plan.supported and plan.action=="replace" and plan.options.literal_text is None:
        if plan.kind!="date" and not plan.options.identifier_pattern and any(getattr(plan.options,key)!=getattr(defaults,key) for key in ("date_format","date_start","date_end")):
            raise ValueError("Date options require a date field; select the date type and retry")
        if plan.options.identifier_pattern and plan.kind not in {"identifier","text","qr","barcode"}:
            raise ValueError("Character patterns require a text, identifier, QR or barcode field")
        if plan.options.portrait_source=="asset_pool" and plan.kind not in {"portrait","stamp"}:
            raise ValueError("Portrait source requires a portrait field")
        if pattern_request:
            if not plan.options.identifier_pattern: raise ValueError("A custom format requires a nonempty pattern")
            for kind,literal in pattern_parts(plan.options.identifier_pattern):
                if kind!="literal": continue
                for word in re.findall(r"[A-Za-z0-9]+",str(literal)):
                    if word.lower() not in region.rule.lower(): raise ValueError(f"Unrequested literal prefix/suffix {word!r}; only include literals explicitly given in the instruction")
                for separator,words in {"-":r"hyphen|dash|separator","_":r"underscore|separator","/":r"slash|separator"}.items():
                    if separator in str(literal) and separator not in region.rule and not re.search(words,region.rule,re.I):
                        raise ValueError("Unrequested separator; adjacent character groups must have no punctuation unless requested")
    return plan


def interpret_local(region: Region) -> RulePlan:
    llm=LocalLLM()
    try:
        if not llm.status()["installed"]: raise RuntimeError("Local Qwen unavailable; use explicit controls or supported shorthand rules")
        schema=RulePlan.model_json_schema()
        schema["required"]=["supported","action","kind","options","explanation"]
        for name in ("kind","action"):
            schema["properties"][name].pop("default",None)
        # Give Qwen only options owned by the semantic tool; fonts/assets stay local.
        properties=schema["$defs"]["RuleOptions"]["properties"]
        for key in ("portrait_asset_ids","font_id","font_size","text_color","color_mode","color_palette","font_weight","background_mode","background_color"): properties.pop(key,None)
        # Rendering controls are retained from the UI in apply_plan. Keep them
        # out of the small local model's context as more asset types are added.
        for key in list(properties):
            if key.startswith(("seal_","stamp_","rubber_stamp_","ink_","drawing_","portrait_background")) or key in {"signature_thickness","signature_content"}: properties.pop(key)
        address_mode=address_request(region.kind,region.rule) and not region.rule.lower().startswith("literal:")
        date_request=not address_mode and bool(re.search(r"\b(?:date|dob|birth|birthday)\b|(?:dd|mm|yyyy)[/-](?:dd|mm|yyyy)",region.rule,re.I))
        pattern_request=not address_mode and not date_request and bool(re.search(r"\b(?:pattern|format|sku|serial|identifier|digits?|letters?|alphanumeric|characters?|code|pan|pancard|permanent account number)\b",region.rule,re.I)) and not region.rule.lower().startswith("literal:")
        if re.search(r"\b(?:remove|erase|delete|clear|keep|preserve|photo|portrait)\b",region.rule,re.I): pattern_request=False
        if pattern_request:
            properties={key:properties[key] for key in ("identifier_pattern",)}
            schema["$defs"]["RuleOptions"]["properties"]=properties
            schema["$defs"]["RuleOptions"]["required"]=["identifier_pattern"]
            schema["properties"]["kind"]={"type":"string","const":region.kind.value if region.kind in {"qr","barcode"} else "identifier"}
            schema["properties"]["action"]={"type":"string","const":"replace"}
        if address_mode:
            properties={key:properties[key] for key in ("address_country","address_format")}
            properties['address_country']={'type':'string','enum':list(COUNTRIES)}
            schema['$defs']['RuleOptions']['properties']=properties
            schema['$defs']['RuleOptions']['required']=['address_country','address_format']
            schema['properties']['kind']={'type':'string','const':'address'}
            schema['properties']['action']={'type':'string','const':'replace'}
        context={"instruction":region.rule,"current_type":region.kind.value,"today":date.today().isoformat(),
                         "verified_format_references":format_references(region.rule),"max_output_characters":500 if region.kind=="qr" else 128}
        if address_mode:
            context.update(supported_address_countries=COUNTRIES,address_components=sorted(FIELDS),
                           current_address_country=region.rule_options.address_country,current_address_format=region.rule_options.address_format)
        if pattern_request:
            context["pattern_examples"]=[
                {"instruction":"3 uppercase letters then 6 digits","identifier_pattern":"{upper:3}{digits:6}"},
                {"instruction":"4 lowercase letters followed by 8 digits","identifier_pattern":"{lower:4}{digits:8}"},
                {"instruction":"12 digits","identifier_pattern":"{digits:12}"},
                {"instruction":"8 letters or digits","identifier_pattern":"{alnum:8}"}]
        request={"model":settings.ollama_model,"stream":False,"think":False,"keep_alive":0,
            "format":schema,"options":{"temperature":0,"num_ctx":4096,"num_predict":1200,"num_gpu":0,"num_thread":4},
            "messages":[{"role":"system","content":"Compile one document-field instruction to a supported executable plan. No tools, network, code or paths. Actions: replace, erase, keep. Dates use kind=date, photos kind=portrait, custom codes kind=identifier (preserve qr/barcode kind for payload rules). Compile any supported custom code format with {upper:N}, {lower:N}, {digits:N}, {alnum:N}, {year}, {month}, {day}. Date tokens use one random date within the date bounds; fixed dates use literals. Literal text outside braces is copied ONLY when explicitly requested. Never invent a prefix, suffix or separator. Adjacent groups have no hyphen unless requested. N is 1–500; output must not exceed max_output_characters from input (128 normally, 500 for QR). Legacy A/9/X tokens are also supported. Never return a sample as literal_text for a random pattern. Never add SYN- or unrequested text. Dates use allowed formats and ISO bounds. Unused options retain defaults. Set supported=true for executable requests, false only for unsupported operations or ambiguity. Checksums, externally validated numbers and incrementing sequences are unsupported; do not pretend random digits satisfy those constraints. Never invent fonts or asset IDs."},
                        {"role":"user","content":json.dumps(context)}]}
        if address_mode:
            request['messages'][0]['content']=("Compile a synthetic address instruction to kind=address, action=replace. "
                "Return address_country as one supported ISO country code and address_format as a string of simple component placeholders, "
                "such as {street}, {city}, {state}, {country}, {postal_code}. Preserve the requested component order, separators and line breaks. "
                "PIN, ZIP and postcode mean {postal_code}. Each component on a separate line means newline separators. "
                "Use the current country/format when the instruction does not change them. Never return an example address as literal_text. "
                "The app generates new streets and samples matching locality/state/postal rows locally; do not invent geographic mappings. "
                "Unsupported countries, city/state filters, real deliverable addresses, language/translation requests or other unimplemented constraints require supported=false. "
                "Do not guess a country if none was supplied or selected. No tools, network, code or paths.")
        for attempt in range(2):
            response=llm.client.post("/api/chat",json=request)
            response.raise_for_status()
            if response.json().get("done_reason")=="length": raise ValueError("Rule interpretation exceeded its token budget; shorten the instruction")
            try:
                return _model_plan(json.loads(response.json()["message"]["content"]),properties,region,pattern_request)
            except ValueError as exc:
                if attempt: raise
                request["messages"].append({"role":"user","content":f"Correct the plan: {str(exc)[:400]}. Use only the original instruction; return valid JSON, no extra literals."})
    finally:
        llm.close()
