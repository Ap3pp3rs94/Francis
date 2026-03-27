const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  GENERATED_SIGNING_DIR,
  buildArtifactSigningReport,
  inspectAuthenticodeSignature,
  resolveOverlayArtifactPaths,
  resolveSignToolPath,
  validateSigningReport,
} = require("./signature-state");

function makeTempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-signing-"));
}

test("inspectAuthenticodeSignature normalizes valid signatures", () => {
  const root = makeTempRoot();
  const filePath = path.join(root, "Francis Overlay.exe");
  fs.writeFileSync(filePath, "overlay", "utf8");

  const record = inspectAuthenticodeSignature(filePath, {
    execFileSync: () =>
      [
        "Verifying: D:\\temp\\Francis Overlay.exe",
        "",
        "Signature Index: 0 (Primary Signature)",
        "Signing Certificate Chain:",
        "    Issued to: Francis Overlay",
        "    Issued by: Francis Root",
        "    Expires:   2026-12-31T00:00:00.000Z",
        "",
        "Successfully verified: D:\\temp\\Francis Overlay.exe",
        "",
        "Number of files successfully Verified: 1",
        "Number of warnings: 0",
        "Number of errors: 0",
      ].join("\n"),
  });

  assert.equal(record.state, "signed");
  assert.equal(record.status, "Valid");
  assert.match(record.summary, /Valid Authenticode signature/i);
});

test("buildArtifactSigningReport counts unsigned artifacts and require-signed failures", () => {
  const root = makeTempRoot();
  const filePath = path.join(root, "Francis Overlay.exe");
  fs.writeFileSync(filePath, "overlay", "utf8");

  const report = buildArtifactSigningReport({
    artifactPaths: [filePath],
    execFileSync: () =>
      (() => {
        const error = new Error("signtool verify failed");
        error.stdout = [
          "Verifying: D:\\temp\\Francis Overlay.exe",
          "",
          "Number of files successfully Verified: 0",
          "Number of warnings: 0",
          "Number of errors: 1",
          "SignTool Error: No signature found.",
        ].join("\n");
        throw error;
      })(),
  });

  assert.equal(report.counts.unsigned, 1);
  assert.match(report.summary, /unsigned/i);
  assert.equal(validateSigningReport(report, { requireSigned: true }).ok, false);
});

test("resolveOverlayArtifactPaths ignores stale top-level artifacts from older builds", () => {
  const root = makeTempRoot();
  const generatedDir = path.join(root, GENERATED_SIGNING_DIR);
  const distRoot = path.join(root, "dist", "overlay");
  const unpackedRoot = path.join(distRoot, "win-unpacked");
  fs.mkdirSync(generatedDir, { recursive: true });
  fs.mkdirSync(unpackedRoot, { recursive: true });

  fs.writeFileSync(
    path.join(root, "package.json"),
    JSON.stringify({
      version: "0.1.0",
      build: {
        productName: "Francis Overlay",
      },
    }),
    "utf8",
  );

  const provenancePath = path.join(generatedDir, "build-provenance.json");
  fs.writeFileSync(
    provenancePath,
    JSON.stringify({
      generatedAt: "2026-03-27T12:00:00.000Z",
    }),
    "utf8",
  );

  const unpackedExe = path.join(unpackedRoot, "Francis Overlay.exe");
  const currentPortable = path.join(distRoot, "Francis-Overlay-0.1.0-x64-portable.exe");
  const staleArtifact = path.join(distRoot, "Francis-Overlay-0.1.0-x64.exe");
  fs.writeFileSync(unpackedExe, "unpacked", "utf8");
  fs.writeFileSync(currentPortable, "portable", "utf8");
  fs.writeFileSync(staleArtifact, "stale", "utf8");

  const staleTime = new Date("2026-03-11T10:28:48.000Z");
  const currentTime = new Date("2026-03-27T12:10:00.000Z");
  fs.utimesSync(currentPortable, currentTime, currentTime);
  fs.utimesSync(staleArtifact, staleTime, staleTime);

  const artifactPaths = resolveOverlayArtifactPaths(root);

  assert.ok(artifactPaths.includes(unpackedExe));
  assert.ok(artifactPaths.includes(currentPortable));
  assert.ok(!artifactPaths.includes(staleArtifact));
});

test("inspectAuthenticodeSignature can query the vendored signtool binary", { skip: process.platform !== "win32" }, () => {
  const signToolPath = resolveSignToolPath();
  assert.ok(signToolPath);

  const record = inspectAuthenticodeSignature(signToolPath);

  assert.equal(record.state, "signed");
  assert.equal(record.status, "Valid");
});
