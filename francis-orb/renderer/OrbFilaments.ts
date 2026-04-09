import * as THREE from "three";
import { DeterministicRng } from "../core/deterministic-rng";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";
import { getOrbMotionEnergy } from "../core/state-semantics";
import filamentFragment from "./shaders/filament.fragment.glsl";
import filamentVertex from "./shaders/filament.vertex.glsl";

interface FilamentRecord {
  group: THREE.Group;
  mesh: THREE.Mesh;
  material: THREE.ShaderMaterial;
  layer: "inner" | "mid" | "outer";
  baseQuaternion: THREE.Quaternion;
  orbitAxisPrimary: THREE.Vector3;
  orbitAxisSecondary: THREE.Vector3;
  orbitAxisTertiary: THREE.Vector3;
  orbitRatePrimary: number;
  orbitRateSecondary: number;
  orbitRateTertiary: number;
  orbitPhasePrimary: number;
  orbitPhaseSecondary: number;
  orbitPhaseTertiary: number;
  weaveRate: number;
  weavePhase: number;
  breatheRate: number;
  breathePhase: number;
  baseScale: number;
  localSpin: THREE.Vector3;
  speedScalar: number;
  continuity: number;
  opacityScalar: number;
  arcCenterA: number;
  arcCenterB: number;
  arcCenterC: number;
  arcSpanA: number;
  arcSpanB: number;
  arcSpanC: number;
  arcSoftness: number;
}

function wrapUnit(value: number): number {
  return value - Math.floor(value);
}

function randomUnitVector(rng: DeterministicRng): THREE.Vector3 {
  const theta = rng.range(0, Math.PI * 2);
  const z = rng.range(-1, 1);
  const radius = Math.sqrt(Math.max(0, 1 - z * z));
  return new THREE.Vector3(radius * Math.cos(theta), radius * Math.sin(theta), z).normalize();
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
    const radialWaveA =
      1 +
      Math.sin(t * 1.42 + phase) * swirl * 0.1 +
      Math.cos(t * 3.1 - phase * 0.5) * swirl * 0.045;
    const radialWaveB =
      1 +
      Math.cos(t * 1.76 - phase * 0.36) * swirl * 0.08 +
      Math.sin(t * 2.8 + phase * 0.28) * swirl * 0.03;
    const x = Math.cos(t) * radiusX * radialWaveA;
    const y = Math.sin(t) * radiusY * radialWaveB;
    const z =
      Math.sin(t * (1.32 + swirl * 0.58) + phase) * wobble +
      Math.cos(t * 2.6 - phase * 0.42) * wobble * 0.18;
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
    depthTest: true,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
    uniforms: {
      uTime: { value: 0 },
      uOpacity: { value: 0.92 },
      uSpeed: { value: 0.5 },
      uTightness: { value: 1.0 },
      uRibbonWidth: { value: width },
      uContinuity: { value: 0.7 },
      uArcCenterA: { value: 0.18 },
      uArcCenterB: { value: 0.54 },
      uArcCenterC: { value: 0.82 },
      uArcSpanA: { value: 0.16 },
      uArcSpanB: { value: 0.12 },
      uArcSpanC: { value: 0.08 },
      uArcSoftness: { value: 0.06 },
    },
  });
}

export class OrbFilaments implements OrbRenderable {
  public readonly group = new THREE.Group();
  private readonly filaments: FilamentRecord[] = [];
  private readonly tempQuatA = new THREE.Quaternion();
  private readonly tempQuatB = new THREE.Quaternion();
  private readonly tempQuatC = new THREE.Quaternion();
  private readonly tempDirection = new THREE.Vector3();
  private readonly tempLateral = new THREE.Vector3();
  private readonly tempBias = new THREE.Vector3();

