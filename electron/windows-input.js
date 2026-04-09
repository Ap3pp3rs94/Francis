const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const { buildOrbExecutionSemantics } = require("./orb-execution");

const execFileAsync = promisify(execFile);
const INPUT_TIMEOUT_MS = 5000;
const WINDOWS_DESKTOP_SURFACE_MATRIX = Object.freeze([
  {
    key: "taskbar",
    label: "Taskbar",
    state: "strong",
    summary: "Explorer-managed taskbar surfaces can be targeted directly on ordinary desktop sessions.",
    fallback: "Keep the orb resident on the active taskbar edge and route precise screen coordinates through the shell bridge.",
  },
  {
    key: "ordinary_windows",
    label: "Ordinary Windows",
    state: "strong",
    summary: "Topmost orb authority can stay above ordinary desktop windows when Windows is running in the standard compositor path.",
    fallback: "Reassert topmost and workspace presence while keeping local controls available.",
  },
  {
    key: "multi_monitor",
    label: "Multi-monitor",
    state: "strong",
    summary: "Display-aware coordinates and virtual desktop bounds can be governed coherently across monitors.",
    fallback: "Anchor the orb to the active display while preserving a virtual desktop surface for cross-screen travel.",
  },
  {
    key: "borderless_fullscreen",
    label: "Borderless Fullscreen",
    state: "bounded",
    summary: "Borderless fullscreen often preserves overlay reach, but compositor policy can still reduce stability.",
    fallback: "Keep the orb resident and reassert presence instead of pretending stable top-layer control is guaranteed.",
  },
  {
    key: "elevated_apps",
    label: "Elevated Apps",
    state: "limited",
    summary: "Non-elevated overlays and input bridges can lose authority against elevated Windows surfaces.",
    fallback: "Hold resident posture, keep local controls live, and wait for the surface to return to standard privileges.",
  },
  {
    key: "exclusive_fullscreen",
    label: "Exclusive Fullscreen",
    state: "blocked",
    summary: "Exclusive fullscreen can bypass normal desktop composition and block overlays outright.",
    fallback: "Hold a truthful resident fallback and document the limit instead of claiming direct authority.",
  },
  {
    key: "protected_surfaces",
    label: "Protected Surfaces",
    state: "blocked",
    summary: "Anti-cheat or protected surfaces can block overlay, accessibility, and input authority.",
    fallback: "Stay resident, preserve local stop and pause, and do not claim direct interaction authority.",
  },
]);

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
  [StructLayout(LayoutKind.Sequential)]
  public struct POINT {
    public int X;
    public int Y;
  }

  [DllImport("user32.dll")]
  public static extern bool SetCursorPos(int x, int y);

  [DllImport("user32.dll")]
  public static extern bool GetCursorPos(out POINT lpPoint);

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

function buildMouseClickCommand({ button = "left", double = false, x, y, preserve_human_cursor = false, preserveHumanCursor = false }) {
  const normalizedButton = String(button || "left").trim().toLowerCase();
  const downFlag = normalizedButton === "right" ? "0x0008" : "0x0002";
  const upFlag = normalizedButton === "right" ? "0x0010" : "0x0004";
  const hasTarget = Number.isFinite(Number(x)) && Number.isFinite(Number(y));
  const nextX = hasTarget ? Math.round(Number(x)) : 0;
  const nextY = hasTarget ? Math.round(Number(y)) : 0;
  const preserveCursor = Boolean(preserve_human_cursor || preserveHumanCursor) && hasTarget;
  const clickBody = `
[FrancisInput]::mouse_event(${downFlag}, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 24
[FrancisInput]::mouse_event(${upFlag}, 0, 0, 0, [UIntPtr]::Zero)
`.trim();
  const repetitions = double ? `${clickBody}\nStart-Sleep -Milliseconds 48\n${clickBody}` : clickBody;
  const captureCursor = preserveCursor
    ? `
$priorCursor = New-Object FrancisInput+POINT
[void][FrancisInput]::GetCursorPos([ref]$priorCursor)
`.trim()
    : "";
  const moveToTarget = hasTarget ? `[void][FrancisInput]::SetCursorPos(${nextX}, ${nextY})` : "";
  const restoreCursor = preserveCursor ? `[void][FrancisInput]::SetCursorPos($priorCursor.X, $priorCursor.Y)` : "";
  const body = [
    captureCursor,
    moveToTarget,
    repetitions,
    restoreCursor,
  ].filter(Boolean).join("\n");
  return `${buildWin32Prelude()}\n${body}`;
}

