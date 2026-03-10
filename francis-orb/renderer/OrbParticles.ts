import * as THREE from "three";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";
import { DeterministicRng } from "../core/deterministic-rng";

export class OrbParticles implements OrbRenderable {
  public readonly points: THREE.Points;
  private readonly positions: Float32Array;
  private readonly seeds: Float32Array;

  constructor(count: number, seed: number) {
    const rng = new DeterministicRng(seed);
    this.positions = new Float32Array(count * 3);
    this.seeds = new Float32Array(count);

    for (let i = 0; i < count; i += 1) {
      const r = rng.range(1.4, 2.6);
      const theta = rng.range(0, Math.PI * 2);
      const phi = Math.acos(rng.range(-1, 1));

      this.positions[i * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
      this.positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      this.positions[i * 3 + 2] = r * Math.cos(phi);
      this.seeds[i] = rng.range(0, Math.PI * 2);
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(this.positions, 3));

    const material = new THREE.PointsMaterial({
      color: 0xe4f5ff,
      size: 0.03,
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.points = new THREE.Points(geometry, material);
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const positionAttr = this.points.geometry.getAttribute("position") as THREE.BufferAttribute;

    for (let i = 0; i < positionAttr.count; i += 1) {
      const ix = i * 3;
      const x = this.positions[ix + 0];
      const y = this.positions[ix + 1];
      const z = this.positions[ix + 2];

      const angle = Math.atan2(y, x) + frame.dt * 0.16 * profile.particleSpeed;
      const radius = Math.sqrt(x * x + y * y);
      const dz = Math.sin(frame.elapsed * 0.7 + this.seeds[i]) * 0.0018 * profile.particleSpeed;

      this.positions[ix + 0] = Math.cos(angle) * radius;
      this.positions[ix + 1] = Math.sin(angle) * radius;
      this.positions[ix + 2] = z + dz;
    }

    positionAttr.needsUpdate = true;

    const material = this.points.material as THREE.PointsMaterial;
    material.opacity = profile.particleOpacity;
  }

  dispose(): void {
    this.points.geometry.dispose();
    (this.points.material as THREE.Material).dispose();
  }
}
