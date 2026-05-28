import assert from "node:assert/strict";
import test from "node:test";

import { TelemetryClient, parseTelemetryStatus } from "./index.ts";

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

test("parseTelemetryStatus preserves Stage 7 source readback truth", () => {
  const status = parseTelemetryStatus({
    ok: true,
    kind: "francis.stage7.telemetry.status",
    stage: "Stage 7 / Telemetry MVP",
    status: "active",
    active: true,
    claim: "explicit_telemetry_events_recorded",
    ts: 123,
    source_total: 3,
    active_source_total: 2,
    sources: [
      {
        id: "terminal",
        label: "Terminal connector",
        description: "Command outcomes and shell context, once explicitly scoped.",
        status: "not_connected",
        active: false,
        visible_indicator: true,
        hidden_sensing: false,
        scope: {
          status: "not_granted",
          allowed_paths: [],
          allowed_processes: [],
          denied_by_default: true,
        },
        redaction: { redact_before_storage: true },
        retention: { stores_raw_events: false },
        signals: [],
        expected_signals: ["command", "cwd"],
        blocked_by: ["connector_not_configured", "operator_scope_not_granted"],
        authority: { telemetry_collection: false, execution_authority: false },
        latest_event: {
          event_id: "tel_terminal_123",
          recorded_ts: 123,
          exit_code: 0,
          cwd: "D:/Francis",
          command: "echo [REDACTED:secret]",
          operation_id: "op_terminal",
          approval_id: "apr_terminal",
          trace_id: "trace_terminal",
          run_id: "run_terminal",
          artifact_dir: "supervised_exec/apr_terminal",
        },
        routes: {
          record: "/telemetry/terminal/events",
        },
      },
      {
        id: "git",
        label: "Git watcher",
        description: "Repository state and file-change activity, once explicitly scoped.",
        status: "snapshot_ready",
        active: true,
        visible_indicator: true,
        hidden_sensing: false,
        scope: {
          status: "repo_root_only",
          allowed_paths: ["D:/Francis"],
          allowed_processes: ["git status"],
          denied_by_default: true,
        },
        redaction: { redact_before_storage: true },
        retention: { stores_raw_events: false },
        signals: ["branch", "dirty_state"],
        expected_signals: ["branch"],
        blocked_by: [],
        authority: { git_watch: false, execution_authority: false },
        latest_snapshot: {
          branch: "main",
          head: "abcdef123456",
          upstream: "origin/main",
          ahead: 0,
          behind: 0,
          dirty: true,
          changed_count: 1,
          changed_paths: [{ status: "M", path: "src/francis/telemetry/git.py" }],
          ts: 123,
        },
        routes: {
          status: "/telemetry/git/status",
        },
      },
      {
        id: "ide_diagnostics",
        label: "IDE diagnostics connector",
        description: "Editor diagnostics and focused file context, once explicitly scoped.",
        status: "explicit_diagnostics_recorded",
        active: true,
        visible_indicator: true,
        hidden_sensing: false,
        scope: {
          status: "write_scope_required",
          allowed_paths: [],
          allowed_processes: [],
          denied_by_default: true,
        },
        redaction: { redact_before_storage: true },
        retention: { stores_raw_events: false, event_count: 1 },
        signals: ["diagnostic_summary"],
        expected_signals: ["file", "diagnostic_code"],
        blocked_by: [],
        authority: { ide_diagnostics: false, execution_authority: false },
        latest_diagnostic: {
          event_id: "tel_ide_123",
          recorded_ts: 123,
          source: "vscode",
          workspace: "D:/Francis",
          file: "src/francis/telemetry/status.py",
          diagnostic_count: 2,
          highest_severity: "error",
          operation_id: "op_ide",
          approval_id: "apr_ide",
          trace_id: "trace_ide",
          run_id: "run_ide",
        },
        routes: {
          record: "/telemetry/ide-diagnostics/events",
          events: "/telemetry/ide-diagnostics/events",
        },
      },
    ],
    redaction: { status: "ready" },
    retention: { status: "bounded_redacted_events", stores_raw_events: false, event_count: 1 },
    sensing: { status: "explicit_events_recorded", hidden_sensing: false },
    governance: { read_only_contract: true, telemetry_collection: false },
    next_smallest_truthful_gap: "stage7_terminal_connector_scope_contract",
  });

  assert.equal(status.kind, "francis.stage7.telemetry.status");
  assert.equal(status.active, true);
  assert.equal(status.active_source_total, 2);
  assert.equal(status.claim, "explicit_telemetry_events_recorded");
  assert.equal(status.sources[0]?.id, "terminal");
  assert.equal(status.sources[0]?.active, false);
  assert.equal(status.sources[0]?.visible_indicator, true);
  assert.equal(status.sources[0]?.hidden_sensing, false);
  assert.equal(status.sources[0]?.scope.status, "not_granted");
  assert.deepEqual(status.sources[0]?.blocked_by, ["connector_not_configured", "operator_scope_not_granted"]);
  assert.equal(status.sources[0]?.latest_event?.event_id, "tel_terminal_123");
  assert.equal(status.sources[0]?.latest_event?.operation_id, "op_terminal");
  assert.equal(status.sources[0]?.routes.record, "/telemetry/terminal/events");
  assert.equal(status.sources[1]?.latest_snapshot?.branch, "main");
  assert.equal(status.sources[1]?.latest_snapshot?.dirty, true);
  assert.equal(status.sources[1]?.latest_snapshot?.changed_paths[0]?.path, "src/francis/telemetry/git.py");
  assert.equal(status.sources[1]?.routes.status, "/telemetry/git/status");
  assert.equal(status.sources[2]?.latest_diagnostic?.event_id, "tel_ide_123");
  assert.equal(status.sources[2]?.latest_diagnostic?.highest_severity, "error");
  assert.equal(status.sources[2]?.routes.record, "/telemetry/ide-diagnostics/events");
  assert.equal(status.governance.telemetry_collection, false);
});

test("TelemetryClient requests the Stage 7 status endpoint", async () => {
  const requests: Array<{ path: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.status",
      stage: "Stage 7 / Telemetry MVP",
      status: "inactive",
      active: false,
      claim: "telemetry_posture_contract_only",
      source_total: 0,
      active_source_total: 0,
      sources: [],
      redaction: {},
      retention: {},
      sensing: {},
      governance: {},
      next_smallest_truthful_gap: "stage7_terminal_connector_scope_contract",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const status = await client.getStatus();
    assert.equal(status.status, "inactive");
    assert.deepEqual(requests, [{ path: "/telemetry/status", method: "GET" }]);
  } finally {
    restore();
  }
});
