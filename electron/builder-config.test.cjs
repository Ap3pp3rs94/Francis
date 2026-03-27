const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildAzureTrustedSigningOptions,
  buildElectronBuilderConfig,
} = require("./builder-config.shared.cjs");

test("builder config enables Azure Trusted Signing only when the config is complete", () => {
  const azureSignOptions = buildAzureTrustedSigningOptions({
    FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT: "https://eus.codesigning.azure.net/",
    FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME: "francis-overlay",
    FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME: "francis-account",
    FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME: "Ap3pp3rs94",
  });

  assert.deepEqual(azureSignOptions, {
    endpoint: "https://eus.codesigning.azure.net/",
    certificateProfileName: "francis-overlay",
    codeSigningAccountName: "francis-account",
    publisherName: "Ap3pp3rs94",
  });
});

test("builder config omits incomplete Azure Trusted Signing settings", () => {
  const config = buildElectronBuilderConfig({
    packageJson: {
      build: {
        appId: "com.francis.overlay",
        win: {
          target: ["portable", "nsis"],
        },
      },
    },
    env: {
      FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT: "https://eus.codesigning.azure.net/",
    },
  });

  assert.equal(config.win.azureSignOptions, undefined);
});

test("builder config can force code signing for release packaging", () => {
  const config = buildElectronBuilderConfig({
    packageJson: {
      build: {
        appId: "com.francis.overlay",
        win: {
          target: ["portable", "nsis"],
        },
      },
    },
    env: {
      FRANCIS_REQUIRE_SIGNED_OVERLAY: "1",
    },
  });

  assert.equal(config.forceCodeSigning, true);
});
