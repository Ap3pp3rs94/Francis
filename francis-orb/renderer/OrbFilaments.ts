import * as THREE from "three";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";
import { DeterministicRng } from "../core/deterministic-rng";

interface FilamentRecord {
  line: THREE.LineLoop;
  baseRotation: THREE.Euler;
  speed: THREE.Vector3;
}

function buildLoopPoints(radiusX: number, radiusY: number, wobble: number, segments: number): THREE.Vector3[] {
  const points: THREE.Vector3[] = [];
  for (let i = 0; i <= segments; i += 1) {
    const t = (i / segments) * Math.PI * 2;
    const z = Math.sin(t * 2.0) * wobble;
    points.push(new THREE.Vector3(Math.cos(t) * radiusX, Math.sin(t) * radiusY, z));
  }
  return points;
}

export class OrbFilaments implements OrbRenderable {
  public readonly group = new THREE.Group();
  private readonly filaments: FilamentRecord[] = [];

  constructor(count: number, segments: number, seed: number) {
    const rng = new DeterministicRng(seed);

    for (let i = 0; i < count; i += 1) {
      const points = buildLoopPoints(
        rng.range(1.1, 1.55),
        rng.range(0.72, 1.25),
        rng.range(0.03, 0.12),
        segments,
      );

      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const material = new THREE.LineBasicMaterial({
        color: 0xd6efff,
        transparent: true,
        opacity: 0.45,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });

      const line = new THREE.LineLoop(geometry, material);
      const baseRotation = new THREE.Euler(
        rng.range(0, Math.PI),
        rng.range(0, Math.PI),
        rng.range(0, Math.PI),
      );

      line.rotation.copy(baseRotation);
      line.scale.setScalar(rng.range(0.94, 1.1));
      this.group.add(line);

      this.filaments.push({
        line,
        baseRotation,
        speed: new THREE.Vector3(
          rng.range(0.1, 0.4) * rng.sign(),
          rng.range(0.1, 0.35) * rng.sign(),
          rng.range(0.08, 0.24) * rng.sign(),
        ),
      });
    }
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    for (const filament of this.filaments) {
      const speed = profile.filamentSpeed;
      filament.line.rotation.x = filament.baseRotation.x + frame.elapsed * filament.speed.x * speed;
      filament.line.rotation.y = filament.baseRotation.y + frame.elapsed * filament.speed.y * speed;
      filament.line.rotation.z = filament.baseRotation.z + frame.elapsed * filament.speed.z * speed;

      const wobble = 1 + Math.sin(frame.elapsed * 1.4 + filament.speed.x * 10.0) * 0.02;
      const tight = profile.filamentTightness * profile.compression;
      filament.line.scale.setScalar(wobble * tight);

      const material = filament.line.material as THREE.LineBasicMaterial;
      material.opacity = profile.filamentOpacity;
    }
  }

  dispose(): void {
    for (const filament of this.filaments) {
      filament.line.geometry.dispose();
      (filament.line.material as THREE.Material).dispose();
    }
  }
}
