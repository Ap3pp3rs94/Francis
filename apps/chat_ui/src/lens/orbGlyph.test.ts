import assert from "node:assert/strict";
import test from "node:test";

import { parseLensMcpStatus } from "./mcpStatus.ts";
import { bodyStateReady, presentOrbGlyph } from "./orbGlyph.ts";

// These tests cover the pure Orb glyph presenter that drives the inline SVG in
// the Chat UI BodyStatePanel. The node:test harness does not render React, so
// they assert the state-driving descriptor (tone/posture/read-only/authority),
// not DOM presence. App.tsx renders the SVG directly from this descriptor.

const READY_STATUS = parseLensMcpStatus({
  ok: true,
  status: "ready",
  embodied_posture: "takeover_ready",
  resident: false,
  blockers: [],
  mcp: { expected_tool_count: 18, tool_count: 18, missing_tools: [], missing_required_tools: [] },
  routes: { mcp_status: "/lens/mcp/status", orb_mcp_status: "/lens/orb/mcp-status" },
  governance: { read_only: true, grants_execution_authority: false, grants_mutation_authority: false },
  components: {},
});

test("presentOrbGlyph derives a ready cue from truthful ready body-state", () => {
  const orb = presentOrbGlyph(READY_STATUS, false);

  assert.equal(orb.tone, "ready");
  assert.equal(orb.ready, true);
  assert.equal(orb.posture, "takeover_ready");
  assert.equal(orb.status, "ready");
  // Dark black-chrome core and smoky white/silver rings are constant; the state
  // cue lives in glow + intensity.
  assert.equal(orb.coreColor, "#0b1220");
  assert.equal(orb.ringColor, "#dbe4f0");
  assert.equal(orb.glowColor, "#eaf2ff");
  assert.ok(orb.intensity > 0.55);
});

test("presentOrbGlyph signals attention on blockers or degraded posture", () => {
  const blocked = parseLensMcpStatus({
    status: "ready",
    embodied_posture: "takeover_ready",
    blockers: ["resident_overlay_runtime_missing"],
    mcp: { expected_tool_count: 18, tool_count: 18, missing_tools: [], missing_required_tools: [] },
    governance: { read_only: true },
  });
  const blockedOrb = presentOrbGlyph(blocked, false);
  assert.equal(blockedOrb.ready, false);
  assert.equal(blockedOrb.tone, "attention");
  assert.equal(blockedOrb.glowColor, "#fbe9cf");

  const degraded = parseLensMcpStatus({
    status: "ready",
    embodied_posture: "degraded",
    blockers: [],
    mcp: { expected_tool_count: 18, tool_count: 18, missing_tools: [], missing_required_tools: [] },
    governance: { read_only: true },
  });
  assert.equal(presentOrbGlyph(degraded, false).tone, "attention");
});

test("presentOrbGlyph rests at idle while loading or without data", () => {
  const loadingOrb = presentOrbGlyph(null, true);
  assert.equal(loadingOrb.tone, "idle");
  assert.equal(loadingOrb.posture, "unknown");
  assert.equal(loadingOrb.status, "unknown");

  const noDataOrb = presentOrbGlyph(null, false);
  assert.equal(noDataOrb.tone, "idle");

  // A ready status that is still loading should not yet claim a ready cue.
  assert.equal(presentOrbGlyph(READY_STATUS, true).tone, "idle");
  assert.ok(loadingOrb.intensity < presentOrbGlyph(READY_STATUS, false).intensity);
});

test("presentOrbGlyph reflects takeover_active posture without granting authority", () => {
  const active = parseLensMcpStatus({
    status: "ready",
    embodied_posture: "takeover_active",
    blockers: [],
    mcp: { expected_tool_count: 18, tool_count: 18, missing_tools: [], missing_required_tools: [] },
    governance: { read_only: true, grants_execution_authority: false, grants_mutation_authority: false },
  });
  const orb = presentOrbGlyph(active, false);
  assert.equal(orb.tone, "active");
  assert.equal(orb.intensity, 1);
  assert.equal(orb.grantsExecutionAuthority, false);
  assert.equal(orb.grantsMutationAuthority, false);
});

test("presentOrbGlyph never claims execution or mutation authority and stays read-only", () => {
  const readyOrb = presentOrbGlyph(READY_STATUS, false);
  assert.equal(readyOrb.readOnly, true);
  assert.equal(readyOrb.grantsExecutionAuthority, false);
  assert.equal(readyOrb.grantsMutationAuthority, false);
  assert.match(readyOrb.label, /read-only/);

  // Missing governance must still default to no granted authority.
  const sparse = parseLensMcpStatus({
    status: "attention",
    embodied_posture: "read_only",
    blockers: ["x"],
    mcp: { expected_tool_count: 18, tool_count: 18, missing_tools: [], missing_required_tools: [] },
  });
  const sparseOrb = presentOrbGlyph(sparse, false);
  assert.equal(sparseOrb.grantsExecutionAuthority, false);
  assert.equal(sparseOrb.grantsMutationAuthority, false);

  // Even with no fetched data the surface remains read-only by contract.
  assert.equal(presentOrbGlyph(null, false).readOnly, true);
});

test("bodyStateReady matches the BodyStatePanel readiness predicate", () => {
  assert.equal(bodyStateReady(READY_STATUS), true);
  assert.equal(bodyStateReady(null), false);

  const missingTools = parseLensMcpStatus({
    status: "ready",
    blockers: [],
    mcp: { expected_tool_count: 18, tool_count: 17, missing_tools: ["francis.input.status"], missing_required_tools: [] },
  });
  assert.equal(bodyStateReady(missingTools), false);

  const notReady = parseLensMcpStatus({
    status: "attention",
    blockers: [],
    mcp: { expected_tool_count: 18, tool_count: 18, missing_tools: [], missing_required_tools: [] },
  });
  assert.equal(bodyStateReady(notReady), false);
});

test("presentOrbGlyph performs no network I/O (calls no new route)", () => {
  const globals = globalThis as typeof globalThis & { fetch?: typeof fetch };
  const originalFetch = globals.fetch;
  let calls = 0;
  globals.fetch = (async () => {
    calls += 1;
    throw new Error("presentOrbGlyph must not perform network I/O");
  }) as typeof fetch;

  try {
    presentOrbGlyph(READY_STATUS, false);
    presentOrbGlyph(null, true);
    bodyStateReady(READY_STATUS);
    assert.equal(calls, 0);
  } finally {
    if (originalFetch) {
      globals.fetch = originalFetch;
    } else {
      delete globals.fetch;
    }
  }
});
