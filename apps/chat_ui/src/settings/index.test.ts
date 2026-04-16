import assert from "node:assert/strict";
import test from "node:test";

import { SettingsClient } from "./index.ts";

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
          recent_missions: [{ id: "mission_alpha", status: "queued" }],
          mission_queue: [],
          deadletter_missions: [],
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
    assert.equal(worldState.overview?.pending_approvals?.[0]?.request_kind, "plugin.run.request");
    assert.equal(worldState.overview?.pending_approvals?.[0]?.previous_approval_id, "apr_plugin_old");
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
    assert.deepEqual(requests[3]?.body, {
      op: "merge",
      path: "ui.preferences",
      value: { density: "compact" },
      reason: "compatibility mutation",
    });
    assert.deepEqual(requests[6]?.body, {
      key: "ui.alias_mode",
      enabled: true,
      reason: "compatibility mutation",
    });
    assert.equal(operatorResponse.ok, true);
    assert.equal(operatorResponse.applied, true);
    assert.equal(operatorResponse.snapshot?.control_mode?.id, "away");
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
              recommended_action: "resume",
            },
          ],
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
        counts: { queued: 2, deadlettered: 1 },
        recently_completed: [
          {
            id: "mission_done",
            objective: "Finish overnight hardening",
            updated_at: "2026-04-14T07:00:00Z",
          },
        ],
        deadletter_preview: [
          {
            id: "mission_dead",
            objective: "Retry failed sync",
            reason: "policy_blocked",
            recommended_action: "inspect approvals",
          },
        ],
      },
    }),
  );

  try {
    const client = new SettingsClient("http://127.0.0.1:8000");
    const briefing = await client.getContinuityBriefing({ timeoutMs: 50 });

    assert.equal(briefing.ok, true);
    assert.deepEqual(briefing.briefing?.counts, { queued: 2, deadlettered: 1 });
    assert.equal(briefing.briefing?.recently_completed?.[0]?.id, "mission_done");
    assert.equal(briefing.briefing?.deadletter_preview?.[0]?.id, "mission_dead");
    assert.equal(briefing.briefing?.headline, "");
    assert.equal(briefing.briefing?.focus?.length, 0);
  } finally {
    restoreFetch();
  }
});
