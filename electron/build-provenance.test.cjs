const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  buildProvenanceManifest,
  normalizeBuildTargets,
  resolveGeneratedProvenancePath,
  writeGeneratedProvenance,
  loadGeneratedProvenance,
} = require("./build-provenance");

function makeTempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-provenance-"));
}

test("normalizeBuildTargets collapses builder targets into stable names", () => {
  const targets = normalizeBuildTargets({
    win: {
      target: [
        { target: "portable", arch: ["x64"] },
        { target: "nsis", arch: ["x64"] },
        "portable",
      ],
    },
  });

  assert.deepEqual(targets, ["portable", "nsis"]);
});

test("provenance manifest captures file hashes and runtime posture", () => {
  const sourceRoot = makeTempRoot();
  const packageJsonPath = path.join(sourceRoot, "package.json");
  const packageLockPath = path.join(sourceRoot, "package-lock.json");
  const pyprojectPath = path.join(sourceRoot, "pyproject.toml");
  const runtimeRoot = path.join(sourceRoot, "dist", "python-runtime-staging");
  fs.mkdirSync(runtimeRoot, { recursive: true });
  fs.writeFileSync(path.join(runtimeRoot, "python.exe"), "python", "utf8");
  fs.writeFileSync(packageJsonPath, JSON.stringify({ version: "0.1.0", build: { appId: "com.francis.overlay", productName: "Francis Overlay", win: { target: ["portable", "nsis"] } }, devDependencies: { electron: "40.8.0", "electron-builder": "^26.8.1" } }), "utf8");
  fs.writeFileSync(packageLockPath, "{\"name\":\"francis-overlay-shell\"}", "utf8");
  fs.writeFileSync(pyprojectPath, "[project]\nname='francis'\n", "utf8");

  const manifest = buildProvenanceManifest({
    sourceRoot,
    buildIdentity: "0.1.0+abc1234",
    packageJson: JSON.parse(fs.readFileSync(packageJsonPath, "utf8")),
    packageJsonPath,
    packageLockPath,
    pyprojectPath,
    runtimeRoot,
    generatedAt: "2026-03-12T12:00:00Z",
  });

  assert.equal(manifest.buildIdentity, "0.1.0+abc1234");
  assert.equal(manifest.targets.includes("portable"), true);
  assert.equal(manifest.inputs.packageJson.exists, true);
  assert.equal(typeof manifest.inputs.packageJson.sha256, "string");
  assert.equal(manifest.runtime.pythonExecutableExists, true);
});

test("generated provenance can be written and reloaded", () => {
  const sourceRoot = makeTempRoot();
  const manifest = { version: 1, buildIdentity: "0.1.0+abc1234" };
  const filePath = writeGeneratedProvenance(sourceRoot, manifest);

  assert.equal(filePath, resolveGeneratedProvenancePath(sourceRoot));
  assert.deepEqual(loadGeneratedProvenance(sourceRoot), manifest);
});
