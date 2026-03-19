const DEFAULT_ORB_FOCUS_SIZE = 196;

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

module.exports = {
  DEFAULT_ORB_FOCUS_SIZE,
  buildOrbFocusCropRect,
};
