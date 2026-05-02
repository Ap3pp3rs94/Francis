export type LensBadge = {
  label: string;
  value: string | number | boolean;
  severity?: string;
};

export type LensModeOption = {
  id?: string;
  label?: string;
  summary?: string;
  implementation_status?: string;
  active?: boolean;
};

export type LensHudRuntime = {
  status?: string;
  claim?: string;
  surface?: string;
  route?: string;
  window_host?: string;
  resident_overlay?: boolean;
  always_on_top?: boolean;
  global_hotkey?: boolean;
  tray_presence?: boolean;
  os_level?: boolean;
  blockers: string[];
  message?: string;
  governance: Record<string, unknown>;
};

export type LensHud = {
  status?: string;
  headline?: string;
  primary_plane?: string;
  primary_plane_label?: string;
  badges: LensBadge[];
  readback_ready?: boolean;
  runtime_status?: string;
  resident_overlay?: boolean;
  runtime: LensHudRuntime;
  route?: string;
};

export type LensPaletteCommand = {
  id?: string;
  label?: string;
  description?: string;
  group?: string;
  keywords?: string;
  status?: string;
  action?: string;
  route?: string;
  method?: string;
  surface?: string;
  mutates?: boolean;
  requires_confirmation?: boolean;
  write_guard?: string;
  target_mode?: string;
  receipt_kind?: string;
  attention_count?: number;
  execution_authority?: boolean;
  approval_decision_authority?: boolean;
  memory_write?: boolean;
};

export type LensCommandPalette = {
  status?: string;
  availability?: string;
  summon_anywhere?: boolean;
  message?: string;
  route?: string;
  local_surface?: string;
  command_total: number;
  groups: Record<string, number>;
  commands: LensPaletteCommand[];
  governance: Record<string, unknown>;
};

export type LensModeSelector = {
  status?: string;
  active_mode?: string;
  available_modes: LensModeOption[];
  mutation_route?: string;
  write_guard?: string;
};

export type LensApprovalView = {
  status?: string;
  pending_count: number;
  items: Array<Record<string, unknown>>;
  route?: string;
  decision_route?: string;
  error?: string;
};

export type LensIncidentView = {
  status?: string;
  observer_headline?: string;
  observer_decision?: string;
  observer_counts: Record<string, number>;
  reactor_review_queue_total: number;
  route?: string;
  reactor_route?: string;
  error?: string;
};

export type LensMissionFeed = {
  headline?: string;
  counts: Record<string, number>;
  memory_receipt_count: number;
  route?: string;
  mission_route?: string;
};

export type LensPilotIndicator = {
  active: boolean;
  status?: string;
  mode?: string;
  message?: string;
  route?: string;
};

export type LensActivationDenialReceipt = {
  kind?: string;
  receipt_id?: string;
  id?: string;
  status?: string;
  route?: string;
  method?: string;
  source_kind?: string;
  source_route?: string;
  approval_id?: string;
  actor?: string;
  reason?: string;
  created_ts?: number;
  blockers: string[];
  approval: Record<string, unknown>;
  permission: Record<string, unknown>;
  execution: Record<string, unknown>;
  denial: Record<string, unknown>;
  governance: Record<string, unknown>;
};

export type LensActivationDenialReceipts = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  execute_route?: string;
  limit: number;
  approval_id?: string;
  filter_status?: string;
  total: number;
  latest?: LensActivationDenialReceipt;
  items: LensActivationDenialReceipt[];
  governance: Record<string, unknown>;
};

export type LensRuntimeLoopReadiness = {
  ok: boolean;
  kind?: string;
  status?: string;
  audit_status?: string;
  route?: string;
  runtime_plan_route?: string;
  runtime_loop_route?: string;
  execute_route?: string;
  denials_route?: string;
  host_route?: string;
  approval_id?: string;
  actor?: string;
  limit: number;
  ready: boolean;
  loop_ready: boolean;
  execution_ready: boolean;
  resident_runtime_loop: boolean;
  resident_runtime_ready: boolean;
  resident_claim_allowed: boolean;
  runtime_plan_available: boolean;
  loop_contract_readback_ready: boolean;
  execution_denial_boundary_observed: boolean;
  denial_receipt_readback_ready: boolean;
  receipt_count: number;
  latest_receipt_id?: string;
  requirements_total: number;
  requirements_ready_total: number;
  requirements_blocked_total: number;
  requirements: Array<Record<string, unknown>>;
  blocked_requirements: string[];
  blockers: string[];
  source_readbacks: Record<string, string>;
  evidence: string[];
  governance: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  message?: string;
};

