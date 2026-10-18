"""Fictional, seeded text synthesis and deterministic entity/answer construction."""
import hashlib
import json
import random
import re
import string
from faker import Faker
from .text_schemas import TextConfig, DRAFT_TYPES, Entity, Message

LANGUAGES = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "hi": "Hindi"}
LOCALES = {"en": "en_US", "es": "es_ES", "fr": "fr_FR", "de": "de_DE", "hi": "hi_IN"}
# Authored templates give an explicitly limited, auditable offline baseline.
TEXT = {
 "en": {
  "positive": ["The service was excellent and I am delighted.", "Everything worked well; I would recommend this service.", "The helpful team made this a wonderful experience."],
  "negative": ["The service was disappointing and I am unhappy.", "Nothing worked as expected; I cannot recommend this service.", "The long delay made this a frustrating experience."],
  "neutral": ["The service request was received on Tuesday.", "The team recorded the request in the system.", "The service desk opens at nine."],
  "record": "Fictional case {code}.", "ner": "[[PERSON]] works at [[ORG]] in [[LOCATION]].",
  "context": "Fictional project {code} earned {answer}.", "unit": "points", "question": "How many points did the project earn?",
  "instruction": "Return only this fictional reference code: {code}", "user": "What is the reference for my fictional case?",
  "assistant": "Your fictional reference is {code}.", "thanks": "Thank you.", "welcome": "You are welcome."},
 "es": {
  "positive": ["El servicio fue excelente y estoy muy satisfecho.", "Todo funcionó bien; recomiendo este servicio.", "El equipo amable hizo que la experiencia fuera maravillosa."],
  "negative": ["El servicio fue decepcionante y estoy descontento.", "Nada funcionó como esperaba; no recomiendo este servicio.", "La larga espera fue muy frustrante."],
  "neutral": ["La solicitud se recibió el martes.", "El equipo registró la solicitud en el sistema.", "La oficina abre a las nueve."],
  "record": "Caso ficticio {code}.", "ner": "[[PERSON]] trabaja en [[ORG]] en [[LOCATION]].",
  "context": "El proyecto ficticio {code} obtuvo {answer}.", "unit": "puntos", "question": "¿Cuántos puntos obtuvo el proyecto?",
  "instruction": "Devuelve solo este código de referencia ficticio: {code}", "user": "¿Cuál es la referencia de mi caso ficticio?",
  "assistant": "Su referencia ficticia es {code}.", "thanks": "Gracias.", "welcome": "De nada."},
 "fr": {
  "positive": ["Le service était excellent et je suis ravi.", "Tout a bien fonctionné ; je recommande ce service.", "L'équipe attentionnée a rendu cette expérience formidable."],
  "negative": ["Le service était décevant et je suis mécontent.", "Rien n'a fonctionné comme prévu ; je ne recommande pas ce service.", "La longue attente a été très frustrante."],
  "neutral": ["La demande a été reçue mardi.", "L'équipe a enregistré la demande dans le système.", "Le bureau ouvre à neuf heures."],
  "record": "Dossier fictif {code}.", "ner": "[[PERSON]] travaille chez [[ORG]] à [[LOCATION]].",
  "context": "Le projet fictif {code} a obtenu {answer}.", "unit": "points", "question": "Combien de points le projet a-t-il obtenus ?",
  "instruction": "Renvoyez uniquement ce code de référence fictif : {code}", "user": "Quelle est la référence de mon dossier fictif ?",
  "assistant": "Votre référence fictive est {code}.", "thanks": "Merci.", "welcome": "Je vous en prie."},
 "de": {
  "positive": ["Der Service war ausgezeichnet und ich bin begeistert.", "Alles hat gut funktioniert; ich empfehle diesen Service.", "Das hilfsbereite Team sorgte für eine wunderbare Erfahrung."],
  "negative": ["Der Service war enttäuschend und ich bin unzufrieden.", "Nichts funktionierte wie erwartet; ich empfehle diesen Service nicht.", "Die lange Wartezeit war sehr frustrierend."],
  "neutral": ["Die Anfrage ging am Dienstag ein.", "Das Team hat die Anfrage im System erfasst.", "Das Büro öffnet um neun Uhr."],
  "record": "Fiktiver Fall {code}.", "ner": "[[PERSON]] arbeitet bei [[ORG]] in [[LOCATION]].",
  "context": "Das fiktive Projekt {code} erhielt {answer}.", "unit": "Punkte", "question": "Wie viele Punkte erhielt das Projekt?",
  "instruction": "Geben Sie nur diesen fiktiven Referenzcode zurück: {code}", "user": "Wie lautet die Referenz für meinen fiktiven Fall?",
  "assistant": "Ihre fiktive Referenz lautet {code}.", "thanks": "Danke.", "welcome": "Gern geschehen."},
 "hi": {
  "positive": ["सेवा उत्कृष्ट थी और मैं बहुत खुश हूँ।", "सब कुछ अच्छी तरह चला; मैं इस सेवा की सिफारिश करता हूँ।", "सहायक टीम ने अनुभव को शानदार बना दिया।"],
  "negative": ["सेवा निराशाजनक थी और मैं असंतुष्ट हूँ।", "कुछ भी उम्मीद के अनुसार नहीं चला; मैं इस सेवा की सिफारिश नहीं करता हूँ।", "लंबा इंतज़ार बहुत निराशाजनक था।"],
  "neutral": ["अनुरोध मंगलवार को प्राप्त हुआ।", "टीम ने अनुरोध प्रणाली में दर्ज किया।", "कार्यालय नौ बजे खुलता है।"],
  "record": "काल्पनिक मामला {code}।", "ner": "[[PERSON]], [[LOCATION]] में [[ORG]] के लिए काम करते हैं।",
  "context": "काल्पनिक परियोजना {code} को {answer} मिले।", "unit": "अंक", "question": "परियोजना को कितने अंक मिले?",
  "instruction": "केवल यह काल्पनिक संदर्भ कोड लौटाएँ: {code}", "user": "मेरे काल्पनिक मामले का संदर्भ क्या है?",
  "assistant": "आपका काल्पनिक संदर्भ {code} है।", "thanks": "धन्यवाद।", "welcome": "आपका स्वागत है।"},
}


