"""Metadata only in SQL; images and label artifacts live on local disk."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


def uid() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Template(Base):
    __tablename__ = "templates"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    image_path: Mapped[str] = mapped_column(Text)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    regions: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    engine: Mapped[str] = mapped_column(String(80), default="manual")
    revision: Mapped[int] = mapped_column(default=1)
    privacy_confirmed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TemplateVersion(Base):
    __tablename__ = "template_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    template_id: Mapped[str] = mapped_column(ForeignKey("templates.id"))
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    template_id: Mapped[str] = mapped_column(ForeignKey("templates.id"))
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    config: Mapped[dict] = mapped_column(JSON)
    template_snapshot: Mapped[dict] = mapped_column(JSON)
    total: Mapped[int] = mapped_column(Integer)
    completed: Mapped[int] = mapped_column(default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Sample(Base):
    __tablename__ = "samples"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(Text)
    annotations: Mapped[list] = mapped_column(JSON)
    validation: Mapped[dict] = mapped_column(JSON)
    sha256: Mapped[str] = mapped_column(String(64))


class Export(Base):
    __tablename__ = "exports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    format: Mapped[str] = mapped_column(String(12))
    path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TextJob(Base):
    __tablename__ = "text_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    config: Mapped[dict] = mapped_column(JSON)
    total: Mapped[int] = mapped_column(Integer)
    completed: Mapped[int] = mapped_column(default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TextSample(Base):
    __tablename__ = "text_samples"
    __table_args__ = (UniqueConstraint("job_id", "index"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("text_jobs.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(Text)
    summary: Mapped[dict] = mapped_column(JSON)
    validation: Mapped[dict] = mapped_column(JSON)
    sha256: Mapped[str] = mapped_column(String(64))


class TextExport(Base):
    __tablename__ = "text_exports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("text_jobs.id"))
    format: Mapped[str] = mapped_column(String(12))
    path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def connect(url: str):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def pragmas(connection, _):
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)
