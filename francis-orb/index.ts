export { ORB_CONFIG } from "./core/config";
export { ORB_STATE_PROFILES } from "./core/state-profiles";
export type {
  FrancisOrbEngineOptions,
  OrbRenderable,
  OrbSignalFrame,
  OrbState,
  OrbStateProfile,
} from "./core/types";
export { DeterministicRng } from "./core/deterministic-rng";
export { FrancisOrbEngine } from "./renderer/FrancisOrbEngine";
export { OrbScene } from "./renderer/OrbScene";
export { OrbComposer } from "./renderer/OrbComposer";
export { OrbCore } from "./renderer/OrbCore";
export { OrbShell } from "./renderer/OrbShell";
export { OrbFilaments } from "./renderer/OrbFilaments";
export { OrbParticles } from "./renderer/OrbParticles";
export { OrbAura } from "./renderer/OrbAura";
export { OrbTargetBeam } from "./renderer/OrbTargetBeam";
export { OrbStateController } from "./control/OrbStateController";
export type { OrbExternalSignals } from "./control/OrbStateController";
export { OrbAttentionController } from "./control/OrbAttentionController";
export { OrbSpeechController } from "./control/OrbSpeechController";
export { OrbActionController } from "./control/OrbActionController";
export { OrbTransitionController } from "./control/OrbTransitionController";
export { InterjectionPolicy } from "./policy/InterjectionPolicy";
export type { InterjectionDecision, InterjectionDecisionInput, InterjectReason } from "./policy/types";
export { createFrancisOrb } from "./integration/createFrancisOrb";
export {
  elementToOrbTarget,
  mapHudOrbPayloadToSignals,
  screenPointToOrbTarget,
} from "./integration/signal-mapping";
export type { HudOrbPayload, HudOrbSignalOverrides } from "./integration/signal-mapping";
