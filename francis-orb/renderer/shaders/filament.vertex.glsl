attribute vec3 aSideDir;
attribute float aSide;
attribute float aAlong;
attribute float aSeed;
attribute float aPhase;
attribute float aRibbonWidth;

uniform float uTime;
uniform float uTightness;
uniform float uSpeed;

varying float vEnergy;
varying float vAcross;
varying float vAlong;

void main() {
  float alongPulse = sin(aAlong * 3.14159265);
  float widthFalloff = 0.28 + pow(alongPulse, 0.72) * 0.72;
  float wobble = sin(uTime * uSpeed + aPhase + aAlong * 12.0 + aSeed) * 0.045;
  float ripple = sin(uTime * (uSpeed * 0.72) + aAlong * 24.0 + aSeed) * 0.018;

  vec3 center = position * mix(1.0, uTightness, 0.84);
  center += normalize(position) * wobble;

  float width = aRibbonWidth * widthFalloff;
  vec3 transformed = center + aSideDir * (aSide * width + ripple * aSide);

  vEnergy = 0.58 + 0.42 * sin(uTime * uSpeed + aPhase + aSeed + aAlong * 14.0);
  vAcross = abs(aSide);
  vAlong = aAlong;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(transformed, 1.0);
}
