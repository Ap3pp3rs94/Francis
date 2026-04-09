(function (globalScope, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  globalScope.FrancisOrbSurfaceState = factory();
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  const BODY_LABELS = Object.freeze({
    idle_anchored: "Idle",
    attentive: "Listening",
    investigate: "Investigating",
    target_lock: "Locked",
    commit_move: "Moving",
    hover_ready: "Ready",
    click_act: "Clicking",
    drag_act: "Dragging",
    type_hold: "Typing",
    waiting_user: "Waiting for approval",
    blocked: "Blocked",
    interrupted: "Interrupted",
    degraded: "Degraded",
    paused: "Paused",
  });

  const BODY_ALIASES = Object.freeze({
    waiting_for_user: "waiting_user",
    blocked_uncertain: "blocked",
    abort_interrupted: "interrupted",
  });

  function titleCase(value) {
    return String(value || "")
      .replaceAll("_", " ")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function cleanText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function normalizeBodyState(value) {
    const normalized = cleanText(value).toLowerCase();
    return BODY_ALIASES[normalized] || normalized || "idle_anchored";
  }

  function normalizePolicyProfile(value) {
    const raw = value && typeof value === "object" ? value : {};
    const state = cleanText(raw.state).toLowerCase();
    return {
      state,
      scope: cleanText(raw.scope).toLowerCase() || "observation",
      summary: cleanText(raw.summary),
      detail: cleanText(raw.detail),
      modeLabel: cleanText(raw.mode_label || raw.modeLabel),
      authorityLabel: cleanText(raw.authority_label || raw.authorityLabel),
      approvalRequired: Boolean(raw.approval_required || state === "approval_required"),
      blocked: Boolean(raw.blocked || state === "policy_blocked"),
    };
  }

  function compressStatusMessage(value, fallback = "Francis is ready.") {
    const message = cleanText(value);
    if (!message) {
      return fallback;
    }
    const lowered = message.toLowerCase();
    if (
      lowered.includes("failed to fetch")
      || lowered.includes("fetch failed")
      || lowered.includes("networkerror")
      || lowered.includes("network request failed")
    ) {
      return "Disconnected from the local operator stack.";
    }
    if (lowered.startsWith("panic stop failed")) {
      return "Panic stop degraded.";
    }
    if (lowered.startsWith("panic stop is unavailable")) {
      return "Panic stop unavailable.";
    }
    if (lowered.startsWith("orb execution failed")) {
      return "Desktop action failed.";
    }
    if (lowered.startsWith("orb chat failed")) {
      return "Conversation failed.";
    }
    if (lowered.includes("queue failed")) {
      return "Action queue failed.";
    }
    if (lowered.includes("continuity failed")) {
      return "Continuity sync failed.";
    }
    return message;
  }

  function compactSurfaceLine(value, fallback = "") {
    const message = cleanText(value);
    if (!message) {
      return fallback;
    }
    const firstSegment = message.split("|").map((part) => cleanText(part)).find(Boolean) || message;
    const firstSentence = firstSegment.split(/(?<=[.!?])\s+/).find(Boolean) || firstSegment;
    if (firstSentence.length <= 92) {
      return firstSentence;
    }
    const clipped = firstSentence.slice(0, 89).replace(/[,:;.!?\s-]+[^,:;.!?\s-]*$/, "").trim();
    return `${clipped || firstSentence.slice(0, 89).trim()}...`;
  }

  function deriveModeLabel({ localPanic, cursorAuthority, waitingForUser, cursorEligibility, pending, policy }) {
    if (localPanic?.engaged) {
      return "Stopped";
    }
    if (policy?.modeLabel && (policy.approvalRequired || policy.blocked || policy.state === "observe_only")) {
      return policy.modeLabel;
    }
    if (cursorAuthority) {
      return "Act";
    }
    if (waitingForUser || cursorEligibility || pending) {
      return "Assist";
    }
    return "Observe";
  }

  function deriveAuthorityLabel({ localPanic, cursorAuthority, waitingForUser, cursorEligibility, policy }) {
    if (localPanic?.engaged) {
      return "Local stop";
    }
    if (policy?.authorityLabel && (policy.approvalRequired || policy.blocked || policy.state === "observe_only")) {
      return policy.authorityLabel;
    }
    if (cursorAuthority) {
      return "Cursor live";
    }
    if (waitingForUser) {
      return "Approval gate";
    }
    if (cursorEligibility) {
      return "Cursor armed";
    }
    return "Observe only";
  }

  function deriveHealthLabel({ degraded, disconnected }) {
    if (disconnected) {
      return "Disconnected";
    }
    if (degraded) {
      return "Degraded";
    }
    return "";
  }

  function deriveTargetLabel({ targetCue, taskbarIntent, bodyState }) {
    const cue = targetCue && typeof targetCue === "object" ? targetCue : {};
    const primaryAction = cleanText(cue.primary_action_label);
    const zoneLabel = cleanText(cue.zone_label);
    const targetLabel = cleanText(cue.target_label);
    if (primaryAction) {
      return `Target: ${primaryAction}`;
    }
    if (taskbarIntent) {
      return "Target: taskbar";
    }
    if (zoneLabel) {
      return `Target: ${zoneLabel}`;
    }
    if (targetLabel) {
      return `Target: ${targetLabel}`;
    }
    if (
      bodyState === "idle_anchored"
      || bodyState === "attentive"
      || bodyState === "waiting_user"
      || bodyState === "blocked"
      || bodyState === "interrupted"
      || bodyState === "degraded"
      || bodyState === "paused"
    ) {
      return "Target: none";
    }
    return "Target: resolving";
  }

  function deriveDetailLabel({
    localPanic,
    bodyState,
    authority,
    ownership,
    policy,
    targetCue,
    statusMessage,
    summary,
    blocked,
    waitingForUser,
    paused,
    degraded,
    disconnected,
    degradedSummary,
  }) {
    const cueAttentionSummary = cleanText(targetCue?.attention_summary);
    const cueAttentionDetail = cleanText(targetCue?.attention_detail);
    const executionSummary = cleanText(authority?.executionSummary || authority?.execution?.summary);
    const executionDetail = cleanText(authority?.executionDetail || authority?.execution?.detail);
    if (localPanic?.engaged) {
      return compactSurfaceLine(localPanic.detail || localPanic.summary || "Local authority dropped.");
    }
    if (disconnected) {
      return compactSurfaceLine(degradedSummary || statusMessage || summary || "Disconnected from the local operator stack.");
    }
    if (degraded) {
      return compactSurfaceLine(degradedSummary || statusMessage || summary || "The local operator stack is degraded.");
    }
    if (policy?.approvalRequired) {
      return compactSurfaceLine(policy.detail || policy.summary || "Waiting for approval.");
    }
    if (policy?.blocked) {
      return compactSurfaceLine(policy.detail || policy.summary || "Blocked by policy.");
    }
    if (waitingForUser) {
      return "Waiting for your approval.";
    }
    if (paused) {
      return "Paused locally and holding position.";
    }
    if (ownership?.userOverrideActive) {
      return compactSurfaceLine(ownership.summary || "You have control. Francis yielded input.");
    }
    if (
      ownership?.passThrough
      && !ownership?.restricted
      && !waitingForUser
      && !blocked
      && bodyState !== "commit_move"
      && bodyState !== "click_act"
      && bodyState !== "drag_act"
      && bodyState !== "type_hold"
    ) {
      return compactSurfaceLine(ownership.summary || "Orb input is passing through to the desktop.");
    }
    if (blocked) {
      return compactSurfaceLine(cueAttentionDetail || cueAttentionSummary || "Blocked: target changed or confidence dropped.");
    }
    if (
      executionSummary
      && (
        bodyState === "commit_move"
        || bodyState === "hover_ready"
        || bodyState === "click_act"
        || bodyState === "drag_act"
        || bodyState === "type_hold"
        || bodyState === "interrupted"
      )
    ) {
      return compactSurfaceLine(executionDetail || executionSummary, executionSummary);
    }
    const cueSummary = cueAttentionSummary || cleanText(targetCue?.summary);
    if (bodyState === "idle_anchored") {
      return "Perched nearby and out of the way.";
    }
    if (bodyState === "attentive") {
      return "Watching the current workspace closely.";
    }
    if (
      cueAttentionSummary
      && (bodyState === "investigate" || bodyState === "target_lock" || bodyState === "hover_ready")
    ) {
      return compactSurfaceLine(cueAttentionSummary);
    }
    if (cueSummary) {
      return compactSurfaceLine(cueSummary);
    }
    return compactSurfaceLine(
      compressStatusMessage(statusMessage || summary, "Francis is ready."),
      "Francis is ready.",
    );
  }

  function deriveOrbSurfaceState(context = {}) {
    const bodyState = normalizeBodyState(context.bodyState);
    const authority = context.authority && typeof context.authority === "object" ? context.authority : null;
    const ownership = context.ownership && typeof context.ownership === "object" ? context.ownership : null;
    const policy = normalizePolicyProfile(context.policy);
    const runtimeHealth = context.runtimeHealth && typeof context.runtimeHealth === "object" ? context.runtimeHealth : null;
    const runtimeStatus = String(runtimeHealth?.status || "nominal").trim().toLowerCase() || "nominal";
    const localPanic = authority?.localStopped
      ? {
          engaged: true,
          detail: cleanText(authority.detail || context.localPanic?.detail || "Local authority dropped."),
          remoteSynced: authority.remoteSyncStatus === "current",
        }
      : context.localPanic && typeof context.localPanic === "object"
        ? context.localPanic
        : null;
    const waitingForUser = Boolean(context.waitingForUser || bodyState === "waiting_user" || policy.approvalRequired);
    const blocked = Boolean(context.blocked || bodyState === "blocked" || policy.blocked);
    const cursorAuthority = typeof authority?.cursorLive === "boolean"
      ? authority.cursorLive
      : Boolean(context.cursorAuthority);
    const cursorEligibility = typeof authority?.cursorArmed === "boolean"
      ? authority.cursorArmed
      : Boolean(context.cursorEligibility);
    const disconnected = runtimeStatus === "disconnected"
      ? true
      : typeof authority?.disconnected === "boolean"
        ? authority.disconnected
        : Boolean(context.disconnected);
    const recovering = runtimeStatus === "recovering";
    const degraded = bodyState === "degraded" || runtimeStatus === "degraded" || recovering || (typeof authority?.degraded === "boolean"
      ? authority.degraded || disconnected
      : Boolean(context.degraded || disconnected));
    const paused = Boolean(authority?.pauseHeld || bodyState === "paused") && !localPanic?.engaged && !disconnected;
    const controlsRestricted = Boolean(
      ownership?.restricted
        || (ownership?.safeFallback && !ownership?.lensInteractive),
    );
    const degradedSummary = cleanText(context.degradedSummary);
    const stateLabel = localPanic?.engaged
      ? "Panic stopped"
      : disconnected
        ? "Disconnected"
        : recovering
          ? "Recovering"
        : paused
          ? "Paused"
        : policy.approvalRequired
          ? "Waiting approval"
        : policy.blocked
          ? "Blocked"
        : degraded
          ? "Degraded"
          : BODY_LABELS[bodyState] || titleCase(bodyState) || "Idle";
    const targetConfidence = String(context.targetConfidence || "low").trim().toLowerCase() || "low";
    const policyModeLabel = cleanText(policy?.modeLabel);
    const policyAuthorityLabel = cleanText(policy?.authorityLabel);
    const modeLabel = (!localPanic?.engaged && !disconnected && !recovering && !degraded && policyModeLabel && (policy.approvalRequired || policy.blocked || policy.state === "observe_only"))
      ? policyModeLabel
      : cleanText(ownership?.modeLabel) || cleanText(authority?.modeLabel) || deriveModeLabel({
      localPanic,
      cursorAuthority,
      waitingForUser,
      cursorEligibility,
      pending: Boolean(context.pending),
      policy,
    });
    const authorityLabel = (!localPanic?.engaged && !disconnected && !recovering && !degraded && policyAuthorityLabel && (policy.approvalRequired || policy.blocked || policy.state === "observe_only"))
      ? policyAuthorityLabel
      : cleanText(ownership?.authorityLabel) || cleanText(authority?.authorityLabel) || (disconnected
      ? "Disconnected"
      : paused
        ? authority?.remoteSyncStatus === "failed"
          ? "Queue clear failed"
          : "Paused locally"
        : recovering
          ? "Recovery hold"
        : deriveAuthorityLabel({
            localPanic,
            cursorAuthority,
            waitingForUser,
            cursorEligibility,
            policy,
          }));
    const runtimeHealthLine = compactSurfaceLine(
      runtimeHealth?.detail || runtimeHealth?.summary,
      runtimeHealth?.summary || "",
    );
    const detailLabel = runtimeStatus !== "nominal" && runtimeHealthLine
      ? runtimeHealthLine
      : authority?.detail && (localPanic?.engaged || paused || disconnected || degraded)
      ? compactSurfaceLine(authority.detail, cleanText(authority.detail))
      : deriveDetailLabel({
          localPanic,
          bodyState,
          authority,
          ownership,
          policy,
          targetCue: context.targetCue,
          statusMessage: context.statusMessage || authority?.summary,
          summary: context.summary || authority?.summary,
          blocked,
          waitingForUser,
          paused,
          degraded,
          disconnected,
          degradedSummary,
        });
    const diagnosticsSummary = localPanic?.engaged
      ? authority?.remoteSyncStatus === "failed"
      ? "Remote sync failed"
      : authority?.remoteSyncStatus === "pending" || localPanic.remoteSynced === false
          ? "Remote sync pending"
          : "Local stop confirmed"
      : paused
        ? authority?.remoteSyncStatus === "failed"
          ? "Remote queue clear failed"
          : "Remote queue clear pending"
      : recovering
        ? "Recovery in progress"
      : disconnected
        ? "Local operator stack unreachable"
      : ownership?.userOverrideActive
        ? "Human override active"
      : degraded
        ? cleanText(runtimeHealth?.summary || authority?.summary || "Runtime degraded")
      : policy.approvalRequired
        ? "Policy hold"
      : policy.blocked
        ? "Policy blocked"
      : blocked
        ? "Reassessing target"
      : "";
    return {
      stateLabel,
      detailLabel,
      modeLabel,
      authorityLabel,
      targetLabel: deriveTargetLabel({
        targetCue: runtimeStatus === "nominal" ? context.targetCue : null,
        taskbarIntent: Boolean(context.taskbarIntent),
        bodyState: runtimeStatus === "nominal" ? bodyState : "idle_anchored",
      }),
      confidenceLabel: runtimeStatus === "nominal"
        ? targetConfidence === "low" ? "Low confidence" : `${titleCase(targetConfidence)} confidence`
        : "Low confidence",
      approvalNeeded: waitingForUser,
      approvalLabel: waitingForUser ? (policy.approvalRequired ? "Policy hold" : "Approval needed") : "",
      approvalDetail: waitingForUser ? compactSurfaceLine(policy.detail || "Waiting for your approval.") : "",
      policyBlocked: policy.blocked,
      policyState: policy.state,
      healthDegraded: degraded,
      healthLabel: disconnected ? "Disconnected" : recovering ? "Recovering" : deriveHealthLabel({ degraded, disconnected }),
      diagnosticsSummary,
      stopped: Boolean(localPanic?.engaged),
      canStop: controlsRestricted ? false : typeof authority?.canStop === "boolean" ? authority.canStop : !localPanic?.engaged,
      canPause: controlsRestricted ? false : recovering || disconnected ? false : typeof authority?.canPause === "boolean" ? authority.canPause : !cursorAuthority,
      pauseLabel: paused ? "Paused" : cursorAuthority ? "Use Stop" : recovering ? "Recovery" : "Pause",
      controlsRestricted,
      tone: localPanic?.engaged
        ? "stopped"
        : degraded
          ? "blocked"
        : blocked
          ? "blocked"
          : waitingForUser
            ? "waiting"
            : cursorAuthority
              ? "active"
              : "idle",
    };
  }

  return {
    BODY_LABELS,
    compressStatusMessage,
    deriveOrbSurfaceState,
  };
});
