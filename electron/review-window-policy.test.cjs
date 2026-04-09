const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const mainPath = path.join(__dirname, "main.js");
const mainSource = fs.readFileSync(mainPath, "utf8");

test("electron runtime keeps the review HUD window disabled in orb-first desktop mode", () => {
  assert.match(mainSource, /const REVIEW_HUD_WINDOW_ENABLED = false;/);
  assert.match(
    mainSource,
    /function showLensWindow\(\) {\s*if \(!REVIEW_HUD_WINDOW_ENABLED\) {\s*const existing = getLiveMainWindow\(\);[\s\S]*resetOrbOwnershipToSafeFallback\("review_window_disabled"\);[\s\S]*return getOverlayState\(existing\);\s*}/,
  );
});

test("generic shell controls no longer construct the review HUD window behind orb-only interactions", () => {
  assert.match(mainSource, /applyAlwaysOnTop\(getLiveMainWindow\(\), !overlayState\.alwaysOnTop\)/);
  assert.match(mainSource, /restartHudAndRefreshWindow\(getLiveMainWindow\(\)\)/);
  assert.match(mainSource, /executeRetainedStateRepair\(getLiveMainWindow\(\)\)/);
  assert.match(mainSource, /exportShellState\(getLiveMainWindow\(\)\)/);
  assert.match(mainSource, /importShellState\(getLiveMainWindow\(\)\)/);
  assert.match(mainSource, /restoreLatestRollbackSnapshot\(getLiveMainWindow\(\)\)/);
  assert.match(mainSource, /ipcMain\.handle\("overlay:set-target-display", \(_event, displayId\) => moveOverlayToDisplay\(displayId, getLiveMainWindow\(\)\)\);/);
  assert.match(mainSource, /ipcMain\.handle\("overlay:reset-layout", \(\) => resetOverlayPreferences\(getLiveMainWindow\(\)\)\);/);
  assert.match(mainSource, /ipcMain\.handle\("overlay:minimize", \(\) => {\s*const win = getShellControlWindow\(\);/);
  assert.match(mainSource, /ipcMain\.handle\("overlay:toggle-devtools", \(\) => {\s*const win = getShellControlWindow\(\);/);
});
