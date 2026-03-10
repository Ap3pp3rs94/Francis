import * as THREE from "three";

export type OrbState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "acting"
  | "interject"
  | "error";

export interface OrbSignalFrame {
  state: OrbState;
  speakingAmplitude: number;
  attentionTarget?: THREE.Vector3 | null;
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
  particleOpacity: number;
  particleSpeed: number;
  auraOpacity: number;
  auraScale: number;
  coreIntensity: number;
  coreDistortion: number;
  compression: number;
  beamOpacity: number;
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
