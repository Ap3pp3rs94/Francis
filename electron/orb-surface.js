const ORB_WINDOW_SIZE = 220;
const ORB_WINDOW_MARGIN = 28;
const ORB_WINDOW_TOPMOST_LEVEL = "screen-saver";

function buildOrbWindowBounds(workArea, { size = ORB_WINDOW_SIZE, margin = ORB_WINDOW_MARGIN } = {}) {
  const safeWidth = Number(workArea?.width) || 1280;
  const safeHeight = Number(workArea?.height) || 720;
  const safeX = Number(workArea?.x) || 0;
  const safeY = Number(workArea?.y) || 0;
  const safeSize = Math.max(160, Math.round(size));
  const safeMargin = Math.max(12, Math.round(margin));

  return {
    x: Math.max(safeX + safeMargin, safeX + safeWidth - safeSize - safeMargin),
    y: Math.max(safeY + safeMargin, safeY + safeMargin),
    width: safeSize,
    height: safeSize,
  };
}

module.exports = {
  ORB_WINDOW_MARGIN,
  ORB_WINDOW_SIZE,
  ORB_WINDOW_TOPMOST_LEVEL,
  buildOrbWindowBounds,
};
