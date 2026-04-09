const { execFile } = require("node:child_process");
const { promisify } = require("node:util");

const execFileAsync = promisify(execFile);

const DEFAULT_ORB_FOCUS_SIZE = 196;
const DEFAULT_ORB_STABILITY_WINDOW_MS = 480;
const DEFAULT_ORB_SETTLE_TRAVEL_PX = 24;
const DEFAULT_ORB_TRACKING_TRAVEL_PX = 120;
const DEFAULT_ORB_SETTLE_DWELL_MS = 180;
const DEFAULT_ORB_ACCESSIBILITY_TIMEOUT_MS = 900;
const DEFAULT_ORB_ENVIRONMENT_WINDOW_MS = 3200;

const EMPTY_ORB_ACCESSIBILITY = Object.freeze({
  available: false,
  attached: false,
  status: "unavailable",
  label: "",
  name: "",
  automationId: "",
  controlType: "",
  localizedControlType: "",
  className: "",
  processId: null,
  hasKeyboardFocus: false,
  enabled: false,
  offscreen: false,
  bounds: {
    x: null,
    y: null,
    width: 0,
    height: 0,
  },
  summary: "Focused accessibility target is unavailable.",
});

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function clampRatio(value) {
  return clamp(Number.isFinite(value) ? value : 0, 0, 1);
}

function normalizeOptionalInt(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.round(number) : null;
}

function normalizeRect(value) {
  const record = value && typeof value === "object" ? value : {};
  return {
    x: normalizeOptionalInt(record.x),
    y: normalizeOptionalInt(record.y),
    width: Math.max(0, Math.round(Number(record.width || 0))),
    height: Math.max(0, Math.round(Number(record.height || 0))),
  };
}

function pointInRect(point, rect) {
  if (!point || typeof point !== "object") {
    return false;
  }
  if (!rect || rect.x === null || rect.y === null || rect.width <= 0 || rect.height <= 0) {
    return false;
  }
  const x = Number(point.x);
  const y = Number(point.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return false;
  }
  return x >= rect.x && x <= rect.x + rect.width && y >= rect.y && y <= rect.y + rect.height;
}

function rectArea(rect) {
  if (!rect || rect.width <= 0 || rect.height <= 0) {
    return 0;
  }
  return rect.width * rect.height;
}

function intersectionArea(left, right) {
  if (!left || !right || left.x === null || left.y === null || right.x === null || right.y === null) {
    return 0;
  }
  const overlapWidth = Math.max(
    0,
    Math.min(left.x + left.width, right.x + right.width) - Math.max(left.x, right.x),
  );
  const overlapHeight = Math.max(
    0,
    Math.min(left.y + left.height, right.y + right.height) - Math.max(left.y, right.y),
  );
  return overlapWidth * overlapHeight;
}

function overlapRatio(subject, container) {
  const area = rectArea(subject);
  if (area <= 0) {
    return 0;
  }
  return clampRatio(intersectionArea(subject, container) / area);
}

function distancePointToRect(point, rect) {
  if (!point || typeof point !== "object" || !rect || rect.x === null || rect.y === null) {
    return null;
  }
  const x = Number(point.x);
  const y = Number(point.y);
  if (!Number.isFinite(x) || !Number.isFinite(y) || rect.width <= 0 || rect.height <= 0) {
    return null;
  }
  const dx = Math.max(rect.x - x, 0, x - (rect.x + rect.width));
  const dy = Math.max(rect.y - y, 0, y - (rect.y + rect.height));
  return Math.hypot(dx, dy);
}

