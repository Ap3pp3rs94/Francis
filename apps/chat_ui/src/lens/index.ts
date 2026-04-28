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

export type LensStage6Criterion = {
  id?: string;
  status?: string;
  evidence: string[];
  command_count?: number;
  pending_count?: number;
  observer_active_count?: number;
  reactor_review_queue_total?: number;
  mission_counts?: Record<string, number>;
  reactor_readback_surfaces?: Record<string, string>;
  resident_overlay?: boolean;
  blockers: string[];
};

export type LensStage6Readiness = {
  stage?: string;
  claim?: string;
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
  command_palette: LensCommandPalette;
  mode_selector: LensModeSelector;
  approvals_view: LensApprovalView;
  incident_view: LensIncidentView;
  mission_feed: LensMissionFeed;
  pilot_indicator: LensPilotIndicator;
  receipts: Record<string, unknown>;
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
    observer_active_count: safeOptionalNumber(value.observer_active_count),
    reactor_review_queue_total: safeOptionalNumber(value.reactor_review_queue_total),
    mission_counts: parseNumberMap(value.mission_counts),
    reactor_readback_surfaces: parseStringMap(value.reactor_readback_surfaces),
    resident_overlay:
      typeof value.resident_overlay === "boolean" ? safeBoolean(value.resident_overlay, false) : undefined,
    blockers: safeStringList(value.blockers),
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
    command_palette: parseCommandPalette(raw.command_palette),
    mode_selector: parseModeSelector(raw.mode_selector),
    approvals_view: parseApprovalView(raw.approvals_view),
    incident_view: parseIncidentView(raw.incident_view),
    mission_feed: parseMissionFeed(raw.mission_feed),
    pilot_indicator: parsePilotIndicator(raw.pilot_indicator),
    receipts: safeRecord(raw.receipts),
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
