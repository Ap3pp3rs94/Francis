const test = require("node:test");
const assert = require("node:assert/strict");

const { buildSigningPosture } = require("./signing-posture");

test("signing posture stays low for source checkouts without signer inputs", () => {
  const posture = buildSigningPosture({
    env: {},
    distribution: "source",
    packaged: false,
  });

  assert.equal(posture.mode, "unsigned");
  assert.equal(posture.severity, "low");
  assert.equal(posture.ready, false);
  assert.match(posture.summary, /source checkout/i);
});

test("signing posture becomes medium for packaged builds without signing material", () => {
  const posture = buildSigningPosture({
    env: {},
    distribution: "portable",
    packaged: true,
  });

  assert.equal(posture.mode, "unsigned");
  assert.equal(posture.severity, "medium");
  assert.equal(posture.ready, false);
  assert.equal(posture.requiresSigning, true);
  assert.match(posture.summary, /unsigned/i);
});

test("signing posture becomes high when signer inputs are partial", () => {
  const posture = buildSigningPosture({
    env: {
      WIN_CSC_LINK: "C:\\secure\\francis.pfx",
    },
    distribution: "installer",
    packaged: false,
  });

  assert.equal(posture.mode, "partial");
  assert.equal(posture.severity, "high");
  assert.equal(posture.ready, false);
  assert.match(posture.summary, /partial/i);
});

test("signing posture ignores placeholder signing template values", () => {
  const posture = buildSigningPosture({
    env: {
      FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME: "<legal publisher name>",
      FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT: "https://<region>.codesigning.azure.net/",
      FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME: "<trusted-signing-account>",
      FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME: "<certificate-profile>",
    },
    distribution: "installer",
    packaged: false,
  });

  assert.equal(posture.mode, "unsigned");
  assert.equal(posture.severity, "medium");
  assert.equal(posture.ready, false);
  assert.deepEqual(posture.configuredPaths, []);
});

test("signing posture is ready when Windows cert-store selectors are configured", () => {
  const posture = buildSigningPosture({
    env: {
      FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME: "Ap3pp3rs94",
    },
    distribution: "installer",
    packaged: false,
  });

  assert.equal(posture.mode, "local_certificate");
  assert.equal(posture.severity, "low");
  assert.equal(posture.ready, true);
  assert.ok(posture.configuredPaths.includes("Windows cert store"));
  assert.match(posture.summary, /certificate-store/i);
});

test("signing posture is ready when Azure Trusted Signing inputs are complete", () => {
  const posture = buildSigningPosture({
    env: {
      FRANCIS_WINDOWS_SIGNING_CHAIN_HINT: "Microsoft ID Verified CS EOC CA 01",
      FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT: "https://eus.codesigning.azure.net/",
      FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME: "francis-overlay",
      FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME: "francis-account",
      AZURE_CLIENT_ID: "client-id",
      AZURE_TENANT_ID: "tenant-id",
      AZURE_CLIENT_SECRET: "secret",
    },
    distribution: "installer",
    packaged: false,
  });

  assert.equal(posture.mode, "cloud_signing");
  assert.equal(posture.severity, "low");
  assert.equal(posture.ready, true);
  assert.ok(posture.configuredPaths.includes("Azure Trusted Signing"));
  assert.match(
    posture.items.find((entry) => entry.id === "chain_hint")?.summary || "",
    /Microsoft ID Verified CS EOC CA 01/,
  );
});

test("signing posture trusts a packaged executable with a verified signature", () => {
  const posture = buildSigningPosture({
    env: {},
    distribution: "installer",
    packaged: true,
    verifiedExecutable: {
      path: "C:\\Program Files\\Francis Overlay\\Francis Overlay.exe",
      state: "signed",
      status: "Valid",
      summary: "Valid Authenticode signature for CN=Francis Overlay.",
      subject: "CN=Francis Overlay",
    },
  });

  assert.equal(posture.mode, "signed");
  assert.equal(posture.severity, "low");
  assert.equal(posture.ready, true);
  assert.equal(posture.verification.state, "signed");
});

test("signing posture blocks a packaged executable with an invalid signature", () => {
  const posture = buildSigningPosture({
    env: {},
    distribution: "portable",
    packaged: true,
    verifiedExecutable: {
      path: "D:\\dist\\overlay\\Francis-Overlay.exe",
      state: "invalid",
      status: "HashMismatch",
      summary: "Authenticode signature is present but not valid: HashMismatch",
    },
  });

  assert.equal(posture.mode, "invalid");
  assert.equal(posture.severity, "high");
  assert.equal(posture.ready, false);
  assert.equal(posture.verification.state, "invalid");
});
