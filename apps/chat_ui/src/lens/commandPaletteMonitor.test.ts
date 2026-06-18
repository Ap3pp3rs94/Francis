import assert from "node:assert/strict";
import test from "node:test";

import { fetchCommandPaletteMonitorStatus, parseCommandPaletteMonitorStatus } from "./commandPaletteMonitor.ts";

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

test("parseCommandPaletteMonitorStatus preserves latest receipt origin without transcript text", () => {
  const status = parseCommandPaletteMonitorStatus({
    ok: true,
    kind: "francis.lens.command_palette.monitor_readback",
    status: "healthy",
    monitor_process_alive: true,
    anomaly_count: 0,
    bridge: {
      ok: true,
      readback_ready: true,
      local_open_available: true,
      route: "/?francis_lens=command_palette",
      local_surface: "chat_ui.command_palette",
      command_total: "2",
    },
    voice_monitor: {
      enabled: true,
      ok: true,
      selected_provider: "ElevenLabs",
      selected_voice: "Emma",
      voice_label: "Emma",
      voice_identity_ok: true,
      overlay_ready: true,
      overlay_voice_status: "listening",
      voice_status: "listening",
      recent_receipt_count: "1",
      latest_receipt_id: "chatgpt-voice-recorded-ui",
      latest_receipt_actor: "chat_ui.voice",
      latest_receipt_source: "chat_ui.voice",
      latest_receipt_client_origin: "francis_chat_ui_browser_voice",
      latest_receipt_ingress_transport: "http_api",
      latest_receipt_counts_as_chatgpt_mcp_proof: false,
      latest_receipt_proof_rejection_reason: "latest_receipt_not_chatgpt_voice_origin",
      transcript: "this transcript must not be parsed",
      chatgpt_mcp_proof: {
        status: "awaiting_chatgpt_mcp_tool_call",
        proof_observed: false,
        chatgpt_source_receipt_count: 0,
        mcp_server_receipt_count: 0,
        latest_fresh_usable_mcp_server_receipt_id: "",
        next_operator_step: "trigger_chatgpt_voice_app_turn_and_confirm_mcp_tool_receipt",
        transcript: "this proof transcript must not be parsed",
      },
    },
    chatgpt_connector_monitor: {
      enabled: true,
      ok: true,
      status: "ready_for_chatgpt_connector",
      connector_url_host: "francis-voice-178175.loca.lt",
      connector_url_source: "localtunnel",
      connector_usable_for_chatgpt: true,
      known_localtunnel: true,
      persistent_ingress_status: "localtunnel_fallback_replace_needed",
      blockers: ["localtunnel_url_is_not_persistent_ingress"],
    },
    chatgpt_persistent_ingress_plan_monitor: {
      enabled: true,
      ok: true,
      status: "localtunnel_fallback_replace_needed",
      recommended_provider_order: ["cloudflared_named_tunnel"],
      next_operator_steps: ["choose_or_install_a_persistent_https_ingress_provider"],
      governance_safe: true,
    },
    governance: { execution_authority: false, captures_audio: false },
  });

  assert.equal(status.status, "healthy");
  assert.equal(status.monitor_process_alive, true);
  assert.equal(status.bridge.command_total, 2);
  assert.equal(status.voice_monitor.selected_voice, "Emma");
  assert.equal(status.voice_monitor.latest_receipt_actor, "chat_ui.voice");
  assert.equal(status.voice_monitor.latest_receipt_ingress_transport, "http_api");
  assert.equal(status.voice_monitor.latest_receipt_counts_as_chatgpt_mcp_proof, false);
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.status, "awaiting_chatgpt_mcp_tool_call");
  assert.equal(status.chatgpt_connector_monitor.known_localtunnel, true);
  assert.deepEqual(status.chatgpt_connector_monitor.blockers, ["localtunnel_url_is_not_persistent_ingress"]);
  assert.equal(status.chatgpt_persistent_ingress_plan_monitor.governance_safe, true);
  assert.equal(JSON.stringify(status).includes("this transcript must not be parsed"), false);
});

test("fetchCommandPaletteMonitorStatus calls the Lens monitor readback route", async () => {
  const requests: Array<{ path: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url, "http://127.0.0.1:5173");
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: false,
      kind: "francis.lens.command_palette.monitor_readback",
      status: "missing",
      voice_monitor: { chatgpt_mcp_proof: { proof_observed: false } },
    });
  });

  try {
    const status = await fetchCommandPaletteMonitorStatus({ baseUrl: "http://127.0.0.1:8000/" });
    assert.equal(status.status, "missing");
    assert.equal(status.voice_monitor.chatgpt_mcp_proof.proof_observed, false);
    assert.deepEqual(requests, [{ path: "/lens/command-palette/monitor", method: "GET" }]);
  } finally {
    restore();
  }
});
