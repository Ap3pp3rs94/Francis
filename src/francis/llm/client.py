from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from francis.settings import Settings

logger = logging.getLogger(__name__)


def _env_text(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def resolve_ollama_config() -> tuple[str, str]:
    settings_base = "http://localhost:11434"
    settings_model = "qwen2.5:7b"
    try:
        settings = Settings()
        settings_base = str(getattr(settings, "ollama_base_url", settings_base) or settings_base)
        settings_model = str(getattr(settings, "ollama_default_model", settings_model) or settings_model)
    except Exception as exc:
        logger.debug("Falling back to direct env resolution for Ollama config: %s", exc)

    base = _env_text("FRANCIS_OLLAMA_BASE_URL", "OLLAMA_BASE_URL", default=settings_base).rstrip("/")
    model = _env_text("FRANCIS_LLM_CHAT_MODEL", "OLLAMA_DEFAULT_MODEL", default=settings_model)
    return base, model


def generate(prompt: str) -> str:
    base, model = resolve_ollama_config()
    url = f"{base}/api/generate"
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
    try:
        r = httpx.post(url, json=payload, timeout=45)
        r.raise_for_status()
        j = r.json()
        return (j.get("response") or "").strip()
    except Exception as exc:
        logger.warning("Ollama generation failed for model=%s base=%s: %s", model, base, exc)
        return ""
