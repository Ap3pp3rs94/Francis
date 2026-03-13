const test = require("node:test");
const assert = require("node:assert/strict");

const { buildUpdateDeliveryPosture } = require("./update-delivery");

test("source delivery posture stays manual and low severity when current", () => {
  const posture = buildUpdateDeliveryPosture({
    distribution: "source",
    buildIdentity: "0.1.0+abc1234",
    update: { currentBuild: "0.1.0+abc1234", pendingNotice: false },
    rollback: { count: 1 },
    signing: { severity: "low" },
  });

  assert.equal(posture.channel, "source");
  assert.equal(posture.severity, "low");
  assert.match(posture.summary, /manual|builder-driven/i);
});

test("portable delivery posture stays review-first when packaged trust is unsigned", () => {
  const posture = buildUpdateDeliveryPosture({
    distribution: "portable",
    buildIdentity: "0.1.0",
    update: { currentBuild: "0.1.0", pendingNotice: false },
    rollback: { count: 2 },
    signing: {
      severity: "medium",
      summary: "Packaged Windows builds are currently unsigned. Installer trust remains blocked on certificate material.",
    },
  });

  assert.equal(posture.channel, "portable");
  assert.equal(posture.severity, "medium");
  assert.ok(posture.items.some((item) => /Trust Path/i.test(item.label)));
});

test("installer delivery posture prefers guided reinstall steps", () => {
  const posture = buildUpdateDeliveryPosture({
    distribution: "installer",
    buildIdentity: "0.1.0",
    update: { currentBuild: "0.1.0", pendingNotice: false },
    rollback: { count: 3 },
    signing: { severity: "low" },
    installRoot: "C:\\Users\\Alice\\AppData\\Local\\Programs\\Francis Overlay",
  });

  assert.equal(posture.channel, "installer");
  assert.equal(posture.severity, "low");
  assert.ok(posture.steps.some((step) => /installer/i.test(step)));
});

test("pending update notice escalates delivery posture", () => {
  const posture = buildUpdateDeliveryPosture({
    distribution: "portable",
    buildIdentity: "0.1.1",
    update: { currentBuild: "0.1.1", pendingNotice: true },
    rollback: { count: 1 },
    signing: { severity: "low" },
  });

  assert.equal(posture.severity, "medium");
  assert.match(posture.summary, /pending/i);
});
