import assert from "node:assert/strict";
import test from "node:test";

import { LensApiError, LensClient, parseLensStatus } from "./index.ts";

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

test("LensClient.getStatus reads the read-only Lens contract without authority claims", async () => {
  const requests: Array<{ path: string; method: string; limit: string | null }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      limit: parsed.searchParams.get("limit"),
    });

    return jsonResponse({
      ok: true,
      kind: "lens.status",
      subsystem: "lens",
      status: "attention",
      generated_at: "1770001000",
      limit: "6",
      read_only: true,
      mode: {
        id: "assist",
        label: "Assist",
        writes: "approval-gated",
      },
      available_modes: [
        {
          id: "assist",
          label: "Assist",
          summary: "Collaborative mode.",
          implementation_status: "ready",
          active: true,
        },
      ],
      scope: {
        focus: {
          plane_id: "P1_INTERFACE",
          label: "Interface",
          reason: "Expose the resident status truthfully.",
        },
      },
      hud: {
        status: "attention",
        headline: "Pending approval requires operator review.",
        primary_plane: "P1_INTERFACE",
        primary_plane_label: "Interface",
        badges: [
          { label: "approvals", value: "2", severity: "attention" },
          { label: "incidents", value: 0, severity: "neutral" },
        ],
        readback_ready: true,
        route: "/lens/hud",
      },
      command_palette: {
        status: "readback_ready",
        availability: "chat_ui_only",
        summon_anywhere: false,
        message: "Palette command readback exists; OS-wide summon and overlay binding are not implemented here.",
        route: "/lens/status",
        local_surface: "chat_ui.command_palette",
        command_total: "3",
        groups: {
          Navigation: "1",
          Control: 2,
        },
        commands: [
          {
            id: "nav.approvals",
            label: "Open Approvals",
            description: "Review the approval queue and make governance decisions.",
            group: "Navigation",
            keywords: "approval review queue governance",
            status: "available",
            action: "open_surface",
            route: "/approvals/list?status=pending",
            method: "GET",
            surface: "chat_ui.approvals",
            mutates: false,
            requires_confirmation: false,
            attention_count: "2",
            execution_authority: false,
            approval_decision_authority: false,
            memory_write: false,
          },
          {
            id: "mode.pilot",
            label: "Switch to Pilot",
            description: "Declare takeover posture and light the pilot indicator.",
            group: "Control",
            status: "available",
            action: "declare_control_mode",
            route: "/system/operator_mode",
            method: "POST",
            mutates: true,
            requires_confirmation: true,
            write_guard: "system.write plus operator posture",
            target_mode: "pilot",
            execution_authority: false,
            approval_decision_authority: false,
            memory_write: false,
          },
          {
            id: "observer.scan",
            label: "Record Observer Scan",
            description: "Trigger an explicit receipted observer scan.",
            group: "Control",
            status: "available",
            action: "record_observer_scan",
            route: "/system/observer/scan",
            method: "POST",
            mutates: true,
            requires_confirmation: true,
            write_guard: "explicit operator action plus system.write",
            receipt_kind: "observer.scan",
            execution_authority: false,
            approval_decision_authority: false,
            memory_write: false,
          },
        ],
        governance: {
          read_only_contract: true,
          execution_authority: false,
          approval_decision_authority: false,
          memory_write: false,
          overlay_control_authority: false,
          summon_authority: false,
          mutation_authority_granted: false,
        },
      },
      mode_selector: {
        status: "readback_ready",
        active_mode: "assist",
        available_modes: [{ id: "assist", label: "Assist" }],
        mutation_route: "/system/operator_mode",
        write_guard: "system.write plus operator posture",
      },
      approvals_view: {
        status: "attention",
        pending_count: "2",
        items: [{ id: "approval_alpha", status: "pending" }],
        route: "/approvals/list?status=pending",
        decision_route: "/approvals/decision",
      },
      incident_view: {
        status: "clear",
        observer_headline: "No active observer incidents.",
        observer_decision: "clear",
        observer_counts: { active: "0" },
        reactor_review_queue_total: "1",
        route: "/system/observer",
        reactor_route: "/reactor/operator_visibility/summary",
      },
      mission_feed: {
        headline: "Mission continuity is available.",
        counts: { active: "1", blocked: 0 },
        memory_receipt_count: "3",
        route: "/continuity/briefing",
        mission_route: "/missions/list",
      },
      pilot_indicator: {
        active: false,
        status: "standby",
        mode: "assist",
        message: "Pilot is not active; indicator is available as read-only groundwork.",
        route: "/system/operator_mode",
      },
      receipts: {
        status: "readback_ready",
        continuity_ledger_route: "/continuity/ledger",
      },
      stage6_readiness: {
        stage: "Stage 6 / Lens MVP",
        claim: "backend_readback_contract_only",
        criteria: [
          {
            id: "command_palette_commands",
            status: "readback_ready",
            evidence: ["/lens/status"],
            command_count: "3",
          },
          {
            id: "approvals_view",
            status: "readback_ready",
            evidence: ["/approvals/list?status=pending", "/lens/status"],
            pending_count: "2",
          },
          {
            id: "summon_anywhere",
            status: "not_implemented",
            evidence: [],
          },
        ],
      },
      governance: {
        gate: "lens_readback_only",
        execution_authority: false,
        approval_decision_authority: false,
        memory_write: false,
        overlay_control_authority: false,
        capture_authority: false,
        new_sensing_authority: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const snapshot = await client.getStatus({ limit: 6 });

    assert.deepEqual(requests, [
      {
        path: "/lens/status",
        method: "GET",
        limit: "6",
      },
    ]);
    assert.equal(snapshot.ok, true);
    assert.equal(snapshot.kind, "lens.status");
    assert.equal(snapshot.generated_at, 1770001000);
    assert.equal(snapshot.limit, 6);
    assert.equal(snapshot.read_only, true);
    assert.equal(snapshot.hud.badges[0]?.value, 2);
    assert.equal(snapshot.command_palette.status, "readback_ready");
    assert.equal(snapshot.command_palette.availability, "chat_ui_only");
    assert.equal(snapshot.command_palette.summon_anywhere, false);
    assert.equal(snapshot.command_palette.command_total, 3);
    assert.equal(snapshot.command_palette.groups.Navigation, 1);
    assert.equal(snapshot.command_palette.groups.Control, 2);
    assert.equal(snapshot.command_palette.commands.length, 3);
    assert.equal(snapshot.command_palette.commands[0]?.id, "nav.approvals");
    assert.equal(snapshot.command_palette.commands[0]?.attention_count, 2);
    assert.equal(snapshot.command_palette.commands[1]?.id, "mode.pilot");
    assert.equal(snapshot.command_palette.commands[1]?.mutates, true);
    assert.equal(snapshot.command_palette.commands[1]?.write_guard, "system.write plus operator posture");
    assert.equal(snapshot.command_palette.commands[1]?.target_mode, "pilot");
    assert.equal(snapshot.command_palette.commands[2]?.receipt_kind, "observer.scan");
    assert.equal(snapshot.command_palette.commands[2]?.execution_authority, false);
    assert.equal(snapshot.command_palette.governance.execution_authority, false);
    assert.equal(snapshot.command_palette.governance.mutation_authority_granted, false);
    assert.equal(snapshot.approvals_view.pending_count, 2);
    assert.equal(snapshot.incident_view.observer_counts.active, 0);
    assert.equal(snapshot.incident_view.reactor_review_queue_total, 1);
    assert.equal(snapshot.mission_feed.counts.active, 1);
    assert.equal(snapshot.mission_feed.memory_receipt_count, 3);
    assert.equal(snapshot.pilot_indicator.active, false);
    assert.equal(snapshot.governance.execution_authority, false);
    assert.equal(snapshot.governance.approval_decision_authority, false);
    assert.equal(snapshot.governance.overlay_control_authority, false);
    assert.equal(snapshot.stage6_readiness.claim, "backend_readback_contract_only");
    assert.equal(snapshot.stage6_readiness.criteria[0]?.id, "command_palette_commands");
    assert.equal(snapshot.stage6_readiness.criteria[0]?.status, "readback_ready");
    assert.equal(snapshot.stage6_readiness.criteria[1]?.pending_count, 2);
    assert.equal(snapshot.stage6_readiness.criteria[2]?.id, "summon_anywhere");
    assert.equal(snapshot.stage6_readiness.criteria[2]?.status, "not_implemented");
  } finally {
    restoreFetch();
  }
});

