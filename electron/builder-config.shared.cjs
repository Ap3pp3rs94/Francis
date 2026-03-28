const packageJson = require("../package.json");
const {
  readConfiguredEnvBoolean,
  readConfiguredEnvValue,
} = require("./signing-env");

const WINDOWS_SIGN_HOOK_PATH = "./build/sign/windows-sign.cjs";

function cloneBuildConfig(buildConfig = {}) {
  return JSON.parse(JSON.stringify(buildConfig));
}

function buildAzureTrustedSigningSigntoolOptions(env = process.env) {
  const endpoint = readConfiguredEnvValue(env, ["FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT"]);
  const certificateProfileName = readConfiguredEnvValue(env, ["FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME"]);
  const codeSigningAccountName = readConfiguredEnvValue(env, ["FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME"]);
  const publisherName = readConfiguredEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME"]);

  if (!(endpoint && certificateProfileName && codeSigningAccountName)) {
    return null;
  }

  return {
    sign: WINDOWS_SIGN_HOOK_PATH,
    signingHashAlgorithms: ["sha256"],
    ...(publisherName ? { publisherName } : {}),
  };
}

function buildWindowsSigntoolOptions(env = process.env) {
  const certificateSubjectName = readConfiguredEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME"]);
  const certificateSha1 = readConfiguredEnvValue(env, ["FRANCIS_WINDOWS_SIGNING_SHA1"]);

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
  const azureSigntoolOptions = buildAzureTrustedSigningSigntoolOptions(env);
  const signtoolOptions = buildWindowsSigntoolOptions(env);

  if (azureSigntoolOptions) {
    win.signtoolOptions = azureSigntoolOptions;
    delete win.azureSignOptions;
  } else if (signtoolOptions) {
    win.signtoolOptions = signtoolOptions;
    delete win.azureSignOptions;
  } else {
    delete win.azureSignOptions;
    delete win.signtoolOptions;
  }

  return {
    ...build,
    win,
    forceCodeSigning:
      build.forceCodeSigning ||
      readConfiguredEnvBoolean(env, ["FRANCIS_REQUIRE_SIGNED_OVERLAY", "FRANCIS_FORCE_CODE_SIGNING"]),
  };
}

module.exports = {
  WINDOWS_SIGN_HOOK_PATH,
  buildAzureTrustedSigningSigntoolOptions,
  buildElectronBuilderConfig,
  buildWindowsSigntoolOptions,
};
