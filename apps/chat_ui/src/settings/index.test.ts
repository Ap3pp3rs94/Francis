import assert from "node:assert/strict";
import test from "node:test";

import { SettingsClient, presentMissionDeadletterItems } from "./index.ts";

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

function jsonRequestBody(init?: RequestInit): unknown {
  const body = init?.body;
  if (typeof body !== "string" || !body.trim()) return undefined;
  return JSON.parse(body) as unknown;
}

test("presentMissionDeadletterItems normalizes reason fields and prioritizes actionable recent deadletters", () => {
  const presentation = presentMissionDeadletterItems(
    [
      {
        id: "mission_old",
        objective: "Older deadletter with no explicit action",
        deadletter_reason: "manual_review_needed",
        recovery: {
          source_status: "deadlettered",
          action: "review_deadletter",
          target_id: "tsk_old",
          reason: "manual_review_needed",
          next_step: "Review receipts before declaring replacement work.",
          operator_required: true,
          automatic_retry: false,
          read_only: true,
        },
        updated_at: "2026-04-22T09:00:00Z",
        latest_activity: { name: "deadlettered", status: "failed", ts: 1_745_312_400 },
        last_task_id: "tsk_old",
        last_task_status: "blocked",
        last_task_result_status: "failed",
        last_task_gate: "approvals_gate",
        last_task_approval_id: "apr_dead_old",
        last_task_previous_approval_id: "apr_dead_prev",
        last_task_previous_approval_status: "approved",
        last_task_approval_status: "pending",
        last_task_approval_replacement_kind: "plugin.run.mismatch",
        last_task_approval_replacement_reason: "approval_payload_mismatch",
        last_task_approval_replacement_changed_keys: ["input"],
        history_count: 4,
        latest_history_event: "continuity_updated",
        latest_history_ts: "2026-04-22T09:00:00+00:00",
        history_tail: [
          {
            event: "status_changed",
            ts: "2026-04-22T08:59:00+00:00",
            details: { from: "blocked", to: "deadlettered" },
          },
          {
            event: "continuity_updated",
            ts: "2026-04-22T09:00:00+00:00",
            details: { deadletter_reason: "manual_review_needed" },
          },
        ],
      },
      {
        id: "mission_actionable",
        objective: "Recent deadletter with a concrete next review step",
        reason: "approval_timeout",
        recommended_action: "inspect approvals",
        updated_at: "2026-04-23T09:00:00Z",
        latest_activity: { name: "governance_hold", status: "blocked", gate: "approvals_gate", ts: 1_745_398_800 },
      },
      {
        id: "mission_newer_no_action",
        objective: "Recent deadletter without an explicit action",
        deadletter_reason: "worker_failed_twice",
        updated_at: "2026-04-23T08:00:00Z",
      },
    ],
    2,
  );

  assert.deepEqual(
    presentation.visible.map((item) => item.id),
    ["mission_actionable", "mission_newer_no_action"],
  );
  assert.equal(presentation.visible[0]?.reason, "approval_timeout");
  assert.equal(presentation.visible[1]?.reason, "worker_failed_twice");
  assert.equal(presentation.visible[1]?.last_task_status, undefined);
  assert.equal(presentation.ordered[2]?.last_task_status, "blocked");
  assert.equal(presentation.ordered[2]?.recovery?.action, "review_deadletter");
  assert.equal(presentation.ordered[2]?.recovery?.target_id, "tsk_old");
  assert.equal(presentation.ordered[2]?.recovery?.automatic_retry, false);
  assert.equal(presentation.ordered[2]?.recovery?.read_only, true);
  assert.equal(presentation.ordered[2]?.last_task_result_status, "failed");
  assert.equal(presentation.ordered[2]?.last_task_gate, "approvals_gate");
  assert.equal(presentation.ordered[2]?.last_task_approval_id, "apr_dead_old");
  assert.equal(presentation.ordered[2]?.last_task_previous_approval_id, "apr_dead_prev");
  assert.equal(presentation.ordered[2]?.last_task_previous_approval_status, "approved");
  assert.equal(presentation.ordered[2]?.last_task_approval_status, "pending");
  assert.equal(presentation.ordered[2]?.last_task_approval_replacement_kind, "plugin.run.mismatch");
  assert.equal(presentation.ordered[2]?.last_task_approval_replacement_reason, "approval_payload_mismatch");
  assert.deepEqual(presentation.ordered[2]?.last_task_approval_replacement_changed_keys, ["input"]);
  assert.equal(
    presentation.ordered[2]?.approval_summary,
    "Approval apr_dead_old remains pending and supersedes prior approval apr_dead_prev (approved).",
  );
  assert.equal(
    presentation.ordered[2]?.approval_replacement_summary,
    "Approval replacement reason approval_payload_mismatch; artifact kind: plugin.run.mismatch; changed payload keys: input.",
  );
  assert.equal(presentation.ordered[2]?.approval_review_label, "Review replacement approval");
  assert.equal(presentation.ordered[2]?.previous_approval_review_label, "Open superseded approval");
  assert.equal(presentation.ordered[2]?.history_count, 4);
  assert.equal(presentation.ordered[2]?.latest_history_event, "continuity_updated");
  assert.equal(presentation.ordered[2]?.latest_history_ts, "2026-04-22T09:00:00+00:00");
  assert.equal(presentation.ordered[2]?.history_tail?.length, 2);
  assert.equal(presentation.ordered[2]?.history_tail?.[0]?.event, "status_changed");
  assert.equal((presentation.ordered[2]?.history_tail?.[1]?.details as Record<string, unknown>)?.deadletter_reason, "manual_review_needed");
  assert.equal(
    presentation.ordered[2]?.history_summary,
    "Deadletter reason manual_review_needed was recorded after mission status moved blocked -> deadlettered.",
  );
  assert.equal(presentation.total, 3);
  assert.equal(presentation.hiddenTotal, 1);
});

test("SettingsClient.getHealth parses Francis health report envelopes without a window global", async () => {
  const requestPaths: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    requestPaths.push(new URL(url).pathname);
    return jsonResponse({
      ok: true,
      report: {
        ts: 1_710_000_123,
        env: "dev",
        trust: { level: 0.75, posture: "standard" },
        stack: { api: "ready" },
      },
    });
  });

  try {
    const client = new SettingsClient("http://127.0.0.1:8000");
    const health = await client.getHealth({ timeoutMs: 50 });

    assert.deepEqual(requestPaths, ["/system/health"]);
    assert.equal(health.ok, true);
    assert.equal(health.status, "ok");
    assert.equal(health.ts, 1_710_000_123);
    assert.deepEqual(health.meta, {
      env: "dev",
      trust: { level: 0.75, posture: "standard" },
      stack: { api: "ready" },
    });
  } finally {
    restoreFetch();
  }
});

