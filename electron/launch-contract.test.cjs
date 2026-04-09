const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const packageJson = JSON.parse(fs.readFileSync(path.join(repoRoot, "package.json"), "utf8"));
const devRunSource = fs.readFileSync(path.join(repoRoot, "electron", "dev-run.ps1"), "utf8");
const startOverlaySource = fs.readFileSync(path.join(repoRoot, "electron", "start-overlay.ps1"), "utf8");
const readmeSource = fs.readFileSync(path.join(repoRoot, "electron", "README-overlay.md"), "utf8");

test("default overlay start uses the clean detached launcher", () => {
  assert.equal(
    packageJson.scripts["overlay:start"],
    "powershell -ExecutionPolicy Bypass -File electron/start-overlay.ps1",
  );
  assert.equal(packageJson.scripts["overlay:start:console"], "electron .");
});

test("dev launch keeps the console-bound engineering path explicit", () => {
  assert.match(devRunSource, /npm run overlay:start:console/);
});

test("start-overlay launches electron hidden from a stable repo root", () => {
  assert.match(startOverlaySource, /\$repoRoot = Split-Path -Parent \$PSScriptRoot/);
  assert.match(startOverlaySource, /node_modules\\electron\\dist\\electron\.exe/);
  assert.match(startOverlaySource, /WindowStyle\s*=\s*"Hidden"/);
  assert.match(startOverlaySource, /WorkingDirectory = \$repoRoot/);
});

test("overlay README documents clean launch versus console launch", () => {
  assert.match(readmeSource, /npm run overlay:start/);
  assert.match(readmeSource, /without a separate black console host/i);
  assert.match(readmeSource, /npm run overlay:start:console/);
});