export type LensResidentHost = {
  route?: string;
  status?: string;
  contract_status?: string;
  availability?: string;
  activation_denial_receipts_route?: string;
  activation_denial_receipts: LensActivationDenialReceipts;
  runtime_loop_readiness_route?: string;
  runtime_loop_readiness: LensRuntimeLoopReadiness;
};

export type LensStage6Criterion = {
  id?: string;
  status?: string;
  evidence: string[];
  command_count?: number;
  pending_count?: number;
  receipt_count?: number;
  latest_receipt_id?: string;
  observer_active_count?: number;
  reactor_review_queue_total?: number;
  mission_counts?: Record<string, number>;
  reactor_readback_surfaces?: Record<string, string>;
  ready?: boolean;
  resident_overlay?: boolean;
  resident_claim_allowed?: boolean;
  summon_anywhere?: boolean;
  global_hotkey?: string;
  tray_presence?: boolean;
  presence_name?: string;
  overlay_window?: boolean;
  overlay_name?: string;
  execution_authority?: boolean;
  approval_decision_authority?: boolean;
  local_process_launch_authority?: boolean;
  service_control_authority?: boolean;
  window_management_authority?: boolean;
  hotkey_registration_authority?: boolean;
  tray_registration_authority?: boolean;
  tray_icon_authority?: boolean;
  notification_authority?: boolean;
  overlay_control_authority?: boolean;
  summon_authority?: boolean;
  capture_authority?: boolean;
  memory_write?: boolean;
  blockers: string[];
};

export type LensStage6ClosureCriterion = {
  id?: string;
  label?: string;
  ready?: boolean;
  status?: string;
  evidence: string[];
  blockers: string[];
  basis?: string;
};

export type LensStage6ClosureReadback = {
  kind?: string;
  status?: string;
  ready_to_close: boolean;
  criteria_total: number;
  ready_total: number;
  blocked_total: number;
  ready_criteria: string[];
  blocked_criteria: string[];
  next_smallest_truthful_gap?: string;
  criteria: LensStage6ClosureCriterion[];
  governance: Record<string, unknown>;
};

export type LensStage6Readiness = {
  stage?: string;
  claim?: string;
  closure_readback: LensStage6ClosureReadback;
  criteria: LensStage6Criterion[];
};

export type LensGovernance = {
  gate?: string;
  execution_authority?: boolean;
  approval_decision_authority?: boolean;
  memory_write?: boolean;
  overlay_control_authority?: boolean;
  capture_authority?: boolean;
  new_sensing_authority?: boolean;
};

export type LensStatus = {
  ok: boolean;
  kind?: string;
  subsystem?: string;
  status?: string;
  generated_at?: number;
  limit?: number;
  read_only?: boolean;
  mode: Record<string, unknown>;
  available_modes: LensModeOption[];
  scope: Record<string, unknown>;
  hud: LensHud;
  resident_host: LensResidentHost;
  command_palette: LensCommandPalette;
  mode_selector: LensModeSelector;
  approvals_view: LensApprovalView;
  incident_view: LensIncidentView;
  mission_feed: LensMissionFeed;
  pilot_indicator: LensPilotIndicator;
  receipts: Record<string, unknown>;
  runtime_loop_readiness: LensRuntimeLoopReadiness;
  stage6_readiness: LensStage6Readiness;
  governance: LensGovernance;
  error?: string;
};

export class LensApiError extends Error {
  readonly status?: number;
  readonly url?: string;

  constructor(message: string, opts?: { status?: number; url?: string; cause?: unknown }) {
    super(message);
    this.name = "LensApiError";
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

function safeString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function safeNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value.trim());
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function safeOptionalNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value.trim());
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function safeBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function safeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => safeString(item).trim()).filter(Boolean);
}

function safeRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function parseNumberMap(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {};
  const out: Record<string, number> = {};
  for (const [key, count] of Object.entries(value)) {
    const safeKey = key.trim();
    if (!safeKey) continue;
    out[safeKey] = safeNumber(count, 0);
  }
  return out;
}