test("SettingsClient uses compatibility aliases for operator-critical read surfaces", async () => {
  const requestPaths: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const path = new URL(url).pathname;
    requestPaths.push(path);

    if (path === "/system/world_state") {
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    }

    if (path === "/system/world-state") {
      return jsonResponse({
        ok: true,
        subsystem: "world_state",
        counts: { queued_tasks: 3 },
        paths: {
          data: {
            path: "C:/Francis/data",
            exists: true,
            is_dir: true,
          },
        },
        overview: {
          pending_approvals: [
            {
              id: "apr_plugin_refresh",
              action: "plugin.run",
              reason: "Deploy production plugin step",
              status: "pending",
              ts: 1_710_000_456,
              request_kind: "plugin.run.request",
              previous_approval_id: "apr_plugin_old",
              previous_approval_status: "approved",
              replacement_kind: "plugin.run.mismatch",
              replacement_reason: "approval_payload_mismatch",
              replacement_expected_payload_keys: ["action", "input", "plugin_id"],
              replacement_previous_payload_keys: ["action", "input", "plugin_id"],
              replacement_changed_keys: ["input"],
              payload_summary: {
                requested_action: "deploy",
                plugin_id: "plugin.deploy",
                risk_tier: "critical",
                required_trust: 5,
                input_keys: ["target"],
                params_keys: ["region"],
              },
            },
          ],
          task_status_counts: { queued: 3 },
          recent_tasks: [],
          mission_status_counts: { queued: 1 },
          recent_missions: [
            {
              id: "mission_alpha",
              status: "queued",
              owner_id: "owner.alpha",
              dependency_ids: ["dep_one"],
              dependency_count: 1,
              escalation_path: "Review with operator if blocked.",
              latest_activity: {
                source: "run_ledger",
                name: "created",
                status: "queued",
                ts: 1_710_000_654,
              },
              current_task: {
                mission_id: "mission_alpha",
                source: "mission_meta",
                operation_id: "tsk_alpha",
                task_status: "accepted",
                latest_receipt_event: "created",
              },
              replacement_for_mission_id: "mission_failed_source",
              replacement_for_status: "failed",
              replacement_source_action: "retry_or_deadletter",
              replacement_source_target_id: "tsk_failed_source",
              replacement_reason: "source operation failed before replacement",
              replacement_declared_by: "chat_ui.orb",
            },
          ],
          mission_queue: [
            {
              id: "mission_blocked",
              status: "blocked",
              owner_id: "owner.blocked",
              dependency_ids: ["dep_policy", "dep_trust"],
              dependency_count: 2,
              dependency_state: {
                status: "blocked",
                total: 2,
                resolved: 1,
                unresolved: 1,
                first_unresolved: {
                  id: "dep_trust",
                  kind: "unknown",
                  state: "missing",
                  status: "missing",
                },
                items: [
                  {
                    id: "dep_trust",
                    kind: "unknown",
                    state: "missing",
                    status: "missing",
                  },
                ],
              },
              escalation_path: "Raise trust or reduce scope.",
              recommended_action: "raise_trust_or_reduce_risk",
              advance: {
                eligible: false,
                action: "raise_trust_or_reduce_risk",
                target_id: "tsk_blocked",
                reason: "A linked task is blocked by trust posture.",
              },
              last_task_approval_id: "apr_queue_exact",
              last_task_previous_approval_id: "apr_queue_previous",
              last_task_previous_approval_status: "approved",
              last_task_approval_status: "pending",
              last_task_approval_replacement_kind: "plugin.run.mismatch",
              last_task_approval_replacement_reason: "approval_payload_mismatch",
              last_task_approval_replacement_changed_keys: ["input"],
              latest_activity: {
                source: "run_ledger",
                name: "governance_hold",
                status: "blocked",
                gate: "trust_gate",
                ts: 1_710_000_655,
              },
              current_task: {
                mission_id: "mission_blocked",
                source: "mission_meta",
                operation_id: "tsk_blocked",
                task_status: "accepted",
                result_status: "blocked",
                gate: "trust_gate",
                approval_id: "apr_queue_exact",
                approval_status: "pending",
              },
              replacement_for_mission_id: "mission_failed_source",
              replacement_for_status: "failed",
              replacement_source_action: "retry_or_deadletter",
              replacement_source_target_id: "tsk_failed_source",
              replacement_reason: "source operation failed before replacement",
              replacement_declared_by: "chat_ui.orb",
              history_count: 2,
              latest_history_event: "mission_ticked",
              latest_history_ts: "2026-04-14T07:45:00Z",
              history_tail: [
                {
                  event: "created",
                  ts: "2026-04-14T07:30:00Z",
                  details: { status: "queued" },
                },
                {
                  event: "mission_ticked",
                  ts: "2026-04-14T07:45:00Z",
                  details: { from: "queued", to: "blocked" },
                },
              ],
            },
          ],
          failed_missions: [
            {
              id: "mission_failed",
              status: "failed",
              objective: "Failed mission with recovery posture",
              recommended_action: "retry_or_deadletter",
              operator_hint: "The latest linked task failed. Retry the work or deadletter the mission.",
              action_target_id: "tsk_failed",
              recovery: {
                source_status: "failed",
                action: "retry_or_deadletter",
                target_id: "tsk_failed",
                reason: "The latest linked task failed. Retry the work or deadletter the mission.",
                next_step: "Review the failed linked task before retrying or deadlettering.",
                operator_required: true,
                automatic_retry: false,
                read_only: true,
                last_review_action: "retry_or_deadletter",
                last_review_outcome: "requires_operator",
                last_review_target_id: "tsk_failed",
                last_review_actor: "chat_ui.orb",
                last_reviewed_at: "2026-04-14T08:10:00Z",
                replacement_mission_id: "mission_replacement",
                replacement_status: "queued",
                replacement_objective: "Replacement mission",
                replacement_next_step: "Declare the first bounded operation.",
              },
              last_recovery_action: "retry_or_deadletter",
              last_recovery_outcome: "requires_operator",
              last_recovery_target_id: "tsk_failed",
              last_recovery_actor: "chat_ui.orb",
              last_recovery_source_status: "failed",
              last_recovery_at: "2026-04-14T08:10:00Z",
              current_task: {
                mission_id: "mission_failed",
                source: "mission_meta",
                operation_id: "tsk_failed",
                task_status: "failed",
                handoff_action: "retry_or_deadletter",
              },
            },
          ],
          deadletter_missions: [
            {
              id: "mission_dead",
              status: "deadlettered",
              objective: "Deadlettered mission with persisted receipts",
              recommended_action: "review_deadletter",
              deadletter_reason: "manual_cleanup",
              recovery: {
                source_status: "deadlettered",
                action: "review_deadletter",
                target_id: "tsk_dead",
                reason: "manual_cleanup",
                next_step: "Review receipts and declare replacement work if continuation is still needed.",
                operator_required: true,
                automatic_retry: false,
                read_only: true,
              },
              last_task_approval_id: "apr_dead_exact",
              last_task_previous_approval_id: "apr_dead_previous",
              last_task_previous_approval_status: "approved",
              last_task_approval_status: "pending",
              last_task_approval_replacement_kind: "plugin.run.mismatch",
              last_task_approval_replacement_reason: "approval_payload_mismatch",
              last_task_approval_replacement_changed_keys: ["input"],
              history_count: 3,
              latest_history_event: "continuity_updated",
              latest_history_ts: "2026-04-14T08:05:00Z",
              history_tail: [
                {
                  event: "status_changed",
                  ts: "2026-04-14T08:04:00Z",
                  details: { from: "blocked", to: "deadlettered" },
                },
                {
                  event: "continuity_updated",
                  ts: "2026-04-14T08:05:00Z",
                  details: { deadletter_reason: "manual_cleanup" },
                },
              ],
              current_task: {
                mission_id: "mission_dead",
                source: "mission_meta",
                operation_id: "tsk_dead",
                task_status: "accepted",
                result_status: "blocked",
                gate: "approvals_gate",
                approval_id: "apr_dead_exact",
                approval_status: "pending",
              },
            },
          ],
          incidents: [],
        },
        trust: { global_level: 0.6 },
      });
    }

    if (path === "/system/orb_status" || path === "/system/orb-status") {
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    }

    if (path === "/system/orb") {
      return jsonResponse({
        ok: true,
        subsystem: "orb_status",
        generated_at: 1_710_000_789,
        model: {
          plane_map_id: "orb.map",
          plane_map_version: 3,
        },
        core_loop: [{ id: "P1_INTERFACE", name: "Interface" }],
        gates: [{ id: "trust_gate", description: "Trust check" }],
        transitions: {
          forbidden: [{ from: "P1_INTERFACE", to: "P7_EXECUTION", conditions: ["approval required"] }],
        },
        state: {
          render_state: "handback",
          handback_state: {
            state: "continuity_ready",
            headline: "Night shift ready",
          },
        },
      });
    }

    if (path === "/system/operator_mode") {
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    }

    if (path === "/system/operator-mode") {
      return jsonResponse({
        ok: true,
        subsystem: "operator_mode",
        environment: { id: "dev", label: "DEV" },
        posture: { writes: "restricted", trust_level: 0.6 },
        control_mode: { id: "assist", label: "Assist" },
        available_modes: [{ id: "assist", active: true }],
        focus: { plane_id: "P3_GOVERNANCE", label: "Governance" },
        backlog: { queued_tasks: 2 },
        notes: ["compatibility path active"],
      });
    }

    if (path === "/system/config/effective" || path === "/system/effective_config") {
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    }

    if (path === "/system/config") {
      return jsonResponse({
        ts: 1_710_000_999,
        env_profile: "dev",
        run_mode: "api",
        config: {
          ui: {
            preferences: {
              density: "compact",
            },
          },
        },
        sources: {
          base: "settings",
        },
      });
    }

    return jsonResponse({ ok: false, error: `unexpected path ${path}` }, 500);
  });

  try {
    const client = new SettingsClient("http://127.0.0.1:8000");
    const worldState = await client.getWorldState({ timeoutMs: 50 });
    const orbStatus = await client.getOrbStatus({ timeoutMs: 50 });
    const operatorMode = await client.getOperatorMode({ timeoutMs: 50 });
    const effectiveConfig = await client.getEffectiveConfig({ timeoutMs: 50 });

    assert.deepEqual(requestPaths, [
      "/system/world_state",
      "/system/world-state",
      "/system/orb_status",
      "/system/orb-status",
      "/system/orb",
      "/system/operator_mode",
      "/system/operator-mode",
      "/system/config/effective",
      "/system/effective_config",
      "/system/config",
    ]);
    assert.equal(worldState.ok, true);
    assert.equal(worldState.counts?.queued_tasks, 3);
    assert.equal(worldState.paths.data?.path, "C:/Francis/data");
    assert.equal(worldState.overview?.recent_missions?.[0]?.id, "mission_alpha");
    assert.equal(worldState.overview?.recent_missions?.[0]?.owner_id, "owner.alpha");
    assert.deepEqual(worldState.overview?.recent_missions?.[0]?.dependency_ids, ["dep_one"]);
    assert.equal(worldState.overview?.recent_missions?.[0]?.dependency_count, 1);
    assert.equal(worldState.overview?.recent_missions?.[0]?.escalation_path, "Review with operator if blocked.");
    assert.equal(worldState.overview?.recent_missions?.[0]?.latest_activity?.name, "created");
    assert.equal(worldState.overview?.recent_missions?.[0]?.latest_activity?.status, "queued");
    assert.equal(worldState.overview?.recent_missions?.[0]?.current_task?.operation_id, "tsk_alpha");
    assert.equal(worldState.overview?.recent_missions?.[0]?.current_task?.latest_receipt_event, "created");
    assert.equal(worldState.overview?.mission_queue?.[0]?.latest_activity?.name, "governance_hold");
    assert.equal(worldState.overview?.mission_queue?.[0]?.latest_activity?.gate, "trust_gate");
    assert.equal(worldState.overview?.recent_missions?.[0]?.replacement_for_mission_id, "mission_failed_source");
    assert.equal(worldState.overview?.recent_missions?.[0]?.replacement_source_action, "retry_or_deadletter");
    assert.equal(worldState.overview?.recent_missions?.[0]?.replacement_source_target_id, "tsk_failed_source");
    assert.equal(worldState.overview?.mission_queue?.[0]?.current_task?.operation_id, "tsk_blocked");
    assert.equal(worldState.overview?.mission_queue?.[0]?.current_task?.approval_id, "apr_queue_exact");
    assert.equal(worldState.overview?.mission_queue?.[0]?.current_task?.gate, "trust_gate");
    assert.equal(worldState.overview?.mission_queue?.[0]?.owner_id, "owner.blocked");
    assert.deepEqual(worldState.overview?.mission_queue?.[0]?.dependency_ids, ["dep_policy", "dep_trust"]);
    assert.equal(worldState.overview?.mission_queue?.[0]?.dependency_count, 2);
    assert.equal(worldState.overview?.mission_queue?.[0]?.dependency_state?.status, "blocked");
    assert.equal(worldState.overview?.mission_queue?.[0]?.dependency_state?.first_unresolved?.id, "dep_trust");
    assert.equal(worldState.overview?.mission_queue?.[0]?.escalation_path, "Raise trust or reduce scope.");
    assert.equal(worldState.overview?.mission_queue?.[0]?.last_task_approval_id, "apr_queue_exact");
    assert.equal(worldState.overview?.mission_queue?.[0]?.last_task_previous_approval_id, "apr_queue_previous");
    assert.equal(worldState.overview?.mission_queue?.[0]?.last_task_previous_approval_status, "approved");
    assert.equal(worldState.overview?.mission_queue?.[0]?.last_task_approval_status, "pending");
    assert.equal(worldState.overview?.mission_queue?.[0]?.last_task_approval_replacement_kind, "plugin.run.mismatch");
    assert.equal(
      worldState.overview?.mission_queue?.[0]?.last_task_approval_replacement_reason,
      "approval_payload_mismatch",
    );
    assert.deepEqual(worldState.overview?.mission_queue?.[0]?.last_task_approval_replacement_changed_keys, ["input"]);
    assert.equal(worldState.overview?.mission_queue?.[0]?.advance?.eligible, false);
    assert.equal(worldState.overview?.mission_queue?.[0]?.advance?.action, "raise_trust_or_reduce_risk");
    assert.equal(worldState.overview?.mission_queue?.[0]?.advance?.target_id, "tsk_blocked");
    assert.equal(worldState.overview?.mission_queue?.[0]?.history_count, 2);
    assert.equal(worldState.overview?.mission_queue?.[0]?.replacement_for_mission_id, "mission_failed_source");
    assert.equal(worldState.overview?.mission_queue?.[0]?.replacement_for_status, "failed");
    assert.equal(worldState.overview?.mission_queue?.[0]?.replacement_declared_by, "chat_ui.orb");
    assert.equal(worldState.overview?.mission_queue?.[0]?.latest_history_event, "mission_ticked");
    assert.equal(worldState.overview?.mission_queue?.[0]?.latest_history_ts, "2026-04-14T07:45:00Z");
    assert.equal(worldState.overview?.mission_queue?.[0]?.history_tail?.[1]?.event, "mission_ticked");
    assert.equal(worldState.overview?.failed_missions?.[0]?.id, "mission_failed");
    assert.equal(worldState.overview?.failed_missions?.[0]?.recovery?.action, "retry_or_deadletter");
    assert.equal(worldState.overview?.failed_missions?.[0]?.recovery?.source_status, "failed");
    assert.equal(worldState.overview?.failed_missions?.[0]?.recovery?.target_id, "tsk_failed");
    assert.equal(worldState.overview?.failed_missions?.[0]?.recovery?.last_review_action, "retry_or_deadletter");
    assert.equal(worldState.overview?.failed_missions?.[0]?.recovery?.last_review_outcome, "requires_operator");
    assert.equal(worldState.overview?.failed_missions?.[0]?.recovery?.replacement_mission_id, "mission_replacement");
    assert.equal(worldState.overview?.failed_missions?.[0]?.recovery?.replacement_status, "queued");
    assert.equal(worldState.overview?.failed_missions?.[0]?.recovery?.replacement_objective, "Replacement mission");
    assert.equal(worldState.overview?.failed_missions?.[0]?.last_recovery_action, "retry_or_deadletter");
    assert.equal(worldState.overview?.failed_missions?.[0]?.last_recovery_outcome, "requires_operator");
    assert.equal(worldState.overview?.failed_missions?.[0]?.last_recovery_actor, "chat_ui.orb");
    assert.equal(worldState.overview?.failed_missions?.[0]?.last_recovery_source_status, "failed");
    assert.equal(worldState.overview?.failed_missions?.[0]?.current_task?.operation_id, "tsk_failed");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.id, "mission_dead");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.recovery?.action, "review_deadletter");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.recovery?.target_id, "tsk_dead");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.recovery?.automatic_retry, false);
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.recovery?.read_only, true);
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.last_task_approval_id, "apr_dead_exact");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.current_task?.operation_id, "tsk_dead");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.current_task?.approval_id, "apr_dead_exact");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.last_task_previous_approval_id, "apr_dead_previous");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.last_task_previous_approval_status, "approved");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.last_task_approval_status, "pending");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.last_task_approval_replacement_kind, "plugin.run.mismatch");
    assert.equal(
      worldState.overview?.deadletter_missions?.[0]?.last_task_approval_replacement_reason,
      "approval_payload_mismatch",
    );
    assert.deepEqual(worldState.overview?.deadletter_missions?.[0]?.last_task_approval_replacement_changed_keys, [
      "input",
    ]);
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.history_count, 3);
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.latest_history_event, "continuity_updated");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.latest_history_ts, "2026-04-14T08:05:00Z");
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.history_tail?.length, 2);
    assert.equal(worldState.overview?.deadletter_missions?.[0]?.history_tail?.[0]?.event, "status_changed");
    assert.equal(
      (worldState.overview?.deadletter_missions?.[0]?.history_tail?.[1]?.details as Record<string, unknown>)?.deadletter_reason,
      "manual_cleanup",
    );
    assert.equal(worldState.overview?.pending_approvals?.[0]?.request_kind, "plugin.run.request");
    assert.equal(worldState.overview?.pending_approvals?.[0]?.previous_approval_id, "apr_plugin_old");
    assert.equal(worldState.overview?.pending_approvals?.[0]?.previous_approval_status, "approved");
    assert.equal(worldState.overview?.pending_approvals?.[0]?.replacement_kind, "plugin.run.mismatch");
    assert.equal(worldState.overview?.pending_approvals?.[0]?.replacement_reason, "approval_payload_mismatch");
    assert.deepEqual(worldState.overview?.pending_approvals?.[0]?.replacement_expected_payload_keys, [
      "action",
      "input",
      "plugin_id",
    ]);
    assert.deepEqual(worldState.overview?.pending_approvals?.[0]?.replacement_previous_payload_keys, [
      "action",
      "input",
      "plugin_id",
    ]);
    assert.deepEqual(worldState.overview?.pending_approvals?.[0]?.replacement_changed_keys, ["input"]);
    assert.equal(worldState.overview?.pending_approvals?.[0]?.payload_summary?.requested_action, "deploy");
    assert.equal(worldState.overview?.pending_approvals?.[0]?.payload_summary?.plugin_id, "plugin.deploy");
    assert.equal(worldState.overview?.pending_approvals?.[0]?.payload_summary?.required_trust, 5);
    assert.deepEqual(worldState.overview?.pending_approvals?.[0]?.payload_summary?.input_keys, ["target"]);
    assert.deepEqual(worldState.overview?.pending_approvals?.[0]?.payload_summary?.params_keys, ["region"]);
    assert.equal(worldState.trust?.global_level, 0.6);
    assert.equal(orbStatus.ok, true);
    assert.equal(orbStatus.model?.plane_map_id, "orb.map");
    assert.equal(orbStatus.core_loop?.[0]?.id, "P1_INTERFACE");
    assert.equal(orbStatus.gates?.[0]?.id, "trust_gate");
    assert.equal(orbStatus.transitions?.forbidden[0]?.to, "P7_EXECUTION");
    assert.deepEqual(orbStatus.state, {
      render_state: "handback",
      handback_state: {
        state: "continuity_ready",
        headline: "Night shift ready",
      },
    });
    assert.equal(operatorMode.ok, true);
    assert.equal(operatorMode.control_mode?.id, "assist");
    assert.equal(operatorMode.focus?.plane_id, "P3_GOVERNANCE");
    assert.equal(operatorMode.posture?.writes, "restricted");
    assert.equal(effectiveConfig.env_profile, "dev");
    assert.equal(effectiveConfig.config.ui.preferences.density, "compact");
    assert.equal(effectiveConfig.sources?.base, "settings");
  } finally {
    restoreFetch();
  }
});

