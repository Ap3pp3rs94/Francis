const ORB_WINDOW_TOPMOST_LEVEL = "screen-saver";
const ORB_WINDOW_TOPMOST_PRIORITY = 1;
const ORB_WINDOW_REINFORCE_INTERVAL_MS = 2400;
const ORB_SURFACE_VERSION = 1;
const ORB_WINDOW_MIN_WIDTH = 320;
const ORB_WINDOW_MIN_HEIGHT = 240;

function clampInteger(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.round(numeric) : fallback;
}

function normalizeSurfaceBounds(rawBounds, { minWidth = 1, minHeight = 1 } = {}) {
  const bounds = rawBounds && typeof rawBounds === "object" ? rawBounds : {};
  return {
    x: clampInteger(bounds.x, 0),
    y: clampInteger(bounds.y, 0),
    width: Math.max(minWidth, clampInteger(bounds.width, minWidth)),
    height: Math.max(minHeight, clampInteger(bounds.height, minHeight)),
  };
}

function resolveTaskbarEdge(bounds, workArea) {
  const safeBounds = normalizeSurfaceBounds(bounds, { minWidth: 1, minHeight: 1 });
  const safeWorkArea = normalizeSurfaceBounds(workArea || safeBounds, { minWidth: 1, minHeight: 1 });
  const insets = {
    top: Math.max(0, safeWorkArea.y - safeBounds.y),
    left: Math.max(0, safeWorkArea.x - safeBounds.x),
    right: Math.max(0, safeBounds.x + safeBounds.width - (safeWorkArea.x + safeWorkArea.width)),
    bottom: Math.max(0, safeBounds.y + safeBounds.height - (safeWorkArea.y + safeWorkArea.height)),
  };
  const [edge = "none", inset = 0] = Object.entries(insets)
    .sort((left, right) => right[1] - left[1])[0] || [];
  return {
    edge: inset > 0 ? edge : "none",
    inset: Math.max(0, clampInteger(inset, 0)),
    insets,
  };
}

function normalizeDisplayRecord(display, index = 0) {
  const bounds = normalizeSurfaceBounds(display?.bounds, { minWidth: 1, minHeight: 1 });
  const workArea = normalizeSurfaceBounds(display?.workArea || bounds, { minWidth: 1, minHeight: 1 });
  const taskbar = resolveTaskbarEdge(bounds, workArea);
  return {
    id: Number(display?.id) || index + 1,
    ordinal: Number(display?.ordinal) || index + 1,
    label:
      String(display?.label || "").trim()
      || (display?.primary ? "Primary Display" : `Display ${index + 1}`),
    primary: Boolean(display?.primary),
    scaleFactor: Number(display?.scaleFactor || 1) || 1,
    bounds,
    workArea,
    workAreaSize:
      display?.workAreaSize && typeof display.workAreaSize === "object"
        ? {
            width: Math.max(1, clampInteger(display.workAreaSize.width, workArea.width)),
            height: Math.max(1, clampInteger(display.workAreaSize.height, workArea.height)),
          }
        : {
            width: workArea.width,
            height: workArea.height,
          },
    taskbarEdge: taskbar.edge,
    taskbarInset: taskbar.inset,
    taskbarInsets: taskbar.insets,
  };
}

function buildOrbWindowBounds(boundsOrDisplays) {
  if (Array.isArray(boundsOrDisplays)) {
    const displays = boundsOrDisplays
      .map((entry, index) => normalizeDisplayRecord(entry, index).bounds)
      .filter((entry) => entry && entry.width > 0 && entry.height > 0);
    if (!displays.length) {
      return normalizeSurfaceBounds(null, {
        minWidth: ORB_WINDOW_MIN_WIDTH,
        minHeight: ORB_WINDOW_MIN_HEIGHT,
      });
    }
    const left = Math.min(...displays.map((entry) => entry.x));
    const top = Math.min(...displays.map((entry) => entry.y));
    const right = Math.max(...displays.map((entry) => entry.x + entry.width));
    const bottom = Math.max(...displays.map((entry) => entry.y + entry.height));
    return {
      x: left,
      y: top,
      width: Math.max(ORB_WINDOW_MIN_WIDTH, right - left),
      height: Math.max(ORB_WINDOW_MIN_HEIGHT, bottom - top),
    };
  }

  return normalizeSurfaceBounds(boundsOrDisplays, {
    minWidth: ORB_WINDOW_MIN_WIDTH,
    minHeight: ORB_WINDOW_MIN_HEIGHT,
  });
}

