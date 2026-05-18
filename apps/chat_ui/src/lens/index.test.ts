import assert from "node:assert/strict";
import test from "node:test";

import {
  LensApiError,
  LensClient,
  parseLensStatus,
  presentPersistentSupervisionReadback,
  presentStage6NextHandoff,
  presentStage6PrerequisiteBringup,
  shouldOpenLensCommandPalette,
  shouldOpenLensStatusPanel,
  stage6PrerequisiteConfirmationMessage,
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
  const residentRuntimeExecutionReceipts = {
    ok: true,
    kind: "lens.resident_runtime.activation.execution_receipts",
    status: "readback_ready",
    route: "/lens/resident-runtime/executions",
    execute_route: "/lens/resident-runtime/execute",
    host_supervision_execute_route: "/lens/host/supervision/execute",
    host_supervision_executions_route: "/lens/host/supervision/executions",
    limit: "6",
    total: "1",
    latest_receipt_id: "lrte_1770001001_alpha",
    latest_status: "resident_supervision_started",
    latest_supervision_mode: "resident_start",
    latest_resident_host_process: true,
    latest_resident_supervised_runtime: true,
    latest_stop_command: "scripts/lens-host-supervisor.ps1 -Mode StopResident",
    latest_next_smallest_truthful_gap: "continue_with_tray_hotkey_overlay_summon_prerequisites",
    resident_supervised_runtime_receipt_observed: true,
    resident_claim_allowed: false,
    latest: { receipt_id: "lrte_1770001001_alpha", status: "resident_supervision_started" },
    items: [{ receipt_id: "lrte_1770001001_alpha", status: "resident_supervision_started" }],
    governance: {
      gate: "lens_resident_runtime_activation_execution_receipts_readback",
      read_only_contract: true,
      host_supervision_receipt_projection: true,
      execution_authority: false,
      process_supervision_authority: false,
      service_control_authority: false,
      memory_write: false,
      resident_claim_authority: false,
    },
  };
  const trayAuthorityRequests = {
    ok: true,
    kind: "lens.tray.presence_authority.request_readback",
    status: "approved_no_authority",
    route: "/lens/tray/authority/requests",
    request_route: "/lens/tray/authority/request",
    authority_route: "/lens/tray/authority",
    grants_route: "/lens/tray/authority/grants",
    execute_route: "/lens/tray/execute",
    executions_route: "/lens/tray/executions",
    action: "lens.tray.presence_authority",
    approval_counts: { pending: "0", approved: "1", rejected: "0", emergency: "0" },
    latest: {
      id: "appr_lens_tray_alpha",
      action: "lens.tray.presence_authority",
      status: "approved",
    },
    pending: [],
    approved: [
      {
        id: "appr_lens_tray_alpha",
        action: "lens.tray.presence_authority",
        status: "approved",
      },
    ],
    rejected: [],
    emergency: [],
    active_authority_grant: {},
    authority_granted: false,
    tray_presence_authority: false,
    tray_presence: false,
    registers_tray: false,
    starts_tray: false,
    stops_tray: false,
    governance: {
      gate: "lens_tray_presence_authority_request_readback",
      read_only_contract: true,
      execution_authority: false,
      approval_decision_authority: false,
      memory_write: false,
    },
  };
  const osBindingAuthorityRequests = {
    ok: true,
    kind: "lens.os_binding.command_palette_binding_authority.request_readback",
    status: "approved_no_authority",
    route: "/lens/os-binding/authority/requests",
    request_route: "/lens/os-binding/authority/request",
    authority_route: "/lens/os-binding/authority",
    grants_route: "/lens/os-binding/authority/grants",
    execute_route: "/lens/os-binding/execute",
    denials_route: "/lens/os-binding/denials",
    execution_readiness_route: "/lens/os-binding/execution/readiness",
    readiness_route: "/lens/os-binding/readiness",
    plan_route: "/lens/os-binding/plan",
    active_grant_receipt_id: "",
    approval_action: "lens.os_binding.command_palette_binding_authority",
    pending_count: "0",
    approved_count: "1",
    rejected_count: "0",
    emergency_count: "0",
    total_count: "1",
    latest: {
      id: "appr_lens_os_binding_alpha",
      action: "lens.os_binding.command_palette_binding_authority",
      status: "approved",
    },
    items: [
      {
        id: "appr_lens_os_binding_alpha",
        action: "lens.os_binding.command_palette_binding_authority",
        status: "approved",
      },
    ],
    by_status: {
      approved: [
        {
          id: "appr_lens_os_binding_alpha",
          action: "lens.os_binding.command_palette_binding_authority",
          status: "approved",
        },
      ],
    },
    authority_granted: false,
    os_level_command_palette_binding_authority: false,
    os_level_command_palette: false,
    registers_hotkey: false,
    governance: {
      gate: "lens_os_binding_command_palette_authority_request_readback",
      read_only_contract: true,
      execution_authority: false,
      approval_decision_authority: false,
      memory_write: false,
    },
  };
  const osBindingExecutionReadiness = {
    ok: true,
    kind: "lens.os_binding.command_palette_binding.execution_readiness",
    status: "blocked",
    route: "/lens/os-binding/execution/readiness",
    ready: false,
    execution_ready: false,
    authority_granted: false,
    os_level_command_palette: false,
    blocked_requirements: ["os_binding_authority_grant", "global_hotkey_binding"],
    blockers: ["os_level_command_palette_binding_authority_not_granted"],
    next_smallest_truthful_gap: "os_binding_execution_prerequisites",
    active_grant_receipt_id: "",
    governance: {
      gate: "lens_os_binding_command_palette_execution_readiness_audit",
      read_only_contract: true,
      execution_authority: false,
      approval_decision_authority: false,
      memory_write: false,
    },
  };
  const osBindingExecutionReceipts = {
    ok: true,
    kind: "lens.os_binding.command_palette_binding.execution_receipts",
    status: "empty",
    route: "/lens/os-binding/executions",
    execute_route: "/lens/os-binding/execute",
    authority_route: "/lens/os-binding/authority",
    authority_grants_route: "/lens/os-binding/authority/grants",
    limit: "6",
    total: "0",
    latest_status: "",
    latest_global_hotkey_binding: false,
    latest_next_smallest_truthful_gap: "",
    items: [],
    governance: {
      gate: "lens_os_binding_command_palette_execution_receipts_readback",
      read_only_contract: true,
      execution_authority: false,
      approval_decision_authority: false,
      memory_write: false,
    },
  };
  const trayExecutionReceipts = {
    ok: true,
    kind: "lens.tray.presence.execution_receipts",
    status: "empty",
    route: "/lens/tray/executions",
    execute_route: "/lens/tray/execute",
    authority_route: "/lens/tray/authority",
    authority_grants_route: "/lens/tray/authority/grants",
    limit: "6",
    total: "0",
    latest_status: "",
    latest_tray_presence: false,
    latest_next_smallest_truthful_gap: "",
    items: [],
    governance: {
      gate: "lens_tray_presence_execution_receipts_readback",
      read_only_contract: true,
      execution_authority: false,
      approval_decision_authority: false,
      memory_write: false,
    },
  };
  const overlayAuthorityRequests = {
    ok: true,
    kind: "lens.overlay.window_authority.request_readback",
    status: "approved_no_authority",
    route: "/lens/overlay/authority/requests",
    request_route: "/lens/overlay/authority/request",
    authority_route: "/lens/overlay/authority",
    grants_route: "/lens/overlay/authority/grants",
    execute_route: "/lens/overlay/execute",
    executions_route: "/lens/overlay/executions",
    action: "lens.overlay.window_authority",
    approval_counts: { pending: "0", approved: "1", rejected: "0", emergency: "0" },
    latest: {
      id: "appr_lens_overlay_alpha",
      action: "lens.overlay.window_authority",
      status: "approved",
    },
    pending: [],
    approved: [
      {
        id: "appr_lens_overlay_alpha",
        action: "lens.overlay.window_authority",
        status: "approved",
      },
    ],
    rejected: [],
    emergency: [],
    active_authority_grant: {},
    authority_granted: false,
    overlay_window_authority: false,
    overlay_window: false,
    governance: {
      gate: "lens_overlay_window_authority_request_readback",
      read_only_contract: true,
      execution_authority: false,
      approval_decision_authority: false,
      memory_write: false,
    },
  };
  const overlayExecutionReceipts = {
    ok: true,
    kind: "lens.overlay.window.execution_receipts",
    status: "empty",
    route: "/lens/overlay/executions",
    execute_route: "/lens/overlay/execute",
    authority_route: "/lens/overlay/authority",
    authority_grants_route: "/lens/overlay/authority/grants",
    limit: "6",
    total: "0",
    latest_status: "",
    latest_overlay_window: false,
    latest_next_smallest_truthful_gap: "",
    items: [],
    governance: {
      gate: "lens_overlay_window_execution_receipts_readback",
      read_only_contract: true,
      execution_authority: false,
      approval_decision_authority: false,
      memory_write: false,
    },
  };
  const summonAuthorityRequests = {
    ok: true,
    kind: "lens.summon.action_authority.request_readback",
    status: "approved_no_authority",
    route: "/lens/summon/authority/requests",
    request_route: "/lens/summon/authority/request",
    authority_route: "/lens/summon/authority",
    grants_route: "/lens/summon/authority/grants",
    execute_route: "/lens/summon/execute",
    executions_route: "/lens/summon/executions",
    action: "lens.summon.action_authority",
    approval_counts: { pending: "0", approved: "1", rejected: "0", emergency: "0" },
    latest: {
      id: "appr_lens_summon_alpha",
      action: "lens.summon.action_authority",
      status: "approved",
    },
    pending: [],
    approved: [
      {
        id: "appr_lens_summon_alpha",
        action: "lens.summon.action_authority",
        status: "approved",
      },
    ],
    rejected: [],
    emergency: [],
    active_authority_grant: {},
    authority_granted: false,
    summon_binding: false,
    summon_anywhere: false,
    governance: {
      gate: "lens_summon_action_authority_request_readback",
      read_only_contract: true,
      execution_authority: false,
      approval_decision_authority: false,
      memory_write: false,
    },
  };
  const summonExecutionReceipts = {
    ok: true,
    kind: "lens.summon.action.execution_receipts",
    status: "empty",
    route: "/lens/summon/executions",
    execute_route: "/lens/summon/execute",
    authority_route: "/lens/summon/authority",
    authority_grants_route: "/lens/summon/authority/grants",
    limit: "6",
    total: "0",
    latest_status: "",
    latest_summon_binding: false,
    latest_summon_anywhere: false,
    latest_next_smallest_truthful_gap: "",
    items: [],
    governance: {
      gate: "lens_summon_action_execution_receipts_readback",
      read_only_contract: true,
      execution_authority: false,
      approval_decision_authority: false,
      memory_write: false,
    },
  };
  const residentRuntimeAuthorityReadiness = {
    ok: true,
    kind: "lens.resident_runtime.execution_authority_grant.readiness_audit",
    status: "blocked",
    audit_status: "complete",
    route: "/lens/resident-runtime/authority-grant/readiness",
    preflight_route: "/lens/resident-runtime/preflight",
    policy_route: "/lens/resident-runtime/policy",
    authority_grant_route: "/lens/resident-runtime/authority-grant",
    authority_grants_route: "/lens/resident-runtime/authority-grant/grants",
    denials_route: "/lens/resident-runtime/denials",
    plan_route: "/lens/resident-runtime/plan",
    execute_route: "/lens/resident-runtime/execute",
    ready: false,
    grant_ready: false,
    authority_grant_ready: false,
    runtime_ready: false,
    resident_claim_allowed: false,
    boundary_observed: true,
    authority_granted: false,
    resident_runtime_execution_authority: false,
    denial_receipt_readback_ready: true,
    grant_receipt_readback_ready: true,
    receipt_count: "0",
    denial_receipt_count: "1",
    latest_denial_receipt_id: "lrtd_1770001002_alpha",
    requirements_total: "3",
    requirements_ready_total: "1",
    requirements_blocked_total: "2",
    requirements: [
      { id: "authority_grant_denial_receipts", ready: true },
      { id: "resident_supervision_gate", ready: false },
      { id: "resident_runtime_execution_authority", ready: false },
    ],
    blocked_requirements: ["resident_supervision_gate", "resident_runtime_execution_authority"],
    operator_surface_readback_ready: true,
    first_blocked_requirement: "resident_supervision_gate",
    first_blocked_requirement_handoff: {
      id: "resident_supervision_gate",
      label: "Resident supervision and service gates",
      status: "blocked",
      route: "/lens/host/supervision",
      readiness_route: "/lens/resident-runtime/authority-grant/readiness",
      host_route: "/lens/host",
      manifest_route: "/lens/host/manifest",
      supervision_route: "/lens/host/supervision",
      next_step: "resolve_resident_host_supervision_gate_blockers_before_runtime_authority_use",
      authority_required: "process_supervision_and_service_control",
      authority_granted: false,
      blockers: ["resident_host_process_missing"],
      would_execute: false,
      would_mutate: false,
    },
    blocked_requirement_handoffs: [
      {
        id: "resident_supervision_gate",
        status: "blocked",
        route: "/lens/host/supervision",
        readiness_route: "/lens/resident-runtime/authority-grant/readiness",
        next_step: "resolve_resident_host_supervision_gate_blockers_before_runtime_authority_use",
        authority_required: "process_supervision_and_service_control",
        authority_granted: false,
        blockers: ["resident_host_process_missing"],
        would_execute: false,
        would_mutate: false,
      },
    ],
    blockers: ["resident_host_process_missing", "resident_runtime_execution_authority_not_granted"],
    next_smallest_truthful_gap: "resolve_resident_host_supervision_gate_blockers_before_runtime_authority_use",
    source_readbacks: {
      preflight_status: "blocked",
      authority_grant_status: "denied_no_approval",
      plan_status: "blocked",
    },
    governance: {
      gate: "lens_resident_runtime_execution_authority_grant_readiness_audit",
      read_only_contract: true,
      audit_only: true,
      resident_runtime_boundary: true,
      execution_authority: false,
      resident_runtime_execution_authority: false,
      approval_decision_authority: false,
      local_process_launch_authority: false,
      process_supervision_authority: false,
      service_control_authority: false,
      memory_write: false,
      receipt_write_authority: false,
      resident_claim_authority: false,
      runtime_mutation_authority_granted: false,
      authority_granted: false,
    },
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
        supervision_authority_request_route: "/lens/host/supervision/authority/request",
        supervision_authority_requests_route: "/lens/host/supervision/authority/requests",
        supervision_authority_requests: {
          ok: true,
          kind: "lens.host.supervision_authority.request_readback",
          status: "approved_no_authority",
          route: "/lens/host/supervision/authority/requests",
          request_route: "/lens/host/supervision/authority/request",
          grant_route: "/lens/host/supervision/authority",
          grants_route: "/lens/host/supervision/authority/grants",
          readiness_route: "/lens/host/supervision/authority/readiness",
          active_grant_receipt_id: "",
          decision_route: "/approvals/decision",
          approval_action: "lens.host.supervision_authority",
          pending_count: "0",
          approved_count: "1",
          rejected_count: "0",
          emergency_count: "0",
          total_count: "1",
          latest: {
            id: "appr_lens_host_supervision_alpha",
            action: "lens.host.supervision_authority",
            status: "approved",
          },
          items: [
            {
              id: "appr_lens_host_supervision_alpha",
              action: "lens.host.supervision_authority",
              status: "approved",
            },
          ],
          by_status: {
            approved: [
              {
                id: "appr_lens_host_supervision_alpha",
                action: "lens.host.supervision_authority",
                status: "approved",
              },
            ],
          },
          authority_granted: false,
          resident_claim_allowed: false,
          governance: {
            gate: "lens_host_supervision_authority_request_readback",
            read_only_contract: true,
            approval_request_write: false,
            process_supervision_authority: false,
          },
        },
        resident_runtime_authority_grant_readiness_route: "/lens/resident-runtime/authority-grant/readiness",
        resident_runtime_authority_request_route: "/lens/resident-runtime/authority-grant/request",
        resident_runtime_authority_requests_route: "/lens/resident-runtime/authority-grant/requests",
        resident_runtime_authority_requests: {
          ok: true,
          kind: "lens.resident_runtime.execution_authority.request_readback",
          status: "approved_no_authority",
          route: "/lens/resident-runtime/authority-grant/requests",
          request_route: "/lens/resident-runtime/authority-grant/request",
          grant_route: "/lens/resident-runtime/authority-grant",
          grants_route: "/lens/resident-runtime/authority-grant/grants",
          readiness_route: "/lens/resident-runtime/authority-grant/readiness",
          denials_route: "/lens/resident-runtime/authority-grant/denials",
          active_grant_receipt_id: "",
          policy_route: "/lens/resident-runtime/policy",
          plan_route: "/lens/resident-runtime/plan",
          execute_route: "/lens/resident-runtime/execute",
          decision_route: "/approvals/decision",
          approval_action: "lens.resident_runtime.execution_authority",
          pending_count: "0",
          approved_count: "1",
          rejected_count: "0",
          emergency_count: "0",
          total_count: "1",
          latest: {
            id: "appr_lens_resident_runtime_alpha",
            action: "lens.resident_runtime.execution_authority",
            status: "approved",
          },
          items: [
            {
              id: "appr_lens_resident_runtime_alpha",
              action: "lens.resident_runtime.execution_authority",
              status: "approved",
            },
          ],
          by_status: {
            approved: [
              {
                id: "appr_lens_resident_runtime_alpha",
                action: "lens.resident_runtime.execution_authority",
                status: "approved",
              },
            ],
          },
          authority_granted: false,
          resident_runtime_execution_authority: false,
          resident_claim_allowed: false,
          execution_authority: false,
          local_process_launch_authority: false,
          process_supervision_authority: false,
          service_control_authority: false,
          receipt_write_authority: false,
          memory_write: false,
          governance: {
            gate: "lens_resident_runtime_execution_authority_request_readback",
            read_only_contract: true,
            resident_runtime_execution_authority: false,
            approval_request_write: false,
          },
        },
        resident_runtime_authority_grant_readiness: residentRuntimeAuthorityReadiness,
        resident_runtime_execution_receipts_route: "/lens/resident-runtime/executions",
        resident_runtime_execution_receipts: residentRuntimeExecutionReceipts,
        runtime_loop_readiness_route: "/lens/host/runtime-loop/readiness",
        runtime_loop_readiness: runtimeLoopReadiness,
      },
      os_binding_authority_requests: osBindingAuthorityRequests,
      os_binding_execution_readiness: osBindingExecutionReadiness,
      os_binding_execution_receipts: osBindingExecutionReceipts,
      tray_authority_requests: trayAuthorityRequests,
      tray_execution_receipts: trayExecutionReceipts,
      overlay_authority_requests: overlayAuthorityRequests,
      overlay_execution_receipts: overlayExecutionReceipts,
      summon_authority_requests: summonAuthorityRequests,
      summon_execution_receipts: summonExecutionReceipts,
      receipts: {
        status: "readback_ready",
        continuity_ledger_route: "/continuity/ledger",
        lens_host_activation_denials_route: "/lens/host/activation/denials",
        lens_host_runtime_loop_readiness_route: "/lens/host/runtime-loop/readiness",
        lens_resident_runtime_authority_grant_readiness_route: "/lens/resident-runtime/authority-grant/readiness",
        lens_resident_runtime_executions_route: "/lens/resident-runtime/executions",
        lens_os_binding_authority_request_route: "/lens/os-binding/authority/request",
        lens_os_binding_execute_route: "/lens/os-binding/execute",
        lens_tray_authority_request_route: "/lens/tray/authority/request",
        lens_tray_execute_route: "/lens/tray/execute",
        lens_overlay_authority_request_route: "/lens/overlay/authority/request",
        lens_overlay_execute_route: "/lens/overlay/execute",
        lens_summon_authority_request_route: "/lens/summon/authority/request",
        lens_summon_execute_route: "/lens/summon/execute",
      },
      resident_runtime_authority_grant_readiness: residentRuntimeAuthorityReadiness,
      resident_runtime_execution_receipts: residentRuntimeExecutionReceipts,
      os_binding_authority_requests: osBindingAuthorityRequests,
      os_binding_execution_readiness: osBindingExecutionReadiness,
      os_binding_execution_receipts: osBindingExecutionReceipts,
      tray_authority_requests: trayAuthorityRequests,
      tray_execution_receipts: trayExecutionReceipts,
      overlay_authority_requests: overlayAuthorityRequests,
      overlay_execution_receipts: overlayExecutionReceipts,
      summon_authority_requests: summonAuthorityRequests,
      summon_execution_receipts: summonExecutionReceipts,
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
        prerequisite_bringup: {
          ok: true,
          kind: "lens.stage6.prerequisite_bringup.plan",
          status: "blocked",
          mode: "status",
          stage: "Stage 6 / Lens MVP",
          stage_state: "active",
          ready_to_close: false,
          acceptance_criterion: "system_resident_presence",
          closure_next_smallest_truthful_gap: "summon_anywhere_blockers",
          persistent_supervision_next_smallest_truthful_gap: "persistent_supervision_authority_not_granted",
          current_truthful_gap: "persistent_supervision_required_prerequisites_missing",
          current_truthful_gap_basis: "missing_required_before_enable",
          current_first_missing_requirement: "resident_host_process",
          current_first_missing_truthful_gap: "resident_host_process_not_supervised",
          raw_persistent_supervision_next_smallest_truthful_gap: "persistent_supervision_authority_not_granted",
          required_before_enable: ["resident_host_process", "tray_presence"],
          missing_required_before_enable: ["resident_host_process", "tray_presence"],
          required_before_enable_ready: false,
          first_missing_required_before_enable: "resident_host_process",
          first_missing_requirement_handoff: {
            id: "resident_host_process",
            read_only_contract: true,
            diagnostic_only: true,
            would_execute: false,
            would_mutate: false,
          },
          ordered_prerequisite_steps: [
            {
              id: "resident_host_process",
              family: "resident_host",
              route: "/lens/host",
              readiness_route: "/lens/host/runtime-loop/readiness",
              ready: false,
              status: "blocked",
              requirement_state: "missing",
              blocker: "resident_host_process_missing",
              blocked_reason: "resident_host_process_missing",
              proof_script: "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
              next_smallest_truthful_gap: "resident_host_process_not_supervised",
              authority_state: {
                resident_runtime: {
                  authority_granted: false,
                },
                host_supervision: {
                  authority_granted: false,
                },
              },
              actions: [
                {
                  id: "request_resident_runtime_execution_authority",
                  route: "/lens/resident-runtime/authority-grant/request",
                  method: "POST",
                  approval_action: "lens.resident_runtime.execution_authority",
                  requires: ["actor with system.write scope"],
                  live_effect: "approval request receipt only",
                  script_would_execute: false,
                  script_would_mutate: false,
                },
              ],
              next_operator_action: {
                id: "request_resident_runtime_execution_authority",
                route: "/lens/resident-runtime/authority-grant/request",
                method: "POST",
                approval_action: "lens.resident_runtime.execution_authority",
                requires: ["actor with system.write scope"],
                live_effect: "approval request receipt only",
                script_would_execute: false,
                script_would_mutate: false,
              },
              script_would_execute: false,
              script_would_mutate: false,
            },
          ],
          persistent_supervision_enablement_steps: [
            {
              id: "request_persistent_supervision_enablement_authority",
              route: "/lens/host/persistent-supervision/enablement/authority/request",
              method: "POST",
              approval_action: "lens.host.persistent_supervision_enablement_authority",
              requires: ["all required prerequisite surfaces ready", "actor with system.write scope"],
              live_effect: "persistent supervision enablement authority request receipt only",
              script_would_execute: false,
              script_would_mutate: false,
            },
          ],
          next_operator_action: {
            id: "request_resident_runtime_execution_authority",
            route: "/lens/resident-runtime/authority-grant/request",
            method: "POST",
            approval_action: "lens.resident_runtime.execution_authority",
            requires: ["actor with system.write scope"],
            live_effect: "approval request receipt only",
            script_would_execute: false,
            script_would_mutate: false,
          },
          next_operator_action_requirement: "resident_host_process",
          next_operator_command: {
            command:
              ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
            mode: "RequestNext",
            requires_confirmation: true,
            requires_approval_id: false,
            requires_operator_approval_decision: false,
          },
          operator_sequence: [
            {
              id: "request_resident_runtime_execution_authority",
              route: "/lens/resident-runtime/authority-grant/request",
              method: "POST",
              approval_action: "lens.resident_runtime.execution_authority",
              requires: ["actor with system.write scope"],
              live_effect: "approval request receipt only",
              script_would_execute: false,
              script_would_mutate: false,
              operator_command: {
                command:
                  ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
                mode: "RequestNext",
                requires_confirmation: true,
                requires_approval_id: false,
                requires_operator_approval_decision: false,
                available_now: true,
                preview_only: false,
                availability_reason: "current_next_operator_action",
              },
            },
          ],
          operator_sequence_command_availability: {
            available_now_count: 1,
            preview_only_count: 0,
            sequence_length: 1,
            truthful: true,
          },
          checks: [
            {
              id: "operator_sequence_command_availability",
              status: "truthful",
              passed: true,
              evidence: "stage6_readiness.prerequisite_bringup.operator_sequence.operator_command",
              reason:
                "Exactly one operator-sequence command may be available now; all future steps must remain preview-only.",
            },
            {
              id: "stage6_status_readback",
              status: "active",
              passed: true,
              evidence: "stage6_readiness.prerequisite_bringup",
              reason: "The bring-up plan is only valid against the active Stage 6 Lens posture.",
            },
            { id: "status_mode_side_effects_denied", passed: true },
          ],
          evidence: ["/lens/status"],
          governance: {
            read_only_contract: true,
            diagnostic_only: true,
            plan_only: true,
            uses_lens_status_readback: true,
            requires_explicit_operator_execution: true,
            request_next_mode_available: true,
            grant_next_mode_available: true,
            execute_next_mode_available: true,
            approval_request_write: false,
            authority_grant_receipt_write: false,
            execution_receipt_write: false,
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
    assert.equal(
      snapshot.resident_host.supervision_authority_request_route,
      "/lens/host/supervision/authority/request",
    );
    assert.equal(snapshot.resident_host.supervision_authority_requests.status, "approved_no_authority");
    assert.equal(snapshot.resident_host.supervision_authority_requests.approved_count, 1);
    assert.equal(snapshot.resident_host.supervision_authority_requests.authority_granted, false);
    assert.equal(
      snapshot.resident_host.supervision_authority_requests.by_status.approved?.[0]?.id,
      "appr_lens_host_supervision_alpha",
    );
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_request_route,
      "/lens/resident-runtime/authority-grant/request",
    );
    assert.equal(snapshot.resident_host.resident_runtime_authority_requests.status, "approved_no_authority");
    assert.equal(snapshot.resident_host.resident_runtime_authority_requests.approved_count, 1);
    assert.equal(snapshot.resident_host.resident_runtime_authority_requests.authority_granted, false);
    assert.equal(snapshot.resident_host.resident_runtime_authority_requests.resident_runtime_execution_authority, false);
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_requests.by_status.approved?.[0]?.id,
      "appr_lens_resident_runtime_alpha",
    );
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_grant_readiness_route,
      "/lens/resident-runtime/authority-grant/readiness",
    );
    assert.equal(snapshot.resident_host.resident_runtime_authority_grant_readiness.status, "blocked");
    assert.equal(snapshot.resident_host.resident_runtime_authority_grant_readiness.ready, false);
    assert.equal(snapshot.resident_host.resident_runtime_authority_grant_readiness.runtime_ready, false);
    assert.equal(snapshot.resident_host.resident_runtime_authority_grant_readiness.authority_granted, false);
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_grant_readiness.resident_runtime_execution_authority,
      false,
    );
    assert.equal(snapshot.resident_host.resident_runtime_authority_grant_readiness.requirements_total, 3);
    assert.equal(snapshot.resident_host.resident_runtime_authority_grant_readiness.requirements_ready_total, 1);
    assert.equal(snapshot.resident_host.resident_runtime_authority_grant_readiness.requirements_blocked_total, 2);
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_grant_readiness.first_blocked_requirement,
      "resident_supervision_gate",
    );
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_grant_readiness.first_blocked_requirement_handoff?.next_step,
      "resolve_resident_host_supervision_gate_blockers_before_runtime_authority_use",
    );
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_grant_readiness.first_blocked_requirement_handoff
        ?.authority_required,
      "process_supervision_and_service_control",
    );
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_grant_readiness.first_blocked_requirement_handoff?.blockers[0],
      "resident_host_process_missing",
    );
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_grant_readiness.next_smallest_truthful_gap,
      "resolve_resident_host_supervision_gate_blockers_before_runtime_authority_use",
    );
    assert.equal(
      snapshot.resident_host.resident_runtime_authority_grant_readiness.governance.execution_authority,
      false,
    );
    assert.equal(snapshot.resident_host.resident_runtime_execution_receipts_route, "/lens/resident-runtime/executions");
    assert.equal(snapshot.resident_host.resident_runtime_execution_receipts.total, 1);
    assert.equal(snapshot.resident_host.resident_runtime_execution_receipts.latest_receipt_id, "lrte_1770001001_alpha");
    assert.equal(snapshot.resident_host.resident_runtime_execution_receipts.latest_status, "resident_supervision_started");
    assert.equal(snapshot.resident_host.resident_runtime_execution_receipts.latest_supervision_mode, "resident_start");
    assert.equal(snapshot.resident_host.resident_runtime_execution_receipts.latest_resident_host_process, true);
    assert.equal(snapshot.resident_host.resident_runtime_execution_receipts.latest_resident_supervised_runtime, true);
    assert.equal(
      snapshot.resident_host.resident_runtime_execution_receipts.resident_supervised_runtime_receipt_observed,
      true,
    );
    assert.equal(snapshot.resident_host.resident_runtime_execution_receipts.resident_claim_allowed, false);
    assert.equal(snapshot.resident_host.resident_runtime_execution_receipts.governance.execution_authority, false);
    assert.equal(snapshot.os_binding_authority_requests.status, "approved_no_authority");
    assert.equal(snapshot.os_binding_authority_requests.request_route, "/lens/os-binding/authority/request");
    assert.equal(snapshot.os_binding_authority_requests.authority_route, "/lens/os-binding/authority");
    assert.equal(snapshot.os_binding_authority_requests.execute_route, "/lens/os-binding/execute");
    assert.equal(snapshot.os_binding_authority_requests.approved_count, 1);
    assert.equal(snapshot.os_binding_authority_requests.by_status.approved[0]?.id, "appr_lens_os_binding_alpha");
    assert.equal(snapshot.os_binding_authority_requests.authority_granted, false);
    assert.equal(snapshot.os_binding_execution_readiness.status, "blocked");
    assert.equal(snapshot.os_binding_execution_readiness.blocked_requirements[0], "os_binding_authority_grant");
    assert.equal(snapshot.os_binding_execution_receipts.status, "empty");
    assert.equal(snapshot.os_binding_execution_receipts.execute_route, "/lens/os-binding/execute");
    assert.equal(snapshot.os_binding_execution_receipts.total, 0);
    assert.equal(snapshot.os_binding_execution_receipts.latest_global_hotkey_binding, false);
    assert.equal(snapshot.tray_authority_requests.status, "approved_no_authority");
    assert.equal(snapshot.tray_authority_requests.request_route, "/lens/tray/authority/request");
    assert.equal(snapshot.tray_authority_requests.authority_route, "/lens/tray/authority");
    assert.equal(snapshot.tray_authority_requests.execute_route, "/lens/tray/execute");
    assert.equal(snapshot.tray_authority_requests.approval_counts.approved, 1);
    assert.equal(snapshot.tray_authority_requests.approved[0]?.id, "appr_lens_tray_alpha");
    assert.equal(snapshot.tray_authority_requests.authority_granted, false);
    assert.equal(snapshot.tray_execution_receipts.status, "empty");
    assert.equal(snapshot.tray_execution_receipts.execute_route, "/lens/tray/execute");
    assert.equal(snapshot.tray_execution_receipts.total, 0);
    assert.equal(snapshot.tray_execution_receipts.latest_tray_presence, false);
    assert.equal(snapshot.overlay_authority_requests.status, "approved_no_authority");
    assert.equal(snapshot.overlay_authority_requests.request_route, "/lens/overlay/authority/request");
    assert.equal(snapshot.overlay_authority_requests.authority_route, "/lens/overlay/authority");
    assert.equal(snapshot.overlay_authority_requests.execute_route, "/lens/overlay/execute");
    assert.equal(snapshot.overlay_authority_requests.approval_counts.approved, 1);
    assert.equal(snapshot.overlay_authority_requests.approved[0]?.id, "appr_lens_overlay_alpha");
    assert.equal(snapshot.overlay_authority_requests.authority_granted, false);
    assert.equal(snapshot.overlay_execution_receipts.status, "empty");
    assert.equal(snapshot.overlay_execution_receipts.execute_route, "/lens/overlay/execute");
    assert.equal(snapshot.overlay_execution_receipts.total, 0);
    assert.equal(snapshot.overlay_execution_receipts.latest_overlay_window, false);
    assert.equal(snapshot.summon_authority_requests.status, "approved_no_authority");
    assert.equal(snapshot.summon_authority_requests.request_route, "/lens/summon/authority/request");
    assert.equal(snapshot.summon_authority_requests.authority_route, "/lens/summon/authority");
    assert.equal(snapshot.summon_authority_requests.execute_route, "/lens/summon/execute");
    assert.equal(snapshot.summon_authority_requests.approval_counts.approved, 1);
    assert.equal(snapshot.summon_authority_requests.approved[0]?.id, "appr_lens_summon_alpha");
    assert.equal(snapshot.summon_authority_requests.authority_granted, false);
    assert.equal(snapshot.summon_execution_receipts.status, "empty");
    assert.equal(snapshot.summon_execution_receipts.execute_route, "/lens/summon/execute");
    assert.equal(snapshot.summon_execution_receipts.total, 0);
    assert.equal(snapshot.summon_execution_receipts.latest_summon_binding, false);
    assert.equal(snapshot.summon_execution_receipts.latest_summon_anywhere, false);
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
    assert.equal(snapshot.receipts.lens_resident_runtime_executions_route, "/lens/resident-runtime/executions");
    assert.equal(
      snapshot.resident_runtime_authority_grant_readiness.route,
      "/lens/resident-runtime/authority-grant/readiness",
    );
    assert.equal(snapshot.resident_runtime_authority_grant_readiness.execute_route, "/lens/resident-runtime/execute");
    assert.equal(snapshot.resident_runtime_authority_grant_readiness.blocked_requirements[0], "resident_supervision_gate");
    assert.equal(snapshot.resident_runtime_execution_receipts.route, "/lens/resident-runtime/executions");
    assert.equal(snapshot.resident_runtime_execution_receipts.resident_claim_allowed, false);
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
    assert.equal(snapshot.stage6_readiness.prerequisite_bringup.kind, "lens.stage6.prerequisite_bringup.plan");
    assert.equal(snapshot.stage6_readiness.prerequisite_bringup.status, "blocked");
    assert.equal(
      snapshot.stage6_readiness.prerequisite_bringup.current_truthful_gap,
      "persistent_supervision_required_prerequisites_missing",
    );
    assert.equal(
      snapshot.stage6_readiness.prerequisite_bringup.current_first_missing_requirement,
      "resident_host_process",
    );
    assert.equal(
      snapshot.stage6_readiness.prerequisite_bringup.next_operator_action.id,
      "request_resident_runtime_execution_authority",
    );
    assert.equal(
      snapshot.stage6_readiness.prerequisite_bringup.next_operator_action.route,
      "/lens/resident-runtime/authority-grant/request",
    );
    assert.equal(snapshot.stage6_readiness.prerequisite_bringup.next_operator_command.mode, "RequestNext");
    assert.equal(snapshot.stage6_readiness.prerequisite_bringup.next_operator_command.requires_confirmation, true);
    assert.equal(snapshot.stage6_readiness.prerequisite_bringup.next_operator_command.requires_approval_id, false);
    assert.equal(snapshot.stage6_readiness.prerequisite_bringup.ordered_prerequisite_steps[0]?.id, "resident_host_process");
    assert.equal(
      snapshot.stage6_readiness.prerequisite_bringup.ordered_prerequisite_steps[0]?.next_operator_action.id,
      "request_resident_runtime_execution_authority",
    );
    assert.equal(snapshot.stage6_readiness.prerequisite_bringup.governance.approval_request_write, false);
    assert.equal(snapshot.stage6_readiness.prerequisite_bringup.governance.mutation_authority_granted, false);
    const prerequisiteBringupFixture = snapshot.stage6_readiness.prerequisite_bringup;
    const prerequisiteBringup = presentStage6PrerequisiteBringup(prerequisiteBringupFixture);
    assert.equal(prerequisiteBringup.loaded, true);
    assert.equal(prerequisiteBringup.status, "blocked");
    assert.equal(prerequisiteBringup.currentGap, "persistent_supervision_required_prerequisites_missing");
    assert.equal(prerequisiteBringup.firstMissingRequirement, "resident_host_process");
    assert.equal(prerequisiteBringup.nextActionId, "request_resident_runtime_execution_authority");
    assert.equal(prerequisiteBringup.nextActionRoute, "/lens/resident-runtime/authority-grant/request");
    assert.equal(prerequisiteBringup.approvedApprovalId, "");
    assert.equal(prerequisiteBringup.activeApprovalId, "");
    assert.equal(prerequisiteBringup.hostSupervisionActiveApprovalId, "");
    assert.equal(prerequisiteBringup.commandMode, "RequestNext");
    assert.equal(prerequisiteBringup.requiresConfirmation, true);
    assert.equal(
      stage6PrerequisiteConfirmationMessage(prerequisiteBringup),
      "Confirm RequestNext for request_resident_runtime_execution_authority?\n\n.\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
    );
    assert.equal(
      stage6PrerequisiteConfirmationMessage({ nextActionId: "", commandMode: "", command: "" }),
      "Confirm for next Stage 6 action?",
    );
    assert.deepEqual(
      prerequisiteBringup.operatorSequence.map((item) => item.id),
      ["request_resident_runtime_execution_authority"],
    );
    assert.equal(prerequisiteBringup.operatorSequence[0]?.current, true);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.index, 1);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.route, "/lens/resident-runtime/authority-grant/request");
    assert.equal(prerequisiteBringup.operatorSequence[0]?.method, "POST");
    assert.equal(prerequisiteBringup.operatorSequence[0]?.approvalAction, "lens.resident_runtime.execution_authority");
    assert.equal(prerequisiteBringup.operatorSequence[0]?.liveEffect, "approval request receipt only");
    assert.equal(
      prerequisiteBringup.operatorSequence[0]?.command,
      ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
    );
    assert.equal(prerequisiteBringup.operatorSequence[0]?.commandMode, "RequestNext");
    assert.equal(prerequisiteBringup.operatorSequence[0]?.commandRequiresConfirmation, true);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.commandRequiresApprovalId, false);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.commandRequiresOperatorApprovalDecision, false);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.commandAvailableNow, true);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.commandPreviewOnly, false);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.commandAvailabilityReason, "current_next_operator_action");
    assert.deepEqual(prerequisiteBringup.operatorSequence[0]?.requires, ["actor with system.write scope"]);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.operatorSuppliedValuesRequired, false);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.wouldExecute, false);
    assert.equal(prerequisiteBringup.operatorSequence[0]?.wouldMutate, false);
    assert.deepEqual(prerequisiteBringup.operatorSequenceCommandAvailability, {
      availableNowCount: 1,
      previewOnlyCount: 0,
      sequenceLength: 1,
      truthful: true,
    });
    assert.deepEqual(prerequisiteBringup.operatorSequenceCommandAvailabilityCheck, {
      id: "operator_sequence_command_availability",
      status: "truthful",
      passed: true,
      evidence: "stage6_readiness.prerequisite_bringup.operator_sequence.operator_command",
      reason: "Exactly one operator-sequence command may be available now; all future steps must remain preview-only.",
    });
    assert.deepEqual(
      prerequisiteBringup.checks.map((check) => [check.id, check.status, check.passed]),
      [
        ["operator_sequence_command_availability", "truthful", true],
        ["stage6_status_readback", "active", true],
        ["status_mode_side_effects_denied", "", true],
      ],
    );
    assert.equal(
      prerequisiteBringup.checks[0]?.evidence,
      "stage6_readiness.prerequisite_bringup.operator_sequence.operator_command",
    );
    assert.equal(
      prerequisiteBringup.checks[0]?.reason,
      "Exactly one operator-sequence command may be available now; all future steps must remain preview-only.",
    );
    const fullSequenceBringup = presentStage6PrerequisiteBringup({
      ...prerequisiteBringupFixture,
      operator_sequence_command_availability: {
        available_now_count: 1,
        preview_only_count: 4,
        sequence_length: 5,
        truthful: true,
      },
      operator_sequence: [
        prerequisiteBringupFixture.next_operator_action,
        {
          id: "request_tray_presence_authority",
          route: "/lens/tray/authority/request",
          method: "POST",
          approval_action: "lens.tray.presence_authority",
          requires: ["actor with system.write scope"],
          live_effect: "approval request receipt only",
          operator_supplied_values_required: true,
          script_would_execute: false,
          script_would_mutate: false,
          operator_command: {
            command:
              ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
            mode: "RequestNext",
            requires_confirmation: true,
            requires_approval_id: false,
            requires_operator_approval_decision: false,
            available_now: false,
            preview_only: true,
            availability_reason: "future_step_waiting_on_prior_prerequisites",
          },
        },
        {
          id: "request_global_hotkey_binding_authority",
          route: "/lens/os-binding/authority/request",
          method: "POST",
          approval_action: "lens.os_binding.command_palette_binding_authority",
          requires: ["actor with system.write scope"],
          live_effect: "approval request receipt only",
          operator_supplied_values_required: true,
          script_would_execute: false,
          script_would_mutate: false,
        },
        {
          id: "request_overlay_window_authority",
          route: "/lens/overlay/authority/request",
          method: "POST",
          approval_action: "lens.overlay.window_authority",
          requires: ["actor with system.write scope"],
          live_effect: "approval request receipt only",
          operator_supplied_values_required: true,
          script_would_execute: false,
          script_would_mutate: false,
        },
        {
          id: "request_summon_binding_authority",
          route: "/lens/summon/authority/request",
          method: "POST",
          approval_action: "lens.summon.action_authority",
          requires: ["actor with system.write scope"],
          live_effect: "approval request receipt only",
          operator_supplied_values_required: true,
          script_would_execute: false,
          script_would_mutate: false,
        },
      ],
    });
    assert.deepEqual(
      fullSequenceBringup.operatorSequence.map((item) => item.id),
      [
        "request_resident_runtime_execution_authority",
        "request_tray_presence_authority",
        "request_global_hotkey_binding_authority",
        "request_overlay_window_authority",
        "request_summon_binding_authority",
      ],
    );
    assert.equal(fullSequenceBringup.operatorSequence[0]?.current, true);
    assert.equal(fullSequenceBringup.operatorSequence[1]?.current, false);
    assert.equal(fullSequenceBringup.operatorSequence[1]?.operatorSuppliedValuesRequired, true);
    assert.equal(fullSequenceBringup.operatorSequence[1]?.commandMode, "RequestNext");
    assert.equal(fullSequenceBringup.operatorSequence[1]?.commandRequiresConfirmation, true);
    assert.equal(fullSequenceBringup.operatorSequence[1]?.commandAvailableNow, false);
    assert.equal(fullSequenceBringup.operatorSequence[1]?.commandPreviewOnly, true);
    assert.equal(
      fullSequenceBringup.operatorSequence[1]?.commandAvailabilityReason,
      "future_step_waiting_on_prior_prerequisites",
    );
    assert.deepEqual(fullSequenceBringup.operatorSequenceCommandAvailability, {
      availableNowCount: 1,
      previewOnlyCount: 4,
      sequenceLength: 5,
      truthful: true,
    });
    assert.equal(fullSequenceBringup.operatorSequenceCommandAvailabilityCheck.status, "truthful");
    assert.equal(fullSequenceBringup.operatorSequenceCommandAvailabilityCheck.passed, true);
    assert.equal(prerequisiteBringup.requiresApprovalId, false);
    assert.equal(prerequisiteBringup.requiresOperatorApprovalDecision, false);
    assert.equal(prerequisiteBringup.readOnlyContract, true);
    assert.equal(prerequisiteBringup.diagnosticOnly, true);
    assert.equal(prerequisiteBringup.planOnly, true);
    assert.equal(prerequisiteBringup.usesLensStatusReadback, true);
    assert.equal(prerequisiteBringup.wouldExecute, false);
    assert.equal(prerequisiteBringup.wouldMutate, false);
    assert.equal(prerequisiteBringup.approvalRequestWrite, false);
    assert.equal(prerequisiteBringup.mutationAuthorityGranted, false);
    assert.equal(prerequisiteBringup.canRequestNextResidentRuntimeAuthority, true);
    assert.equal(prerequisiteBringup.canGrantNextResidentRuntimeAuthority, false);
    assert.equal(prerequisiteBringup.canRequestNextHostSupervisionAuthority, false);
    assert.equal(prerequisiteBringup.canGrantNextHostSupervisionAuthority, false);
    assert.equal(prerequisiteBringup.canExecuteNextSupervisedResidentHostStart, false);
    assert.equal(prerequisiteBringup.canRequestNextTrayAuthority, false);
    assert.equal(prerequisiteBringup.canGrantNextTrayAuthority, false);
    assert.equal(prerequisiteBringup.canExecuteNextTrayPresence, false);
    assert.equal(prerequisiteBringup.canRequestNextOsBindingAuthority, false);
    assert.equal(prerequisiteBringup.canGrantNextOsBindingAuthority, false);
    assert.equal(prerequisiteBringup.canExecuteNextOsBinding, false);
    assert.equal(prerequisiteBringup.canRequestNextOverlayAuthority, false);
    assert.equal(prerequisiteBringup.canGrantNextOverlayAuthority, false);
    assert.equal(prerequisiteBringup.canExecuteNextOverlayWindow, false);
    assert.equal(prerequisiteBringup.canRequestNextSummonAuthority, false);
    assert.equal(prerequisiteBringup.canGrantNextSummonAuthority, false);
    assert.equal(prerequisiteBringup.canExecuteNextSummonAction, false);
    assert.equal(prerequisiteBringup.canRequestNextPersistentSupervisionEnablementAuthority, false);
    assert.equal(prerequisiteBringup.canGrantNextPersistentSupervisionEnablementAuthority, false);
    assert.equal(prerequisiteBringup.canRequestNextPersistentSupervisionExecutionAuthority, false);
    assert.equal(prerequisiteBringup.canGrantNextPersistentSupervisionExecutionAuthority, false);
    assert.equal(prerequisiteBringup.canApplyNextPersistentSupervisionEnablement, false);
    const residentGrantBringup = presentStage6PrerequisiteBringup({
      ...prerequisiteBringupFixture,
      next_operator_action: {
        ...prerequisiteBringupFixture.next_operator_action,
        id: "grant_resident_runtime_execution_authority",
        route: "/lens/resident-runtime/authority-grant",
        approval_action: "lens.resident_runtime.execution_authority",
        live_effect: "resident runtime authority grant receipt",
        approved_approval_id: "approval-resident-runtime-1",
      },
      next_operator_command: {
        command:
          ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode GrantNext -Actor <actor> -ApprovalId approval-resident-runtime-1 -ConfirmGrant",
        mode: "GrantNext",
        requires_confirmation: true,
        requires_approval_id: true,
        requires_operator_approval_decision: true,
      },
    });
    assert.equal(residentGrantBringup.approvedApprovalId, "approval-resident-runtime-1");
    assert.equal(residentGrantBringup.canRequestNextResidentRuntimeAuthority, false);
    assert.equal(residentGrantBringup.canGrantNextResidentRuntimeAuthority, true);
    const hostRequestBringup = presentStage6PrerequisiteBringup({
      ...prerequisiteBringupFixture,
      next_operator_action: {
        ...prerequisiteBringupFixture.next_operator_action,
        id: "request_host_supervision_authority",
        route: "/lens/host/supervision/authority/request",
        approval_action: "lens.host.supervision_authority",
        live_effect: "host supervision authority request receipt only",
      },
      next_operator_command: {
        command: ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
        mode: "RequestNext",
        requires_confirmation: true,
        requires_approval_id: false,
        requires_operator_approval_decision: false,
      },
    });
    assert.equal(hostRequestBringup.canRequestNextHostSupervisionAuthority, true);
    const hostGrantBringup = presentStage6PrerequisiteBringup({
      ...prerequisiteBringupFixture,
      next_operator_action: {
        ...prerequisiteBringupFixture.next_operator_action,
        id: "grant_host_supervision_authority",
        route: "/lens/host/supervision/authority",
        approval_action: "lens.host.supervision_authority",
        live_effect: "host supervision authority grant receipt",
        approved_approval_id: "approval-host-supervision-1",
      },
      next_operator_command: {
        command:
          ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode GrantNext -Actor <actor> -ApprovalId approval-host-supervision-1 -ConfirmGrant",
        mode: "GrantNext",
        requires_confirmation: true,
        requires_approval_id: true,
        requires_operator_approval_decision: true,
      },
    });
    assert.equal(hostGrantBringup.approvedApprovalId, "approval-host-supervision-1");
    assert.equal(hostGrantBringup.canGrantNextHostSupervisionAuthority, true);
    const executeBringup = presentStage6PrerequisiteBringup({
      ...prerequisiteBringupFixture,
      next_operator_action: {
        ...prerequisiteBringupFixture.next_operator_action,
        id: "execute_supervised_resident_host_start",
        route: "/lens/resident-runtime/execute",
        approval_action: "lens.resident_runtime.execution_authority",
        mode: "resident_start",
        live_effect: "bounded supervised resident host lease",
        active_approval_id: "approval-resident-runtime-1",
        host_supervision_active_approval_id: "approval-host-supervision-1",
      },
      next_operator_command: {
        command:
          ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode ExecuteNext -Actor <actor> -ApprovalId approval-resident-runtime-1 -RunSeconds 2 -ConfirmExecute",
        mode: "ExecuteNext",
        requires_confirmation: true,
        requires_approval_id: true,
        requires_operator_approval_decision: false,
      },
    });
    assert.equal(executeBringup.activeApprovalId, "approval-resident-runtime-1");
    assert.equal(executeBringup.hostSupervisionActiveApprovalId, "approval-host-supervision-1");
    assert.equal(executeBringup.canExecuteNextSupervisedResidentHostStart, true);
    const presentNextPrerequisiteAction = (action, command) =>
      presentStage6PrerequisiteBringup({
        ...prerequisiteBringupFixture,
        next_operator_action: {
          ...prerequisiteBringupFixture.next_operator_action,
          ...action,
        },
        next_operator_command: command,
      });
    const requestCommand = {
      command: ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
      mode: "RequestNext",
      requires_confirmation: true,
      requires_approval_id: false,
      requires_operator_approval_decision: false,
    };
    const grantCommand = {
      command:
        ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode GrantNext -Actor <actor> -ApprovalId approval-surface-1 -ConfirmGrant",
      mode: "GrantNext",
      requires_confirmation: true,
      requires_approval_id: true,
      requires_operator_approval_decision: true,
    };
    const executeCommand = {
      command:
        ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode ExecuteNext -Actor <actor> -ApprovalId approval-surface-1 -RunSeconds 2 -ConfirmExecute",
      mode: "ExecuteNext",
      requires_confirmation: true,
      requires_approval_id: true,
      requires_operator_approval_decision: false,
    };
    const surfaceActionCases = [
      [
        "canRequestNextTrayAuthority",
        {
          id: "request_tray_presence_authority",
          route: "/lens/tray/authority/request",
          live_effect: "approval request receipt only",
        },
        requestCommand,
      ],
      [
        "canGrantNextTrayAuthority",
        {
          id: "grant_tray_presence_authority",
          route: "/lens/tray/authority",
          live_effect: "authority grant receipt",
          approved_approval_id: "approval-surface-1",
        },
        grantCommand,
      ],
      [
        "canExecuteNextTrayPresence",
        {
          id: "execute_tray_presence",
          route: "/lens/tray/execute",
          live_effect: "bounded tray presence lease",
          active_approval_id: "approval-surface-1",
        },
        executeCommand,
      ],
      [
        "canRequestNextOsBindingAuthority",
        {
          id: "request_global_hotkey_binding_authority",
          route: "/lens/os-binding/authority/request",
          live_effect: "approval request receipt only",
        },
        requestCommand,
      ],
      [
        "canGrantNextOsBindingAuthority",
        {
          id: "grant_global_hotkey_binding_authority",
          route: "/lens/os-binding/authority",
          live_effect: "authority grant receipt",
          approved_approval_id: "approval-surface-1",
        },
        grantCommand,
      ],
      [
        "canExecuteNextOsBinding",
        {
          id: "execute_global_hotkey_binding",
          route: "/lens/os-binding/execute",
          live_effect: "bounded global hotkey binding lease",
          active_approval_id: "approval-surface-1",
        },
        executeCommand,
      ],
      [
        "canRequestNextOverlayAuthority",
        {
          id: "request_overlay_window_authority",
          route: "/lens/overlay/authority/request",
          live_effect: "approval request receipt only",
        },
        requestCommand,
      ],
      [
        "canGrantNextOverlayAuthority",
        {
          id: "grant_overlay_window_authority",
          route: "/lens/overlay/authority",
          live_effect: "authority grant receipt",
          approved_approval_id: "approval-surface-1",
        },
        grantCommand,
      ],
      [
        "canExecuteNextOverlayWindow",
        {
          id: "execute_overlay_window",
          route: "/lens/overlay/execute",
          live_effect: "bounded overlay window lease",
          active_approval_id: "approval-surface-1",
        },
        executeCommand,
      ],
      [
        "canRequestNextSummonAuthority",
        {
          id: "request_summon_binding_authority",
          route: "/lens/summon/authority/request",
          live_effect: "approval request receipt only",
        },
        requestCommand,
      ],
      [
        "canGrantNextSummonAuthority",
        {
          id: "grant_summon_binding_authority",
          route: "/lens/summon/authority",
          live_effect: "authority grant receipt",
          approved_approval_id: "approval-surface-1",
        },
        grantCommand,
      ],
      [
        "canExecuteNextSummonAction",
        {
          id: "execute_summon_binding",
          route: "/lens/summon/execute",
          live_effect: "bounded summon handoff without summon-anywhere claim",
          active_approval_id: "approval-surface-1",
        },
        executeCommand,
      ],
      [
        "canRequestNextPersistentSupervisionEnablementAuthority",
        {
          id: "request_persistent_supervision_enablement_authority",
          route: "/lens/host/persistent-supervision/enablement/authority/request",
          live_effect: "persistent supervision enablement authority request receipt only",
        },
        requestCommand,
      ],
      [
        "canGrantNextPersistentSupervisionEnablementAuthority",
        {
          id: "grant_persistent_supervision_enablement_authority",
          route: "/lens/host/persistent-supervision/enablement/authority",
          live_effect: "persistent supervision enablement authority grant receipt",
          approved_approval_id: "approval-surface-1",
        },
        grantCommand,
      ],
      [
        "canRequestNextPersistentSupervisionExecutionAuthority",
        {
          id: "request_persistent_supervision_execution_authority",
          route: "/lens/host/persistent-supervision/enablement/execution/request",
          live_effect: "persistent supervision execution authority request receipt only",
        },
        requestCommand,
      ],
      [
        "canGrantNextPersistentSupervisionExecutionAuthority",
        {
          id: "grant_persistent_supervision_execution_authority",
          route: "/lens/host/persistent-supervision/enablement/execution/authority",
          live_effect: "persistent supervision execution authority grant receipt",
          approved_approval_id: "approval-surface-1",
        },
        grantCommand,
      ],
      [
        "canApplyNextPersistentSupervisionEnablement",
        {
          id: "apply_persistent_supervision_enablement",
          route: "/lens/host/persistent-supervision/enablement/execution/apply",
          live_effect: "persistent supervision service config update and execution receipt",
          active_approval_id: "approval-surface-1",
        },
        executeCommand,
      ],
    ];
    for (const [flag, action, command] of surfaceActionCases) {
      const surfaceBringup = presentNextPrerequisiteAction(action, command);
      assert.equal(surfaceBringup[flag], true);
    }
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
    const persistentSupervision = presentPersistentSupervisionReadback(snapshot.stage6_readiness.next_handoff);
    assert.equal(persistentSupervision.loaded, true);
    assert.equal(persistentSupervision.status, "readback_ready");
    assert.equal(persistentSupervision.readOnlyContract, true);
    assert.equal(persistentSupervision.diagnosticOnly, true);
    assert.equal(persistentSupervision.wouldExecute, false);
    assert.equal(persistentSupervision.wouldMutate, false);
    assert.equal(persistentSupervision.prerequisitesObserved, true);
    assert.equal(persistentSupervision.prerequisitesReady, false);
    assert.deepEqual(persistentSupervision.missingPrerequisites, ["resident_host_process", "tray_presence"]);
    assert.equal(persistentSupervision.firstMissingPrerequisite, "resident_host_process");
    assert.equal(
      persistentSupervision.firstMissingHandoff,
      "resolve_resident_host_process_before_persistent_supervision_enablement",
    );
    assert.equal(
      persistentSupervision.firstMissingProof,
      "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
    );
    assert.equal(persistentSupervision.firstMissingRoute, "/lens/host/runtime-loop/readiness");
    assert.equal(persistentSupervision.firstMissingAuthority, "process_supervision_authority");
    assert.equal(persistentSupervision.enablementAuthorityHandoffObserved, true);
    assert.equal(persistentSupervision.enablementAuthorityGranted, false);
    assert.equal(persistentSupervision.executionAuthorityGranted, false);
    assert.equal(persistentSupervision.receiptWriteAuthority, false);
    assert.equal(persistentSupervision.residentClaimAllowed, false);
    assert.equal(persistentSupervision.serviceConfigUpdated, false);
    assert.equal(persistentSupervision.applied, false);
    assert.equal(persistentSupervision.executed, false);
    assert.deepEqual(persistentSupervision.blockers, [
      "resident_host_process",
      "tray_presence",
      "persistent_supervision_enablement_authority_not_granted",
      "persistent_supervision_execution_authority_not_granted",
    ]);
    assert.equal(persistentSupervision.blockerCount, 4);
    assert.equal(
      persistentSupervision.currentGap,
      "persistent_supervision_enablement_authority_not_granted",
    );
    assert.equal(
      persistentSupervision.currentHandoff,
      "prove_persistent_supervision_enablement_authority_after_candidate_handoff",
    );
    assert.equal(
      persistentSupervision.currentProof,
      "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status",
    );
    assert.equal(
      persistentSupervision.currentRoute,
      "/lens/host/persistent-supervision/enablement/authority/readiness",
    );
    assert.equal(
      persistentSupervision.currentRequestRoute,
      "/lens/host/persistent-supervision/enablement/authority/request",
    );
    assert.equal(persistentSupervision.currentGrantRoute, "/lens/host/persistent-supervision/enablement/authority");
    assert.equal(
      persistentSupervision.currentGrantsRoute,
      "/lens/host/persistent-supervision/enablement/authority/grants",
    );
    assert.equal(
      persistentSupervision.currentExecutionReadinessRoute,
      "/lens/host/persistent-supervision/enablement/execution/readiness",
    );
    assert.equal(persistentSupervision.prerequisiteSource, "persistent_supervision_required_prerequisites_handoff");
    assert.equal(
      persistentSupervision.prerequisiteHandoff,
      "resolve_persistent_supervision_required_prerequisites_before_enablement",
    );
    assert.equal(
      persistentSupervision.prerequisiteProof,
      "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status",
    );
    assert.equal(persistentSupervision.prerequisiteRoute, "/lens/host/persistent-supervision/enablement");
    assert.equal(
      persistentSupervision.prerequisiteAuthority,
      "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
    );
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

