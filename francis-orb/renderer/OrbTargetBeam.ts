import * as THREE from "three";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";
import { shouldRenderOrbBeam } from "../core/state-semantics";

export class OrbTargetBeam implements OrbRenderable {
  public readonly mesh: THREE.Mesh;
  private readonly material: THREE.MeshBasicMaterial;
  private readonly temp = new THREE.Vector3();
  private readonly origin = new THREE.Vector3(0, 0, 0);

  constructor() {
    const geometry = new THREE.CylinderGeometry(0.004, 0.014, 1, 10, 1, true);
    geometry.translate(0, 0.5, 0);

    this.material = new THREE.MeshBasicMaterial({
      color: 0xf2f8ff,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    });

    this.mesh = new THREE.Mesh(geometry, this.material);
    this.mesh.visible = false;
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const beamTarget = frame.actionTarget ?? (frame.state === "target_lock" ? frame.attentionTarget : null);
    if (!shouldRenderOrbBeam(frame.state) || !beamTarget) {
      this.mesh.visible = false;
      this.material.opacity = 0;
      return;
    }

    const target = beamTarget.clone();
    const direction = target.clone().sub(this.origin);
    const length = direction.length();

    if (length < 0.001) {
      this.mesh.visible = false;
      this.material.opacity = 0;
      return;
    }

    this.mesh.visible = true;
    this.mesh.lookAt(target);
    this.mesh.scale.set(1, length, 1);

    this.temp.copy(this.origin).add(target).multiplyScalar(0.5);
    this.mesh.position.copy(this.temp);

    const strength = frame.actionTarget
      ? frame.actionStrength ?? 1
      : Math.max(0.18, Math.min(0.54, Number(frame.attentionLock ?? frame.attentionStrength ?? 0.24)));
    this.material.opacity = profile.beamOpacity * strength * 0.54;
  }

  dispose(): void {
    this.mesh.geometry.dispose();
    this.material.dispose();
  }
}
