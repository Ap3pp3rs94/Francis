const packageJson = require("../package.json");

function readEnvValue(env, keys = []) {
  for (const key of keys) {
    const value = env && typeof env[key] === "string" ? env[key].trim() : "";
    if (value) {
      return value;
    }
  }
  return "";
}

function readEnvBoolean(env, keys = []) {
  const value = readEnvValue(env, keys).toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

function cloneBuildConfig(buildConfig = {}) {
  return JSON.parse(JSON.stringify(buildConfig));
}

function buildAzureTrustedSigningOptions(env = process.env) {
  const endpoint = readEnvValue(env, ["FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT"]);
  const certificateProfileName = readEnvValue(env, ["FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME"]);
  const codeSigningAccountName = readEnvValue(env, ["FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME"]);
  const publisherName = readEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME"]);

  if (!(endpoint && certificateProfileName && codeSigningAccountName)) {
    return null;
  }

  return {
    endpoint,
    certificateProfileName,
    codeSigningAccountName,
    ...(publisherName ? { publisherName } : {}),
  };
}

function buildWindowsSigntoolOptions(env = process.env) {
  const certificateSubjectName = readEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME"]);
  const certificateSha1 = readEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_SHA1"]);

  if (!(certificateSubjectName || certificateSha1)) {
    return null;
  }

  return {
    ...(certificateSubjectName ? { certificateSubjectName } : {}),
    ...(certificateSha1 ? { certificateSha1 } : {}),
  };
}

function buildElectronBuilderConfig({
  packageJson: packageJsonInput = packageJson,
  env = process.env,
} = {}) {
  const build = cloneBuildConfig(packageJsonInput.build || {});
  const win = { ...(build.win || {}) };
  const azureSignOptions = buildAzureTrustedSigningOptions(env);
  const signtoolOptions = buildWindowsSigntoolOptions(env);

  if (azureSignOptions) {
    win.azureSignOptions = azureSignOptions;
    delete win.signtoolOptions;
  } else if (signtoolOptions) {
    win.signtoolOptions = signtoolOptions;
  } else {
    delete win.azureSignOptions;
    delete win.signtoolOptions;
  }

  return {
    ...build,
    win,
    forceCodeSigning:
      build.forceCodeSigning ||
      readEnvBoolean(env, ["FRANCIS_REQUIRE_SIGNED_OVERLAY", "FRANCIS_FORCE_CODE_SIGNING"]),
  };
}

module.exports = {
  buildAzureTrustedSigningOptions,
  buildElectronBuilderConfig,
  buildWindowsSigntoolOptions,
};
