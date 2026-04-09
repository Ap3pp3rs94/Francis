const FAILURE_DEGRADED_THRESHOLD = 1;
const FAILURE_DISCONNECTED_THRESHOLD = 3;
const FAILURE_CIRCUIT_THRESHOLD = 5;
const RECOVERY_SUCCESS_THRESHOLD = 2;
const FAILURE_BACKOFF_BASE_MS = 600;
const FAILURE_BACKOFF_MAX_MS = 12000;
const FAILURE_CIRCUIT_HOLD_MS = 12000;

function cleanText(value, fallback = "") {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text || fallback;
}

function looksTransportLevelMessage(value = "") {
  const lowered = cleanText(value).toLowerCase();
  return Boolean(
    lowered.includes("failed to fetch")
    || lowered.includes("fetch failed")
    || lowered.includes("network error")
    || lowered.includes("networkerror")
    || lowered.includes("timed out")
    || lowered.includes("econn")
    || lowered.includes("connection refused")
    || lowered.includes("connection reset")
  );
}

function getOrbRuntimeRetryDelayMs(failureCount, {
  baseMs = FAILURE_BACKOFF_BASE_MS,
  maxMs = FAILURE_BACKOFF_MAX_MS,
} = {}) {
  const safeFailures = Math.max(0, Number(failureCount || 0));
  const safeBase = Math.max(150, Number(baseMs || FAILURE_BACKOFF_BASE_MS));
  const safeMax = Math.max(safeBase, Number(maxMs || FAILURE_BACKOFF_MAX_MS));
  return Math.min(safeMax, safeBase * Math.max(1, 2 ** Math.min(safeFailures - 1, 4)));
}

function sanitizeRuntimeHealthDetail(reason = "", fallback = "") {
  const message = cleanText(reason);
  if (!message) {
    return cleanText(fallback);
  }
  if (looksTransportLevelMessage(message)) {
    return cleanText(fallback);
  }
  return message;
}

function isOrbRuntimeProbeDeferred(state = {}, nowMs = Date.now()) {
  const current = normalizeOrbRuntimeHealth(state);
  const now = Math.max(0, Number(nowMs || Date.now()));
  return Math.max(
    Number(current.nextProbeAtMs || 0),
    Number(current.circuitOpenUntilMs || 0),
  ) > now;
}

function buildDefaultOrbRuntimeHealth() {
  return {
    status: "nominal",
    source: "hud",
    summary: "Local operator runtime is nominal.",
    detail: "Local operator runtime is nominal.",
    failureCount: 0,
    consecutiveHealthy: 0,
    lastFailureAtMs: 0,
    lastHealthyAtMs: 0,
    lastChangedAtMs: 0,
    nextProbeAtMs: 0,
    circuitOpenUntilMs: 0,
  };
}

function normalizeOrbRuntimeHealth(state = {}) {
  const next = {
    ...buildDefaultOrbRuntimeHealth(),
    ...(state && typeof state === "object" ? state : {}),
  };
  next.status = ["nominal", "degraded", "disconnected", "recovering"].includes(String(next.status || "").trim().toLowerCase())
    ? String(next.status).trim().toLowerCase()
    : "nominal";
  next.source = cleanText(next.source, "hud");
  next.summary = cleanText(next.summary, "Local operator runtime is nominal.");
  next.detail = cleanText(next.detail, next.summary);
  next.failureCount = Math.max(0, Number(next.failureCount || 0));
  next.consecutiveHealthy = Math.max(0, Number(next.consecutiveHealthy || 0));
  next.lastFailureAtMs = Math.max(0, Number(next.lastFailureAtMs || 0));
  next.lastHealthyAtMs = Math.max(0, Number(next.lastHealthyAtMs || 0));
  next.lastChangedAtMs = Math.max(0, Number(next.lastChangedAtMs || 0));
  next.nextProbeAtMs = Math.max(0, Number(next.nextProbeAtMs || 0));
  next.circuitOpenUntilMs = Math.max(0, Number(next.circuitOpenUntilMs || 0));
  return next;
}

