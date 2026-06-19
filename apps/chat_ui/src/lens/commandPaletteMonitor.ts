export type CommandPaletteMonitorCheck = {
  id: string;
  passed: boolean;
  status: string;
  evidence: string;
};

export type ChatGptMcpProof = {
  status: string;
  proof_observed: boolean;
  mcp_connection_proof_observed: boolean;
  mcp_connection_proof_status: string;
  chatgpt_source_receipt_count: number;
  any_mcp_server_receipt_count: number;
  fresh_any_mcp_server_receipt_count: number;
  latest_any_mcp_server_receipt_id: string;
  latest_any_mcp_server_receipt_source: string;
  latest_any_mcp_server_receipt_client_origin: string;
  any_mcp_probe_receipt_count: number;
  fresh_any_mcp_probe_receipt_count: number;
  latest_any_mcp_probe_receipt_id: string;
  latest_any_mcp_probe_receipt_source: string;
  latest_any_mcp_probe_receipt_client_origin: string;
  mcp_server_receipt_count: number;
  mcp_probe_receipt_count: number;
  fresh_mcp_probe_receipt_count: number;
  mcp_connection_proof_receipt_count: number;
  fresh_mcp_connection_proof_receipt_count: number;
  usable_mcp_server_receipt_count: number;
  fresh_usable_mcp_server_receipt_count: number;
  latest_chatgpt_source_receipt_id: string;
  latest_mcp_server_receipt_id: string;
  latest_mcp_probe_receipt_id: string;
  latest_mcp_connection_proof_receipt_id: string;
  latest_mcp_connection_proof_tool: string;
  latest_fresh_usable_mcp_server_receipt_id: string;
  latest_mcp_transcript_unavailable: boolean;
  transcript_redacted_from_summary: boolean;
  required_actor: string;
  required_source: string;
  required_ingress_transport: string;
  required_mcp_gateway_tool: string;
  required_mcp_server_tool: string;
  required_mcp_probe_gateway_tool: string;
  required_mcp_probe_server_tool: string;
  next_operator_step: string;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
};

export type VoiceBridgeMonitor = {
  enabled: boolean;
  ok: boolean;
  selected_provider: string;
  active_provider_configured: boolean;
  selected_voice: string;
  voice_label: string;
  voice_identity_ok: boolean;
  generic_voice_label_observed: boolean;
  overlay_status: string;
  overlay_ready: boolean;
  overlay_voice_status: string;
  voice_status: string;
  voice_turn_status: string;
  wake_listening: boolean;
  wake_phrase: string;
  passive_listen_contract: string;
  continuous_voice_chat: boolean;
  continuous_voice_chat_mode: string;
  continuous_voice_chat_self_trigger_guard: string;
  microphone_gate_while_speaking: string;
  conversation_forwarding_while_speaking: boolean;
  interrupt_phrase: string;
  voice_input_ready: boolean;
  voice_input_status: string;
  voice_input_blocker: string;
  next_voice_input_step: string;
  api_permission_denied_observed: boolean;
  recent_receipt_count: number;
  denied_recent_receipt_count: number;
  latest_receipt_denied: boolean;
  latest_receipt_status: string;
  latest_receipt_chat_forward_status: string;
  latest_receipt_chat_forward_error: string;
  latest_receipt_id: string;
  latest_receipt_actor: string;
  latest_receipt_source: string;
  latest_receipt_client_origin: string;
  latest_receipt_ingress_transport: string;
  latest_receipt_mcp_gateway_tool: string;
  latest_receipt_mcp_server_tool: string;
  latest_receipt_counts_as_chatgpt_mcp_proof: boolean;
  latest_receipt_proof_rejection_reason: string;
  chatgpt_mcp_proof: ChatGptMcpProof;
};

export type ChatGptConnectorMonitor = {
  enabled: boolean;
  ok: boolean;
  status: string;
  connector_url_present: boolean;
  connector_url_host: string;
  connector_url_source: string;
  connector_shape_valid: boolean;
  connector_usable_for_chatgpt: boolean;
  expected_tool_present: boolean;
  local_listener_ready: boolean;
  mcp_launcher_alive: boolean;
  public_tunnel_process_alive: boolean;
  known_localtunnel: boolean;
  persistent_candidate: boolean;
  persistent_ingress_status: string;
  blockers: string[];
  next_operator_step: string;
};