function buildOrbFocusCropRect({
  sourceWidth,
  sourceHeight,
  displayBounds,
  cursorScreen,
  cropSize = DEFAULT_ORB_FOCUS_SIZE,
} = {}) {
  const width = Math.max(1, Math.round(Number(sourceWidth || 0)));
  const height = Math.max(1, Math.round(Number(sourceHeight || 0)));
  const display = displayBounds && typeof displayBounds === "object" ? displayBounds : {};
  const displayWidth = Math.max(1, Math.round(Number(display.width || width)));
  const displayHeight = Math.max(1, Math.round(Number(display.height || height)));
  const displayX = Math.round(Number(display.x || 0));
  const displayY = Math.round(Number(display.y || 0));
  const requestedCrop = Math.max(64, Math.round(Number(cropSize || DEFAULT_ORB_FOCUS_SIZE)));
  const cropWidth = Math.min(width, requestedCrop);
  const cropHeight = Math.min(height, requestedCrop);
  const cursor = cursorScreen && typeof cursorScreen === "object" ? cursorScreen : {};
  const relativeX = clamp(
    Number(cursor.x || displayX) - displayX,
    0,
    displayWidth,
  );
  const relativeY = clamp(
    Number(cursor.y || displayY) - displayY,
    0,
    displayHeight,
  );
  const targetX = Math.round((relativeX / displayWidth) * width);
  const targetY = Math.round((relativeY / displayHeight) * height);
  const x = clamp(Math.round(targetX - cropWidth / 2), 0, Math.max(0, width - cropWidth));
  const y = clamp(Math.round(targetY - cropHeight / 2), 0, Math.max(0, height - cropHeight));

  return {
    x,
    y,
    width: cropWidth,
    height: cropHeight,
  };
}

function buildOrbTargetStability({
  samples = [],
  nowMs = Date.now(),
  windowMs = DEFAULT_ORB_STABILITY_WINDOW_MS,
  settleTravelPx = DEFAULT_ORB_SETTLE_TRAVEL_PX,
  trackingTravelPx = DEFAULT_ORB_TRACKING_TRAVEL_PX,
  settleDwellMs = DEFAULT_ORB_SETTLE_DWELL_MS,
} = {}) {
  const normalizedSamples = Array.isArray(samples)
    ? samples
      .filter((sample) =>
        sample
        && Number.isFinite(sample.x)
        && Number.isFinite(sample.y)
        && Number.isFinite(sample.at),
      )
      .map((sample) => ({
        x: Math.round(Number(sample.x)),
        y: Math.round(Number(sample.y)),
        at: Number(sample.at),
      }))
      .filter((sample) => nowMs - sample.at <= Math.max(120, Number(windowMs || DEFAULT_ORB_STABILITY_WINDOW_MS)))
      .sort((left, right) => left.at - right.at)
    : [];

  if (!normalizedSamples.length) {
    return {
      state: "idle",
      dwellMs: 0,
      travelPx: 0,
      sampleCount: 0,
      summary: "Cursor stability is not attached yet.",
    };
  }

  let travelPx = 0;
  for (let index = 1; index < normalizedSamples.length; index += 1) {
    const previous = normalizedSamples[index - 1];
    const current = normalizedSamples[index];
    travelPx += Math.hypot(current.x - previous.x, current.y - previous.y);
  }

  const latest = normalizedSamples[normalizedSamples.length - 1];
  const settleRadius = Math.max(8, Math.round(Number(settleTravelPx || DEFAULT_ORB_SETTLE_TRAVEL_PX) / 3));
  let dwellAnchorAt = latest.at;
  for (let index = normalizedSamples.length - 2; index >= 0; index -= 1) {
    const sample = normalizedSamples[index];
    const driftPx = Math.hypot(latest.x - sample.x, latest.y - sample.y);
    if (driftPx > settleRadius) {
      break;
    }
    dwellAnchorAt = sample.at;
  }

  const dwellMs = Math.max(0, Math.round(nowMs - dwellAnchorAt));
  const roundedTravelPx = Math.max(0, Math.round(travelPx));
  let state = "tracking";
  if (dwellMs >= Math.max(80, Number(settleDwellMs || DEFAULT_ORB_SETTLE_DWELL_MS)) && travelPx <= Math.max(8, Number(settleTravelPx || DEFAULT_ORB_SETTLE_TRAVEL_PX))) {
    state = "settled";
  } else if (travelPx > Math.max(24, Number(trackingTravelPx || DEFAULT_ORB_TRACKING_TRAVEL_PX))) {
    state = "transient";
  }

  const summary = state === "settled"
    ? `Cursor target is settled after ${dwellMs}ms with ${roundedTravelPx}px of recent travel.`
    : state === "transient"
      ? `Cursor target is transient with ${roundedTravelPx}px of recent travel.`
      : `Cursor target is still tracking with ${roundedTravelPx}px of recent travel.`;

  return {
    state,
    dwellMs,
    travelPx: roundedTravelPx,
    sampleCount: normalizedSamples.length,
    summary,
  };
}

