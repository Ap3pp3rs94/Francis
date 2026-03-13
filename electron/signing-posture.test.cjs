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

test("signing posture is ready when Azure signing inputs are complete", () => {
  const posture = buildSigningPosture({
    env: {
      AZURE_KEY_VAULT_URI: "https://vault.example.vault.azure.net/",
      AZURE_CLIENT_ID: "client-id",
      AZURE_TENANT_ID: "tenant-id",
      AZURE_CLIENT_SECRET: "secret",
    },
    distribution: "installer",
    packaged: true,
  });

  assert.equal(posture.mode, "cloud_signing");
  assert.equal(posture.severity, "low");
  assert.equal(posture.ready, true);
  assert.ok(posture.configuredPaths.includes("Azure Key Vault"));
});
