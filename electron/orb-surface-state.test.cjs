const test = require("node:test");
const assert = require("node:assert/strict");

const {
  compressStatusMessage,
  deriveOrbSurfaceState,
} = require("../services/hud/app/static/orb/orb-surface-state.js");

test("compressStatusMessage removes raw transport noise from the operator surface", () => {
  assert.equal(
    compressStatusMessage("Orb chat failed: Failed to fetch"),
    "Disconnected from the local operator stack.",
  );
  assert.equal(
    compressStatusMessage("Panic stop failed: fetch failed"),
    "Disconnected from the local operator stack.",
  );
});

test("deriveOrbSurfaceState keeps idle posture compact and observant", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "idle_anchored",
    cursorAuthority: false,
    cursorEligibility: false,
    statusMessage: "Francis is ready.",
  });
  assert.equal(surface.stateLabel, "Idle");
  assert.equal(surface.modeLabel, "Observe");
  assert.equal(surface.authorityLabel, "Observe only");
  assert.equal(surface.targetLabel, "Target: none");
});

test("deriveOrbSurfaceState keeps lock state concise for the compact orb strip", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "target_lock",
    cursorAuthority: false,
    cursorEligibility: true,
    targetCue: {
      primary_action_label: "Pinned terminal",
      attention_summary: "Locked on pinned terminal.",
      summary: "Pinned terminal | Francis is holding a grounded click line on the terminal tab.",
    },
  });

  assert.equal(surface.stateLabel, "Locked");
  assert.equal(surface.detailLabel, "Locked on pinned terminal.");
  assert.equal(surface.targetLabel, "Target: Pinned terminal");
});

test("deriveOrbSurfaceState uses reassessment attention copy without turning the strip into diagnostics", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "blocked",
    blocked: true,
    targetCue: {
      target_label: "Editor focus point",
      attention_summary: "Reassessing editor focus point.",
      attention_detail: "Francis is easing off editor focus point until confidence settles again.",
    },
  });

  assert.equal(surface.stateLabel, "Blocked");
  assert.equal(surface.detailLabel, "Francis is easing off editor focus point until confidence settles again.");
  assert.equal(surface.targetLabel, "Target: Editor focus point");
});

test("deriveOrbSurfaceState elevates approval pressure without pretending to act", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "waiting_user",
    waitingForUser: true,
    cursorAuthority: false,
    cursorEligibility: true,
    policy: {
      state: "approval_required",
      summary: "Waiting approval",
      detail: "Repo test execution is held at the policy boundary until you approve.",
      mode_label: "Assist",
      authority_label: "Policy hold",
    },
    targetCue: { primary_action_label: "Approve + Run" },
  });
  assert.equal(surface.stateLabel, "Waiting approval");
  assert.equal(surface.modeLabel, "Assist");
  assert.equal(surface.authorityLabel, "Policy hold");
  assert.equal(surface.approvalNeeded, true);
  assert.equal(surface.approvalLabel, "Policy hold");
  assert.equal(surface.approvalDetail, "Repo test execution is held at the policy boundary until you approve.");
  assert.equal(surface.targetLabel, "Target: Approve + Run");
});

test("deriveOrbSurfaceState distinguishes policy blocked posture from reassessment blocked posture", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "blocked",
    blocked: true,
    policy: {
      state: "policy_blocked",
      summary: "Blocked by policy",
      detail: "Cross-app click is outside the current governed boundary.",
      mode_label: "Assist",
      authority_label: "Policy blocked",
      blocked: true,
    },
    targetCue: {
      primary_action_label: "Production control",
    },
  });

  assert.equal(surface.stateLabel, "Blocked");
  assert.equal(surface.modeLabel, "Assist");
  assert.equal(surface.authorityLabel, "Policy blocked");
  assert.equal(surface.detailLabel, "Cross-app click is outside the current governed boundary.");
  assert.equal(surface.diagnosticsSummary, "Policy blocked");
  assert.equal(surface.policyBlocked, true);
});