function parseStringMap(value: unknown): Record<string, string> {
  if (!isRecord(value)) return {};
  const out: Record<string, string> = {};
  for (const [key, item] of Object.entries(value)) {
    const safeKey = key.trim();
    const safeValue = safeString(item).trim();
    if (!safeKey || !safeValue) continue;
    out[safeKey] = safeValue;
  }
  return out;
}

function parseModeOption(value: unknown): LensModeOption | null {
  if (!isRecord(value)) return null;
  const id = safeString(value.id).trim();
  const label = safeString(value.label).trim();
  if (!id && !label) return null;
  return {
    id: id || undefined,
    label: label || undefined,
    summary: safeString(value.summary).trim() || undefined,
    implementation_status: safeString(value.implementation_status).trim() || undefined,
    active: safeBoolean(value.active, false),
  };
}

function parseModeOptions(value: unknown): LensModeOption[] {
  if (!Array.isArray(value)) return [];
  return value.map(parseModeOption).filter((item): item is LensModeOption => item !== null);
}

function parseBadge(value: unknown): LensBadge | null {
  if (!isRecord(value)) return null;
  const label = safeString(value.label).trim();
  if (!label) return null;
  const rawValue = value.value;
  let parsedValue: LensBadge["value"] = safeString(rawValue).trim();
  if (typeof rawValue === "number" || typeof rawValue === "boolean") {
    parsedValue = rawValue;
  } else if (typeof rawValue === "string") {
    const trimmed = rawValue.trim();
    const parsedNumber = Number(trimmed);
    parsedValue = trimmed !== "" && Number.isFinite(parsedNumber) ? parsedNumber : trimmed;
  }
  return {
    label,
    value: parsedValue,
    severity: safeString(value.severity).trim() || undefined,
  };
}

function parseBadges(value: unknown): LensBadge[] {
  if (!Array.isArray(value)) return [];
  return value.map(parseBadge).filter((item): item is LensBadge => item !== null);
}

function parseHudRuntime(value: unknown): LensHudRuntime {
  const raw = safeRecord(value);
  return {
    status: safeString(raw.status).trim(),
    claim: safeString(raw.claim).trim(),
    surface: safeString(raw.surface).trim(),
    route: safeString(raw.route).trim(),
    window_host: safeString(raw.window_host).trim(),
    resident_overlay: safeBoolean(raw.resident_overlay, false),
    always_on_top: safeBoolean(raw.always_on_top, false),
    global_hotkey: safeBoolean(raw.global_hotkey, false),
    tray_presence: safeBoolean(raw.tray_presence, false),
    os_level: safeBoolean(raw.os_level, false),
    blockers: safeStringList(raw.blockers),
    message: safeString(raw.message).trim(),
    governance: safeRecord(raw.governance),
  };
}

function parseHud(value: unknown): LensHud {
  const raw = safeRecord(value);
  return {
    status: safeString(raw.status).trim(),
    headline: safeString(raw.headline).trim(),
    primary_plane: safeString(raw.primary_plane).trim(),
    primary_plane_label: safeString(raw.primary_plane_label).trim(),
    badges: parseBadges(raw.badges),
    readback_ready: safeBoolean(raw.readback_ready, false),
    runtime_status: safeString(raw.runtime_status).trim(),
    resident_overlay: safeBoolean(raw.resident_overlay, false),
    runtime: parseHudRuntime(raw.runtime),
    route: safeString(raw.route).trim(),
  };
}

function parseCommandPalette(value: unknown): LensCommandPalette {
  const raw = safeRecord(value);
  return {
    status: safeString(raw.status).trim(),
    availability: safeString(raw.availability).trim(),
    summon_anywhere: safeBoolean(raw.summon_anywhere, false),
    message: safeString(raw.message).trim(),
    route: safeString(raw.route).trim(),
    local_surface: safeString(raw.local_surface).trim(),
    command_total: safeNumber(raw.command_total, 0),
    groups: parseNumberMap(raw.groups),
    commands: parsePaletteCommands(raw.commands),
    governance: safeRecord(raw.governance),
  };
}

