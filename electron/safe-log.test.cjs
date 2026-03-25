const test = require("node:test");
const assert = require("node:assert/strict");

const { guardStandardStreams, isDetachedConsoleError, patchConsoleForDetachedPipes, writeConsole } = require("./safe-log");

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

test("patchConsoleForDetachedPipes wraps console methods only once", () => {
  const calls = [];
  const fakeConsole = {
    log: (...args) => calls.push(["log", ...args]),
    warn: (...args) => calls.push(["warn", ...args]),
    error: (...args) => calls.push(["error", ...args]),
  };

  patchConsoleForDetachedPipes(fakeConsole);
  patchConsoleForDetachedPipes(fakeConsole);

  fakeConsole.log("hello");
  fakeConsole.warn("warn");
  fakeConsole.error("error");

  assert.deepEqual(calls, [
    ["log", "hello"],
    ["warn", "warn"],
    ["error", "error"],
  ]);
  assert.equal(fakeConsole.__francisDetachedPipeSafe, true);
});

test("guardStandardStreams adds detached-pipe guards only once", async () => {
  const listeners = [];
  const fakeStream = {
    on(eventName, handler) {
      listeners.push([eventName, handler]);
      return this;
    },
  };

  guardStandardStreams(fakeStream, fakeStream);
  guardStandardStreams(fakeStream, fakeStream);

  assert.equal(listeners.length, 1);
  assert.equal(listeners[0][0], "error");
  assert.equal(fakeStream.__francisDetachedPipeSafe, true);

  await assert.doesNotReject(async () => {
    listeners[0][1]({ code: "EPIPE", message: "broken pipe" });
  });

  assert.throws(() => {
    listeners[0][1](new Error("real stream failure"));
  }, /real stream failure/);
});
