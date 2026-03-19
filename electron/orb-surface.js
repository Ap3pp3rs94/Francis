const ORB_WINDOW_TOPMOST_LEVEL = "screen-saver";

function buildOrbWindowBounds(workArea) {
  const safeWidth = Number(workArea?.width) || 1280;
  const safeHeight = Number(workArea?.height) || 720;
  const safeX = Number(workArea?.x) || 0;
  const safeY = Number(workArea?.y) || 0;

  return {
    x: safeX,
    y: safeY,
    width: Math.max(320, Math.round(safeWidth)),
    height: Math.max(240, Math.round(safeHeight)),
  };
}

module.exports = {
  ORB_WINDOW_TOPMOST_LEVEL,
  buildOrbWindowBounds,
};
