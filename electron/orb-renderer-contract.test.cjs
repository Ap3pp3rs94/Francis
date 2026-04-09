const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const filamentsPath = path.join(__dirname, "..", "francis-orb", "renderer", "OrbFilaments.ts");
const configPath = path.join(__dirname, "..", "francis-orb", "core", "config.ts");
const corePath = path.join(__dirname, "..", "francis-orb", "renderer", "OrbCore.ts");
const shellPath = path.join(__dirname, "..", "francis-orb", "renderer", "OrbShell.ts");
const scenePath = path.join(__dirname, "..", "francis-orb", "renderer", "OrbScene.ts");
const enginePath = path.join(__dirname, "..", "francis-orb", "renderer", "FrancisOrbEngine.ts");
const stateProfilesPath = path.join(__dirname, "..", "francis-orb", "core", "state-profiles.ts");
const signalMappingPath = path.join(__dirname, "..", "francis-orb", "integration", "signal-mapping.ts");
const filamentShaderPath = path.join(
  __dirname,
  "..",
  "francis-orb",
  "renderer",
  "shaders",
  "filament.fragment.glsl",
);

const filamentsSource = fs.readFileSync(filamentsPath, "utf8");
const configSource = fs.readFileSync(configPath, "utf8");
const coreSource = fs.readFileSync(corePath, "utf8");
const shellSource = fs.readFileSync(shellPath, "utf8");
const sceneSource = fs.readFileSync(scenePath, "utf8");
const engineSource = fs.readFileSync(enginePath, "utf8");
const stateProfilesSource = fs.readFileSync(stateProfilesPath, "utf8");
const signalMappingSource = fs.readFileSync(signalMappingPath, "utf8");
const filamentShader = fs.readFileSync(filamentShaderPath, "utf8");

test("orb filaments keep independent multi-axis ring motion instead of one synchronized spin", () => {
  assert.match(filamentsSource, /orbitAxisPrimary/);
  assert.match(filamentsSource, /orbitAxisSecondary/);
  assert.match(filamentsSource, /orbitAxisTertiary/);
  assert.match(filamentsSource, /arcCenterA/);
  assert.match(filamentsSource, /arcSpanA/);
  assert.match(filamentsSource, /arcSoftness/);
  assert.match(filamentsSource, /continuity:/);
  assert.match(filamentsSource, /uContinuity/);
  assert.match(filamentsSource, /group\.quaternion\.multiply/);
  assert.match(filamentsSource, /primaryOrbit/);
  assert.match(filamentsSource, /secondaryOrbit/);
  assert.match(filamentsSource, /tertiaryOrbit/);
});

test("filament shader keeps the bands soft, translucent, and depth-shaped", () => {
  assert.match(filamentShader, /uniform float uTime;/);
  assert.match(filamentShader, /uniform float uContinuity;/);
  assert.match(filamentShader, /uniform float uArcCenterA;/);
  assert.match(filamentShader, /float ringDistance/);
  assert.match(filamentShader, /float mist =/);
  assert.match(filamentShader, /float continuityMask =/);
  assert.match(filamentShader, /float arcMask =/);
  assert.match(filamentShader, /frontGain/);
  assert.match(filamentShader, /radialGain/);
});