test("SettingsClient.getContinuityLedger requests the continuity ledger tail with a bounded limit", async () => {
  const requests: Array<{ path: string; limit: string | null }> = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, limit: parsed.searchParams.get("limit") });

    return jsonResponse({
      entries: [
        {
          ts: 1_710_001_501,
          role: "user",
          content: "Carry forward the morning continuity pass.",
          meta: { session_id: "chat_alpha", mission_id: "mission_alpha" },
        },
        {
          ts: 1_710_001_540,
          role: "system",
          content: "daemon started",
          meta: { subsystem: "daemon", profile: "dev", run_mode: "api" },
        },
      ],
    });
  });

  try {
    const client = new SettingsClient("http://127.0.0.1:8000");
    const ledger = await client.getContinuityLedger({ limit: 8, timeoutMs: 50 });

    assert.deepEqual(requests, [{ path: "/continuity/ledger", limit: "8" }]);
    assert.equal(ledger.entries.length, 2);
    assert.equal(ledger.entries[0]?.role, "user");
    assert.equal(ledger.entries[0]?.meta?.mission_id, "mission_alpha");
    assert.equal(ledger.entries[1]?.role, "system");
    assert.equal(ledger.entries[1]?.meta?.subsystem, "daemon");
    assert.equal(ledger.entries[1]?.meta?.run_mode, "api");
    assert.equal(ledger.error, undefined);
  } finally {
    restoreFetch();
  }
});

