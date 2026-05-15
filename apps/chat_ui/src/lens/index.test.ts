import assert from "node:assert/strict";
import test from "node:test";

import {
  LensApiError,
  LensClient,
  parseLensStatus,
  presentStage6NextHandoff,
  shouldOpenLensCommandPalette,
  shouldOpenLensStatusPanel,
} from "./index.ts";

type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response>;

test("shouldOpenLensCommandPalette accepts governed URL intents", () => {
  assert.equal(shouldOpenLensCommandPalette("?francis_lens=command_palette"), true);
  assert.equal(shouldOpenLensCommandPalette("?lens_palette=open"), true);
  assert.equal(shouldOpenLensCommandPalette("", "#francis_lens=command_palette"), true);
  assert.equal(shouldOpenLensCommandPalette("", "#/console?lens_palette=command_palette"), true);
  assert.equal(shouldOpenLensCommandPalette("?francis_lens=status"), false);
  assert.equal(shouldOpenLensCommandPalette("?lens_palette=closed"), false);
});

test("shouldOpenLensStatusPanel accepts read-only Lens status URL intents", () => {
  assert.equal(shouldOpenLensStatusPanel("?francis_lens=status"), true);
  assert.equal(shouldOpenLensStatusPanel("?lens_panel=status"), true);
  assert.equal(shouldOpenLensStatusPanel("", "#/console?francis_lens=status"), true);
  assert.equal(shouldOpenLensStatusPanel("", "#/console?lens_panel=status"), true);
  assert.equal(shouldOpenLensStatusPanel("?francis_lens=command_palette"), false);
  assert.equal(shouldOpenLensStatusPanel("?lens_panel=approvals"), false);
});

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
  const runtimeLoopReadiness = {
    ok: true,
    kind: "lens.host.runtime_loop.readiness_audit",
    status: "blocked",
    audit_status: "complete",
    route: "/lens/host/runtime-loop/readiness",
    runtime_plan_route: "/lens/host/runtime-plan",
    runtime_loop_route: "/lens/host/runtime-loop",
    execute_route: "/lens/host/runtime-loop/execute",
    denials_route: "/lens/host/runtime-loop/denials",
    host_route: "/lens/host",
    limit: "6",
    ready: false,
    loop_ready: false,
    execution_ready: false,
    resident_runtime_loop: false,
    resident_runtime_ready: false,
    resident_claim_allowed: false,
    runtime_plan_available: true,
    loop_contract_readback_ready: true,
    execution_denial_boundary_observed: true,
    denial_receipt_readback_ready: true,
    receipt_count: "0",
    latest_receipt_id: "",
    requirements_total: "6",
    requirements_ready_total: "3",
    requirements_blocked_total: "3",
    requirements: [
      { id: "runtime_loop_contract", ready: true },
      { id: "resident_loop_process_supervision", ready: false },
    ],
    blocked_requirements: [
      "resident_loop_process_supervision",
      "resident_loop_service_lifecycle",
      "resident_loop_surface_presence",
    ],
    operator_surface_readback_ready: true,
    first_blocked_requirement: "resident_loop_process_supervision",
    first_blocked_requirement_handoff: {
      id: "resident_loop_process_supervision",
      label: "Resident loop process supervision",
      status: "blocked",
      route: "/lens/host/supervision",
      readiness_route: "/lens/host/supervision/authority/readiness",
      request_route: "/lens/host/supervision/authority/request",
      requests_route: "/lens/host/supervision/authority/requests",
      grant_route: "/lens/host/supervision/authority",
      grants_route: "/lens/host/supervision/authority/grants",
      denials_route: "/lens/host/supervision/authority/denials",
      next_step: "resolve_host_supervision_authority_readiness_blockers_before_implementation",
      authority_required: "process_supervision_authority",
      authority_granted: false,
      blockers: [
        "resident_host_process_missing",
        "process_supervision_authority_not_granted",
        "process_restart_authority_not_granted",
      ],
      would_execute: false,
      would_mutate: false,
    },
    blocked_requirement_handoffs: [
      {
        id: "resident_loop_process_supervision",
        label: "Resident loop process supervision",
        status: "blocked",
        route: "/lens/host/supervision",
        readiness_route: "/lens/host/supervision/authority/readiness",
        request_route: "/lens/host/supervision/authority/request",
        requests_route: "/lens/host/supervision/authority/requests",
        grant_route: "/lens/host/supervision/authority",
        grants_route: "/lens/host/supervision/authority/grants",
        denials_route: "/lens/host/supervision/authority/denials",
        next_step: "resolve_host_supervision_authority_readiness_blockers_before_implementation",
        authority_required: "process_supervision_authority",
        authority_granted: false,
        blockers: [
          "resident_host_process_missing",
          "process_supervision_authority_not_granted",
          "process_restart_authority_not_granted",
        ],
        would_execute: false,
        would_mutate: false,
      },
    ],
    blockers: ["resident_runtime_loop_not_implemented", "resident_runtime_loop_not_supervised"],
    source_readbacks: {
      runtime_plan_status: "blocked",
      runtime_loop_status: "blocked",
      execution_denial_status: "denied_no_approval",
      denial_receipts_status: "empty",
    },
    evidence: [
      "/lens/host/runtime-loop/readiness",
      "/lens/host/runtime-plan",
      "/lens/host/runtime-loop",
      "/lens/host/runtime-loop/execute",
      "/lens/host/runtime-loop/denials",
    ],
    governance: {
      gate: "lens_host_runtime_loop_readiness_audit",
      read_only_contract: true,
      audit_only: true,
      execution_authority: false,
      receipt_write_authority: false,
      resident_claim_authority: false,
    },
    next_smallest_truthful_gap: "resident_host_supervision_authority_readiness_blockers",
    message: "Lens can audit resident host runtime loop readiness, but the loop remains blocked.",
  };
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
        runtime_status: "readback_only",
        resident_overlay: false,
        runtime: {
          status: "readback_only",
          claim: "chat_ui_hud_readback_only",
          surface: "chat_ui.system_orb",
          route: "/lens/hud",
          window_host: "chat_ui",
          resident_overlay: false,
          always_on_top: false,
          global_hotkey: false,
          tray_presence: false,
          os_level: false,
          blockers: ["resident_overlay_runtime_missing", "global_hotkey_binding_missing"],
          message: "HUD readback exists through chat UI; resident OS overlay runtime is not implemented here.",
          governance: {
            read_only_contract: true,
            overlay_control_authority: false,
            summon_authority: false,
            capture_authority: false,
            new_sensing_authority: false,
          },
        },
        route: "/lens/hud",
      },
      command_palette: {
        status: "readback_ready",
        availability: "chat_ui_only",
        summon_anywhere: false,
        url_entrypoint_ready: true,
        url_entrypoint: {
          kind: "lens.command_palette.url_entrypoint",
          status: "ready",
          route: "/?francis_lens=command_palette",
          local_surface: "chat_ui.command_palette",
          opens_palette_in_chat_ui: true,
          requires_running_chat_ui: true,
          os_level_command_palette: false,
          summon_anywhere: false,
          global_hotkey: false,
        },
        message:
          "Palette command readback and chat-UI URL entrypoint exist; OS-wide summon, global hotkey, tray, and overlay binding are not implemented here.",
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
      resident_host: {
        route: "/lens/host",
        status: "not_implemented",
        contract_status: "readback_ready",
        availability: "backend_readback_only",
        activation_denial_receipts_route: "/lens/host/activation/denials",
        activation_denial_receipts: {
          ok: true,
          kind: "lens.host.activation.denial_receipts",
          status: "readback_ready",
          route: "/lens/host/activation/denials",
          execute_route: "/lens/host/activation/execute",
          limit: "6",
          approval_id: "",
          filter_status: "",
          total: "1",
          latest: {
            kind: "lens.host.activation.denial.receipt",
            receipt_id: "lad_1770001000_alpha",
            id: "lad_1770001000_alpha",
            status: "denied_no_execution_authority",
            route: "/lens/host/activation/execute",
            method: "POST",
            source_kind: "lens.host.activation.execution_denial",
            source_route: "/lens/host/activation/execute",
            approval_id: "appr_lens_alpha",
            actor: "chat_ui.lens",
            reason: "operator asked to prove launch stays blocked",
            created_ts: "1770001000",
            blockers: ["local_process_launch_authority_not_granted"],
            approval: { approved: true, status: "approved" },
            permission: { ready: true, allowed: true, required_scope: "system.write" },
            execution: {
              applied: false,
              executed: false,
              would_launch_process: false,
              would_write_memory: false,
            },
            denial: {
              reason: "local_process_launch_authority_not_granted",
              would_launch_process: false,
              denial_receipt_written: true,
            },
            governance: {
              gate: "lens_host_activation_denial_receipt",
              execution_authority: false,
              approval_decision_authority: false,
              local_process_launch_authority: false,
              memory_write: false,
              denial_receipt_write_authority: true,
            },
          },
          items: [
            {
              receipt_id: "lad_1770001000_alpha",
              status: "denied_no_execution_authority",
              route: "/lens/host/activation/execute",
              approval_id: "appr_lens_alpha",
              created_ts: "1770001000",
              blockers: ["local_process_launch_authority_not_granted"],
              approval: { approved: true },
              permission: { ready: true },
              execution: { applied: false, executed: false, would_launch_process: false, would_write_memory: false },
              denial: { reason: "local_process_launch_authority_not_granted" },
              governance: {
                execution_authority: false,
                approval_decision_authority: false,
                local_process_launch_authority: false,
                memory_write: false,
              },
            },
          ],
          governance: {
            gate: "lens_host_activation_denial_receipts_readback",
            read_only_contract: true,
            execution_authority: false,
            approval_decision_authority: false,
            memory_write: false,
          },
        },
        runtime_loop_readiness_route: "/lens/host/runtime-loop/readiness",
        runtime_loop_readiness: runtimeLoopReadiness,
      },
      receipts: {
        status: "readback_ready",
        continuity_ledger_route: "/continuity/ledger",
        lens_host_activation_denials_route: "/lens/host/activation/denials",
        lens_host_runtime_loop_readiness_route: "/lens/host/runtime-loop/readiness",
      },
      runtime_loop_readiness: runtimeLoopReadiness,
      stage6_readiness: {
        stage: "Stage 6 / Lens MVP",
        claim: "backend_readback_contract_only",
        closure_readback: {
          kind: "lens.stage6.closure_readback",
          status: "blocked",
          ready_to_close: false,
          criteria_total: "5",
          ready_total: "2",
          blocked_total: "3",
          ready_criteria: ["mode_visibility", "pilot_visibility_groundwork"],
          blocked_criteria: ["summon_anywhere", "helpful_not_noisy", "system_resident_presence"],
          next_smallest_truthful_gap: "resident_host_supervision_boundary",
          criteria: [
            {
              id: "summon_anywhere",
              label: "Summon anywhere",
              ready: false,
              status: "blocked",
              evidence: ["/lens/summon", "/lens/status"],
              blockers: ["summon_anywhere_missing"],
              basis: "OS-wide summon requires a resident host plus explicit hotkey/summon authority.",
              next_smallest_truthful_gap: "summon_anywhere_blockers",
              handoff: {
                next_step: "resolve_summon_anywhere_blockers_before_stage6_closure",
                readiness_route: "/lens/summon/readiness",
                summon_route: "/lens/summon",
                status_route: "/lens/status",
                proof_script: "scripts/lens-summon-preflight.ps1 -Mode Status",
                first_blocker_family: "resident_host",
                first_blocker_family_next_smallest_truthful_gap: "resident_host_runtime_blocker_boundary",
                summon_anywhere_family_chain_completion_audit_handoff: {
                  proof_script: "scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status",
                  next_smallest_truthful_gap: "stage6_lens_completion_audit",
                  blocked_families: [
                    "resident_host",
                    "tray_presence",
                    "overlay_window",
                    "global_hotkey_binding",
                    "summon_binding",
                    "authority",
                  ],
                  would_execute: false,
                  would_mutate: false,
                },
                authority_required: "resident_runtime_execution_authority",
                next_smallest_truthful_gap: "summon_anywhere_blockers",
                read_only_contract: true,
                diagnostic_only: true,
                would_execute: false,
                would_mutate: false,
              },
            },
            {
              id: "mode_visibility",
              label: "Mode visibility",
              ready: true,
              status: "ready",
              evidence: ["/system/operator_mode", "/lens/status"],
              blockers: [],
            },
          ],
          governance: {
            read_only_contract: true,
            execution_authority: false,
            resident_claim_authority: false,
          },
        },
        next_handoff: {
          kind: "lens.stage6.next_handoff.readback",
          status: "readback_ready",
          ready_to_close: false,
          stage_next_smallest_truthful_gap: "summon_anywhere_blockers",
          next_smallest_truthful_gap: "persistent_supervision_enablement_authority_not_granted",
          recommended_next_slice: "prove_persistent_supervision_enablement_authority_after_candidate_handoff",
          recommended_handoff_source: "persistent_supervision_enablement_authority_denial_handoff",
          recommended_proof_script: "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status",
          recommended_route: "/lens/host/persistent-supervision/enablement",
          recommended_readiness_route: "/lens/host/persistent-supervision/enablement/authority/readiness",
          recommended_request_route: "/lens/host/persistent-supervision/enablement/authority/request",
          recommended_grant_route: "/lens/host/persistent-supervision/enablement/authority",
          recommended_grants_route: "/lens/host/persistent-supervision/enablement/authority/grants",
          recommended_execution_readiness_route: "/lens/host/persistent-supervision/enablement/execution/readiness",
          authority_required: "persistent_supervision_enablement_authority",
          recommended_prerequisites_handoff_source: "persistent_supervision_required_prerequisites_handoff",
          recommended_prerequisites_next_slice: "resolve_persistent_supervision_required_prerequisites_before_enablement",
          recommended_prerequisites_proof_script: "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status",
          recommended_prerequisites_route: "/lens/host/persistent-supervision",
          recommended_prerequisites_readiness_route: "/lens/host/persistent-supervision/enablement",
          recommended_prerequisites_authority_required:
            "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
          recommended_first_missing_handoff_source: "persistent_supervision_first_missing_requirement_handoff",
          recommended_first_missing_next_slice: "resolve_resident_host_process_before_persistent_supervision_enablement",
          recommended_first_missing_proof_script: "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
          recommended_first_missing_route: "/lens/host",
          recommended_first_missing_readiness_route: "/lens/host/runtime-loop/readiness",
          recommended_first_missing_authority_required: "process_supervision_authority",
          first_blocked_criterion: "summon_anywhere",
          persistent_supervision_required_prerequisites_observed: true,
          persistent_supervision_missing_required_before_enable: ["resident_host_process", "tray_presence"],
          persistent_supervision_first_missing_required_before_enable: "resident_host_process",
          persistent_supervision_first_missing_requirement_handoff: {
            id: "resident_host_process",
            next_step: "resolve_resident_host_process_before_persistent_supervision_enablement",
            proof_script: "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
          },
          persistent_supervision_required_prerequisites_handoff: {
            next_smallest_truthful_gap: "persistent_supervision_required_prerequisites_missing",
          },
          activation_execution_handoff_observed: false,
          activation_execution_handoff: {},
          persistent_supervision_enablement_authority_handoff_observed: true,
          persistent_supervision_enablement_authority_handoff: {
            id: "persistent_supervision_enablement_authority",
            status: "blocked",
            previous_next_smallest_truthful_gap: "persistent_supervision_authority_not_granted",
            consumed_audit_next_smallest_truthful_gap: "persistent_supervision_enablement_denial_boundary",
            next_smallest_truthful_gap: "persistent_supervision_enablement_authority_not_granted",
            next_step: "prove_persistent_supervision_enablement_authority_after_candidate_handoff",
            acceptance_criterion: "system_resident_presence",
            authority_required: "persistent_supervision_enablement_authority",
            read_only_contract: true,
            diagnostic_only: true,
            would_execute: false,
            would_mutate: false,
            authority_granted: false,
            enablement_denial_observed: true,
            execution_denial_observed: true,
            persistent_supervision_enablement_authority: false,
            service_config_write_authority: false,
            persistent_supervision_execution_authority: false,
            receipt_write_authority: false,
            resident_claim_authority: false,
            resident_claim_allowed: false,
            service_config_updated: false,
            applied: false,
            executed: false,
            blockers: [
              "persistent_supervision_enablement_authority_not_granted",
              "persistent_supervision_execution_authority_not_granted",
            ],
          },
          resident_runtime_candidate_handoff_observed: false,
          resident_runtime_candidate_handoff: {},
          governance: {
            read_only_contract: true,
            diagnostic_only: true,
            uses_lens_status_readback: true,
            execution_authority: false,
            approval_decision_authority: false,
            local_process_launch_authority: false,
            process_supervision_authority: false,
            process_restart_authority: false,
            service_install_authority: false,
            service_control_authority: false,
            hotkey_registration_authority: false,
            tray_registration_authority: false,
            overlay_control_authority: false,
            summon_authority: false,
            memory_write: false,
            receipt_write_authority: false,
            resident_claim_authority: false,
            mutation_authority_granted: false,
          },
        },
        criteria: [
          {
            id: "hud_layer_runtime",
            status: "readback_only",
            evidence: ["/lens/hud", "/lens/status"],
            resident_overlay: false,
            blockers: ["resident_overlay_runtime_missing"],
          },
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
            id: "host_activation_denial_receipt_readback",
            status: "readback_ready",
            evidence: ["/lens/host/activation/denials", "/lens/host/activation/execute", "/lens/status"],
            receipt_count: "1",
            latest_receipt_id: "lad_1770001000_alpha",
            execution_authority: false,
            approval_decision_authority: false,
            local_process_launch_authority: false,
            memory_write: false,
          },
          {
            id: "summon_anywhere",
            status: "not_implemented",
            evidence: [],
          },
          {
            id: "resident_supervision_enablement_gate",
            status: "blocked",
            evidence: ["/lens/host/supervision", "/lens/host/manifest", "/lens/status"],
            ready: false,
            resident_claim_allowed: false,
            blockers: ["process_supervision_enabled"],
            service_control_authority: false,
          },
          {
            id: "summon_enablement_gate",
            status: "blocked",
            evidence: ["/lens/summon", "/lens/preflight", "/lens/status"],
            ready: false,
            summon_anywhere: false,
            global_hotkey: "Ctrl+Alt+Space",
            blockers: ["summon_authority_not_granted"],
            hotkey_registration_authority: false,
            summon_authority: false,
            overlay_control_authority: false,
          },
          {
            id: "tray_enablement_gate",
            status: "blocked",
            evidence: ["/lens/tray", "/lens/preflight", "/lens/status"],
            ready: false,
            tray_presence: false,
            presence_name: "Francis Lens Tray Presence",
            blockers: ["tray_registration_authority_not_granted"],
            tray_registration_authority: false,
            tray_icon_authority: false,
            notification_authority: false,
          },
          {
            id: "overlay_enablement_gate",
            status: "blocked",
            evidence: ["/lens/overlay", "/lens/preflight", "/lens/status"],
            ready: false,
            overlay_window: false,
            overlay_name: "Francis Lens Overlay",
            blockers: ["overlay_control_authority_not_granted"],
            window_management_authority: false,
            overlay_control_authority: false,
            capture_authority: false,
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
    assert.equal(snapshot.hud.runtime_status, "readback_only");
    assert.equal(snapshot.hud.resident_overlay, false);
    assert.equal(snapshot.hud.runtime.claim, "chat_ui_hud_readback_only");
    assert.equal(snapshot.hud.runtime.resident_overlay, false);
    assert.equal(snapshot.hud.runtime.always_on_top, false);
    assert.equal(snapshot.hud.runtime.global_hotkey, false);
    assert.equal(snapshot.hud.runtime.tray_presence, false);
    assert.equal(snapshot.hud.runtime.blockers[0], "resident_overlay_runtime_missing");
    assert.equal(snapshot.hud.runtime.governance.overlay_control_authority, false);
    assert.equal(snapshot.hud.runtime.governance.summon_authority, false);
    assert.equal(snapshot.command_palette.status, "readback_ready");
    assert.equal(snapshot.command_palette.availability, "chat_ui_only");
    assert.equal(snapshot.command_palette.summon_anywhere, false);
    assert.equal(snapshot.command_palette.url_entrypoint_ready, true);
    assert.equal(snapshot.command_palette.url_entrypoint.route, "/?francis_lens=command_palette");
    assert.equal(snapshot.command_palette.url_entrypoint.opens_palette_in_chat_ui, true);
    assert.equal(snapshot.command_palette.url_entrypoint.os_level_command_palette, false);
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
    assert.equal(snapshot.resident_host.activation_denial_receipts_route, "/lens/host/activation/denials");
    assert.equal(snapshot.resident_host.activation_denial_receipts.total, 1);
    assert.equal(snapshot.resident_host.activation_denial_receipts.latest?.receipt_id, "lad_1770001000_alpha");
    assert.equal(snapshot.resident_host.activation_denial_receipts.latest?.approval_id, "appr_lens_alpha");
    assert.equal(snapshot.resident_host.activation_denial_receipts.latest?.created_ts, 1770001000);
    assert.equal(
      snapshot.resident_host.activation_denial_receipts.latest?.blockers[0],
      "local_process_launch_authority_not_granted",
    );
    assert.equal(snapshot.resident_host.activation_denial_receipts.latest?.execution.would_launch_process, false);
    assert.equal(snapshot.resident_host.activation_denial_receipts.latest?.governance.execution_authority, false);
    assert.equal(snapshot.resident_host.runtime_loop_readiness_route, "/lens/host/runtime-loop/readiness");
    assert.equal(snapshot.resident_host.runtime_loop_readiness.kind, "lens.host.runtime_loop.readiness_audit");
    assert.equal(snapshot.resident_host.runtime_loop_readiness.status, "blocked");
    assert.equal(snapshot.resident_host.runtime_loop_readiness.ready, false);
    assert.equal(snapshot.resident_host.runtime_loop_readiness.runtime_plan_available, true);
    assert.equal(snapshot.resident_host.runtime_loop_readiness.loop_contract_readback_ready, true);
    assert.equal(snapshot.resident_host.runtime_loop_readiness.execution_denial_boundary_observed, true);
    assert.equal(snapshot.resident_host.runtime_loop_readiness.denial_receipt_readback_ready, true);
    assert.equal(snapshot.resident_host.runtime_loop_readiness.requirements_total, 6);
    assert.equal(snapshot.resident_host.runtime_loop_readiness.requirements_ready_total, 3);
    assert.equal(snapshot.resident_host.runtime_loop_readiness.requirements_blocked_total, 3);
    assert.equal(
      snapshot.resident_host.runtime_loop_readiness.blocked_requirements[0],
      "resident_loop_process_supervision",
    );
    assert.equal(snapshot.resident_host.runtime_loop_readiness.operator_surface_readback_ready, true);
    assert.equal(
      snapshot.resident_host.runtime_loop_readiness.first_blocked_requirement,
      "resident_loop_process_supervision",
    );
    assert.equal(
      snapshot.resident_host.runtime_loop_readiness.first_blocked_requirement_handoff?.request_route,
      "/lens/host/supervision/authority/request",
    );
    assert.equal(
      snapshot.resident_host.runtime_loop_readiness.first_blocked_requirement_handoff?.next_step,
      "resolve_host_supervision_authority_readiness_blockers_before_implementation",
    );
    assert.equal(snapshot.resident_host.runtime_loop_readiness.first_blocked_requirement_handoff?.would_execute, false);
    assert.deepEqual(
      snapshot.resident_host.runtime_loop_readiness.blocked_requirement_handoffs.map((item) => item.id),
      snapshot.resident_host.runtime_loop_readiness.blocked_requirements.slice(0, 1),
    );
    assert.equal(snapshot.resident_host.runtime_loop_readiness.blockers[0], "resident_runtime_loop_not_implemented");
    assert.equal(snapshot.resident_host.runtime_loop_readiness.governance.execution_authority, false);
    assert.equal(
      snapshot.resident_host.runtime_loop_readiness.next_smallest_truthful_gap,
      "resident_host_supervision_authority_readiness_blockers",
    );
    assert.equal(snapshot.receipts.lens_host_activation_denials_route, "/lens/host/activation/denials");
    assert.equal(snapshot.receipts.lens_host_runtime_loop_readiness_route, "/lens/host/runtime-loop/readiness");
    assert.equal(snapshot.runtime_loop_readiness.route, "/lens/host/runtime-loop/readiness");
    assert.equal(snapshot.runtime_loop_readiness.ready, false);
    assert.equal(snapshot.runtime_loop_readiness.blocked_requirements[0], "resident_loop_process_supervision");
    assert.equal(snapshot.governance.execution_authority, false);
    assert.equal(snapshot.governance.approval_decision_authority, false);
    assert.equal(snapshot.governance.overlay_control_authority, false);
    assert.equal(snapshot.stage6_readiness.claim, "backend_readback_contract_only");
    assert.equal(snapshot.stage6_readiness.closure_readback.status, "blocked");
    assert.equal(snapshot.stage6_readiness.closure_readback.ready_to_close, false);
    assert.equal(snapshot.stage6_readiness.closure_readback.criteria_total, 5);
    assert.equal(snapshot.stage6_readiness.closure_readback.ready_total, 2);
    assert.equal(snapshot.stage6_readiness.closure_readback.blocked_total, 3);
    assert.equal(snapshot.stage6_readiness.closure_readback.ready_criteria[0], "mode_visibility");
    assert.equal(snapshot.stage6_readiness.closure_readback.blocked_criteria[2], "system_resident_presence");
    assert.equal(
      snapshot.stage6_readiness.closure_readback.next_smallest_truthful_gap,
      "resident_host_supervision_boundary",
    );
    assert.equal(snapshot.stage6_readiness.closure_readback.criteria[0]?.id, "summon_anywhere");
    assert.equal(snapshot.stage6_readiness.closure_readback.criteria[0]?.ready, false);
    assert.equal(snapshot.stage6_readiness.closure_readback.criteria[0]?.blockers[0], "summon_anywhere_missing");
    assert.equal(
      snapshot.stage6_readiness.closure_readback.criteria[0]?.next_smallest_truthful_gap,
      "summon_anywhere_blockers",
    );
    assert.equal(
      snapshot.stage6_readiness.closure_readback.criteria[0]?.handoff?.next_step,
      "resolve_summon_anywhere_blockers_before_stage6_closure",
    );
    assert.equal(
      snapshot.stage6_readiness.closure_readback.criteria[0]?.handoff?.readiness_route,
      "/lens/summon/readiness",
    );
    assert.equal(
      snapshot.stage6_readiness.closure_readback.criteria[0]?.handoff?.proof_script,
      "scripts/lens-summon-preflight.ps1 -Mode Status",
    );
    assert.equal(snapshot.stage6_readiness.closure_readback.criteria[0]?.handoff?.would_execute, false);
    assert.equal(snapshot.stage6_readiness.closure_readback.criteria[0]?.handoff?.read_only_contract, true);
    assert.equal(
      snapshot.stage6_readiness.closure_readback.criteria[0]?.handoff
        ?.summon_anywhere_family_chain_completion_audit_handoff.proof_script,
      "scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status",
    );
    assert.equal(snapshot.stage6_readiness.closure_readback.governance.execution_authority, false);
    assert.equal(snapshot.stage6_readiness.closure_readback.governance.resident_claim_authority, false);
    assert.equal(snapshot.stage6_readiness.next_handoff.status, "readback_ready");
    assert.equal(
      snapshot.stage6_readiness.next_handoff.next_smallest_truthful_gap,
      "persistent_supervision_enablement_authority_not_granted",
    );
    assert.equal(
      snapshot.stage6_readiness.next_handoff.recommended_handoff_source,
      "persistent_supervision_enablement_authority_denial_handoff",
    );
    assert.equal(
      snapshot.stage6_readiness.next_handoff.recommended_prerequisites_handoff_source,
      "persistent_supervision_required_prerequisites_handoff",
    );
    assert.equal(
      snapshot.stage6_readiness.next_handoff.recommended_prerequisites_next_slice,
      "resolve_persistent_supervision_required_prerequisites_before_enablement",
    );
    assert.equal(
      snapshot.stage6_readiness.next_handoff.recommended_prerequisites_proof_script,
      "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status",
    );
    assert.equal(
      snapshot.stage6_readiness.next_handoff.recommended_first_missing_handoff_source,
      "persistent_supervision_first_missing_requirement_handoff",
    );
    assert.equal(
      snapshot.stage6_readiness.next_handoff.recommended_first_missing_next_slice,
      "resolve_resident_host_process_before_persistent_supervision_enablement",
    );
    assert.equal(
      snapshot.stage6_readiness.next_handoff.recommended_first_missing_proof_script,
      "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
    );
    assert.equal(
      snapshot.stage6_readiness.next_handoff.recommended_first_missing_authority_required,
      "process_supervision_authority",
    );
    assert.equal(snapshot.stage6_readiness.next_handoff.persistent_supervision_required_prerequisites_observed, true);
    assert.equal(
      snapshot.stage6_readiness.next_handoff.persistent_supervision_missing_required_before_enable[0],
      "resident_host_process",
    );
    assert.equal(
      snapshot.stage6_readiness.next_handoff.persistent_supervision_enablement_authority_handoff_observed,
      true,
    );
    assert.equal(snapshot.stage6_readiness.next_handoff.governance.execution_authority, false);
    const handoffPresentation = presentStage6NextHandoff(snapshot.stage6_readiness.next_handoff);
    assert.equal(handoffPresentation.loaded, true);
    assert.equal(handoffPresentation.kind, "lens.stage6.next_handoff.readback");
    assert.equal(handoffPresentation.status, "readback_ready");
    assert.equal(handoffPresentation.readyToClose, false);
    assert.equal(handoffPresentation.readOnlyContract, true);
    assert.equal(handoffPresentation.diagnosticOnly, true);
    assert.equal(handoffPresentation.usesLensStatusReadback, true);
    assert.equal(handoffPresentation.executionAuthority, false);
    assert.equal(handoffPresentation.approvalDecisionAuthority, false);
    assert.equal(handoffPresentation.localProcessLaunchAuthority, false);
    assert.equal(handoffPresentation.processSupervisionAuthority, false);
    assert.equal(handoffPresentation.processRestartAuthority, false);
    assert.equal(handoffPresentation.serviceInstallAuthority, false);
    assert.equal(handoffPresentation.serviceControlAuthority, false);
    assert.equal(handoffPresentation.hotkeyRegistrationAuthority, false);
    assert.equal(handoffPresentation.trayRegistrationAuthority, false);
    assert.equal(handoffPresentation.overlayControlAuthority, false);
    assert.equal(handoffPresentation.summonAuthority, false);
    assert.equal(handoffPresentation.memoryWrite, false);
    assert.equal(handoffPresentation.receiptWriteAuthority, false);
    assert.equal(handoffPresentation.residentClaimAuthority, false);
    assert.equal(handoffPresentation.mutationAuthorityGranted, false);
    assert.equal(handoffPresentation.prerequisitesObserved, true);
    assert.equal(handoffPresentation.activationExecutionHandoffObserved, false);
    assert.equal(handoffPresentation.enablementAuthorityHandoffObserved, true);
    assert.equal(handoffPresentation.residentCandidateHandoffObserved, false);
    assert.equal(handoffPresentation.sourceHandoffLoaded, true);
    assert.equal(handoffPresentation.sourceHandoffId, "persistent_supervision_enablement_authority");
    assert.equal(
      handoffPresentation.sourceHandoffNextStep,
      "prove_persistent_supervision_enablement_authority_after_candidate_handoff",
    );
    assert.equal(handoffPresentation.sourceHandoffAcceptanceCriterion, "system_resident_presence");
    assert.equal(handoffPresentation.sourceHandoffAuthorityRequired, "persistent_supervision_enablement_authority");
    assert.equal(handoffPresentation.sourceHandoffStatus, "blocked");
    assert.equal(handoffPresentation.sourceHandoffReadOnlyContract, true);
    assert.equal(handoffPresentation.sourceHandoffDiagnosticOnly, true);
    assert.equal(handoffPresentation.sourceHandoffWouldExecute, false);
    assert.equal(handoffPresentation.sourceHandoffWouldMutate, false);
    assert.equal(handoffPresentation.sourceHandoffAuthorityGranted, false);
    assert.deepEqual(handoffPresentation.sourceHandoffBlockers, [
      "persistent_supervision_enablement_authority_not_granted",
      "persistent_supervision_execution_authority_not_granted",
    ]);
    assert.equal(handoffPresentation.sourceHandoffPreviousGap, "persistent_supervision_authority_not_granted");
    assert.equal(
      handoffPresentation.sourceHandoffConsumedAuditGap,
      "persistent_supervision_enablement_denial_boundary",
    );
    assert.equal(handoffPresentation.sourceHandoffEnablementDenialObserved, true);
    assert.equal(handoffPresentation.sourceHandoffExecutionDenialObserved, true);
    assert.equal(handoffPresentation.sourceHandoffPersistentSupervisionEnablementAuthority, false);
    assert.equal(handoffPresentation.sourceHandoffServiceConfigWriteAuthority, false);
    assert.equal(handoffPresentation.sourceHandoffPersistentSupervisionExecutionAuthority, false);
    assert.equal(handoffPresentation.sourceHandoffReceiptWriteAuthority, false);
    assert.equal(handoffPresentation.sourceHandoffResidentClaimAuthority, false);
    assert.equal(handoffPresentation.sourceHandoffResidentClaimAllowed, false);
    assert.equal(handoffPresentation.sourceHandoffServiceConfigUpdated, false);
    assert.equal(handoffPresentation.sourceHandoffApplied, false);
    assert.equal(handoffPresentation.sourceHandoffExecuted, false);
    assert.equal(handoffPresentation.source, "persistent_supervision_enablement_authority_denial_handoff");
    assert.equal(handoffPresentation.authority, "persistent_supervision_enablement_authority");
    assert.equal(handoffPresentation.stageGap, "summon_anywhere_blockers");
    assert.equal(handoffPresentation.currentGap, "persistent_supervision_enablement_authority_not_granted");
    assert.equal(
      handoffPresentation.currentHandoff,
      "prove_persistent_supervision_enablement_authority_after_candidate_handoff",
    );
    assert.equal(
      handoffPresentation.currentProof,
      "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status",
    );
    assert.equal(
      handoffPresentation.currentRoute,
      "/lens/host/persistent-supervision/enablement/authority/readiness",
    );
    assert.equal(
      handoffPresentation.currentRequestRoute,
      "/lens/host/persistent-supervision/enablement/authority/request",
    );
    assert.equal(handoffPresentation.currentGrantRoute, "/lens/host/persistent-supervision/enablement/authority");
    assert.equal(
      handoffPresentation.currentGrantsRoute,
      "/lens/host/persistent-supervision/enablement/authority/grants",
    );
    assert.equal(
      handoffPresentation.currentExecutionReadinessRoute,
      "/lens/host/persistent-supervision/enablement/execution/readiness",
    );
    assert.equal(handoffPresentation.firstBlockedCriterion, "summon_anywhere");
    assert.equal(handoffPresentation.firstBlockedCriterionGap, "");
    assert.equal(handoffPresentation.prerequisiteSource, "persistent_supervision_required_prerequisites_handoff");
    assert.equal(
      handoffPresentation.prerequisiteHandoff,
      "resolve_persistent_supervision_required_prerequisites_before_enablement",
    );
    assert.equal(
      handoffPresentation.prerequisiteProof,
      "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status",
    );
    assert.equal(handoffPresentation.prerequisiteRoute, "/lens/host/persistent-supervision/enablement");
    assert.equal(
      handoffPresentation.prerequisiteAuthority,
      "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
    );
    assert.deepEqual(handoffPresentation.missingPrerequisites, ["resident_host_process", "tray_presence"]);
    assert.equal(handoffPresentation.firstMissingPrerequisite, "resident_host_process");
    assert.equal(handoffPresentation.firstMissingSource, "persistent_supervision_first_missing_requirement_handoff");
    assert.equal(
      handoffPresentation.firstMissingHandoff,
      "resolve_resident_host_process_before_persistent_supervision_enablement",
    );
    assert.equal(
      handoffPresentation.firstMissingProof,
      "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
    );
    assert.equal(handoffPresentation.firstMissingRoute, "/lens/host/runtime-loop/readiness");
    assert.equal(handoffPresentation.firstMissingAuthority, "process_supervision_authority");
    assert.equal(snapshot.stage6_readiness.criteria[0]?.id, "hud_layer_runtime");
    assert.equal(snapshot.stage6_readiness.criteria[0]?.status, "readback_only");
    assert.equal(snapshot.stage6_readiness.criteria[0]?.resident_overlay, false);
    assert.equal(snapshot.stage6_readiness.criteria[0]?.blockers[0], "resident_overlay_runtime_missing");
    assert.equal(snapshot.stage6_readiness.criteria[1]?.id, "command_palette_commands");
    assert.equal(snapshot.stage6_readiness.criteria[1]?.status, "readback_ready");
    assert.equal(snapshot.stage6_readiness.criteria[2]?.pending_count, 2);
    assert.equal(snapshot.stage6_readiness.criteria[3]?.id, "host_activation_denial_receipt_readback");
    assert.equal(snapshot.stage6_readiness.criteria[3]?.receipt_count, 1);
    assert.equal(snapshot.stage6_readiness.criteria[3]?.latest_receipt_id, "lad_1770001000_alpha");
    assert.equal(snapshot.stage6_readiness.criteria[3]?.execution_authority, false);
    assert.equal(snapshot.stage6_readiness.criteria[4]?.id, "summon_anywhere");
    assert.equal(snapshot.stage6_readiness.criteria[4]?.status, "not_implemented");
    assert.equal(snapshot.stage6_readiness.criteria[5]?.id, "resident_supervision_enablement_gate");
    assert.equal(snapshot.stage6_readiness.criteria[5]?.ready, false);
    assert.equal(snapshot.stage6_readiness.criteria[5]?.resident_claim_allowed, false);
    assert.equal(snapshot.stage6_readiness.criteria[5]?.service_control_authority, false);
    assert.equal(snapshot.stage6_readiness.criteria[6]?.id, "summon_enablement_gate");
    assert.equal(snapshot.stage6_readiness.criteria[6]?.summon_anywhere, false);
    assert.equal(snapshot.stage6_readiness.criteria[6]?.global_hotkey, "Ctrl+Alt+Space");
    assert.equal(snapshot.stage6_readiness.criteria[6]?.hotkey_registration_authority, false);
    assert.equal(snapshot.stage6_readiness.criteria[7]?.id, "tray_enablement_gate");
    assert.equal(snapshot.stage6_readiness.criteria[7]?.tray_presence, false);
    assert.equal(snapshot.stage6_readiness.criteria[7]?.presence_name, "Francis Lens Tray Presence");
    assert.equal(snapshot.stage6_readiness.criteria[7]?.notification_authority, false);
    assert.equal(snapshot.stage6_readiness.criteria[8]?.id, "overlay_enablement_gate");
    assert.equal(snapshot.stage6_readiness.criteria[8]?.overlay_window, false);
    assert.equal(snapshot.stage6_readiness.criteria[8]?.overlay_name, "Francis Lens Overlay");
    assert.equal(snapshot.stage6_readiness.criteria[8]?.window_management_authority, false);
  } finally {
    restoreFetch();
  }
});

