const childProcess = require("node:child_process");
const path = require("node:path");

const { loadGeneratedSigningReport } = require("./signature-state");
const { readConfiguredEnvValue } = require("./signing-env");

function normalizeIdentity(value = "") {
  return String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
}

function normalizePublisherDisplay(value = "") {
  return String(value || "").trim().replace(/^CN=/i, "").trim();
}

function quotePowerShell(value = "") {
  return `'${String(value || "").replace(/'/g, "''")}'`;
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

function buildPowerShellSuggestion({
  env = {},
  command = "",
  available = true,
  reason = "",
} = {}) {
  const envEntries = Object.entries(env).filter(([, value]) => String(value || "").trim());
  return {
    available,
    reason: available ? "" : reason,
    env,
    lines: available
      ? [
          ...envEntries.map(([key, value]) => `$env:${key}=${quotePowerShell(value)}`),
          ...(command ? [command] : []),
        ]
      : [],
  };
}

function buildSigningDoctor({
  env = process.env,
  certificates = [],
  signingReport = null,
} = {}) {
  const azureEndpoint = readConfiguredEnvValue(env, ["FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT"]);
  const azureAccount = readConfiguredEnvValue(env, ["FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME"]);
  const azureProfile = readConfiguredEnvValue(env, ["FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME"]);
  const azurePublisher = readConfiguredEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME"]);
  const chainHint = readConfiguredEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_CHAIN_HINT"]);
  const azureClient = readConfiguredEnvValue(env, ["AZURE_CLIENT_ID"]);
  const azureTenant = readConfiguredEnvValue(env, ["AZURE_TENANT_ID"]);
  const azureSecret = readConfiguredEnvValue(env, ["AZURE_CLIENT_SECRET"]);
  const azureCertificatePath = readConfiguredEnvValue(env, ["AZURE_CLIENT_CERTIFICATE_PATH"]);
  const azureUsername = readConfiguredEnvValue(env, ["AZURE_USERNAME"]);
  const azurePassword = readConfiguredEnvValue(env, ["AZURE_PASSWORD"]);
  const localCertificate = readConfiguredEnvValue(env, ["WIN_CSC_LINK", "CSC_LINK"]);
  const localPassword = readConfiguredEnvValue(env, ["WIN_CSC_KEY_PASSWORD", "CSC_KEY_PASSWORD"]);
  const localStoreSubject = readConfiguredEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME"]);
  const localStoreSha1 = readConfiguredEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_SHA1"]);

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
  const normalizedChainHint = normalizeIdentity(chainHint);
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
  if (!normalizedChainHint) {
    blockingReasons.push("missing_chain_hint");
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
    (azureReady && Boolean(normalizedPublisher) && Boolean(normalizedChainHint)) ||
    (Boolean(normalizedPublisher) && Boolean(normalizedChainHint) && matchingPublisherCandidates.length > 0);
  const signedPackagingReady =
    azureReady || localPfxReady || localStoreReady || currentArtifactsSigned;
  const localStoreCandidates = certificateRows.filter((entry) => entry.hasPrivateKey);
  const preferredMachineLocalCandidate =
    localStoreCandidates[0] || null;
  const preferredPublicCertStoreCandidate =
    matchingPublisherCandidates[0] ||
    (!normalizedPublisher ? publicTrustCandidates[0] : null) ||
    null;

  const nextSteps = [];
  if (!azurePublisher) {
    nextSteps.push(
      "Set FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME to the exact legal publisher name in the release certificate.",
    );
  }
  if (!chainHint) {
    nextSteps.push(
      "Set FRANCIS_WINDOWS_SIGNING_CHAIN_HINT to the expected non-leaf issuer or chain identity for the public release signer.",
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

  const suggestedPowerShell = {
    machineLocalSignedBuild: preferredMachineLocalCandidate
      ? buildPowerShellSuggestion({
          env: {
            FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME: normalizePublisherDisplay(
              preferredMachineLocalCandidate.subject,
            ),
            FRANCIS_WINDOWS_SIGNING_SHA1: preferredMachineLocalCandidate.thumbprint,
          },
          command: "npm run release:publish:windows",
        })
      : buildPowerShellSuggestion({
          available: false,
          reason: "no_local_signing_certificate",
        }),
    publicReleaseCertStore: preferredPublicCertStoreCandidate
      ? buildPowerShellSuggestion({
          env: {
            FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME:
              azurePublisher || normalizePublisherDisplay(preferredPublicCertStoreCandidate.subject),
            FRANCIS_WINDOWS_SIGNING_CHAIN_HINT:
              chainHint || normalizePublisherDisplay(preferredPublicCertStoreCandidate.issuer),
            FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME: normalizePublisherDisplay(
              preferredPublicCertStoreCandidate.subject,
            ),
            FRANCIS_WINDOWS_SIGNING_SHA1: preferredPublicCertStoreCandidate.thumbprint,
          },
          command: "npm run release:publish:windows:public",
        })
      : buildPowerShellSuggestion({
          available: false,
          reason: selfIssuedPrivateKeyCertificates.length > 0
            ? "self_issued_only"
            : "no_public_trust_certificate",
        }),
    publicReleaseAzureTrustedSigning: buildPowerShellSuggestion({
      env: {
        FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME: azurePublisher || "<legal publisher name>",
        FRANCIS_WINDOWS_SIGNING_CHAIN_HINT: chainHint || "<expected issuer or chain hint>",
        FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT:
          azureEndpoint || "https://<region>.codesigning.azure.net/",
        FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME:
          azureAccount || "<trusted-signing-account>",
        FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME:
          azureProfile || "<certificate-profile>",
        AZURE_CLIENT_ID: azureClient || "<entra-client-id>",
        AZURE_TENANT_ID: azureTenant || "<entra-tenant-id>",
        AZURE_CLIENT_SECRET: azureSecret || "<entra-client-secret>",
      },
      command: "npm run release:publish:windows:public",
    }),
  };

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
    chainHint,
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
    suggestedPowerShell,
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

function validateSigningDoctorReport(
  report,
  {
    requirePublicReady = false,
  } = {},
) {
  if (!requirePublicReady) {
    return {
      ok: true,
      reasons: [],
    };
  }

  return {
    ok: Boolean(report?.publicReleaseReady),
    reasons: Array.isArray(report?.blockingReasons)
      ? report.blockingReasons
      : report?.blockingReason
        ? [report.blockingReason]
        : [],
  };
}

function main() {
  const requirePublicReady = process.argv.includes("--require-public-ready");
  const report = runSigningDoctor();
  console.log(JSON.stringify(report, null, 2));

  const validation = validateSigningDoctorReport(report, {
    requirePublicReady,
  });
  if (!validation.ok) {
    const reasons = validation.reasons.length
      ? validation.reasons.join(", ")
      : "not_ready";
    console.error(
      `[francis-overlay] Public signing is not ready: ${reasons}`,
    );
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  buildSigningDoctor,
  loadWindowsCodeSigningCertificates,
  parseCertificateRows,
  runSigningDoctor,
  validateSigningDoctorReport,
};