test("SettingsClient.getObserverEvents uses bounded audit aliases and preserves receipt history", async () => {
  const requests: Array<{
    path: string;
    limit: string | null;
    status: string | null;
    decision: string | null;
  }> = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      limit: parsed.searchParams.get("limit"),
      status: parsed.searchParams.get("status"),
      decision: parsed.searchParams.get("decision"),
    });

    if (parsed.pathname === "/system/observer/events" || parsed.pathname === "/system/observer/log") {
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    }

    if (parsed.pathname === "/system/observer/audit") {
      return jsonResponse({
        ok: true,
        subsystem: "observer_events",
        items: [
          {
            receipt_id: "obs_scan_007",
            event: "observer.scan",
            status: "attention",
            decision: "urgent_review",
            headline: "Observer flagged 1 active incident(s); highest-priority issue: Tasks are blocked by governance.",
            incident_count: 1,
            probes: ["task_runtime"],
            trace_id: "trace_observer_events",
            run_id: "run_observer_events",
          },
        ],
        total: 1,
        limit: 6,
      });
    }

    return jsonResponse({ ok: false, error: `unexpected path ${parsed.pathname}` }, 500);
  });

  try {
    const client = new SettingsClient("http://127.0.0.1:8000");
    const snapshot = await client.getObserverEvents({
      limit: 6,
      status: "attention",
      decision: "urgent_review",
      timeoutMs: 50,
    });

    assert.deepEqual(requests, [
      {
        path: "/system/observer/events",
        limit: "6",
        status: "attention",
        decision: "urgent_review",
      },
      {
        path: "/system/observer/log",
        limit: "6",
        status: "attention",
        decision: "urgent_review",
      },
      {
        path: "/system/observer/audit",
        limit: "6",
        status: "attention",
        decision: "urgent_review",
      },
    ]);
    assert.equal(snapshot.ok, true);
    assert.equal(snapshot.subsystem, "observer_events");
    assert.equal(snapshot.total, 1);
    assert.equal(snapshot.limit, 6);
    assert.equal(snapshot.items[0]?.receipt_id, "obs_scan_007");
    assert.equal(snapshot.items[0]?.decision, "urgent_review");
    assert.equal(snapshot.items[0]?.trace_id, "trace_observer_events");
    assert.equal(snapshot.items[0]?.run_id, "run_observer_events");
  } finally {
    restoreFetch();
  }
});