test("deriveOrbSurfaceState accepts legacy body aliases but reports canonical labels", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "abort_interrupted",
    cursorAuthority: false,
  });

  assert.equal(surface.stateLabel, "Interrupted");
});

test("deriveOrbSurfaceState reports live action and taskbar intent clearly", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "commit_move",
    cursorAuthority: true,
    cursorEligibility: true,
    taskbarIntent: true,
    targetConfidence: "high",
  });
  assert.equal(surface.stateLabel, "Moving");
  assert.equal(surface.modeLabel, "Act");
  assert.equal(surface.authorityLabel, "Cursor live");
  assert.equal(surface.targetLabel, "Target: taskbar");
  assert.equal(surface.confidenceLabel, "High confidence");
});

test("deriveOrbSurfaceState prefers canonical execution detail for active execution posture", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "drag_act",
    authority: {
      cursorLive: true,
      executionSummary: "Anchored drag control is live.",
      executionDetail: "Francis is maintaining anchored contact and tension across the drag path.",
    },
    cursorAuthority: true,
    cursorEligibility: true,
  });

  assert.equal(surface.stateLabel, "Dragging");
  assert.equal(surface.detailLabel, "Francis is maintaining anchored contact and tension across the drag path.");
  assert.equal(surface.modeLabel, "Act");
});

test("deriveOrbSurfaceState lets local panic stop override all other runtime text", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "commit_move",
    cursorAuthority: true,
    localPanic: {
      engaged: true,
      detail: "Local authority dropped. Remote sync pending.",
      remoteSynced: false,
    },
  });
  assert.equal(surface.stateLabel, "Panic stopped");
  assert.equal(surface.modeLabel, "Stopped");
  assert.equal(surface.authorityLabel, "Local stop");
  assert.equal(surface.diagnosticsSummary, "Remote sync pending");
});

test("deriveOrbSurfaceState surfaces disconnected degraded posture cleanly", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "idle_anchored",
    disconnected: true,
    degraded: true,
    degradedSummary: "HUD disconnected.",
    statusMessage: "Failed to fetch",
  });
  assert.equal(surface.stateLabel, "Disconnected");
  assert.equal(surface.healthDegraded, true);
  assert.equal(surface.healthLabel, "Disconnected");
  assert.equal(surface.detailLabel, "HUD disconnected.");
  assert.equal(surface.diagnosticsSummary, "Local operator stack unreachable");
});

test("deriveOrbSurfaceState compacts long degraded detail for the orb strip", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "commit_move",
    degraded: true,
    degradedSummary: "HUD disconnected. Waiting for the local operator stack to recover before Francis trusts actuation again. Longer diagnostics belong in Lens.",
  });

  assert.equal(surface.stateLabel, "Degraded");
  assert.equal(surface.detailLabel, "HUD disconnected.");
});

test("deriveOrbSurfaceState prefers canonical authority truth when local stop is engaged", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "commit_move",
    authority: {
      localStopped: true,
      remoteSyncStatus: "failed",
      modeLabel: "Stopped",
      authorityLabel: "Local stop",
      detail: "Francis dropped local authority immediately.",
      canStop: false,
      canPause: false,
    },
  });

  assert.equal(surface.stateLabel, "Panic stopped");
  assert.equal(surface.authorityLabel, "Local stop");
  assert.equal(surface.canStop, false);
  assert.equal(surface.canPause, false);
  assert.equal(surface.diagnosticsSummary, "Remote sync failed");
});

test("deriveOrbSurfaceState does not show false cursor live labels after authority loss", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "commit_move",
    cursorAuthority: true,
    authority: {
      cursorLive: false,
      cursorArmed: false,
      disconnected: true,
      degraded: true,
      canStop: true,
      canPause: false,
      detail: "HUD disconnected. Human control remains primary.",
    },
  });

  assert.equal(surface.stateLabel, "Disconnected");
  assert.equal(surface.authorityLabel, "Disconnected");
  assert.equal(surface.pauseLabel, "Pause");
  assert.equal(surface.canPause, false);
});

