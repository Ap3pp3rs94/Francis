uniform float uOpacity;
varying vec2 vUv;

void main() {
  float center = abs(vUv.y - 0.5);
  float glow = smoothstep(0.5, 0.0, center);
  vec3 color = vec3(0.72, 0.9, 1.0);
  gl_FragColor = vec4(color, glow * uOpacity);
}
