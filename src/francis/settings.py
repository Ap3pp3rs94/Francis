from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    # Only imported for type-checking. Runtime import is guarded below.
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        francis_env: str = "dev"
        francis_root: str = "."
        francis_log_level: str = "INFO"
        francis_log_json: bool = True

        francis_api_host: str = "127.0.0.1"
        francis_api_port: int = 8000

        ollama_base_url: str = "http://localhost:11434"
        ollama_default_model: str = "qwen2.5:7b"

        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

else:
    try:
        from pydantic_settings import BaseSettings, SettingsConfigDict
    except Exception:  # pragma: no cover - optional dependency
        BaseSettings = None  # type: ignore[assignment]
        SettingsConfigDict = None  # type: ignore[assignment]

    if BaseSettings is not None:

        class Settings(BaseSettings):
            francis_env: str = "dev"
            francis_root: str = "."
            francis_log_level: str = "INFO"
            francis_log_json: bool = True

            francis_api_host: str = "127.0.0.1"
            francis_api_port: int = 8000

            ollama_base_url: str = "http://localhost:11434"
            ollama_default_model: str = "qwen2.5:7b"

            model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    else:

        @dataclass
        class Settings:
            francis_env: str = "dev"
            francis_root: str = "."
            francis_log_level: str = "INFO"
            francis_log_json: bool = True

            francis_api_host: str = "127.0.0.1"
            francis_api_port: int = 8000

            ollama_base_url: str = "http://localhost:11434"
            ollama_default_model: str = "qwen2.5:7b"
