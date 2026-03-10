from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .tone import normalize_mode

SEVERITY_SCORES = {
    "nominal": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}
ACTIVE_EXECUTION_PHASES = {
    "act",
    "action",
    "autonomy",
    "cycle",
    "dispatch",
    "execute",
    "executing",
    "pilot",
    "takeover",
}
MODE_COLORWAYS = {
    "observe": {
        "core": "#dce6f4",
        "ring": "#95a7c8",
        "halo": "rgba(132, 155, 199, 0.28)",
        "accent": "#eff4fb",
    },
    "assist": {
        "core": "#f5d7a7",
        "ring": "#db8f55",
        "halo": "rgba(219, 143, 85, 0.30)",
        "accent": "#fff3e1",
    },
    "pilot": {
        "core": "#f7f0d6",
        "ring": "#d65d36",
        "halo": "rgba(214, 93, 54, 0.38)",
        "accent": "#fff7eb",
    },
    "away": {
        "core": "#d8f0e3",
        "ring": "#2d8a69",
        "halo": "rgba(45, 138, 105, 0.34)",
        "accent": "#effbf5",
    },
}


def _section(snapshot: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = snapshot.get(key, {})
    return value if isinstance(value, Mapping) else {}


def _count(snapshot: Mapping[str, Any], section_name: str, field: str) -> int:
    section = _section(snapshot, section_name)
    try:
        return int(section.get(field, 0))
    except (TypeError, ValueError):
        return 0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _severity_score(snapshot: Mapping[str, Any]) -> int:
    incidents = _section(snapshot, "incidents")
    severity = str(incidents.get("highest_severity", "nominal")).strip().lower() or "nominal"
    return int(SEVERITY_SCORES.get(severity, 0))


def _is_active_execution(mode: str, snapshot: Mapping[str, Any]) -> bool:
    runs = _section(snapshot, "runs")
    last_run = runs.get("last_run", {})
    if not isinstance(last_run, Mapping):
        last_run = {}
    phase = str(last_run.get("phase", "")).strip().lower()
    return mode in {"pilot", "away"} and phase in ACTIVE_EXECUTION_PHASES


def _interjection_level(
    *,
    kill_switch: bool,
    incident_score: int,
    approvals: int,
    blocked_actions: int,
    quarantines: int,
    alerts: int,
) -> int:
    if kill_switch or quarantines > 0 or incident_score >= 3:
        return 3
    if approvals > 0 or blocked_actions > 0 or incident_score == 2:
        return 2
    if alerts > 0:
        return 1
    return 0


def _orb_posture(
    *,
    mode: str,
    kill_switch: bool,
    active_execution: bool,
    interjection_level: int,
    active_missions: int,
) -> str:
    if kill_switch:
        return "panic"
    if active_execution:
        return "acting"
    if interjection_level >= 2:
        return "interjecting"
    if active_missions > 0 or mode in {"pilot", "away"}:
        return "focused"
    return "resting"


def _pulse_kind(*, posture: str, voice_lines: int, interjection_level: int) -> str:
    if posture == "panic":
        return "panic"
    if posture == "acting":
        return "execution"
    if interjection_level >= 2:
        return "interjection"
    if voice_lines > 0:
        return "voice_ready"
    return "steady"


def _movement_profile(*, active_execution: bool, interjection_level: int, panic_ready: bool) -> dict[str, Any]:
    cursor_lock = active_execution or panic_ready
    return {
        "anchor": "cursor",
        "profile": "cursor_lock" if cursor_lock else "cursor_drift",
        "cursor_lock": cursor_lock,
        "lead_style": "human_correction",
        "randomness": "hand_tremor" if cursor_lock else "breathing_variation",
        "lead_strength": round(0.06 if cursor_lock else 0.035, 3),
        "settle_strength": round(0.42 if cursor_lock else 0.24, 3),
        "damping": round(0.68 if cursor_lock else 0.82, 3),
        "drift_strength": round(0.45 if cursor_lock else 1.35, 3),
        "micro_strength": round(0.22 if cursor_lock else 0.75, 3),
        "vertical_bias": round(-0.02 if cursor_lock else -0.06, 3),
        "hesitation_ms": 180 if cursor_lock else 260,
        "interjection_bias": round(0.08 * interjection_level, 3),
    }


def _handback_profile(*, mode: str, active_execution: bool) -> dict[str, Any]:
    orchestrated_mode = mode in {"pilot", "away"}
    return {
        "visible": orchestrated_mode or active_execution,
        "ritual": "return_to_ambient",
        "return_profile": "graceful_arc",
        "anchor": "ambient_rest",
        "duration_ms": 1400 if orchestrated_mode else 1100,
    }


def build_orb_state(
    *,
    mode: str,
    snapshot: Mapping[str, Any],
    actions_payload: Mapping[str, Any] | None = None,
    voice: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_mode = normalize_mode(mode)
    actions_payload = actions_payload if isinstance(actions_payload, Mapping) else {}
    voice = voice if isinstance(voice, Mapping) else {}
    action_chips = [
        chip
        for chip in actions_payload.get("action_chips", [])
        if isinstance(chip, Mapping)
    ]
    blocked_actions = [
        chip
        for chip in actions_payload.get("blocked_actions", [])
        if isinstance(chip, Mapping)
    ]
    colorway = dict(MODE_COLORWAYS[normalized_mode])
    objective = _section(snapshot, "objective")
    control = _section(snapshot, "control")
    security = _section(snapshot, "security")
    runs = _section(snapshot, "runs")
    voice_lines = len([line for line in voice.get("lines", []) if isinstance(line, str) and line.strip()])
    incident_score = _severity_score(snapshot)
    pending_approvals = _count(snapshot, "approvals", "pending_count")
    quarantines = _count(snapshot, "security", "quarantine_count")
    alerts = _count(snapshot, "inbox", "alert_count")
    active_missions = _count(snapshot, "missions", "active_count")
    kill_switch = bool(control.get("kill_switch", False))
    enabled_actions = len([chip for chip in action_chips if bool(chip.get("enabled", False))])
    blocked_count = len(blocked_actions)
    panic_ready = kill_switch or any(
        str(chip.get("kind", "")).strip().lower() == "control.panic" and bool(chip.get("enabled", False))
        for chip in action_chips
    )
    active_execution = _is_active_execution(normalized_mode, snapshot)
    interjection_level = _interjection_level(
        kill_switch=kill_switch,
        incident_score=incident_score,
        approvals=pending_approvals,
        blocked_actions=blocked_count,
        quarantines=quarantines,
        alerts=alerts,
    )
    posture = _orb_posture(
        mode=normalized_mode,
        kill_switch=kill_switch,
        active_execution=active_execution,
        interjection_level=interjection_level,
        active_missions=active_missions,
    )
    pulse_kind = _pulse_kind(
        posture=posture,
        voice_lines=voice_lines,
        interjection_level=interjection_level,
    )
    top_category = next(
        iter(
            (
                security.get("top_categories", {})
                if isinstance(security.get("top_categories"), Mapping)
                else {}
            ).items()
        ),
        None,
    )
    last_run = runs.get("last_run", {})
    if not isinstance(last_run, Mapping):
        last_run = {}
    run_phase = str(last_run.get("phase", "unknown")).strip().lower() or "unknown"
    objective_label = (
        str(objective.get("label", "Systematically build Francis")).strip()
        or "Systematically build Francis"
    )

    core_brightness = _clamp(
        0.34
        + (0.08 * incident_score)
        + (0.10 * min(pending_approvals, 3))
        + (0.14 * min(quarantines, 2))
        + (0.18 if kill_switch else 0.0),
        0.28,
        1.0,
    )
    orbit_speed = _clamp(
        {
            "observe": 0.26,
            "assist": 0.38,
            "pilot": 0.56,
            "away": 0.46,
        }[normalized_mode]
        + (0.12 if active_execution else 0.0)
        + (0.06 * min(interjection_level, 3))
        + (0.02 * min(enabled_actions, 4)),
        0.2,
        1.0,
    )
    ring_tightness = _clamp(
        0.34 + (0.12 * interjection_level) + (0.14 if active_execution else 0.0),
        0.3,
        0.92,
    )
    ring_density = 5 + min(7, active_missions + enabled_actions + max(1, interjection_level))
    resonance = _clamp(0.18 + (0.08 * min(voice_lines, 5)) + (0.05 * interjection_level), 0.18, 0.82)

    if posture == "panic":
        summary = "Kill switch is live. The Orb is now the immediate stop surface."
    elif posture == "acting":
        summary = f"Francis is acting in {normalized_mode} mode. Follow the Orb to see where authority is landing."
    elif interjection_level >= 2:
        summary = "The work needs you now. The Orb is holding focus on a real decision edge."
    elif normalized_mode in {"observe", "assist"}:
        summary = "Ambient presence is live. The Orb is calm, grounded, and ready in place."
    else:
        summary = "Presence remains active and bounded while Francis keeps continuity alive."

    if quarantines > 0:
        detail = (
            f"{quarantines} quarantined ingress event(s) detected."
            + (f" Top category: {top_category[0]} ({int(top_category[1])})." if top_category else "")
        )
    elif pending_approvals > 0:
        detail = f"{pending_approvals} approval(s) are waiting before the next authority edge."
    elif active_execution:
        detail = f"Active run phase is {run_phase}. Handback should remain spatial and visible."
    else:
        detail = f"Objective remains {objective_label}."

    return {
        "surface": "orb",
        "mode": normalized_mode,
        "posture": posture,
        "interjection_level": interjection_level,
        "summary": summary,
        "detail": detail,
        "conversation_ready": True,
        "panic_ready": panic_ready,
        "operator_cursor": active_execution,
        "voice_channel": pulse_kind in {"voice_ready", "interjection", "execution"},
        "handback_visible": normalized_mode in {"pilot", "away"} or active_execution,
        "handback": _handback_profile(
            mode=normalized_mode,
            active_execution=active_execution,
        ),
        "palette": colorway,
        "movement": _movement_profile(
            active_execution=active_execution,
            interjection_level=interjection_level,
            panic_ready=panic_ready,
        ),
        "visual": {
            "core_brightness": round(core_brightness, 3),
            "orbit_speed": round(orbit_speed, 3),
            "ring_tightness": round(ring_tightness, 3),
            "ring_density": int(ring_density),
            "voice_resonance": round(resonance, 3),
            "halo_strength": round(_clamp(core_brightness + 0.08, 0.3, 1.0), 3),
            "pulse_kind": pulse_kind,
        },
        "state": {
            "objective": objective_label,
            "active_run_phase": run_phase,
            "active_missions": active_missions,
            "pending_approvals": pending_approvals,
            "blocked_actions": blocked_count,
            "enabled_actions": enabled_actions,
            "incident_severity": str(_section(snapshot, "incidents").get("highest_severity", "nominal")),
            "security_quarantines": quarantines,
            "inbox_alerts": alerts,
        },
        "controls": {
            "summon": "hotkey or click",
            "panic": "hold to stop",
            "inspect": "focus orb for detail",
        },
    }