test("parseLensStatus drops malformed nested items and preserves governance defaults", () => {
  const snapshot = parseLensStatus({
    ok: true,
    hud: {
      badges: [{ label: "mode", value: "assist" }, { value: "missing label" }],
    },
    available_modes: [{ id: "assist", label: "Assist" }, { no_id: true }],
    mode_selector: {
      available_modes: [{ id: "pilot", label: "Pilot", active: false }],
    },
    command_palette: {
      command_total: "2",
      groups: { Navigation: "1" },
      commands: [{ id: "nav.orb", label: "Open ORB" }, { label: "missing id" }, "bad item"],
      governance: { execution_authority: false },
    },
    approvals_view: {
      pending_count: "4",
      items: [{ id: "approval_visible" }, "bad item"],
    },
    incident_view: {
      observer_counts: { active: "2", warning: "3" },
    },
    mission_feed: {
      counts: { active: "1" },
    },
    stage6_readiness: {
      criteria: [
        { id: "mode_visibility", status: "readback_ready", evidence: ["/lens/status"] },
        { status: "missing id" },
      ],
    },
    governance: {},
  });

  assert.equal(snapshot.hud.badges.length, 1);
  assert.equal(snapshot.available_modes.length, 1);
  assert.equal(snapshot.mode_selector.available_modes.length, 1);
  assert.equal(snapshot.command_palette.command_total, 2);
  assert.equal(snapshot.command_palette.groups.Navigation, 1);
  assert.equal(snapshot.command_palette.commands.length, 1);
  assert.equal(snapshot.command_palette.commands[0]?.id, "nav.orb");
  assert.equal(snapshot.approvals_view.pending_count, 4);
  assert.equal(snapshot.approvals_view.items.length, 1);
  assert.equal(snapshot.incident_view.observer_counts.active, 2);
  assert.equal(snapshot.incident_view.observer_counts.warning, 3);
  assert.equal(snapshot.mission_feed.counts.active, 1);
  assert.equal(snapshot.stage6_readiness.criteria.length, 1);
  assert.equal(snapshot.governance.execution_authority, false);
  assert.equal(snapshot.governance.approval_decision_authority, false);
  assert.equal(snapshot.governance.memory_write, false);
});

test("LensClient.getStatus throws LensApiError on HTTP failures", async () => {
  const restoreFetch = installFetch(() => jsonResponse({ ok: false }, 503));

  try {
    const client = new LensClient("http://127.0.0.1:8000");
    await assert.rejects(
      () => client.getStatus(),
      (err: unknown) => {
        assert.ok(err instanceof LensApiError);
        assert.equal(err.status, 503);
        assert.match(err.message, /HTTP 503/);
        return true;
      },
    );
  } finally {
    restoreFetch();
  }
});
