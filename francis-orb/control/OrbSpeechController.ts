import { clamp, lerp } from "../core/math";

export class OrbSpeechController {
  private smoothedAmplitude = 0;

  update(rawAmplitude: number): number {
    const next = clamp(rawAmplitude, 0, 1);
    this.smoothedAmplitude = lerp(this.smoothedAmplitude, next, 0.18);
    return this.smoothedAmplitude;
  }

  get value(): number {
    return this.smoothedAmplitude;
  }
}
