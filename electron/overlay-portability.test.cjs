const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  PORTABILITY_EXPORT_VERSION,
  assessPortablePayloadCompatibility,
  PORTABILITY_STATE_FILE,
  buildOverlayExportPayload,
  extractPortablePreferences,
  getPortabilityStatePath,
  loadPortabilityState,
  savePortabilityState,
} = require("./overlay-portability");

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-portability-"));
}

test("overlay portability export includes safe shell preferences and import limits", () => {
  const payload = buildOverlayExportPayload({
    buildIdentity: "0.1.0+abc1234",
    version: "0.1.0",
    exportedAt: "2026-03-12T12:00:00Z",
    preferences: {
      startupProfile: "quiet",
      motionMode: "reduce",
      alwaysOnTop: false,
      ignoreMouseEvents: true,
      targetDisplayId: 202,
      windowBounds: { x: 64, y: 48, width: 1200, height: 800 },
    },
  });

  assert.equal(payload.buildIdentity, "0.1.0+abc1234");
  assert.equal(payload.version, PORTABILITY_EXPORT_VERSION);
  assert.equal(payload.compatibility.channel, "0.1");
  assert.equal(payload.shell.startupProfile, "quiet");
  assert.equal(payload.shell.motionMode, "reduce");
  assert.equal(payload.shell.ignoreMouseEvents, true);
  assert.match(payload.limits.launchAtLogin, /Not imported automatically/);
});

test("overlay portability import only extracts safe portable preferences", () => {
  const preferences = extractPortablePreferences({
    compatibility: {
      exportVersion: PORTABILITY_EXPORT_VERSION,
      buildIdentity: "0.1.2+abc1234",
      version: "0.1.2",
      channel: "0.1",
      portabilityStateVersion: 1,
    },
    shell: {
      startupProfile: "core_only",
      motionMode: "full",
      alwaysOnTop: true,
      ignoreMouseEvents: false,
      targetDisplayId: 101,
      windowBounds: { x: 0, y: 0, width: 1280, height: 720 },
    },
  }, {
    currentBuildIdentity: "0.1.3+def5678",
    currentVersion: "0.1.3",
  });

  assert.equal(preferences.startupProfile, "core_only");
  assert.equal(preferences.motionMode, "full");
  assert.equal(preferences.targetDisplayId, 101);
  assert.deepEqual(preferences.windowBounds, {
    x: 0,
    y: 0,
    width: 1280,
    height: 720,
  });
});

test("overlay portability blocks incompatible import channels", () => {
  const compatibility = assessPortablePayloadCompatibility({
    version: PORTABILITY_EXPORT_VERSION,
    compatibility: {
      exportVersion: PORTABILITY_EXPORT_VERSION,
      buildIdentity: "0.2.0+abc1234",
      version: "0.2.0",
      channel: "0.2",
      portabilityStateVersion: 1,
    },
    shell: {},
  }, {
    currentBuildIdentity: "0.1.3+def5678",
    currentVersion: "0.1.3",
  });

  assert.equal(compatibility.compatible, false);
  assert.equal(compatibility.status, "blocked");
  assert.match(compatibility.summary, /does not match current channel/i);
});

test("overlay portability state persists export and import activity", () => {
  const userDataPath = makeTempUserData();
  const saved = savePortabilityState(userDataPath, {
    lastExportAt: "2026-03-12T12:00:00Z",
    lastExportPath: "C:\\temp\\francis-overlay.json",
    lastImportAt: "2026-03-12T12:05:00Z",
    lastImportPath: "C:\\temp\\francis-overlay.json",
    lastImportStatus: "applied",
    lastImportMessage: "Imported safe shell preferences only.",
  });

  assert.equal(path.basename(getPortabilityStatePath(userDataPath)), PORTABILITY_STATE_FILE);
  assert.equal(saved.lastImportStatus, "applied");

  const loaded = loadPortabilityState(userDataPath);
  assert.deepEqual(loaded, saved);
});
