import * as THREE from "three";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";
import { getOrbPulseEnergy } from "../core/state-semantics";
import coreVertex from "./shaders/core.vertex.glsl";
import coreFragment from "./shaders/core.fragment.glsl";

export class OrbCore implements OrbRenderable {
  public readonly mesh: THREE.Mesh;
  private readonly material: THREE.ShaderMaterial;

  constructor(radius: number) {
    const geometry = new THREE.SphereGeometry(radius, 48, 48);

    this.material = new THREE.ShaderMaterial({
      vertexShader: coreVertex,
      fragmentShader: coreFragment,
      transparent: true,
      uniforms: {
        uTime: { value: 0 },
        uIntensity: { value: 1.0 },
        uPulse: { value: 1.0 },
        uDistortion: { value: 0.12 },
      },
      blending: THREE.AdditiveBlending,
      depthWrite: true,
      depthTest: true,
      toneMapped: false,
    });

    this.mesh = new THREE.Mesh(geometry, this.material);
    this.mesh.renderOrder = 3;
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const pulseEnergy = getOrbPulseEnergy(frame.state);
    const attentionStrength = Math.max(0, Math.min(1, Number(frame.attentionStrength ?? frame.confidence ?? 0.28)));
    const attentionLock = Math.max(0, Math.min(1, Number(frame.attentionLock ?? 0.18)));
    const attentionUncertainty = Math.max(0, Math.min(1, Number(frame.attentionUncertainty ?? 0.14)));
    const coreBrightness = Math.max(0, Math.min(1, Number(frame.visualCoreBrightness ?? 0.76)));
    const pulse =
      1 +
      Math.sin(frame.elapsed * profile.pulseSpeed * Math.PI * 2) *
        profile.pulseAmplitude * pulseEnergy +
      (frame.speakingAmplitude > 0 ? frame.speakingAmplitude * 0.018 : 0) +
      attentionStrength * 0.004 -
      attentionUncertainty * 0.005;

    const compactness =
      0.88 +
      attentionLock * 0.07 -
      attentionUncertainty * 0.03 +
      (1 - Math.max(0, Math.min(1, Number(profile.rootStillness ?? 0.62)))) * 0.02;
    this.mesh.scale.setScalar(pulse * Math.max(0.82, profile.compression * 0.94) * compactness);

    this.material.uniforms.uTime.value = frame.elapsed;
    this.material.uniforms.uIntensity.value =
      profile.coreIntensity +
      frame.speakingAmplitude * 0.04 +
      attentionStrength * 0.03 +
      attentionLock * 0.05 -
      attentionUncertainty * 0.05 +
      coreBrightness * 0.12;
    this.material.uniforms.uPulse.value = pulse;
    this.material.uniforms.uDistortion.value =
      profile.coreDistortion + attentionUncertainty * 0.006 - attentionLock * 0.004;
  }

  dispose(): void {
    this.mesh.geometry.dispose();
    this.material.dispose();
  }
}
