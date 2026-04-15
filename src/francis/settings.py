from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    # Only imported for type-checking. Runtime import is guarded below.
    from pydantic import AliasChoices, Field
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
        from pydantic import AliasChoices, Field
        from pydantic_settings import BaseSettings, SettingsConfigDict
    except Exception:  # pragma: no cover - optional dependency
        BaseSettings = None  # type: ignore[assignment]
        SettingsConfigDict = None  # type: ignore[assignment]
        AliasChoices = None  # type: ignore[assignment]
        Field = None  # type: ignore[assignment]


def _env_text(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _env_int(*names: str, default: int) -> int:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        try:
            return int(text)
        except Exception:
            logger.warning("Ignoring invalid integer env %s=%r", name, value)
    return default

if not TYPE_CHECKING and BaseSettings is not None:

    class Settings(BaseSettings):
        francis_env: str = Field(
            default="dev",
            validation_alias=AliasChoices("FRANCIS_ENV_PROFILE", "FRANCIS_ENV"),
        )
        francis_root: str = Field(
            default=".",
            validation_alias=AliasChoices("FRANCIS_ROOT", "FRANCIS_HOME"),
        )
        francis_log_level: str = Field(
            default="INFO",
            validation_alias=AliasChoices("FRANCIS_LOG_LEVEL", "LOG_LEVEL"),
        )
        francis_log_json: bool = Field(
            default=True,
            validation_alias=AliasChoices("FRANCIS_LOG_JSON", "LOG_JSON"),
        )

        francis_api_host: str = Field(
            default="127.0.0.1",
            validation_alias=AliasChoices("FRANCIS_API_HOST", "API_HOST"),
        )
        francis_api_port: int = Field(
            default=8000,
            validation_alias=AliasChoices("FRANCIS_API_PORT", "API_PORT"),
        )

        ollama_base_url: str = Field(
            default="http://localhost:11434",
            validation_alias=AliasChoices("FRANCIS_OLLAMA_BASE_URL", "OLLAMA_BASE_URL"),
        )
        ollama_default_model: str = Field(
            default="qwen2.5:7b",
            validation_alias=AliasChoices("FRANCIS_LLM_CHAT_MODEL", "OLLAMA_DEFAULT_MODEL"),
        )

        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

elif not TYPE_CHECKING:

    @dataclass
    class Settings:
        francis_env: str = field(default_factory=lambda: _env_text("FRANCIS_ENV_PROFILE", "FRANCIS_ENV", default="dev"))
        francis_root: str = field(default_factory=lambda: _env_text("FRANCIS_ROOT", "FRANCIS_HOME", default="."))
        francis_log_level: str = field(default_factory=lambda: _env_text("FRANCIS_LOG_LEVEL", "LOG_LEVEL", default="INFO"))
        francis_log_json: bool = field(
            default_factory=lambda: _env_text("FRANCIS_LOG_JSON", "LOG_JSON", default="true").lower() not in {"0", "false", "no", "off"}
        )

        francis_api_host: str = field(default_factory=lambda: _env_text("FRANCIS_API_HOST", "API_HOST", default="127.0.0.1"))
        francis_api_port: int = field(default_factory=lambda: _env_int("FRANCIS_API_PORT", "API_PORT", default=8000))

        ollama_base_url: str = field(
            default_factory=lambda: _env_text("FRANCIS_OLLAMA_BASE_URL", "OLLAMA_BASE_URL", default="http://localhost:11434")
        )
        ollama_default_model: str = field(
            default_factory=lambda: _env_text("FRANCIS_LLM_CHAT_MODEL", "OLLAMA_DEFAULT_MODEL", default="qwen2.5:7b")
        )
