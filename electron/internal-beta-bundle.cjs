const fs = require("node:fs");
const path = require("node:path");

const {
  loadGeneratedSigningReport,
  resolveGeneratedSigningPath,
} = require("./signature-state");
const {
  loadGeneratedProvenance,
  resolveGeneratedProvenancePath,
} = require("./build-provenance");

const INTERNAL_BETA_ROOT = path.join("dist", "internal-beta", "windows", "current");
const INTERNAL_BETA_MANIFEST = "internal-beta-manifest.json";
const INTERNAL_BETA_NOTICE = "INTERNAL-BETA-NOTICE.txt";
const INTERNAL_BETA_INSTALL_DOC = "INSTALL-WINDOWS-INTERNAL-BETA.md";
const INTERNAL_BETA_CERT = "Francis-Overlay-Internal-Beta-Signer.cer";
const INTERNAL_BETA_DOC_SOURCE = path.join("docs", "operations", "WINDOWS_INTERNAL_BETA.md");

function safeStat(targetPath) {
  try {
    return fs.statSync(targetPath);
  } catch {
    return null;
  }
}

function ensureDirectory(targetPath) {
  fs.mkdirSync(targetPath, { recursive: true });
}

function normalizeVersion(rawValue = "") {
  return String(rawValue || "").trim() || "unknown";
}

function isTopLevelWindowsArtifact(targetPath = "", sourceRoot = "") {
  const resolvedPath = path.resolve(targetPath);
  const normalizedPath = resolvedPath.toLowerCase();
  const distRoot = path.join(path.resolve(sourceRoot), "dist", "overlay").toLowerCase();
  const winUnpacked = path.join(distRoot, "win-unpacked").toLowerCase();
  return (
    normalizedPath.startsWith(distRoot) &&
    !normalizedPath.startsWith(winUnpacked) &&
    normalizedPath.endsWith(".exe")
  );
}

function buildInternalArtifactName(fileName = "", packageVersion = "unknown") {
  const parsed = path.parse(fileName);
  if (!parsed.name) {
    return `Francis-Overlay-${packageVersion}-internal-beta.exe`;
  }
  const normalizedBase = parsed.name;
  if (/-portable$/i.test(normalizedBase)) {
    return `${normalizedBase.replace(/-portable$/i, "")}-internal-beta-portable${parsed.ext}`;
  }
  if (/-installer$/i.test(normalizedBase)) {
    return `${normalizedBase.replace(/-installer$/i, "")}-internal-beta-installer${parsed.ext}`;
  }
  return `${normalizedBase}-internal-beta${parsed.ext}`;
}

function resolveInternalBetaOutputRoot(sourceRoot, outputRoot = "") {
  return outputRoot
    ? path.resolve(outputRoot)
    : path.join(path.resolve(sourceRoot), INTERNAL_BETA_ROOT);
}

function resolveInternalBetaArtifactEntries({
  sourceRoot,
  signingReport,
  packageVersion,
} = {}) {
  const artifacts = Array.isArray(signingReport?.artifacts) ? signingReport.artifacts : [];
  return artifacts
    .filter((entry) => entry?.state === "signed" && isTopLevelWindowsArtifact(entry.path, sourceRoot))
    .map((entry) => {
      const fileName = path.basename(entry.path);
      const targetFileName = buildInternalArtifactName(fileName, packageVersion);
      return {
        sourcePath: entry.path,
        sourceFileName: fileName,
        targetFileName,
        state: entry.state,
        subject: entry.subject || "",
        issuer: entry.issuer || "",
        rootSubject: entry.rootSubject || "",
        rootIssuer: entry.rootIssuer || "",
        thumbprint: entry.thumbprint || "",
        summary: entry.summary || "",
      };
    });
}

function buildInternalBetaNotice({
  generatedAt,
  signer = {},
  outputRoot = "",
  includeSignerCert = false,
} = {}) {
  const signerSummary = signer.subject
    ? `${signer.subject} (${signer.issuer || "unknown issuer"})`
    : "unknown signer";
  const certLine = includeSignerCert
    ? `Tester trust certificate: ${path.join(outputRoot, INTERNAL_BETA_CERT)}`
    : "Tester trust certificate: not exported for this build route.";
  return [
    "FRANCIS OVERLAY INTERNAL BETA",
    "INTERNAL / QA / TESTER ONLY",
    "",
    "This bundle is not public-trust signed.",
    "Do not redistribute it as a public release.",
    "Do not describe it as Microsoft-trusted or store-grade signed.",
    "",
    `Generated: ${generatedAt}`,
    `Signer posture: ${signerSummary}`,
    `Output root: ${outputRoot}`,
    certLine,
    "",
    "Install caveat:",
    "- Approved testers may need to import the included signer certificate into Trusted People.",
    "- SmartScreen reputation can still warn even when the signer certificate is trusted locally.",
    "",
    `Operator doc: ${path.join(outputRoot, INTERNAL_BETA_INSTALL_DOC)}`,
  ].join("\n");
}

