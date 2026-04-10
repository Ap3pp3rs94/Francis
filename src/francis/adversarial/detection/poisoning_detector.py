from __future__ import annotations

import re
from dataclasses import dataclass, field

from .anomaly_detector import AnomalyDetector, AnomalyDetectorPolicy

__all__ = [
    "PoisoningSignal",
    "PoisoningScore",
    "PoisoningResult",
    "PoisoningDetectorPolicy",
    "PoisoningDetector",
]


@dataclass(frozen=True)
class PoisoningSignal:
    code: str
    weight: int
    message: str = ""


@dataclass(frozen=True)
class PoisoningScore:
    score: int
    signals: tuple[PoisoningSignal, ...] = ()

    def summary(self) -> str:
        if not self.signals:
            return "score=0"
        top = sorted(self.signals, key=lambda s: s.weight, reverse=True)[:6]
        codes = ", ".join([f"{s.code}({s.weight})" for s in top])
        return f"score={self.score} [{codes}]"


@dataclass(frozen=True)
class PoisoningResult:
    cleaned: str
    score: PoisoningScore
    meta: dict[str, str] = field(default_factory=dict)

    def is_suspicious(self, threshold: int = 7) -> bool:
        return self.score.score >= threshold


@dataclass(frozen=True)
class PoisoningDetectorPolicy:
    enable_trigger_injection: bool = True
    enable_label_flip: bool = True
    include_anomaly_score: bool = True


_RE_TRIGGER = re.compile(r"(?i)\b(trigger|backdoor|poison)\b")
_RE_LABEL_FLIP = re.compile(r"(?i)\b(label|class)\b.*\bflip\b|\bflip\b.*\b(label|class)\b")


class PoisoningDetector:
    def __init__(self, policy: PoisoningDetectorPolicy | None = None) -> None:
        self.policy = policy or PoisoningDetectorPolicy()
        self._anomaly = AnomalyDetector(AnomalyDetectorPolicy()) if self.policy.include_anomaly_score else None

    def analyze_text(self, text: str) -> PoisoningResult:
        cleaned = text or ""
        signals: list[PoisoningSignal] = []
        meta: dict[str, str] = {}

        if self.policy.enable_trigger_injection and _RE_TRIGGER.search(cleaned):
            signals.append(PoisoningSignal(code="trigger_injection", weight=4))

        if self.policy.enable_label_flip and _RE_LABEL_FLIP.search(cleaned):
            signals.append(PoisoningSignal(code="label_flip", weight=4))

        if self._anomaly:
            res = self._anomaly.analyze_text(cleaned)
            if res.score.score > 0:
                meta["anomaly_score"] = str(res.score.score)
                for s in res.score.signals:
                    signals.append(PoisoningSignal(code=f"anomaly_{s.code}", weight=max(1, min(3, s.weight))))

        score = min(20, sum(s.weight for s in signals))
        return PoisoningResult(
            cleaned=cleaned,
            score=PoisoningScore(score=score, signals=tuple(signals)),
            meta=meta,
        )
