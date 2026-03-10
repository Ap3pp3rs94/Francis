uniform float uOpacity;

varying float vEnergy;
varying float vAcross;
varying float vAlong;

void main() {
  float edgeFade = 1.0 - smoothstep(0.45, 1.0, vAcross);
  float tipFade = 0.22 + pow(sin(vAlong * 3.14159265), 0.58) * 0.78;
  float alpha = uOpacity * edgeFade * tipFade * (0.48 + vEnergy * 0.52);

  vec3 base = vec3(0.58, 0.8, 0.98);
  vec3 hot = vec3(0.96, 0.99, 1.0);
  vec3 color = mix(base, hot, vEnergy);

  gl_FragColor = vec4(color, alpha);
}
