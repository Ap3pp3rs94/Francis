from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root

from .adversary_profiler import AdversaryProfile

__all__ = [
    "ScenarioStep",
    "AttackScenario",
    "AttackScenarioGenerator",
    "main",
]


@dataclass
class ScenarioStep:
    phase: str
    title: str
    attacker_activity: str
    defender_visibility: list[str] = field(default_factory=list)
    detection_ideas: list[str] = field(default_factory=list)
    mitigation_ideas: list[str] = field(default_factory=list)
    tabletop_questions: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class AttackScenario:
    scenario_id: str
    title: str
    summary: str
    tags: list[str] = field(default_factory=list)
    likelihood: float = 0.0
    confidence: float = 0.0
    impact: float = 0.0
    steps: list[ScenarioStep] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _default_root() -> Path:
    return repo_root()


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


class ScenarioLibrary:
    @staticmethod
    def ransomware_phishing() -> AttackScenario:
        return AttackScenario(
            scenario_id="SCN-RANSOM-PHISH",
            title="Ransomware via user-driven initial access",
            summary="User-driven access leads to ransomware impact.",
            tags=["objective:ransomware", "vector:phishing", "actor:criminal"],
            steps=[
                ScenarioStep(
                    phase="Initial Access",
                    title="User interaction initial access",
                    attacker_activity="Adversary gains access via user interaction.",
                    defender_visibility=["Email security logs", "Auth anomalies", "EDR alerts"],
                    detection_ideas=["Correlate email delivery with anomalous sign-in"],
                    mitigation_ideas=["Phishing-resistant MFA", "User reporting workflow"],
                    tabletop_questions=["How fast can sessions be revoked after compromise?"],
                ),
                ScenarioStep(
                    phase="Impact",
                    title="Disruptive impact on data/services",
                    attacker_activity="Adversary triggers disruptive impact to pressure recovery.",
                    defender_visibility=["Backup anomalies", "File change spikes"],
                    detection_ideas=["Detect sudden spikes in file modifications"],
                    mitigation_ideas=["Immutable backups", "Segmentation playbooks"],
                    tabletop_questions=["Can Tier-0 services be restored within RTO/RPO?"],
                ),
            ],
        )

    @staticmethod
    def ransomware_exposed_service() -> AttackScenario:
        return AttackScenario(
            scenario_id="SCN-RANSOM-EXPOSED",
            title="Ransomware via exposed service compromise",
            summary="Exposed service compromise leads to ransomware impact.",
            tags=["objective:ransomware", "vector:exposed_service", "actor:criminal"],
            steps=[
                ScenarioStep(
                    phase="Initial Access",
                    title="Compromise of exposed service",
                    attacker_activity="Adversary gains access via exposed service.",
                    defender_visibility=["WAF/edge logs", "Service auth logs"],
                    detection_ideas=["Alert on abnormal auth patterns to exposed services"],
                    mitigation_ideas=["Reduce exposure", "Rapid patch lanes"],
                    tabletop_questions=["Which services are exposed and who owns them?"],
                ),
                ScenarioStep(
                    phase="Impact",
                    title="Disruption and recovery pressure",
                    attacker_activity="Adversary triggers disruptive impact.",
                    defender_visibility=["Backup anomalies", "Service outages"],
                    detection_ideas=["Detect backup tampering indicators"],
                    mitigation_ideas=["Immutable backups", "Isolation playbooks"],
                    tabletop_questions=["Who can authorize emergency segmentation changes?"],
                ),
            ],
        )

    @staticmethod
    def targeted_data_theft() -> AttackScenario:
        return AttackScenario(
            scenario_id="SCN-THEFT-TARGETED",
            title="Targeted data theft with OPSEC-conscious behavior",
            summary="Adversary prioritizes stealth and exfiltration over disruption.",
            tags=["objective:theft", "actor:targeted", "opsec:strong"],
            steps=[
                ScenarioStep(
                    phase="Collection",
                    title="Data discovery and collection",
                    attacker_activity="Adversary locates and collects sensitive datasets.",
                    defender_visibility=["Audit logs", "DLP alerts"],
                    detection_ideas=["Detect anomalous bulk reads/exports"],
                    mitigation_ideas=["Least privilege", "DLP enforcement"],
                    tabletop_questions=["Do we know where crown jewels live?"],
                ),
                ScenarioStep(
                    phase="Exfiltration",
                    title="Staging and exfiltration attempts",
                    attacker_activity="Adversary stages and exfiltrates data.",
                    defender_visibility=["Egress telemetry", "Large outbound transfers"],
                    detection_ideas=["Alert on unusual upload volume"],
                    mitigation_ideas=["Egress allowlisting", "CASB policies"],
                    tabletop_questions=["How do we contain suspected exfiltration?"],
                ),
            ],
        )

    @staticmethod
    def insider_misuse() -> AttackScenario:
        return AttackScenario(
            scenario_id="SCN-INSIDER-MISUSE",
            title="Insider misuse or compromised privileged account",
            summary="Privileged access used in ways that violate policy.",
            tags=["actor:insider", "vector:insider", "objective:unknown"],
            steps=[
                ScenarioStep(
                    phase="Access",
                    title="Legitimate access abused",
                    attacker_activity="Privileged identity used in abnormal ways.",
                    defender_visibility=["Privileged session logs", "Change records"],
                    detection_ideas=["Alert on privileged actions without tickets"],
                    mitigation_ideas=["PAM approvals", "Session recording"],
                    tabletop_questions=["Who reviews privileged logs and how often?"],
                ),
            ],
        )


