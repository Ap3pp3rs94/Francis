uniform float uTime;
uniform float uOpacity;
uniform float uContinuity;
uniform float uArcCenterA;
uniform float uArcCenterB;
uniform float uArcCenterC;
uniform float uArcSpanA;
uniform float uArcSpanB;
uniform float uArcSpanC;
uniform float uArcSoftness;

varying float vEnergy;
varying float vAcross;
varying float vAlong;
varying float vDepthCue;
varying float vRadial;
varying float vBandSeed;

float ringDistance(float a, float b) {
  return abs(fract(a - b + 0.5) - 0.5);
}

void main() {
  float across = abs(vAcross);
  float strand = 1.0 - smoothstep(0.08, 0.86, across);
  float halo = 1.0 - smoothstep(0.18, 1.14, across);
  float tipFade = 0.16 + pow(sin(vAlong * 3.14159265), 0.82) * 0.84;
  float frontGain = mix(0.78, 1.34, vDepthCue);
  float radialGain =
    0.74 +
    smoothstep(0.08, 0.54, vRadial) * 0.88 -
    smoothstep(0.86, 1.0, vRadial) * 0.08;
  float mist =
    0.96 +
    sin(vAlong * 19.0 + uTime * 0.34 + vDepthCue * 2.2) * 0.04 +
    cos(vAlong * 11.0 - uTime * 0.24 + vRadial * 3.14159265) * 0.03;
  float continuityWave =
    sin(
      vAlong * 6.2831853 * (1.4 + fract(vBandSeed * 0.31) * 3.2) +
      vBandSeed * 7.0 +
      uTime * (0.05 + fract(vBandSeed * 0.17) * 0.035)
    );
  float continuityMask = mix(
    1.0,
    smoothstep(-0.55, 0.28, continuityWave),
    clamp(1.0 - uContinuity, 0.0, 1.0),
  );
  float arcA = 1.0 - smoothstep(uArcSpanA, uArcSpanA + uArcSoftness, ringDistance(vAlong, uArcCenterA));
  float arcB = 1.0 - smoothstep(uArcSpanB, uArcSpanB + uArcSoftness, ringDistance(vAlong, uArcCenterB));
  float arcC = 1.0 - smoothstep(uArcSpanC, uArcSpanC + uArcSoftness, ringDistance(vAlong, uArcCenterC));
  float arcMask = max(arcA, max(arcB * 0.92, arcC * 0.84));
  float alpha =
    uOpacity *
    mix(halo, strand, 0.76) *
    tipFade *
    frontGain *
    radialGain *
    arcMask *
    continuityMask *
    mist *
    (0.86 + vEnergy * 0.42) *
    1.55;

  vec3 base = vec3(0.82, 0.85, 0.89);
  vec3 cool = vec3(0.93, 0.95, 0.98);
  vec3 hot = vec3(1.0, 1.0, 1.0);
  vec3 color = mix(base, cool, clamp(vEnergy * 0.52 + (1.0 - vRadial) * 0.24, 0.0, 1.0));
  color = mix(color, hot, clamp(vEnergy * 0.42 + vDepthCue * 0.38 + (1.0 - vRadial) * 0.18, 0.0, 1.0));
  color *= (0.98 + mist * 0.06) * (0.94 + arcMask * 0.14);

  gl_FragColor = vec4(color, alpha);
}