test("orb renderer now defaults to a smaller filament-first body instead of the old large celestial field", () => {
  assert.match(configSource, /camera:\s*\{[\s\S]*fov: 36,[\s\S]*z: 5\.8,/);
  assert.match(configSource, /coreRadius: 0\.22,/);
  assert.match(configSource, /shellRadius: 0\.54,/);
  assert.match(configSource, /auraRadius: 1\.35,/);
  assert.match(configSource, /filamentCount: 60,/);
  assert.match(configSource, /filamentSegments: 360,/);
  assert.match(configSource, /particleCount: 0,/);
  assert.match(filamentsSource, /layer:\s*"inner"\s*\|\s*"mid"\s*\|\s*"outer"/);
  assert.match(filamentsSource, /layer === "inner"/);
  assert.match(filamentsSource, /layer === "mid"/);
  assert.match(filamentsSource, /layer === "outer"/);
  assert.match(filamentsSource, /depthTest: true,/);
  assert.match(filamentsSource, /blending: THREE\.AdditiveBlending,/);
  assert.match(filamentsSource, /mesh\.renderOrder = layer === "inner" \? 7 : layer === "mid" \? 6 : 5;/);
  assert.match(filamentsSource, /wrapUnit/);
  assert.match(filamentsSource, /layerOrbitRange/);
  assert.match(filamentsSource, /opacityScalar:/);
  assert.match(coreSource, /depthWrite: true,/);
  assert.match(coreSource, /depthTest: true,/);
  assert.match(coreSource, /this\.mesh\.renderOrder = 3;/);
  assert.match(shellSource, /depthTest: true,/);
  assert.match(shellSource, /this\.mesh\.renderOrder = 2;/);
  assert.match(sceneSource, /this\.root\.add\(this\.core\.mesh\);/);
  assert.match(sceneSource, /this\.root\.add\(this\.filaments\.group\);/);
  assert.match(sceneSource, /this\.root\.scale\.setScalar\(1\.32\);/);
  assert.match(stateProfilesSource, /shellOpacity: 0\.0014,/);
  assert.match(stateProfilesSource, /filamentOpacity: 0\.82,/);
  assert.match(stateProfilesSource, /filamentContinuity: 0\.44,/);
  assert.match(stateProfilesSource, /filamentDrift: 0\.58,/);
  assert.match(stateProfilesSource, /filamentSpread: 0\.84,/);
  assert.match(stateProfilesSource, /directionalBias: 0\.08,/);
  assert.match(stateProfilesSource, /auraOpacity: 0\.007,/);
  assert.match(stateProfilesSource, /coreIntensity: 0\.86,/);
  assert.match(stateProfilesSource, /rootStillness: 0\.58,/);
  assert.match(sceneSource, /this\.animateRoot\(frame, profile\);/);
  assert.match(sceneSource, /const directionalBias = Math\.max\(0, Number\(profile\.directionalBias \?\? 0\)\);/);
  assert.match(sceneSource, /const rootStillness = Math\.max\(0\.22, Math\.min\(1, Number\(profile\.rootStillness \?\? 0\.62\)\)\);/);
});

test("renderer mount contract marks the live container as renderer-owned and falls back cleanly on dispose", () => {
  assert.match(engineSource, /this\.container\.dataset\.renderer = "live";/);
  assert.match(engineSource, /this\.container\.dataset\.rendererOwner = "francis_orb";/);
  assert.match(engineSource, /this\.renderer\.domElement\.dataset\.rendererSurface = "orb_canvas";/);
  assert.match(engineSource, /this\.container\.dataset\.renderer = "fallback";/);
  assert.match(engineSource, /delete this\.container\.dataset\.rendererOwner;/);
});

test("observation states separate readability through filament coherence, drift, and directional bias", () => {
  assert.match(stateProfilesSource, /attentive:[\s\S]*filamentContinuity: 0\.54,[\s\S]*filamentDrift: 0\.48,[\s\S]*directionalBias: 0\.12,/);
  assert.match(stateProfilesSource, /investigate:[\s\S]*filamentContinuity: 0\.48,[\s\S]*filamentDrift: 0\.88,[\s\S]*filamentSpread: 0\.96,[\s\S]*directionalBias: 0\.28,/);
  assert.match(stateProfilesSource, /target_lock:[\s\S]*filamentContinuity: 0\.68,[\s\S]*filamentDrift: 0\.26,[\s\S]*filamentSpread: 0\.72,[\s\S]*directionalBias: 0\.32,/);
  assert.match(signalMappingSource, /if \(state === "waiting_user"\) \{[\s\S]*rawStrength = Math\.max\(rawStrength, 0\.36\);[\s\S]*rawLock = Math\.max\(rawLock, 0\.48\);[\s\S]*rawUncertainty = Math\.min\(rawUncertainty, 0\.24\);/);
});

test("execution states tighten through filament compression and continuity instead of core inflation", () => {
  assert.match(stateProfilesSource, /commit_move:[\s\S]*filamentTightness: 1\.24,[\s\S]*filamentContinuity: 0\.74,[\s\S]*filamentDrift: 0\.18,[\s\S]*compression: 0\.86,/);
  assert.match(stateProfilesSource, /hover_ready:[\s\S]*filamentTightness: 1\.22,[\s\S]*filamentContinuity: 0\.76,[\s\S]*filamentDrift: 0\.12,[\s\S]*compression: 0\.88,/);
  assert.match(stateProfilesSource, /click_act:[\s\S]*filamentTightness: 1\.28,[\s\S]*filamentContinuity: 0\.8,[\s\S]*directionalBias: 0\.54,[\s\S]*compression: 0\.8,/);
  assert.match(stateProfilesSource, /drag_act:[\s\S]*filamentTightness: 1\.22,[\s\S]*filamentDrift: 0\.22,[\s\S]*directionalBias: 0\.48,/);
  assert.match(stateProfilesSource, /type_hold:[\s\S]*filamentContinuity: 0\.7,[\s\S]*filamentDrift: 0\.1,[\s\S]*directionalBias: 0\.3,/);
  assert.match(sceneSource, /0\.022 \+\s*attentionStrength \* 0\.024 \+\s*attentionLock \* 0\.034 \+\s*directionalBias \* 0\.02/);
});

test("wait, blocked, interrupted, degraded, and paused no longer collapse into one weak filament posture", () => {
  assert.match(stateProfilesSource, /waiting_user:[\s\S]*filamentContinuity: 0\.72,[\s\S]*filamentDrift: 0\.16,[\s\S]*rootStillness: 0\.9,/);
  assert.match(stateProfilesSource, /blocked:[\s\S]*filamentTightness: 1\.14,[\s\S]*filamentContinuity: 0\.38,[\s\S]*filamentDrift: 0\.08,[\s\S]*compression: 0\.9,/);
  assert.match(stateProfilesSource, /interrupted:[\s\S]*filamentContinuity: 0\.24,[\s\S]*filamentDrift: 0\.28,[\s\S]*compression: 1\.02,/);
  assert.match(stateProfilesSource, /degraded:[\s\S]*filamentOpacity: 0\.46,[\s\S]*filamentContinuity: 0\.28,[\s\S]*filamentDrift: 0\.12,[\s\S]*rootStillness: 0\.62,/);
  assert.match(stateProfilesSource, /paused:[\s\S]*filamentOpacity: 0\.52,[\s\S]*filamentContinuity: 0\.52,[\s\S]*filamentDrift: 0\.03,[\s\S]*rootStillness: 0\.98,/);
  assert.match(signalMappingSource, /else if \(state === "blocked"\) \{[\s\S]*rawLock = Math\.max\(rawLock, 0\.46\);[\s\S]*rawUncertainty = Math\.min\(rawUncertainty, 0\.32\);/);
  assert.match(signalMappingSource, /else if \(state === "paused"\) \{[\s\S]*rawStrength = Math\.min\(rawStrength, 0\.14\);/);
  assert.match(signalMappingSource, /else if \(state === "degraded"\) \{[\s\S]*rawStrength \*= 0\.52;[\s\S]*rawLock \*= 0\.44;[\s\S]*rawUncertainty = Math\.max\(rawUncertainty, 0\.4\);/);
});