function buildMouseDragCommand({ start_x, start_y, x, y, button = "left", duration_ms = 220, steps = 12 }) {
  const normalizedButton = String(button || "left").trim().toLowerCase();
  const downFlag = normalizedButton === "right" ? "0x0008" : "0x0002";
  const upFlag = normalizedButton === "right" ? "0x0010" : "0x0004";
  const startX = Math.round(Number.isFinite(Number(start_x)) ? Number(start_x) : Number(x || 0));
  const startY = Math.round(Number.isFinite(Number(start_y)) ? Number(start_y) : Number(y || 0));
  const endX = Math.round(Number(x || 0));
  const endY = Math.round(Number(y || 0));
  const totalSteps = Math.max(4, Math.min(48, Math.round(Number(steps || 12))));
  const totalDuration = Math.max(60, Math.min(1800, Math.round(Number(duration_ms || 220))));
  const sleepMs = Math.max(4, Math.round(totalDuration / totalSteps));
  return `${buildWin32Prelude()}
[void][FrancisInput]::SetCursorPos(${startX}, ${startY})
[FrancisInput]::mouse_event(${downFlag}, 0, 0, 0, [UIntPtr]::Zero)
for ($i = 1; $i -le ${totalSteps}; $i++) {
  $progress = [double]$i / ${totalSteps}
  $nextX = [int][Math]::Round(${startX} + ((${endX} - ${startX}) * $progress))
  $nextY = [int][Math]::Round(${startY} + ((${endY} - ${startY}) * $progress))
  [void][FrancisInput]::SetCursorPos($nextX, $nextY)
  Start-Sleep -Milliseconds ${sleepMs}
}
[FrancisInput]::mouse_event(${upFlag}, 0, 0, 0, [UIntPtr]::Zero)`;
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

function buildWindowsDesktopCapabilityProfile({
  platform = process.platform,
  foregroundWindow = null,
} = {}) {
  const profile = {
    platform,
    matrix: WINDOWS_DESKTOP_SURFACE_MATRIX.map((entry) => ({ ...entry })),
    activeLimitations: [],
  };

  if (platform !== "win32") {
    profile.activeLimitations.push({
      key: "non_windows_platform",
      scope: "desktop_platform",
      severity: "blocked",
      summary: "Desktop-native Windows surface authority is unavailable on the current platform.",
      fallback: "Run the Windows shell build to gain taskbar, topmost, and native desktop authority.",
    });
    return profile;
  }

  const processName = String(foregroundWindow?.process || "").trim().toLowerCase();
  const title = String(foregroundWindow?.title || "").trim().toLowerCase();
  const protectedSurface = /(easyanti|battleye|eac|vgc|valorant|faceit|anti[-_ ]?cheat)/i.test(`${processName} ${title}`);

  if (protectedSurface) {
    profile.activeLimitations.push({
      key: "protected_surface",
      scope: "protected_surfaces",
      severity: "blocked",
      summary: "The current foreground surface looks protected or anti-cheat controlled.",
      fallback: "Francis holds resident posture and preserves local controls without claiming direct overlay or input authority.",
    });
  }
  if (foregroundWindow?.elevated === true) {
    profile.activeLimitations.push({
      key: "elevated_foreground",
      scope: "elevated_apps",
      severity: "bounded",
      summary: "The foreground app is elevated, so non-elevated desktop authority can weaken here.",
      fallback: "Francis keeps the orb resident, documents the limit honestly, and waits for the surface to return to standard privileges.",
    });
  }
  if (foregroundWindow?.fullscreenLike === true) {
    profile.activeLimitations.push({
      key: "borderless_fullscreen",
      scope: "borderless_fullscreen",
      severity: "bounded",
      summary: "The foreground surface is effectively fullscreen, so compositor stability can weaken.",
      fallback: "Francis reasserts topmost presence and falls back to resident edge posture if Windows pushes the orb back.",
    });
  }

  return profile;
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
    await executePowerShell(buildMoveCursorCommand(args), options);
    return {
      status: "ok",
      kind,
      execution: buildOrbExecutionSemantics({
        kind,
        args,
        status: "completed",
        target: args,
      }),
    };
  }
  if (kind === "mouse.click") {
    await executePowerShell(buildMouseClickCommand(args), options);
    return {
      status: "ok",
      kind,
      execution: buildOrbExecutionSemantics({
        kind,
        args,
        status: "completed",
        target: args,
      }),
    };
  }
  if (kind === "mouse.drag") {
    await executePowerShell(buildMouseDragCommand(args), options);
    return {
      status: "ok",
      kind,
      execution: buildOrbExecutionSemantics({
        kind,
        args,
        status: "completed",
        target: { x: args.x, y: args.y, coordinate_space: args.coordinate_space || args.coordinateSpace || "screen" },
      }),
    };
  }
  if (kind === "keyboard.type") {
    await executePowerShell(buildTypeTextCommand(args), options);
    return {
      status: "ok",
      kind,
      execution: buildOrbExecutionSemantics({
        kind,
        args,
        status: "completed",
      }),
    };
  }
  if (kind === "keyboard.key") {
    await executePowerShell(buildKeyCommand(args), options);
    return {
      status: "ok",
      kind,
      execution: buildOrbExecutionSemantics({
        kind,
        args,
        status: "completed",
      }),
    };
  }
  if (kind === "keyboard.shortcut") {
    await executePowerShell(buildShortcutCommand(args), options);
    return {
      status: "ok",
      kind,
      execution: buildOrbExecutionSemantics({
        kind,
        args,
        status: "completed",
      }),
    };
  }
  throw new Error(`Unsupported Windows input command: ${kind}`);
}

module.exports = {
  INPUT_TIMEOUT_MS,
  WINDOWS_DESKTOP_SURFACE_MATRIX,
  buildWindowsDesktopCapabilityProfile,
  buildKeyCommand,
  buildMouseClickCommand,
  buildMouseDragCommand,
  buildMoveCursorCommand,
  buildShortcutCommand,
  buildTypeTextCommand,
  buildWin32Prelude,
  escapeSendKeysText,
  executePowerShell,
  executeWindowsInputCommand,
  toSendKeysShortcut,
};
