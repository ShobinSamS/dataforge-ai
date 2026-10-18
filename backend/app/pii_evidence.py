"""Precision checks for OCR-grounded PII values, independent of any document layout."""
import re
from datetime import datetime

EMAIL=re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
DATE=re.compile(r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b")
CODE=re.compile(r"(?<!\w)[A-Za-z0-9][A-Za-z0-9./-]{4,}(?!\w)")
ID_CONTEXT=re.compile(r"\b(?:(?:account|document|registration|tax|patient|employee|student|reference|policy|member|national)\s*(?:number|no\.?|id|code|identifier)|passport|licen[cs]e|pan|aadhaar|ssn|iban|identifier)\b",re.I)
PUBLIC_WORDS=set("income tax department government govt india ministry authority card apply online application form invoice receipt certificate reference sample purpose purposes only amount item total qty quantity price unit subtotal discount description currency permanent account number name date incorporation formation birth dob email phone address".split())


def is_public_or_label(text: str) -> bool:
    words=re.findall(r"[^\W\d_]+",text.lower())
    # A label is not a value. This also rejects promotional words under a Name label.
    if not words: return not any(c.isdigit() for c in text)
    return all(word in PUBLIC_WORDS or word in {"e","of","the","and","for","no","id"} for word in words) and not any(c.isdigit() for c in text)


def date_value(text: str) -> str:
    for match in DATE.finditer(text):
        value=match.group()
        for fmt in ("%Y-%m-%d","%Y/%m/%d","%d-%m-%Y","%d/%m/%Y","%m-%d-%Y","%m/%d/%Y"):
            try:
                parsed=datetime.strptime(value,fmt)
                if 1900<=parsed.year<=2100:return value
            except ValueError: pass
    return ""


def checked_value(text: str,category: str,evidence: str,context: str="") -> str:
    """Require a literal source quote plus category-specific evidence, never a heading."""
    value=evidence.strip()
    if not value or value not in text or is_public_or_label(value): return ""
    if category=="email": return value if EMAIL.fullmatch(value) else ""
    if category=="date": return value if date_value(value)==value else ""
    if category=="phone":
        digits=re.sub(r"\D","",value)
        return value if re.fullmatch(r"\+?[\d ()-]+",value) and 8<=len(digits)<=15 and not date_value(value) else ""
    if category in {"identifier","financial"}:
        digits=sum(c.isdigit() for c in value)
        if category=="financial" and re.search(r"(?:amount|price|total|subtotal|tax|currency)\s*[:=]?\s*"+re.escape(value),text,re.I): return ""
        # No "ITEM", "AMOUNT", field headings, currency names or arbitrary prose IDs.
        if digits<2 or not CODE.fullmatch(value): return ""
        return value if any(c.isalpha() for c in value) or (digits>=6 and ID_CONTEXT.search(text+" "+context)) else ""
    if category=="person":
        words=re.findall(r"[^\W\d_]+",value,flags=re.UNICODE)
        if not 2<=len(words)<=6 or any(c.isdigit() for c in value): return ""
        if any(w.lower() in PUBLIC_WORDS for w in words): return ""
        return value
    if category=="address":
        return value if len(value)>=8 and any(c.isalpha() for c in value) and (any(c.isdigit() for c in value) or re.search(r"\b(?:street|road|lane|avenue|residence|address)\b",text+" "+context,re.I)) else ""
    if category=="medical":
        return value if ":" in text and re.search(r"\b(?:patient|diagnosis|condition|blood group|medical record)\b",text+" "+context,re.I) else ""
    # Public organization names and untyped "other" strings are not sufficient
    # evidence of personal data. A user can still draw/label these manually.
    return ""


def rule_values(text: str,context: str="") -> list[tuple]:
    result=[]
    for match in EMAIL.finditer(text):result.append(("email",match.group(),"An email address is present in the OCR text."))
    value=date_value(text)
    if value:result.append(("date",value,"A calendar date is present. Review its document label; this does not by itself establish that it is a birth date."))
    if not value:
        for match in re.finditer(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)",text):
            value=checked_value(text,"phone",match.group(),context)
            if value:result.append(("phone",value,"A phone-shaped contact value is present."))
    if ID_CONTEXT.search(text+" "+context):
        for match in CODE.finditer(text):
            value=checked_value(text,"identifier",match.group(),context)
            if value and not date_value(value):result.append(("identifier",value,"An identifier value appears beside document/account identity context."))
    return result
