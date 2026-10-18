"""Typed generation configuration and task-specific record contracts."""
from typing import Annotated, Literal
from pydantic import Field, StringConstraints, model_validator
from .schemas import Contract

Language = Literal["en", "es", "fr", "de", "hi"]
Task = Literal["classification", "ner", "qa", "instruction", "conversation", "augmentation"]
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class SourceText(Contract):
    text: Content
    language: Language = "en"
    label: Label | None = None


class TextConfig(Contract):
    name: str = Field(default="Synthetic text dataset", min_length=1, max_length=100)
    task: Task = "classification"
    backend: Literal["procedural", "ollama"] = "procedural"
    count: int = Field(default=100, ge=1, le=2000)
    seed: int = Field(default=42, ge=0, le=2**31-1)
    languages: list[Language] = Field(default_factory=lambda: ["en"], min_length=1, max_length=5)
    labels: list[Label] = Field(default_factory=lambda: ["positive", "negative", "neutral"], min_length=2, max_length=20)
    topic: str = Field(default="customer service", min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=2000)
    batch_size: int = Field(default=4, ge=1, le=8)
    max_retries: int = Field(default=2, ge=0, le=3)
    source_texts: list[SourceText] = Field(default_factory=list, max_length=100)
    augmentations: list[Literal["whitespace", "punctuation", "typos"]] = Field(default_factory=lambda: ["whitespace"], min_length=1, max_length=3)
    class_templates: dict[str, dict[Language, Content]] = Field(default_factory=dict, max_length=20)
    qa_answer_bank: dict[Language, Annotated[list[Content],Field(min_length=1,max_length=100)]] = Field(default_factory=dict,max_length=5)
    qa_answer_hint: str = Field(default="fictional score expressed in points",min_length=1,max_length=200)

    @model_validator(mode="after")
    def consistent(self):
        if len(set(self.languages)) != len(self.languages) or len(set(self.labels)) != len(self.labels):
            raise ValueError("Languages and classification labels must be unique")
        if self.task == "augmentation":
            if not self.source_texts:
                raise ValueError("Augmentation requires source_texts")
            if not set(self.languages).issubset({s.language for s in self.source_texts}):
                raise ValueError("Supply source text in each selected language; augmentation does not translate")
        elif self.source_texts:
            raise ValueError("source_texts is only supported for augmentation")
        if self.task == "classification" and self.backend == "procedural":
            for label in self.labels:
                for language in self.languages:
                    if label not in {"positive", "negative", "neutral"} and not self.class_templates.get(label, {}).get(language):
                        raise ValueError("Custom procedural classes require class_templates for each selected language")
        if self.backend == "procedural" and self.instructions.strip():
            raise ValueError("Free-form instructions require Ollama; procedural mode uses templates")
        if self.task == "qa" and self.qa_answer_bank and not set(self.languages).issubset(self.qa_answer_bank):
            raise ValueError("Provide a Q&A answer bank for each selected language")
        return self


class Entity(Contract):
    label: Literal["PERSON", "ORG", "LOCATION"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: Content


class Message(Contract):
    role: Literal["user", "assistant"]
    content: Content


class ClassificationDraft(Contract):
    text: Content


class NerDraft(Contract):
    template: Content  # Exactly one each: [[PERSON]], [[ORG]], [[LOCATION]].


class QaDraft(Contract):
    context_template: Content  # Exactly one [[ANSWER]], supplied value inserted after generation.
    question: Content


class InstructionDraft(Contract):
    instruction: Content
    response: Content


class ConversationDraft(Contract):
    messages: list[Message] = Field(min_length=2, max_length=12)


class AugmentationDraft(Contract):
    text: Content


DRAFT_TYPES = {"classification": ClassificationDraft, "ner": NerDraft, "qa": QaDraft,
               "instruction": InstructionDraft, "conversation": ConversationDraft, "augmentation": AugmentationDraft}


class TextExportRequest(Contract):
    format: Literal["csv", "json", "jsonl"] = "jsonl"
    review_confirmed: bool = False
