import * as THREE from "three";
import type { FrancisOrbEngineOptions } from "../core/types";
import { FrancisOrbEngine } from "../renderer/FrancisOrbEngine";
import { InterjectionPolicy } from "../policy/InterjectionPolicy";

export function createFrancisOrb(
  container: HTMLElement,
  options: Partial<Omit<FrancisOrbEngineOptions, "container">> = {},
) {
  const orb = new FrancisOrbEngine({
    container,
    seed: 77,
    background: 0x000000,
    usePostFX: true,
    enableBeam: true,
    transparentBackground: true,
    ...options,
  });

  const policy = new InterjectionPolicy();
  orb.start();

  return {
    orb,
    setIdle() {
      orb.setSignals({ state: "idle" });
    },
    setListening() {
      orb.setSignals({ state: "listening" });
    },
    setThinking(confidence = 1.0) {
      const decision = policy.decide({
        confidence,
        missingRequiredField: false,
        confirmationRequired: false,
        conflictingIntent: false,
        permissionBlocked: false,
        unsafeAction: false,
      });

      orb.setSignals({
        state: decision.interject ? "interject" : "thinking",
        confidence,
        interjectionIntent: decision.interject,
      });
    },
    setSpeaking(amplitude: number) {
      orb.setSignals({
        state: "speaking",
        speakingAmplitude: amplitude,
      });
    },
    setActing(target: THREE.Vector3, strength = 1) {
      orb.setSignals({
        state: "acting",
        actionTarget: target,
        actionStrength: strength,
        attentionTarget: target,
      });
    },
    dispose() {
      orb.dispose();
    },
  };
}
