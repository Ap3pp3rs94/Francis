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
varying float vDepthCue;
varying float vRadial;
varying float vBandSeed;

void main() {
  float alongPulse = sin(aAlong * 3.14159265);
  float widthFalloff = 0.18 + pow(alongPulse, 0.82) * 0.72;
  float wobble = sin(uTime * uSpeed + aPhase + aAlong * 9.0 + aSeed) * 0.012;
  float ripple = sin(uTime * (uSpeed * 0.72) + aAlong * 18.0 + aSeed) * 0.004;

  vec3 center = position * mix(1.0, uTightness, 0.9);
  center += normalize(position) * wobble;

  float width = aRibbonWidth * widthFalloff;
  vec3 transformed = center + aSideDir * (aSide * width + ripple * aSide);
  vec4 centerView = modelViewMatrix * vec4(center, 1.0);
  vec4 orbCenterView = modelViewMatrix * vec4(0.0, 0.0, 0.0, 1.0);

  vEnergy = 0.64 + 0.36 * sin(uTime * uSpeed + aPhase + aSeed + aAlong * 14.0);
  vAcross = aSide;
  vAlong = aAlong;
  vDepthCue = clamp(0.5 + (centerView.z - orbCenterView.z) * 0.36, 0.0, 1.0);
  vRadial = clamp(length(center) / 1.25, 0.0, 1.0);
  vBandSeed = aSeed;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(transformed, 1.0);
}
