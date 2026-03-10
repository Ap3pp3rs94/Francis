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
  float fresnel = pow(1.0 - clamp(dot(normal, viewDir), 0.0, 1.0), uFresnelPower);

  vec3 basePos = vObjectPos * (2.8 * uNoiseDensity);
  vec3 slowFlow = vec3(uTime * 0.12, -uTime * 0.08, uTime * 0.18);
  vec3 fastFlow = vec3(-uTime * 0.21, uTime * 0.15, -uTime * 0.11);
  vec3 refracted = refract(-viewDir, normal, 1.0 / (1.04 + uRefractionStrength * 0.08));

  vec3 warp = vec3(
    fbm(basePos + slowFlow),
    fbm(basePos * 1.7 - fastFlow),
    fbm(vWorldPos * 1.3 + slowFlow * 0.6)
  ) - 0.5;

  float coarse = fbm(basePos + slowFlow + refracted * (0.7 + uRefractionStrength * 0.8));
  float billow = fbm(basePos * 2.05 - fastFlow + warp * 1.8);
  float grain = fbm(basePos * 3.9 + refracted * 1.35 - slowFlow * 1.4);
  float filigree = fbm(basePos * 4.6 + warp * 2.4 - fastFlow * 1.6);

  float shellBody = smoothstep(0.26, 0.88, coarse * 0.6 + billow * 0.4);
  float internalHaze = smoothstep(0.18, 0.92, grain * 0.65 + coarse * 0.35);
  float fracture = smoothstep(0.5, 0.94, filigree + grain * 0.22);
  float meshLines = 1.0 - smoothstep(0.08, 0.28, abs(billow - filigree));
  meshLines *= 0.55 + fracture * 0.45;

  float rim = clamp(fresnel * 1.2 + meshLines * 0.35 + fracture * 0.25, 0.0, 1.0);
  float shimmer = clamp(0.82 + (uPulse - 1.0) * 2.8, 0.75, 1.1);

  float prismR = fbm(basePos * 2.6 + refracted * 1.4 + vec3(uTime * 0.18, 0.0, 0.0));
  float prismB = fbm(basePos * 2.6 + refracted * 1.4 - vec3(0.0, uTime * 0.16, 0.0));
  vec3 prismShift = vec3(prismR - 0.5, internalHaze - 0.5, prismB - 0.5);

  vec3 deepColor = vec3(0.08, 0.19, 0.28);
  vec3 bodyColor = vec3(0.33, 0.72, 0.94);
  vec3 rimColor = vec3(0.84, 0.97, 1.0);

  vec3 color = mix(deepColor, bodyColor, shellBody);
  color = mix(color, rimColor, rim * 0.45 + fracture * 0.2);
  color += prismShift * (0.09 + uRefractionStrength * 0.06) * (0.35 + rim * 0.65);
  color += rimColor * meshLines * (0.08 + uActivity * 0.06);
  color *= (0.62 + internalHaze * 0.25 + rim * 0.45) * shimmer;
  color = max(color, vec3(0.0));

  float alpha = uOpacity * (0.78 + uActivity * 0.32);
  alpha *= clamp(fresnel * 1.15 + shellBody * 0.42 + fracture * 0.18, 0.0, 1.1);
  alpha *= 0.86 + meshLines * 0.22;

  gl_FragColor = vec4(color, alpha);
}
