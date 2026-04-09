const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildWindowsDesktopCapabilityProfile,
  buildMouseClickCommand,
  buildMouseDragCommand,
  buildMoveCursorCommand,
  buildShortcutCommand,
  buildTypeTextCommand,
  escapeSendKeysText,
  executeWindowsInputCommand,
  toSendKeysShortcut,
} = require("./windows-input");

test("buildMoveCursorCommand uses SetCursorPos", () => {
  const script = buildMoveCursorCommand({ x: 240.2, y: 128.7 });
  assert.match(script, /SetCursorPos\(240, 129\)/);
});

test("buildMouseClickCommand uses left button events", () => {
  const script = buildMouseClickCommand({ button: "left", double: true });
  assert.match(script, /0x0002/);
  assert.match(script, /0x0004/);
  assert.match(script, /Start-Sleep -Milliseconds 48/);
});

test("buildMouseClickCommand can preserve cursor position around a targeted click", () => {
  const script = buildMouseClickCommand({
    button: "left",
    x: 500,
    y: 320,
    preserve_human_cursor: true,
  });
  assert.match(script, /GetCursorPos/);
  assert.match(script, /SetCursorPos\(500, 320\)/);
  assert.match(script, /SetCursorPos\(\$priorCursor\.X, \$priorCursor\.Y\)/);
});

test("buildMouseDragCommand anchors contact and interpolates the drag path", () => {
  const script = buildMouseDragCommand({ start_x: 100, start_y: 120, x: 320, y: 260, steps: 8, duration_ms: 240 });
  assert.match(script, /SetCursorPos\(100, 120\)/);
  assert.match(script, /\$progress = \[double\]\$i \/ 8/);
  assert.match(script, /SetCursorPos\(\$nextX, \$nextY\)/);
  assert.match(script, /0x0002/);
  assert.match(script, /0x0004/);
});

test("escapeSendKeysText escapes reserved sendkeys tokens", () => {
  assert.equal(escapeSendKeysText("a+b^{x}"), "a{+}b{^}{{}x{}}");
});

test("toSendKeysShortcut maps modifier arrays", () => {
  assert.equal(toSendKeysShortcut(["ctrl", "shift", "s"]), "^+s");
  assert.equal(toSendKeysShortcut(["alt", "enter"]), "%{ENTER}");
});

test("buildTypeTextCommand and buildShortcutCommand use SendWait", () => {
  assert.match(buildTypeTextCommand({ text: "hello+world" }), /SendWait\('hello\{\+\}world'\)/);
  assert.match(buildShortcutCommand({ keys: ["ctrl", "shift", "s"] }), /SendWait\('\^\+s'\)/);
});

test("buildWindowsDesktopCapabilityProfile exposes honest active desktop limits", () => {
  const profile = buildWindowsDesktopCapabilityProfile({
    platform: "win32",
    foregroundWindow: {
      process: "VALORANT-Win64-Shipping",
      title: "VALORANT",
      elevated: true,
      fullscreenLike: true,
    },
  });

  assert.equal(profile.matrix[0].key, "taskbar");
  assert.deepEqual(
    profile.activeLimitations.map((entry) => entry.key),
    ["protected_surface", "elevated_foreground", "borderless_fullscreen"],
  );
});

test("executeWindowsInputCommand returns canonical execution semantics for drag", async () => {
  const calls = [];
  const result = await executeWindowsInputCommand(
    {
      kind: "mouse.drag",
      args: { start_x: 120, start_y: 160, x: 420, y: 280, steps: 6, duration_ms: 180 },
    },
    {
      platform: "win32",
      execFileImpl: async (...args) => {
        calls.push(args);
        return { stdout: "", stderr: "" };
      },
    },
  );

  assert.equal(calls.length, 1);
  assert.match(String(calls[0][1][2] || ""), /SetCursorPos\(120, 160\)/);
  assert.equal(result.status, "ok");
  assert.equal(result.execution.phase, "drag_act");
  assert.equal(result.execution.sustained_contact, true);
});

test("executeWindowsInputCommand preserves cursor position when requested for mouse click", async () => {
  const calls = [];
  const result = await executeWindowsInputCommand(
    {
      kind: "mouse.click",
      args: { x: 320, y: 280, preserve_human_cursor: true },
    },
    {
      platform: "win32",
      execFileImpl: async (...args) => {
        calls.push(args);
        return { stdout: "", stderr: "" };
      },
    },
  );

  assert.equal(calls.length, 1);
  const script = String(calls[0][1][2] || "");
  assert.match(script, /GetCursorPos/);
  assert.match(script, /SetCursorPos\(320, 280\)/);
  assert.match(script, /SetCursorPos\(\$priorCursor\.X, \$priorCursor\.Y\)/);
  assert.equal(result.status, "ok");
  assert.equal(result.execution.phase, "click_act");
});