export type PersistentIngressPlanMonitor = {
  enabled: boolean;
  ok: boolean;
  status: string;
  blockers: string[];
  recommended_provider_order: string[];
  next_operator_steps: string[];
  operator_handoff: PersistentIngressOperatorHandoff;
  providers: Record<string, boolean>;
  governance_safe: boolean;
};

export type PersistentIngressOperatorHandoff = {
  kind: string;
  safe_to_display: boolean;
  read_only_plan: boolean;
  installs_provider: boolean;
  opens_tunnel: boolean;
  writes_state: boolean;
  requires_operator_provider_account_or_hostname: boolean;
  preferred_provider: string;
  local_endpoint: string;
  stable_url_placeholder: string;
  install_commands: Record<string, string>;
  governed_handoff_commands: Record<string, string>;
};

export type CommandPaletteMonitorStatus = {
  ok: boolean;
  kind: string;
  status: string;
  checked_at: string;
  monitor_pid: number;
  monitor_process_alive: boolean;
  monitor_heartbeat_fresh: boolean;
  command_palette_url: string;
  anomaly_count: number;
  anomalies: CommandPaletteMonitorCheck[];
  checks: CommandPaletteMonitorCheck[];
  bridge: {
    ok: boolean;
    readback_ready: boolean;
    local_open_available: boolean;
    route: string;
    local_surface: string;
    command_total: number;
    availability: string;
    observed_blockers: string[];
  };
  voice_monitor: VoiceBridgeMonitor;
  chatgpt_connector_monitor: ChatGptConnectorMonitor;
  chatgpt_persistent_ingress_plan_monitor: PersistentIngressPlanMonitor;
  governance: Record<string, unknown>;
};

export class CommandPaletteMonitorStatusError extends Error {
  readonly status?: number;
  readonly url?: string;

