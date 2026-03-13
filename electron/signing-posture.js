function readEnvValue(env, keys = []) {
  for (const key of keys) {
    const value = env && typeof env[key] === "string" ? env[key].trim() : "";
    if (value) {
      return value;
    }
  }
  return "";
}

function buildSigningPosture({
  env = process.env,
  distribution = "source",
  packaged = false,
} = {}) {
  const localCertificate = readEnvValue(env, ["WIN_CSC_LINK", "CSC_LINK"]);
  const localPassword = readEnvValue(env, ["WIN_CSC_KEY_PASSWORD", "CSC_KEY_PASSWORD"]);
  const azureVault = readEnvValue(env, ["AZURE_KEY_VAULT_URI"]);
  const azureClient = readEnvValue(env, ["AZURE_CLIENT_ID"]);
  const azureTenant = readEnvValue(env, ["AZURE_TENANT_ID"]);
  const azureSecret = readEnvValue(env, ["AZURE_CLIENT_SECRET"]);
  const signpathToken = readEnvValue(env, ["SIGNPATH_API_TOKEN"]);
  const signpathProject = readEnvValue(env, ["SIGNPATH_PROJECT_SLUG", "SIGNPATH_ORGANIZATION_ID"]);
  const requiresSigning = distribution === "installer" || distribution === "portable";

  const localReady = Boolean(localCertificate && localPassword);
  const azureReady = Boolean(azureVault && azureClient && azureTenant && azureSecret);
  const signpathReady = Boolean(signpathToken && signpathProject);
  const anySignals = Boolean(localCertificate || localPassword || azureVault || azureClient || azureTenant || azureSecret || signpathToken || signpathProject);

  let mode = "unsigned";
  let severity = "low";
  let summary = "Code signing is not active in this source checkout.";

  if (localReady) {
    mode = "local_certificate";
    summary = "Windows signing material is configured through a local certificate path.";
  } else if (azureReady) {
    mode = "cloud_signing";
    summary = "Windows signing material is configured through Azure Key Vault.";
  } else if (signpathReady) {
    mode = "cloud_signing";
    summary = "Windows signing material is configured through SignPath.";
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
  if (azureReady || azureVault) {
    configuredPaths.push("Azure Key Vault");
  }
  if (signpathReady || signpathToken) {
    configuredPaths.push("SignPath");
  }

  return {
    severity,
    mode,
    summary,
    requiresSigning,
    ready: localReady || azureReady || signpathReady,
    configuredPaths,
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
        value: localReady || azureReady || signpathReady ? "ready" : anySignals ? "partial" : "missing",
        tone: localReady || azureReady || signpathReady ? "low" : anySignals ? "high" : requiresSigning ? "medium" : "low",
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
    ],
    items: [
      {
        id: "certificate",
        label: "Local certificate",
        tone: localReady ? "low" : localCertificate || localPassword ? "high" : "low",
        summary: localReady
          ? "Certificate path and password are configured."
          : localCertificate || localPassword
            ? "Certificate path or password is present, but the local signer is incomplete."
            : "No local certificate path is configured.",
      },
      {
        id: "azure",
        label: "Azure Key Vault",
        tone: azureReady ? "low" : azureVault || azureClient || azureTenant || azureSecret ? "high" : "low",
        summary: azureReady
          ? "Azure signing inputs are complete."
          : azureVault || azureClient || azureTenant || azureSecret
            ? "Azure signing inputs are present, but the signer is incomplete."
            : "No Azure signing inputs are configured.",
      },
      {
        id: "signpath",
        label: "SignPath",
        tone: signpathReady ? "low" : signpathToken || signpathProject ? "high" : "low",
        summary: signpathReady
          ? "SignPath signing inputs are complete."
          : signpathToken || signpathProject
            ? "SignPath signing inputs are present, but the signer is incomplete."
            : "No SignPath signing inputs are configured.",
      },
    ],
  };
}

module.exports = {
  buildSigningPosture,
};
