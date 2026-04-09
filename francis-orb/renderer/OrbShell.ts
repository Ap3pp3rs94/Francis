import * as THREE from "three";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";
import { getOrbSettleEnergy, getOrbStateBoost } from "../core/state-semantics";
import shellVertex from "./shaders/shell.vertex.glsl";
import shellFragment from "./shaders/shell.fragment.glsl";

export class OrbShell implements OrbRenderable {
  public readonly mesh: THREE.Mesh;
  private readonly material: THREE.ShaderMaterial;

  constructor(radius: number) {
    const geometry = new THREE.SphereGeometry(radius, 40, 40);

    this.material = new THREE.ShaderMaterial({
      vertexShader: shellVertex,
      fragmentShader: shellFragment,
      transparent: true,
      side: THREE.DoubleSide,
      uniforms: {
        uTime: { value: 0 },
        uOpacity: { value: 0.018 },
        uFresnelPower: { value: 4.6 },
        uActivity: { value: 0 },
        uPulse: { value: 1.0 },
        uNoiseDensity: { value: 0.6 },
        uRefractionStrength: { value: 0.02 },
      },
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      depthTest: true,
      toneMapped: false,
    });

    this.mesh = new THREE.Mesh(geometry, this.material);
    this.mesh.renderOrder = 2;
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const settleEnergy = getOrbSettleEnergy(frame.state);
    const breathe = 1 + Math.sin(frame.elapsed * 0.48) * (0.002 * settleEnergy);
    const stateBoost = getOrbStateBoost(frame.state);
    const attentionStrength = Math.max(0, Math.min(1, Number(frame.attentionStrength ?? frame.confidence ?? 0.28)));
    const attentionLock = Math.max(0, Math.min(1, Number(frame.attentionLock ?? 0.18)));
    const attentionUncertainty = Math.max(0, Math.min(1, Number(frame.attentionUncertainty ?? 0.14)));
    const activity = Math.min(
      1,
      stateBoost +
        frame.speakingAmplitude * 0.6 +
        attentionStrength * 0.2 +
        attentionLock * 0.16 -
        attentionUncertainty * 0.08,
    );
    const shimmer =
      1 +
      Math.sin(frame.elapsed * (profile.pulseSpeed * Math.PI * 1.2 + 0.4)) *
        ((0.003 + profile.pulseAmplitude * 0.08 + activity * 0.008) * settleEnergy);

    this.mesh.scale.setScalar(breathe * Math.max(0.82, profile.compression * 0.9));

    this.material.uniforms.uTime.value = frame.elapsed;
    this.material.uniforms.uOpacity.value = profile.shellOpacity;
    this.material.uniforms.uFresnelPower.value = profile.shellFresnelPower;
    this.material.uniforms.uActivity.value = activity;
    this.material.uniforms.uPulse.value = shimmer;
    this.material.uniforms.uNoiseDensity.value =
      0.42 +
      profile.coreDistortion * 0.42 +
      (1 - profile.compression) * 0.18 +
      stateBoost * 0.04 +
      attentionUncertainty * 0.06 -
      attentionLock * 0.04;
    this.material.uniforms.uRefractionStrength.value =
      0.008 +
      profile.coreDistortion * 0.14 +
      activity * 0.015 +
      attentionLock * 0.012 -
      attentionUncertainty * 0.01;
  }

  dispose(): void {
    this.mesh.geometry.dispose();
    this.material.dispose();
  }
}
