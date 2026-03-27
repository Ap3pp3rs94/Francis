const fs = require("node:fs");
const path = require("node:path");
const childProcess = require("node:child_process");

const GENERATED_SIGNING_DIR = path.join("electron", "generated");
const GENERATED_SIGNING_FILE = "build-signing.json";
const GENERATED_PROVENANCE_FILE = "build-provenance.json";

function safeStat(targetPath) {
  try {
    return fs.statSync(targetPath);
  } catch {
    return null;
  }
}

function resolveSignToolPath(env = process.env) {
  const explicitPath = typeof env.FRANCIS_SIGNTOOL_PATH === "string" ? env.FRANCIS_SIGNTOOL_PATH.trim() : "";
  const candidates = [
    explicitPath,
    path.resolve(__dirname, "..", "node_modules", "@electron", "windows-sign", "vendor", "signtool.exe"),
    path.resolve(__dirname, "..", "node_modules", "electron-winstaller", "vendor", "signtool.exe"),
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return "";
}

function normalizeAuthenticodeState(status = "") {
  const normalized = String(status || "").trim();
  if (!normalized) {
    return "unavailable";
  }
  if (/^valid$/i.test(normalized)) {
    return "signed";
  }
  if (/^notsigned$/i.test(normalized)) {
    return "unsigned";
  }
  return "invalid";
}

function summarizeSignatureRecord(record = {}) {
  switch (record.state) {
    case "signed":
      return record.subject
        ? `Valid Authenticode signature for ${record.subject}.`
        : "Valid Authenticode signature.";
    case "unsigned":
      return "No Authenticode signature is present.";
    case "invalid":
      return record.statusMessage
        ? `Authenticode signature is present but not valid: ${record.statusMessage}`
        : `Authenticode signature status is ${record.status || "invalid"}.`;
    case "missing":
      return "Expected artifact is missing.";
    default:
      return record.statusMessage || "Authenticode inspection is unavailable.";
  }
}

function createSignatureRecord({
  path: filePath,
  exists = false,
  state = "unavailable",
  status = "",
  statusMessage = "",
  subject = "",
  issuer = "",
  chainSubjects = [],
  chainIssuers = [],
  rootSubject = "",
  rootIssuer = "",
  thumbprint = "",
  notAfter = "",
  checkedAt = new Date().toISOString(),
} = {}) {
  const record = {
    path: filePath || "",
    exists: Boolean(exists),
    state,
    status: status || "",
    statusMessage: statusMessage || "",
    subject: subject || "",
    issuer: issuer || "",
    chainSubjects: Array.isArray(chainSubjects) ? chainSubjects.filter(Boolean) : [],
    chainIssuers: Array.isArray(chainIssuers) ? chainIssuers.filter(Boolean) : [],
    rootSubject: rootSubject || "",
    rootIssuer: rootIssuer || "",
    thumbprint: thumbprint || "",
    notAfter: notAfter || "",
    checkedAt,
  };
  return {
    ...record,
    summary: summarizeSignatureRecord(record),
  };
}

function parseSigntoolOutput(output, resolvedPath) {
  const text = String(output || "");
  const firstMatch = (pattern, input = text) => {
    const match = input.match(pattern);
    return match ? match[1].trim() : "";
  };
  const lastMatch = (pattern) => {
    const matches = [...text.matchAll(pattern)];
    return matches.length ? matches[matches.length - 1][1].trim() : "";
  };
  const primaryChainSection =
    firstMatch(
      /Signing Certificate Chain:\s*([\s\S]*?)(?:\r?\n\s*\r?\n(?:The signature is timestamped:|Successfully verified:)|\r?\n(?:The signature is timestamped:|Successfully verified:)|$)/i,
    ) || text;
  const primaryChainSubjects = [...primaryChainSection.matchAll(/Issued to:\s+([^\r\n]+)/gi)].map((match) =>
    match[1].trim(),
  );
  const primaryChainIssuers = [...primaryChainSection.matchAll(/Issued by:\s+([^\r\n]+)/gi)].map((match) =>
    match[1].trim(),
  );

  if (/No signature found/i.test(text)) {
    return createSignatureRecord({
      path: resolvedPath,
      exists: true,
      state: "unsigned",
      status: "NotSigned",
      statusMessage: "No signature found.",
    });
  }

  if (/(^|\r?\n)Successfully verified:/i.test(text) || /Number of files successfully Verified:\s+1(\D|$)/i.test(text)) {
    return createSignatureRecord({
      path: resolvedPath,
      exists: true,
      state: "signed",
      status: "Valid",
      statusMessage: "Successfully verified by signtool.",
      subject:
        firstMatch(/Issued to:\s+([^\r\n]+)/i, primaryChainSection) ||
        lastMatch(/Issued to:\s+([^\r\n]+)/gi),
      issuer:
        firstMatch(/Issued by:\s+([^\r\n]+)/i, primaryChainSection) ||
        lastMatch(/Issued by:\s+([^\r\n]+)/gi),
      chainSubjects: primaryChainSubjects,
      chainIssuers: primaryChainIssuers,
      rootSubject:
        primaryChainSubjects[primaryChainSubjects.length - 1] ||
        lastMatch(/Issued to:\s+([^\r\n]+)/gi),
      rootIssuer:
        primaryChainIssuers[primaryChainIssuers.length - 1] ||
        lastMatch(/Issued by:\s+([^\r\n]+)/gi),
      notAfter:
        firstMatch(/Expires:\s+([^\r\n]+)/i, primaryChainSection) ||
        lastMatch(/Expires:\s+([^\r\n]+)/gi),
      thumbprint:
        firstMatch(/SHA1 hash:\s+([A-Fa-f0-9]+)/i, primaryChainSection) ||
        lastMatch(/SHA1 hash:\s+([A-Fa-f0-9]+)/gi),
    });
  }

  return createSignatureRecord({
    path: resolvedPath,
    exists: true,
    state: "invalid",
    status: "VerifyFailed",
    statusMessage:
      lastMatch(/SignTool Error:\s*([^\r\n]+)/gi) ||
      text.trim() ||
      "signtool verification failed.",
  });
}

function inspectAuthenticodeSignature(
  filePath,
  {
    execFileSync = childProcess.execFileSync,
    env = process.env,
  } = {},
) {
  const resolvedPath = path.resolve(String(filePath || ""));
  const stat = safeStat(resolvedPath);

  if (!stat || !stat.isFile()) {
    return createSignatureRecord({
      path: resolvedPath,
      exists: false,
      state: "missing",
      status: "MissingFile",
      statusMessage: "Expected file does not exist.",
    });
  }

  if (process.platform !== "win32") {
    return createSignatureRecord({
      path: resolvedPath,
      exists: true,
      state: "unavailable",
      status: "UnsupportedPlatform",
      statusMessage: `Authenticode inspection requires Windows; current platform is ${process.platform}.`,
    });
  }

  const signToolPath = resolveSignToolPath(env);
  if (!signToolPath) {
    return createSignatureRecord({
      path: resolvedPath,
      exists: true,
      state: "unavailable",
      status: "VerifierUnavailable",
      statusMessage: "signtool.exe is not available for Authenticode verification.",
    });
  }

  try {
    const raw = execFileSync(
      signToolPath,
      ["verify", "/pa", "/v", resolvedPath],
      {
        encoding: "utf8",
        windowsHide: true,
      },
    );
    return parseSigntoolOutput(raw, resolvedPath);
  } catch (error) {
    const combinedOutput = `${error?.stdout || ""}${error?.stderr || ""}`;
    if (combinedOutput) {
      return parseSigntoolOutput(combinedOutput, resolvedPath);
    }
    return createSignatureRecord({
      path: resolvedPath,
      exists: true,
      state: "unavailable",
      status: "InspectionFailed",
      statusMessage: error instanceof Error ? error.message : String(error),
    });
  }
}

function buildSigningSummary(counts = {}, artifactCount = 0) {
  if (!artifactCount) {
    return "No packaged overlay artifacts were found for Authenticode verification.";
  }
  if (counts.invalid > 0) {
    return `${counts.invalid} artifact${counts.invalid === 1 ? "" : "s"} have invalid or untrusted Authenticode signatures.`;
  }
  if (counts.unsigned > 0) {
    return `${counts.unsigned} artifact${counts.unsigned === 1 ? "" : "s"} are unsigned.`;
  }
  if (counts.unavailable > 0) {
    return `${counts.unavailable} artifact${counts.unavailable === 1 ? "" : "s"} could not be inspected for Authenticode state.`;
  }
  if (counts.missing > 0) {
    return `${counts.missing} expected artifact${counts.missing === 1 ? "" : "s"} are missing.`;
  }
  if (counts.signed > 0) {
    return `${counts.signed} artifact${counts.signed === 1 ? "" : "s"} carry valid Authenticode signatures.`;
  }
  return "Authenticode verification completed without any matching packaged artifacts.";
}

function buildArtifactSigningReport({
  artifactPaths = [],
  platform = process.platform,
  execFileSync = childProcess.execFileSync,
  generatedAt = new Date().toISOString(),
} = {}) {
  const uniqueArtifactPaths = [...new Set((artifactPaths || []).filter(Boolean).map((entry) => path.resolve(String(entry))))];
  const artifacts = uniqueArtifactPaths.map((artifactPath) =>
    inspectAuthenticodeSignature(artifactPath, {
      platform,
      execFileSync,
    }),
  );
  const counts = {
    signed: artifacts.filter((entry) => entry.state === "signed").length,
    unsigned: artifacts.filter((entry) => entry.state === "unsigned").length,
    invalid: artifacts.filter((entry) => entry.state === "invalid").length,
    missing: artifacts.filter((entry) => entry.state === "missing").length,
    unavailable: artifacts.filter((entry) => entry.state === "unavailable").length,
  };

  return {
    version: 1,
    generatedAt,
    summary: buildSigningSummary(counts, artifacts.length),
    counts,
    artifacts,
  };
}

function normalizeIdentityValue(value = "") {
  return String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
}

function validateSigningReport(
  report,
  {
    requireSigned = false,
    requirePublisherName = "",
    rejectSelfIssued = false,
  } = {},
) {
  const normalizedPublisherName = normalizeIdentityValue(requirePublisherName);
  if (!requireSigned && !normalizedPublisherName && !rejectSelfIssued) {
    return {
      ok: true,
      failures: [],
    };
  }

  const failures = [];
  for (const entry of report?.artifacts || []) {
    if (requireSigned && entry.state !== "signed") {
      failures.push({
        ...entry,
        reason: entry.state,
      });
      continue;
    }

    if (entry.state !== "signed") {
      continue;
    }

    const normalizedSubject = normalizeIdentityValue(entry.subject);
    const normalizedIssuer = normalizeIdentityValue(entry.issuer);

    if (normalizedPublisherName && !normalizedSubject.includes(normalizedPublisherName)) {
      failures.push({
        ...entry,
        reason: "publisher_mismatch",
      });
      continue;
    }

    if (rejectSelfIssued && normalizedSubject && normalizedSubject === normalizedIssuer) {
      failures.push({
        ...entry,
        reason: "self_issued",
      });
    }
  }
  return {
    ok: failures.length === 0 && (report?.artifacts || []).length > 0,
    failures,
  };
}

function resolveGeneratedSigningPath(sourceRoot) {
  return path.join(sourceRoot, GENERATED_SIGNING_DIR, GENERATED_SIGNING_FILE);
}

function writeGeneratedSigningReport(sourceRoot, report) {
  const filePath = resolveGeneratedSigningPath(sourceRoot);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(report, null, 2), "utf8");
  return filePath;
}

