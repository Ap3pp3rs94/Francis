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

test("parseTelemetryStatus preserves inactive Stage 7 source truth", () => {
  const status = parseTelemetryStatus({
    ok: true,
    kind: "francis.stage7.telemetry.status",
    stage: "Stage 7 / Telemetry MVP",
    status: "inactive",
    active: false,
    claim: "telemetry_posture_contract_only",
    ts: 123,
    source_total: 3,
    active_source_total: 0,
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
    ],
    redaction: { status: "ready" },
    retention: { stores_raw_events: false },
    sensing: { hidden_sensing: false },
    governance: { read_only_contract: true, telemetry_collection: false },
    next_smallest_truthful_gap: "stage7_terminal_connector_scope_contract",
  });

  assert.equal(status.kind, "francis.stage7.telemetry.status");
  assert.equal(status.active, false);
  assert.equal(status.active_source_total, 0);
  assert.equal(status.sources[0]?.id, "terminal");
  assert.equal(status.sources[0]?.active, false);
  assert.equal(status.sources[0]?.visible_indicator, true);
  assert.equal(status.sources[0]?.hidden_sensing, false);
  assert.equal(status.sources[0]?.scope.status, "not_granted");
  assert.deepEqual(status.sources[0]?.blocked_by, ["connector_not_configured", "operator_scope_not_granted"]);
  assert.equal(status.sources[0]?.latest_event?.event_id, "tel_terminal_123");
  assert.equal(status.sources[0]?.latest_event?.operation_id, "op_terminal");
  assert.equal(status.sources[0]?.routes.record, "/telemetry/terminal/events");
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
