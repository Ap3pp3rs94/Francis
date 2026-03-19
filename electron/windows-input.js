const { execFile } = require("node:child_process");
const { promisify } = require("node:util");

const execFileAsync = promisify(execFile);
const INPUT_TIMEOUT_MS = 5000;

function escapeSingleQuotedPowerShell(value) {
  return String(value || "").replace(/'/g, "''");
}

function escapeSendKeysText(value) {
  return String(value || "").replace(/[+^%~(){}\[\]]/g, (match) => `{${match}}`);
}

function toSendKeysShortcut(keys) {
  if (typeof keys === "string" && keys.trim()) {
    return keys.trim();
  }
  const parts = Array.isArray(keys) ? keys : [];
  const modifiers = [];
  let primary = "";
  for (const part of parts) {
    const normalized = String(part || "").trim().toLowerCase();
    if (!normalized) {
      continue;
    }
    if (normalized === "ctrl" || normalized === "control") {
      modifiers.push("^");
      continue;
    }
    if (normalized === "shift") {
      modifiers.push("+");
      continue;
    }
    if (normalized === "alt") {
      modifiers.push("%");
      continue;
    }
    if (normalized === "enter" || normalized === "return") {
      primary = "{ENTER}";
    } else if (normalized === "tab") {
      primary = "{TAB}";
    } else if (normalized === "esc" || normalized === "escape") {
      primary = "{ESC}";
    } else if (normalized === "backspace") {
      primary = "{BACKSPACE}";
    } else if (normalized === "delete") {
      primary = "{DELETE}";
    } else if (normalized === "space") {
      primary = " ";
    } else if (/^f\d{1,2}$/.test(normalized)) {
      primary = `{${normalized.toUpperCase()}}`;
    } else if (["up", "down", "left", "right", "home", "end", "pgup", "pgdn"].includes(normalized)) {
      primary = `{${normalized.toUpperCase()}}`;
    } else if (normalized.length === 1) {
      primary = normalized;
    }
  }
  return `${modifiers.join("")}${primary}`;
}

function buildWin32Prelude() {
  return `
$ErrorActionPreference = "Stop"
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class FrancisInput {
  [DllImport("user32.dll")]
  public static extern bool SetCursorPos(int x, int y);

  [DllImport("user32.dll")]
  public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
}
"@
Add-Type -AssemblyName System.Windows.Forms
`;
}

function buildMoveCursorCommand({ x, y }) {
  const nextX = Math.round(Number(x || 0));
  const nextY = Math.round(Number(y || 0));
  return `${buildWin32Prelude()}\n[void][FrancisInput]::SetCursorPos(${nextX}, ${nextY})`;
}

function buildMouseClickCommand({ button = "left", double = false }) {
  const normalizedButton = String(button || "left").trim().toLowerCase();
  const downFlag = normalizedButton === "right" ? "0x0008" : "0x0002";
  const upFlag = normalizedButton === "right" ? "0x0010" : "0x0004";
  const clickBody = `
[FrancisInput]::mouse_event(${downFlag}, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 24
[FrancisInput]::mouse_event(${upFlag}, 0, 0, 0, [UIntPtr]::Zero)
`.trim();
  const repetitions = double ? `${clickBody}\nStart-Sleep -Milliseconds 48\n${clickBody}` : clickBody;
  return `${buildWin32Prelude()}\n${repetitions}`;
}

function buildTypeTextCommand({ text }) {
  const escaped = escapeSendKeysText(text);
  return `${buildWin32Prelude()}\n[System.Windows.Forms.SendKeys]::SendWait('${escapeSingleQuotedPowerShell(escaped)}')`;
}

function buildShortcutCommand({ keys }) {
  const sendKeys = toSendKeysShortcut(keys);
  return `${buildWin32Prelude()}\n[System.Windows.Forms.SendKeys]::SendWait('${escapeSingleQuotedPowerShell(sendKeys)}')`;
}

function buildKeyCommand({ key }) {
  return buildShortcutCommand({ keys: [String(key || "")] });
}

async function executePowerShell(script, { timeoutMs = INPUT_TIMEOUT_MS, platform = process.platform, execFileImpl = execFileAsync } = {}) {
  if (platform !== "win32") {
    throw new Error("Windows input authority is only available on win32.");
  }
  await execFileImpl(
    "powershell",
    ["-NoProfile", "-Command", script],
    {
      timeout: timeoutMs,
      windowsHide: true,
      maxBuffer: 1024 * 64,
    },
  );
  return { status: "ok" };
}

async function executeWindowsInputCommand(command, options = {}) {
  const payload = command && typeof command === "object" ? command : {};
  const kind = String(payload.kind || "").trim().toLowerCase();
  const args = payload.args && typeof payload.args === "object" ? payload.args : {};
  if (kind === "mouse.move") {
    return executePowerShell(buildMoveCursorCommand(args), options);
  }
  if (kind === "mouse.click") {
    return executePowerShell(buildMouseClickCommand(args), options);
  }
  if (kind === "keyboard.type") {
    return executePowerShell(buildTypeTextCommand(args), options);
  }
  if (kind === "keyboard.key") {
    return executePowerShell(buildKeyCommand(args), options);
  }
  if (kind === "keyboard.shortcut") {
    return executePowerShell(buildShortcutCommand(args), options);
  }
  throw new Error(`Unsupported Windows input command: ${kind}`);
}

module.exports = {
  INPUT_TIMEOUT_MS,
  buildKeyCommand,
  buildMouseClickCommand,
  buildMoveCursorCommand,
  buildShortcutCommand,
  buildTypeTextCommand,
  buildWin32Prelude,
  escapeSendKeysText,
  executePowerShell,
  executeWindowsInputCommand,
  toSendKeysShortcut,
};
