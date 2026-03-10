uniform float uOpacity;

varying float vEnergy;
varying float vAcross;
varying float vAlong;

void main() {
  float edgeFade = 1.0 - smoothstep(0.45, 1.0, vAcross);
  float tipFade = 0.22 + pow(sin(vAlong * 3.14159265), 0.58) * 0.78;
  float alpha = uOpacity * edgeFade * tipFade * (0.62 + vEnergy * 0.58);

  vec3 base = vec3(0.42, 0.66, 0.86);
  vec3 hot = vec3(0.84, 0.94, 0.99);
  vec3 color = mix(base, hot, vEnergy);

  gl_FragColor = vec4(color, alpha);
}
