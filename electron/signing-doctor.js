const childProcess = require("node:child_process");
const path = require("node:path");

const { loadGeneratedSigningReport } = require("./signature-state");

function normalizeIdentity(value = "") {
  return String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
}

function asArray(value) {
  if (Array.isArray(value)) {
    return value;
  }
  if (value == null) {
    return [];
  }
  return [value];
}

function normalizeCertificateRows(certificates = []) {
  return asArray(certificates).map((entry) => ({
    subject: String(entry.subject || entry.Subject || "").trim(),
    issuer: String(entry.issuer || entry.Issuer || "").trim(),
    thumbprint: String(entry.thumbprint || entry.Thumbprint || "").trim().toUpperCase(),
    enhancedKeyUsage: String(entry.enhancedKeyUsage || entry.EnhancedKeyUsage || "").trim(),
    hasPrivateKey: Boolean(
      entry.hasPrivateKey ??
        entry.HasPrivateKey ??
        entry.has_private_key ??
        false,
    ),
    store: String(entry.store || entry.Store || entry.PSParentPath || "").trim(),
  }));
}

function parseCertificateRows(rawValue = "") {
  const text = String(rawValue || "").trim();
  if (!text) {
    return [];
  }
  try {
    return normalizeCertificateRows(JSON.parse(text));
  } catch {
    return [];
  }
}

function loadWindowsCodeSigningCertificates({
  platform = process.platform,
  execFileSync = childProcess.execFileSync,
  shellCandidates = ["pwsh.exe", "powershell.exe"],
} = {}) {
  if (platform !== "win32") {
    return [];
  }

  const script = [
    '$stores = @("Cert:\\CurrentUser\\My", "Cert:\\LocalMachine\\My")',
    "$rows = foreach ($store in $stores) {",
    "  if (Test-Path $store) {",
    "    Get-ChildItem $store -CodeSigningCert | ForEach-Object {",
    "      [PSCustomObject]@{",
    "        subject = $_.Subject",
    "        issuer = $_.Issuer",
    "        thumbprint = $_.Thumbprint",
    "        enhancedKeyUsage = ($_.EnhancedKeyUsageList | ForEach-Object { $_.FriendlyName }) -join '; '",
    "        hasPrivateKey = [bool]$_.HasPrivateKey",
    "        store = $store",
    "      }",
    "    }",
    "  }",
    "}",
    "if ($null -eq $rows) { @() | ConvertTo-Json -Compress } else { $rows | ConvertTo-Json -Depth 4 -Compress }",
  ].join("\n");

  for (const shellPath of shellCandidates) {
    try {
      const raw = execFileSync(
        shellPath,
        [
          "-NoProfile",
          "-NonInteractive",
          "-ExecutionPolicy",
          "Bypass",
          "-Command",
          script,
        ],
        {
          encoding: "utf8",
          windowsHide: true,
        },
      );
      return parseCertificateRows(raw);
    } catch {
      // Try the next shell candidate.
    }
  }

  return [];
}