  constructor(count: number, segments: number, seed: number) {
    const rng = new DeterministicRng(seed);

    for (let i = 0; i < count; i += 1) {
      const layerRatio = i / Math.max(1, count - 1);
      const layer: FilamentRecord["layer"] =
        layerRatio < 0.42 ? "inner" : layerRatio < 0.84 ? "mid" : "outer";
      const phase = rng.range(0, Math.PI * 2);
      const width =
        layer === "inner"
          ? rng.range(0.016, 0.03)
          : layer === "mid"
            ? rng.range(0.013, 0.024)
            : rng.range(0.01, 0.018);
      const orbitalRadius =
        layer === "inner"
          ? rng.range(0.5, 0.78)
          : layer === "mid"
            ? rng.range(0.78, 1.08)
            : rng.range(1.02, 1.28);
      const points = buildLoopPoints(
        orbitalRadius * rng.range(0.72, 1.06),
        orbitalRadius * rng.range(0.48, 0.94),
        layer === "outer" ? rng.range(0.01, 0.026) : rng.range(0.008, 0.02),
        segments,
        phase,
        layer === "inner" ? rng.range(0.03, 0.07) : rng.range(0.04, 0.1),
      );

      const geometry = buildRibbonGeometry(points, {
        width,
        seed: rng.range(0, Math.PI * 2),
        phase,
      });
      const material = createFilamentMaterial(width);
      const mesh = new THREE.Mesh(geometry, material);
      const group = new THREE.Group();
      const baseRotation = new THREE.Euler(
        rng.range(0, Math.PI * 2),
        rng.range(0, Math.PI * 2),
        rng.range(0, Math.PI * 2),
      );
      const baseQuaternion = new THREE.Quaternion().setFromEuler(baseRotation);
      const baseScale =
        layer === "inner"
          ? rng.range(0.94, 1.04)
          : layer === "mid"
            ? rng.range(0.98, 1.08)
            : rng.range(1.0, 1.1);

      group.quaternion.copy(baseQuaternion);
      group.scale.setScalar(baseScale);
      mesh.renderOrder = layer === "inner" ? 7 : layer === "mid" ? 6 : 5;
      mesh.rotation.set(
        rng.range(-0.1, 0.1),
        rng.range(-0.1, 0.1),
        rng.range(-0.1, 0.1),
      );
      group.add(mesh);
      this.group.add(group);

      this.filaments.push({
        group,
        mesh,
        material,
        layer,
        baseQuaternion,
        orbitAxisPrimary: randomUnitVector(rng),
        orbitAxisSecondary: randomUnitVector(rng),
        orbitAxisTertiary: randomUnitVector(rng),
        orbitRatePrimary: rng.range(0.12, 0.34),
        orbitRateSecondary: rng.range(0.05, 0.18),
        orbitRateTertiary: rng.range(0.02, 0.1),
        orbitPhasePrimary: rng.range(0, Math.PI * 2),
        orbitPhaseSecondary: rng.range(0, Math.PI * 2),
        orbitPhaseTertiary: rng.range(0, Math.PI * 2),
        weaveRate: rng.range(0.16, 0.42),
        weavePhase: rng.range(0, Math.PI * 2),
        breatheRate: rng.range(0.12, 0.3),
        breathePhase: rng.range(0, Math.PI * 2),
        baseScale,
        localSpin: new THREE.Vector3(
          rng.range(0.012, 0.05) * rng.sign(),
          rng.range(0.012, 0.05) * rng.sign(),
          rng.range(0.01, 0.04) * rng.sign(),
        ),
        speedScalar:
          layer === "inner"
            ? rng.range(0.84, 1.02)
            : layer === "mid"
              ? rng.range(0.9, 1.08)
              : rng.range(0.94, 1.14),
        continuity:
          layer === "inner"
            ? rng.range(0.34, 0.64)
            : layer === "mid"
              ? rng.range(0.18, 0.48)
              : rng.range(0.08, 0.28),
        opacityScalar:
          layer === "inner"
            ? rng.range(1.12, 1.34)
            : layer === "mid"
              ? rng.range(0.94, 1.18)
              : rng.range(0.72, 0.96),
        arcCenterA: rng.range(0, 1),
        arcCenterB: rng.range(0, 1),
        arcCenterC: rng.range(0, 1),
        arcSpanA:
          layer === "inner"
            ? rng.range(0.08, 0.16)
            : layer === "mid"
              ? rng.range(0.07, 0.14)
              : rng.range(0.05, 0.12),
        arcSpanB:
          layer === "inner"
            ? rng.range(0.04, 0.1)
            : layer === "mid"
              ? rng.range(0.035, 0.08)
              : rng.range(0.025, 0.07),
        arcSpanC:
          layer === "inner"
            ? rng.range(0.03, 0.08)
            : layer === "mid"
              ? rng.range(0.024, 0.06)
              : rng.range(0.018, 0.05),
        arcSoftness: rng.range(0.02, 0.05),
      });

    }
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const motionEnergy = getOrbMotionEnergy(frame.state);
    const attentionStrength = Math.max(0, Math.min(1, Number(frame.attentionStrength ?? frame.confidence ?? 0.28)));
    const attentionLock = Math.max(0, Math.min(1, Number(frame.attentionLock ?? 0.18)));
    const attentionUncertainty = Math.max(0, Math.min(1, Number(frame.attentionUncertainty ?? 0.14)));
    const ringDensity = Math.max(0, Math.min(1, Number(frame.visualRingDensity ?? 0.72)));
    const ringTightness = Math.max(0, Math.min(1, Number(frame.visualRingTightness ?? 0.72)));
    const orbitSpeedBias = Math.max(0, Math.min(1, Number(frame.visualOrbitSpeed ?? 0.68)));
    const directionalTarget = frame.actionTarget ?? frame.attentionTarget ?? null;
    const hasDirectionalTarget = Boolean(directionalTarget && directionalTarget.lengthSq() > 1e-4);
    const biasStrengthBase = frame.actionTarget
      ? Math.max(0.42, Math.min(1, Number(frame.actionStrength ?? 0.54)))
      : Math.max(0.14, attentionStrength * 0.54 + attentionLock * 0.34 - attentionUncertainty * 0.12);
    const directionProfileBias = Math.max(0, profile.directionalBias);
    if (directionalTarget && directionalTarget.lengthSq() > 1e-4) {
      this.tempDirection.copy(directionalTarget).normalize();
      this.tempLateral.set(-this.tempDirection.y, this.tempDirection.x, 0);
      if (this.tempLateral.lengthSq() < 1e-4) {
        this.tempLateral.set(0, 1, 0);
      } else {
        this.tempLateral.normalize();
      }
    } else {
      this.tempDirection.set(0, 0, 0);
      this.tempLateral.set(0, 0, 0);
    }

    for (const filament of this.filaments) {
      const layerSpeedBias =
        filament.layer === "inner" ? 0.92 : filament.layer === "mid" ? 1.0 : 1.08;
      const layerBiasScalar =
        filament.layer === "inner" ? 1.0 : filament.layer === "mid" ? 0.78 : 0.56;
      const layerOrbitRange =
        (filament.layer === "inner" ? 0.18 : filament.layer === "mid" ? 0.28 : 0.38) *
        Math.max(0.22, profile.filamentDrift);
      const speed =
        profile.filamentSpeed *
        Math.max(
          0.16,
          0.7 +
            motionEnergy * 0.46 +
            attentionStrength * 0.08 -
            attentionLock * 0.02 +
            attentionUncertainty * 0.02 +
            orbitSpeedBias * 0.12,
        );
      const ringSpeed = speed * filament.speedScalar * layerSpeedBias;
      const primaryOrbit =
        Math.sin(frame.elapsed * filament.orbitRatePrimary * ringSpeed + filament.orbitPhasePrimary) *
        (layerOrbitRange + attentionStrength * 0.03 + motionEnergy * 0.02 - attentionUncertainty * 0.02);
      const secondaryOrbit =
        Math.cos(frame.elapsed * filament.orbitRateSecondary * ringSpeed + filament.orbitPhaseSecondary) *
        (layerOrbitRange * 0.46 + attentionLock * 0.03 - attentionUncertainty * 0.02);
      const tertiaryOrbit =
        Math.sin(frame.elapsed * filament.orbitRateTertiary * ringSpeed + filament.orbitPhaseTertiary) *
        (layerOrbitRange * 0.22 + attentionUncertainty * 0.03);

      filament.group.quaternion.copy(filament.baseQuaternion);
      filament.group.quaternion.multiply(
        this.tempQuatA.setFromAxisAngle(filament.orbitAxisPrimary, primaryOrbit),
      );
      filament.group.quaternion.multiply(
        this.tempQuatB.setFromAxisAngle(filament.orbitAxisSecondary, secondaryOrbit),
      );
      filament.group.quaternion.multiply(
        this.tempQuatC.setFromAxisAngle(filament.orbitAxisTertiary, tertiaryOrbit),
      );

      filament.mesh.rotation.x =
        Math.sin(frame.elapsed * (filament.weaveRate + filament.localSpin.x * 0.06) * ringSpeed + filament.weavePhase) *
        (0.055 * Math.max(0.28, profile.filamentDrift));
      filament.mesh.rotation.y =
        Math.cos(frame.elapsed * (filament.weaveRate * 0.82 + filament.localSpin.y * 0.05) * ringSpeed + filament.weavePhase * 0.8) *
        (0.045 * Math.max(0.28, profile.filamentDrift));
      filament.mesh.rotation.z =
        Math.sin(frame.elapsed * (filament.weaveRate * 0.54 + Math.abs(filament.localSpin.z) * 0.05) * ringSpeed + filament.weavePhase * 1.2) *
        (0.035 * Math.max(0.28, profile.filamentDrift));

      const wobble =
        1 +
        Math.sin(frame.elapsed * filament.breatheRate + filament.breathePhase) *
          ((0.01 + motionEnergy * (filament.layer === "outer" ? 0.016 : 0.01)) * Math.max(0.22, profile.filamentDrift));
      const layerTightBias =
        filament.layer === "inner" ? 1.08 : filament.layer === "mid" ? 1.0 : 0.92;
      const tight =
        profile.filamentTightness *
        profile.compression *
        layerTightBias *
        Math.max(
          0.84,
          0.96 +
            attentionStrength * 0.03 +
            attentionLock * 0.12 -
            attentionUncertainty * 0.08 +
            ringTightness * 0.08,
        );
      filament.group.scale.setScalar(filament.baseScale * wobble * tight);

      if (hasDirectionalTarget) {
        const directionalBias = directionProfileBias * biasStrengthBase * layerBiasScalar;
        const forwardBias =
          frame.state === "investigate"
            ? 0.08 + attentionStrength * 0.04
            : frame.state === "target_lock"
              ? 0.11 + attentionLock * 0.04
              : frame.state === "commit_move" || frame.state === "hover_ready" || frame.state === "click_act" || frame.state === "drag_act" || frame.state === "type_hold"
                ? 0.16 + biasStrengthBase * 0.05
                : frame.state === "interrupted"
                  ? -0.05
                  : 0.04;
        const lateralBias =
          frame.state === "investigate"
            ? 0.09 + attentionUncertainty * 0.04
            : frame.state === "blocked"
              ? -0.016
              : frame.state === "interrupted"
                ? -0.028
                : 0.012;

        this.tempBias
          .copy(this.tempDirection)
          .multiplyScalar(directionalBias * forwardBias)
          .addScaledVector(this.tempLateral, directionalBias * lateralBias);
        filament.group.position.copy(this.tempBias);
      } else {
        filament.group.position.set(0, 0, 0);
      }

      filament.material.uniforms.uTime.value = frame.elapsed;
      filament.material.uniforms.uOpacity.value =
        profile.filamentOpacity *
        filament.opacityScalar *
        (0.98 + ringDensity * 0.42) *
        (filament.layer === "inner" ? 1.0 : filament.layer === "mid" ? 0.96 : 0.84);
      filament.material.uniforms.uSpeed.value = ringSpeed;
      filament.material.uniforms.uTightness.value = tight;
      filament.material.uniforms.uContinuity.value = Math.max(
        0.04,
        Math.min(
          0.82,
          profile.filamentContinuity +
            filament.continuity * 0.34 +
            attentionLock * (filament.layer === "inner" ? 0.18 : 0.1) -
            attentionUncertainty * 0.1 -
            Math.max(0, profile.filamentDrift - 0.5) * 0.08,
        ),
      );
      filament.material.uniforms.uArcCenterA.value = wrapUnit(
        filament.arcCenterA + Math.sin(frame.elapsed * filament.orbitRateSecondary * 0.2 + filament.weavePhase) * 0.012,
      );
      filament.material.uniforms.uArcCenterB.value = wrapUnit(
        filament.arcCenterB + Math.cos(frame.elapsed * filament.orbitRatePrimary * 0.16 + filament.weavePhase * 0.7) * 0.01,
      );
      filament.material.uniforms.uArcCenterC.value = wrapUnit(
        filament.arcCenterC + Math.sin(frame.elapsed * filament.orbitRateTertiary * 0.26 + filament.weavePhase * 1.2) * 0.008,
      );
      filament.material.uniforms.uArcSpanA.value =
        filament.arcSpanA * profile.filamentSpread * Math.max(0.74, 1 - attentionLock * 0.12 + attentionUncertainty * 0.08);
      filament.material.uniforms.uArcSpanB.value =
        filament.arcSpanB * profile.filamentSpread * Math.max(0.76, 1 - attentionLock * 0.1 + attentionUncertainty * 0.08);
      filament.material.uniforms.uArcSpanC.value =
        filament.arcSpanC * profile.filamentSpread * Math.max(0.78, 1 - attentionLock * 0.08 + attentionUncertainty * 0.08);
      filament.material.uniforms.uArcSoftness.value =
        filament.arcSoftness * (1 + attentionUncertainty * 0.12 + Math.max(0, profile.filamentDrift - 0.5) * 0.08);
    }
  }

  dispose(): void {
    for (const filament of this.filaments) {
      filament.mesh.geometry.dispose();
      filament.material.dispose();
    }
  }
}
