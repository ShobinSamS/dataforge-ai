"""Bounded pattern templates, never executable regex or model-written code."""
import random
import re
import string
from datetime import date

SETS = {"upper": string.ascii_uppercase, "lower": string.ascii_lowercase,
        "digits": string.digits, "alnum": string.ascii_uppercase + string.digits}
MAX_LENGTH = 500


def pattern_parts(pattern: str) -> list[tuple[str, str | int]]:
    if not pattern: return []
    if "{" not in pattern and "}" not in pattern:
        if not re.fullmatch(r"[A9X-]+", pattern):
            raise ValueError("Use A/9/X/- tokens, or templates such as INV-{upper:2}-{digits:6}")
        parts=[({"A":"upper", "9":"digits", "X":"alnum"}.get(c,"literal"), c if c=="-" else 1) for c in pattern]
    else:
        parts=[];position=0
        for match in re.finditer(r"\{([^{}]+)\}", pattern):
            literal=pattern[position:match.start()]
            if "{" in literal or "}" in literal: raise ValueError("Unbalanced pattern braces")
            if literal: parts.append(("literal",literal))
            token=match[1]
            if token in {"year","month","day"}: parts.append((token,0))
            else:
                spec=re.fullmatch(r"(upper|lower|digits|alnum):([1-9][0-9]{0,2})",token)
                if not spec or int(spec[2])>MAX_LENGTH: raise ValueError("Unsupported pattern token; use upper/lower/digits/alnum:1–500, year, month or day")
                parts.append((spec[1],int(spec[2])))
            position=match.end()
        tail=pattern[position:]
        if "{" in tail or "}" in tail: raise ValueError("Unbalanced pattern braces")
        if tail: parts.append(("literal",tail))
    length=sum(len(value) if kind=="literal" else 4 if kind=="year" else 2 if kind in {"month","day"} else int(value) for kind,value in parts)
    if not 1<=length<=MAX_LENGTH: raise ValueError("Pattern must produce 1–500 characters")
    return parts


def pattern_length(pattern: str) -> int:
    return sum(len(value) if kind=="literal" else 4 if kind=="year" else 2 if kind in {"month","day"} else int(value) for kind,value in pattern_parts(pattern))


def generate_pattern(pattern: str, seed: int, start: date, end: date) -> str:
    rng=random.Random(f"{seed}:{pattern}")
    selected=date.fromordinal(rng.randint(start.toordinal(),end.toordinal()))
    dates={"year":f"{selected.year:04d}","month":f"{selected.month:02d}","day":f"{selected.day:02d}"}
    return "".join(str(value) if kind=="literal" else dates[kind] if kind in dates else
                   "".join(rng.choice(SETS[kind]) for _ in range(int(value))) for kind,value in pattern_parts(pattern))