function buildSigningDoctor({
  env = process.env,
  certificates = [],
  signingReport = null,
} = {}) {
  const azureEndpoint = String(env.FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT || "").trim();
  const azureAccount = String(env.FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME || "").trim();
  const azureProfile = String(env.FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME || "").trim();
  const azurePublisher = String(env.FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME || "").trim();
  const azureClient = String(env.AZURE_CLIENT_ID || "").trim();
  const azureTenant = String(env.AZURE_TENANT_ID || "").trim();
  const azureSecret = String(env.AZURE_CLIENT_SECRET || "").trim();
  const azureCertificatePath = String(env.AZURE_CLIENT_CERTIFICATE_PATH || "").trim();
  const azureUsername = String(env.AZURE_USERNAME || "").trim();
  const azurePassword = String(env.AZURE_PASSWORD || "").trim();
  const localCertificate = String(env.WIN_CSC_LINK || env.CSC_LINK || "").trim();
  const localPassword = String(env.WIN_CSC_KEY_PASSWORD || env.CSC_KEY_PASSWORD || "").trim();
  const localStoreSubject = String(env.FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME || "").trim();
  const localStoreSha1 = String(env.FRANCIS_WINDOWS_SIGNING_SHA1 || "").trim();

  const azureAuthReady = Boolean(
    azureClient &&
      azureTenant &&
      (azureSecret || azureCertificatePath || (azureUsername && azurePassword)),
  );
  const azureReady = Boolean(azureEndpoint && azureAccount && azureProfile && azureAuthReady);
  const localPfxReady = Boolean(localCertificate && localPassword);
  const localStoreReady = Boolean(localStoreSubject || localStoreSha1);

  const certificateRows = normalizeCertificateRows(certificates);
  const normalizedPublisher = normalizeIdentity(azurePublisher);
  const publicTrustCandidates = certificateRows.filter((entry) => {
    const subject = normalizeIdentity(entry.subject);
    const issuer = normalizeIdentity(entry.issuer);
    return entry.hasPrivateKey && subject && issuer && subject !== issuer;
  });
  const selfIssuedPrivateKeyCertificates = certificateRows.filter((entry) => {
    const subject = normalizeIdentity(entry.subject);
    const issuer = normalizeIdentity(entry.issuer);
    return entry.hasPrivateKey && subject && subject === issuer;
  });
  const matchingPublisherCandidates = publicTrustCandidates.filter((entry) =>
    normalizedPublisher ? normalizeIdentity(entry.subject).includes(normalizedPublisher) : true,
  );

  const signedArtifactCount = Number(signingReport?.counts?.signed || 0);
  const signedArtifacts = asArray(signingReport?.artifacts).filter((entry) => entry?.state === "signed");
  const currentArtifactsSigned =
    signedArtifactCount > 0 && signedArtifacts.length === signedArtifactCount;

  const blockingReasons = [];
  if (!normalizedPublisher) {
    blockingReasons.push("missing_publisher_hint");
  }
  if (!azureReady) {
    if (!publicTrustCandidates.length) {
      blockingReasons.push(
        selfIssuedPrivateKeyCertificates.length > 0
          ? "self_issued_only"
          : "no_public_trust_certificate",
      );
    } else if (normalizedPublisher && matchingPublisherCandidates.length === 0) {
      blockingReasons.push("publisher_mismatch");
    }
  }

  const publicReleaseReady =
    (azureReady && Boolean(normalizedPublisher)) ||
    (Boolean(normalizedPublisher) && matchingPublisherCandidates.length > 0);
  const signedPackagingReady =
    azureReady || localPfxReady || localStoreReady || currentArtifactsSigned;

  const nextSteps = [];
  if (!azurePublisher) {
    nextSteps.push(
      "Set FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME to the exact legal publisher name in the release certificate.",
    );
  }
  if (selfIssuedPrivateKeyCertificates.length > 0 && !publicTrustCandidates.length) {
    nextSteps.push(
      "Replace the self-issued Windows code-signing certificate with a non-self-issued publisher certificate or Azure Trusted Signing identity before attempting public release.",
    );
  } else if (!azureReady && matchingPublisherCandidates.length === 0) {
    nextSteps.push(
      "Provision either Azure Trusted Signing credentials or a non-self-issued Windows code-signing certificate whose subject matches FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME.",
    );
  }
  if (signedPackagingReady && !publicReleaseReady) {
    nextSteps.push(
      "Use npm run release:publish:windows for machine-local signed builds, and reserve npm run release:publish:windows:public for a real publisher identity.",
    );
  }
  if (publicReleaseReady) {
    nextSteps.push("Run npm run release:publish:windows:public.");
  }

  return {
    status: publicReleaseReady ? "ready" : "blocked",
    signedPackagingReady,
    publicReleaseReady,
    blockingReason: blockingReasons[0] || "",
    blockingReasons,
    configuredPaths: {
      localPfxReady,
      localStoreReady,
      azureReady,
    },
    publisherName: azurePublisher,
    certificates: {
      total: certificateRows.length,
      publicTrustCandidates: publicTrustCandidates.length,
      selfIssuedPrivateKeyCertificates: selfIssuedPrivateKeyCertificates.length,
      matchingPublisherCandidates: matchingPublisherCandidates.length,
      entries: certificateRows,
    },
    currentSigningReport: {
      signedArtifactCount,
      currentArtifactsSigned,
      reportPath: path.join("electron", "generated", "build-signing.json"),
    },
    nextSteps,
  };
}

function runSigningDoctor({
  sourceRoot = path.resolve(__dirname, ".."),
  env = process.env,
  platform = process.platform,
} = {}) {
  const signingReport = loadGeneratedSigningReport(sourceRoot);
  const certificates = loadWindowsCodeSigningCertificates({ platform });
  return buildSigningDoctor({
    env,
    certificates,
    signingReport,
  });
}

function main() {
  const report = runSigningDoctor();
  console.log(JSON.stringify(report, null, 2));
}

if (require.main === module) {
  main();
}

module.exports = {
  buildSigningDoctor,
  loadWindowsCodeSigningCertificates,
  parseCertificateRows,
  runSigningDoctor,
};
