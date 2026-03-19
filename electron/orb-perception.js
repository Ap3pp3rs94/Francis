const DEFAULT_ORB_FOCUS_SIZE = 196;
const DEFAULT_ORB_STABILITY_WINDOW_MS = 480;
const DEFAULT_ORB_SETTLE_TRAVEL_PX = 24;
const DEFAULT_ORB_TRACKING_TRAVEL_PX = 120;
const DEFAULT_ORB_SETTLE_DWELL_MS = 180;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
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

module.exports = {
  DEFAULT_ORB_FOCUS_SIZE,
  DEFAULT_ORB_SETTLE_DWELL_MS,
  DEFAULT_ORB_SETTLE_TRAVEL_PX,
  DEFAULT_ORB_STABILITY_WINDOW_MS,
  DEFAULT_ORB_TRACKING_TRAVEL_PX,
  buildOrbFocusCropRect,
  buildOrbTargetStability,
};