function loadGeneratedSigningReport(sourceRoot) {
  const filePath = resolveGeneratedSigningPath(sourceRoot);
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

function resolveGeneratedProvenancePath(sourceRoot) {
  return path.join(sourceRoot, GENERATED_SIGNING_DIR, GENERATED_PROVENANCE_FILE);
}

function loadGeneratedBuildProvenance(sourceRoot) {
  const filePath = resolveGeneratedProvenancePath(sourceRoot);
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

function resolveOverlayArtifactPaths(sourceRoot) {
  const distRoot = path.join(sourceRoot, "dist", "overlay");
  const buildProvenance = loadGeneratedBuildProvenance(sourceRoot);
  const buildStartMs = Date.parse(String(buildProvenance?.generatedAt || ""));
  const topLevelArtifacts = [];
  try {
    for (const entry of fs.readdirSync(distRoot, { withFileTypes: true })) {
      if (entry.isFile() && entry.name.toLowerCase().endsWith(".exe")) {
        const artifactPath = path.join(distRoot, entry.name);
        const artifactStat = safeStat(artifactPath);
        if (
          Number.isFinite(buildStartMs) &&
          artifactStat &&
          artifactStat.mtimeMs < buildStartMs
        ) {
          continue;
        }
        topLevelArtifacts.push(artifactPath);
      }
    }
  } catch {
    // Missing dist artifacts are surfaced in the report.
  }

  const packageJsonPath = path.join(sourceRoot, "package.json");
  let productName = "Francis Overlay";
  try {
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
    productName = packageJson?.build?.productName || productName;
  } catch {
    // Fall back to the default product name.
  }

  return [
    path.join(distRoot, "win-unpacked", `${productName}.exe`),
    ...topLevelArtifacts,
  ];
}

module.exports = {
  GENERATED_PROVENANCE_FILE,
  GENERATED_SIGNING_DIR,
  GENERATED_SIGNING_FILE,
  buildArtifactSigningReport,
  inspectAuthenticodeSignature,
  loadGeneratedBuildProvenance,
  loadGeneratedSigningReport,
  normalizeAuthenticodeState,
  resolveSignToolPath,
  resolveGeneratedProvenancePath,
  resolveGeneratedSigningPath,
  resolveOverlayArtifactPaths,
  validateSigningReport,
  writeGeneratedSigningReport,
};
