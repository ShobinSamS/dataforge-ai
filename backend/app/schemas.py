"""Public contracts; all coordinates are pixels in the canonical page image."""
from enum import StrEnum
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from .patterns import pattern_parts, pattern_length
from .seals import validate_seal_format,duplicate_words
from .colors import DEFAULT_PALETTE
from .addresses import DEFAULT_FORMAT,normalize_country,validate_format


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldType(StrEnum):
    text = "text"
    name = "name"
    address = "address"
    date = "date"
    email = "email"
    phone = "phone"
    identifier = "identifier"
    signature = "signature"
    seal = "seal"
    qr = "qr"
    barcode = "barcode"
    portrait = "portrait"
    # Append new classes: existing YOLO/COCO class IDs must never move.
    stamp = "stamp"
    rubber_stamp = "rubber_stamp"
    drawing = "drawing"


CLASS_NAMES = [v.value for v in FieldType]
SignatureStyle = Literal["mixed","name","first_name","single_letter","two_letters","initials","letter_wave","monogram","flourish","tall_initial","compact","angular","looped","sweeping","gestural","stacked","initial_bridge","terminal_loop","crossed","minimal","surname","split","enclosed","interwoven"]


class RuleOptions(Contract):
    address_country: str = Field(default="",max_length=100)
    address_format: str = Field(default=DEFAULT_FORMAT,min_length=1,max_length=500)
    date_format: Literal["yyyy-mm-dd","dd/mm/yyyy","mm/dd/yyyy","dd-mm-yyyy","yyyy/mm/dd"] = "yyyy-mm-dd"
    date_start: date = date(2015,1,1)
    date_end: date = date(2025,12,31)
    identifier_pattern: str = Field(default="",max_length=256)
    character_length: int | None = Field(default=None,ge=1,le=500)
    character_set: Literal["alnum","digits","upper","lower"] = "alnum"
    literal_text: str | None = Field(default=None,min_length=1,max_length=1000)
    portrait_source: Literal["illustration","asset_pool"] = "illustration"
    portrait_asset_ids: list[str] = Field(default_factory=list,max_length=20)
    portrait_background: Literal["preserve","transparent","solid","random"] = "preserve"
    portrait_background_color: str = Field(default="#ffffff",pattern=r"^#[0-9a-fA-F]{6}$")
    portrait_background_palette: list[str] = Field(default_factory=lambda:["#ffffff","#d9e8ff","#ddd9ef","#ddebd9"],min_length=1,max_length=20)
    drawing_points: list[tuple[float,float]] = Field(default_factory=list,max_length=4000)
    drawing_width: float = Field(default=3,ge=.5,le=80,allow_inf_nan=False)
    font_id: str = Field(default="auto",max_length=100,pattern=r"^[a-zA-Z0-9_.-]+$")
    font_size: int | None = Field(default=None,ge=6,le=200)
    text_color: str = Field(default="#000000",pattern=r"^#[0-9a-fA-F]{6}$")
    color_mode: Literal["black","auto","manual","random","mixed"] = "black"
    color_palette: list[str] = Field(default_factory=lambda:DEFAULT_PALETTE[:],min_length=1,max_length=20)
    font_weight: Literal["auto","normal","bold"] = "auto"
    background_mode: Literal["auto","solid"] = "auto"
    background_color: str = Field(default="#ffffff",pattern=r"^#[0-9a-fA-F]{6}$")
    cleanup_mode: Literal["full_region","ink_only"] = "full_region"
    writing_style: Literal["printed","cursive"] = "printed"
    code_background: Literal["transparent","white"] = "transparent"
    signature_style: SignatureStyle = "mixed"
    signature_content: Literal["current","name","alphabet","mixed"] = "current"
    signature_thickness: float = Field(default=1,ge=1,le=5,allow_inf_nan=False)
    ink_opacity_mode: Literal["random","fixed"] = "random"
    ink_opacity: float = Field(default=1,ge=.05,le=1,allow_inf_nan=False)
    ink_opacity_min: float = Field(default=.45,ge=.05,le=1,allow_inf_nan=False)
    ink_opacity_max: float = Field(default=1,ge=.05,le=1,allow_inf_nan=False)
    ink_finish: Literal["clean","natural","worn"] = "natural"
    ink_irregularity: float = Field(default=.55,ge=0,le=1,allow_inf_nan=False)
    seal_style: Literal["random","ring","round","double_ring","oval","badge","square","rectangle","professional","form","dated","text","attestation","corporate","form_block","nameplate"] = "random"
    seal_color: Literal["random","red","blue","green","purple","black","brown","mixed"] = "black"
    seal_text_mode: Literal["random","static","custom"] = "random"
    seal_allow_repeated_words: bool = False
    seal_text: str = Field(default="SAMPLE OFFICE",max_length=100)
    seal_subtext: str = Field(default="RECEIVED",max_length=360)
    seal_bottom_text: str = Field(default="",max_length=100)
    seal_top_format: str = Field(default="{organization}",max_length=200)
    seal_bottom_format: str = Field(default="{city} · {state}",max_length=200)
    seal_body_format: str = Field(default="{department}\n{name}\nREF {reference}",max_length=480)
    seal_border: Literal["random","solid","double","dotted","dashed","serrated","rosettes"] = "random"
    seal_symbol: Literal["random","none","star","diamond","rosette","monogram"] = "random"
    seal_wear: float = Field(default=.08,ge=0,le=.45)
    seal_inner_top_text: str = Field(default="",max_length=160)
    seal_inner_bottom_text: str = Field(default="",max_length=160)
    seal_center_motif: Literal["none","shield","rosette","rays"] = "none"
    seal_field_writing: Literal["printed","cursive"] = "printed"
    seal_embedded_signature: bool = False
    seal_signer_name: str = Field(default="",max_length=100)
    stamp_style: Literal["random","portrait","architecture","botanical","commemorative","revenue"] = "random"
    stamp_palette: Literal["black","custom","random","sepia","red","blue","green","purple","monochrome","multicolor"] = "black"
    stamp_ink_mode: Literal["default","custom"] = "default"
    stamp_color: str = Field(default="#000000",pattern=r"^#[0-9a-fA-F]{6}$")
    stamp_issuer: str = Field(default="",max_length=80)
    stamp_caption: str = Field(default="",max_length=100)
    stamp_denomination: str = Field(default="",max_length=16)
    stamp_perforated: bool = True
    stamp_age: float = Field(default=.35,ge=0,le=1,allow_inf_nan=False)
    stamp_cancellation: Literal["random","none","postmark","waves","pen"] = "none"
    rubber_stamp_style: Literal["random","boxed","text","round","dated","postmark","waves"] = "boxed"
    rubber_stamp_mode: Literal["random","static","custom"] = "random"
    rubber_stamp_text: str = Field(default="RECEIVED",max_length=100)
    rubber_stamp_format: str = Field(default="{department}\n{date}\nREF {reference}",max_length=480)
    rubber_stamp_color: Literal["random","red","blue","green","purple","black","brown"] = "random"

    @field_validator("address_country")
    @classmethod
    def valid_address_country(cls,value):return normalize_country(value)

    @field_validator("address_format")
    @classmethod
    def valid_address_format(cls,value):return validate_format(value)

    @field_validator("rubber_stamp_format")
    @classmethod
    def valid_rubber_format(cls,value):
        try:return validate_seal_format(value)
        except ValueError as exc:raise ValueError(str(exc).replace("Seal format","Rubber stamp format")) from exc

    @field_validator("seal_signer_name")
    @classmethod
    def valid_seal_signer(cls,value):
        if value.strip() and not any(c.isalpha() for c in value):raise ValueError("Signing name needs at least one letter")
        return value

    @field_validator("seal_top_format","seal_bottom_format","seal_body_format","seal_inner_top_text","seal_inner_bottom_text")
    @classmethod
    def valid_seal_format(cls,value):return validate_seal_format(value)

    @field_validator("identifier_pattern")
    @classmethod
    def valid_pattern(cls, value):
        pattern_parts(value)
        return value

    @field_validator("portrait_asset_ids")
    @classmethod
    def asset_ids(cls, values):
        import re
        if any(not re.fullmatch(r"[a-f0-9]{32}",v) for v in values):
            raise ValueError("Invalid portrait asset ID")
        return list(dict.fromkeys(values))

    @field_validator("color_palette","portrait_background_palette")
    @classmethod
    def valid_colors(cls,values):
        import re
        if any(not re.fullmatch(r"#[0-9a-fA-F]{6}",value) for value in values):raise ValueError("Palette colors must use #RRGGBB format")
        return list(dict.fromkeys(value.lower() for value in values))

    @field_validator("drawing_points")
    @classmethod
    def valid_drawing(cls,values):
        if any(not 0<=coordinate<=1 for point in values for coordinate in point):
            raise ValueError("Drawing coordinates must be finite fractions between 0 and 1")
        return values

    @model_validator(mode="after")
    def valid_dates(self):
        if self.ink_opacity_min>self.ink_opacity_max:
            raise ValueError("Minimum ink opacity must not exceed maximum ink opacity")
        if self.seal_text_mode=="static" and not self.seal_allow_repeated_words:
            duplicates=duplicate_words([self.seal_text,self.seal_subtext,self.seal_bottom_text,self.seal_inner_top_text,self.seal_inner_bottom_text])
            if duplicates:raise ValueError("Repeated seal words: "+", ".join(duplicates)+". Enable repeated words if intentional.")
        if self.date_start>self.date_end or self.date_start.year<1900 or self.date_end.year>2100:
            raise ValueError("Date range must be ordered and within 1900–2100")
        if self.identifier_pattern and self.character_length is not None and pattern_length(self.identifier_pattern)!=self.character_length:
            raise ValueError("Character length must match the pattern's output length, or leave length automatic")
        if self.literal_text is not None and self.character_length is not None and len(self.literal_text)!=self.character_length:
            raise ValueError("Literal text does not match the configured character length")
        return self


