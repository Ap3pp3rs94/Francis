const { execFile } = require("node:child_process");
const { promisify } = require("node:util");

const execFileAsync = promisify(execFile);

const EMPTY_FOREGROUND_WINDOW = Object.freeze({
  title: "",
  process: "",
  pid: null,
});

function normalizeForegroundWindowInfo(payload) {
  const record = payload && typeof payload === "object" ? payload : {};
  const pid = Number(record.pid);
  return {
    title: String(record.title || "").trim(),
    process: String(record.process || "").trim(),
    pid: Number.isFinite(pid) && pid > 0 ? Math.round(pid) : null,
  };
}

function buildForegroundWindowCommand() {
  return `
$ErrorActionPreference = "Stop"
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class FrancisForegroundWindow {
  [DllImport("user32.dll")]
  public static extern IntPtr GetForegroundWindow();

  [DllImport("user32.dll", CharSet = CharSet.Unicode)]
  public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

  [DllImport("user32.dll")]
  public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

$windowHandle = [FrancisForegroundWindow]::GetForegroundWindow()
$titleBuilder = New-Object System.Text.StringBuilder 1024
[void][FrancisForegroundWindow]::GetWindowText($windowHandle, $titleBuilder, $titleBuilder.Capacity)
[uint32]$processIdValue = 0
[void][FrancisForegroundWindow]::GetWindowThreadProcessId($windowHandle, [ref]$processIdValue)
$processName = ""
if ($processIdValue -gt 0) {
  $process = Get-Process -Id $processIdValue -ErrorAction SilentlyContinue
  if ($process) {
    $processName = $process.ProcessName
  }
}

[pscustomobject]@{
  title = $titleBuilder.ToString()
  process = $processName
  pid = [int]$processIdValue
} | ConvertTo-Json -Compress
`.trim();
}

async function getForegroundWindowInfo(options = {}) {
  const {
    platform = process.platform,
    execFileImpl = execFileAsync,
    timeoutMs = 1500,
  } = options;

  if (platform !== "win32") {
    return { ...EMPTY_FOREGROUND_WINDOW };
  }

  try {
    const { stdout } = await execFileImpl(
      "powershell",
      ["-NoProfile", "-Command", buildForegroundWindowCommand()],
      {
        timeout: timeoutMs,
        windowsHide: true,
        maxBuffer: 1024 * 32,
      },
    );
    return normalizeForegroundWindowInfo(JSON.parse(String(stdout || "{}")));
  } catch {
    return { ...EMPTY_FOREGROUND_WINDOW };
  }
}

module.exports = {
  EMPTY_FOREGROUND_WINDOW,
  buildForegroundWindowCommand,
  getForegroundWindowInfo,
  normalizeForegroundWindowInfo,
};
