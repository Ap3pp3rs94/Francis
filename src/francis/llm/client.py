from __future__ import annotations

import os
from typing import Any

import httpx


def generate(prompt: str) -> str:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:7b")
    url = f"{base}/api/generate"
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
    try:
        r = httpx.post(url, json=payload, timeout=45)
        r.raise_for_status()
        j = r.json()
        return (j.get("response") or "").strip()
    except Exception:
        return ""
