import * as THREE from "three";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";
import coreVertex from "./shaders/core.vertex.glsl";
import coreFragment from "./shaders/core.fragment.glsl";

export class OrbCore implements OrbRenderable {
  public readonly mesh: THREE.Mesh;
  private readonly material: THREE.ShaderMaterial;

  constructor(radius: number) {
    const geometry = new THREE.SphereGeometry(radius, 96, 96);

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
      depthWrite: false,
    });

    this.mesh = new THREE.Mesh(geometry, this.material);
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const pulse =
      1 +
      Math.sin(frame.elapsed * profile.pulseSpeed * Math.PI * 2) *
        profile.pulseAmplitude +
      (frame.state === "speaking" ? frame.speakingAmplitude * 0.08 : 0);

    this.mesh.scale.setScalar(pulse * profile.compression);

    this.material.uniforms.uTime.value = frame.elapsed;
    this.material.uniforms.uIntensity.value =
      profile.coreIntensity + frame.speakingAmplitude * 0.25;
    this.material.uniforms.uPulse.value = pulse;
    this.material.uniforms.uDistortion.value = profile.coreDistortion;
  }

  dispose(): void {
    this.mesh.geometry.dispose();
    this.material.dispose();
  }
}
