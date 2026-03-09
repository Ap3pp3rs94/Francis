from __future__ import annotations

SUPPORTED_LOCALES = ("en-US",)


def capability_status() -> dict[str, object]:
    return {
        "status": "preview_ready",
        "engine": "contract_stub",
        "supported_locales": list(SUPPORTED_LOCALES),
        "receipts_required": True,
    }


def preview_transcription(utterance: str, *, locale: str = "en-US") -> dict[str, object]:
    if locale not in SUPPORTED_LOCALES:
        raise ValueError(f"Unsupported locale: {locale}")
    normalized = " ".join(str(utterance).strip().split())
    return {
        "accepted": bool(normalized),
        "locale": locale,
        "normalized_text": normalized,
        "word_count": len(normalized.split()) if normalized else 0,
        "trust": "Likely" if normalized else "Uncertain",
    }
