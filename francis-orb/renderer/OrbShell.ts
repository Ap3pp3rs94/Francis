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
        uOpacity: { value: 0.1 },
        uFresnelPower: { value: 2.2 },
      },
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.mesh = new THREE.Mesh(geometry, this.material);
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const breathe = 1 + Math.sin(frame.elapsed * 0.7) * 0.006;
    this.mesh.scale.setScalar(breathe * profile.compression);

    this.material.uniforms.uOpacity.value = profile.shellOpacity;
    this.material.uniforms.uFresnelPower.value = profile.shellFresnelPower;
  }

  dispose(): void {
    this.mesh.geometry.dispose();
    this.material.dispose();
  }
}