function buildOrbDisplayTopology(displays, {
  targetDisplayId = null,
  activeDisplayId = null,
} = {}) {
  const normalizedDisplays = (Array.isArray(displays) ? displays : [displays])
    .filter(Boolean)
    .map((display, index) => normalizeDisplayRecord(display, index));
  const primaryDisplay = normalizedDisplays.find((display) => display.primary) || normalizedDisplays[0] || null;
  const targetDisplay = normalizedDisplays.find((display) => display.id === Number(targetDisplayId)) || primaryDisplay;
  const activeDisplay = normalizedDisplays.find((display) => display.id === Number(activeDisplayId)) || targetDisplay || primaryDisplay;
  const virtualBounds = buildOrbWindowBounds(normalizedDisplays);

  return {
    version: ORB_SURFACE_VERSION,
    displayCount: normalizedDisplays.length,
    primaryDisplayId: primaryDisplay?.id || null,
    targetDisplayId: targetDisplay?.id || null,
    activeDisplayId: activeDisplay?.id || null,
    primaryDisplay,
    targetDisplay,
    activeDisplay,
    displays: normalizedDisplays,
    virtualBounds,
    summary:
      normalizedDisplays.length <= 1
        ? `Single display desktop with ${activeDisplay?.taskbarEdge && activeDisplay.taskbarEdge !== "none" ? `${activeDisplay.taskbarEdge} taskbar` : "floating taskbar"} posture.`
        : `${normalizedDisplays.length} displays with target ${String(targetDisplay?.label || "display")} and active ${String(activeDisplay?.label || "display")}.`,
  };
}

function calculateIntersectionArea(left, right) {
  if (!left || !right) {
    return 0;
  }
  const overlapWidth = Math.max(0, Math.min(left.x + left.width, right.x + right.width) - Math.max(left.x, right.x));
  const overlapHeight = Math.max(0, Math.min(left.y + left.height, right.y + right.height) - Math.max(left.y, right.y));
  return overlapWidth * overlapHeight;
}

function getDisplayForBounds(topology, bounds) {
  const safeBounds = normalizeSurfaceBounds(bounds, { minWidth: 1, minHeight: 1 });
  const displays = Array.isArray(topology?.displays) ? topology.displays : [];
  let bestDisplay = null;
  let bestArea = 0;
  for (const display of displays) {
    const area = calculateIntersectionArea(safeBounds, display?.bounds);
    if (area > bestArea) {
      bestArea = area;
      bestDisplay = display;
    }
  }
  return bestDisplay || topology?.activeDisplay || topology?.targetDisplay || null;
}

function isNearlyFullscreen(bounds, displayBounds) {
  if (!bounds || !displayBounds) {
    return false;
  }
  const safeBounds = normalizeSurfaceBounds(bounds, { minWidth: 1, minHeight: 1 });
  const safeDisplayBounds = normalizeSurfaceBounds(displayBounds, { minWidth: 1, minHeight: 1 });
  const horizontalSlack = Math.max(8, Math.round(safeDisplayBounds.width * 0.02));
  const verticalSlack = Math.max(8, Math.round(safeDisplayBounds.height * 0.02));
  return (
    Math.abs(safeBounds.x - safeDisplayBounds.x) <= horizontalSlack
    && Math.abs(safeBounds.y - safeDisplayBounds.y) <= verticalSlack
    && Math.abs((safeBounds.x + safeBounds.width) - (safeDisplayBounds.x + safeDisplayBounds.width)) <= horizontalSlack
    && Math.abs((safeBounds.y + safeBounds.height) - (safeDisplayBounds.y + safeDisplayBounds.height)) <= verticalSlack
  );
}

