from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root

__all__ = [
    "Observation",
    "AdversaryProfile",
    "AdversaryProfiler",
    "main",
]


@dataclass(frozen=True)
class Observation:
    time: str
    category: str
    indicator: str
    detail: str = ""
    severity: int = 3
    source: str = ""

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Observation":
        return Observation(
            time=str(data.get("time", "")) or datetime.utcnow().isoformat(timespec="seconds"),
            category=str(data.get("category", "")).strip().lower(),
            indicator=str(data.get("indicator", "")).strip().lower(),
            detail=str(data.get("detail", "")),
            severity=int(data.get("severity", 3)),
            source=str(data.get("source", "")),
        )


@dataclass
class DimensionScore:
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def add(self, delta: float, reason: str, *, weight: float = 1.0) -> None:
        self.score += float(delta) * float(weight)
        self.reasons.append(reason)

    def clamp(self, lo: float, hi: float) -> None:
        self.score = max(lo, min(hi, self.score))


@dataclass
class AdversaryProfile:
    generated_at: str
    incident_id: str = ""
    org: str = ""
    env: str = ""
    actor_type: str = "unknown"
    objectives: list[str] = field(default_factory=list)
    likely_vectors: list[str] = field(default_factory=list)
    sophistication: str = "unknown"
    opsec: str = "unknown"
    persistence_likelihood: float = 0.0
    lateral_movement_likelihood: float = 0.0
    exfiltration_likelihood: float = 0.0
    destructive_impact_likelihood: float = 0.0
    scores: dict[str, dict[str, Any]] = field(default_factory=dict)
    observation_count: int = 0
    top_observations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AdversaryProfiler:
    def __init__(self) -> None:
        self._rules: dict[str, list[tuple[str, float, str]]] = {
            "phishing_suspected": [
                ("vector_phishing", 1.0, "Phishing-like indicators observed."),
                ("actor_criminal", 0.7, "Phishing often aligns with criminal activity."),
            ],
            "exposed_service_suspected": [
                ("vector_exposed_service", 1.0, "Exposed service indicators observed."),
                ("actor_opportunistic", 0.6, "Often opportunistic."),
            ],
            "valid_accounts_suspected": [
                ("vector_valid_accounts", 1.0, "Valid account usage suspected."),
                ("opsec", 0.4, "Valid accounts can indicate better OPSEC."),
            ],
            "credential_dumping_artifacts": [
                ("credential_access", 1.0, "Credential access indicators observed."),
                ("lateral_movement", 0.5, "Credential access often enables lateral movement."),
                ("actor_criminal", 0.6, "Common in criminal intrusions."),
            ],
            "beaconing_pattern": [
                ("command_and_control", 1.0, "Beaconing behavior detected."),
                ("opsec", 0.4, "Steady beaconing may indicate discipline."),
            ],
            "large_outbound_transfer": [
                ("exfiltration", 0.8, "Large outbound transfer suggests exfiltration."),
                ("objective_theft", 0.7, "Data movement aligns with theft objectives."),
            ],
            "ransomware_notes": [
                ("impact", 1.0, "Ransomware note detected."),
                ("objective_ransomware", 1.0, "Ransomware objective likely."),
                ("actor_criminal", 1.0, "Often criminal."),
            ],
            "wiper_suspected": [
                ("impact", 1.0, "Destructive wiping suspected."),
                ("objective_disruption", 1.0, "Disruption objective likely."),
                ("actor_targeted", 0.7, "Destructive acts can be targeted."),
            ],
            "privileged_user_abuse_suspected": [
                ("actor_insider", 1.0, "Insider activity suspected."),
                ("vector_insider", 1.0, "Insider access vector."),
                ("opsec", 0.3, "Legitimate access can mask activity."),
            ],
        }

        self._category_weight: dict[str, float] = {
            "initial_access": 1.0,
            "execution": 1.0,
            "persistence": 1.0,
            "privilege_escalation": 1.0,
            "defense_evasion": 1.1,
            "credential_access": 1.2,
            "lateral_movement": 1.2,
            "exfiltration": 1.3,
            "command_and_control": 1.2,
            "impact": 1.4,
            "opsec": 1.0,
        }

    @staticmethod
    def _sev_weight(severity: int) -> float:
        s = max(1, min(5, int(severity)))
        return {1: 0.6, 2: 0.8, 3: 1.0, 4: 1.2, 5: 1.4}[s]

    def profile(self, observations: list[Observation], *, context: dict[str, Any] | None = None) -> AdversaryProfile:
        ctx = context or {}
        dims: dict[str, DimensionScore] = {}

        def dim(name: str) -> DimensionScore:
            dims.setdefault(name, DimensionScore())
            return dims[name]

        for obs in observations:
            weight = self._category_weight.get(obs.category, 1.0) * self._sev_weight(obs.severity)
            for dname, delta, reason in self._rules.get(obs.indicator, []):
                dim(dname).add(delta, reason, weight=weight)

        for k in ("sophistication", "opsec", "lateral_movement", "exfiltration", "impact"):
            if k in dims:
                dims[k].clamp(0.0, 10.0)

        vectors = self._ranked_labels(
            {
                "phishing": dims.get("vector_phishing", DimensionScore()).score,
                "exposed_service": dims.get("vector_exposed_service", DimensionScore()).score,
                "valid_accounts": dims.get("vector_valid_accounts", DimensionScore()).score,
                "insider": dims.get("vector_insider", DimensionScore()).score,
            }
        )
        objectives = self._ranked_labels(
            {
                "ransomware": dims.get("objective_ransomware", DimensionScore()).score,
                "theft": dims.get("objective_theft", DimensionScore()).score,
                "disruption": dims.get("objective_disruption", DimensionScore()).score,
            }
        )

        actor_scores = {
            "opportunistic": dims.get("actor_opportunistic", DimensionScore()).score,
            "criminal": dims.get("actor_criminal", DimensionScore()).score,
            "targeted": dims.get("actor_targeted", DimensionScore()).score,
            "insider": dims.get("actor_insider", DimensionScore()).score,
        }
        actor_type = max(actor_scores.items(), key=lambda kv: kv[1])[0] if any(actor_scores.values()) else "unknown"

        sophistication = self._bucket(dims.get("sophistication", DimensionScore()).score)
        opsec = self._bucket(dims.get("opsec", DimensionScore()).score, labels=("poor", "mixed", "strong"))

        def to_like(score: float, scale: float = 8.0) -> float:
            return max(0.0, min(1.0, min(score, 10.0) / scale))

        profile = AdversaryProfile(
            generated_at=datetime.utcnow().isoformat(timespec="seconds"),
            incident_id=str(ctx.get("incident_id", "")),
            org=str(ctx.get("org", "")),
            env=str(ctx.get("env", "")),
            actor_type=actor_type,
            objectives=objectives or ["unknown"],
            likely_vectors=vectors or ["unknown"],
            sophistication=sophistication,
            opsec=opsec,
            persistence_likelihood=to_like(dims.get("persistence", DimensionScore()).score),
            lateral_movement_likelihood=to_like(dims.get("lateral_movement", DimensionScore()).score),
            exfiltration_likelihood=to_like(dims.get("exfiltration", DimensionScore()).score),
            destructive_impact_likelihood=to_like(dims.get("impact", DimensionScore()).score, scale=7.0),
            scores=self._scores_out(dims),
            observation_count=len(observations),
            top_observations=[asdict(o) for o in observations[:10]],
        )
        return profile

    @staticmethod
    def _bucket(score: float, labels: tuple[str, str, str] = ("low", "moderate", "high")) -> str:
        if score >= 6.5:
            return labels[2]
        if score >= 3.0:
            return labels[1]
        if score > 0.0:
            return labels[0]
        return "unknown"

    @staticmethod
    def _ranked_labels(scores: dict[str, float]) -> list[str]:
        ordered = [name for name, sc in sorted(scores.items(), key=lambda kv: kv[1], reverse=True) if sc >= 0.8]
        return ordered

    @staticmethod
    def _scores_out(dims: dict[str, DimensionScore]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name, ds in dims.items():
            out[name] = {"score": round(ds.score, 3), "reasons": ds.reasons[:20]}
        return out


def _default_root() -> Path:
    return repo_root()


def _load_input(path: Path) -> tuple[dict[str, Any], list[Observation]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    obj = json.loads(raw)
    ctx = obj.get("context", {}) if isinstance(obj, dict) else {}
    obs = obj.get("observations", []) if isinstance(obj, dict) else []
    if not isinstance(ctx, dict):
        ctx = {}
    if not isinstance(obs, list):
        obs = []
    observations = [Observation.from_dict(x) for x in obs if isinstance(x, dict)]
    return ctx, observations


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="adversary_profiler")
    parser.add_argument("--root", default=str(_default_root()))
    parser.add_argument("--in", dest="in_path", required=True)
    parser.add_argument("--out", dest="out_path", default="")
    parser.add_argument("--log-dir", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).expanduser()
    in_path = Path(args.in_path).expanduser()
    if not in_path.exists():
        print(f"ERROR: input not found: {in_path}", file=sys.stderr)
        return 2

    log_dir = Path(args.log_dir).expanduser() if args.log_dir else (root / "data" / "logs" / "operations")
    log_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"adversary_profile_{now}.log"

    def log(msg: str) -> None:
        line = f"[{datetime.utcnow().strftime('%F %T')}] {msg}"
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
        print(line)

    log(f"Input: {in_path}")
    try:
        ctx, observations = _load_input(in_path)
    except Exception as exc:
        log(f"ERROR: parse failed: {type(exc).__name__}: {exc}")
        return 2

    profiler = AdversaryProfiler()
    profile = profiler.profile(observations, context=ctx)

    out_path = Path(args.out_path).expanduser() if args.out_path else (log_dir / f"adversary_profile_{now}.json")
    _write_text(out_path, profile.to_json())
    log(f"Wrote: {out_path}")
    log(
        f"actor_type={profile.actor_type} objectives={','.join(profile.objectives)} vectors={','.join(profile.likely_vectors)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
