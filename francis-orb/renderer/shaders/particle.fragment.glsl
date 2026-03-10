uniform float uOpacity;
varying float vAlpha;

void main() {
  vec2 uv = gl_PointCoord.xy - 0.5;
  float d = length(uv);
  float falloff = smoothstep(0.5, 0.0, d);
  vec3 color = vec3(0.88, 0.96, 1.0);
  gl_FragColor = vec4(color, falloff * uOpacity * vAlpha);
}