def plan_record(config: TextConfig, index: int) -> dict:
    # Cross product prevents a class from being permanently tied to a language.
    language = config.languages[(index // len(config.labels) if config.task == "classification" else index) % len(config.languages)]
    plan = {"index": index, "language": language, "language_name": LANGUAGES[language]}
    if config.task == "classification":
        plan["label"] = config.labels[index % len(config.labels)]
    if config.task == "qa":
        rng=random.Random(config.seed+index*1009)
        bank=config.qa_answer_bank.get(language)
        plan["answer"] = rng.choice(bank) if bank else f"{rng.randint(10,999)} {TEXT[language]['unit']}"
        plan["answer_hint"] = config.qa_answer_hint
    if config.task == "augmentation":
        sources = [(i,s) for i,s in enumerate(config.source_texts) if s.language == language]
        source_id,source = sources[(index // len(config.languages)) % len(sources)]
        plan.update(source_id=source_id, source=source.text, label=source.label)
    return plan


def procedural(config: TextConfig, plan: dict, seed: int) -> dict:
    rng = random.Random(seed)
    code = "SYN-" + "".join(rng.choices(string.ascii_uppercase, k=10))
    lang = plan["language"]; text = TEXT[lang]
    if config.task == "classification":
        custom = config.class_templates.get(plan["label"], {}).get(lang)
        phrase = custom if custom else rng.choice(text[plan["label"]])
        return {"text": phrase.replace("{record}",code) + " " + text["record"].format(code=code)}
    if config.task == "ner":
        return {"template": text["ner"] + " " + text["record"].format(code=code)}
    if config.task == "qa":
        if config.qa_answer_bank:
            custom={"en":("Fictional record {code} states: [[ANSWER]]", "What does the fictional record state?"),
                    "es":("El registro ficticio {code} indica: [[ANSWER]]", "¿Qué indica el registro ficticio?"),
                    "fr":("Le dossier fictif {code} indique : [[ANSWER]]", "Que dit le dossier fictif ?"),
                    "de":("Im fiktiven Datensatz {code} steht: [[ANSWER]]", "Was steht im fiktiven Datensatz?"),
                    "hi":("काल्पनिक रिकॉर्ड {code} बताता है: [[ANSWER]]", "काल्पनिक रिकॉर्ड क्या बताता है?")}
            context,question=custom[lang]
            return {"context_template":context.format(code=code),"question":question}
        return {"context_template": text["context"].format(code=code,answer="[[ANSWER]]"), "question": text["question"]}
    if config.task == "instruction":
        return {"instruction": text["instruction"].format(code=code), "response": code}
    if config.task == "conversation":
        return {"messages": [{"role":"user","content": text["user"]},
            {"role":"assistant","content": text["assistant"].format(code=code)},
            {"role":"user","content": text["thanks"]}, {"role":"assistant","content":text["welcome"]}]}
    source = plan["source"]
    operation = rng.choice(config.augmentations)
    if operation == "whitespace":
        words = source.split()
        augmented = "".join(word + (" "*rng.randint(1,5) if i<len(words)-1 else "") for i,word in enumerate(words))
    elif operation == "punctuation":
        augmented = source.rstrip(".!?। ") + rng.choice(["!",".","…","!!","।"])
    else:
        positions = [i for i,c in enumerate(source[:-1]) if c.isascii() and c.isalpha() and source[i+1].isascii() and source[i+1].isalpha() and c!=source[i+1]]
        if not positions:
            raise ValueError("No eligible Latin-letter typo position; choose whitespace or punctuation for this source")
        i = rng.choice(positions)
        augmented = source[:i]+source[i+1]+source[i]+source[i+2:]
    return {"text": augmented, "operation": operation}


def ner_text(template: str, language: str, seed: int) -> tuple[str,list[dict]]:
    markers = re.findall(r"\[\[([A-Z_]+)\]\]",template)
    if sorted(markers) != ["LOCATION","ORG","PERSON"]:
        raise ValueError("NER template needs exactly one PERSON, ORG and LOCATION marker")
    fake = Faker(LOCALES[language]); fake.seed_instance(seed)
    tag = "".join(random.Random(seed).choices(string.ascii_uppercase,k=8))
    values = {"PERSON": fake.name(), "ORG": f"Northstar Fictional {tag}", "LOCATION": f"Test City {tag}"}
    pieces: list[str] = []; entities=[]; cursor=0; length=0
    for match in re.finditer(r"\[\[([A-Z_]+)\]\]",template):
        prefix=template[cursor:match.start()]; pieces.append(prefix); length+=len(prefix)
        value=values[match[1]]
        entities.append(Entity(label=match[1],start=length,end=length+len(value),text=value).model_dump())
        pieces.append(value); length+=len(value); cursor=match.end()
    pieces.append(template[cursor:])
    return "".join(pieces),entities


def bio_tokens(text: str, entities: list[dict]) -> list[dict]:
    tokens=[]; seen=set()
    for match in re.finditer(r"\w+|[^\w\s]",text, re.UNICODE):
        entity=next((e for e in entities if e["start"]<=match.start() and match.end()<=e["end"]),None)
        tag="O"
        if entity:
            key=entity["start"]
            tag=("I-" if key in seen else "B-")+entity["label"]; seen.add(key)
        tokens.append({"text":match[0],"start":match.start(),"end":match.end(),"tag":tag})
    return tokens


def assemble(config: TextConfig, plan: dict, draft: dict, seed: int) -> dict:
    # Procedural augmentation carries operation separately; never accept arbitrary model keys.
    operation=draft.get("operation", "llm_paraphrase")
    checked=DRAFT_TYPES[config.task].model_validate({k:v for k,v in draft.items() if k!="operation"}).model_dump()
    row={"id":f"text-{config.seed}-{plan['index']:06d}","index":plan["index"],"task":config.task,
         "language":plan["language"],"seed":seed,**checked,
         "provenance":{"engine":config.backend,"labels":"conditioned-model" if config.backend=="ollama" else "authored-template",
                       "semantic_accuracy_verified":False}}
    if config.task=="classification":
        row["label"]=plan["label"]
    elif config.task=="ner":
        row.pop("template")
        row["text"],row["entities"]=ner_text(checked["template"],plan["language"],seed)
        row["tokens"]=bio_tokens(row["text"],row["entities"])
        row["provenance"]["labels"]="entity-first-character-offsets"
    elif config.task=="qa":
        template=row.pop("context_template")
        if template.count("[[ANSWER]]")!=1:
            raise ValueError("Q&A context needs exactly one ANSWER marker")
        row["context"]=template.replace("[[ANSWER]]",plan["answer"])
        row["answer"]=plan["answer"]
        if row["context"].count(row["answer"])!=1:
            raise ValueError("Q&A answer must appear exactly once in context")
        row["answer_start"]=row["context"].index(row["answer"])
        row["provenance"]["labels"]="constructed-extractive-answer"
    elif config.task=="augmentation":
        if row["text"]==plan["source"]:
            raise ValueError("Augmentation returned unchanged source text")
        row.update(source_id=plan["source_id"],source_sha256=hashlib.sha256(plan["source"].encode()).hexdigest(),
                   label=plan["label"],augmentation=operation)
        row["provenance"]["labels"]="inherited-source-label-review-required"
    return row


def content_hash(row: dict) -> str:
    # Ignore IDs, seeds and labels so relabelled duplicate content is also detected.
    content={k:v for k,v in row.items() if k in {"text","context","question","answer","instruction","response","messages"}}
    return hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def validate_record(row: dict, config: TextConfig) -> dict:
    errors=[]
    if row.get("language") not in config.languages: errors.append("unexpected_language")
    task=config.task
    if row.get("task")!=task: errors.append("unexpected_task")
    if task=="classification" and row.get("label") not in config.labels: errors.append("invalid_class_label")
    if task=="ner":
        text=row["text"]; end=0
        for entity in row["entities"]:
            if not 0<=entity["start"]<entity["end"]<=len(text) or entity["start"]<end or text[entity["start"]:entity["end"]]!=entity["text"]:
                errors.append("invalid_entity_span")
            end=entity["end"]
        if sorted(e["label"] for e in row["entities"])!=["LOCATION","ORG","PERSON"]: errors.append("missing_entity_class")
        if row["tokens"]!=bio_tokens(text,row["entities"]): errors.append("invalid_bio_tokens")
        for token in row["tokens"]:
            for entity in row["entities"]:
                overlaps=token["start"]<entity["end"] and entity["start"]<token["end"]
                if overlaps and not entity["start"]<=token["start"]<token["end"]<=entity["end"]:
                    errors.append("entity_token_boundary")
    if task=="qa":
        start=row["answer_start"]
        if start<0 or row["context"][start:start+len(row["answer"])]!=row["answer"]: errors.append("invalid_answer_span")
    if task=="conversation":
        messages=[Message.model_validate(m) for m in row["messages"]]
        if len(messages)%2 or any(m.role!=("user" if i%2==0 else "assistant") for i,m in enumerate(messages)):
            errors.append("invalid_conversation_roles")
    # Advisory detection catches common contact/credential patterns; never claims full PII coverage.
    content=json.dumps({k:v for k,v in row.items() if k not in {"provenance","validation"}},ensure_ascii=False)
    if re.search(r"[\w.+-]+@(?!example\.(?:invalid|com)\b)[\w.-]+\.[A-Za-z]{2,}|\b(?:sk-[a-zA-Z0-9]{16,}|\d{3}-\d{2}-\d{4})\b",content):
        errors.append("suspected_sensitive_pattern")
    warnings=["Semantic correctness, actual language, label meaning and privacy require human review", "Synthetic data utility and bias are not evaluated"]
    if task=="augmentation": warnings.append("Source labels are copied; paraphrase/noise can change meaning")
    task_checks={"classification":["label_membership"],"ner":["entity_offsets_and_bio"],"qa":["answer_offsets"],
                 "instruction":["nonempty_instruction_response"],"conversation":["conversation_roles"],"augmentation":["source_lineage"]}
    return {"passed":not errors,"errors":errors,"warnings":warnings,"training_ready":False,
            "checked":["task_schema","language_allowlist","duplicate_content","sensitive_patterns"]+task_checks[task],
            "not_checked":["semantic_correctness","language_identification","complete_pii_detection","statistical_utility"]}
