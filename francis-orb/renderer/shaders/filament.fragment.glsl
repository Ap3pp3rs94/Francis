uniform float uOpacity;
varying float vEnergy;

void main() {
  vec3 color = mix(vec3(0.75, 0.9, 1.0), vec3(1.0), vEnergy);
  gl_FragColor = vec4(color, uOpacity * (0.55 + vEnergy * 0.45));
}
