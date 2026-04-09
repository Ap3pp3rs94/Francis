import * as THREE from "three";
import type { OrbExternalSignals } from "../control/OrbStateController";
import type { OrbAttentionState, OrbState } from "../core/types";
import { isOrbActionState } from "../core/state-semantics";

interface HudOrbTargetCue {
  state?: string;
  attention_state?: string;
  attention_strength?: number;
  lock_strength?: number;
  uncertainty?: number;
  salience?: string;
  confidence?: string;
  stability?: string;
  control_ready?: boolean;
  window_match?: string;
}

interface HudOrbPerceptionTarget {
  confidence?: string;
  stability?: {
    state?: string;
  };
  attention?: {
    state?: string;
    salience?: string;
    strength?: number;
    lock_strength?: number;
    uncertainty?: number;
  };
}

export interface HudOrbPayload {
  posture?: string;
  interjection_level?: number;
  operator_cursor?: boolean;
  panic_ready?: boolean;
  voice_channel?: boolean;
  visual?: {
    pulse_kind?: string;
    core_brightness?: number;
    halo_strength?: number;
    ring_density?: number;
    ring_tightness?: number;
    orbit_speed?: number;
    voice_resonance?: number;
  };
  state?: {
    pending_approvals?: number;
    blocked_actions?: number;
    enabled_actions?: number;
    security_quarantines?: number;
    incident_severity?: string;
  };
  operator?: {
    target_cue?: HudOrbTargetCue | null;
  };
  perception?: {
    target?: HudOrbPerceptionTarget | null;
  };
}

export interface HudOrbSignalOverrides {
  stateOverride?: OrbState | null;
  speakingAmplitude?: number;
  attentionTarget?: THREE.Vector3 | null;
  attentionState?: OrbAttentionState | null;
  attentionStrength?: number;
  attentionLock?: number;
  attentionUncertainty?: number;
  actionTarget?: THREE.Vector3 | null;
  actionStrength?: number;
  confidence?: number;
}

export function screenPointToOrbTarget(
  clientX: number,
  clientY: number,
  viewportWidth: number,
  viewportHeight: number,
): THREE.Vector3 {
  const normalizedX = ((clientX / Math.max(viewportWidth, 1)) - 0.5) * 4.6;
  const normalizedY = (0.5 - (clientY / Math.max(viewportHeight, 1))) * 2.8;
  return new THREE.Vector3(normalizedX, normalizedY, 0);
}

export function elementToOrbTarget(element: Element | null): THREE.Vector3 | null {
  if (!element || typeof window === "undefined") {
    return null;
  }
  const rect = element.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    return null;
  }
  return screenPointToOrbTarget(
    rect.left + rect.width / 2,
    rect.top + rect.height / 2,
    window.innerWidth,
    window.innerHeight,
  );
}

function mapHudPayloadToState(payload: HudOrbPayload): OrbState {
  const targetCue = payload.operator?.target_cue ?? null;
  const pulseKind = String(payload.visual?.pulse_kind || "steady");
  const severity = String(payload.state?.incident_severity || "nominal").toLowerCase();
  const pendingApprovals = Number(payload.state?.pending_approvals ?? 0);
  const blockedActions = Number(payload.state?.blocked_actions ?? 0);
  const enabledActions = Number(payload.state?.enabled_actions ?? 0);

  if (payload.panic_ready && String(payload.posture || "") === "panic") {
    return "degraded";
  }
  if ((payload.state?.security_quarantines ?? 0) > 0 || severity === "critical") {
    return "degraded";
  }
  if (String(targetCue?.attention_state || "").trim().toLowerCase() === "target_lock") {
    return "target_lock";
  }
  if (String(targetCue?.attention_state || "").trim().toLowerCase() === "reassess") {
    return "blocked";
  }
  if (payload.operator_cursor || pulseKind === "execution") {
    return "commit_move";
  }
  if (blockedActions > 0) {
    return "blocked";
  }
  if (pendingApprovals > 0 || (payload.interjection_level ?? 0) >= 2 || String(payload.posture || "") === "interjecting") {
    return "waiting_user";
  }
  if (enabledActions > 0 || payload.voice_channel || pulseKind === "voice_ready") {
    return "investigate";
  }
  if (String(payload.posture || "") === "focused") {
    return "attentive";
  }
  return "idle_anchored";
}

function confidenceTextToScore(value: string | undefined): number {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "high" || normalized === "likely") {
    return 0.92;
  }
  if (normalized === "medium") {
    return 0.64;
  }
  if (normalized === "low") {
    return 0.28;
  }
  return 0.18;
}

function salienceTextToScore(value: string | undefined): number {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "high") {
    return 0.88;
  }
  if (normalized === "medium") {
    return 0.58;
  }
  return 0.26;
}

function stabilityTextToScore(value: string | undefined): number {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "settled") {
    return 0.92;
  }
  if (normalized === "tracking") {
    return 0.6;
  }
  if (normalized === "transient") {
    return 0.18;
  }
  return 0.08;
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.max(min, Math.min(max, value));
}

function normalizeAttentionState(value: string | undefined, fallback: OrbAttentionState = "idle"): OrbAttentionState {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "investigate" || normalized === "target_lock" || normalized === "reassess") {
    return normalized;
  }
  return fallback;
}

function defaultAttentionStateForState(state: OrbState): OrbAttentionState {
  if (state === "target_lock" || state === "commit_move" || state === "hover_ready" || state === "click_act" || state === "drag_act" || state === "type_hold") {
    return "target_lock";
  }
  if (state === "investigate" || state === "attentive") {
    return "investigate";
  }
  if (state === "blocked" || state === "interrupted") {
    return "reassess";
  }
  return "idle";
}

