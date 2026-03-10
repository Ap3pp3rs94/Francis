import * as THREE from "three";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";

function createAuraTexture(size = 512): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;

  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Unable to build aura texture");

  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0.0, "rgba(255,255,255,1)");
  g.addColorStop(0.15, "rgba(220,240,255,0.95)");
  g.addColorStop(0.4, "rgba(120,190,255,0.28)");
  g.addColorStop(0.75, "rgba(60,140,255,0.08)");
  g.addColorStop(1.0, "rgba(0,0,0,0)");

  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);

  return new THREE.CanvasTexture(canvas);
}

export class OrbAura implements OrbRenderable {
  public readonly sprite: THREE.Sprite;
  private readonly material: THREE.SpriteMaterial;
  private readonly baseScale: number;

  constructor(baseScale: number) {
    this.baseScale = baseScale;
    this.material = new THREE.SpriteMaterial({
      map: createAuraTexture(),
      transparent: true,
      opacity: 0.16,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      depthTest: false,
      color: 0xb8d8ea,
    });

    this.sprite = new THREE.Sprite(this.material);
    this.sprite.scale.setScalar(this.baseScale);
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const flicker = 1 + Math.sin(frame.elapsed * 1.7) * 0.03;
    this.material.opacity = profile.auraOpacity * flicker;

    const amp = frame.state === "speaking" ? frame.speakingAmplitude * 0.08 : 0;
    const scale = this.baseScale * profile.auraScale * (1 + amp);
    this.sprite.scale.set(scale, scale, 1);
  }

  dispose(): void {
    this.material.map?.dispose();
    this.material.dispose();
  }
}