function classifyForegroundSurface(foregroundWindow, topology) {
  const processName = String(foregroundWindow?.process || "").trim().toLowerCase();
  const title = String(foregroundWindow?.title || "").trim();
  const elevated = foregroundWindow?.elevated === true;
  const bounds = normalizeSurfaceBounds(foregroundWindow?.bounds, { minWidth: 1, minHeight: 1 });
  const hostDisplay = getDisplayForBounds(topology, bounds);
  const fullscreenLike = Boolean(hostDisplay) && isNearlyFullscreen(bounds, hostDisplay.bounds);
  const taskbarHost = processName === "explorer";
  const protectedSurface = /(easyanti|battleye|eac|vgc|valorant|faceit|anti[-_ ]?cheat)/i.test(`${processName} ${title}`);

  let limitation = null;
  if (protectedSurface) {
    limitation = {
      key: "protected_surface",
      scope: "protected_surfaces",
      severity: "blocked",
      summary: "The foreground surface looks protected or anti-cheat controlled. Windows can block overlay and input authority here.",
      fallback: "Francis holds a truthful resident fallback posture and keeps local controls live without claiming direct surface authority.",
    };
  } else if (elevated) {
    limitation = {
      key: "elevated_foreground",
      scope: "elevated_apps",
      severity: "bounded",
      summary: "The foreground app is elevated. Non-elevated overlays and input bridges can lose authority on this surface.",
      fallback: "Francis stays resident, keeps local stop and pause live, and waits for the surface to return to standard desktop privileges.",
    };
  } else if (fullscreenLike) {
    limitation = {
      key: "borderless_fullscreen",
      scope: "borderless_fullscreen",
      severity: "bounded",
      summary: "The foreground surface is effectively fullscreen. Windows can weaken z-order stability here even when the orb is reinforced.",
      fallback: "Francis keeps the orb resident and reasserts topmost presence while holding honest degraded posture if the compositor pushes it back.",
    };
  }

  return {
    process: processName,
    title,
    pid: Number(foregroundWindow?.pid || 0) || null,
    elevated,
    bounds,
    hostDisplayId: hostDisplay?.id || null,
    hostDisplayLabel: hostDisplay?.label || "",
    fullscreenLike,
    taskbarHost,
    protectedSurface,
    limitation,
  };
}

