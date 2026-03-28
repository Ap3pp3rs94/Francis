const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_TIMESTAMP_URL,
  resolveWindowsSigningConfig,
  validateWindowsSigningConfig,
} = require("./windows-sign.config.cjs");

test("resolveWindowsSigningConfig reads the deterministic Azure signtool env", () => {
  const config = resolveWindowsSigningConfig({
    AZURE_SIGN_SIGNSDK_SIGNSTOOL: "C:\\tools\\signtool.exe",
    AZURE_SIGN_DLIB_PATH: "C:\\tools\\Azure.CodeSigning.Dlib.dll",
    AZURE_SIGN_METADATA_PATH: "C:\\tools\\metadata.json",
  });

  assert.equal(config.signToolPath, "C:\\tools\\signtool.exe");
  assert.equal(config.dlibPath, "C:\\tools\\Azure.CodeSigning.Dlib.dll");
  assert.equal(config.metadataPath, "C:\\tools\\metadata.json");
  assert.equal(config.timestampUrl, DEFAULT_TIMESTAMP_URL);
});

test("validateWindowsSigningConfig rejects missing files and metadata", () => {
  const validation = validateWindowsSigningConfig(
    {
      signToolPath: "C:\\missing\\signtool.exe",
      dlibPath: "C:\\missing\\Azure.CodeSigning.Dlib.dll",
      metadataPath: "C:\\missing\\metadata.json",
      timestampUrl: DEFAULT_TIMESTAMP_URL,
      summaryPath: "D:\\tmp\\windows-sign-summary.json",
    },
    {
      existsSync: () => false,
    },
  );

  assert.equal(validation.ok, false);
  assert.deepEqual(
    validation.failures.map((entry) => entry.key),
    [
      "AZURE_SIGN_SIGNSDK_SIGNSTOOL",
      "AZURE_SIGN_DLIB_PATH",
      "AZURE_SIGN_METADATA_PATH",
    ],
  );
});

test("validateWindowsSigningConfig accepts present files and parses metadata", () => {
  const validation = validateWindowsSigningConfig(
    {
      signToolPath: "C:\\tools\\signtool.exe",
      dlibPath: "C:\\tools\\Azure.CodeSigning.Dlib.dll",
      metadataPath: "C:\\tools\\metadata.json",
      timestampUrl: DEFAULT_TIMESTAMP_URL,
      summaryPath: "D:\\tmp\\windows-sign-summary.json",
    },
    {
      existsSync: () => true,
      readFileSync: () =>
        JSON.stringify({
          Endpoint: "https://cus.codesigning.azure.net/",
          CodeSigningAccountName: "francis-signing-rg",
          CertificateProfileName: "francis-public-trust",
        }),
    },
  );

  assert.equal(validation.ok, true);
  assert.equal(validation.metadata.Endpoint, "https://cus.codesigning.azure.net/");
});