function buildOrbFocusedAccessibilityCommand() {
  return `
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$element = [System.Windows.Automation.AutomationElement]::FocusedElement
if ($null -eq $element) {
  [pscustomobject]@{
    available = $true
    attached = $false
    status = "idle"
    name = ""
    automationId = ""
    controlType = ""
    localizedControlType = ""
    className = ""
    processId = $null
    hasKeyboardFocus = $false
    enabled = $false
    offscreen = $false
    bounds = [pscustomobject]@{
      x = $null
      y = $null
      width = 0
      height = 0
    }
  } | ConvertTo-Json -Compress
  return
}
$rect = $element.Current.BoundingRectangle
$controlType = ""
if ($element.Current.ControlType -ne $null) {
  $controlType = $element.Current.ControlType.ProgrammaticName
}
[pscustomobject]@{
  available = $true
  attached = $true
  status = "attached"
  name = $element.Current.Name
  automationId = $element.Current.AutomationId
  controlType = $controlType
  localizedControlType = $element.Current.LocalizedControlType
  className = $element.Current.ClassName
  processId = [int]$element.Current.ProcessId
  hasKeyboardFocus = [bool]$element.Current.HasKeyboardFocus
  enabled = [bool]$element.Current.IsEnabled
  offscreen = [bool]$element.Current.IsOffscreen
  bounds = [pscustomobject]@{
    x = [int]$rect.Left
    y = [int]$rect.Top
    width = [int]$rect.Width
    height = [int]$rect.Height
  }
} | ConvertTo-Json -Compress
`.trim();
}

function normalizeOrbFocusedAccessibilityInfo(payload = {}) {
  const record = payload && typeof payload === "object" ? payload : {};
  const bounds = normalizeRect(record.bounds);
  const available = Boolean(record.available);
  const offscreen = Boolean(record.offscreen);
  const processId = normalizeOptionalInt(record.processId ?? record.pid);
  const rawControlType = String(record.controlType || "").trim();
  const normalizedControlType = rawControlType
    ? rawControlType.split(".").pop().replace(/controltype$/i, "").replace(/_/g, " ").trim().toLowerCase()
    : "";
  const localizedControlType = String(record.localizedControlType || "").trim();
  const name = String(record.name || "").trim();
  const automationId = String(record.automationId || "").trim();
  const label = name || localizedControlType || automationId || (normalizedControlType ? `${normalizedControlType} control` : "");
  const attached = Boolean(
    (record.attached || available)
    && !offscreen
    && bounds.width > 0
    && bounds.height > 0
    && (label || processId !== null),
  );
  const status = String(record.status || "").trim().toLowerCase()
    || (attached ? "attached" : available ? "idle" : "unavailable");
  const summary = attached
    ? `Focused accessibility target is ${label || "attached"}${normalizedControlType ? ` (${normalizedControlType})` : ""}.`
    : available
      ? "Focused accessibility target is not attached right now."
      : "Focused accessibility target is unavailable.";

  return {
    available,
    attached,
    status,
    label,
    name,
    automationId,
    controlType: normalizedControlType,
    localizedControlType,
    className: String(record.className || "").trim(),
    processId,
    hasKeyboardFocus: Boolean(record.hasKeyboardFocus),
    enabled: Boolean(record.enabled),
    offscreen,
    bounds,
    summary,
  };
}

