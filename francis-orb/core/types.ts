import * as THREE from "three";

export type OrbState =
  | "idle_anchored"
  | "attentive"
  | "investigate"
  | "target_lock"
  | "commit_move"
  | "hover_ready"
  | "click_act"
  | "drag_act"
  | "type_hold"
  | "waiting_user"
  | "blocked"
  | "interrupted"
  | "degraded"
  | "paused";

export type OrbAttentionState =
  | "idle"
  | "investigate"
  | "target_lock"
  | "reassess";

export interface OrbSignalFrame {
  state: OrbState;
  speakingAmplitude: number;
  visualCoreBrightness?: number;
  visualHaloStrength?: number;
  visualRingDensity?: number;
  visualRingTightness?: number;
  visualOrbitSpeed?: number;
  attentionTarget?: THREE.Vector3 | null;
  attentionState?: OrbAttentionState;
  attentionStrength?: number;
  attentionLock?: number;
  attentionUncertainty?: number;
  actionTarget?: THREE.Vector3 | null;
  actionStrength?: number;
  confidence?: number;
  interjectionIntent?: boolean;
  dt: number;
  elapsed: number;
}

export interface OrbStateProfile {
  pulseSpeed: number;
  pulseAmplitude: number;
  shellOpacity: number;
  shellFresnelPower: number;
  filamentOpacity: number;
  filamentSpeed: number;
  filamentTightness: number;
  filamentContinuity: number;
  filamentDrift: number;
  filamentSpread: number;
  directionalBias: number;
  particleOpacity: number;
  particleSpeed: number;
  auraOpacity: number;
  auraScale: number;
  coreIntensity: number;
  coreDistortion: number;
  rootStillness: number;
  compression: number;
  beamOpacity: number;
}

export interface OrbVisualTelemetry {
  coreBrightness?: number;
  haloStrength?: number;
  ringDensity?: number;
  ringTightness?: number;
  orbitSpeed?: number;
}

export interface FrancisOrbEngineOptions {
  container: HTMLElement;
  seed?: number;
  background?: number;
  pixelRatio?: number;
  usePostFX?: boolean;
  enableBeam?: boolean;
  transparentBackground?: boolean;
}

export interface OrbRenderable {
  update(frame: OrbSignalFrame, profile: OrbStateProfile): void;
  dispose(): void;
}
