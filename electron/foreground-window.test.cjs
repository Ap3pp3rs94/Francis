const test = require("node:test");
const assert = require("node:assert/strict");

const {
  EMPTY_FOREGROUND_WINDOW,
  buildForegroundWindowCommand,
  getForegroundWindowInfo,
  normalizeForegroundWindowInfo,
} = require("./foreground-window");

test("normalizeForegroundWindowInfo trims values and validates pid", () => {
  const payload = normalizeForegroundWindowInfo({
    title: "  Francis Lens  ",
    process: "  electron.exe  ",
    pid: "4120",
  });

  assert.deepEqual(payload, {
    title: "Francis Lens",
    process: "electron.exe",
    pid: 4120,
    bounds: {
      x: null,
      y: null,
      width: 0,
      height: 0,
    },
  });
});

test("buildForegroundWindowCommand includes the Win32 foreground probes", () => {
  const command = buildForegroundWindowCommand();

  assert.match(command, /GetForegroundWindow/);
  assert.match(command, /GetWindowText/);
  assert.match(command, /GetWindowRect/);
  assert.match(command, /GetWindowThreadProcessId/);
  assert.match(command, /ConvertTo-Json/);
});

test("getForegroundWindowInfo returns empty payload outside Windows", async () => {
  const payload = await getForegroundWindowInfo({ platform: "linux" });

  assert.deepEqual(payload, { ...EMPTY_FOREGROUND_WINDOW });
});

test("getForegroundWindowInfo uses the provided execFile implementation", async () => {
  const calls = [];
  const payload = await getForegroundWindowInfo({
    platform: "win32",
    execFileImpl: async (command, args, options) => {
      calls.push({ command, args, options });
      return {
        stdout: JSON.stringify({
          title: "Orb Window",
          process: "electron",
          pid: 5120,
          bounds: { x: 240, y: 120, width: 1280, height: 820 },
        }),
      };
    },
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].command, "powershell");
  assert.deepEqual(payload, {
    title: "Orb Window",
    process: "electron",
    pid: 5120,
    bounds: {
      x: 240,
      y: 120,
      width: 1280,
      height: 820,
    },
  });
});