class AttackScenarioGenerator:
    def generate(self, profile: AdversaryProfile, *, max_scenarios: int = 5) -> list[AttackScenario]:
        objectives = _as_list(profile.objectives)
        vectors = _as_list(profile.likely_vectors)
        actor_type = str(profile.actor_type or "unknown").lower()

        lateral_like = float(profile.lateral_movement_likelihood or 0.0)
        exfil_like = float(profile.exfiltration_likelihood or 0.0)
        impact_like = float(profile.destructive_impact_likelihood or 0.0)
        sophistication = str(profile.sophistication or "unknown").lower()
        opsec = str(profile.opsec or "unknown").lower()

        candidates: list[tuple[AttackScenario, float, list[str]]] = []

        def add(scn: AttackScenario, base: float, rationale: list[str]) -> None:
            candidates.append((scn, base, rationale))

        if "ransomware" in objectives or ("unknown" in objectives and impact_like >= 0.5):
            if "phishing" in vectors or "unknown" in vectors:
                add(ScenarioLibrary.ransomware_phishing(), 0.65 + 0.2 * impact_like, ["Impact suggests ransomware."])
            if "exposed_service" in vectors:
                add(ScenarioLibrary.ransomware_exposed_service(), 0.65 + 0.2 * impact_like, ["Exposed service vector."])

        if "theft" in objectives or exfil_like >= 0.45:
            base = 0.55 + 0.25 * exfil_like
            if opsec in ("strong", "mixed"):
                base += 0.05
            if sophistication in ("high", "moderate"):
                base += 0.05
            add(ScenarioLibrary.targeted_data_theft(), base, ["Exfiltration likelihood elevated."])

        if actor_type == "insider" or "insider" in vectors:
            add(ScenarioLibrary.insider_misuse(), 0.75, ["Insider indicators present."])

        if not candidates:
            add(
                ScenarioLibrary.targeted_data_theft(),
                0.40 + 0.15 * exfil_like + 0.1 * lateral_like,
                ["Fallback scenario."],
            )

        out: list[AttackScenario] = []
        for scn, base, rationale in candidates:
            like = _clamp01(base + 0.10 * lateral_like + 0.10 * exfil_like)
            impact = _clamp01(0.30 + 0.50 * impact_like)
            specificity = 0.0
            specificity += 0.15 if objectives and "unknown" not in objectives else 0.0
            specificity += 0.15 if vectors and "unknown" not in vectors else 0.0
            specificity += 0.10 if actor_type != "unknown" else 0.0
            specificity += 0.10 if sophistication != "unknown" else 0.0
            specificity += 0.10 if opsec != "unknown" else 0.0
            confidence = _clamp01(0.35 + specificity)

            scn.likelihood = round(like, 3)
            scn.impact = round(impact, 3)
            scn.confidence = round(confidence, 3)
            scn.rationale = list(rationale)
            out.append(scn)

        uniq: dict[str, AttackScenario] = {}
        for scn in out:
            uniq.setdefault(scn.scenario_id, scn)
        ranked = sorted(uniq.values(), key=lambda s: (s.likelihood, s.impact, s.confidence), reverse=True)
        return ranked[: max(1, int(max_scenarios))]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="attack_scenario_generator")
    parser.add_argument("--root", default=str(_default_root()))
    parser.add_argument("--in", dest="in_path", required=True)
    parser.add_argument("--out", dest="out_path", default="")
    parser.add_argument("--format", choices=["json"], default="json")
    parser.add_argument("--max", dest="max_scenarios", type=int, default=5)
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
    _safe_mkdir(log_dir)
    now = _ts()
    log_path = log_dir / f"attack_scenarios_{now}.log"

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
        raw = json.loads(in_path.read_text(encoding="utf-8", errors="replace"))
        profile = AdversaryProfile(**raw)
    except Exception as exc:
        log(f"ERROR: failed to parse profile: {type(exc).__name__}: {exc}")
        return 2

    scenarios = AttackScenarioGenerator().generate(profile, max_scenarios=args.max_scenarios)
    out_path = Path(args.out_path).expanduser() if args.out_path else (log_dir / f"attack_scenarios_{now}.json")

    payload = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "source_profile": str(in_path),
        "scenario_count": len(scenarios),
        "scenarios": [s.to_dict() for s in scenarios],
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