class Region(Contract):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    label: str = Field(default="Field", min_length=1, max_length=100)
    kind: FieldType = FieldType.text
    box: tuple[int, int, int, int]
    text: str = Field(default="", max_length=4000)
    confidence: float = Field(default=0, ge=0, le=1)
    sensitive: bool = True
    replace: bool = True
    confirmed: bool = False
    page: int = Field(default=0, ge=0, le=0)
    rule: str = Field(default="", max_length=2000)
    action: Literal["replace","erase","keep"] | None = None
    rule_options: RuleOptions = Field(default_factory=RuleOptions)
    rule_resolved_hash: str = Field(default="",max_length=64)
    source_font: str = Field(default="",max_length=150)
    source_font_size: float | None = Field(default=None,gt=0,le=1000)
    origin: Literal["manual","ocr","pii","visual"] = "manual"
    pii_category: Literal["","person","address","email","phone","date","identifier","financial","organization","medical","other"] = ""
    pii_value: str = Field(default="",max_length=400)
    pii_reason: str = Field(default="",max_length=500)

    @model_validator(mode="after")
    def valid_box(self):
        if self.action is not None:
            self.replace=self.action!="keep"
        if self.kind not in {"text","identifier","qr","barcode"} and (self.rule_options.identifier_pattern or self.rule_options.character_length is not None):
            raise ValueError("Character patterns/lengths apply to text, identifier, QR and barcode fields")
        if self.kind!="qr" and self.rule_options.character_length and self.rule_options.character_length>128:
            raise ValueError("Only QR payloads support more than 128 characters (up to 500)")
        if self.kind!="qr" and self.rule_options.identifier_pattern and pattern_length(self.rule_options.identifier_pattern)>128:
            raise ValueError("Only QR patterns support more than 128 characters (up to 500)")
        x, y, w, h = self.box
        if x < 0 or y < 0 or w < 4 or h < 4:
            raise ValueError("Region needs nonnegative position and at least 4x4 pixels")
        return self


