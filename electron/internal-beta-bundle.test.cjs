const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  INTERNAL_BETA_CERT,
  INTERNAL_BETA_INSTALL_DOC,
  buildInternalArtifactName,
  buildInternalBetaManifest,
  writeInternalBetaBundle,
} = require("./internal-beta-bundle.cjs");

function makeTempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-internal-beta-"));
}

function seedGeneratedReports(root) {
  const generatedRoot = path.join(root, "electron", "generated");
  const distRoot = path.join(root, "dist", "overlay");
  const docsRoot = path.join(root, "docs", "operations");
  fs.mkdirSync(generatedRoot, { recursive: true });
  fs.mkdirSync(distRoot, { recursive: true });
  fs.mkdirSync(docsRoot, { recursive: true });

  const portablePath = path.join(distRoot, "Francis-Overlay-0.1.0-x64-portable.exe");
  const installerPath = path.join(distRoot, "Francis-Overlay-0.1.0-x64-installer.exe");
  fs.writeFileSync(portablePath, "portable", "utf8");
  fs.writeFileSync(installerPath, "installer", "utf8");
  fs.writeFileSync(path.join(docsRoot, "WINDOWS_INTERNAL_BETA.md"), "# Internal beta\n", "utf8");

  fs.writeFileSync(
    path.join(generatedRoot, "build-provenance.json"),
    JSON.stringify({
      version: 1,
      packageVersion: "0.1.0",
      generatedAt: "2026-03-27T12:00:00.000Z",
    }),
    "utf8",
  );
  fs.writeFileSync(
    path.join(generatedRoot, "build-signing.json"),
    JSON.stringify({
      version: 1,
      counts: {
        signed: 2,
        unsigned: 0,
        invalid: 0,
        missing: 0,
        unavailable: 0,
      },
      artifacts: [
        {
          path: portablePath,
          exists: true,
          state: "signed",
          subject: "Francis Overlay Dev Signing",
          issuer: "Francis Overlay Dev Signing",
          rootSubject: "Francis Overlay Dev Signing",
          rootIssuer: "Francis Overlay Dev Signing",
          thumbprint: "ABC123",
          summary: "Valid Authenticode signature for Francis Overlay Dev Signing.",
        },
        {
          path: installerPath,
          exists: true,
          state: "signed",
          subject: "Francis Overlay Dev Signing",
          issuer: "Francis Overlay Dev Signing",
          rootSubject: "Francis Overlay Dev Signing",
          rootIssuer: "Francis Overlay Dev Signing",
          thumbprint: "ABC123",
          summary: "Valid Authenticode signature for Francis Overlay Dev Signing.",
        },
      ],
    }),
    "utf8",
  );
  return {
    portablePath,
    installerPath,
  };
}

test("buildInternalArtifactName inserts the internal beta label before portable and installer suffixes", () => {
  assert.equal(
    buildInternalArtifactName("Francis-Overlay-0.1.0-x64-portable.exe", "0.1.0"),
    "Francis-Overlay-0.1.0-x64-internal-beta-portable.exe",
  );
  assert.equal(
    buildInternalArtifactName("Francis-Overlay-0.1.0-x64-installer.exe", "0.1.0"),
    "Francis-Overlay-0.1.0-x64-internal-beta-installer.exe",
  );
});

test("buildInternalBetaManifest marks the bundle as internal-only and references the exported signer cert", () => {
  const root = makeTempRoot();
  seedGeneratedReports(root);
  const outputRoot = path.join(root, "dist", "custom-internal-beta");

  const manifest = buildInternalBetaManifest({
    sourceRoot: root,
    includeSignerCert: true,
    outputRoot,
    generatedAt: "2026-03-27T12:30:00.000Z",
  });

  assert.equal(manifest.releaseChannel, "internal-beta");
  assert.equal(manifest.publicTrustReleaseReady, false);
  assert.equal(manifest.signer.selfIssued, true);
  assert.equal(manifest.outputRoot, outputRoot);
  assert.equal(manifest.exportedSignerCertificate.targetFileName, INTERNAL_BETA_CERT);
  assert.equal(manifest.installDoc.targetFileName, INTERNAL_BETA_INSTALL_DOC);
  assert.equal(manifest.artifacts.length, 2);
});

test("writeInternalBetaBundle copies signed artifacts and writes the manifest and notice", () => {
  const root = makeTempRoot();
  seedGeneratedReports(root);

  const manifest = writeInternalBetaBundle({
    sourceRoot: root,
    includeSignerCert: true,
    generatedAt: "2026-03-27T12:45:00.000Z",
  });

  assert.equal(fs.existsSync(manifest.manifestPath), true);
  assert.equal(fs.existsSync(manifest.noticePath), true);
  assert.equal(fs.existsSync(manifest.installDoc.targetPath), true);
  for (const artifact of manifest.artifacts) {
    assert.equal(fs.existsSync(artifact.targetPath), true);
  }
  const notice = fs.readFileSync(manifest.noticePath, "utf8");
  assert.match(notice, /INTERNAL \/ QA \/ TESTER ONLY/);
  assert.match(notice, /not public-trust signed/i);
});
