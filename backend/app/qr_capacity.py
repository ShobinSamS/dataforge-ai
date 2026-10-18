"""Shared QR encoding and preflight checks; no payload or geometry is silently changed."""
import qrcode
from qrcode.exceptions import DataOverflowError
from .patterns import pattern_parts
from .schemas import GenerationConfig, Region, region_action

PIXELS_PER_MODULE=3


def qr_code(value: str,padding: int):
    code=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=4,border=padding)
    code.add_data(value)
    return code


def required_side(value: str,padding: int) -> int:
    # best_fit calculates encoding capacity without rendering a matrix or image.
    code=qr_code(value,padding)
    version=code.best_fit()
    return (version*4+17+padding*2)*PIXELS_PER_MODULE


def payload_bound(region: Region,config: GenerationConfig) -> tuple[str,str]:
    options=region.rule_options
    if options.literal_text is not None: return options.literal_text,"field literal"
    if region.rule.startswith("literal:"): return region.rule[8:],"field literal"
    if options.identifier_pattern:
        # Use letters for mixed groups so accidental numeric runs cannot make
        # the capacity estimate smaller than generated random strings.
        dates={"year":"2000","month":"12","day":"28"}
        chars={"upper":"Z","lower":"z","alnum":"Z","digits":"7"}
        value="".join(str(value) if kind=="literal" else dates[kind] if kind in dates else chars[kind]*int(value)
            for kind,value in pattern_parts(options.identifier_pattern))
        return value,"field pattern"
    length=options.character_length or config.qr_payload_length
    char={"upper":"Z","lower":"z","alnum":"Z","digits":"7"}[options.character_set]
    return char*length,"field length override" if options.character_length is not None else "generation default"


def maximum_length(side: int,padding: int,charset: str) -> int:
    char={"upper":"Z","lower":"z","alnum":"Z","digits":"7"}[charset]
    low,high=0,500
    while low<high:
        mid=(low+high+1)//2
        if required_side(char*mid,padding)<=side: low=mid
        else: high=mid-1
    return low


def qr_preflight(regions: list[Region],config: GenerationConfig) -> dict:
    reports=[]
    if config.qr_codes:
        for region in regions:
            if region.kind!="qr" or region_action(region)!="replace":continue
            value,source=payload_bound(region,config)
            w,h=region.box[2:]
            required=None;error=""
            try:required=required_side(value,config.qr_padding)
            except DataOverflowError:error="Payload exceeds QR encoding capacity; shorten the literal or pattern."
            fits=required is not None and min(w,h)>=required
            maximum=maximum_length(min(w,h),config.qr_padding,region.rule_options.character_set) if source in {"field length override","generation default"} else None
            if not fits and not error:
                remedy=f" Shorten this field to at most {maximum} {region.rule_options.character_set} characters, or enlarge both dimensions to at least {required} px." if maximum else f" Enlarge both dimensions to at least {required} px or shorten the field pattern/literal."
                error=f"QR region {region.label} is {w}×{h} px. Its {source} uses {len(value)} characters and needs at least {required}×{required} px.{remedy}"
                if source=="field length override":error+=" Changing the generation default does not override this field setting."
            reports.append({"region_id":region.id,"label":region.label,"width":w,"height":h,"payload_characters":len(value),"payload_source":source,
                "required_size":required,"max_automatic_characters":maximum,"fits":fits,"error":error})
    errors=[r["error"] for r in reports if not r["fits"]]
    if config.qr_required and not reports:errors.append("QR is required: add and verify a QR replacement region in this template")
    return {"valid":not errors,"qr_regions":reports,"errors":errors,"pixels_per_module":PIXELS_PER_MODULE}


def check_qr_capacity(regions: list[Region],config: GenerationConfig) -> None:
    report=qr_preflight(regions,config)
    if not report["valid"]:raise ValueError(" ".join(report["errors"]))
