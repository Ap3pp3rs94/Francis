import * as THREE from "three";
import { ORB_CONFIG } from "../core/config";
import { clamp, lerp, vec3Lerp } from "../core/math";

export class OrbActionController {
  private readonly currentTarget = new THREE.Vector3(0, 0, 0);
  private readonly neutralTarget = new THREE.Vector3(0, 0, 0);
  private currentStrength = 0;

  update(
    target?: THREE.Vector3 | null,
    strength = 0,
  ): { target: THREE.Vector3 | null; strength: number } {
    const nextTarget = target ?? this.neutralTarget;
    vec3Lerp(this.currentTarget, nextTarget, ORB_CONFIG.beamLerp);
    this.currentStrength = lerp(
      this.currentStrength,
      target ? clamp(strength, 0, 1) : 0,
      ORB_CONFIG.beamLerp,
    );

    if (!target && this.currentStrength < 0.02) {
      return { target: null, strength: 0 };
    }

    return {
      target: this.currentTarget.clone(),
      strength: this.currentStrength,
    };
  }

  get value(): { target: THREE.Vector3 | null; strength: number } {
    return {
      target: this.currentStrength > 0.02 ? this.currentTarget.clone() : null,
      strength: this.currentStrength,
    };
  }
}
