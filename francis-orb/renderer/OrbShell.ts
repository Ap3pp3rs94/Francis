import * as THREE from "three";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";
import shellVertex from "./shaders/shell.vertex.glsl";
import shellFragment from "./shaders/shell.fragment.glsl";

export class OrbShell implements OrbRenderable {
  public readonly mesh: THREE.Mesh;
  private readonly material: THREE.ShaderMaterial;

  constructor(radius: number) {
    const geometry = new THREE.SphereGeometry(radius, 96, 96);

    this.material = new THREE.ShaderMaterial({
      vertexShader: shellVertex,
      fragmentShader: shellFragment,
      transparent: true,
      side: THREE.DoubleSide,
      uniforms: {
        uTime: { value: 0 },
        uOpacity: { value: 0.1 },
        uFresnelPower: { value: 2.2 },
        uActivity: { value: 0 },
        uPulse: { value: 1.0 },
        uNoiseDensity: { value: 1.0 },
        uRefractionStrength: { value: 0.45 },
      },
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      toneMapped: false,
    });

    this.mesh = new THREE.Mesh(geometry, this.material);
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const breathe = 1 + Math.sin(frame.elapsed * 0.7) * 0.006;
    const stateBoost =
      frame.state === "interject"
        ? 0.33
        : frame.state === "acting"
          ? 0.28
          : frame.state === "speaking"
            ? 0.24
            : frame.state === "thinking"
              ? 0.18
              : frame.state === "listening"
                ? 0.12
                : frame.state === "error"
                  ? 0.08
                  : 0;
    const activity = Math.min(1, stateBoost + frame.speakingAmplitude * 0.9);
    const shimmer =
      1 +
      Math.sin(frame.elapsed * (profile.pulseSpeed * Math.PI * 1.5 + 0.5)) *
        (0.03 + profile.pulseAmplitude * 0.6 + activity * 0.03);

    this.mesh.scale.setScalar(breathe * profile.compression);

    this.material.uniforms.uTime.value = frame.elapsed;
    this.material.uniforms.uOpacity.value = profile.shellOpacity;
    this.material.uniforms.uFresnelPower.value = profile.shellFresnelPower;
    this.material.uniforms.uActivity.value = activity;
    this.material.uniforms.uPulse.value = shimmer;
    this.material.uniforms.uNoiseDensity.value =
      1 + profile.coreDistortion * 1.8 + (1 - profile.compression) * 1.2 + stateBoost * 0.25;
    this.material.uniforms.uRefractionStrength.value =
      0.34 + profile.coreDistortion * 1.45 + activity * 0.18;
  }

  dispose(): void {
    this.mesh.geometry.dispose();
    this.material.dispose();
  }
}
