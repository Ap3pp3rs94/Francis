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
OPERATOR_CURSOR_IDLE_THRESHOLD_MS = 30_000
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


def _cursor_authority_eligible(mode: str, active_execution: bool) -> bool:
    return mode == "away" and active_execution


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


def _movement_profile(
    *,
    active_execution: bool,
    interjection_level: int,
    panic_ready: bool,
    cursor_authority_eligible: bool,
) -> dict[str, Any]:
    motion_law = {
        "state_machine": "option_a_cursor_body",
        "anchor_strategy": "edge_window_perch",
        "safe_margin_px": 28,
        "taskbar_margin_px": 18,
        "idle_amplitude_px": 1,
        "attentive_bias": 0.14,
        "investigate_radius_px": 16,
        "lock_radius_px": 18,
        "hover_radius_px": 16,
        "hover_dwell_ms": 140,
        "click_pulse_ms": 160,
        "click_pulse_scale": 0.93,
        "blocked_recoil_px": 32,
        "type_hold_offset_x_px": 22,
        "type_hold_offset_y_px": -28,
        "idle_stiffness": 0.22,
        "attentive_stiffness": 0.24,
        "investigate_stiffness": 0.24,
        "lock_stiffness": 0.34,
        "commit_stiffness": 0.48,
        "hover_stiffness": 0.42,
        "drag_stiffness": 0.58,
        "abort_stiffness": 0.28,
        "damping_idle": 0.84,
        "damping_commit": 0.72,
        "damping_hover": 0.8,
        "lock_scale": 0.965,
        "hover_scale": 0.952,
        "drag_scale": 0.94,
        "blocked_scale": 0.985,
        "waiting_scale": 0.988,
        "topmost_posture": "screen_saver_visible_on_fullscreen",
    }
    trace_profile = {
        "human_follow_delay_ms": 156,
        "human_follow_delay_reduced_ms": 88,
        "human_follow_trail_nodes": 10,
        "human_follow_trail_spacing_ms": 18,
        "human_follow_trail_opacity": 0.24,
        "human_follow_trail_decay": 0.86,
        "autonomous_replay_enabled": True,
        "autonomous_replay_window_ms": 720,
        "autonomous_replay_max_snippets": 18,
        "autonomous_replay_min_points": 5,
        "autonomous_replay_scale_min": 0.38,
        "autonomous_replay_scale_max": 0.82,
        "autonomous_replay_wander_px": 18,
        "autonomous_replay_pause_min_ms": 820,
        "autonomous_replay_pause_max_ms": 2200,
        "autonomous_replay_bias": 0.28,
    }
    if cursor_authority_eligible:
        return {
            **motion_law,
            "anchor": "cursor",
            "profile": "cursor_ride",
            "cursor_lock": True,
            "lead_style": "predictive_commit",
            "randomness": "operator_tremor",
            "lead_strength": 0.082,
            "settle_strength": 0.56,
            "damping": 0.64,
            "drift_strength": 0.16,
            "micro_strength": 0.08,
            "vertical_bias": -0.008,
            "hesitation_ms": 120,
            "correction_strength": 2.6,
            "correction_cap": 4.5,
            "lead_cap": 10.0,
            "lock_radius": 0.72,
            "orbit_bias": 0.06,
            "interjection_bias": round(0.04 * interjection_level, 3),
            "lock_stiffness": 0.48,
            "commit_stiffness": 0.62,
            "hover_stiffness": 0.56,
            "hover_dwell_ms": 110,
            "click_pulse_scale": 0.922,
            "drag_stiffness": 0.68,
            "idle_amplitude_px": 1,
            **trace_profile,
        }
    if active_execution:
        return {
            **motion_law,
            "anchor": "ambient",
            "profile": "focus_orbit",
            "cursor_lock": False,
            "lead_style": "focus_orbit",
            "randomness": "operator_breathing",
            "lead_strength": 0.028,
            "settle_strength": 0.34,
            "damping": 0.78,
            "drift_strength": 0.28,
            "micro_strength": 0.12,
            "vertical_bias": -0.11,
            "hesitation_ms": 240,
            "correction_strength": 1.8,
            "correction_cap": 2.8,
            "lead_cap": 4.2,
            "lock_radius": 0.86,
            "orbit_bias": 0.06,
            "interjection_bias": round(0.04 * interjection_level, 3),
            "anchor_strategy": "window_task_perch",
            "idle_amplitude_px": 2,
            "attentive_bias": 0.2,
            "investigate_radius_px": 18,
            "lock_radius_px": 16,
            "lock_stiffness": 0.38,
            "commit_stiffness": 0.52,
            "hover_stiffness": 0.46,
            "hover_dwell_ms": 120,
            "click_pulse_scale": 0.932,
            "blocked_recoil_px": 28,
            **trace_profile,
        }
    if panic_ready:
        return {
            **motion_law,
            "anchor": "ambient",
            "profile": "guard_orbit",
            "cursor_lock": False,
            "lead_style": "authority_guard",
            "randomness": "tension_hold",
            "lead_strength": 0.024,
            "settle_strength": 0.38,
            "damping": 0.78,
            "drift_strength": 0.22,
            "micro_strength": 0.1,
            "vertical_bias": -0.1,
            "hesitation_ms": 180,
            "correction_strength": 1.9,
            "correction_cap": 3.2,
            "lead_cap": 4.8,
            "lock_radius": 0.8,
            "orbit_bias": 0.04,
            "interjection_bias": round(0.05 * interjection_level, 3),
            "anchor_strategy": "guard_edge_perch",
            "idle_amplitude_px": 1,
            "investigate_radius_px": 14,
            "lock_radius_px": 14,
            "lock_stiffness": 0.4,
            "commit_stiffness": 0.5,
            "hover_stiffness": 0.44,
            "blocked_recoil_px": 24,
            **trace_profile,
        }
    return {
        **motion_law,
        "anchor": "ambient",
        "profile": "ambient_float",
        "cursor_lock": False,
        "lead_style": "ambient_float",
        "randomness": "breathing_variation",
        "lead_strength": 0.0,
        "settle_strength": 0.28,
        "damping": 0.88,
        "drift_strength": 0.18,
        "micro_strength": 0.08,
        "vertical_bias": -0.12,
        "hesitation_ms": 340,
        "correction_strength": 1.2,
        "correction_cap": 2.2,
        "lead_cap": 0.0,
        "lock_radius": 0.72,
        "orbit_bias": 0.03,
        "interjection_bias": round(0.08 * interjection_level, 3),
        "anchor_strategy": "edge_window_perch",
        "idle_amplitude_px": 1,
        "attentive_bias": 0.14,
        "investigate_radius_px": 16,
        "lock_radius_px": 18,
        "lock_stiffness": 0.32,
        "commit_stiffness": 0.44,
        "hover_stiffness": 0.38,
        "hover_dwell_ms": 140,
        "click_pulse_scale": 0.938,
        "blocked_recoil_px": 34,
        **trace_profile,
    }