test("deriveOrbSurfaceState shows recovering posture from canonical runtime health", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "commit_move",
    runtimeHealth: {
      status: "recovering",
      summary: "Local operator runtime is recovering.",
      detail: "Waiting for consecutive healthy proofs before Francis trusts the runtime again.",
    },
    authority: {
      cursorLive: false,
      cursorArmed: false,
      canStop: true,
      canPause: false,
    },
    targetCue: { primary_action_label: "Pinned terminal" },
    targetConfidence: "high",
  });

  assert.equal(surface.stateLabel, "Recovering");
  assert.equal(surface.healthLabel, "Recovering");
  assert.equal(surface.diagnosticsSummary, "Recovery in progress");
  assert.equal(surface.targetLabel, "Target: none");
  assert.equal(surface.confidenceLabel, "Low confidence");
  assert.equal(surface.canPause, false);
  assert.equal(surface.pauseLabel, "Recovery");
});

test("deriveOrbSurfaceState treats paused body posture as a first-class compact state", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "paused",
    authority: {
      pauseHeld: true,
      cursorLive: false,
      cursorArmed: true,
      canStop: true,
      canPause: true,
    },
  });

  assert.equal(surface.stateLabel, "Paused");
  assert.equal(surface.authorityLabel, "Paused locally");
  assert.equal(surface.detailLabel, "Paused locally and holding position.");
  assert.equal(surface.pauseLabel, "Paused");
});

test("deriveOrbSurfaceState treats degraded body posture as a first-class compact state", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "degraded",
    degradedSummary: "HUD disconnected.",
  });

  assert.equal(surface.stateLabel, "Degraded");
  assert.equal(surface.healthLabel, "Degraded");
  assert.equal(surface.detailLabel, "HUD disconnected.");
});

test("deriveOrbSurfaceState keeps strip controls truthful when ownership is in safe fallback", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "idle_anchored",
    authority: {
      cursorLive: false,
      cursorArmed: true,
      canStop: true,
      canPause: true,
    },
    ownership: {
      state: "restricted",
      safeFallback: true,
      restricted: true,
      lensInteractive: false,
    },
    runtimeHealth: {
      status: "degraded",
      summary: "Local operator runtime is degraded.",
      detail: "Francis is holding safe pass-through until stability returns.",
    },
  });

  assert.equal(surface.healthLabel, "Degraded");
  assert.equal(surface.canStop, false);
  assert.equal(surface.canPause, false);
  assert.equal(surface.controlsRestricted, true);
});

test("deriveOrbSurfaceState shows user override without losing the underlying assist posture", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "idle_anchored",
    authority: {
      modeLabel: "Assist",
      authorityLabel: "Cursor armed",
      cursorLive: false,
      cursorArmed: true,
      canStop: true,
      canPause: true,
    },
    ownership: {
      state: "pass_through",
      passThrough: true,
      restricted: false,
      safeFallback: false,
      lensInteractive: false,
      userOverrideActive: true,
      modeLabel: "Assist",
      authorityLabel: "User override",
      summary: "User override is active. Francis yielded orb input.",
    },
  });

  assert.equal(surface.modeLabel, "Assist");
  assert.equal(surface.authorityLabel, "User override");
  assert.equal(surface.detailLabel, "User override is active.");
  assert.equal(surface.diagnosticsSummary, "Human override active");
});

test("deriveOrbSurfaceState keeps nominal pass-through concise when Francis is yielding input", () => {
  const surface = deriveOrbSurfaceState({
    bodyState: "idle_anchored",
    authority: {
      modeLabel: "Observe",
      authorityLabel: "Observe only",
      cursorLive: false,
      cursorArmed: false,
    },
    ownership: {
      state: "pass_through",
      passThrough: true,
      restricted: false,
      safeFallback: false,
      lensInteractive: false,
      modeLabel: "Observe",
      authorityLabel: "Pass-through",
      summary: "Orb input is passing through to the desktop.",
    },
  });

  assert.equal(surface.modeLabel, "Observe");
  assert.equal(surface.authorityLabel, "Pass-through");
  assert.equal(surface.detailLabel, "Orb input is passing through to the desktop.");
});