def region_action(region: Region) -> str:
    return region.action or ("replace" if region.replace else "keep")


class Review(Contract):
    regions: list[Region] = Field(max_length=200)
    privacy_confirmed: bool = False
    revision: int = Field(ge=1)


class GenerationConfig(Contract):
    template_id: str
    name: str = Field(default="Certificate dataset", min_length=1, max_length=100)
    count: int = Field(default=100, ge=1, le=2000)
    seed: int = Field(default=42, ge=0, le=2**31-1)
    blur_probability: float = Field(default=.2, ge=0, le=1)
    rotation_probability: float = Field(default=.15, ge=0, le=1)
    rotation_degrees: float = Field(default=3, ge=0, le=8)
    noise_sigma: float = Field(default=0, ge=0, le=12)
    signatures: bool = True
    signature_style_override: Literal["mixed"] | None = None
    signature_content_override: Literal["current","name","alphabet","mixed"] | None = None
    seals: bool = True
    stamps: bool = True
    rubber_stamps: bool = True
    qr_codes: bool = True
    barcodes: bool = False
    max_retries: int = Field(default=2, ge=0, le=5)
    qr_padding: int = Field(default=0,ge=0,le=8)
    qr_payload_length: int = Field(default=10,ge=1,le=500)
    identifier_length: int = Field(default=10,ge=1,le=128)
    qr_required: bool = False

    @model_validator(mode="after")
    def required_qr_enabled(self):
        if self.qr_required and not self.qr_codes: raise ValueError("Enable QR codes when QR is required")
        return self


class ExportRequest(Contract):
    format: str = Field(default="yolo", pattern="^(yolo|coco|ocr)$")
    review_confirmed: bool = False
