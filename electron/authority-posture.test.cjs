const test = require("node:test");
const assert = require("node:assert/strict");

const { buildAuthorityPosture } = require("./authority-posture");

test("authority posture stays local-first without connector or support credentials", () => {
  const posture = buildAuthorityPosture({
    env: {
      COMPUTERNAME: "WORKSTATION-1",
    },
    portability: {
      lastImportStatus: "idle",
    },
    provider: {
      severity: "low",
    },
  });

  assert.equal(posture.severity, "low");
  assert.equal(posture.supportConfigured, false);
  assert.equal(posture.connectorCredentialClasses.length, 0);
  assert.match(posture.summary, /local-first/i);
});

test("authority posture warns when connector credentials exist under implicit identities", () => {
  const posture = buildAuthorityPosture({
    env: {
      COMPUTERNAME: "WORKSTATION-1",
      OPENAI_API_KEY: "redacted",
      GITHUB_TOKEN: "redacted",
    },
    portability: {
      lastImportStatus: "idle",
    },
    provider: {
      severity: "low",
    },
  });

  assert.equal(posture.severity, "medium");
  assert.ok(posture.connectorCredentialClasses.includes("Remote model providers"));
  assert.ok(posture.connectorCredentialClasses.includes("GitHub"));
  assert.match(posture.summary, /implicit/i);
});

test("authority posture blocks ambiguous support authority", () => {
  const posture = buildAuthorityPosture({
    env: {
      FRANCIS_NODE_ID: "node-1",
      FRANCIS_SERVICE_ID: "overlay-shell",
      FRANCIS_SUPPORT_OPERATOR: "tier3",
    },
    portability: {
      lastImportStatus: "idle",
    },
    provider: {
      severity: "low",
    },
  });

  assert.equal(posture.severity, "high");
  assert.equal(posture.supportConfigured, true);
  assert.equal(posture.supportBound, false);
  assert.match(posture.summary, /tenant|managed-copy/i);
});

test("authority posture accepts explicitly bound support authority", () => {
  const posture = buildAuthorityPosture({
    env: {
      FRANCIS_NODE_ID: "node-1",
      FRANCIS_SERVICE_ID: "overlay-shell",
      FRANCIS_SUPPORT_OPERATOR: "tier3",
      FRANCIS_TENANT_ID: "tenant-7",
    },
    portability: {
      lastImportStatus: "idle",
    },
    provider: {
      severity: "low",
    },
  });

  assert.equal(posture.severity, "low");
  assert.equal(posture.supportBound, true);
  assert.equal(posture.cards.find((entry) => entry.label === "Support").value, "bound");
});
