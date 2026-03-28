const fs = require("node:fs");
const path = require("node:path");

const { readConfiguredEnvValue } = require("../../electron/signing-env");

const DEFAULT_TIMESTAMP_URL = "http://timestamp.acs.microsoft.com";
const GENERATED_SIGNING_SUMMARY_PATH = path.resolve(__dirname, "..", "..", "electron", "generated", "windows-sign-summary.json");

function resolveWindowsSigningConfig(env = process.env) {
  return {
    signToolPath: readConfiguredEnvValue(env, ["AZURE_SIGN_SIGNSDK_SIGNSTOOL"]),
    dlibPath: readConfiguredEnvValue(env, ["AZURE_SIGN_DLIB_PATH"]),
    metadataPath: readConfiguredEnvValue(env, ["AZURE_SIGN_METADATA_PATH"]),
    timestampUrl: readConfiguredEnvValue(env, ["AZURE_SIGN_TIMESTAMP_URL"]) || DEFAULT_TIMESTAMP_URL,
    summaryPath: GENERATED_SIGNING_SUMMARY_PATH,
  };
}

function loadWindowsSigningMetadata(metadataPath, fsImpl = fs) {
  const raw = fsImpl.readFileSync(metadataPath, "utf8");
  return JSON.parse(raw);
}

function validateWindowsSigningConfig(config, fsImpl = fs) {
  const failures = [];

  if (!config.signToolPath) {
    failures.push({
      key: "AZURE_SIGN_SIGNSDK_SIGNSTOOL",
      reason: "missing",
      message: "Set AZURE_SIGN_SIGNSDK_SIGNSTOOL to the exact signtool.exe path from the Azure signing toolchain.",
    });
  } else if (!fsImpl.existsSync(config.signToolPath)) {
    failures.push({
      key: "AZURE_SIGN_SIGNSDK_SIGNSTOOL",
      reason: "missing_file",
      message: `signtool.exe was not found at ${config.signToolPath}.`,
    });
  }

  if (!config.dlibPath) {
    failures.push({
      key: "AZURE_SIGN_DLIB_PATH",
      reason: "missing",
      message: "Set AZURE_SIGN_DLIB_PATH to Azure.CodeSigning.Dlib.dll from the Artifact Signing client tools.",
    });
  } else if (!fsImpl.existsSync(config.dlibPath)) {
    failures.push({
      key: "AZURE_SIGN_DLIB_PATH",
      reason: "missing_file",
      message: `Azure.CodeSigning.Dlib.dll was not found at ${config.dlibPath}.`,
    });
  }

  if (!config.metadataPath) {
    failures.push({
      key: "AZURE_SIGN_METADATA_PATH",
      reason: "missing",
      message: "Set AZURE_SIGN_METADATA_PATH to a metadata.json file for Azure Artifact Signing.",
    });
  } else if (!fsImpl.existsSync(config.metadataPath)) {
    failures.push({
      key: "AZURE_SIGN_METADATA_PATH",
      reason: "missing_file",
      message: `metadata.json was not found at ${config.metadataPath}.`,
    });
  }

  let metadata = null;
  if (config.metadataPath && fsImpl.existsSync(config.metadataPath)) {
    try {
      metadata = loadWindowsSigningMetadata(config.metadataPath, fsImpl);
    } catch (error) {
      failures.push({
        key: "AZURE_SIGN_METADATA_PATH",
        reason: "invalid_json",
        message: `metadata.json could not be parsed: ${error instanceof Error ? error.message : String(error)}`,
      });
    }
  }

  if (metadata) {
    for (const field of ["Endpoint", "CodeSigningAccountName", "CertificateProfileName"]) {
      if (!String(metadata[field] || "").trim()) {
        failures.push({
          key: "AZURE_SIGN_METADATA_PATH",
          reason: "missing_metadata_field",
          message: `metadata.json is missing ${field}.`,
        });
      }
    }
  }

  return {
    ok: failures.length === 0,
    failures,
    metadata,
  };
}

module.exports = {
  DEFAULT_TIMESTAMP_URL,
  GENERATED_SIGNING_SUMMARY_PATH,
  loadWindowsSigningMetadata,
  resolveWindowsSigningConfig,
  validateWindowsSigningConfig,
};
