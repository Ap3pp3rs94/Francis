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


def resolve_ollama_timeout_seconds() -> int:
    settings_timeout = 90
    try:
        settings = Settings()
        settings_timeout = int(getattr(settings, "llm_request_timeout_seconds", settings_timeout) or settings_timeout)
    except Exception as exc:
        logger.debug("Falling back to direct env resolution for Ollama timeout: %s", exc)

    timeout_text = _env_text(
        "FRANCIS_LLM_REQUEST_TIMEOUT_S",
        "LLM_REQUEST_TIMEOUT_S",
        default=str(settings_timeout),
    )
    try:
        timeout = int(timeout_text)
    except Exception:
        logger.warning("Ignoring invalid LLM request timeout: %r", timeout_text)
        timeout = settings_timeout
    return max(5, min(timeout, 300))


def generate(prompt: str) -> str:
    base, model = resolve_ollama_config()
    timeout_seconds = resolve_ollama_timeout_seconds()
    url = f"{base}/api/generate"
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
    try:
        r = httpx.post(url, json=payload, timeout=timeout_seconds)
        r.raise_for_status()
        j = r.json()
        return (j.get("response") or "").strip()
    except Exception as exc:
        logger.warning("Ollama generation failed for model=%s base=%s: %s", model, base, exc)
        return ""
