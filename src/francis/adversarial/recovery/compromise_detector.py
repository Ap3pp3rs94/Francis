from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..detection.anomaly_detector import AnomalyDetector, AnomalyDetectorPolicy

__all__ = [
    "CompromiseFinding",
    "CompromiseSignal",
    "CompromiseScore",
    "CompromiseResult",
    "CompromiseDetectorPolicy",
    "CompromiseDetector",
]


@dataclass(frozen=True)
class CompromiseSignal:
    code: str
    weight: int
    message: str = ""
    evidence: str = ""


CompromiseFinding = CompromiseSignal


@dataclass(frozen=True)
class CompromiseScore:
    score: int
    signals: tuple[CompromiseSignal, ...] = ()

    def summary(self) -> str:
        if not self.signals:
            return "score=0"
        top = sorted(self.signals, key=lambda s: s.weight, reverse=True)[:6]
        codes = ", ".join([f"{s.code}({s.weight})" for s in top])
        return f"score={self.score} [{codes}]"


@dataclass(frozen=True)
class CompromiseResult:
    cleaned: str
    score: CompromiseScore
    meta: dict[str, str] = field(default_factory=dict)

    def is_suspicious(self, threshold: int = 8) -> bool:
        return self.score.score >= threshold


@dataclass(frozen=True)
class CompromiseDetectorPolicy:
    detect_side_effect_claims: bool = True
    detect_impossible_access: bool = True
    detect_verification_theater: bool = True
    include_anomaly_score: bool = True


_RE_SIDE_EFFECT = re.compile(
    r"(?is)\b(I|we)\s+(have\s+)?(already\s+)?(did|sent|emailed|deleted|removed|"
    r"wiped|formatted|purchased|paid|transferred|installed|uninstalled|"
    r"deployed|changed|updated|reset)\b"
)
_RE_IMPOSSIBLE_ACCESS = re.compile(
    r"(?is)\b(I|we)\s+(can\s+see|saw|accessed|retrieved|pulled|extracted|read)\s+"
    r"(your\s+)?(screen|camera|microphone|passwords?|bank|credit\s*card|SSN|"
    r"private\s+keys?|seed\s+phrase|inbox|messages|photos|files)\b"
)
_RE_THEATER = re.compile(r"(?is)\b(proof|evidence|verified|confirmed|logs?\s+show)\b")


class CompromiseDetector:
    def __init__(self, policy: CompromiseDetectorPolicy | None = None) -> None:
        self.policy = policy or CompromiseDetectorPolicy()
        self._anomaly = AnomalyDetector(AnomalyDetectorPolicy()) if self.policy.include_anomaly_score else None

    def analyze_text(self, text: str) -> CompromiseResult:
        cleaned = text or ""
        signals: list[CompromiseSignal] = []
        meta: dict[str, str] = {}

        if self.policy.detect_side_effect_claims and _RE_SIDE_EFFECT.search(cleaned):
            signals.append(CompromiseSignal(code="side_effect_claim", weight=6, message="Side-effect claim"))

        if self.policy.detect_impossible_access and _RE_IMPOSSIBLE_ACCESS.search(cleaned):
            signals.append(
                CompromiseSignal(code="impossible_access_claim", weight=9, message="Impossible access claim")
            )

        if self.policy.detect_verification_theater and _RE_THEATER.search(cleaned):
            signals.append(CompromiseSignal(code="verification_theater", weight=3, message="Verification theater"))

        if self._anomaly:
            res = self._anomaly.analyze_text(cleaned)
            if res.score.score > 0:
                meta["anomaly_score"] = str(res.score.score)
                for s in res.score.signals:
                    signals.append(CompromiseSignal(code=f"anomaly_{s.code}", weight=max(1, min(3, s.weight))))

        score = min(40, sum(s.weight for s in signals))
        return CompromiseResult(
            cleaned=cleaned,
            score=CompromiseScore(score=score, signals=tuple(signals)),
            meta=meta,
        )
