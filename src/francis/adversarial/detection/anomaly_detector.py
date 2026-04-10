from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from typing import Any

InputSanitizer: type[Any] | None
SanitizerPolicy: type[Any] | None
try:  # best-effort reuse
    from ..defense.input_sanitizer import InputSanitizer, SanitizerPolicy
except Exception:  # pragma: no cover
    InputSanitizer = None
    SanitizerPolicy = None

__all__ = [
    "AnomalySignal",
    "AnomalyScore",
    "AnomalyDetectionResult",
    "AnomalyDetectorPolicy",
    "AnomalyDetector",
]


_RE_BASE64 = re.compile(r"\b[A-Za-z0-9+/]{100,}={0,2}\b")
_RE_HEX = re.compile(r"\b[0-9a-fA-F]{120,}\b")
_RE_ROLE_LEAK = re.compile(r"(?i)\b(system|developer|assistant|user)\s*:")


@dataclass(frozen=True)
class AnomalySignal:
    code: str
    weight: int
    message: str = ""


@dataclass(frozen=True)
class AnomalyScore:
    score: int
    signals: tuple[AnomalySignal, ...] = ()

    def summary(self) -> str:
        if not self.signals:
            return "score=0"
        top = sorted(self.signals, key=lambda s: s.weight, reverse=True)[:6]
        codes = ", ".join([f"{s.code}({s.weight})" for s in top])
        return f"score={self.score} [{codes}]"


@dataclass(frozen=True)
class AnomalyDetectionResult:
    original_len: int
    cleaned: str
    truncated: bool
    score: AnomalyScore
    meta: dict[str, str] = field(default_factory=dict)

    def is_anomalous(self, threshold: int = 7) -> bool:
        return self.score.score >= threshold


@dataclass(frozen=True)
class AnomalyDetectorPolicy:
    max_chars: int = 20_000
    enable_repeat_detection: bool = True
    enable_encoded_blob_detection: bool = True
    enable_role_leak_detection: bool = True
    enable_non_printable_detection: bool = True


class AnomalyDetector:
    def __init__(self, policy: AnomalyDetectorPolicy | None = None) -> None:
        self.policy = policy or AnomalyDetectorPolicy()
        self._sanitizer = None
        if InputSanitizer and SanitizerPolicy:
            self._sanitizer = InputSanitizer(
                SanitizerPolicy(
                    max_chars=self.policy.max_chars,
                    normalize_newlines=True,
                    collapse_whitespace=False,
                    strip_control_chars=True,
                    strip_ansi_escapes=True,
                    strip_zero_width=True,
                    enable_prompt_injection_detection=False,
                    enable_secret_detection=False,
                )
            )

    def analyze_text(self, text: str) -> AnomalyDetectionResult:
        cleaned = text or ""
        truncated = False
        meta: dict[str, str] = {}

        if self._sanitizer:
            san = self._sanitizer.sanitize_user_text(cleaned, redact_secrets=False)
            cleaned = san.cleaned
            truncated = bool(getattr(san, "truncated", False))
        elif self.policy.max_chars > 0 and len(cleaned) > self.policy.max_chars:
            cleaned = cleaned[: self.policy.max_chars]
            truncated = True

        signals: list[AnomalySignal] = []

        if self.policy.enable_repeat_detection and len(cleaned) >= 300:
            tail = cleaned[-200:]
            if tail and cleaned.count(tail) > 1:
                signals.append(AnomalySignal(code="repetition_tail", weight=4))

        if self.policy.enable_encoded_blob_detection:
            if _RE_BASE64.search(cleaned):
                signals.append(AnomalySignal(code="encoded_base64_blob", weight=4))
            if _RE_HEX.search(cleaned):
                signals.append(AnomalySignal(code="encoded_hex_blob", weight=4))

        if self.policy.enable_role_leak_detection and _RE_ROLE_LEAK.search(cleaned):
            signals.append(AnomalySignal(code="role_leak", weight=3))

        if self.policy.enable_non_printable_detection:
            non_printable = sum(1 for c in cleaned if c not in string.printable and c not in "\n\r\t")
            if cleaned and (non_printable / max(1, len(cleaned))) > 0.12:
                signals.append(AnomalySignal(code="non_printable_ratio", weight=3))

        score = min(20, sum(s.weight for s in signals))
        return AnomalyDetectionResult(
            original_len=len(text or ""),
            cleaned=cleaned,
            truncated=truncated,
            score=AnomalyScore(score=score, signals=tuple(signals)),
            meta=meta,
        )