function escalateOrbRuntimeFailure(state = {}, { reason = "", source = "hud", nowMs = Date.now() } = {}) {
  const current = normalizeOrbRuntimeHealth(state);
  const failureCount = current.failureCount + 1;
  const status = failureCount >= FAILURE_DISCONNECTED_THRESHOLD ? "disconnected" : "degraded";
  const summary = status === "disconnected"
    ? "Local operator runtime is disconnected."
    : "Local operator runtime is degraded.";
  const detail = sanitizeRuntimeHealthDetail(
    reason,
    status === "disconnected"
      ? "Fresh local runtime proofs are missing. Francis is holding a disconnected local posture while retries back off."
      : "Fresh local runtime proofs are missing. Francis is holding a degraded local posture while retries back off.",
  );
  const nextProbeAtMs = nowMs + getOrbRuntimeRetryDelayMs(failureCount);
  const circuitOpenUntilMs = failureCount >= FAILURE_CIRCUIT_THRESHOLD
    ? nowMs + FAILURE_CIRCUIT_HOLD_MS
    : Math.max(0, Number(current.circuitOpenUntilMs || 0));
  return normalizeOrbRuntimeHealth({
    ...current,
    status,
    source,
    summary,
    detail,
    failureCount,
    consecutiveHealthy: 0,
    lastFailureAtMs: nowMs,
    lastChangedAtMs: nowMs,
    nextProbeAtMs,
    circuitOpenUntilMs,
  });
}

function startOrbRuntimeRecovery(state = {}, { reason = "", source = "hud", nowMs = Date.now() } = {}) {
  const current = normalizeOrbRuntimeHealth(state);
  return normalizeOrbRuntimeHealth({
    ...current,
    status: "recovering",
    source,
    summary: "Local operator runtime is recovering.",
    detail: sanitizeRuntimeHealthDetail(reason, "Fresh healthy proofs are being gathered before Francis trusts the runtime again."),
    consecutiveHealthy: 0,
    lastChangedAtMs: nowMs,
  });
}

function recordOrbRuntimeHealthy(state = {}, { reason = "", source = "hud", nowMs = Date.now() } = {}) {
  const current = normalizeOrbRuntimeHealth(state);
  if (current.status === "nominal" && current.failureCount === 0) {
    return normalizeOrbRuntimeHealth({
      ...current,
      source,
      summary: "Local operator runtime is nominal.",
      detail: cleanText(reason, "Local operator runtime is nominal."),
      lastHealthyAtMs: nowMs,
      lastChangedAtMs: nowMs,
    });
  }

  const consecutiveHealthy = current.consecutiveHealthy + 1;
  if (consecutiveHealthy >= RECOVERY_SUCCESS_THRESHOLD) {
    return normalizeOrbRuntimeHealth({
      ...current,
      status: "nominal",
      source,
      summary: "Local operator runtime is nominal.",
      detail: cleanText(reason, "Runtime health has been re-established with consecutive healthy proofs."),
      failureCount: 0,
      consecutiveHealthy,
      lastHealthyAtMs: nowMs,
      lastChangedAtMs: nowMs,
      nextProbeAtMs: 0,
      circuitOpenUntilMs: 0,
    });
  }

  return normalizeOrbRuntimeHealth({
    ...current,
    status: "recovering",
    source,
    summary: "Local operator runtime is recovering.",
    detail: cleanText(reason, "Recovery is in progress while Francis waits for consecutive healthy proofs."),
    consecutiveHealthy,
    lastHealthyAtMs: nowMs,
    lastChangedAtMs: nowMs,
    nextProbeAtMs: 0,
    circuitOpenUntilMs: 0,
  });
}

module.exports = {
  FAILURE_DEGRADED_THRESHOLD,
  FAILURE_DISCONNECTED_THRESHOLD,
  FAILURE_CIRCUIT_THRESHOLD,
  RECOVERY_SUCCESS_THRESHOLD,
  FAILURE_BACKOFF_BASE_MS,
  FAILURE_BACKOFF_MAX_MS,
  FAILURE_CIRCUIT_HOLD_MS,
  buildDefaultOrbRuntimeHealth,
  getOrbRuntimeRetryDelayMs,
  isOrbRuntimeProbeDeferred,
  normalizeOrbRuntimeHealth,
  escalateOrbRuntimeFailure,
  startOrbRuntimeRecovery,
  recordOrbRuntimeHealthy,
};
