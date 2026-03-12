const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
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
    exportedAt: "2026-03-12T12:00:00Z",
    preferences: {
      startupProfile: "quiet",
      alwaysOnTop: false,
      ignoreMouseEvents: true,
      targetDisplayId: 202,
      windowBounds: { x: 64, y: 48, width: 1200, height: 800 },
    },
  });

  assert.equal(payload.buildIdentity, "0.1.0+abc1234");
  assert.equal(payload.shell.startupProfile, "quiet");
  assert.equal(payload.shell.ignoreMouseEvents, true);
  assert.match(payload.limits.launchAtLogin, /Not imported automatically/);
});

test("overlay portability import only extracts safe portable preferences", () => {
  const preferences = extractPortablePreferences({
    shell: {
      startupProfile: "core_only",
      alwaysOnTop: true,
      ignoreMouseEvents: false,
      targetDisplayId: 101,
      windowBounds: { x: 0, y: 0, width: 1280, height: 720 },
    },
  });

  assert.equal(preferences.startupProfile, "core_only");
  assert.equal(preferences.targetDisplayId, 101);
  assert.deepEqual(preferences.windowBounds, {
    x: 0,
    y: 0,
    width: 1280,
    height: 720,
  });
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