test("SettingsClient uses compatibility aliases for operator-critical mutations", async () => {
  const requests: Array<{ path: string; method: string; body: unknown }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const path = new URL(url).pathname;
    const method = (init?.method ?? "GET").toUpperCase();
    requests.push({ path, method, body: jsonRequestBody(init) });

    if (path === "/system/operator_mode") {
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    }

    if (path === "/system/operator-mode") {
      return jsonResponse({
        ok: true,
        applied: true,
        status: "applied",
        message: "control_mode_updated",
        subsystem: "operator_mode",
        control_mode: { id: "away", label: "Away" },
      });
    }

    if (path === "/system/observer/scan") {
      return jsonResponse({
        ok: true,
        subsystem: "observer",
        headline: "Observer flagged 1 active incident(s); highest-priority issue: Tasks are blocked by governance.",
        decision: "urgent_review",
        observed_at: 1_710_000_500,
        counts: { active: 1, error: 1 },
        anomaly: {
          score: 50,
          level: "error",
          reasons: ["error incidents: 1", "active probes: task_runtime"],
        },
        readiness: {
          stage: "Stage 2 - Observer",
          status: "ready",
          satisfied: 5,
          total: 5,
          next_action: "Stage 2 observer criteria are satisfied for the current local state.",
          criteria: [
            {
              id: "traceable_scans",
              label: "Scans are traceable",
              status: "satisfied",
              detail: "Recent observer scans include receipt, trace, and run identifiers.",
              evidence: { recent_scan_count: 1, traceable_scan_count: 1 },
            },
          ],
        },
        receipt: {
          receipt_id: "obs_scan_003",
          event: "observer.scan",
          status: "attention",
          decision: "urgent_review",
          headline: "Observer flagged 1 active incident(s); highest-priority issue: Tasks are blocked by governance.",
          incident_count: 1,
          probes: ["task_runtime"],
          probe_statuses: [
            {
              id: "task_runtime",
              status: "attention",
              severity: "error",
              headline: "Tasks are blocked by governance",
              detail: "blocked 1; awaiting approval 0; failed 0.",
              incident_count: 1,
              observed_at: 1_710_000_500,
            },
          ],
          anomaly: {
            score: 50,
            level: "error",
            reasons: ["error incidents: 1", "active probes: task_runtime"],
          },
          trace_id: "trace_observer_scan",
          run_id: "run_observer_scan",
        },
      });
    }

    if (path === "/system/config/mutate") {
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    }

    if (path === "/system/config/patch") {
      return jsonResponse({
        ok: true,
        applied: true,
        status: "applied",
        resulting_value: { density: "compact" },
      });
    }

    if (path === "/system/flags/ui.alias_mode" || path === "/system/feature_flags/ui.alias_mode") {
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    }

    if (path === "/system/flags/set") {
      return jsonResponse({
        ok: true,
        applied: true,
        status: "applied",
        item: { key: "ui.alias_mode", enabled: true },
      });
    }

    return jsonResponse({ ok: false, error: `unexpected path ${path}` }, 500);
  });

  try {
    const client = new SettingsClient("http://127.0.0.1:8000", { mutationsEnabled: true });
    const operatorResponse = await client.setOperatorMode(
      {
        mode: "away",
        reason: "night shift handoff",
        actor: "chat_ui_test",
      },
      { timeoutMs: 50 },
    );
    const observerResponse = await client.recordObserverScan(
      {
        reason: "manual continuity review",
        actor: "chat_ui_test",
      },
      { timeoutMs: 50 },
    );
    const configResponse = await client.mutateConfig(
      {
        op: "merge",
        path: "ui.preferences",
        value: { density: "compact" },
        reason: "compatibility mutation",
      },
      { timeoutMs: 50 },
    );
    const flagResponse = await client.setFeatureFlag("ui.alias_mode", true, {
      reason: "compatibility mutation",
      timeoutMs: 50,
    });

    assert.deepEqual(
      requests.map(({ path, method }) => ({ path, method })),
      [
        { path: "/system/operator_mode", method: "POST" },
        { path: "/system/operator-mode", method: "POST" },
        { path: "/system/observer/scan", method: "POST" },
        { path: "/system/config/mutate", method: "POST" },
        { path: "/system/config/patch", method: "POST" },
        { path: "/system/flags/ui.alias_mode", method: "POST" },
        { path: "/system/feature_flags/ui.alias_mode", method: "POST" },
        { path: "/system/flags/set", method: "POST" },
      ],
    );
    assert.deepEqual(requests[1]?.body, {
      mode: "away",
      reason: "night shift handoff",
      actor: "chat_ui_test",
    });
    assert.deepEqual(requests[2]?.body, {
      reason: "manual continuity review",
      actor: "chat_ui_test",
    });
    assert.deepEqual(requests[4]?.body, {
      op: "merge",
      path: "ui.preferences",
      value: { density: "compact" },
      reason: "compatibility mutation",
    });
    assert.deepEqual(requests[7]?.body, {
      key: "ui.alias_mode",
      enabled: true,
      reason: "compatibility mutation",
    });
    assert.equal(operatorResponse.ok, true);
    assert.equal(operatorResponse.applied, true);
    assert.equal(operatorResponse.snapshot?.control_mode?.id, "away");
    assert.equal(observerResponse.ok, true);
    assert.equal(observerResponse.decision, "urgent_review");
    assert.equal(observerResponse.observed_at, 1_710_000_500);
    assert.equal(observerResponse.readiness?.status, "ready");
    assert.equal(observerResponse.readiness?.criteria?.[0]?.id, "traceable_scans");
    assert.equal(observerResponse.readiness?.criteria?.[0]?.evidence?.recent_scan_count, 1);
    assert.equal(observerResponse.anomaly?.level, "error");
    assert.equal(observerResponse.anomaly?.score, 50);
    assert.equal(observerResponse.receipt?.receipt_id, "obs_scan_003");
    assert.equal(observerResponse.receipt?.anomaly?.level, "error");
    assert.equal(observerResponse.receipt?.probe_statuses?.[0]?.id, "task_runtime");
    assert.equal(observerResponse.receipt?.probe_statuses?.[0]?.status, "attention");
    assert.equal(observerResponse.receipt?.probe_statuses?.[0]?.observed_at, 1_710_000_500);
    assert.equal(observerResponse.receipt?.trace_id, "trace_observer_scan");
    assert.equal(observerResponse.receipt?.run_id, "run_observer_scan");
    assert.equal(configResponse.ok, true);
    assert.deepEqual(configResponse.resulting_value, { density: "compact" });
    assert.equal(flagResponse.ok, true);
    assert.equal(flagResponse.applied, true);
  } finally {
    restoreFetch();
  }
});

