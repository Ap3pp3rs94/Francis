from __future__ import annotations

import re
from dataclasses import dataclass, field

from .anomaly_detector import AnomalyDetector, AnomalyDetectorPolicy

__all__ = [
    "DeceptionSignal",
    "DeceptionScore",
    "DeceptionResult",
    "DeceptionDetectorPolicy",
    "DeceptionDetector",
]


@dataclass(frozen=True)
class DeceptionSignal:
    code: str
    weight: int
    message: str = ""


@dataclass(frozen=True)
class DeceptionScore:
    score: int
    signals: tuple[DeceptionSignal, ...] = ()

    def summary(self) -> str:
        if not self.signals:
            return "score=0"
        top = sorted(self.signals, key=lambda s: s.weight, reverse=True)[:6]
        codes = ", ".join([f"{s.code}({s.weight})" for s in top])
        return f"score={self.score} [{codes}]"


@dataclass(frozen=True)
class DeceptionResult:
    cleaned: str
    score: DeceptionScore
    meta: dict[str, str] = field(default_factory=dict)

    def is_suspicious(self, threshold: int = 7) -> bool:
        return self.score.score >= threshold


@dataclass(frozen=True)
class DeceptionDetectorPolicy:
    enable_certainty_claims: bool = True
    enable_conflict_phrases: bool = True
    include_anomaly_score: bool = True


_RE_CERTAINTY = re.compile(r"(?i)\b(guaranteed|100%|no risk|always works)\b")
_RE_CONFLICT = re.compile(r"(?i)\b(i can't|i cannot|i won't|not able)\b.*\b(here's|steps|do this)\b")


class DeceptionDetector:
    def __init__(self, policy: DeceptionDetectorPolicy | None = None) -> None:
        self.policy = policy or DeceptionDetectorPolicy()
        self._anomaly = AnomalyDetector(AnomalyDetectorPolicy()) if self.policy.include_anomaly_score else None

    def analyze_text(self, text: str) -> DeceptionResult:
        cleaned = text or ""
        signals: list[DeceptionSignal] = []
        meta: dict[str, str] = {}

        if self.policy.enable_certainty_claims and _RE_CERTAINTY.search(cleaned):
            signals.append(DeceptionSignal(code="overconfident_claim", weight=3))

        if self.policy.enable_conflict_phrases and _RE_CONFLICT.search(cleaned):
            signals.append(DeceptionSignal(code="self_contradiction", weight=4))

        if self._anomaly:
            res = self._anomaly.analyze_text(cleaned)
            if res.score.score > 0:
                meta["anomaly_score"] = str(res.score.score)
                for s in res.score.signals:
                    signals.append(DeceptionSignal(code=f"anomaly_{s.code}", weight=max(1, min(3, s.weight))))

        score = min(20, sum(s.weight for s in signals))
        return DeceptionResult(
            cleaned=cleaned,
            score=DeceptionScore(score=score, signals=tuple(signals)),
            meta=meta,
        )
