import assert from "node:assert/strict";
import test from "node:test";

import {
  ApprenticeshipClient,
  parseApprenticeshipLiveTeachingSessionUx,
  parseApprenticeshipStatusSnapshot,
  presentApprenticeshipPanel,
  trimTrailingSlashes,
} from "./index.ts";

type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function installFetch(handler: FetchHandler): () => void {
  const globals = globalThis as typeof globalThis & { fetch?: typeof fetch };
  const originalFetch = globals.fetch;

  globals.fetch = (async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = input instanceof Request ? input.url : input.toString();
    return await handler(url, init);
  }) as typeof fetch;

  return () => {
    if (originalFetch) {
      globals.fetch = originalFetch;
      return;
    }
    delete globals.fetch;
  };
}

test("trimTrailingSlashes uses bounded scanning", () => {
  assert.equal(trimTrailingSlashes("http://127.0.0.1:8000///"), "http://127.0.0.1:8000");
  assert.equal(trimTrailingSlashes("http://127.0.0.1:8000/path"), "http://127.0.0.1:8000/path");
});

test("parseApprenticeshipStatusSnapshot preserves Stage 11 readiness and guards", () => {
  const parsed = parseApprenticeshipStatusSnapshot({
    ok: true,
    kind: "francis.stage11.apprenticeship.status",
    stage: "Stage 11 / Apprenticeship",
    status: "stage11_operator_surface_ready",
    ready_count: 5,
    required_count: 5,
    teaching_session_ready: true,
    replay_generalization_ready: true,
    skillization_ready: true,
    forge_handoff_ready: true,
    live_teaching_session_ux_ready: true,
    deliverables: [
      { id: "teaching_session_ux", label: "Teaching session UX", ready: true },
      { id: "forge_ready_outputs", label: "Forge-ready outputs", ready: true },
    ],
    routes: {
      status: "/apprenticeship/status",
      live_teaching_session_ux: "/apprenticeship/live-teaching-session-ux",
    },
    writes_receipts: false,
    writes_memory: false,
    captures_screen: false,
    captures_audio: false,
    captures_keystrokes: false,
    passive_learning_enabled: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    next_smallest_truthful_gap: "stage11_teaching_session_receipt_write_path",
  });

  assert.equal(parsed.ok, true);
  assert.equal(parsed.status, "stage11_operator_surface_ready");
  assert.equal(parsed.ready_count, 5);
  assert.equal(parsed.required_count, 5);
  assert.equal(parsed.live_teaching_session_ux_ready, true);
  assert.equal(parsed.routes.live_teaching_session_ux, "/apprenticeship/live-teaching-session-ux");
  assert.equal(parsed.writes_memory, false);
  assert.equal(parsed.captures_screen, false);
  assert.equal(parsed.next_smallest_truthful_gap, "stage11_teaching_session_receipt_write_path");
});

test("parseApprenticeshipLiveTeachingSessionUx preserves visible sections and disabled actions", () => {
  const parsed = parseApprenticeshipLiveTeachingSessionUx({
    ok: true,
    kind: "francis.stage11.apprenticeship.live_teaching_session_ux",
    stage: "Stage 11 / Apprenticeship",
    status: "ready",
    surface: "chat_ui.apprenticeship_panel",
    route: "/apprenticeship/live-teaching-session-ux",
    live_teaching_session_ux_ready: true,
    visible_sections: [
      { id: "stage_status", label: "Stage status", visible: true, source_route: "/apprenticeship/status" },
      { id: "capture_boundaries", label: "Capture boundaries", visible: true },
    ],
    visible_section_count: 2,
    operator_actions: [
      { id: "start_teaching_session", label: "Start teaching session", enabled: false },
      { id: "stage_forge_handoff", label: "Stage Forge handoff", enabled: false },
    ],
    operator_action_count: 2,
    denied_modes: ["ambient_capture_start", "forge_promotion_from_ui_surface"],
    writes_receipts: false,
    writes_memory: false,
    writes_skill_artifact: false,
    writes_forge_proposal: false,
    starts_teaching_session: false,
    captures_screen: false,
    captures_audio: false,
    captures_keystrokes: false,
    passive_learning_enabled: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    next_smallest_truthful_gap: "stage11_teaching_session_receipt_write_path",
  });

  assert.equal(parsed.live_teaching_session_ux_ready, true);
  assert.equal(parsed.visible_sections.length, 2);
  assert.equal(parsed.operator_actions.length, 2);
  assert.equal(parsed.operator_actions[0]?.enabled, false);
  assert.equal(parsed.starts_teaching_session, false);
  assert.equal(parsed.writes_forge_proposal, false);
});

test("presentApprenticeshipPanel keeps write and capture guards visible", () => {
  const status = parseApprenticeshipStatusSnapshot({
    ok: true,
    stage: "Stage 11 / Apprenticeship",
    status: "stage11_operator_surface_ready",
    ready_count: 5,
    required_count: 5,
    deliverables: [
      { id: "teaching_session_ux", label: "Teaching session UX", ready: true },
      { id: "forge_ready_outputs", label: "Forge-ready outputs", ready: true },
    ],
    writes_memory: false,
    captures_screen: false,
    captures_audio: false,
    captures_keystrokes: false,
    grants_execution_authority: false,
    next_smallest_truthful_gap: "stage11_teaching_session_receipt_write_path",
  });
  const ux = parseApprenticeshipLiveTeachingSessionUx({
    ok: true,
    visible_sections: [{ id: "stage_status", label: "Stage status", visible: true }],
    operator_actions: [{ id: "start_teaching_session", label: "Start teaching session", enabled: false }],
    writes_forge_proposal: false,
    starts_teaching_session: false,
    grants_execution_authority: false,
  });

  const model = presentApprenticeshipPanel(status, ux);

  assert.equal(model.status, "stage11_operator_surface_ready");
  assert.equal(model.readyCount, 5);
  assert.deepEqual(model.readyDeliverables, ["Teaching session UX", "Forge-ready outputs"]);
  assert.deepEqual(model.visibleSections, ["Stage status"]);
  assert.deepEqual(model.disabledActions, ["Start teaching session"]);
  assert.ok(model.guardLines.includes("memory writes blocked"));
  assert.ok(model.guardLines.includes("ambient capture blocked"));
  assert.ok(model.guardLines.includes("Forge proposal writes blocked"));
  assert.equal(model.nextGap, "stage11_teaching_session_receipt_write_path");
});

test("ApprenticeshipClient reads bounded status and live teaching UX routes", async () => {
  const requests: Array<{ path: string; method: string }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, method: (init?.method ?? "GET").toUpperCase() });
    if (parsed.pathname.endsWith("/apprenticeship/status")) {
      return jsonResponse({ ok: true, status: "stage11_operator_surface_ready", ready_count: 5, required_count: 5 });
    }
    return jsonResponse({
      ok: true,
      status: "ready",
      live_teaching_session_ux_ready: true,
      visible_sections: [],
      operator_actions: [],
    });
  });

  try {
    const client = new ApprenticeshipClient("http://127.0.0.1:8000/");
    const status = await client.getStatus();
    const ux = await client.getLiveTeachingSessionUx();

    assert.deepEqual(requests, [
      { path: "/apprenticeship/status", method: "GET" },
      { path: "/apprenticeship/live-teaching-session-ux", method: "GET" },
    ]);
    assert.equal(status.status, "stage11_operator_surface_ready");
    assert.equal(ux.live_teaching_session_ux_ready, true);
  } finally {
    restoreFetch();
  }
});