async function getOrbFocusedAccessibilitySnapshot(options = {}) {
  const {
    platform = process.platform,
    execFileImpl = execFileAsync,
    timeoutMs = DEFAULT_ORB_ACCESSIBILITY_TIMEOUT_MS,
  } = options;

  if (platform !== "win32") {
    return { ...EMPTY_ORB_ACCESSIBILITY, status: "unsupported", summary: "Focused accessibility target is unsupported on this platform." };
  }

  try {
    const { stdout } = await execFileImpl(
      "powershell",
      ["-NoProfile", "-Command", buildOrbFocusedAccessibilityCommand()],
      {
        timeout: timeoutMs,
        windowsHide: true,
        maxBuffer: 1024 * 32,
      },
    );
    return normalizeOrbFocusedAccessibilityInfo(JSON.parse(String(stdout || "{}")));
  } catch {
    return { ...EMPTY_ORB_ACCESSIBILITY, status: "unavailable", summary: "Focused accessibility target is unavailable." };
  }
}

function buildOrbEnvironmentGrounding({
  cursorScreen = null,
  displayBounds = null,
  foregroundWindow = null,
  accessibility = null,
  targetStability = null,
  focusAttached = false,
  frameAttached = false,
  samples = [],
  nowMs = Date.now(),
  windowMs = DEFAULT_ORB_ENVIRONMENT_WINDOW_MS,
} = {}) {
  const cursor = cursorScreen && typeof cursorScreen === "object"
    ? {
        x: Number.isFinite(Number(cursorScreen.x)) ? Math.round(Number(cursorScreen.x)) : null,
        y: Number.isFinite(Number(cursorScreen.y)) ? Math.round(Number(cursorScreen.y)) : null,
      }
    : { x: null, y: null };
  const displayRect = normalizeRect(displayBounds);
  const windowRecord = foregroundWindow && typeof foregroundWindow === "object" ? foregroundWindow : {};
  const windowBounds = normalizeRect(windowRecord.bounds);
  const windowPid = normalizeOptionalInt(windowRecord.pid);
  const windowAttached = Boolean(
    String(windowRecord.title || "").trim()
    || String(windowRecord.process || "").trim()
    || windowPid !== null
    || rectArea(windowBounds) > 0,
  );
  const cursorInWindow = pointInRect(cursor, windowBounds);
  const windowOverlapRatio = rectArea(windowBounds) > 0 && rectArea(displayRect) > 0
    ? clampRatio(intersectionArea(windowBounds, displayRect) / rectArea(windowBounds))
    : 0;
  const windowOnDisplay = !windowAttached || rectArea(displayRect) === 0 || windowOverlapRatio >= 0.35;

  const normalizedAccessibility = normalizeOrbFocusedAccessibilityInfo(accessibility || {});
  const accessibilityBounds = normalizeRect(normalizedAccessibility.bounds);
  const accessibilityAttached = Boolean(normalizedAccessibility.attached);
  const accessibilityProcessMatch = accessibilityAttached
    ? (windowPid === null || normalizedAccessibility.processId === null || windowPid === normalizedAccessibility.processId)
    : false;
  const accessibilityInWindow = accessibilityAttached && windowAttached
    ? overlapRatio(accessibilityBounds, windowBounds) >= 0.55
    : false;
  const cursorInsideAccessibility = accessibilityAttached && pointInRect(cursor, accessibilityBounds);
  const cursorDistancePxRaw = accessibilityAttached ? distancePointToRect(cursor, accessibilityBounds) : null;
  const cursorDistancePx = cursorDistancePxRaw === null ? null : Math.round(cursorDistancePxRaw);

  const stabilityState = String(targetStability?.state || "idle").trim().toLowerCase() || "idle";
  const currentWindowKey = windowAttached
    ? [
        windowPid ?? "nopid",
        String(windowRecord.process || "").trim().toLowerCase(),
        String(windowRecord.title || "").trim().toLowerCase(),
        `${windowBounds.x ?? "x"}:${windowBounds.y ?? "y"}:${windowBounds.width}:${windowBounds.height}`,
      ].join("|")
    : "";
  const normalizedSamples = Array.isArray(samples)
    ? samples
      .filter((sample) => sample && Number.isFinite(Number(sample.at)))
      .map((sample) => ({
        key: String(sample.key || "").trim(),
        at: Number(sample.at),
      }))
      .filter((sample) => nowMs - sample.at <= Math.max(800, Number(windowMs || DEFAULT_ORB_ENVIRONMENT_WINDOW_MS)))
    : [];
  const continuityMatches = currentWindowKey
    ? normalizedSamples.filter((sample) => sample.key === currentWindowKey).length + 1
    : 0;
  const recentSwitch = Boolean(
    currentWindowKey
    && normalizedSamples.some((sample) => sample.key && sample.key !== currentWindowKey && nowMs - sample.at <= 1000),
  );
  const continuityState = !currentWindowKey
    ? "unavailable"
    : continuityMatches >= 3
      ? "anchored"
      : continuityMatches >= 2
        ? "tracking"
        : recentSwitch
          ? "recent_switch"
          : "observed";

  const sourcePriority = [];
  if (accessibilityAttached && accessibilityProcessMatch && (cursorInsideAccessibility || accessibilityInWindow)) {
    sourcePriority.push("accessibility");
  }
  if (windowAttached && cursorInWindow) {
    sourcePriority.push("window_metadata");
  }
  if (focusAttached) {
    sourcePriority.push("visual_focus");
  }
  if (frameAttached) {
    sourcePriority.push("display_capture");
  }
  if (!sourcePriority.length && windowAttached) {
    sourcePriority.push("window_metadata");
  }

  let score = 0;
  if (frameAttached) {
    score += 0.08;
  }
  if (focusAttached) {
    score += 0.16;
  }
  if (windowAttached) {
    score += cursorInWindow ? 0.18 : 0.03;
    score += windowOnDisplay ? 0.08 : -0.08;
  }
  if (continuityState === "anchored") {
    score += 0.14;
  } else if (continuityState === "tracking") {
    score += 0.08;
  } else if (continuityState === "observed") {
    score += 0.03;
  } else if (continuityState === "recent_switch") {
    score -= 0.06;
  }
  if (stabilityState === "settled") {
    score += 0.22;
  } else if (stabilityState === "tracking") {
    score += 0.12;
  } else if (stabilityState === "transient") {
    score -= 0.08;
  }
  if (accessibilityAttached && accessibilityProcessMatch) {
    if (cursorInsideAccessibility) {
      score += 0.24;
    } else if (accessibilityInWindow) {
      score += 0.16;
    } else {
      score += 0.04;
      score -= 0.08;
    }
    if (cursorDistancePx !== null && cursorDistancePx <= 96) {
      score += 0.06;
    }
  }
  score = clampRatio(score);

  let state = "weak";
  let invalidationReason = "";
  if (!windowAttached && !focusAttached && !frameAttached && !accessibilityAttached) {
    state = "weak";
    invalidationReason = "no_environment_evidence";
  } else if (
    windowAttached
    && (!cursorInWindow || !windowOnDisplay)
    && !(accessibilityAttached && accessibilityProcessMatch && cursorInsideAccessibility)
  ) {
    state = "detached";
    invalidationReason = !windowOnDisplay
      ? "window_detached_from_active_display"
      : "cursor_left_foreground_window";
  } else if (stabilityState === "transient" && score < 0.6) {
    state = "reassess";
    invalidationReason = "transient_cursor";
  } else if (
    score >= 0.78
    && cursorInWindow
    && (focusAttached || (accessibilityAttached && accessibilityProcessMatch && accessibilityInWindow))
    && stabilityState === "settled"
  ) {
    state = "grounded";
  } else if (
    score >= 0.52
    && (cursorInWindow || (accessibilityAttached && accessibilityProcessMatch && accessibilityInWindow))
    && ["settled", "tracking"].includes(stabilityState)
  ) {
    state = "tracking";
  } else if (score >= 0.34 || focusAttached || accessibilityAttached) {
    state = "reassess";
    invalidationReason = invalidationReason || "grounding_not_settled";
  }

  const primarySource = sourcePriority[0] || "";
  const summary = state === "grounded"
    ? "Accessibility, window, and visual evidence align on the current target."
    : state === "tracking"
      ? "Foreground window and local evidence plausibly track the current target."
      : state === "detached"
        ? "The current focus point drifted outside the grounded foreground path."
        : state === "reassess"
          ? "Environmental grounding is present, but Francis should reassess before locking."
          : "Environmental grounding is weak and should not hard-lock yet.";
  const detail = state === "grounded"
    ? `Primary source is ${primarySource || "window metadata"} with ${continuityState.replace(/_/g, " ")} foreground continuity.`
    : state === "tracking"
      ? `Primary source is ${primarySource || "window metadata"} while the cursor still ${stabilityState === "tracking" ? "tracks" : "settles"} inside the foreground window.`
      : state === "detached"
        ? "The cursor or focused control is no longer grounded cleanly inside the active foreground window."
        : state === "reassess"
          ? "The target remains visible, but Francis should re-evaluate before promoting it into lock."
          : "Only shallow environmental evidence is attached right now.";

  return {
    sourcePriority,
    primarySource,
    sample: currentWindowKey ? { key: currentWindowKey, at: nowMs } : null,
    sources: {
      accessibility: {
        available: Boolean(normalizedAccessibility.available),
        attached: accessibilityAttached,
        process_match: accessibilityProcessMatch,
        in_window: accessibilityInWindow,
        cursor_inside: cursorInsideAccessibility,
        cursor_distance_px: cursorDistancePx,
        label: normalizedAccessibility.label,
        control_type: normalizedAccessibility.controlType,
        summary: normalizedAccessibility.summary,
      },
      window_metadata: {
        attached: windowAttached,
        in_window: cursorInWindow,
        on_display: windowOnDisplay,
        overlap_ratio: Number(windowOverlapRatio.toFixed(3)),
        continuity_state: continuityState,
        summary: windowAttached
          ? (cursorInWindow
            ? "Cursor remains grounded inside the foreground window."
            : "Cursor is outside the grounded foreground window.")
          : "Foreground-window metadata is unavailable.",
      },
      visual_focus: {
        attached: Boolean(focusAttached),
        summary: focusAttached
          ? "A focused local crop is attached around the current target region."
          : "No focused local crop is attached.",
      },
      display_capture: {
        attached: Boolean(frameAttached),
        summary: frameAttached
          ? "The active display thumbnail is attached."
          : "No active display thumbnail is attached.",
      },
    },
    grounding: {
      state,
      score: Number(score.toFixed(3)),
      in_window: cursorInWindow,
      on_display: windowOnDisplay,
      continuity_state: continuityState,
      invalidation_reason: invalidationReason,
      summary,
      detail,
    },
  };
}

module.exports = {
  DEFAULT_ORB_ACCESSIBILITY_TIMEOUT_MS,
  DEFAULT_ORB_ENVIRONMENT_WINDOW_MS,
  DEFAULT_ORB_FOCUS_SIZE,
  DEFAULT_ORB_SETTLE_DWELL_MS,
  DEFAULT_ORB_SETTLE_TRAVEL_PX,
  DEFAULT_ORB_STABILITY_WINDOW_MS,
  DEFAULT_ORB_TRACKING_TRAVEL_PX,
  EMPTY_ORB_ACCESSIBILITY,
  buildOrbEnvironmentGrounding,
  buildOrbFocusCropRect,
  buildOrbFocusedAccessibilityCommand,
  buildOrbTargetStability,
  getOrbFocusedAccessibilitySnapshot,
  normalizeOrbFocusedAccessibilityInfo,
};