test("LensClient.requestHostSupervisionAuthority creates an approval request without authority claims", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    return jsonResponse({
      ok: true,
      applied: false,
      approval_requested: true,
      status: "approval_requested",
      action: "lens.host.supervision_authority",
      approval_id: "appr_lens_host_supervision_alpha",
      approval: {
        id: "appr_lens_host_supervision_alpha",
        status: "pending_review",
      },
      supervision_authority: {
        route: "/lens/host/supervision/authority/request",
      },
      authority_granted: false,
      resident_claim_allowed: false,
      governance: {
        gate: "lens_host_supervision_authority_request",
        execution_authority: false,
        approval_decision_authority: false,
        process_supervision_authority: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const response = await client.requestHostSupervisionAuthority({
      actor: "chat_ui.system",
      reason: "request Lens host supervision authority from operator UI",
    });

    assert.equal(requests.length, 1);
    assert.equal(requests[0]?.path, "/lens/host/supervision/authority/request");
    assert.equal(requests[0]?.method, "POST");
    assert.deepEqual(requests[0]?.body, {
      actor: "chat_ui.system",
      reason: "request Lens host supervision authority from operator UI",
    });
    assert.equal(response.ok, true);
    assert.equal(response.applied, false);
    assert.equal(response.approval_requested, true);
    assert.equal(response.approval_id, "appr_lens_host_supervision_alpha");
    assert.equal(response.route, "/lens/host/supervision/authority/request");
    assert.equal(response.authority_granted, false);
    assert.equal(response.resident_claim_allowed, false);
    assert.equal(response.governance.process_supervision_authority, false);
  } finally {
    restoreFetch();
  }
});

test("LensClient.grantHostSupervisionAuthority posts an approved request without process execution", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    return jsonResponse({
      ok: true,
      kind: "lens.host.supervision_authority.grant",
      status: "authority_granted",
      route: "/lens/host/supervision/authority",
      method: "POST",
      approval_id: "appr_lens_host_supervision_alpha",
      approval: {
        required: true,
        found: true,
        status: "approved",
        approved: true,
      },
      authority_granted: true,
      applied: true,
      executed: false,
      resident_claim_allowed: false,
      blockers: [],
      governance: {
        gate: "lens_host_supervision_authority_grant_boundary",
        execution_authority: false,
        approval_decision_authority: false,
        process_supervision_authority: true,
        process_restart_authority: true,
        service_control_authority: true,
        memory_write: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const response = await client.grantHostSupervisionAuthority({
      approvalId: "appr_lens_host_supervision_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens host supervision authority from operator UI",
    });

    assert.equal(requests.length, 1);
    assert.equal(requests[0]?.path, "/lens/host/supervision/authority");
    assert.equal(requests[0]?.method, "POST");
    assert.deepEqual(requests[0]?.body, {
      approval_id: "appr_lens_host_supervision_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens host supervision authority from operator UI",
      lease_seconds: 3600,
    });
    assert.equal(response.ok, true);
    assert.equal(response.applied, true);
    assert.equal(response.authority_granted, true);
    assert.equal(response.resident_claim_allowed, false);
    assert.equal(response.blockers.length, 0);
    assert.equal(response.governance.execution_authority, false);
    assert.equal(response.governance.approval_decision_authority, false);
    assert.equal(response.governance.memory_write, false);
  } finally {
    restoreFetch();
  }
});

test("LensClient.executeHostSupervision posts a governed resident lease action", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    return jsonResponse({
      ok: true,
      applied: true,
      executed: true,
      kind: "lens.host.supervision.execution",
      status: "resident_supervision_started",
      route: "/lens/host/supervision/execute",
      approval_id: "appr_lens_host_supervision_alpha",
      supervision_mode: "resident_start",
      resident_host_process: true,
      resident_supervised_runtime: true,
      resident_claim_allowed: false,
      blockers: [],
      governance: {
        gate: "lens_host_supervision_execution",
        execution_authority: true,
        approval_decision_authority: false,
        process_supervision_authority: true,
        service_control_authority: false,
        resident_claim_authority: false,
        memory_write: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const response = await client.executeHostSupervision({
      approvalId: "appr_lens_host_supervision_alpha",
      actor: "chat_ui.system",
      reason: "start governed Lens resident host supervision from operator UI",
      mode: "resident_start",
      runSeconds: 25,
    });

    assert.equal(requests.length, 1);
    assert.equal(requests[0]?.path, "/lens/host/supervision/execute");
    assert.equal(requests[0]?.method, "POST");
    assert.deepEqual(requests[0]?.body, {
      approval_id: "appr_lens_host_supervision_alpha",
      actor: "chat_ui.system",
      reason: "start governed Lens resident host supervision from operator UI",
      run_seconds: 10,
      mode: "resident_start",
    });
    assert.equal(response.ok, true);
    assert.equal(response.applied, true);
    assert.equal(response.executed, true);
    assert.equal(response.route, "/lens/host/supervision/execute");
    assert.equal(response.resident_claim_allowed, false);
    assert.equal(response.blockers.length, 0);
    assert.equal(response.governance.approval_decision_authority, false);
    assert.equal(response.governance.service_control_authority, false);
    assert.equal(response.governance.resident_claim_authority, false);
    assert.equal(response.governance.memory_write, false);
  } finally {
    restoreFetch();
  }
});

test("LensClient OS-binding authority and execution methods post governed hotkey actions", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    if (parsed.pathname.endsWith("/request")) {
      return jsonResponse({
        ok: true,
        applied: false,
        executed: false,
        approval_requested: true,
        status: "approval_requested",
        approval_id: "appr_lens_os_binding_alpha",
        route: "/lens/os-binding/authority/request",
        authority_granted: false,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: "lens_os_binding_command_palette_authority_request",
          execution_authority: false,
          approval_decision_authority: false,
          memory_write: false,
        },
      });
    }
    if (parsed.pathname.endsWith("/authority")) {
      return jsonResponse({
        ok: true,
        applied: true,
        executed: false,
        status: "authority_granted",
        route: "/lens/os-binding/authority",
        approval_id: "appr_lens_os_binding_alpha",
        authority_granted: true,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: "lens_os_binding_command_palette_authority_grant",
          execution_authority: false,
          hotkey_registration_authority: true,
          approval_decision_authority: false,
          memory_write: false,
        },
      });
    }
    return jsonResponse({
      ok: true,
      applied: true,
      executed: true,
      status: "global_hotkey_bound",
      route: "/lens/os-binding/execute",
      approval_id: "appr_lens_os_binding_alpha",
      global_hotkey_binding: true,
      resident_claim_allowed: false,
      blockers: [],
      governance: {
        gate: "lens_os_binding_command_palette_execution",
        execution_authority: true,
        hotkey_registration_authority: true,
        approval_decision_authority: false,
        memory_write: false,
        resident_claim_authority: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const requested = await client.requestOsBindingAuthority({
      actor: "chat_ui.system",
      reason: "request Lens OS-binding hotkey authority from operator UI",
    });
    const granted = await client.grantOsBindingAuthority({
      approvalId: "appr_lens_os_binding_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens OS-binding hotkey authority from operator UI",
    });
    const executed = await client.executeOsBinding({
      approvalId: "appr_lens_os_binding_alpha",
      actor: "chat_ui.system",
      reason: "bind governed Lens global hotkey from operator UI",
      mode: "bind",
      runSeconds: 25,
    });

    assert.equal(requests.length, 3);
    assert.deepEqual(requests.map((request) => request.path), [
      "/lens/os-binding/authority/request",
      "/lens/os-binding/authority",
      "/lens/os-binding/execute",
    ]);
    assert.deepEqual(requests[2]?.body, {
      approval_id: "appr_lens_os_binding_alpha",
      actor: "chat_ui.system",
      reason: "bind governed Lens global hotkey from operator UI",
      run_seconds: 10,
      mode: "bind",
    });
    assert.equal(requested.approval_requested, true);
    assert.equal(requested.route, "/lens/os-binding/authority/request");
    assert.equal(granted.authority_granted, true);
    assert.equal(executed.executed, true);
    assert.equal(executed.route, "/lens/os-binding/execute");
    assert.equal(executed.governance.approval_decision_authority, false);
    assert.equal(executed.governance.memory_write, false);
    assert.equal(executed.governance.resident_claim_authority, false);
  } finally {
    restoreFetch();
  }
});

test("LensClient tray authority and execution methods post governed tray actions", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    if (parsed.pathname.endsWith("/request")) {
      return jsonResponse({
        ok: true,
        applied: false,
        executed: false,
        approval_requested: true,
        status: "approval_requested",
        approval_id: "appr_lens_tray_alpha",
        route: "/lens/tray/authority/request",
        authority_granted: false,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: "lens_tray_presence_authority_request",
          execution_authority: false,
          approval_decision_authority: false,
          memory_write: false,
        },
      });
    }
    if (parsed.pathname.endsWith("/authority")) {
      return jsonResponse({
        ok: true,
        applied: true,
        executed: false,
        status: "authority_granted",
        route: "/lens/tray/authority",
        approval_id: "appr_lens_tray_alpha",
        authority_granted: true,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: "lens_tray_presence_authority_grant",
          execution_authority: false,
          tray_registration_authority: true,
          approval_decision_authority: false,
          memory_write: false,
        },
      });
    }
    return jsonResponse({
      ok: true,
      applied: true,
      executed: true,
      status: "tray_presence_started",
      route: "/lens/tray/execute",
      approval_id: "appr_lens_tray_alpha",
      tray_presence: true,
      resident_claim_allowed: false,
      blockers: [],
      governance: {
        gate: "lens_tray_presence_execution",
        execution_authority: true,
        approval_decision_authority: false,
        memory_write: false,
        resident_claim_authority: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const requested = await client.requestTrayAuthority({
      actor: "chat_ui.system",
      reason: "request Lens tray presence authority from operator UI",
    });
    const granted = await client.grantTrayAuthority({
      approvalId: "appr_lens_tray_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens tray presence authority from operator UI",
    });
    const executed = await client.executeTrayPresence({
      approvalId: "appr_lens_tray_alpha",
      actor: "chat_ui.system",
      reason: "start Lens tray presence from operator UI",
      mode: "start",
      runSeconds: 25,
    });

    assert.equal(requests.length, 3);
    assert.deepEqual(requests.map((request) => request.path), [
      "/lens/tray/authority/request",
      "/lens/tray/authority",
      "/lens/tray/execute",
    ]);
    assert.deepEqual(requests[0]?.body, {
      actor: "chat_ui.system",
      reason: "request Lens tray presence authority from operator UI",
    });
    assert.deepEqual(requests[1]?.body, {
      approval_id: "appr_lens_tray_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens tray presence authority from operator UI",
      lease_seconds: 3600,
    });
    assert.deepEqual(requests[2]?.body, {
      approval_id: "appr_lens_tray_alpha",
      actor: "chat_ui.system",
      reason: "start Lens tray presence from operator UI",
      run_seconds: 10,
      mode: "start",
    });
    assert.equal(requested.approval_requested, true);
    assert.equal(requested.route, "/lens/tray/authority/request");
    assert.equal(granted.authority_granted, true);
    assert.equal(granted.executed, false);
    assert.equal(executed.executed, true);
    assert.equal(executed.route, "/lens/tray/execute");
    assert.equal(executed.governance.approval_decision_authority, false);
    assert.equal(executed.governance.memory_write, false);
    assert.equal(executed.governance.resident_claim_authority, false);
  } finally {
    restoreFetch();
  }
});

test("LensClient overlay and summon methods post governed Stage 6 prerequisite actions", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    if (parsed.pathname.endsWith("/request")) {
      const isOverlay = parsed.pathname.includes("/overlay/");
      return jsonResponse({
        ok: true,
        applied: false,
        executed: false,
        approval_requested: true,
        status: "approval_requested",
        approval_id: isOverlay ? "appr_lens_overlay_alpha" : "appr_lens_summon_alpha",
        route: isOverlay ? "/lens/overlay/authority/request" : "/lens/summon/authority/request",
        authority_granted: false,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: isOverlay ? "lens_overlay_window_authority_request" : "lens_summon_action_authority_request",
          execution_authority: false,
          approval_decision_authority: false,
          memory_write: false,
        },
      });
    }
    if (parsed.pathname.endsWith("/authority")) {
      const isOverlay = parsed.pathname.includes("/overlay/");
      return jsonResponse({
        ok: true,
        applied: true,
        executed: false,
        status: "authority_granted",
        route: isOverlay ? "/lens/overlay/authority" : "/lens/summon/authority",
        approval_id: isOverlay ? "appr_lens_overlay_alpha" : "appr_lens_summon_alpha",
        authority_granted: true,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: isOverlay ? "lens_overlay_window_authority_grant" : "lens_summon_action_authority_grant",
          execution_authority: false,
          approval_decision_authority: false,
          memory_write: false,
          overlay_control_authority: isOverlay,
          summon_authority: !isOverlay,
        },
      });
    }
    const isOverlay = parsed.pathname.includes("/overlay/");
    return jsonResponse({
      ok: true,
      applied: true,
      executed: true,
      status: isOverlay ? "overlay_window_started" : "summon_binding_observed",
      route: isOverlay ? "/lens/overlay/execute" : "/lens/summon/execute",
      approval_id: isOverlay ? "appr_lens_overlay_alpha" : "appr_lens_summon_alpha",
      resident_claim_allowed: false,
      blockers: [],
      governance: {
        gate: isOverlay ? "lens_overlay_window_execution" : "lens_summon_action_execution",
        execution_authority: true,
        approval_decision_authority: false,
        memory_write: false,
        resident_claim_authority: false,
        overlay_control_authority: isOverlay,
        summon_authority: !isOverlay,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const overlayRequested = await client.requestOverlayAuthority({
      actor: "chat_ui.system",
      reason: "request Lens overlay window authority from operator UI",
    });
    const overlayGranted = await client.grantOverlayAuthority({
      approvalId: "appr_lens_overlay_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens overlay window authority from operator UI",
    });
    const overlayExecuted = await client.executeOverlayWindow({
      approvalId: "appr_lens_overlay_alpha",
      actor: "chat_ui.system",
      reason: "start Lens overlay window from operator UI",
      mode: "start",
      runSeconds: 25,
    });
    const summonRequested = await client.requestSummonAuthority({
      actor: "chat_ui.system",
      reason: "request Lens summon action authority from operator UI",
    });
    const summonGranted = await client.grantSummonAuthority({
      approvalId: "appr_lens_summon_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens summon action authority from operator UI",
    });
    const summonExecuted = await client.executeSummonAction({
      approvalId: "appr_lens_summon_alpha",
      actor: "chat_ui.system",
      reason: "record bounded Lens summon handoff from operator UI",
      mode: "launch",
      runSeconds: 25,
    });

    assert.equal(requests.length, 6);
    assert.deepEqual(requests.map((request) => request.path), [
      "/lens/overlay/authority/request",
      "/lens/overlay/authority",
      "/lens/overlay/execute",
      "/lens/summon/authority/request",
      "/lens/summon/authority",
      "/lens/summon/execute",
    ]);
    assert.deepEqual(requests[2]?.body, {
      approval_id: "appr_lens_overlay_alpha",
      actor: "chat_ui.system",
      reason: "start Lens overlay window from operator UI",
      run_seconds: 10,
      mode: "start",
    });
    assert.deepEqual(requests[5]?.body, {
      approval_id: "appr_lens_summon_alpha",
      actor: "chat_ui.system",
      reason: "record bounded Lens summon handoff from operator UI",
      run_seconds: 10,
      mode: "launch",
      allow_launch: false,
    });
    assert.equal(overlayRequested.approval_requested, true);
    assert.equal(overlayGranted.authority_granted, true);
    assert.equal(overlayExecuted.executed, true);
    assert.equal(overlayExecuted.route, "/lens/overlay/execute");
    assert.equal(summonRequested.approval_requested, true);
    assert.equal(summonGranted.authority_granted, true);
    assert.equal(summonExecuted.executed, true);
    assert.equal(summonExecuted.route, "/lens/summon/execute");
    assert.equal(summonExecuted.governance.approval_decision_authority, false);
    assert.equal(summonExecuted.governance.memory_write, false);
    assert.equal(summonExecuted.governance.resident_claim_authority, false);
  } finally {
    restoreFetch();
  }
});

