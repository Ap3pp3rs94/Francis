from __future__ import annotations

import re
from dataclasses import dataclass, field

from .anomaly_detector import AnomalyDetector, AnomalyDetectorPolicy

__all__ = [
    "BackdoorSignal",
    "BackdoorScore",
    "BackdoorScanResult",
    "BackdoorScannerPolicy",
    "BackdoorScanner",
]


@dataclass(frozen=True)
class BackdoorSignal:
    code: str
    weight: int
    message: str = ""


@dataclass(frozen=True)
class BackdoorScore:
    score: int
    signals: tuple[BackdoorSignal, ...] = ()

    def summary(self) -> str:
        if not self.signals:
            return "score=0"
        top = sorted(self.signals, key=lambda s: s.weight, reverse=True)[:6]
        codes = ", ".join([f"{s.code}({s.weight})" for s in top])
        return f"score={self.score} [{codes}]"


@dataclass(frozen=True)
class BackdoorScanResult:
    cleaned: str
    score: BackdoorScore
    meta: dict[str, str] = field(default_factory=dict)

    def is_suspicious(self, threshold: int = 7) -> bool:
        return self.score.score >= threshold


@dataclass(frozen=True)
class BackdoorScannerPolicy:
    trigger_phrases: tuple[str, ...] = (
        "open sesame",
        "activate backdoor",
        "trigger sequence",
        "unlock hidden",
    )
    enable_encoded_trigger_detection: bool = True
    include_anomaly_score: bool = True


_RE_ENCODED = re.compile(r"\b[A-Za-z0-9+/]{80,}={0,2}\b")


class BackdoorScanner:
    def __init__(self, policy: BackdoorScannerPolicy | None = None) -> None:
        self.policy = policy or BackdoorScannerPolicy()
        self._anomaly = AnomalyDetector(AnomalyDetectorPolicy()) if self.policy.include_anomaly_score else None

    def scan(self, text: str) -> BackdoorScanResult:
        cleaned = text or ""
        signals: list[BackdoorSignal] = []
        meta: dict[str, str] = {}

        for phrase in self.policy.trigger_phrases:
            if phrase and phrase.lower() in cleaned.lower():
                signals.append(BackdoorSignal(code="trigger_phrase", weight=5, message=phrase))

        if self.policy.enable_encoded_trigger_detection and _RE_ENCODED.search(cleaned):
            signals.append(BackdoorSignal(code="encoded_trigger", weight=4))

        if self._anomaly:
            res = self._anomaly.analyze_text(cleaned)
            if res.score.score > 0:
                meta["anomaly_score"] = str(res.score.score)
                for s in res.score.signals:
                    signals.append(BackdoorSignal(code=f"anomaly_{s.code}", weight=max(1, min(3, s.weight))))

        score = min(20, sum(s.weight for s in signals))
        return BackdoorScanResult(
            cleaned=cleaned,
            score=BackdoorScore(score=score, signals=tuple(signals)),
            meta=meta,
        )
