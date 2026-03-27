const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  buildArtifactSigningReport,
  inspectAuthenticodeSignature,
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

test("inspectAuthenticodeSignature can query the vendored signtool binary", { skip: process.platform !== "win32" }, () => {
  const signToolPath = resolveSignToolPath();
  assert.ok(signToolPath);

  const record = inspectAuthenticodeSignature(signToolPath);

  assert.equal(record.state, "signed");
  assert.equal(record.status, "Valid");
});
