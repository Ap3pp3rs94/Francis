import * as THREE from "three";
import { OrbRenderable, OrbSignalFrame, OrbStateProfile } from "../core/types";

function createAuraTexture(size = 512): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;

  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Unable to build aura texture");

  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0.0, "rgba(255,255,255,0.1)");
  g.addColorStop(0.08, "rgba(244,247,251,0.05)");
  g.addColorStop(0.2, "rgba(214,224,236,0.02)");
  g.addColorStop(0.38, "rgba(150,166,184,0.006)");
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
      opacity: 0.008,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      depthTest: false,
      color: 0xf5f8fb,
    });

    this.sprite = new THREE.Sprite(this.material);
    this.sprite.scale.setScalar(this.baseScale);
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const attentionStrength = Math.max(0, Math.min(1, Number(frame.attentionStrength ?? frame.confidence ?? 0.28)));
    const attentionLock = Math.max(0, Math.min(1, Number(frame.attentionLock ?? 0.18)));
    const attentionUncertainty = Math.max(0, Math.min(1, Number(frame.attentionUncertainty ?? 0.14)));
    const haloStrength = Math.max(0, Math.min(1, Number(frame.visualHaloStrength ?? 0.78)));
    const flicker =
      1 +
      Math.sin(frame.elapsed * (0.82 + attentionStrength * 0.12)) *
        (0.008 + attentionUncertainty * 0.004);
    this.material.opacity =
      profile.auraOpacity *
      flicker *
      Math.max(
        0.54,
        0.82 +
          attentionStrength * 0.04 +
          attentionLock * 0.04 -
          attentionUncertainty * 0.1 +
          haloStrength * 0.04,
      );

    const amp = frame.speakingAmplitude > 0 ? frame.speakingAmplitude * 0.012 : 0;
    const scale =
      this.baseScale *
      profile.auraScale *
      (0.94 +
        amp +
        attentionStrength * 0.004 +
        attentionLock * 0.004 -
        attentionUncertainty * 0.012 +
        haloStrength * 0.008 -
        Math.max(0, Math.min(1, Number(profile.rootStillness ?? 0.62))) * 0.01);
    this.sprite.scale.set(scale, scale, 1);
  }

  dispose(): void {
    this.material.map?.dispose();
    this.material.dispose();
  }
}