function parsePaletteCommand(value: unknown): LensPaletteCommand | null {
  if (!isRecord(value)) return null;
  const id = safeString(value.id).trim();
  const label = safeString(value.label).trim();
  if (!id || !label) return null;
  return {
    id,
    label,
    description: safeString(value.description).trim() || undefined,
    group: safeString(value.group).trim() || undefined,
    keywords: safeString(value.keywords).trim() || undefined,
    status: safeString(value.status).trim() || undefined,
    action: safeString(value.action).trim() || undefined,
    route: safeString(value.route).trim() || undefined,
    method: safeString(value.method).trim() || undefined,
    surface: safeString(value.surface).trim() || undefined,
    mutates: safeBoolean(value.mutates, false),
    requires_confirmation: safeBoolean(value.requires_confirmation, false),
    write_guard: safeString(value.write_guard).trim() || undefined,
    target_mode: safeString(value.target_mode).trim() || undefined,
    receipt_kind: safeString(value.receipt_kind).trim() || undefined,
    attention_count: safeNumber(value.attention_count, 0),
    execution_authority: safeBoolean(value.execution_authority, false),
    approval_decision_authority: safeBoolean(value.approval_decision_authority, false),
    memory_write: safeBoolean(value.memory_write, false),
  };
}

function parsePaletteCommands(value: unknown): LensPaletteCommand[] {
  if (!Array.isArray(value)) return [];
  return value.map(parsePaletteCommand).filter((item): item is LensPaletteCommand => item !== null);
}

function parseModeSelector(value: unknown): LensModeSelector {
  const raw = safeRecord(value);
  return {
    status: safeString(raw.status).trim(),
    active_mode: safeString(raw.active_mode).trim(),
    available_modes: parseModeOptions(raw.available_modes),
    mutation_route: safeString(raw.mutation_route).trim(),
    write_guard: safeString(raw.write_guard).trim(),
  };
}

function parseApprovalView(value: unknown): LensApprovalView {
  const raw = safeRecord(value);
  const items = Array.isArray(raw.items)
    ? raw.items.filter((item): item is Record<string, unknown> => isRecord(item))
    : [];
  return {
    status: safeString(raw.status).trim(),
    pending_count: safeNumber(raw.pending_count, items.length),
    items,
    route: safeString(raw.route).trim(),
    decision_route: safeString(raw.decision_route).trim(),
    error: safeString(raw.error).trim() || undefined,
  };
}

function parseIncidentView(value: unknown): LensIncidentView {
  const raw = safeRecord(value);
  return {
    status: safeString(raw.status).trim(),
    observer_headline: safeString(raw.observer_headline).trim(),
    observer_decision: safeString(raw.observer_decision).trim(),
    observer_counts: parseNumberMap(raw.observer_counts),
    reactor_review_queue_total: safeNumber(raw.reactor_review_queue_total, 0),
    route: safeString(raw.route).trim(),
    reactor_route: safeString(raw.reactor_route).trim(),
    error: safeString(raw.error).trim() || undefined,
  };
}

function parseMissionFeed(value: unknown): LensMissionFeed {
  const raw = safeRecord(value);
  return {
    headline: safeString(raw.headline).trim(),
    counts: parseNumberMap(raw.counts),
    memory_receipt_count: safeNumber(raw.memory_receipt_count, 0),
    route: safeString(raw.route).trim(),
    mission_route: safeString(raw.mission_route).trim(),
  };
}

function parsePilotIndicator(value: unknown): LensPilotIndicator {
  const raw = safeRecord(value);
  return {
    active: safeBoolean(raw.active, false),
    status: safeString(raw.status).trim(),
    mode: safeString(raw.mode).trim(),
    message: safeString(raw.message).trim(),
    route: safeString(raw.route).trim(),
  };
}

function parseActivationDenialReceipt(value: unknown): LensActivationDenialReceipt | null {
  if (!isRecord(value)) return null;
  const receiptId = safeString(value.receipt_id).trim() || safeString(value.id).trim();
  const status = safeString(value.status).trim();
  if (!receiptId && !status) return null;
  return {
    kind: safeString(value.kind).trim() || undefined,
    receipt_id: receiptId || undefined,
    id: safeString(value.id).trim() || receiptId || undefined,
    status: status || undefined,
    route: safeString(value.route).trim() || undefined,
    method: safeString(value.method).trim() || undefined,
    source_kind: safeString(value.source_kind).trim() || undefined,
    source_route: safeString(value.source_route).trim() || undefined,
    approval_id: safeString(value.approval_id).trim() || undefined,
    actor: safeString(value.actor).trim() || undefined,
    reason: safeString(value.reason).trim() || undefined,
    created_ts: safeOptionalNumber(value.created_ts),
    blockers: safeStringList(value.blockers),
    approval: safeRecord(value.approval),
    permission: safeRecord(value.permission),
    execution: safeRecord(value.execution),
    denial: safeRecord(value.denial),
    governance: safeRecord(value.governance),
  };
}