function buildInternalBetaManifest({
  sourceRoot = path.resolve(__dirname, ".."),
  generatedAt = new Date().toISOString(),
  includeSignerCert = false,
  outputRoot = "",
} = {}) {
  const resolvedSourceRoot = path.resolve(sourceRoot);
  const signingReport = loadGeneratedSigningReport(resolvedSourceRoot);
  const provenance = loadGeneratedProvenance(resolvedSourceRoot);
  const resolvedOutputRoot = resolveInternalBetaOutputRoot(resolvedSourceRoot, outputRoot);
  const packageVersion = normalizeVersion(provenance?.packageVersion);
  const artifacts = resolveInternalBetaArtifactEntries({
    sourceRoot: resolvedSourceRoot,
    signingReport,
    packageVersion,
  });
  if (!artifacts.length) {
    throw new Error("No signed top-level Windows artifacts were found for the internal beta bundle.");
  }

  const firstSigner = artifacts[0];
  const signer = {
    subject: firstSigner.subject || "",
    issuer: firstSigner.issuer || "",
    rootSubject: firstSigner.rootSubject || "",
    rootIssuer: firstSigner.rootIssuer || "",
    thumbprint: firstSigner.thumbprint || "",
    selfIssued:
      Boolean(firstSigner.subject) &&
      Boolean(firstSigner.issuer) &&
      String(firstSigner.subject).trim().toLowerCase() === String(firstSigner.issuer).trim().toLowerCase(),
  };

  return {
    version: 1,
    generatedAt,
    releaseChannel: "internal-beta",
    intendedAudience: "approved-testers-and-qa-only",
    trustClass: signer.selfIssued ? "machine-local-self-issued" : "machine-local-signed",
    publicTrustReleaseReady: false,
    canonicalCommand: "npm run release:publish:windows",
    blockedPublicCommand: "npm run release:publish:windows:public",
    summary:
      "Internal beta bundle for approved testers. Not a public-trust Windows release.",
    outputRoot: resolvedOutputRoot,
    packageVersion,
    sourceReports: {
      signingReportPath: resolveGeneratedSigningPath(resolvedSourceRoot),
      provenancePath: resolveGeneratedProvenancePath(resolvedSourceRoot),
    },
    signer,
    installDoc: {
      sourcePath: path.join(resolvedSourceRoot, INTERNAL_BETA_DOC_SOURCE),
      targetFileName: INTERNAL_BETA_INSTALL_DOC,
      targetPath: path.join(resolvedOutputRoot, INTERNAL_BETA_INSTALL_DOC),
    },
    exportedSignerCertificate: includeSignerCert
      ? {
          targetFileName: INTERNAL_BETA_CERT,
          targetPath: path.join(resolvedOutputRoot, INTERNAL_BETA_CERT),
        }
      : null,
    artifacts: artifacts.map((entry) => ({
      ...entry,
      targetPath: path.join(resolvedOutputRoot, entry.targetFileName),
    })),
    reportsToCopy: [
      {
        sourcePath: resolveGeneratedSigningPath(resolvedSourceRoot),
        targetPath: path.join(resolvedOutputRoot, path.basename(resolveGeneratedSigningPath(resolvedSourceRoot))),
      },
      {
        sourcePath: resolveGeneratedProvenancePath(resolvedSourceRoot),
        targetPath: path.join(resolvedOutputRoot, path.basename(resolveGeneratedProvenancePath(resolvedSourceRoot))),
      },
    ],
    noticePath: path.join(resolvedOutputRoot, INTERNAL_BETA_NOTICE),
    manifestPath: path.join(resolvedOutputRoot, INTERNAL_BETA_MANIFEST),
  };
}

function copyFileIfPresent(sourcePath, targetPath) {
  const stat = safeStat(sourcePath);
  if (!stat || !stat.isFile()) {
    return false;
  }
  ensureDirectory(path.dirname(targetPath));
  fs.copyFileSync(sourcePath, targetPath);
  return true;
}

function writeInternalBetaBundle(options = {}) {
  const manifest = buildInternalBetaManifest(options);
  fs.rmSync(manifest.outputRoot, { recursive: true, force: true });
  ensureDirectory(manifest.outputRoot);

  for (const artifact of manifest.artifacts) {
    copyFileIfPresent(artifact.sourcePath, artifact.targetPath);
  }
  for (const report of manifest.reportsToCopy) {
    copyFileIfPresent(report.sourcePath, report.targetPath);
  }
  copyFileIfPresent(manifest.installDoc.sourcePath, manifest.installDoc.targetPath);

  const notice = buildInternalBetaNotice({
    generatedAt: manifest.generatedAt,
    signer: manifest.signer,
    outputRoot: manifest.outputRoot,
    includeSignerCert: Boolean(manifest.exportedSignerCertificate),
  });
  fs.writeFileSync(manifest.noticePath, notice, "utf8");
  fs.writeFileSync(manifest.manifestPath, JSON.stringify(manifest, null, 2), "utf8");

  return manifest;
}

function main() {
  const includeSignerCert = process.argv.includes("--include-signer-cert");
  const outputRootArg = process.argv.find((entry) => entry.startsWith("--output-root="));
  const manifest = writeInternalBetaBundle({
    includeSignerCert,
    outputRoot: outputRootArg ? outputRootArg.slice("--output-root=".length) : "",
  });
  console.log(JSON.stringify(manifest, null, 2));
}

if (require.main === module) {
  main();
}

module.exports = {
  INTERNAL_BETA_CERT,
  INTERNAL_BETA_INSTALL_DOC,
  INTERNAL_BETA_MANIFEST,
  INTERNAL_BETA_NOTICE,
  buildInternalArtifactName,
  buildInternalBetaManifest,
  buildInternalBetaNotice,
  resolveInternalBetaArtifactEntries,
  resolveInternalBetaOutputRoot,
  writeInternalBetaBundle,
};