function buildDesktopAuthoritySnapshot({
  displays,
  targetDisplayId = null,
  activeDisplayId = null,
  foregroundWindow = null,
  capabilityProfile = null,
  orbVisible = false,
  lensVisible = false,
  alwaysOnTop = true,
  overlayIgnoreMouseEvents = false,
  orbIgnoreMouseEvents = true,
  captureSuspended = false,
} = {}) {
  const topology = buildOrbDisplayTopology(displays, { targetDisplayId, activeDisplayId });
  const foreground = classifyForegroundSurface(foregroundWindow, topology);
  const baseProfile = capabilityProfile && typeof capabilityProfile === "object" ? capabilityProfile : {};
  const matrix = Array.isArray(baseProfile.matrix) ? baseProfile.matrix.map((entry) => ({ ...entry })) : [];
  const activeLimitations = Array.isArray(baseProfile.activeLimitations)
    ? baseProfile.activeLimitations.map((entry) => ({ ...entry }))
    : [];

  if (foreground.limitation && !activeLimitations.some((entry) => entry.key === foreground.limitation.key)) {
    activeLimitations.unshift({ ...foreground.limitation });
  }

  let mode = "desktop_authoritative";
  let summary = `Orb desktop authority is reinforced across ${Math.max(1, topology.displayCount)} display${topology.displayCount === 1 ? "" : "s"} with ${String(topology.activeDisplay?.label || "the active display")} as the live reference surface.`;
  let fallbackPosture = {
    mode: "full_desktop_authority",
    summary: "Orb topmost posture, taskbar reach, and display routing are all running at the strongest stable desktop level.",
  };

  if (captureSuspended) {
    mode = "capture_suspended";
    summary = "Protected capture mode is active. Francis is holding a truthful resident fallback instead of claiming desktop authority.";
    fallbackPosture = {
      mode: "resident_capture_hold",
      summary: "The orb stays resident with local controls while protected capture mode temporarily suppresses desktop authority.",
    };
  } else if (activeLimitations.length) {
    const blocked = activeLimitations.some((entry) => String(entry.severity || "").toLowerCase() === "blocked");
    mode = blocked ? "desktop_authority_limited" : "desktop_authority_bounded";
    summary = activeLimitations[0].summary;
    fallbackPosture = {
      mode: blocked ? "resident_truthful_hold" : "resident_reinforced_hold",
      summary: activeLimitations[0].fallback || "Francis keeps the orb resident and local controls live while desktop authority is partially constrained.",
    };
  }

  const cards = [
    {
      label: "Taskbar",
      value:
        topology.activeDisplay?.taskbarEdge && topology.activeDisplay.taskbarEdge !== "none"
          ? `${topology.activeDisplay.label} ${topology.activeDisplay.taskbarEdge} edge`
          : `${String(topology.activeDisplay?.label || "Active display")} edge routing`,
      tone: "medium",
    },
    {
      label: "Top Layer",
      value: alwaysOnTop ? `reinforced ${ORB_WINDOW_TOPMOST_LEVEL}` : "released",
      tone: alwaysOnTop ? "high" : "low",
    },
    {
      label: "Displays",
      value: `${Math.max(1, topology.displayCount)} display${topology.displayCount === 1 ? "" : "s"} | target ${String(topology.targetDisplay?.label || "display")}`,
      tone: "medium",
    },
    {
      label: "Fallback",
      value: fallbackPosture.summary,
      tone: mode === "desktop_authoritative" ? "medium" : mode === "capture_suspended" ? "high" : "medium",
    },
  ];

  if (foreground.hostDisplayLabel || foreground.process || foreground.title) {
    cards.push({
      label: "Foreground",
      value:
        foreground.hostDisplayLabel
          ? `${foreground.hostDisplayLabel} | ${foreground.process || foreground.title || "desktop surface"}`
          : foreground.process || foreground.title || "desktop surface",
      tone: activeLimitations.length ? "medium" : "low",
    });
  }

  if (activeLimitations.length) {
    cards.push({
      label: "Active Limit",
      value: activeLimitations[0].summary,
      tone: String(activeLimitations[0].severity || "").toLowerCase() === "blocked" ? "high" : "medium",
    });
  }

  const items = [
    {
      label: "Resident Surface",
      summary: orbVisible
        ? `Orb visible | ${orbIgnoreMouseEvents ? "pass-through resident" : "interactive resident"}`
        : "Orb hidden",
    },
    {
      label: "Lens Surface",
      summary: lensVisible
        ? `Lens visible | ${overlayIgnoreMouseEvents ? "click-through" : "interactive"}`
        : "Lens hidden",
    },
    {
      label: "Virtual Bounds",
      summary: `${topology.virtualBounds.width}x${topology.virtualBounds.height} @ ${topology.virtualBounds.x},${topology.virtualBounds.y}`,
    },
    {
      label: "Reassertion",
      summary: `Topmost and workspace presence are reasserted every ${Math.round(ORB_WINDOW_REINFORCE_INTERVAL_MS / 100) / 10}s while the orb is visible.`,
    },
  ];

  for (const limitation of activeLimitations) {
    items.push({
      label: limitation.scope || limitation.key || "Desktop limit",
      summary: `${limitation.summary} ${limitation.fallback || ""}`.trim(),
    });
  }

  return {
    version: ORB_SURFACE_VERSION,
    mode,
    summary,
    topmostLevel: ORB_WINDOW_TOPMOST_LEVEL,
    topmostPriority: ORB_WINDOW_TOPMOST_PRIORITY,
    reassertionMs: ORB_WINDOW_REINFORCE_INTERVAL_MS,
    targetDisplayId: topology.targetDisplayId,
    activeDisplayId: topology.activeDisplayId,
    virtualBounds: topology.virtualBounds,
    displays: topology.displays,
    targetDisplay: topology.targetDisplay,
    activeDisplay: topology.activeDisplay,
    foreground,
    matrix,
    activeLimitations,
    fallbackPosture,
    cards,
    items,
  };
}

module.exports = {
  ORB_SURFACE_VERSION,
  ORB_WINDOW_REINFORCE_INTERVAL_MS,
  ORB_WINDOW_TOPMOST_LEVEL,
  ORB_WINDOW_TOPMOST_PRIORITY,
  buildDesktopAuthoritySnapshot,
  buildOrbDisplayTopology,
  buildOrbWindowBounds,
  resolveTaskbarEdge,
};
