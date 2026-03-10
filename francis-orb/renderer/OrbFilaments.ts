import * as THREE from "three";
import { DeterministicRng } from "../core/deterministic-rng";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";
import filamentFragment from "./shaders/filament.fragment.glsl";
import filamentVertex from "./shaders/filament.vertex.glsl";

interface FilamentRecord {
  mesh: THREE.Mesh;
  material: THREE.ShaderMaterial;
  baseRotation: THREE.Euler;
  speed: THREE.Vector3;
}

function buildLoopPoints(
  radiusX: number,
  radiusY: number,
  wobble: number,
  segments: number,
  phase: number,
  swirl: number,
): THREE.Vector3[] {
  const points: THREE.Vector3[] = [];
  for (let i = 0; i <= segments; i += 1) {
    const t = (i / segments) * Math.PI * 2;
    const radialWave = 1 + Math.sin(t * 3 + phase) * swirl + Math.cos(t * 2 - phase * 0.65) * swirl * 0.45;
    const x = Math.cos(t) * radiusX * radialWave;
    const y = Math.sin(t) * radiusY * (1 - swirl * 0.14 * Math.cos(t * 2.5 + phase));
    const z =
      Math.sin(t * (2.1 + swirl * 1.4) + phase) * wobble +
      Math.cos(t * 3.2 - phase * 0.4) * wobble * 0.38;
    points.push(new THREE.Vector3(x, y, z));
  }
  return points;
}

function buildRibbonGeometry(
  points: THREE.Vector3[],
  options: {
    width: number;
    seed: number;
    phase: number;
  },
): THREE.BufferGeometry {
  const { width, seed, phase } = options;
  const count = points.length;
  const positions = new Float32Array(count * 2 * 3);
  const sideDirs = new Float32Array(count * 2 * 3);
  const sides = new Float32Array(count * 2);
  const along = new Float32Array(count * 2);
  const seeds = new Float32Array(count * 2);
  const phases = new Float32Array(count * 2);
  const indices: number[] = [];
  const up = new THREE.Vector3(0, 1, 0);

  for (let i = 0; i < count; i += 1) {
    const current = points[i];
    const prev = points[(i - 1 + count) % count];
    const next = points[(i + 1) % count];
    const tangent = next.clone().sub(prev).normalize();
    const radial = current.clone().normalize();
    let sideDir = tangent.clone().cross(radial);
    if (sideDir.lengthSq() < 1e-5) {
      sideDir = tangent.clone().cross(up);
    }
    if (sideDir.lengthSq() < 1e-5) {
      sideDir = new THREE.Vector3(1, 0, 0);
    }
    sideDir.normalize();

    const vertexBase = i * 2;
    const alongValue = i / Math.max(1, count - 1);

    for (let sideIndex = 0; sideIndex < 2; sideIndex += 1) {
      const vertexIndex = vertexBase + sideIndex;
      const side = sideIndex === 0 ? -1 : 1;
      const positionOffset = vertexIndex * 3;

      positions[positionOffset + 0] = current.x;
      positions[positionOffset + 1] = current.y;
      positions[positionOffset + 2] = current.z;

      sideDirs[positionOffset + 0] = sideDir.x;
      sideDirs[positionOffset + 1] = sideDir.y;
      sideDirs[positionOffset + 2] = sideDir.z;

      sides[vertexIndex] = side;
      along[vertexIndex] = alongValue;
      seeds[vertexIndex] = seed;
      phases[vertexIndex] = phase;
    }

    if (i < count - 1) {
      const start = i * 2;
      indices.push(start, start + 1, start + 2);
      indices.push(start + 1, start + 3, start + 2);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setIndex(indices);
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("aSideDir", new THREE.BufferAttribute(sideDirs, 3));
  geometry.setAttribute("aSide", new THREE.BufferAttribute(sides, 1));
  geometry.setAttribute("aAlong", new THREE.BufferAttribute(along, 1));
  geometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));
  geometry.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));
  geometry.computeBoundingSphere();

  const materialWidth = new Float32Array(count * 2);
  materialWidth.fill(width);
  geometry.setAttribute("aRibbonWidth", new THREE.BufferAttribute(materialWidth, 1));

  return geometry;
}

function createFilamentMaterial(width: number): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    vertexShader: filamentVertex,
    fragmentShader: filamentFragment,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uTime: { value: 0 },
      uOpacity: { value: 0.52 },
      uSpeed: { value: 0.5 },
      uTightness: { value: 1.0 },
      uRibbonWidth: { value: width },
    },
  });
}

export class OrbFilaments implements OrbRenderable {
  public readonly group = new THREE.Group();
  private readonly filaments: FilamentRecord[] = [];

  constructor(count: number, segments: number, seed: number) {
    const rng = new DeterministicRng(seed);

    for (let i = 0; i < count; i += 1) {
      const phase = rng.range(0, Math.PI * 2);
      const width = rng.range(0.04, 0.085);
      const points = buildLoopPoints(
        rng.range(1.03, 1.42),
        rng.range(0.66, 1.08),
        rng.range(0.025, 0.11),
        segments,
        phase,
        rng.range(0.05, 0.22),
      );

      const geometry = buildRibbonGeometry(points, {
        width,
        seed: rng.range(0, Math.PI * 2),
        phase,
      });
      const material = createFilamentMaterial(width);
      const mesh = new THREE.Mesh(geometry, material);
      const baseRotation = new THREE.Euler(
        rng.range(0, Math.PI),
        rng.range(0, Math.PI),
        rng.range(0, Math.PI),
      );

      mesh.rotation.copy(baseRotation);
      mesh.scale.setScalar(rng.range(0.88, 1.03));
      this.group.add(mesh);

      this.filaments.push({
        mesh,
        material,
        baseRotation,
        speed: new THREE.Vector3(
          rng.range(0.08, 0.24) * rng.sign(),
          rng.range(0.08, 0.22) * rng.sign(),
          rng.range(0.05, 0.16) * rng.sign(),
        ),
      });
    }
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    for (const filament of this.filaments) {
      const speed = profile.filamentSpeed;
      filament.mesh.rotation.x = filament.baseRotation.x + frame.elapsed * filament.speed.x * speed;
      filament.mesh.rotation.y = filament.baseRotation.y + frame.elapsed * filament.speed.y * speed;
      filament.mesh.rotation.z = filament.baseRotation.z + frame.elapsed * filament.speed.z * speed;

      const wobble = 1 + Math.sin(frame.elapsed * 1.65 + filament.speed.x * 10.0) * 0.018;
      const tight = profile.filamentTightness * profile.compression;
      filament.mesh.scale.setScalar(wobble * tight);

      filament.material.uniforms.uTime.value = frame.elapsed;
      filament.material.uniforms.uOpacity.value = profile.filamentOpacity;
      filament.material.uniforms.uSpeed.value = speed;
      filament.material.uniforms.uTightness.value = tight;
    }
  }

  dispose(): void {
    for (const filament of this.filaments) {
      filament.mesh.geometry.dispose();
      filament.material.dispose();
    }
  }
}