  constructor(message: string, opts?: { status?: number; url?: string; cause?: unknown }) {
    super(message);
    this.name = "CommandPaletteMonitorStatusError";
    this.status = opts?.status;
    this.url = opts?.url;
    if (opts?.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = opts.cause;
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function safeString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function safeNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function safeStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => safeString(item)).filter(Boolean) : [];
}

function safeStringRecord(value: unknown): Record<string, string> {
  const raw = safeRecord(value);
  const parsed: Record<string, string> = {};
  for (const [key, item] of Object.entries(raw)) {
    parsed[key] = safeString(item);
  }
  return parsed;
}

function normalizeBaseUrl(value: string | undefined): string {
  return (value ?? "").trim().replace(/\/+$/, "");
}

function parseCheck(value: unknown): CommandPaletteMonitorCheck {
  const raw = safeRecord(value);
  return {
    id: safeString(raw["id"]),
    passed: safeBoolean(raw["passed"]),
    status: safeString(raw["status"]),
    evidence: safeString(raw["evidence"]),
  };
}

function parseChecks(value: unknown): CommandPaletteMonitorCheck[] {
  return Array.isArray(value) ? value.map(parseCheck).filter((item) => item.id) : [];
}

function parseMcpProof(value: unknown): ChatGptMcpProof {
  const raw = safeRecord(value);
  return {
    status: safeString(raw["status"]) || "not_checked",
    proof_observed: safeBoolean(raw["proof_observed"]),
    mcp_connection_proof_observed: safeBoolean(raw["mcp_connection_proof_observed"]),
    mcp_connection_proof_status: safeString(raw["mcp_connection_proof_status"]) || "missing",
    chatgpt_source_receipt_count: safeNumber(raw["chatgpt_source_receipt_count"]),
    any_mcp_server_receipt_count: safeNumber(raw["any_mcp_server_receipt_count"]),
    fresh_any_mcp_server_receipt_count: safeNumber(raw["fresh_any_mcp_server_receipt_count"]),
    latest_any_mcp_server_receipt_id: safeString(raw["latest_any_mcp_server_receipt_id"]),
    latest_any_mcp_server_receipt_source: safeString(raw["latest_any_mcp_server_receipt_source"]),
    latest_any_mcp_server_receipt_client_origin: safeString(raw["latest_any_mcp_server_receipt_client_origin"]),
    any_mcp_probe_receipt_count: safeNumber(raw["any_mcp_probe_receipt_count"]),
    fresh_any_mcp_probe_receipt_count: safeNumber(raw["fresh_any_mcp_probe_receipt_count"]),
    latest_any_mcp_probe_receipt_id: safeString(raw["latest_any_mcp_probe_receipt_id"]),
    latest_any_mcp_probe_receipt_source: safeString(raw["latest_any_mcp_probe_receipt_source"]),
    latest_any_mcp_probe_receipt_client_origin: safeString(raw["latest_any_mcp_probe_receipt_client_origin"]),
    mcp_server_receipt_count: safeNumber(raw["mcp_server_receipt_count"]),
    mcp_probe_receipt_count: safeNumber(raw["mcp_probe_receipt_count"]),
    fresh_mcp_probe_receipt_count: safeNumber(raw["fresh_mcp_probe_receipt_count"]),
    mcp_connection_proof_receipt_count: safeNumber(raw["mcp_connection_proof_receipt_count"]),
    fresh_mcp_connection_proof_receipt_count: safeNumber(raw["fresh_mcp_connection_proof_receipt_count"]),
    usable_mcp_server_receipt_count: safeNumber(raw["usable_mcp_server_receipt_count"]),
    fresh_usable_mcp_server_receipt_count: safeNumber(raw["fresh_usable_mcp_server_receipt_count"]),
    latest_chatgpt_source_receipt_id: safeString(raw["latest_chatgpt_source_receipt_id"]),
    latest_mcp_server_receipt_id: safeString(raw["latest_mcp_server_receipt_id"]),
    latest_mcp_probe_receipt_id: safeString(raw["latest_mcp_probe_receipt_id"]),
    latest_mcp_connection_proof_receipt_id: safeString(raw["latest_mcp_connection_proof_receipt_id"]),
    latest_mcp_connection_proof_tool: safeString(raw["latest_mcp_connection_proof_tool"]),
    latest_fresh_usable_mcp_server_receipt_id: safeString(raw["latest_fresh_usable_mcp_server_receipt_id"]),
    latest_mcp_transcript_unavailable: safeBoolean(raw["latest_mcp_transcript_unavailable"]),
    transcript_redacted_from_summary: safeBoolean(raw["transcript_redacted_from_summary"], true),
    required_actor: safeString(raw["required_actor"]) || "chatgpt.voice",
    required_source: safeString(raw["required_source"]) || "chatgpt.voice",
    required_ingress_transport: safeString(raw["required_ingress_transport"]) || "mcp_gateway_tool",
    required_mcp_gateway_tool: safeString(raw["required_mcp_gateway_tool"]) || "francis.chatgpt_voice.ingress",
    required_mcp_server_tool: safeString(raw["required_mcp_server_tool"]) || "francis_chatgpt_voice_ingress",
    required_mcp_probe_gateway_tool:
      safeString(raw["required_mcp_probe_gateway_tool"]) || "francis.chatgpt_voice.mcp_probe",
    required_mcp_probe_server_tool:
      safeString(raw["required_mcp_probe_server_tool"]) || "francis_chatgpt_voice_mcp_probe",
    next_operator_step: safeString(raw["next_operator_step"]),
    grants_execution_authority: safeBoolean(raw["grants_execution_authority"]),
    grants_mutation_authority: safeBoolean(raw["grants_mutation_authority"]),
  };
}

function parseVoiceMonitor(value: unknown): VoiceBridgeMonitor {
  const raw = safeRecord(value);
  return {
    enabled: safeBoolean(raw["enabled"]),
    ok: safeBoolean(raw["ok"]),
    selected_provider: safeString(raw["selected_provider"]),
    active_provider_configured: safeBoolean(raw["active_provider_configured"]),
    selected_voice: safeString(raw["selected_voice"]),
    voice_label: safeString(raw["voice_label"]),
    voice_identity_ok: safeBoolean(raw["voice_identity_ok"]),
    generic_voice_label_observed: safeBoolean(raw["generic_voice_label_observed"]),
    overlay_status: safeString(raw["overlay_status"]),
    overlay_ready: safeBoolean(raw["overlay_ready"]),
    overlay_voice_status: safeString(raw["overlay_voice_status"]),
    voice_status: safeString(raw["voice_status"]),
    voice_turn_status: safeString(raw["voice_turn_status"]),
    wake_listening: safeBoolean(raw["wake_listening"]),
    wake_phrase: safeString(raw["wake_phrase"]),
    passive_listen_contract: safeString(raw["passive_listen_contract"]),
    continuous_voice_chat: safeBoolean(raw["continuous_voice_chat"]),
    continuous_voice_chat_mode: safeString(raw["continuous_voice_chat_mode"]),
    continuous_voice_chat_self_trigger_guard: safeString(raw["continuous_voice_chat_self_trigger_guard"]),
    microphone_gate_while_speaking: safeString(raw["microphone_gate_while_speaking"]),
    conversation_forwarding_while_speaking: safeBoolean(raw["conversation_forwarding_while_speaking"]),
    interrupt_phrase: safeString(raw["interrupt_phrase"]),
    voice_input_ready: safeBoolean(raw["voice_input_ready"]),
    voice_input_status: safeString(raw["voice_input_status"]),
    voice_input_blocker: safeString(raw["voice_input_blocker"]),
    next_voice_input_step: safeString(raw["next_voice_input_step"]),
    api_permission_denied_observed: safeBoolean(raw["api_permission_denied_observed"]),
    recent_receipt_count: safeNumber(raw["recent_receipt_count"]),
    denied_recent_receipt_count: safeNumber(raw["denied_recent_receipt_count"]),
    latest_receipt_denied: safeBoolean(raw["latest_receipt_denied"]),
    latest_receipt_status: safeString(raw["latest_receipt_status"]),
    latest_receipt_chat_forward_status: safeString(raw["latest_receipt_chat_forward_status"]),
    latest_receipt_chat_forward_error: safeString(raw["latest_receipt_chat_forward_error"]),
    latest_receipt_id: safeString(raw["latest_receipt_id"]),
    latest_receipt_actor: safeString(raw["latest_receipt_actor"]),
    latest_receipt_source: safeString(raw["latest_receipt_source"]),
    latest_receipt_client_origin: safeString(raw["latest_receipt_client_origin"]),
    latest_receipt_ingress_transport: safeString(raw["latest_receipt_ingress_transport"]),
    latest_receipt_mcp_gateway_tool: safeString(raw["latest_receipt_mcp_gateway_tool"]),
    latest_receipt_mcp_server_tool: safeString(raw["latest_receipt_mcp_server_tool"]),
    latest_receipt_counts_as_chatgpt_mcp_proof: safeBoolean(raw["latest_receipt_counts_as_chatgpt_mcp_proof"]),
    latest_receipt_proof_rejection_reason: safeString(raw["latest_receipt_proof_rejection_reason"]),
    chatgpt_mcp_proof: parseMcpProof(raw["chatgpt_mcp_proof"]),
  };
}

function parseConnectorMonitor(value: unknown): ChatGptConnectorMonitor {
  const raw = safeRecord(value);
  return {
    enabled: safeBoolean(raw["enabled"]),
    ok: safeBoolean(raw["ok"]),
    status: safeString(raw["status"]),
    connector_url_present: safeBoolean(raw["connector_url_present"]),
    connector_url_host: safeString(raw["connector_url_host"]),
    connector_url_source: safeString(raw["connector_url_source"]),
    connector_shape_valid: safeBoolean(raw["connector_shape_valid"]),
    connector_usable_for_chatgpt: safeBoolean(raw["connector_usable_for_chatgpt"]),
    expected_tool_present: safeBoolean(raw["expected_tool_present"]),
    local_listener_ready: safeBoolean(raw["local_listener_ready"]),
    mcp_launcher_alive: safeBoolean(raw["mcp_launcher_alive"]),
    public_tunnel_process_alive: safeBoolean(raw["public_tunnel_process_alive"]),
    known_localtunnel: safeBoolean(raw["known_localtunnel"]),
    persistent_candidate: safeBoolean(raw["persistent_candidate"]),
    persistent_ingress_status: safeString(raw["persistent_ingress_status"]),
    blockers: safeStringList(raw["blockers"]),
    next_operator_step: safeString(raw["next_operator_step"]),
  };
}

function parsePersistentIngressPlan(value: unknown): PersistentIngressPlanMonitor {
  const raw = safeRecord(value);
  const providers = safeRecord(raw["providers"]);
  const handoff = safeRecord(raw["operator_handoff"]);
  const parsedProviders: Record<string, boolean> = {};
  for (const [key, ready] of Object.entries(providers)) {
    parsedProviders[key] = safeBoolean(ready);
  }
  return {
    enabled: safeBoolean(raw["enabled"]),
    ok: safeBoolean(raw["ok"]),
    status: safeString(raw["status"]),
    blockers: safeStringList(raw["blockers"]),
    recommended_provider_order: safeStringList(raw["recommended_provider_order"]),
    next_operator_steps: safeStringList(raw["next_operator_steps"]),
    operator_handoff: {
      kind: safeString(handoff["kind"]),
      safe_to_display: safeBoolean(handoff["safe_to_display"]),
      read_only_plan: safeBoolean(handoff["read_only_plan"]),
      installs_provider: safeBoolean(handoff["installs_provider"]),
      opens_tunnel: safeBoolean(handoff["opens_tunnel"]),
      writes_state: safeBoolean(handoff["writes_state"]),
      requires_operator_provider_account_or_hostname: safeBoolean(
        handoff["requires_operator_provider_account_or_hostname"],
      ),
      preferred_provider: safeString(handoff["preferred_provider"]),
      local_endpoint: safeString(handoff["local_endpoint"]),
      stable_url_placeholder: safeString(handoff["stable_url_placeholder"]),
      install_commands: safeStringRecord(handoff["install_commands"]),
      governed_handoff_commands: safeStringRecord(handoff["governed_handoff_commands"]),
    },
    providers: parsedProviders,
    governance_safe: safeBoolean(raw["governance_safe"]),
  };
}

export function parseCommandPaletteMonitorStatus(value: unknown): CommandPaletteMonitorStatus {
  const raw = safeRecord(value);
  const bridge = safeRecord(raw["bridge"]);
  return {
    ok: safeBoolean(raw["ok"]),
    kind: safeString(raw["kind"]),
    status: safeString(raw["status"]) || "unknown",
    checked_at: safeString(raw["checked_at"]),
    monitor_pid: safeNumber(raw["monitor_pid"]),
    monitor_process_alive: safeBoolean(raw["monitor_process_alive"]),
    monitor_heartbeat_fresh: safeBoolean(raw["monitor_heartbeat_fresh"]),
    command_palette_url: safeString(raw["command_palette_url"]),
    anomaly_count: safeNumber(raw["anomaly_count"]),
    anomalies: parseChecks(raw["anomalies"]),
    checks: parseChecks(raw["checks"]),
    bridge: {
      ok: safeBoolean(bridge["ok"]),
      readback_ready: safeBoolean(bridge["readback_ready"]),
      local_open_available: safeBoolean(bridge["local_open_available"]),
      route: safeString(bridge["route"]),
      local_surface: safeString(bridge["local_surface"]),
      command_total: safeNumber(bridge["command_total"]),
      availability: safeString(bridge["availability"]),
      observed_blockers: safeStringList(bridge["observed_blockers"]),
    },
    voice_monitor: parseVoiceMonitor(raw["voice_monitor"]),
    chatgpt_connector_monitor: parseConnectorMonitor(raw["chatgpt_connector_monitor"]),
    chatgpt_persistent_ingress_plan_monitor: parsePersistentIngressPlan(
      raw["chatgpt_persistent_ingress_plan_monitor"],
    ),
    governance: safeRecord(raw["governance"]),
  };
}

export async function fetchCommandPaletteMonitorStatus(opts?: {
  baseUrl?: string;
  signal?: AbortSignal;
}): Promise<CommandPaletteMonitorStatus> {
  const baseUrl = normalizeBaseUrl(opts?.baseUrl);
  const url = `${baseUrl}/lens/command-palette/monitor`;
  const res = await fetch(url, { method: "GET", signal: opts?.signal });
  const text = await res.text();

  let json: unknown = {};
  if (text.trim()) {
    try {
      json = JSON.parse(text);
    } catch (err) {
      throw new CommandPaletteMonitorStatusError("Command-palette monitor response was not valid JSON.", {
        status: res.status,
        url,
        cause: err,
      });
    }
  }

  if (!res.ok) {
    throw new CommandPaletteMonitorStatusError(`Command-palette monitor request failed with HTTP ${res.status}.`, {
      status: res.status,
      url,
    });
  }

  return parseCommandPaletteMonitorStatus(json);
}