function parseActivationDenialReceipts(value: unknown): LensActivationDenialReceipts {
  const raw = safeRecord(value);
  const items = Array.isArray(raw.items)
    ? raw.items
        .map(parseActivationDenialReceipt)
        .filter((item): item is LensActivationDenialReceipt => item !== null)
    : [];
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim(),
    status: safeString(raw.status).trim(),
    route: safeString(raw.route).trim(),
    execute_route: safeString(raw.execute_route).trim(),
    limit: safeNumber(raw.limit, 0),
    approval_id: safeString(raw.approval_id).trim(),
    filter_status: safeString(raw.filter_status).trim(),
    total: safeNumber(raw.total, items.length),
    latest: parseActivationDenialReceipt(raw.latest) ?? items[0],
    items,
    governance: safeRecord(raw.governance),
  };
}

function parseRuntimeLoopReadiness(value: unknown): LensRuntimeLoopReadiness {
  const raw = safeRecord(value);
  const requirements = Array.isArray(raw.requirements) ? raw.requirements.filter(isRecord) : [];
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    audit_status: safeString(raw.audit_status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    runtime_plan_route: safeString(raw.runtime_plan_route).trim() || undefined,
    runtime_loop_route: safeString(raw.runtime_loop_route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    denials_route: safeString(raw.denials_route).trim() || undefined,
    host_route: safeString(raw.host_route).trim() || undefined,
    approval_id: safeString(raw.approval_id).trim() || undefined,
    actor: safeString(raw.actor).trim() || undefined,
    limit: safeNumber(raw.limit, 0),
    ready: safeBoolean(raw.ready, false),
    loop_ready: safeBoolean(raw.loop_ready, false),
    execution_ready: safeBoolean(raw.execution_ready, false),
    resident_runtime_loop: safeBoolean(raw.resident_runtime_loop, false),
    resident_runtime_ready: safeBoolean(raw.resident_runtime_ready, false),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    runtime_plan_available: safeBoolean(raw.runtime_plan_available, false),
    loop_contract_readback_ready: safeBoolean(raw.loop_contract_readback_ready, false),
    execution_denial_boundary_observed: safeBoolean(raw.execution_denial_boundary_observed, false),
    denial_receipt_readback_ready: safeBoolean(raw.denial_receipt_readback_ready, false),
    receipt_count: safeNumber(raw.receipt_count, 0),
    latest_receipt_id: safeString(raw.latest_receipt_id).trim() || undefined,
    requirements_total: safeNumber(raw.requirements_total, requirements.length),
    requirements_ready_total: safeNumber(raw.requirements_ready_total, 0),
    requirements_blocked_total: safeNumber(raw.requirements_blocked_total, 0),
    requirements,
    blocked_requirements: safeStringList(raw.blocked_requirements),
    blockers: safeStringList(raw.blockers),
    source_readbacks: parseStringMap(raw.source_readbacks),
    evidence: safeStringList(raw.evidence),
    governance: safeRecord(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap).trim() || undefined,
    message: safeString(raw.message).trim() || undefined,
  };
}

function parseResidentHost(value: unknown): LensResidentHost {
  const raw = safeRecord(value);
  return {
    route: safeString(raw.route).trim(),
    status: safeString(raw.status).trim(),
    contract_status: safeString(raw.contract_status).trim(),
    availability: safeString(raw.availability).trim(),
    activation_denial_receipts_route: safeString(raw.activation_denial_receipts_route).trim(),
    activation_denial_receipts: parseActivationDenialReceipts(raw.activation_denial_receipts),
    runtime_loop_readiness_route: safeString(raw.runtime_loop_readiness_route).trim(),
    runtime_loop_readiness: parseRuntimeLoopReadiness(raw.runtime_loop_readiness),
  };
}

function parseStage6Criterion(value: unknown): LensStage6Criterion | null {
  if (!isRecord(value)) return null;
  const id = safeString(value.id).trim();
  if (!id) return null;
  return {
    id,
    status: safeString(value.status).trim(),
    evidence: safeStringList(value.evidence),
    command_count: safeOptionalNumber(value.command_count),
    pending_count: safeOptionalNumber(value.pending_count),
    receipt_count: safeOptionalNumber(value.receipt_count),
    latest_receipt_id: safeString(value.latest_receipt_id).trim() || undefined,
    observer_active_count: safeOptionalNumber(value.observer_active_count),
    reactor_review_queue_total: safeOptionalNumber(value.reactor_review_queue_total),
    mission_counts: parseNumberMap(value.mission_counts),
    reactor_readback_surfaces: parseStringMap(value.reactor_readback_surfaces),
    ready: typeof value.ready === "boolean" ? safeBoolean(value.ready, false) : undefined,
    resident_overlay:
      typeof value.resident_overlay === "boolean" ? safeBoolean(value.resident_overlay, false) : undefined,
    resident_claim_allowed:
      typeof value.resident_claim_allowed === "boolean"
        ? safeBoolean(value.resident_claim_allowed, false)
        : undefined,
    summon_anywhere:
      typeof value.summon_anywhere === "boolean" ? safeBoolean(value.summon_anywhere, false) : undefined,
    global_hotkey: safeString(value.global_hotkey).trim() || undefined,
    tray_presence: typeof value.tray_presence === "boolean" ? safeBoolean(value.tray_presence, false) : undefined,
    presence_name: safeString(value.presence_name).trim() || undefined,
    overlay_window: typeof value.overlay_window === "boolean" ? safeBoolean(value.overlay_window, false) : undefined,
    overlay_name: safeString(value.overlay_name).trim() || undefined,
    execution_authority:
      typeof value.execution_authority === "boolean" ? safeBoolean(value.execution_authority, false) : undefined,
    approval_decision_authority:
      typeof value.approval_decision_authority === "boolean"
        ? safeBoolean(value.approval_decision_authority, false)
        : undefined,
    local_process_launch_authority:
      typeof value.local_process_launch_authority === "boolean"
        ? safeBoolean(value.local_process_launch_authority, false)
        : undefined,
    service_control_authority:
      typeof value.service_control_authority === "boolean"
        ? safeBoolean(value.service_control_authority, false)
        : undefined,
    window_management_authority:
      typeof value.window_management_authority === "boolean"
        ? safeBoolean(value.window_management_authority, false)
        : undefined,
    hotkey_registration_authority:
      typeof value.hotkey_registration_authority === "boolean"
        ? safeBoolean(value.hotkey_registration_authority, false)
        : undefined,
    tray_registration_authority:
      typeof value.tray_registration_authority === "boolean"
        ? safeBoolean(value.tray_registration_authority, false)
        : undefined,
    tray_icon_authority:
      typeof value.tray_icon_authority === "boolean" ? safeBoolean(value.tray_icon_authority, false) : undefined,
    notification_authority:
      typeof value.notification_authority === "boolean" ? safeBoolean(value.notification_authority, false) : undefined,
    overlay_control_authority:
      typeof value.overlay_control_authority === "boolean"
        ? safeBoolean(value.overlay_control_authority, false)
        : undefined,
    summon_authority:
      typeof value.summon_authority === "boolean" ? safeBoolean(value.summon_authority, false) : undefined,
    capture_authority:
      typeof value.capture_authority === "boolean" ? safeBoolean(value.capture_authority, false) : undefined,
    memory_write: typeof value.memory_write === "boolean" ? safeBoolean(value.memory_write, false) : undefined,
    blockers: safeStringList(value.blockers),
  };
}

function parseStage6ClosureCriterion(value: unknown): LensStage6ClosureCriterion | null {
  if (!isRecord(value)) return null;
  const id = safeString(value.id).trim();
  if (!id) return null;
  return {
    id,
    label: safeString(value.label).trim() || undefined,
    ready: typeof value.ready === "boolean" ? safeBoolean(value.ready, false) : undefined,
    status: safeString(value.status).trim() || undefined,
    evidence: safeStringList(value.evidence),
    blockers: safeStringList(value.blockers),
    basis: safeString(value.basis).trim() || undefined,
  };
}

function parseStage6ClosureReadback(value: unknown): LensStage6ClosureReadback {
  const raw = safeRecord(value);
  const criteria = Array.isArray(raw.criteria)
    ? raw.criteria.map(parseStage6ClosureCriterion).filter((item): item is LensStage6ClosureCriterion => item !== null)
    : [];
  return {
    kind: safeString(raw.kind).trim(),
    status: safeString(raw.status).trim(),
    ready_to_close: safeBoolean(raw.ready_to_close, false),
    criteria_total: safeNumber(raw.criteria_total, criteria.length),
    ready_total: safeNumber(raw.ready_total, 0),
    blocked_total: safeNumber(raw.blocked_total, criteria.filter((item) => item.ready === false).length),
    ready_criteria: safeStringList(raw.ready_criteria),
    blocked_criteria: safeStringList(raw.blocked_criteria),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap).trim() || undefined,
    criteria,
    governance: safeRecord(raw.governance),
  };
}

