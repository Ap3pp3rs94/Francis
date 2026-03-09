from __future__ import annotations

import re
from typing import Any

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9._:/-]*", re.IGNORECASE)


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(str(value or "").lower())]


def chunk_text(text: str, *, max_chars: int = 900) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    words = normalized.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        next_len = current_len + len(word) + (1 if current else 0)
        if current and next_len > max_chars:
            chunks.append(" ".join(current))
            overlap = current[-18:] if len(current) > 18 else current
            current = list(overlap)
            current_len = len(" ".join(current))
        current.append(word)
        current_len = len(" ".join(current))
    if current:
        chunks.append(" ".join(current))
    return chunks


def build_artifact_chunks(artifacts: list[dict[str, Any]], *, max_chars: int = 900) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for artifact in artifacts:
        artifact_id = str(artifact.get("id", "")).strip()
        search_text = str(
            artifact.get("search_text")
            or f"{artifact.get('title', '')}\n{artifact.get('body', '')}"
        ).strip()
        if not artifact_id or not search_text:
            continue
        for index, chunk in enumerate(chunk_text(search_text, max_chars=max_chars)):
            chunks.append(
                {
                    "chunk_id": f"{artifact_id}:chunk:{index + 1}",
                    "artifact_id": artifact_id,
                    "chunk_index": index + 1,
                    "text": chunk,
                    "tokens": tokenize(chunk),
                }
            )
    return chunks
