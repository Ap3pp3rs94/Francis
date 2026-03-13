const fs = require("node:fs");
const path = require("node:path");

const LIFECYCLE_HISTORY_FILE = "overlay-lifecycle-history.json";
const LIFECYCLE_HISTORY_VERSION = 1;
const MAX_LIFECYCLE_HISTORY_ITEMS = 24;

function getLifecycleHistoryPath(userDataPath) {
  return path.join(userDataPath, LIFECYCLE_HISTORY_FILE);
}

function buildDefaultLifecycleHistoryState() {
  return {
    version: LIFECYCLE_HISTORY_VERSION,
    items: [],
  };
}

function normalizeHistoryItem(raw) {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const kind = typeof raw.kind === "string" ? raw.kind : "";
  const summary = typeof raw.summary === "string" ? raw.summary : "";
  if (!kind || !summary) {
    return null;
  }
  return {
    id: typeof raw.id === "string" && raw.id ? raw.id : `${Date.now()}-${kind}`,
    at: typeof raw.at === "string" ? raw.at : new Date().toISOString(),
    kind,
    summary,
    tone: typeof raw.tone === "string" ? raw.tone : "low",
    detail: raw.detail && typeof raw.detail === "object" ? raw.detail : {},
  };
}

function normalizeLifecycleHistoryState(raw) {
  const defaults = buildDefaultLifecycleHistoryState();
  if (!raw || typeof raw !== "object") {
    return defaults;
  }
  const items = Array.isArray(raw.items)
    ? raw.items.map(normalizeHistoryItem).filter(Boolean).slice(0, MAX_LIFECYCLE_HISTORY_ITEMS)
    : [];
  return {
    version: LIFECYCLE_HISTORY_VERSION,
    items,
  };
}

function loadLifecycleHistoryState(userDataPath) {
  const filePath = getLifecycleHistoryPath(userDataPath);
  try {
    return normalizeLifecycleHistoryState(JSON.parse(fs.readFileSync(filePath, "utf8")));
  } catch {
    return buildDefaultLifecycleHistoryState();
  }
}

function saveLifecycleHistoryState(userDataPath, state) {
  const filePath = getLifecycleHistoryPath(userDataPath);
  const normalized = normalizeLifecycleHistoryState(state);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(normalized, null, 2), "utf8");
  return normalized;
}

function recordLifecycleEvent(userDataPath, state, event) {
  const current = normalizeLifecycleHistoryState(state);
  const item = normalizeHistoryItem(event);
  if (!item) {
    return current;
  }
  return saveLifecycleHistoryState(userDataPath, {
    ...current,
    items: [item, ...current.items].slice(0, MAX_LIFECYCLE_HISTORY_ITEMS),
  });
}

function buildLifecycleHistorySurface(state) {
  const normalized = normalizeLifecycleHistoryState(state);
  const latest = normalized.items[0] || null;
  const summary = latest
    ? `${latest.summary} (${latest.at})`
    : "No shell lifecycle actions have been recorded yet.";

  return {
    summary,
    count: normalized.items.length,
    latestKind: latest?.kind || null,
    cards: [
      {
        label: "Summary",
        value: summary,
        tone: latest?.tone || "low",
      },
      {
        label: "Entries",
        value: String(normalized.items.length),
        tone: normalized.items.length > 0 ? "medium" : "low",
      },
      {
        label: "Latest Kind",
        value: latest?.kind || "none",
        tone: latest?.tone || "low",
      },
    ],
    items: normalized.items.slice(0, 8),
  };
}

module.exports = {
  LIFECYCLE_HISTORY_FILE,
  LIFECYCLE_HISTORY_VERSION,
  MAX_LIFECYCLE_HISTORY_ITEMS,
  buildDefaultLifecycleHistoryState,
  buildLifecycleHistorySurface,
  getLifecycleHistoryPath,
  loadLifecycleHistoryState,
  normalizeLifecycleHistoryState,
  recordLifecycleEvent,
  saveLifecycleHistoryState,
};