def _handback_profile(*, mode: str, active_execution: bool) -> dict[str, Any]:
    orchestrated_mode = mode in {"pilot", "away"}
    return {
        "visible": orchestrated_mode or active_execution,
        "ritual": "return_to_ambient",
        "return_profile": "release_arc",
        "anchor": "ambient_rest",
        "duration_ms": 1480 if orchestrated_mode else 1180,
        "linger_ms": 120 if orchestrated_mode else 90,
        "settle_ms": 180 if orchestrated_mode else 140,
        "arc_lift_px": 72 if orchestrated_mode else 56,
        "release_bias": 0.22 if orchestrated_mode else 0.18,
        "velocity_carry": 0.34 if orchestrated_mode else 0.26,
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
    cursor_authority_eligible = _cursor_authority_eligible(normalized_mode, active_execution)
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
        0.68
        + (0.08 * incident_score)
        + (0.10 * min(pending_approvals, 3))
        + (0.14 * min(quarantines, 2))
        + (0.18 if kill_switch else 0.0),
        0.58,
        1.0,
    )
    orbit_speed = _clamp(
        {
            "observe": 0.46,
            "assist": 0.58,
            "pilot": 0.74,
            "away": 0.64,
        }[normalized_mode]
        + (0.12 if active_execution else 0.0)
        + (0.06 * min(interjection_level, 3))
        + (0.02 * min(enabled_actions, 4)),
        0.4,
        1.0,
    )
    ring_tightness = _clamp(
        0.64 + (0.1 * interjection_level) + (0.16 if active_execution else 0.0),
        0.58,
        0.98,
    )
    ring_density = 11 + min(13, active_missions + enabled_actions + max(3, interjection_level))
    resonance = _clamp(0.18 + (0.08 * min(voice_lines, 5)) + (0.05 * interjection_level), 0.18, 0.82)

    if posture == "panic":
        summary = "Kill switch is live. The Orb is the immediate stop surface without taking your cursor."
    elif posture == "acting" and cursor_authority_eligible:
        summary = (
            "Francis is acting in away mode. Cursor authority stays idle-gated and will arm only after 30 seconds of mouse and keyboard inactivity."
        )
    elif posture == "acting":
        summary = f"Francis is acting in {normalized_mode} mode while leaving your mouse under your control. The Orb stays free-floating and visible."
    elif interjection_level >= 2:
        summary = "The work needs you now. The Orb is holding focus on a real decision edge."
    elif normalized_mode in {"observe", "assist"}:
        summary = "Ambient presence is live. The Orb stays nearby and out of the way until the work needs attention."
    else:
        summary = "Presence remains active and bounded while Francis keeps continuity alive without taking the cursor."

    if quarantines > 0:
        detail = (
            f"{quarantines} quarantined ingress event(s) detected."
            + (f" Top category: {top_category[0]} ({int(top_category[1])})." if top_category else "")
        )
    elif pending_approvals > 0:
        detail = f"{pending_approvals} approval(s) are waiting before the next authority edge."
    elif active_execution and cursor_authority_eligible:
        detail = (
            f"Active run phase is {run_phase}. Away execution is cursor-eligible, but live cursor authority waits for "
            "30 seconds of local mouse and keyboard inactivity so the user keeps immediate control until they step away."
        )
    elif active_execution:
        detail = f"Active run phase is {run_phase}. The Orb stays free-floating while you keep direct mouse control."
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
        "operator_cursor": False,
        "operator_cursor_eligible": cursor_authority_eligible,
        "cursor_policy": {
            "eligible": cursor_authority_eligible,
            "activation": "mouse_idle",
            "threshold_ms": OPERATOR_CURSOR_IDLE_THRESHOLD_MS,
            "summary": (
                "Away execution may take cursor authority only after 30 seconds of mouse and keyboard inactivity."
                if cursor_authority_eligible
                else "Cursor authority is not eligible in the current mode and run state."
            ),
        },
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
            cursor_authority_eligible=cursor_authority_eligible,
        ),
        "visual": {
            "core_brightness": round(core_brightness, 3),
            "orbit_speed": round(orbit_speed, 3),
            "ring_tightness": round(ring_tightness, 3),
            "ring_density": int(ring_density),
            "voice_resonance": round(resonance, 3),
            "halo_strength": round(_clamp(core_brightness + 0.16, 0.62, 1.0), 3),
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