function parseStage6Readiness(value: unknown): LensStage6Readiness {
  const raw = safeRecord(value);
  const criteria = Array.isArray(raw.criteria)
    ? raw.criteria.map(parseStage6Criterion).filter((item): item is LensStage6Criterion => item !== null)
    : [];
  return {
    stage: safeString(raw.stage).trim(),
    claim: safeString(raw.claim).trim(),
    closure_readback: parseStage6ClosureReadback(raw.closure_readback),
    criteria,
  };
}

function parseGovernance(value: unknown): LensGovernance {
  const raw = safeRecord(value);
  return {
    gate: safeString(raw.gate).trim(),
    execution_authority: safeBoolean(raw.execution_authority, false),
    approval_decision_authority: safeBoolean(raw.approval_decision_authority, false),
    memory_write: safeBoolean(raw.memory_write, false),
    overlay_control_authority: safeBoolean(raw.overlay_control_authority, false),
    capture_authority: safeBoolean(raw.capture_authority, false),
    new_sensing_authority: safeBoolean(raw.new_sensing_authority, false),
  };
}

export function parseLensStatus(value: unknown): LensStatus {
  const raw = safeRecord(value);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim(),
    subsystem: safeString(raw.subsystem).trim(),
    status: safeString(raw.status).trim(),
    generated_at: safeNumber(raw.generated_at, 0),
    limit: safeNumber(raw.limit, 0),
    read_only: safeBoolean(raw.read_only, false),
    mode: safeRecord(raw.mode),
    available_modes: parseModeOptions(raw.available_modes),
    scope: safeRecord(raw.scope),
    hud: parseHud(raw.hud),
    resident_host: parseResidentHost(raw.resident_host),
    command_palette: parseCommandPalette(raw.command_palette),
    mode_selector: parseModeSelector(raw.mode_selector),
    approvals_view: parseApprovalView(raw.approvals_view),
    incident_view: parseIncidentView(raw.incident_view),
    mission_feed: parseMissionFeed(raw.mission_feed),
    pilot_indicator: parsePilotIndicator(raw.pilot_indicator),
    receipts: safeRecord(raw.receipts),
    runtime_loop_readiness: parseRuntimeLoopReadiness(raw.runtime_loop_readiness),
    stage6_readiness: parseStage6Readiness(raw.stage6_readiness),
    governance: parseGovernance(raw.governance),
    error: safeString(raw.error).trim() || undefined,
  };
}

export class LensClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = (baseUrl || "").replace(/\/+$/, "");
  }

  async getStatus(opts?: { limit?: number; signal?: AbortSignal }): Promise<LensStatus> {
    const safeLimit = Math.max(1, Math.min(Math.floor(opts?.limit ?? 5), 50));
    const url = `${this.baseUrl}/lens/status?limit=${encodeURIComponent(String(safeLimit))}`;
    const res = await fetch(url, { method: "GET", signal: opts?.signal });
    const text = await res.text();
    let json: unknown = {};
    if (text.trim()) {
      try {
        json = JSON.parse(text);
      } catch (err) {
        throw new LensApiError("Lens response was not valid JSON.", {
          status: res.status,
          url,
          cause: err,
        });
      }
    }
    if (!res.ok) {
      throw new LensApiError(`Lens request failed with HTTP ${res.status}.`, { status: res.status, url });
    }
    return parseLensStatus(json);
  }
}
