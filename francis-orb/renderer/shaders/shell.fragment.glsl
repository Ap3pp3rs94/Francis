uniform float uTime;
uniform float uOpacity;
uniform float uFresnelPower;
uniform float uActivity;
uniform float uPulse;
uniform float uNoiseDensity;
uniform float uRefractionStrength;

varying vec3 vNormal;
varying vec3 vViewDir;
varying vec3 vWorldPos;
varying vec3 vObjectPos;

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

float fbm(vec3 p) {
  float value = 0.0;
  float amplitude = 0.55;

  for (int i = 0; i < 4; i++) {
    value += noise(p) * amplitude;
    p = p * 2.03 + vec3(11.7, 5.2, 9.3);
    amplitude *= 0.5;
  }

  return value;
}

void main() {
  vec3 normal = normalize(vNormal) * (gl_FrontFacing ? 1.0 : -1.0);
  vec3 viewDir = normalize(vViewDir);
  float facing = clamp(dot(normal, viewDir), 0.0, 1.0);
  float fresnel = pow(1.0 - facing, uFresnelPower);

  vec3 basePos = normalize(vObjectPos) * (1.32 + uNoiseDensity * 0.08);
  vec3 slowFlow = vec3(uTime * 0.06, -uTime * 0.04, uTime * 0.08);
  vec3 fastFlow = vec3(-uTime * 0.09, uTime * 0.06, -uTime * 0.05);
  vec3 refracted = refract(-viewDir, normal, 1.0 / (1.005 + uRefractionStrength * 0.012));

  float veil = fbm(basePos * 1.9 + slowFlow + refracted * 0.08);
  float wisps = fbm(basePos * 3.1 - fastFlow + vec3(veil * 0.12));
  float threads = fbm(basePos * 4.1 + refracted * 0.16 - slowFlow * 0.6);

  float rim = smoothstep(0.4, 1.0, fresnel);
  float veilMask = smoothstep(0.6, 0.88, veil * 0.68 + wisps * 0.32);
  float fiber = smoothstep(0.56, 0.84, wisps * 0.44 + threads * 0.56);
  float innerVeil = (1.0 - facing) * (0.02 + veilMask * 0.04);
  float shimmer = clamp(0.96 + (uPulse - 1.0) * 0.42, 0.92, 1.02);

  vec3 voidTone = vec3(0.004, 0.006, 0.01);
  vec3 silver = vec3(0.42, 0.48, 0.56);
  vec3 ice = vec3(0.86, 0.9, 0.95);

  vec3 color = mix(voidTone, silver, veilMask * 0.05 + fiber * 0.07 + innerVeil * 0.06);
  color = mix(color, ice, rim * 0.16 + fiber * 0.04);
  color *= (0.06 + rim * 0.16 + innerVeil * 0.08) * shimmer;
  color = max(color, vec3(0.0));

  float alpha = uOpacity * (0.56 + uActivity * 0.08);
  alpha *= clamp(rim * 0.18 + fiber * 0.12 + innerVeil * 0.1, 0.0, 1.0);

  gl_FragColor = vec4(color, alpha);
}
