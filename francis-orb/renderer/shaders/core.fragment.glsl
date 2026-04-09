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
  float facing = clamp(dot(normalize(vNormal), normalize(vViewDir)), 0.0, 1.0);
  float fresnel = pow(1.0 - facing, 4.8);
  float nucleus = pow(facing, 4.8);
  float innerHalo = pow(facing, 1.8);

  float n1 = noise(vWorldPos * 3.2 + uTime * 0.6);
  float n2 = noise(vWorldPos * 7.4 - uTime * 0.78);
  float plasma = mix(n1, n2, 0.42);
  float heartbeat = 0.985 + (uPulse - 1.0) * 0.44;
  float innerGlow = clamp(nucleus * 1.92 + plasma * (0.04 + uDistortion * 0.12), 0.0, 1.0);
  float veil = clamp(innerHalo * 0.56 + plasma * (0.04 + uDistortion * 0.08), 0.0, 1.0);
  float corona = clamp(fresnel * 0.16 + plasma * 0.04, 0.0, 1.0);
  float shimmer = (1.04 + plasma * (0.05 + uDistortion * 0.1)) * heartbeat * uIntensity;

  vec3 cool = vec3(0.86, 0.89, 0.93);
  vec3 pearl = vec3(0.96, 0.98, 0.995);
  vec3 silver = vec3(1.0, 1.0, 1.0);

  vec3 color = mix(cool, pearl, 0.24 + innerGlow * 0.34);
  color = mix(color, silver, clamp(innerGlow * 0.92 + nucleus * 0.22 + veil * 0.1, 0.0, 1.0));
  color += pearl * corona * 0.1;

  float alpha = 0.14 + innerGlow * 0.42 + veil * 0.14 + corona * 0.05;
  gl_FragColor = vec4(color * shimmer, alpha);
}
