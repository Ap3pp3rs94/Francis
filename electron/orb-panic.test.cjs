const test = require("node:test");
const assert = require("node:assert/strict");

const { buildPanicStopResult } = require("./orb-panic");

test("panic stop reports full success when local and remote paths clear", () => {
  const result = buildPanicStopResult({
    queueCleared: true,
    authorityReleased: true,
  });
  assert.equal(result.ok, true);
  assert.equal(result.status, "stopped");
  assert.equal(result.remoteSynced, true);
});

test("panic stop remains locally successful when only remote sync fails", () => {
  const result = buildPanicStopResult({
    queueCleared: false,
    authorityReleased: true,
    remoteError: "fetch failed",
  });
  assert.equal(result.ok, true);
  assert.equal(result.status, "local_only");
  assert.equal(result.remoteSynced, false);
  assert.match(result.summary, /locally/i);
  assert.equal(result.diagnostics.remoteError, "fetch failed");
});

test("panic stop reports degraded posture when local stop fails", () => {
  const result = buildPanicStopResult({
    queueCleared: true,
    authorityReleased: false,
    localError: "release failed",
  });
  assert.equal(result.ok, false);
  assert.equal(result.status, "degraded");
  assert.equal(result.diagnostics.localError, "release failed");
});
