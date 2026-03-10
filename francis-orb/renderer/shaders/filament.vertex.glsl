attribute float aPhase;
attribute float aSeed;

uniform float uTime;
uniform float uTightness;
uniform float uSpeed;

varying float vEnergy;

void main() {
  vec3 transformed = position;

  float wobble = sin(uTime * uSpeed + aPhase + position.x * 3.0 + aSeed) * 0.04;
  transformed *= mix(1.0, uTightness, 0.5);
  transformed += normal * wobble;

  vEnergy = 0.55 + 0.45 * sin(uTime * uSpeed + aPhase + aSeed);

  gl_Position = projectionMatrix * modelViewMatrix * vec4(transformed, 1.0);
}