test("SettingsClient.getContinuityBriefing falls back to alias routes and preserves embedded operator/orb surfaces", async () => {
  const requestPaths: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const path = new URL(url).pathname;
    requestPaths.push(path);

    if (path === "/continuity/briefing") {
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    }

    if (path === "/continuity/shift_briefing") {
      return jsonResponse({
        ok: true,
        subsystem: "continuity_briefing",
        generated_at: 1_710_000_456,
        briefing: {
          headline: "Night shift ready",
          counts: { queued: 2 },
          focus: [
            {
              id: "mission_alpha",
              objective: "Carry continuity",
              dependency_ids: ["msn_dependency"],
              dependency_count: 1,
              dependency_state: {
                status: "waiting",
                total: 1,
                resolved: 0,
                unresolved: 1,
                first_unresolved: {
                  id: "msn_dependency",
                  kind: "mission",
                  state: "waiting",
                  status: "active",
                },
                items: [
                  {
                    id: "msn_dependency",
                    kind: "mission",
                    state: "waiting",
                    status: "active",
                  },
                ],
              },
              escalation_path: "Ask the operator whether to replace or deadletter the dependency.",
              recommended_action: "resume",
              advance: {
                eligible: false,
                action: "resume",
                target_id: "msn_dependency",
                reason: "Dependency msn_dependency is waiting before the mission can continue.",
              },
              last_task_approval_id: "apr_focus_exact",
              last_task_previous_approval_id: "apr_focus_previous",
              last_task_approval_status: "pending",
              replacement_for_mission_id: "mission_failed_source",
              replacement_for_status: "failed",
              replacement_source_action: "retry_or_deadletter",
              replacement_source_target_id: "tsk_failed_source",
              replacement_reason: "source operation failed before replacement",
              replacement_declared_by: "chat_ui.orb",
              history_count: 3,
              latest_history_event: "mission_ticked",
              latest_history_ts: "2026-04-14T06:30:00Z",
              history_tail: [
                {
                  event: "created",
                  ts: "2026-04-14T06:20:00Z",
                  details: { status: "queued" },
                },
                {
                  event: "mission_ticked",
                  ts: "2026-04-14T06:30:00Z",
                  details: { from: "queued", to: "blocked" },
                },
              ],
              current_task: {
                mission_id: "mission_alpha",
                source: "mission_meta",
                operation_id: "tsk_focus",
                task_status: "accepted",
                result_status: "pending",
                gate: "approvals_gate",
                approval_id: "apr_focus_exact",
                approval_status: "pending",
                handoff_action: "review_pending_approval",
              },
            },
          ],
          readiness: {
            stage: "Stage 3 - Missions",
            status: "review",
            satisfied: 4,
            total: 5,
            next_action: "Exercise mission tick and deadletter paths, then inspect the continuity briefing again.",
            criteria: [
              {
                id: "deadletter_cleanly",
                label: "Failures deadletter cleanly",
                status: "not_yet_observed",
                detail: "Deadletter path has not been exercised in this data set.",
                evidence: { deadlettered_count: 0 },
              },
            ],
          },
          observer: {
            headline: "Observer flagged 1 active incident(s); Tasks are blocked by governance leads review.",
            counts: { active: 1, error: 1 },
            probes: [
              {
                id: "stack_status",
                status: "ok",
                severity: "clear",
                headline: "Stack surfaces are ready.",
                detail: "9/9 stack surfaces ready; missing 0.",
                incident_count: 0,
              },
              {
                id: "task_runtime",
                status: "attention",
                severity: "error",
                headline: "Tasks are blocked by governance",
                detail: "blocked 1; awaiting approval 0; failed 0.",
                incident_count: 1,
                observed_at: 1_710_000_450,
              },
            ],
            anomaly: {
              score: 50,
              level: "error",
              reasons: ["error incidents: 1", "active probes: task_runtime"],
            },
            readiness: {
              stage: "Stage 2 - Observer",
              status: "ready",
              satisfied: 5,
              total: 5,
              next_action: "Stage 2 observer criteria are satisfied for the current local state.",
              criteria: [
                {
                  id: "observer_findings_receipted",
                  label: "Observer findings are receipted",
                  status: "satisfied",
                  detail: "The latest observer scan receipt covers the current active findings.",
                  evidence: { latest_receipt_id: "obs_scan_001" },
                },
              ],
            },
            observed_at: 1_710_000_450,
            focus: [
              {
                id: "governance.blocked_tasks",
                severity: "error",
                category: "governance",
                title: "Tasks are blocked by governance",
                detail: "1 task is blocked by trust policy.",
                source: "tasks",
                probe: "task_runtime",
                observed_at: 1_710_000_450,
                evidence: [
                  {
                    kind: "task",
                    id: "tsk_blocked",
                    label: "Blocked deploy",
                    status: "blocked",
                    detail: "insufficient_trust",
                  },
                ],
              },
            ],
            recent_scans: [
              {
                receipt_id: "obs_scan_001",
                event: "observer.scan",
                status: "attention",
                decision: "urgent_review",
                headline: "Observer flagged 1 active incident(s); highest-priority issue: Tasks are blocked by governance.",
                incident_count: 1,
                probes: ["task_runtime"],
                probe_statuses: [
                  {
                    id: "task_runtime",
                    status: "attention",
                    severity: "error",
                    headline: "Tasks are blocked by governance",
                    detail: "blocked 1; awaiting approval 0; failed 0.",
                    incident_count: 1,
                  },
                ],
                anomaly: {
                  score: 50,
                  level: "error",
                  reasons: ["error incidents: 1", "active probes: task_runtime"],
                },
                focus: [
                  {
                    id: "governance.blocked_tasks",
                    severity: "error",
                    title: "Tasks are blocked by governance",
                  },
                ],
                generated_at: 1_710_000_452,
                actor: "operator",
                reason: "manual_scan",
                trace_id: "trace_observer_scan",
                run_id: "run_observer_scan",
              },
            ],
          },
        },
        mission_status_counts: { queued: 2 },
        recent_missions: [{ id: "mission_alpha", status: "queued" }],
        operator: {
          available: true,
          control_mode: { id: "assist", label: "Assist" },
          focus: { plane_id: "P3_GOVERNANCE", label: "Governance" },
          posture: { writes: "restricted", trust_level: 0.4 },
        },
        orb: {
          available: true,
          state: { current: "observe", handback_state: { state: "none" } },
        },
      });
    }

    return jsonResponse({ ok: false, error: `unexpected path ${path}` }, 500);
  });

  try {
    const client = new SettingsClient("http://127.0.0.1:8000");
    const briefing = await client.getContinuityBriefing({ timeoutMs: 50 });

    assert.deepEqual(requestPaths, ["/continuity/briefing", "/continuity/shift_briefing"]);
    assert.equal(briefing.ok, true);
    assert.equal(briefing.generated_at, 1_710_000_456);
    assert.equal(briefing.briefing?.headline, "Night shift ready");
    assert.equal(briefing.briefing?.readiness?.stage, "Stage 3 - Missions");
    assert.equal(briefing.briefing?.readiness?.status, "review");
    assert.equal(briefing.briefing?.readiness?.satisfied, 4);
    assert.equal(briefing.briefing?.readiness?.criteria?.[0]?.id, "deadletter_cleanly");
    assert.equal(briefing.briefing?.readiness?.criteria?.[0]?.evidence?.deadlettered_count, 0);
    assert.deepEqual(briefing.briefing?.focus?.[0]?.dependency_ids, ["msn_dependency"]);
    assert.equal(briefing.briefing?.focus?.[0]?.dependency_count, 1);
    assert.equal(briefing.briefing?.focus?.[0]?.dependency_state?.status, "waiting");
    assert.equal(briefing.briefing?.focus?.[0]?.dependency_state?.first_unresolved?.id, "msn_dependency");
    assert.equal(
      briefing.briefing?.focus?.[0]?.escalation_path,
      "Ask the operator whether to replace or deadletter the dependency.",
    );
    assert.equal(briefing.briefing?.focus?.[0]?.last_task_approval_id, "apr_focus_exact");
    assert.equal(briefing.briefing?.focus?.[0]?.last_task_previous_approval_id, "apr_focus_previous");
    assert.equal(briefing.briefing?.focus?.[0]?.last_task_approval_status, "pending");
    assert.equal(briefing.briefing?.focus?.[0]?.replacement_for_mission_id, "mission_failed_source");
    assert.equal(briefing.briefing?.focus?.[0]?.replacement_source_action, "retry_or_deadletter");
    assert.equal(briefing.briefing?.focus?.[0]?.replacement_source_target_id, "tsk_failed_source");
    assert.equal(briefing.briefing?.focus?.[0]?.current_task?.operation_id, "tsk_focus");
    assert.equal(briefing.briefing?.focus?.[0]?.current_task?.approval_id, "apr_focus_exact");
    assert.equal(briefing.briefing?.focus?.[0]?.current_task?.handoff_action, "review_pending_approval");
    assert.equal(briefing.briefing?.focus?.[0]?.history_count, 3);
    assert.equal(briefing.briefing?.focus?.[0]?.latest_history_event, "mission_ticked");
    assert.equal(briefing.briefing?.focus?.[0]?.latest_history_ts, "2026-04-14T06:30:00Z");
    assert.equal(briefing.briefing?.focus?.[0]?.history_tail?.[1]?.event, "mission_ticked");
    assert.equal(briefing.briefing?.focus?.[0]?.advance?.eligible, false);
    assert.equal(briefing.briefing?.focus?.[0]?.advance?.action, "resume");
    assert.equal(briefing.briefing?.focus?.[0]?.advance?.target_id, "msn_dependency");
    assert.equal(briefing.briefing?.observer?.counts?.active, 1);
    assert.equal(briefing.briefing?.observer?.probes?.[1]?.id, "task_runtime");
    assert.equal(briefing.briefing?.observer?.probes?.[1]?.status, "attention");
    assert.equal(briefing.briefing?.observer?.anomaly?.level, "error");
    assert.equal(briefing.briefing?.observer?.anomaly?.score, 50);
    assert.equal(briefing.briefing?.observer?.readiness?.status, "ready");
    assert.equal(briefing.briefing?.observer?.readiness?.criteria?.[0]?.id, "observer_findings_receipted");
    assert.equal(briefing.briefing?.observer?.readiness?.criteria?.[0]?.evidence?.latest_receipt_id, "obs_scan_001");
    assert.equal(briefing.briefing?.observer?.focus?.[0]?.probe, "task_runtime");
    assert.equal(briefing.briefing?.observer?.focus?.[0]?.evidence?.[0]?.id, "tsk_blocked");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.receipt_id, "obs_scan_001");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.decision, "urgent_review");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.probes?.[0], "task_runtime");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.probe_statuses?.[0]?.id, "task_runtime");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.probe_statuses?.[0]?.status, "attention");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.trace_id, "trace_observer_scan");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.run_id, "run_observer_scan");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.anomaly?.level, "error");
    assert.equal(briefing.operator?.available, true);
    assert.equal(briefing.operator?.control_mode?.id, "assist");
    assert.equal(briefing.operator?.focus?.plane_id, "P3_GOVERNANCE");
    assert.equal(briefing.operator?.posture?.writes, "restricted");
    assert.equal(briefing.operator?.posture?.trust_level, 0.4);
    assert.equal(briefing.orb?.available, true);
    assert.deepEqual(briefing.orb?.state, {
      current: "observe",
      handback_state: { state: "none" },
    });
  } finally {
    restoreFetch();
  }
});

