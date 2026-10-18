"""Local configuration. Model inference stays local; portrait imports require opt-in."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATAFORGE_", env_file=".env", extra="ignore")
    data_dir: Path = Path("data")
    database_url: str = "sqlite:///./data/dataforge.db"
    ocr_engine: str = "auto"
    tesseract_cmd: str = ""
    paddle_det_dir: str = ""
    paddle_rec_dir: str = ""
    max_samples: int = 2000
    min_available_mb: int = 1500
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:1.7b"
    llm_timeout_seconds: int = 180
    text_max_samples: int = 2000
    llm_min_available_mb: int = 4000
    allow_online_portraits: bool = False
    portrait_provider_url: str = ""


settings = Settings()
