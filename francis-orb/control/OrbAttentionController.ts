import * as THREE from "three";
import { ORB_CONFIG } from "../core/config";
import { vec3Lerp } from "../core/math";

export class OrbAttentionController {
  private readonly current = new THREE.Vector3(0, 0, 0);

  update(target?: THREE.Vector3 | null): THREE.Vector3 {
    const desired = target ?? new THREE.Vector3(0, 0, 0);
    return vec3Lerp(this.current, desired, ORB_CONFIG.attentionLerp);
  }

  get value(): THREE.Vector3 {
    return this.current;
  }
}
