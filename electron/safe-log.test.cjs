const test = require("node:test");
const assert = require("node:assert/strict");

const { isDetachedConsoleError, writeConsole } = require("./safe-log");

test("detects detached console errors", () => {
  assert.equal(isDetachedConsoleError({ code: "EPIPE" }), true);
  assert.equal(isDetachedConsoleError({ code: "ERR_STREAM_DESTROYED" }), true);
  assert.equal(isDetachedConsoleError({ message: "broken pipe, write" }), true);
  assert.equal(isDetachedConsoleError({ code: "EINVAL", message: "different failure" }), false);
});

test("writeConsole suppresses broken pipe errors and preserves other failures", () => {
  let called = 0;
  const ok = writeConsole(() => {
    called += 1;
  }, "hello");
  assert.equal(ok, true);
  assert.equal(called, 1);

  const detached = writeConsole(() => {
    const error = new Error("broken pipe");
    error.code = "EPIPE";
    throw error;
  }, "hello");
  assert.equal(detached, false);

  assert.throws(
    () =>
      writeConsole(() => {
        throw new Error("other failure");
      }, "hello"),
    /other failure/,
  );
});