test("presentStage6NextHandoff returns an unloaded readback when the contract is missing", () => {
  assert.deepEqual(presentStage6NextHandoff(undefined), {
    loaded: false,
    kind: "",
    status: "readback",
    readyToClose: false,
    source: "",
    authority: "",
    readOnlyContract: false,
    diagnosticOnly: false,
    usesLensStatusReadback: false,
    executionAuthority: false,
    approvalDecisionAuthority: false,
    localProcessLaunchAuthority: false,
    processSupervisionAuthority: false,
    processRestartAuthority: false,
    serviceInstallAuthority: false,
    serviceControlAuthority: false,
    hotkeyRegistrationAuthority: false,
    trayRegistrationAuthority: false,
    overlayControlAuthority: false,
    summonAuthority: false,
    memoryWrite: false,
    receiptWriteAuthority: false,
    residentClaimAuthority: false,
    mutationAuthorityGranted: false,
    prerequisitesObserved: false,
    activationExecutionHandoffObserved: false,
    enablementAuthorityHandoffObserved: false,
    residentCandidateHandoffObserved: false,
    sourceHandoffLoaded: false,
    sourceHandoffId: "",
    sourceHandoffNextStep: "",
    sourceHandoffAcceptanceCriterion: "",
    sourceHandoffAuthorityRequired: "",
    sourceHandoffStatus: "",
    sourceHandoffReadOnlyContract: false,
    sourceHandoffDiagnosticOnly: false,
    sourceHandoffWouldExecute: false,
    sourceHandoffWouldMutate: false,
    sourceHandoffAuthorityGranted: false,
    sourceHandoffBlockers: [],
    sourceHandoffPreviousGap: "",
    sourceHandoffConsumedAuditGap: "",
    sourceHandoffEnablementDenialObserved: false,
    sourceHandoffExecutionDenialObserved: false,
    sourceHandoffPersistentSupervisionEnablementAuthority: false,
    sourceHandoffServiceConfigWriteAuthority: false,
    sourceHandoffPersistentSupervisionExecutionAuthority: false,
    sourceHandoffReceiptWriteAuthority: false,
    sourceHandoffResidentClaimAuthority: false,
    sourceHandoffResidentClaimAllowed: false,
    sourceHandoffServiceConfigUpdated: false,
    sourceHandoffApplied: false,
    sourceHandoffExecuted: false,
    stageGap: "",
    currentGap: "",
    currentHandoff: "",
    currentProof: "",
    currentRoute: "",
    currentRequestRoute: "",
    currentRequestsRoute: "",
    currentGrantRoute: "",
    currentGrantsRoute: "",
    currentDenialsRoute: "",
    currentExecutionReadinessRoute: "",
    firstBlockedCriterion: "",
    firstBlockedCriterionGap: "",
    prerequisiteSource: "",
    prerequisiteHandoff: "",
    prerequisiteProof: "",
    prerequisiteRoute: "",
    prerequisiteAuthority: "",
    missingPrerequisites: [],
    firstMissingPrerequisite: "",
    firstMissingSource: "",
    firstMissingHandoff: "",
    firstMissingProof: "",
    firstMissingRoute: "",
    firstMissingAuthority: "",
  });
});

