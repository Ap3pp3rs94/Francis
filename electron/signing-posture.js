const { readConfiguredEnvValue } = require("./signing-env");

function normalizeVerifiedExecutable(entry = null) {
  if (!entry || typeof entry !== "object") {
    return null;
  }
  return {
    path: typeof entry.path === "string" ? entry.path : "",
    state: typeof entry.state === "string" ? entry.state : "unavailable",
    status: typeof entry.status === "string" ? entry.status : "",
    statusMessage: typeof entry.statusMessage === "string" ? entry.statusMessage : "",
    subject: typeof entry.subject === "string" ? entry.subject : "",
    issuer: typeof entry.issuer === "string" ? entry.issuer : "",
    thumbprint: typeof entry.thumbprint === "string" ? entry.thumbprint : "",
    notAfter: typeof entry.notAfter === "string" ? entry.notAfter : "",
    checkedAt: typeof entry.checkedAt === "string" ? entry.checkedAt : "",
    summary: typeof entry.summary === "string" ? entry.summary : "",
  };
}

function buildSigningPosture({
  env = process.env,
  distribution = "source",
  packaged = false,
  verifiedExecutable = null,
} = {}) {
  const localCertificate = readConfiguredEnvValue(env, ["WIN_CSC_LINK", "CSC_LINK"]);
  const localPassword = readConfiguredEnvValue(env, ["WIN_CSC_KEY_PASSWORD", "CSC_KEY_PASSWORD"]);
  const localStoreSubject = readConfiguredEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME"]);
  const localStoreSha1 = readConfiguredEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_SHA1"]);
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
  const signpathToken = readConfiguredEnvValue(env, ["SIGNPATH_API_TOKEN"]);
  const signpathProject = readConfiguredEnvValue(env, ["SIGNPATH_PROJECT_SLUG", "SIGNPATH_ORGANIZATION_ID"]);
  const requiresSigning = distribution === "installer" || distribution === "portable";
  const verified = normalizeVerifiedExecutable(verifiedExecutable);

  const localFileReady = Boolean(localCertificate && localPassword);
  const localStoreReady = Boolean(localStoreSubject || localStoreSha1);
  const localReady = localFileReady || localStoreReady;
  const azureAuthReady = Boolean(
    azureClient &&
      azureTenant &&
      (azureSecret || azureCertificatePath || (azureUsername && azurePassword)),
  );
  const azureReady = Boolean(azureEndpoint && azureAccount && azureProfile && azureAuthReady);
  const signpathSignals = Boolean(signpathToken || signpathProject);
  const anySignals = Boolean(
    localCertificate ||
      localPassword ||
      localStoreSubject ||
      localStoreSha1 ||
      azureEndpoint ||
      azureAccount ||
      azureProfile ||
      azurePublisher ||
      chainHint ||
      azureClient ||
      azureTenant ||
      azureSecret ||
      azureCertificatePath ||
      azureUsername ||
      azurePassword ||
      signpathSignals,
  );

  let mode = "unsigned";
  let severity = "low";
  let summary = "Code signing is not active in this source checkout.";

  if (packaged && verified?.state === "signed") {
    mode = "signed";
    severity = "low";
    summary = verified.summary || "Packaged Windows build carries a valid Authenticode signature.";
  } else if (packaged && verified?.state === "invalid") {
    mode = "invalid";
    severity = "high";
    summary = verified.summary || "Packaged Windows build signature is present but not valid.";
  } else if (localReady) {
    mode = "local_certificate";
    summary = localStoreReady
      ? "Windows signing material is configured through a Windows certificate-store selector."
      : "Windows signing material is configured through a local certificate path.";
  } else if (azureReady) {
    mode = "cloud_signing";
    summary = "Windows signing material is configured through Azure Trusted Signing.";
  } else if (signpathSignals) {
    mode = "partial";
    severity = "high";
    summary = "SignPath inputs are present, but the overlay build is not wired to SignPath. Use Azure Trusted Signing or local certificate signing.";
  } else if (anySignals) {
    mode = "partial";
    severity = "high";
    summary = "Signing configuration is partial. Packaging trust cannot be treated as ready until the signer inputs are complete.";
  } else if (requiresSigning) {
    mode = "unsigned";
    severity = "medium";
    summary = "Packaged Windows builds are currently unsigned. Installer trust remains blocked on certificate material.";
  } else if (packaged) {
    mode = "unsigned";
    severity = "medium";
    summary = "Packaged build posture is visible, but no signing material is configured.";
  }

  const configuredPaths = [];
  if (localCertificate) {
    configuredPaths.push("local certificate");
  }
  if (localStoreReady) {
    configuredPaths.push("Windows cert store");
  }
  if (azureReady || azureEndpoint || azureAccount || azureProfile || azurePublisher) {
    configuredPaths.push("Azure Trusted Signing");
  }
  if (signpathSignals) {
    configuredPaths.push("SignPath");
  }

  const verificationState =
    packaged && verified
      ? verified.state
      : packaged
        ? "unavailable"
        : "not_applicable";
  const verificationSummary =
    packaged && verified
      ? verified.summary
      : packaged
        ? "Packaged executable verification has not been captured yet."
        : "Source checkout does not require packaged Authenticode verification.";
  const ready = packaged
    ? verified?.state === "signed"
    : localReady || azureReady;

  return {
    severity,
    mode,
    summary,
    requiresSigning,
    ready,
    configuredPaths,
    verification: {
      state: verificationState,
      summary: verificationSummary,
      path: verified?.path || "",
      status: verified?.status || "",
      subject: verified?.subject || "",
      issuer: verified?.issuer || "",
      thumbprint: verified?.thumbprint || "",
      notAfter: verified?.notAfter || "",
      checkedAt: verified?.checkedAt || "",
    },
    cards: [
      {
        label: "Summary",
        value: summary,
        tone: severity,
      },
      {
        label: "Mode",
        value: mode,
        tone: severity,
      },
      {
        label: "Distribution",
        value: distribution,
        tone: requiresSigning ? "medium" : "low",
      },
      {
        label: "Readiness",
        value: ready ? "ready" : anySignals ? "partial" : packaged ? "missing" : "missing",
        tone: ready ? "low" : anySignals ? "high" : requiresSigning ? "medium" : "low",
      },
      {
        label: "Paths",
        value: configuredPaths.length ? configuredPaths.join(", ") : "none",
        tone: configuredPaths.length ? "medium" : requiresSigning ? "medium" : "low",
      },
      {
        label: "Packaging",
        value: requiresSigning ? "signature expected" : "source-only",
        tone: requiresSigning ? "medium" : "low",
      },
      {
        label: "Verification",
        value: verificationState.replaceAll("_", " "),
        tone:
          verificationState === "signed"
            ? "low"
            : verificationState === "invalid"
              ? "high"
              : verificationState === "unsigned"
                ? "medium"
                : requiresSigning
                  ? "medium"
                  : "low",
      },
    ],
    items: [
      {
        id: "certificate",
        label: "Local signing",
        tone:
          localReady
            ? "low"
            : localCertificate || localPassword || localStoreSubject || localStoreSha1
              ? "high"
              : "low",
        summary: localFileReady
          ? "Certificate path and password are configured."
          : localStoreReady
            ? localStoreSubject && localStoreSha1
              ? "Windows cert-store subject and thumbprint selectors are configured."
              : "A Windows cert-store selector is configured."
            : localCertificate || localPassword
              ? "Certificate path or password is present, but the local signer is incomplete."
              : localStoreSubject || localStoreSha1
                ? "A Windows cert-store selector is present, but it is incomplete."
                : "No local certificate path or Windows cert-store selector is configured.",
      },
      {
        id: "azure",
        label: "Azure Trusted Signing",
        tone:
          azureReady
            ? "low"
            : azureEndpoint ||
                azureAccount ||
                azureProfile ||
                azurePublisher ||
                azureClient ||
                azureTenant ||
                azureSecret ||
                azureCertificatePath ||
                azureUsername ||
                azurePassword
              ? "high"
              : "low",
        summary: azureReady
          ? "Azure Trusted Signing inputs are complete."
          : azureEndpoint ||
              azureAccount ||
              azureProfile ||
              azurePublisher ||
              azureClient ||
              azureTenant ||
              azureSecret ||
              azureCertificatePath ||
              azureUsername ||
              azurePassword
            ? "Azure Trusted Signing inputs are present, but the signer is incomplete."
            : "No Azure Trusted Signing inputs are configured.",
      },
      {
        id: "signpath",
        label: "SignPath",
        tone: signpathSignals ? "high" : "low",
        summary: signpathSignals
          ? "SignPath inputs are present, but the overlay build is not wired to SignPath."
          : "No SignPath signing inputs are configured.",
      },
      {
        id: "verification",
        label: "Authenticode verification",
        tone:
          verificationState === "signed"
            ? "low"
            : verificationState === "invalid"
              ? "high"
              : verificationState === "unsigned"
                ? "medium"
                : requiresSigning
                  ? "medium"
                  : "low",
        summary:
          verificationState === "not_applicable"
            ? "Source checkout does not require packaged Authenticode verification."
            : verificationSummary,
      },
      {
        id: "publisher",
        label: "Publisher hint",
        tone: azurePublisher ? "medium" : "low",
        summary: azurePublisher
          ? `Expected publisher hint is ${azurePublisher}.`
          : "No publisher hint is configured.",
      },
      {
        id: "chain_hint",
        label: "Chain hint",
        tone: chainHint ? "medium" : "low",
        summary: chainHint
          ? `Expected non-leaf chain hint is ${chainHint}.`
          : "No public chain hint is configured.",
      },
      {
        id: "signing_mode",
        label: "Packaging route",
        tone: azureReady || localReady ? "low" : requiresSigning ? "medium" : "low",
        summary: azureReady
          ? "Electron Builder will use Azure Trusted Signing when packaging."
          : localReady
            ? localStoreReady
              ? "Electron Builder will use signtool with Windows cert-store selection when packaging."
              : "Electron Builder will use signtool/local certificate signing when packaging."
            : requiresSigning
              ? "Packaging will remain unsigned until a supported signing route is configured."
              : "Source checkout does not require packaged signing.",
      },
    ],
  };
}

module.exports = {
  buildSigningPosture,
};