function deriveAttentionTelemetry(payload: HudOrbPayload, state: OrbState) {
  const targetCue = payload.operator?.target_cue ?? null;
  const perceptionTarget = payload.perception?.target ?? null;
  const perceptionAttention = perceptionTarget?.attention ?? null;
  const confidenceText = String(targetCue?.confidence || perceptionTarget?.confidence || "").trim().toLowerCase();
  const stabilityText = String(targetCue?.stability || perceptionTarget?.stability?.state || "").trim().toLowerCase();
  const defaultState = defaultAttentionStateForState(state);
  const requestedState = normalizeAttentionState(
    String(targetCue?.attention_state || perceptionAttention?.state || ""),
    defaultState,
  );

  const attentionState = state === "paused" || state === "degraded" || state === "interrupted"
    ? "idle"
    : state === "blocked"
      ? "reassess"
      : requestedState;
  let rawStrength = Number(
    targetCue?.attention_strength
      ?? perceptionAttention?.strength
      ?? Math.max(confidenceTextToScore(confidenceText), salienceTextToScore(perceptionAttention?.salience || targetCue?.salience)),
  );
  let rawLock = Number(
    targetCue?.lock_strength
      ?? perceptionAttention?.lock_strength
      ?? Math.max(
        stabilityTextToScore(stabilityText),
        attentionState === "target_lock" ? 0.78 : attentionState === "investigate" ? 0.42 : 0.18,
      ),
  );
  let rawUncertainty = Number(
    targetCue?.uncertainty
      ?? perceptionAttention?.uncertainty
      ?? (attentionState === "reassess" ? 0.72 : attentionState === "investigate" ? 0.34 : 0.12),
  );

  if (state === "waiting_user") {
    rawStrength = Math.max(rawStrength, 0.36);
    rawLock = Math.max(rawLock, 0.48);
    rawUncertainty = Math.min(rawUncertainty, 0.24);
  } else if (state === "blocked") {
    rawStrength = Math.max(rawStrength, 0.32);
    rawLock = Math.max(rawLock, 0.46);
    rawUncertainty = Math.min(rawUncertainty, 0.32);
  } else if (state === "paused") {
    rawStrength = Math.min(rawStrength, 0.14);
    rawLock = Math.max(rawLock, 0.18);
    rawUncertainty = Math.min(rawUncertainty, 0.12);
  } else if (state === "degraded") {
    rawStrength *= 0.52;
    rawLock *= 0.44;
    rawUncertainty = Math.max(rawUncertainty, 0.4);
  } else if (state === "interrupted") {
    rawStrength = Math.min(rawStrength, 0.18);
    rawLock = Math.min(rawLock, 0.22);
    rawUncertainty = Math.max(rawUncertainty, 0.28);
  }

  return {
    state: attentionState,
    strength: clamp(rawStrength),
    lock: clamp(rawLock),
    uncertainty: clamp(rawUncertainty),
  };
}

function deriveConfidence(payload: HudOrbPayload, attention: { lock: number; uncertainty: number }): number {
  const brightness = Number(payload.visual?.core_brightness ?? 0.72);
  const severity = String(payload.state?.incident_severity || "nominal").toLowerCase();
  const quarantinePenalty = Math.min(0.32, (payload.state?.security_quarantines ?? 0) * 0.18);
  const severityPenalty = severity === "high" ? 0.14 : severity === "critical" ? 0.22 : severity === "medium" ? 0.08 : 0;
  return Math.max(
    0.2,
    Math.min(0.98, brightness - quarantinePenalty - severityPenalty + attention.lock * 0.08 - attention.uncertainty * 0.1),
  );
}

export function mapHudOrbPayloadToSignals(
  payload: HudOrbPayload,
  overrides: HudOrbSignalOverrides = {},
): OrbExternalSignals {
  const state = overrides.stateOverride ?? mapHudPayloadToState(payload);
  const attention = deriveAttentionTelemetry(payload, state);
  const actionTarget = overrides.actionTarget ?? (isOrbActionState(state) ? new THREE.Vector3(2.1, 0.8, 0) : null);

  return {
    state,
    visual: {
      coreBrightness: clamp(Number(payload.visual?.core_brightness ?? 0.84)),
      haloStrength: clamp(Number(payload.visual?.halo_strength ?? 0.9)),
      ringDensity: clamp(Number(payload.visual?.ring_density ?? 10) / 10),
      ringTightness: clamp(Number(payload.visual?.ring_tightness ?? 0.82)),
      orbitSpeed: clamp(Number(payload.visual?.orbit_speed ?? 0.74)),
    },
    speakingAmplitude: overrides.speakingAmplitude ?? Number(payload.visual?.voice_resonance ?? 0),
    attentionTarget: overrides.attentionTarget ?? actionTarget,
    attentionState: overrides.attentionState ?? attention.state,
    attentionStrength: overrides.attentionStrength ?? attention.strength,
    attentionLock: overrides.attentionLock ?? attention.lock,
    attentionUncertainty: overrides.attentionUncertainty ?? attention.uncertainty,
    actionTarget,
    actionStrength:
      overrides.actionStrength ??
      (isOrbActionState(state) ? Math.max(0.42, Number(payload.visual?.core_brightness ?? 0.68)) : 0),
    confidence: overrides.confidence ?? deriveConfidence(payload, attention),
    interjectionIntent: state === "waiting_user" || state === "blocked",
  };
}
