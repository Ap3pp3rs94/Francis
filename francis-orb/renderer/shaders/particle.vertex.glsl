attribute float aScale;
attribute float aSeed;

uniform float uTime;
uniform float uSpeed;
uniform float uPixelRatio;

varying float vAlpha;

void main() {
  vec3 p = position;

  float drift = sin(uTime * uSpeed + aSeed) * 0.08;
  p += normalize(position) * drift;

  vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mvPosition;

  gl_PointSize = aScale * uPixelRatio * (8.0 / -mvPosition.z);
  vAlpha = 0.7 + 0.3 * sin(uTime + aSeed);
}
