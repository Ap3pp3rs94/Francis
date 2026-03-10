uniform float uTime;
uniform float uIntensity;
uniform float uPulse;
uniform float uDistortion;

varying vec3 vNormal;
varying vec3 vWorldPos;
varying vec3 vViewDir;

float hash(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float noise(vec3 x) {
  vec3 i = floor(x);
  vec3 f = fract(x);

  float n000 = hash(i + vec3(0.0, 0.0, 0.0));
  float n100 = hash(i + vec3(1.0, 0.0, 0.0));
  float n010 = hash(i + vec3(0.0, 1.0, 0.0));
  float n110 = hash(i + vec3(1.0, 1.0, 0.0));
  float n001 = hash(i + vec3(0.0, 0.0, 1.0));
  float n101 = hash(i + vec3(1.0, 0.0, 1.0));
  float n011 = hash(i + vec3(0.0, 1.0, 1.0));
  float n111 = hash(i + vec3(1.0, 1.0, 1.0));

  vec3 u = f * f * (3.0 - 2.0 * f);

  return mix(
    mix(mix(n000, n100, u.x), mix(n010, n110, u.x), u.y),
    mix(mix(n001, n101, u.x), mix(n011, n111, u.x), u.y),
    u.z
  );
}

void main() {
  float fresnel = pow(1.0 - max(dot(normalize(vNormal), normalize(vViewDir)), 0.0), 2.0);

  float n1 = noise(vWorldPos * 3.2 + uTime * 0.6);
  float n2 = noise(vWorldPos * 6.8 - uTime * 0.9);
  float plasma = mix(n1, n2, 0.5);

  float brightness = 0.46 + plasma * uDistortion + uPulse * 0.14;
  brightness *= uIntensity;

  vec3 base = vec3(0.78, 0.89, 0.97);
  vec3 hot = vec3(0.96, 0.99, 1.0);

  vec3 color = mix(base, hot, clamp(brightness + fresnel * 0.2, 0.0, 1.0));

  float alpha = 0.78;
  gl_FragColor = vec4(color * brightness, alpha);
}