test("parseLensStatus drops malformed nested items and preserves governance defaults", () => {
  const snapshot = parseLensStatus({
    ok: true,
    hud: {
      badges: [{ label: "mode", value: "assist" }, { value: "missing label" }],
      runtime: {
        blockers: ["resident_overlay_runtime_missing", 3, ""],
        governance: { overlay_control_authority: false },
      },
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
        { id: "hud_layer_runtime", status: "readback_only", resident_overlay: false, blockers: ["tray_host_missing"] },
        { status: "missing id" },
      ],
    },
    governance: {},
  });

  assert.equal(snapshot.hud.badges.length, 1);
  assert.equal(snapshot.hud.runtime.blockers.length, 1);
  assert.equal(snapshot.hud.runtime.blockers[0], "resident_overlay_runtime_missing");
  assert.equal(snapshot.hud.runtime.governance.overlay_control_authority, false);
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
  assert.equal(snapshot.stage6_readiness.criteria.length, 2);
  assert.equal(snapshot.stage6_readiness.closure_readback.ready_to_close, false);
  assert.equal(snapshot.stage6_readiness.closure_readback.criteria.length, 0);
  assert.equal(snapshot.stage6_readiness.criteria[1]?.resident_overlay, false);
  assert.equal(snapshot.stage6_readiness.criteria[1]?.blockers[0], "tray_host_missing");
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
