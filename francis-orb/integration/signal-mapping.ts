import * as THREE from "three";
import type { OrbExternalSignals } from "../control/OrbStateController";
import type { OrbState } from "../core/types";

export interface HudOrbPayload {
  posture?: string;
  interjection_level?: number;
  operator_cursor?: boolean;
  panic_ready?: boolean;
  voice_channel?: boolean;
  visual?: {
    pulse_kind?: string;
    core_brightness?: number;
    voice_resonance?: number;
  };
  state?: {
    pending_approvals?: number;
    blocked_actions?: number;
    enabled_actions?: number;
    security_quarantines?: number;
    incident_severity?: string;
  };
}

export interface HudOrbSignalOverrides {
  stateOverride?: OrbState | null;
  speakingAmplitude?: number;
  attentionTarget?: THREE.Vector3 | null;
  actionTarget?: THREE.Vector3 | null;
  actionStrength?: number;
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
  const pulseKind = String(payload.visual?.pulse_kind || "steady");
  const severity = String(payload.state?.incident_severity || "nominal").toLowerCase();

  if (payload.panic_ready && String(payload.posture || "") === "panic") {
    return "error";
  }
  if ((payload.state?.security_quarantines ?? 0) > 0 || severity === "critical") {
    return "error";
  }
  if (payload.operator_cursor || pulseKind === "execution") {
    return "acting";
  }
  if ((payload.interjection_level ?? 0) >= 2 || String(payload.posture || "") === "interjecting") {
    return "interject";
  }
  if (payload.voice_channel || pulseKind === "voice_ready") {
    return "speaking";
  }
  if ((payload.state?.enabled_actions ?? 0) > 0 || (payload.state?.pending_approvals ?? 0) > 0) {
    return "thinking";
  }
  return "idle";
}

function deriveConfidence(payload: HudOrbPayload): number {
  const brightness = Number(payload.visual?.core_brightness ?? 0.72);
  const severity = String(payload.state?.incident_severity || "nominal").toLowerCase();
  const quarantinePenalty = Math.min(0.32, (payload.state?.security_quarantines ?? 0) * 0.18);
  const severityPenalty = severity === "high" ? 0.14 : severity === "critical" ? 0.22 : severity === "medium" ? 0.08 : 0;
  return Math.max(0.2, Math.min(0.98, brightness - quarantinePenalty - severityPenalty));
}

export function mapHudOrbPayloadToSignals(
  payload: HudOrbPayload,
  overrides: HudOrbSignalOverrides = {},
): OrbExternalSignals {
  const state = overrides.stateOverride ?? mapHudPayloadToState(payload);
  const actionTarget = overrides.actionTarget ?? (state === "acting" ? new THREE.Vector3(2.1, 0.8, 0) : null);

  return {
    state,
    speakingAmplitude: overrides.speakingAmplitude ?? Number(payload.visual?.voice_resonance ?? 0),
    attentionTarget: overrides.attentionTarget ?? actionTarget,
    actionTarget,
    actionStrength:
      overrides.actionStrength ??
      (state === "acting" ? Math.max(0.42, Number(payload.visual?.core_brightness ?? 0.68)) : 0),
    confidence: deriveConfidence(payload),
    interjectionIntent: state === "interject",
  };
}
