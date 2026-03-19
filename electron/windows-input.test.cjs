const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildMouseClickCommand,
  buildMoveCursorCommand,
  buildShortcutCommand,
  buildTypeTextCommand,
  escapeSendKeysText,
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
