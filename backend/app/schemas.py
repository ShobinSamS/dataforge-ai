"""Public contracts; all coordinates are pixels in the canonical page image."""
from enum import StrEnum
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from .patterns import pattern_parts, pattern_length


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


CLASS_NAMES = [v.value for v in FieldType]


class RuleOptions(Contract):
    date_format: Literal["yyyy-mm-dd","dd/mm/yyyy","mm/dd/yyyy","dd-mm-yyyy","yyyy/mm/dd"] = "yyyy-mm-dd"
    date_start: date = date(2015,1,1)
    date_end: date = date(2025,12,31)
    identifier_pattern: str = Field(default="",max_length=256)
    character_length: int | None = Field(default=None,ge=1,le=500)
    character_set: Literal["alnum","digits","upper","lower"] = "alnum"
    literal_text: str | None = Field(default=None,min_length=1,max_length=1000)
    portrait_source: Literal["illustration","asset_pool"] = "illustration"
    portrait_asset_ids: list[str] = Field(default_factory=list,max_length=20)
    font_id: str = Field(default="auto",max_length=100,pattern=r"^[a-zA-Z0-9_.-]+$")
    font_size: int | None = Field(default=None,ge=6,le=200)
    text_color: str = Field(default="#000000",pattern=r"^#[0-9a-fA-F]{6}$")
    color_mode: Literal["auto","manual"] = "auto"
    font_weight: Literal["auto","normal","bold"] = "auto"
    background_mode: Literal["auto","solid"] = "auto"
    background_color: str = Field(default="#ffffff",pattern=r"^#[0-9a-fA-F]{6}$")

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

    @model_validator(mode="after")
    def valid_dates(self):
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
    seals: bool = True
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
