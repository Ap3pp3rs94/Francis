from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "ConstraintSet",
    "PlanStep",
    "Plan",
    "PlanStateMachine",
    "extract_constraints",
    "create_plan",
    "plan_from_dict",
    "revise_plan",
]


@dataclass(frozen=True)
class ConstraintSet:
    time_budget_sec: int | None = None
    budget: float | None = None
    privacy: str | None = None
    no_network: bool = False
    no_touch_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_budget_sec": self.time_budget_sec,
            "budget": self.budget,
            "privacy": self.privacy,
            "no_network": self.no_network,
            "no_touch_paths": list(self.no_touch_paths),
        }


@dataclass
class PlanStep:
    step_id: str
    title: str
    action: str
    status: str = "pending"
    depends_on: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Plan:
    goal: str
    constraints: ConstraintSet
    steps: list[PlanStep]
    status: str = "planned"
    checkpoints: list[str] = field(default_factory=list)
    revisions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "constraints": self.constraints.to_dict(),
            "status": self.status,
            "checkpoints": list(self.checkpoints),
            "revisions": list(self.revisions),
            "steps": [
                {
                    "step_id": s.step_id,
                    "title": s.title,
                    "action": s.action,
                    "status": s.status,
                    "depends_on": list(s.depends_on),
                    "notes": s.notes,
                }
                for s in self.steps
            ],
        }


class PlanStateMachine:
    def __init__(self, plan: Plan) -> None:
        self.plan = plan

    def start(self) -> None:
        if self.plan.status in {"completed", "failed"}:
            return
        self.plan.status = "in_progress"
        for step in self.plan.steps:
            if step.status == "pending":
                step.status = "in_progress"
                break

    def complete_step(self, step_id: str) -> None:
        for step in self.plan.steps:
            if step.step_id == step_id:
                step.status = "completed"
                break
        self._advance()

    def fail_step(self, step_id: str, reason: str) -> None:
        for step in self.plan.steps:
            if step.step_id == step_id:
                step.status = "failed"
                if reason:
                    step.notes = reason
                break
        self.plan.status = "blocked"

    def revise_for_failure(self, reason: str) -> None:
        revision = {
            "time": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "reason": reason,
        }
        self.plan.revisions.append(revision)
        self.plan.steps.extend(
            [
                PlanStep("revise_diagnose", "Diagnose failure", "inspect failure and logs", "pending"),
                PlanStep("revise_fix", "Apply fix", "make targeted change", "pending", depends_on=["revise_diagnose"]),
                PlanStep(
                    "revise_verify", "Verify recovery", "rerun checks/tests", "pending", depends_on=["revise_fix"]
                ),
            ]
        )
        self.plan.status = "revised"

    def _advance(self) -> None:
        if all(s.status == "completed" for s in self.plan.steps):
            self.plan.status = "completed"
            return
        for step in self.plan.steps:
            if step.status == "pending" and self._deps_done(step):
                step.status = "in_progress"
                self.plan.status = "in_progress"
                return

    def _deps_done(self, step: PlanStep) -> bool:
        if not step.depends_on:
            return True
        done = {s.step_id for s in self.plan.steps if s.status == "completed"}
        return all(dep in done for dep in step.depends_on)


def extract_constraints(goal: str, extra: dict[str, Any] | None = None) -> ConstraintSet:
    try:
        text = goal or ""
        no_network = bool(re.search(r"\b(no\s+network|offline|no\s+internet)\b", text, re.I))
        time_budget = _parse_time_budget(text)
        budget = _parse_budget(text)
        privacy = "strict" if re.search(r"\bprivacy\b|\bconfidential\b|\bprivate\b", text, re.I) else None
        no_touch = _parse_no_touch(text)

        if extra:
            time_budget = extra.get("time_budget_sec", time_budget)
            budget = extra.get("budget", budget)
            privacy = extra.get("privacy", privacy)
            no_network = bool(extra.get("no_network", no_network))
            no_touch_extra = extra.get("no_touch_paths") or []
            if isinstance(no_touch_extra, list):
                no_touch.extend([str(p) for p in no_touch_extra if str(p).strip()])
        return ConstraintSet(
            time_budget_sec=_to_int_or_none(time_budget),
            budget=_to_float_or_none(budget),
            privacy=privacy,
            no_network=no_network,
            no_touch_paths=_dedupe(no_touch),
        )
    except Exception as exc:
        logger.error("Constraint parsing failed: %s", exc)
        return ConstraintSet()


def create_plan(goal: str, constraints: dict[str, Any] | None = None) -> Plan:
    """Create a minimal, constraint-aware plan with checkpoints."""
    cs = extract_constraints(goal, constraints)
    steps = [
        PlanStep("understand", "Understand goal + constraints", "review goal and constraints"),
        PlanStep("execute", "Execute changes", "apply changes within constraints", depends_on=["understand"]),
        PlanStep("verify", "Verify outcome", "run checks/tests or validate output", depends_on=["execute"]),
        PlanStep("report", "Report results", "summarize changes and constraints", depends_on=["verify"]),
    ]
    checkpoints = ["plan_created", "changes_applied", "verification_complete"]
    return Plan(goal=goal, constraints=cs, steps=steps, checkpoints=checkpoints)


def plan_from_dict(data: dict[str, Any]) -> Plan:
    constraints = data.get("constraints") or {}
    cs = ConstraintSet(
        time_budget_sec=_to_int_or_none(constraints.get("time_budget_sec")),
        budget=_to_float_or_none(constraints.get("budget")),
        privacy=constraints.get("privacy"),
        no_network=bool(constraints.get("no_network", False)),
        no_touch_paths=list(constraints.get("no_touch_paths") or []),
    )
    steps = []
    for raw in data.get("steps") or []:
        if not isinstance(raw, dict):
            continue
        steps.append(
            PlanStep(
                step_id=str(raw.get("step_id", "")),
                title=str(raw.get("title", "")),
                action=str(raw.get("action", "")),
                status=str(raw.get("status", "pending")),
                depends_on=list(raw.get("depends_on") or []),
                notes=str(raw.get("notes", "")),
            )
        )
    if not steps:
        steps = create_plan(str(data.get("goal", ""))).steps
    return Plan(
        goal=str(data.get("goal", "")),
        constraints=cs,
        steps=steps,
        status=str(data.get("status", "planned")),
        checkpoints=list(data.get("checkpoints") or []),
        revisions=list(data.get("revisions") or []),
    )


def revise_plan(plan: Plan, reason: str) -> Plan:
    machine = PlanStateMachine(plan)
    machine.revise_for_failure(reason)
    return machine.plan


def _parse_time_budget(text: str) -> int | None:
    m = re.search(r"(\d+)\s*(hours|hrs|h|minutes|min|m|seconds|sec|s)\b", text, re.I)
    if not m:
        return None
    value = int(m.group(1))
    unit = m.group(2).lower()
    if unit in {"hours", "hrs", "h"}:
        return value * 3600
    if unit in {"minutes", "min", "m"}:
        return value * 60
    return value


def _parse_budget(text: str) -> float | None:
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*(usd|dollars|$)?", text, re.I)
    if not m:
        return None
    return float(m.group(1))


def _parse_no_touch(text: str) -> list[str]:
    paths: list[str] = []
    for m in re.finditer(r"(?:don't|do not)\s+touch\s+([^\n,;]+)", text, re.I):
        chunk = m.group(1).strip()
        match = re.findall(r"(?:[A-Za-z]:\\[^\\s,;]+|/[^\\s,;]+)", chunk)
        if match:
            paths.extend(match)
        else:
            paths.append(chunk)
    return paths


def _to_int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _to_float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out
