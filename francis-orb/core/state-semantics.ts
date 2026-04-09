import type { OrbState } from "./types";

const ORB_STATE_ORDER: readonly OrbState[] = [
  "idle_anchored",
  "attentive",
  "investigate",
  "target_lock",
  "commit_move",
  "hover_ready",
  "click_act",
  "drag_act",
  "type_hold",
  "waiting_user",
  "blocked",
  "interrupted",
  "degraded",
  "paused",
] as const;

const ORB_STATE_METRICS: Record<
  OrbState,
  {
    settleEnergy: number;
    stateBoost: number;
    pulseEnergy: number;
    motionEnergy: number;
    beam: boolean;
  }
> = {
  idle_anchored: { settleEnergy: 0.06, stateBoost: 0.0, pulseEnergy: 0.08, motionEnergy: 0.04, beam: false },
  attentive: { settleEnergy: 0.18, stateBoost: 0.12, pulseEnergy: 0.2, motionEnergy: 0.18, beam: false },
  investigate: { settleEnergy: 0.3, stateBoost: 0.18, pulseEnergy: 0.34, motionEnergy: 0.36, beam: false },
  target_lock: { settleEnergy: 0.54, stateBoost: 0.22, pulseEnergy: 0.46, motionEnergy: 0.48, beam: true },
  commit_move: { settleEnergy: 0.84, stateBoost: 0.28, pulseEnergy: 0.78, motionEnergy: 0.82, beam: true },
  hover_ready: { settleEnergy: 0.76, stateBoost: 0.26, pulseEnergy: 0.72, motionEnergy: 0.76, beam: true },
  click_act: { settleEnergy: 1.0, stateBoost: 0.34, pulseEnergy: 1.0, motionEnergy: 1.0, beam: true },
  drag_act: { settleEnergy: 0.92, stateBoost: 0.3, pulseEnergy: 0.82, motionEnergy: 0.9, beam: true },
  type_hold: { settleEnergy: 0.72, stateBoost: 0.24, pulseEnergy: 0.68, motionEnergy: 0.72, beam: true },
  waiting_user: { settleEnergy: 0.16, stateBoost: 0.1, pulseEnergy: 0.18, motionEnergy: 0.12, beam: false },
  blocked: { settleEnergy: 0.18, stateBoost: 0.08, pulseEnergy: 0.18, motionEnergy: 0.16, beam: false },
  interrupted: { settleEnergy: 0.14, stateBoost: 0.06, pulseEnergy: 0.14, motionEnergy: 0.12, beam: false },
  degraded: { settleEnergy: 0.14, stateBoost: 0.06, pulseEnergy: 0.16, motionEnergy: 0.14, beam: false },
  paused: { settleEnergy: 0.12, stateBoost: 0.04, pulseEnergy: 0.12, motionEnergy: 0.08, beam: false },
};

const ACTION_STATES = new Set<OrbState>([
  "target_lock",
  "commit_move",
  "hover_ready",
  "click_act",
  "drag_act",
  "type_hold",
]);

export function normalizeOrbState(value: OrbState | string | null | undefined): OrbState {
  const normalized = String(value || "").trim().toLowerCase() as OrbState;
  return ORB_STATE_ORDER.includes(normalized) ? normalized : "idle_anchored";
}

export function isOrbActionState(value: OrbState | string | null | undefined): boolean {
  return ACTION_STATES.has(normalizeOrbState(value));
}

export function getOrbSettleEnergy(state: OrbState | string | null | undefined): number {
  return ORB_STATE_METRICS[normalizeOrbState(state)].settleEnergy;
}

export function getOrbStateBoost(state: OrbState | string | null | undefined): number {
  return ORB_STATE_METRICS[normalizeOrbState(state)].stateBoost;
}

export function getOrbPulseEnergy(state: OrbState | string | null | undefined): number {
  return ORB_STATE_METRICS[normalizeOrbState(state)].pulseEnergy;
}

export function getOrbMotionEnergy(state: OrbState | string | null | undefined): number {
  return ORB_STATE_METRICS[normalizeOrbState(state)].motionEnergy;
}

export function shouldRenderOrbBeam(state: OrbState | string | null | undefined): boolean {
  return ORB_STATE_METRICS[normalizeOrbState(state)].beam;
}
