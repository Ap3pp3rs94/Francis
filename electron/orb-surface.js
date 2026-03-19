const ORB_WINDOW_TOPMOST_LEVEL = "screen-saver";

function _normalizeRegion(region) {
  const workArea = region?.workArea && typeof region.workArea === "object" ? region.workArea : region;
  return {
    x: Number(workArea?.x) || 0,
    y: Number(workArea?.y) || 0,
    width: Number(workArea?.width) || 0,
    height: Number(workArea?.height) || 0,
  };
}

function _resolveVirtualWorkArea(regions) {
  if (!Array.isArray(regions) || !regions.length) {
    return { x: 0, y: 0, width: 1280, height: 720 };
  }

  const normalized = regions
    .map((region) => _normalizeRegion(region))
    .filter((region) => region.width > 0 && region.height > 0);

  if (!normalized.length) {
    return { x: 0, y: 0, width: 1280, height: 720 };
  }

  const left = Math.min(...normalized.map((region) => region.x));
  const top = Math.min(...normalized.map((region) => region.y));
  const right = Math.max(...normalized.map((region) => region.x + region.width));
  const bottom = Math.max(...normalized.map((region) => region.y + region.height));

  return {
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
  };
}

function buildOrbWindowBounds(workAreaOrDisplays) {
  const virtualWorkArea = Array.isArray(workAreaOrDisplays)
    ? _resolveVirtualWorkArea(workAreaOrDisplays)
    : _normalizeRegion(workAreaOrDisplays);
  const safeWidth = Number(virtualWorkArea?.width) || 1280;
  const safeHeight = Number(virtualWorkArea?.height) || 720;
  const safeX = Number(virtualWorkArea?.x) || 0;
  const safeY = Number(virtualWorkArea?.y) || 0;

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