test("SettingsClient.getContinuityBriefing preserves counts and handoff lists without headline or focus", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({
      ok: true,
      subsystem: "continuity_briefing",
      generated_at: 1_710_001_234,
      briefing: {
        counts: { queued: 2, failed: 1, deadlettered: 1 },
        readiness: {
          stage: "Stage 3 - Missions",
          status: "review",
          satisfied: 0,
          total: 5,
          criteria: [
            {
              id: "idempotent_ticks",
              label: "Mission ticks are idempotent",
              status: "not_yet_observed",
            },
          ],
        },
        observer: {
          headline: "Observer reports no active incidents.",
          counts: { active: 0 },
          probes: [
            {
              id: "approval_queue",
              status: "ok",
              severity: "clear",
              headline: "Approval queue is clear.",
              detail: "0 approval request(s) queued for review.",
              incident_count: 0,
            },
          ],
          anomaly: {
            score: 0,
            level: "clear",
          },
          focus: [],
          recent_scans: [
            {
              receipt_id: "obs_scan_002",
              status: "ok",
              decision: "stable",
              headline: "Observer reports no active incidents.",
              probe_statuses: [
                {
                  id: "approval_queue",
                  status: "ok",
                  severity: "clear",
                  headline: "Approval queue is clear.",
                  detail: "0 approval request(s) queued for review.",
                  incident_count: 0,
                },
              ],
              anomaly: {
                score: 0,
                level: "clear",
              },
              trace_id: "trace_observer_clear",
              run_id: "run_observer_clear",
            },
          ],
        },
        recently_completed: [
          {
            id: "mission_done",
            objective: "Finish overnight hardening",
            updated_at: "2026-04-14T07:00:00Z",
            history_count: 4,
            latest_history_event: "status_changed",
            latest_history_ts: "2026-04-14T07:00:00Z",
            history_tail: [
              {
                event: "advance_receipt",
                ts: "2026-04-14T06:59:00Z",
                details: { operation_id: "tsk_done" },
              },
              {
                event: "status_changed",
                ts: "2026-04-14T07:00:00Z",
                details: { from: "active", to: "completed" },
              },
            ],
            current_task: {
              mission_id: "mission_done",
              source: "mission_meta",
              operation_id: "tsk_done",
              task_status: "completed",
              result_status: "completed",
              handoff_action: "review_completion",
            },
          },
        ],
        failed_preview: [
          {
            id: "mission_failed",
            status: "failed",
            objective: "Recover failed sync",
            reason: "worker_failed",
            recommended_action: "retry_or_deadletter",
            operator_hint: "The latest linked task failed. Retry the work or deadletter the mission.",
            action_target_id: "tsk_failed",
            recovery: {
              source_status: "failed",
              action: "retry_or_deadletter",
              target_id: "tsk_failed",
              reason: "worker_failed",
              next_step: "Review the failed linked task before retrying or deadlettering.",
              operator_required: true,
              automatic_retry: false,
              read_only: true,
              last_review_action: "retry_or_deadletter",
              last_review_outcome: "requires_operator",
              last_review_target_id: "tsk_failed",
              last_review_actor: "chat_ui.orb",
              last_reviewed_at: "2026-04-14T08:10:00Z",
              replacement_mission_id: "mission_replacement",
              replacement_status: "active",
              replacement_last_task_id: "tsk_replacement",
              replacement_last_task_status: "running",
            },
            last_recovery_action: "retry_or_deadletter",
            last_recovery_outcome: "requires_operator",
            last_recovery_target_id: "tsk_failed",
            last_recovery_actor: "chat_ui.orb",
            last_recovery_source_status: "failed",
            last_recovery_at: "2026-04-14T08:10:00Z",
            current_task: {
              mission_id: "mission_failed",
              source: "mission_meta",
              operation_id: "tsk_failed",
              task_status: "failed",
              handoff_action: "retry_or_deadletter",
            },
          },
        ],
        deadletter_preview: [
          {
            id: "mission_dead",
            objective: "Retry failed sync",
            reason: "policy_blocked",
            recommended_action: "inspect approvals",
            recovery: {
              source_status: "deadlettered",
              action: "review_deadletter",
              target_id: "tsk_dead_current",
              reason: "policy_blocked",
              next_step: "Review receipts before declaring replacement work.",
              operator_required: true,
              automatic_retry: false,
              read_only: true,
            },
            last_task_id: "tsk_dead",
            last_task_status: "accepted",
            last_task_result_status: "blocked",
            last_task_gate: "approvals_gate",
            last_task_approval_id: "apr_dead_exact",
            last_task_previous_approval_id: "apr_dead_previous",
            last_task_previous_approval_status: "approved",
            last_task_approval_status: "pending",
            last_task_approval_replacement_kind: "plugin.run.mismatch",
            last_task_approval_replacement_reason: "approval_payload_mismatch",
            last_task_approval_replacement_changed_keys: ["input"],
            current_task: {
              mission_id: "mission_dead",
              source: "mission_meta",
              operation_id: "tsk_dead_current",
              task_status: "accepted",
              result_status: "blocked",
              gate: "approvals_gate",
              approval_id: "apr_dead_exact",
              approval_status: "pending",
              handoff_action: "review_deadletter",
            },
            history_count: 5,
            latest_history_event: "continuity_updated",
            latest_history_ts: "2026-04-14T08:01:00Z",
            history_tail: [
              {
                event: "status_changed",
                ts: "2026-04-14T08:00:30Z",
                details: { from: "blocked", to: "deadlettered" },
              },
              {
                event: "continuity_updated",
                ts: "2026-04-14T08:01:00Z",
                details: { deadletter_reason: "policy_blocked" },
              },
            ],
            updated_at: "2026-04-14T08:00:00Z",
            latest_activity: {
              name: "governance_hold",
              status: "blocked",
              gate: "approvals_gate",
              ts: 1_744_622_800,
            },
          },
        ],
      },
    }),
  );

  try {
    const client = new SettingsClient("http://127.0.0.1:8000");
    const briefing = await client.getContinuityBriefing({ timeoutMs: 50 });

    assert.equal(briefing.ok, true);
    assert.deepEqual(briefing.briefing?.counts, { queued: 2, failed: 1, deadlettered: 1 });
    assert.equal(briefing.briefing?.readiness?.status, "review");
    assert.equal(briefing.briefing?.readiness?.satisfied, 0);
    assert.equal(briefing.briefing?.readiness?.total, 5);
    assert.equal(briefing.briefing?.readiness?.criteria?.[0]?.id, "idempotent_ticks");
    assert.equal(briefing.briefing?.recently_completed?.[0]?.id, "mission_done");
    assert.equal(briefing.briefing?.recently_completed?.[0]?.current_task?.operation_id, "tsk_done");
    assert.equal(briefing.briefing?.recently_completed?.[0]?.current_task?.handoff_action, "review_completion");
    assert.equal(briefing.briefing?.recently_completed?.[0]?.history_count, 4);
    assert.equal(briefing.briefing?.recently_completed?.[0]?.latest_history_event, "status_changed");
    assert.equal(briefing.briefing?.recently_completed?.[0]?.history_tail?.[1]?.event, "status_changed");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.id, "mission_failed");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.status, "failed");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.recovery?.action, "retry_or_deadletter");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.recovery?.target_id, "tsk_failed");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.recovery?.last_review_action, "retry_or_deadletter");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.recovery?.last_review_outcome, "requires_operator");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.recovery?.replacement_mission_id, "mission_replacement");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.recovery?.replacement_status, "active");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.recovery?.replacement_last_task_id, "tsk_replacement");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.last_recovery_action, "retry_or_deadletter");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.last_recovery_outcome, "requires_operator");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.last_recovery_source_status, "failed");
    assert.equal(briefing.briefing?.failed_preview?.[0]?.current_task?.operation_id, "tsk_failed");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.id, "mission_dead");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.recovery?.action, "review_deadletter");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.recovery?.target_id, "tsk_dead_current");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.recovery?.automatic_retry, false);
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.recovery?.read_only, true);
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.last_task_id, "tsk_dead");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.current_task?.operation_id, "tsk_dead_current");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.current_task?.approval_id, "apr_dead_exact");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.current_task?.handoff_action, "review_deadletter");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.last_task_status, "accepted");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.last_task_result_status, "blocked");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.last_task_gate, "approvals_gate");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.last_task_approval_id, "apr_dead_exact");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.last_task_previous_approval_id, "apr_dead_previous");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.last_task_previous_approval_status, "approved");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.last_task_approval_status, "pending");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.last_task_approval_replacement_kind, "plugin.run.mismatch");
    assert.equal(
      briefing.briefing?.deadletter_preview?.[0]?.last_task_approval_replacement_reason,
      "approval_payload_mismatch",
    );
    assert.deepEqual(briefing.briefing?.deadletter_preview?.[0]?.last_task_approval_replacement_changed_keys, [
      "input",
    ]);
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.history_count, 5);
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.latest_history_event, "continuity_updated");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.latest_history_ts, "2026-04-14T08:01:00Z");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.history_tail?.length, 2);
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.history_tail?.[0]?.event, "status_changed");
    assert.equal(
      (briefing.briefing?.deadletter_preview?.[0]?.history_tail?.[1]?.details as Record<string, unknown>)?.deadletter_reason,
      "policy_blocked",
    );
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.latest_activity?.gate, "approvals_gate");
    assert.equal(briefing.briefing?.observer?.headline, "Observer reports no active incidents.");
    assert.equal(briefing.briefing?.observer?.probes?.[0]?.id, "approval_queue");
    assert.equal(briefing.briefing?.observer?.probes?.[0]?.status, "ok");
    assert.equal(briefing.briefing?.observer?.anomaly?.level, "clear");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.decision, "stable");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.probe_statuses?.[0]?.id, "approval_queue");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.trace_id, "trace_observer_clear");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.run_id, "run_observer_clear");
    assert.equal(briefing.briefing?.observer?.recent_scans?.[0]?.anomaly?.level, "clear");
    assert.equal(briefing.briefing?.headline, "");
    assert.equal(briefing.briefing?.focus?.length, 0);
  } finally {
    restoreFetch();
  }
});