test("LensClient.requestResidentRuntimeAuthority creates an approval request without launch authority", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    return jsonResponse({
      ok: true,
      applied: false,
      executed: false,
      approval_requested: true,
      status: "approval_requested",
      action: "lens.resident_runtime.execution_authority",
      approval_id: "appr_lens_resident_runtime_alpha",
      approval: {
        id: "appr_lens_resident_runtime_alpha",
        status: "pending_review",
      },
      resident_runtime_execution_authority: {
        route: "/lens/resident-runtime/authority-grant/request",
      },
      authority_granted: false,
      resident_claim_allowed: false,
      execution_authority: false,
      local_process_launch_authority: false,
      memory_write: false,
      governance: {
        gate: "lens_resident_runtime_execution_authority_request",
        execution_authority: false,
        approval_decision_authority: false,
        local_process_launch_authority: false,
        memory_write: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const response = await client.requestResidentRuntimeAuthority({
      actor: "chat_ui.system",
      reason: "request Lens resident runtime execution authority from operator UI",
    });

    assert.equal(requests.length, 1);
    assert.equal(requests[0]?.path, "/lens/resident-runtime/authority-grant/request");
    assert.equal(requests[0]?.method, "POST");
    assert.deepEqual(requests[0]?.body, {
      actor: "chat_ui.system",
      reason: "request Lens resident runtime execution authority from operator UI",
    });
    assert.equal(response.ok, true);
    assert.equal(response.applied, false);
    assert.equal(response.executed, false);
    assert.equal(response.approval_requested, true);
    assert.equal(response.approval_id, "appr_lens_resident_runtime_alpha");
    assert.equal(response.route, "/lens/resident-runtime/authority-grant/request");
    assert.equal(response.authority_granted, false);
    assert.equal(response.resident_claim_allowed, false);
    assert.equal(response.governance.local_process_launch_authority, false);
    assert.equal(response.governance.memory_write, false);
  } finally {
    restoreFetch();
  }
});

test("LensClient.grantResidentRuntimeAuthority posts an approved request without starting runtime", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    return jsonResponse({
      ok: true,
      kind: "lens.resident_runtime.execution_authority_grant.grant",
      status: "authority_granted",
      route: "/lens/resident-runtime/authority-grant",
      method: "POST",
      approval_id: "appr_lens_resident_runtime_alpha",
      approval: {
        required: true,
        found: true,
        status: "approved",
        approved: true,
      },
      authority_granted: true,
      resident_runtime_execution_authority: true,
      applied: true,
      executed: false,
      resident_claim_allowed: false,
      blockers: [],
      governance: {
        gate: "lens_resident_runtime_execution_authority_grant_boundary",
        execution_authority: false,
        approval_decision_authority: false,
        resident_runtime_execution_authority: true,
        local_process_launch_authority: false,
        process_supervision_authority: false,
        memory_write: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const response = await client.grantResidentRuntimeAuthority({
      approvalId: "appr_lens_resident_runtime_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens resident runtime execution authority from operator UI",
    });

    assert.equal(requests.length, 1);
    assert.equal(requests[0]?.path, "/lens/resident-runtime/authority-grant");
    assert.equal(requests[0]?.method, "POST");
    assert.deepEqual(requests[0]?.body, {
      approval_id: "appr_lens_resident_runtime_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens resident runtime execution authority from operator UI",
      lease_seconds: 3600,
    });
    assert.equal(response.ok, true);
    assert.equal(response.applied, true);
    assert.equal(response.executed, false);
    assert.equal(response.authority_granted, true);
    assert.equal(response.resident_claim_allowed, false);
    assert.equal(response.blockers.length, 0);
    assert.equal(response.governance.execution_authority, false);
    assert.equal(response.governance.approval_decision_authority, false);
    assert.equal(response.governance.local_process_launch_authority, false);
    assert.equal(response.governance.process_supervision_authority, false);
    assert.equal(response.governance.memory_write, false);
  } finally {
    restoreFetch();
  }
});

test("LensClient.executeResidentRuntimeActivation posts a bounded resident start request", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    return jsonResponse({
      ok: true,
      applied: true,
      executed: true,
      kind: "lens.resident_runtime.activation.execution",
      status: "resident_supervision_started",
      route: "/lens/resident-runtime/execute",
      approval_id: "appr_lens_resident_runtime_alpha",
      host_supervision_approval_id: "appr_lens_host_supervision_alpha",
      run_seconds: 2,
      resident_runtime_authority: {
        active: true,
        receipt_id: "lrra_1770001000_alpha",
      },
      host_supervision_authority: {
        active: true,
        receipt_id: "lhsa_1770001000_alpha",
      },
      resident_host_process: true,
      resident_supervised_runtime: true,
      resident_claim_allowed: false,
      blockers: [],
      governance: {
        gate: "lens_resident_runtime_activation_execution",
        execution_authority: true,
        approval_decision_authority: false,
        resident_runtime_execution_authority: true,
        process_supervision_authority: true,
        resident_claim_authority: false,
        memory_write: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const response = await client.executeResidentRuntimeActivation({
      approvalId: "appr_lens_resident_runtime_alpha",
      actor: "chat_ui.system",
      reason: "start bounded Lens resident runtime from operator UI",
      runSeconds: 25,
    });

    assert.equal(requests.length, 1);
    assert.equal(requests[0]?.path, "/lens/resident-runtime/execute");
    assert.equal(requests[0]?.method, "POST");
    assert.deepEqual(requests[0]?.body, {
      approval_id: "appr_lens_resident_runtime_alpha",
      actor: "chat_ui.system",
      reason: "start bounded Lens resident runtime from operator UI",
      run_seconds: 10,
    });
    assert.equal(response.ok, true);
    assert.equal(response.applied, true);
    assert.equal(response.executed, true);
    assert.equal(response.route, "/lens/resident-runtime/execute");
    assert.equal(response.resident_claim_allowed, false);
    assert.equal(response.blockers.length, 0);
    assert.equal(response.governance.approval_decision_authority, false);
    assert.equal(response.governance.memory_write, false);
    assert.equal(response.governance.resident_claim_authority, false);
  } finally {
    restoreFetch();
  }
});

test("LensClient persistent supervision enablement methods post governed authority and apply actions", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    if (parsed.pathname.endsWith("/authority/request")) {
      return jsonResponse({
        ok: true,
        applied: false,
        executed: false,
        approval_requested: true,
        status: "approval_requested",
        route: "/lens/host/persistent-supervision/enablement/authority/request",
        approval_id: "appr_lens_persistent_enablement_alpha",
        authority_granted: false,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: "lens_host_persistent_supervision_enablement_authority_request",
          execution_authority: false,
          approval_decision_authority: false,
          service_config_write_authority: false,
          memory_write: false,
        },
      });
    }
    if (parsed.pathname.endsWith("/enablement/authority")) {
      return jsonResponse({
        ok: true,
        applied: true,
        executed: false,
        status: "authority_granted",
        route: "/lens/host/persistent-supervision/enablement/authority",
        approval_id: "appr_lens_persistent_enablement_alpha",
        authority_granted: true,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: "lens_host_persistent_supervision_enablement_authority_grant_boundary",
          execution_authority: false,
          approval_decision_authority: false,
          service_config_write_authority: false,
          memory_write: false,
          resident_claim_authority: false,
        },
      });
    }
    if (parsed.pathname.endsWith("/execution/request")) {
      return jsonResponse({
        ok: true,
        applied: false,
        executed: false,
        approval_requested: true,
        status: "approval_requested",
        route: "/lens/host/persistent-supervision/enablement/execution/request",
        approval_id: "appr_lens_persistent_execution_alpha",
        authority_granted: false,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: "lens_host_persistent_supervision_enablement_execution_request",
          execution_authority: false,
          approval_decision_authority: false,
          service_config_write_authority: false,
          memory_write: false,
        },
      });
    }
    if (parsed.pathname.endsWith("/execution/authority")) {
      return jsonResponse({
        ok: true,
        applied: true,
        executed: false,
        status: "authority_granted",
        route: "/lens/host/persistent-supervision/enablement/execution/authority",
        approval_id: "appr_lens_persistent_execution_alpha",
        authority_granted: true,
        resident_claim_allowed: false,
        blockers: [],
        governance: {
          gate: "lens_host_persistent_supervision_enablement_execution_authority_grant_boundary",
          execution_authority: false,
          approval_decision_authority: false,
          service_config_write_authority: true,
          persistent_supervision_execution_authority: true,
          memory_write: false,
          resident_claim_authority: false,
        },
      });
    }
    return jsonResponse({
      ok: true,
      applied: true,
      executed: true,
      status: "persistent_supervision_enabled",
      route: "/lens/host/persistent-supervision/enablement/execution/apply",
      approval_id: "appr_lens_persistent_execution_alpha",
      resident_claim_allowed: false,
      blockers: [],
      governance: {
        gate: "lens_host_persistent_supervision_enablement_execution",
        execution_authority: true,
        approval_decision_authority: false,
        service_config_write_authority: true,
        memory_write: false,
        resident_claim_authority: false,
      },
    });
  });

  try {
    const client = new LensClient("http://127.0.0.1:8000/");
    const enablementRequested = await client.requestPersistentSupervisionEnablementAuthority({
      actor: "chat_ui.system",
      reason: "request Lens persistent supervision enablement authority from operator UI",
    });
    const enablementGranted = await client.grantPersistentSupervisionEnablementAuthority({
      approvalId: "appr_lens_persistent_enablement_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens persistent supervision enablement authority from operator UI",
    });
    const executionRequested = await client.requestPersistentSupervisionExecutionAuthority({
      actor: "chat_ui.system",
      reason: "request Lens persistent supervision execution authority from operator UI",
    });
    const executionGranted = await client.grantPersistentSupervisionExecutionAuthority({
      approvalId: "appr_lens_persistent_execution_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens persistent supervision execution authority from operator UI",
    });
    const applied = await client.applyPersistentSupervisionEnablement({
      approvalId: "appr_lens_persistent_execution_alpha",
      actor: "chat_ui.system",
      reason: "apply Lens persistent supervision enablement from operator UI",
    });

    assert.equal(requests.length, 5);
    assert.deepEqual(requests.map((request) => request.path), [
      "/lens/host/persistent-supervision/enablement/authority/request",
      "/lens/host/persistent-supervision/enablement/authority",
      "/lens/host/persistent-supervision/enablement/execution/request",
      "/lens/host/persistent-supervision/enablement/execution/authority",
      "/lens/host/persistent-supervision/enablement/execution/apply",
    ]);
    assert.deepEqual(requests[0]?.body, {
      actor: "chat_ui.system",
      reason: "request Lens persistent supervision enablement authority from operator UI",
    });
    assert.deepEqual(requests[1]?.body, {
      approval_id: "appr_lens_persistent_enablement_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens persistent supervision enablement authority from operator UI",
      lease_seconds: 3600,
    });
    assert.deepEqual(requests[2]?.body, {
      actor: "chat_ui.system",
      reason: "request Lens persistent supervision execution authority from operator UI",
    });
    assert.deepEqual(requests[3]?.body, {
      approval_id: "appr_lens_persistent_execution_alpha",
      actor: "chat_ui.system",
      reason: "grant Lens persistent supervision execution authority from operator UI",
      lease_seconds: 3600,
    });
    assert.deepEqual(requests[4]?.body, {
      approval_id: "appr_lens_persistent_execution_alpha",
      actor: "chat_ui.system",
      reason: "apply Lens persistent supervision enablement from operator UI",
    });
    assert.equal(enablementRequested.approval_requested, true);
    assert.equal(enablementGranted.authority_granted, true);
    assert.equal(enablementGranted.executed, false);
    assert.equal(executionRequested.approval_requested, true);
    assert.equal(executionGranted.authority_granted, true);
    assert.equal(applied.applied, true);
    assert.equal(applied.executed, true);
    assert.equal(applied.route, "/lens/host/persistent-supervision/enablement/execution/apply");
    assert.equal(applied.governance.approval_decision_authority, false);
    assert.equal(applied.governance.memory_write, false);
    assert.equal(applied.governance.resident_claim_authority, false);
  } finally {
    restoreFetch();
  }
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
