import * as THREE from "three";
import { ORB_CONFIG } from "../core/config";
import { vec3Lerp } from "../core/math";
import type { OrbAttentionState } from "../core/types";

export interface OrbAttentionInput {
  target?: THREE.Vector3 | null;
  state?: OrbAttentionState | null;
  strength?: number;
  lock?: number;
  uncertainty?: number;
  elapsed?: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function normalizeAttentionState(value: OrbAttentionState | string | null | undefined): OrbAttentionState {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "investigate" || normalized === "target_lock" || normalized === "reassess") {
    return normalized;
  }
  return "idle";
}

export class OrbAttentionController {
  private readonly current = new THREE.Vector3(0, 0, 0);
  private readonly desired = new THREE.Vector3(0, 0, 0);
  private readonly neutral = new THREE.Vector3(0, 0, 0);
  private readonly offset = new THREE.Vector3(0, 0, 0);

  update(input: OrbAttentionInput = {}): THREE.Vector3 {
    const state = normalizeAttentionState(input.state);
    const target = input.target ?? this.neutral;
    const strength = clamp(Number(input.strength ?? 0.32), 0, 1);
    const lock = clamp(Number(input.lock ?? 0.18), 0, 1);
    const uncertainty = clamp(Number(input.uncertainty ?? 0.16), 0, 1);
    const elapsed = Number(input.elapsed ?? 0);

    this.desired.copy(target);
    this.offset.set(0, 0, 0);

    if (state === "investigate") {
      const radius = 0.12 + strength * 0.26 + uncertainty * 0.08;
      this.offset.set(
        Math.sin(elapsed * 0.92) * radius,
        Math.cos(elapsed * 1.18) * radius * 0.62,
        0,
      );
      this.desired.add(this.offset);
    } else if (state === "target_lock") {
      const radius = 0.016 + (1 - lock) * 0.06 + uncertainty * 0.02;
      this.offset.set(
        Math.sin(elapsed * 0.44) * radius,
        Math.cos(elapsed * 0.58) * radius * 0.48,
        0,
      );
      this.desired.add(this.offset);
    } else if (state === "reassess") {
      const retreat = 0.34 + uncertainty * 0.22;
      this.desired.multiplyScalar(Math.max(0.18, 1 - retreat));
      const radius = 0.08 + uncertainty * 0.12;
      this.offset.set(
        Math.sin(elapsed * 0.56) * radius,
        Math.cos(elapsed * 0.76) * radius * 0.52,
        0,
      );
      this.desired.add(this.offset);
    } else if (!input.target) {
      this.desired.copy(this.neutral);
    }

    const lerpAmount = state === "target_lock"
      ? clamp(ORB_CONFIG.attentionLerp + 0.03 + lock * 0.08 - uncertainty * 0.02, 0.05, 0.2)
      : state === "investigate"
        ? clamp(ORB_CONFIG.attentionLerp + 0.01 + strength * 0.05 - uncertainty * 0.01, 0.04, 0.14)
        : state === "reassess"
          ? clamp(ORB_CONFIG.attentionLerp + 0.008 + uncertainty * 0.03, 0.04, 0.12)
          : ORB_CONFIG.attentionLerp;
    return vec3Lerp(this.current, this.desired, lerpAmount);
  }

  get value(): THREE.Vector3 {
    return this.current;
  }
}
