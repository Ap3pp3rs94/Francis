uniform float uOpacity;
uniform float uFresnelPower;

varying vec3 vNormal;
varying vec3 vViewDir;

void main() {
  float fresnel = pow(1.0 - max(dot(normalize(vNormal), normalize(vViewDir)), 0.0), uFresnelPower);
  vec3 color = vec3(0.78, 0.92, 1.0);
  gl_FragColor = vec4(color, fresnel * uOpacity);
}
