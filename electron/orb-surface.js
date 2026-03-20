const ORB_WINDOW_TOPMOST_LEVEL = "screen-saver";

function _resolveRegionSource(region, { preferWorkArea = false } = {}) {
  if (preferWorkArea) {
    if (region?.workArea && typeof region.workArea === "object") {
      return region.workArea;
    }
    if (region?.bounds && typeof region.bounds === "object") {
      return region.bounds;
    }
    return region;
  }
  if (region?.bounds && typeof region.bounds === "object") {
    return region.bounds;
  }
  if (region?.workArea && typeof region.workArea === "object") {
    return region.workArea;
  }
  return region;
}

function _normalizeRegion(region, options = {}) {
  const source = _resolveRegionSource(region, options);
  return {
    x: Number(source?.x) || 0,
    y: Number(source?.y) || 0,
    width: Number(source?.width) || 0,
    height: Number(source?.height) || 0,
  };
}

function _resolveVirtualRegion(regions, options = {}) {
  if (!Array.isArray(regions) || !regions.length) {
    return { x: 0, y: 0, width: 1280, height: 720 };
  }

  const normalized = regions
    .map((region) => _normalizeRegion(region, options))
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

function buildOrbWindowBounds(boundsOrDisplays) {
  const virtualBounds = Array.isArray(boundsOrDisplays)
    ? _resolveVirtualRegion(boundsOrDisplays)
    : _normalizeRegion(boundsOrDisplays);
  const safeWidth = Number(virtualBounds?.width) || 1280;
  const safeHeight = Number(virtualBounds?.height) || 720;
  const safeX = Number(virtualBounds?.x) || 0;
  const safeY = Number(virtualBounds?.y) || 0;

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
