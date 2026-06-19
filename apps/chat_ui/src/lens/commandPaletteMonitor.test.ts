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
      overlay_status: "visible",
      overlay_ready: true,
      overlay_voice_status: "listening",
      voice_status: "listening",
      wake_listening: true,
      wake_phrase: "hey francis",
      passive_listen_contract: "passive_transcript_awareness_only_until_wake_phrase",
      continuous_voice_chat: true,
      continuous_voice_chat_mode: "enabled_no_wake_phrase_required",
      continuous_voice_chat_self_trigger_guard: "suppress_all_except_francis_stop_while_owned_speech_process_active",
      microphone_gate_while_speaking: "francis_stop_only",
      conversation_forwarding_while_speaking: false,
      interrupt_phrase: "francis stop",
      voice_input_ready: false,
      voice_input_status: "waiting_for_audio_signal",
      voice_input_blocker: "audio_signal_not_confirmed",
      next_voice_input_step: "say_hey_francis_to_confirm_default_microphone_signal",
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
        status: "fresh_mcp_connection_proof_observed",
        proof_observed: false,
        mcp_connection_proof_observed: true,
        mcp_connection_proof_status: "fresh_observed",
        chatgpt_source_receipt_count: 0,
        any_mcp_server_receipt_count: "1",
        fresh_any_mcp_server_receipt_count: "1",
        latest_any_mcp_server_receipt_id: "chatgpt-voice-recorded-selftest",
        latest_any_mcp_server_receipt_source: "local.mcp.selftest",
        latest_any_mcp_server_receipt_client_origin: "codex_live_mcp_selftest",
        any_mcp_probe_receipt_count: "1",
        fresh_any_mcp_probe_receipt_count: "1",
        latest_any_mcp_probe_receipt_id: "chatgpt-voice-recorded-probe",
        latest_any_mcp_probe_receipt_source: "chatgpt.voice",
        latest_any_mcp_probe_receipt_client_origin: "chatgpt_app_voice",
        mcp_server_receipt_count: 0,
        mcp_probe_receipt_count: "1",
        fresh_mcp_probe_receipt_count: "1",
        mcp_connection_proof_receipt_count: "1",
        fresh_mcp_connection_proof_receipt_count: "1",
        latest_mcp_probe_receipt_id: "chatgpt-voice-recorded-probe",
        latest_mcp_connection_proof_receipt_id: "chatgpt-voice-recorded-probe",
        latest_mcp_connection_proof_tool: "francis_chatgpt_voice_mcp_probe",
        latest_fresh_usable_mcp_server_receipt_id: "",
        next_operator_step: "call_francis_chatgpt_voice_mcp_probe_from_chatgpt_connector",
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
      operator_handoff: {
        kind: "francis.chatgpt_voice.persistent_ingress_operator_handoff",
        safe_to_display: true,
        read_only_plan: true,
        installs_provider: false,
        opens_tunnel: false,
        writes_state: false,
        requires_operator_provider_account_or_hostname: true,
        preferred_provider: "cloudflared_named_tunnel",
        local_endpoint: "http://127.0.0.1:8787/mcp",
        stable_url_placeholder: "https://YOUR-STABLE-HOST/mcp",
        install_commands: {
          cloudflared_winget:
            "winget install --id Cloudflare.cloudflared --exact --accept-source-agreements --accept-package-agreements",
        },
        governed_handoff_commands: {
          record_url:
            '.\\scripts\\chatgpt-voice-connector.ps1 -Mode RecordUrl -ConnectorUrl "https://YOUR-STABLE-HOST/mcp" -Json',
          start_persistent_mcp:
            '.\\scripts\\chatgpt-voice-connector.ps1 -Mode StartPersistent -ConnectorUrl "https://YOUR-STABLE-HOST/mcp" -VerifyConnector -Json',
          start_cloudflared_named:
            '.\\scripts\\chatgpt-voice-connector.ps1 -Mode StartCloudflaredNamed -CloudflaredTunnelName "francis" -CloudflaredHostname "YOUR-STABLE-HOST" -ExposePublicTunnel -VerifyConnector -Json',
        },
      },
      providers: {
        cloudflared_named_tunnel_available: true,
        cloudflared_named_tunnel_path: "C:\\Program Files (x86)\\cloudflared\\cloudflared.exe",
        cloudflared_named_tunnel_origin_cert_present: false,
        cloudflared_named_tunnel_origin_cert_content_read: false,
        cloudflared_named_tunnel_login_required: true,
        cloudflared_named_tunnel_requested: true,
        cloudflared_named_tunnel_requested_name: "francis",
        cloudflared_named_tunnel_requested_hostname: "francis.example.test",
        cloudflared_named_tunnel_exists: false,
        cloudflared_named_tunnel_preflight_checked: false,
        cloudflared_named_tunnel_preflight_exists: false,
        cloudflared_named_tunnel_preflight_output_discarded: true,
        cloudflared_named_tunnel_operator_provider_setup_commands: [
          "cloudflared tunnel create francis",
          "cloudflared tunnel route dns francis francis.example.test",
        ],
        cloudflared_named_tunnel_next_operator_step: "run_cloudflared_tunnel_login",
        ngrok_reserved_domain_available: false,
        caddy_reverse_proxy_available: false,
        ssh_reverse_tunnel_available: true,
        winget_available: true,
      },
      governance_safe: true,
    },
    governance: { execution_authority: false, captures_audio: false },
  });

  assert.equal(status.status, "healthy");
  assert.equal(status.monitor_process_alive, true);
  assert.equal(status.bridge.command_total, 2);
  assert.equal(status.voice_monitor.selected_voice, "Emma");
  assert.equal(status.voice_monitor.overlay_status, "visible");
  assert.equal(status.voice_monitor.wake_listening, true);
  assert.equal(status.voice_monitor.wake_phrase, "hey francis");
  assert.equal(status.voice_monitor.passive_listen_contract, "passive_transcript_awareness_only_until_wake_phrase");
  assert.equal(status.voice_monitor.microphone_gate_while_speaking, "francis_stop_only");
  assert.equal(status.voice_monitor.conversation_forwarding_while_speaking, false);
  assert.equal(status.voice_monitor.interrupt_phrase, "francis stop");
  assert.equal(status.voice_monitor.voice_input_status, "waiting_for_audio_signal");
  assert.equal(status.voice_monitor.voice_input_blocker, "audio_signal_not_confirmed");
  assert.equal(status.voice_monitor.latest_receipt_actor, "chat_ui.voice");
  assert.equal(status.voice_monitor.latest_receipt_ingress_transport, "http_api");
  assert.equal(status.voice_monitor.latest_receipt_counts_as_chatgpt_mcp_proof, false);
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.status, "fresh_mcp_connection_proof_observed");
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.proof_observed, false);
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.mcp_connection_proof_observed, true);
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.mcp_connection_proof_status, "fresh_observed");
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.any_mcp_server_receipt_count, 1);
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.fresh_any_mcp_server_receipt_count, 1);
  assert.equal(
    status.voice_monitor.chatgpt_mcp_proof.latest_any_mcp_server_receipt_id,
    "chatgpt-voice-recorded-selftest",
  );
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.latest_any_mcp_server_receipt_source, "local.mcp.selftest");
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.mcp_probe_receipt_count, 1);
  assert.equal(status.voice_monitor.chatgpt_mcp_proof.fresh_mcp_probe_receipt_count, 1);
  assert.equal(
    status.voice_monitor.chatgpt_mcp_proof.latest_mcp_connection_proof_receipt_id,
    "chatgpt-voice-recorded-probe",
  );
  assert.equal(
    status.voice_monitor.chatgpt_mcp_proof.latest_mcp_connection_proof_tool,
    "francis_chatgpt_voice_mcp_probe",
  );
  assert.equal(status.chatgpt_connector_monitor.known_localtunnel, true);
  assert.deepEqual(status.chatgpt_connector_monitor.blockers, ["localtunnel_url_is_not_persistent_ingress"]);
  assert.equal(status.chatgpt_persistent_ingress_plan_monitor.governance_safe, true);
  assert.equal(
    status.chatgpt_persistent_ingress_plan_monitor.operator_handoff.preferred_provider,
    "cloudflared_named_tunnel",
  );
  assert.equal(
    status.chatgpt_persistent_ingress_plan_monitor.operator_handoff.install_commands.cloudflared_winget.endsWith(
      "--accept-source-agreements --accept-package-agreements",
    ),
    true,
  );
  assert.equal(
    status.chatgpt_persistent_ingress_plan_monitor.operator_handoff.governed_handoff_commands.record_url.includes(
      "RecordUrl",
    ),
    true,
  );
  assert.equal(
    status.chatgpt_persistent_ingress_plan_monitor.operator_handoff.governed_handoff_commands.start_cloudflared_named.includes(
      "StartCloudflaredNamed",
    ),
    true,
  );
  assert.equal(status.chatgpt_persistent_ingress_plan_monitor.providers.cloudflared_named_tunnel_available, true);
  assert.equal(
    status.chatgpt_persistent_ingress_plan_monitor.providers.cloudflared_named_tunnel_login_required,
    true,
  );
  assert.equal(
    status.chatgpt_persistent_ingress_plan_monitor.providers.cloudflared_named_tunnel_next_operator_step,
    "run_cloudflared_tunnel_login",
  );
  assert.deepEqual(
    status.chatgpt_persistent_ingress_plan_monitor.providers.cloudflared_named_tunnel_operator_provider_setup_commands,
    ["cloudflared tunnel create francis", "cloudflared tunnel route dns francis francis.example.test"],
  );
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
