import * as THREE from "three";

export function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function smoothDamp(current: number, target: number, factor: number): number {
  return lerp(current, target, factor);
}

export function vec3Lerp(
  current: THREE.Vector3,
  target: THREE.Vector3,
  factor: number,
): THREE.Vector3 {
  current.lerp(target, factor);
  return current;
}
