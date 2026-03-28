const test = require("node:test");
const assert = require("node:assert/strict");

const {
  WINDOWS_SIGN_HOOK_PATH,
  buildAzureTrustedSigningSigntoolOptions,
  buildElectronBuilderConfig,
  buildWindowsSigntoolOptions,
} = require("./builder-config.shared.cjs");

test("builder config enables the repo-owned Azure Trusted Signing hook only when the config is complete", () => {
  const signtoolOptions = buildAzureTrustedSigningSigntoolOptions({
    FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT: "https://eus.codesigning.azure.net/",
    FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME: "francis-overlay",
    FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME: "francis-account",
    FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME: "Ap3pp3rs94",
  });

  assert.deepEqual(signtoolOptions, {
    sign: WINDOWS_SIGN_HOOK_PATH,
    signingHashAlgorithms: ["sha256"],
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

  assert.equal(config.win.signtoolOptions, undefined);
});

test("builder config ignores placeholder signing template values", () => {
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
      FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME: "<legal publisher name>",
      FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT: "https://<region>.codesigning.azure.net/",
      FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME: "<certificate-profile>",
      FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME: "<trusted-signing-account>",
    },
  });

  assert.equal(config.win.azureSignOptions, undefined);
  assert.equal(config.win.signtoolOptions, undefined);
});

test("builder config supports Windows cert-store selectors when Azure signing is absent", () => {
  const signtoolOptions = buildWindowsSigntoolOptions({
    FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME: "Ap3pp3rs94",
    FRANCIS_WINDOWS_SIGNING_SHA1: "ABCDEF1234567890",
  });

  assert.deepEqual(signtoolOptions, {
    certificateSubjectName: "Ap3pp3rs94",
    certificateSha1: "ABCDEF1234567890",
  });

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
      FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME: "Ap3pp3rs94",
      FRANCIS_WINDOWS_SIGNING_SHA1: "ABCDEF1234567890",
    },
  });

  assert.deepEqual(config.win.signtoolOptions, {
    certificateSubjectName: "Ap3pp3rs94",
    certificateSha1: "ABCDEF1234567890",
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

test("builder config prefers Azure signing when both Azure and cert-store selectors are configured", () => {
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
      FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME: "francis-overlay",
      FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME: "francis-account",
      FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME: "Ap3pp3rs94",
    },
  });

  assert.deepEqual(config.win.signtoolOptions, {
    sign: WINDOWS_SIGN_HOOK_PATH,
    signingHashAlgorithms: ["sha256"],
  });
  assert.equal(config.win.azureSignOptions, undefined);
});
