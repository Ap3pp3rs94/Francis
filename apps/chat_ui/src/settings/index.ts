/**
 * Settings module (UI).
 *
 * This module is the browser-side "control plane" for:
 *  - Server introspection: health, runtime info, effective config snapshot
 *  - Feature flags (read by default; optionally mutable)
 *  - UI preferences (local, versioned, defensive storage)
 *
 * Design contract:
 *  1) Framework-agnostic core:
 *     - This file contains NO React imports.
 *     - Consumers (React components) should live alongside (e.g., SettingsPanel.tsx).
 *
 *  2) Defensive parsing:
 *     - Treat all JSON as untrusted.
 *     - Accept reasonable alias shapes for forward/back compatibility.
 *
 *  3) Safe-by-default mutations:
 *     - "Write" endpoints exist but are opt-in (mutationsEnabled=false by default).
 *     - Server should enforce approvals/policies for any mutation.
 *
 *  4) Forward-compatible endpoints:
 *     - Endpoints are configurable and can probe multiple candidate paths.
 *     - This lets backend routes evolve without breaking the UI immediately.
 */

export type UnixSeconds = number;

export type SystemInfo = {
  service?: string;
  instance_id?: string;
  version?: string;
  build?: string;
  git_sha?: string;

  env_profile?: string;
  run_mode?: string;

  started_ts?: UnixSeconds;
  uptime_s?: number;

  host?: string;
  pid?: number;

  python?: {
    version?: string;
    executable?: string;
    implementation?: string;
    platform?: string;
  };

  meta?: Record<string, unknown>;
};

export type HealthCheck = {
  name?: string;
  ok: boolean;
  detail?: string;
  latency_ms?: number;
  ts?: UnixSeconds;
  meta?: Record<string, unknown>;
};

export type SystemHealth = {
  ok: boolean;
  status?: string; // "ok" | "degraded" | "down" | ...
  ts?: UnixSeconds;
  checks?: HealthCheck[];
  meta?: Record<string, unknown>;
};

export type FeatureFlag = {
  key: string;
  enabled: boolean;

  description?: string;
  source?: string; // e.g., "env", "config", "runtime"
  ts?: UnixSeconds;

  meta?: Record<string, unknown>;
};

export type FeatureFlagsResponse = {
  items: FeatureFlag[];
};

export type EffectiveConfigSnapshot = {
  ts?: UnixSeconds;
  env_profile?: string;
  run_mode?: string;

  // The effective, merged config. Shape is intentionally open-ended.
  config: Record<string, unknown>;

  // Optional provenance hints (forward compatible)
  sources?: Record<string, string>;
  meta?: Record<string, unknown>;
};

export type WorldStatePathState = {
  path?: string;
  exists?: boolean;
  is_dir?: boolean;
};

export type WorldStateCounts = {
  pending_approvals?: number;
  approved_approvals?: number;
  rejected_approvals?: number;
  tasks?: number;
  queued_tasks?: number;
  approval_pending_tasks?: number;
  blocked_tasks?: number;
  running_tasks?: number;
  missions?: number;
  queued_missions?: number;
  active_missions?: number;
  blocked_missions?: number;
  deadlettered_missions?: number;
  active_incidents?: number;
  generated_plugins?: number;
};

export type WorldStateApprovalSummary = {
  id: string;
  action?: string;
  reason?: string;
  status?: string;
  ts?: UnixSeconds;
  request_kind?: string;
  previous_approval_id?: string;
  previous_approval_status?: string;
  payload_summary?: WorldStateApprovalPayloadSummary;
};

export type WorldStateApprovalPayloadSummary = {
  requested_action?: string;
  plugin_id?: string;
  scope_id?: string;
  provider?: string;
  credential_type?: string;
  label?: string;
  credential_id?: string;
  target_kind?: string;
  target_id?: string;
  twin_id?: string;
  url?: string;
  domain?: string;
  actor?: string;
  risk?: string;
  enabled?: boolean;
  dry_run?: boolean;
  risk_tier?: string;
  required_trust?: number;
  payload_keys?: string[];
  input_keys?: string[];
  meta_keys?: string[];
  params_keys?: string[];
};

export type WorldStateTaskSummary = {
  id: string;
  status?: string;
  capability?: string;
  objective?: string;
  requester_id?: string;
  assigned_to?: string;
  created_at?: string;
  updated_at?: string;
  status_reason?: string;
  terminal?: boolean;
};

export type WorldStateIncidentSummary = {
  id: string;
  severity?: string;
  category?: string;
  status?: string;
  title?: string;
  detail?: string;
  source?: string;
  count?: number;
  approval_id?: string;
  task_id?: string;
  probe?: string;
  observed_at?: number;
  evidence?: Array<{
    kind?: string;
    id?: string;
    label?: string;
    status?: string;
    detail?: string;
    path?: string;
    ts?: number;
  }>;
};

export type WorldStateMissionSummary = {
  id: string;
  status?: string;
  objective?: string;
  summary?: string;
  next_step?: string;
  requester_id?: string;
  owner_id?: string;
  priority?: number;
  risk_tier?: string;
  dependency_ids?: string[];
  dependency_count?: number;
  escalation_path?: string;
  linked_task_ids?: string[];
  linked_task_count?: number;
  deadletter_reason?: string;
  last_task_id?: string;
  last_task_status?: string;
  last_task_result_status?: string;
  last_task_reason?: string;
  last_task_gate?: string;
  last_task_next_step?: string;
  last_task_updated_at?: string;
  created_at?: string;
  updated_at?: string;
  terminal?: boolean;
  latest_activity?: Record<string, unknown>;
};

export type WorldStateMissionDependencyItem = {
  id?: string;
  kind?: string;
  state?: string;
  status?: string;
  result_status?: string;
  gate?: string;
  approval_id?: string;
  objective?: string;
  detail?: string;
  updated_at?: string;
};

export type WorldStateMissionDependencyState = {
  status?: string;
  total?: number;
  resolved?: number;
  unresolved?: number;
  items?: WorldStateMissionDependencyItem[];
  first_unresolved?: WorldStateMissionDependencyItem;
};

export type WorldStateMissionAdvanceProjection = {
  eligible?: boolean;
  action?: string;
  target_id?: string;
  reason?: string;
};

export type WorldStateMissionQueueItem = {
  id: string;
  status?: string;
  objective?: string;
  summary?: string;
  next_step?: string;
  owner_id?: string;
  priority?: number;
  risk_tier?: string;
  dependency_ids?: string[];
  dependency_count?: number;
  dependency_state?: WorldStateMissionDependencyState;
  escalation_path?: string;
  linked_task_count?: number;
  linked_task_ids?: string[];
  last_task_id?: string;
  last_task_status?: string;
  last_task_result_status?: string;
  last_task_gate?: string;
  last_task_approval_id?: string;
  last_task_previous_approval_id?: string;
  last_task_approval_status?: string;
  recommended_action?: string;
  operator_hint?: string;
  action_target_id?: string;
  advance?: WorldStateMissionAdvanceProjection;
  deadletter_reason?: string;
  updated_at?: string;
  latest_activity?: Record<string, unknown>;
};

export type WorldStateOverview = {
  pending_approvals: WorldStateApprovalSummary[];
  task_status_counts: Record<string, number>;
  recent_tasks: WorldStateTaskSummary[];
  mission_status_counts: Record<string, number>;
  recent_missions: WorldStateMissionSummary[];
  mission_queue: WorldStateMissionQueueItem[];
  deadletter_missions: WorldStateMissionQueueItem[];
  incidents: WorldStateIncidentSummary[];
};

export type WorldStateSnapshot = {
  ok: boolean;
  subsystem?: string;
  generated_at?: number;
  repo_root?: string;
  data_dir?: string;
  counts?: WorldStateCounts;
  paths?: Record<string, WorldStatePathState>;
  overview?: WorldStateOverview;
  trust?: Record<string, unknown>;
  stack?: Record<string, unknown>;
  services?: Record<string, unknown>;
  meta?: Record<string, unknown>;
};

export type OrbPlaneSummary = {
  id: string;
  name?: string;
  category?: string;
  purpose?: string;
  side_effects_allowed?: boolean;
  default_risk_class?: string;
  primary_modules?: string[];
};

export type OrbGateSummary = {
  id: string;
  description?: string;
};

export type OrbTransitionSummary = {
  from: string;
  to: string;
  conditions: string[];
  reason?: string;
};

export type OrbModelInfo = {
  plane_map_id?: string;
  plane_map_version?: number;
  action_taxonomy_id?: string;
  action_taxonomy_version?: number;
};

export type OrbStatusSnapshot = {
  ok: boolean;
  subsystem?: string;
  generated_at?: number;
  repo_root?: string;
  model?: OrbModelInfo;
  core_loop?: OrbPlaneSummary[];
  planes?: OrbPlaneSummary[];
  gates?: OrbGateSummary[];
  transitions?: {
    allowed: OrbTransitionSummary[];
    forbidden: OrbTransitionSummary[];
  };
  state?: Record<string, unknown>;
  meta?: Record<string, unknown>;
};

export type OperatorModeEnvironment = {
  id: string;
  name?: string;
  description?: string;
  label?: string;
  banner_text?: string;
  run_mode?: string;
  runtime_mode?: string;
  profile_path?: string;
};

export type OperatorModePosture = {
  governance_mode?: string;
  trust_posture?: string;
  trust_level?: number;
  minimum_operational_trust?: number;
  web_access?: string;
  writes?: string;
  network_egress?: string;
};

export type OperatorModeFocus = {
  plane_id: string;
  label?: string;
  reason?: string;
};

export type OperatorModeBacklog = {
  pending_approvals?: number;
  approval_pending_tasks?: number;
  blocked_tasks?: number;
  queued_tasks?: number;
  running_tasks?: number;
};

export type OperatorControlModeId = "observe" | "assist" | "pilot" | "away" | string;

export type OperatorControlMode = {
  id: OperatorControlModeId;
  label?: string;
  summary?: string;
  writes?: string;
  implementation_status?: string;
  changed_at?: number;
  changed_by?: string;
  reason?: string;
  source?: string;
};

export type OperatorControlModeOption = {
  id: OperatorControlModeId;
  label?: string;
  summary?: string;
  implementation_status?: string;
  active?: boolean;
};

export type OperatorModeSnapshot = {
  ok: boolean;
  subsystem?: string;
  generated_at?: number;
  environment?: OperatorModeEnvironment;
  posture?: OperatorModePosture;
  control_mode?: OperatorControlMode;
  available_modes?: OperatorControlModeOption[];
  focus?: OperatorModeFocus;
  backlog?: OperatorModeBacklog;
  notes?: string[];
  meta?: Record<string, unknown>;
};

export type ContinuityBriefingFocusItem = {
  id: string;
  status?: string;
  objective?: string;
  summary?: string;
  next_step?: string;
  priority?: number;
  risk_tier?: string;
  dependency_ids?: string[];
  dependency_count?: number;
  dependency_state?: WorldStateMissionDependencyState;
  escalation_path?: string;
  linked_task_count?: number;
  recommended_action?: string;
  operator_hint?: string;
  action_target_id?: string;
  advance?: WorldStateMissionAdvanceProjection;
  last_task_id?: string;
  last_task_status?: string;
  last_task_result_status?: string;
  last_task_gate?: string;
  last_task_approval_id?: string;
  last_task_previous_approval_id?: string;
  last_task_approval_status?: string;
  last_advance_action?: string;
  last_advance_outcome?: string;
  last_advance_operation_id?: string;
  last_advance_operation_status?: string;
  last_advance_message?: string;
  last_advance_actor?: string;
  last_advance_applied?: boolean;
  last_advance_at?: string;
  deadletter_reason?: string;
  updated_at?: string;
  latest_activity?: Record<string, unknown>;
};

export type ContinuityBriefingCompletedItem = {
  id: string;
  objective?: string;
  updated_at?: string;
  last_task_id?: string;
  last_advance_action?: string;
  last_advance_outcome?: string;
  latest_activity?: Record<string, unknown>;
};

export type ContinuityBriefingDeadletterItem = {
  id: string;
  objective?: string;
  reason?: string;
  recommended_action?: string;
  updated_at?: string;
  latest_activity?: Record<string, unknown>;
};

export type ObserverAnomalySummary = {
  score?: number;
  level?: string;
  reasons?: string[];
};

export type ObserverProbeSummary = {
  id?: string;
  status?: string;
  severity?: string;
  headline?: string;
  detail?: string;
  incident_count?: number;
  observed_at?: number;
};

export type ObserverReadinessCriterion = {
  id?: string;
  label?: string;
  status?: string;
  detail?: string;
  evidence?: Record<string, unknown>;
};

export type ObserverReadinessSummary = {
  stage?: string;
  status?: string;
  criteria?: ObserverReadinessCriterion[];
  satisfied?: number;
  total?: number;
  next_action?: string;
};

export type MissionReadinessCriterion = ObserverReadinessCriterion;
export type MissionReadinessSummary = ObserverReadinessSummary;

export type ObserverScanReceiptSummary = {
  ts?: number;
  receipt_id?: string;
  event?: string;
  status?: string;
  decision?: string;
  headline?: string;
  incident_count?: number;
  counts?: Record<string, number>;
  incident_ids?: string[];
  probes?: string[];
  focus?: WorldStateIncidentSummary[];
  probe_statuses?: ObserverProbeSummary[];
  anomaly?: ObserverAnomalySummary;
  generated_at?: number;
  reason?: string;
  actor?: string;
  trace_id?: string;
  run_id?: string;
};

export type ObserverEventsSnapshot = {
  ok: boolean;
  subsystem?: string;
  items: ObserverScanReceiptSummary[];
  total?: number;
  limit?: number;
  error?: string;
};

export type ContinuityBriefingPayload = {
  headline?: string;
  counts?: Record<string, number>;
  focus?: ContinuityBriefingFocusItem[];
  recently_completed?: ContinuityBriefingCompletedItem[];
  deadletter_preview?: ContinuityBriefingDeadletterItem[];
  readiness?: MissionReadinessSummary;
  observer?: {
    headline?: string;
    counts?: Record<string, number>;
    focus?: WorldStateIncidentSummary[];
    probes?: ObserverProbeSummary[];
    recent_scans?: ObserverScanReceiptSummary[];
    anomaly?: ObserverAnomalySummary;
    readiness?: ObserverReadinessSummary;
    observed_at?: number;
    error?: string;
  };
};

export type ContinuityLedgerEntry = {
  ts?: UnixSeconds;
  role: string;
  content: string;
  meta?: Record<string, unknown>;
};

export type ContinuityLedgerSnapshot = {
  entries: ContinuityLedgerEntry[];
  error?: string;
};

type MissionDeadletterLike = {
  id: string;
  status?: string;
  objective?: string;
  reason?: string;
  recommended_action?: string;
  updated_at?: string;
  latest_activity?: Record<string, unknown>;
  deadletter_reason?: string;
  last_task_id?: string;
};

export type MissionDeadletterPresentationItem = {
  id: string;
  status?: string;
  objective?: string;
  reason?: string;
  recommended_action?: string;
  updated_at?: string;
  latest_activity?: Record<string, unknown>;
  last_task_id?: string;
};

export type MissionDeadletterPresentation = {
  ordered: MissionDeadletterPresentationItem[];
  visible: MissionDeadletterPresentationItem[];
  total: number;
  hiddenTotal: number;
};

export type ContinuityOperatorSurface = {
  available: boolean;
  error?: string;
  control_mode?: OperatorControlMode;
  focus?: OperatorModeFocus;
  posture?: OperatorModePosture;
};

export type ContinuityOrbSurface = {
  available: boolean;
  error?: string;
  state?: Record<string, unknown>;
};

export type ContinuityBriefingSnapshot = {
  ok: boolean;
  subsystem?: string;
  generated_at?: number;
  briefing?: ContinuityBriefingPayload;
  mission_status_counts?: Record<string, number>;
  recent_missions?: WorldStateMissionSummary[];
  operator?: ContinuityOperatorSurface;
  orb?: ContinuityOrbSurface;
  meta?: Record<string, unknown>;
};

/**
 * A controlled server mutation request.
 * The backend is expected to enforce approvals/policy; the UI just submits intent.
 */
export type ConfigMutationOp = "set" | "unset" | "merge" | "append" | "remove" | string;

export type ConfigMutationRequest = {
  op: ConfigMutationOp;

  /**
   * Path format is intentionally flexible:
   *  - dot.path.like.this
   *  - /json/pointer/style
   *
   * Backend decides what it supports; UI remains forward-compatible.
   */
  path: string;

  value?: unknown;

  // Strongly recommended: justification / governance context
  reason?: string;
  domain?: string;
  actor?: string;

  meta?: Record<string, unknown>;
};

export type ConfigMutationResponse = {
  ok: boolean;

  /**
   * If mutations are approval-gated, backend can return:
   *  - approval_id: created approval item
   *  - status: "pending" | "approved" | "rejected" | ...
   */
  approval_id?: string;
  status?: string;

  /**
   * If applied immediately (no approval required), backend can return:
   *  - applied: true
   *  - resulting_value or snapshot
   */
  applied?: boolean;
  resulting_value?: unknown;

  message?: string;
  meta?: Record<string, unknown>;
};

export type ObserverScanRequest = {
  reason?: string;
  actor?: string;
  meta?: Record<string, unknown>;
};

export type ObserverScanResponse = {
  ok: boolean;
  subsystem?: string;
  headline?: string;
  decision?: string;
  observed_at?: number;
  counts?: Record<string, number>;
  anomaly?: ObserverAnomalySummary;
  receipt?: ObserverScanReceiptSummary;
  readiness?: ObserverReadinessSummary;
};

export type OperatorModeMutationRequest = {
  mode: OperatorControlModeId;
  reason?: string;
  actor?: string;
  meta?: Record<string, unknown>;
};

export type OperatorModeMutationResponse = {
  ok: boolean;
  applied?: boolean;
  status?: string;
  message?: string;
  snapshot?: OperatorModeSnapshot;
};

export class SettingsApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly requestId?: string;
  readonly bodySnippet?: string;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; requestId?: string; bodySnippet?: string; cause?: unknown },
  ) {
    super(message);
    this.name = "SettingsApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.requestId = opts?.requestId;
    this.bodySnippet = opts?.bodySnippet;
    // @ts-expect-error - Error.cause not always in TS lib target
    this.cause = opts?.cause;
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeBoolean(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function safeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => safeString(item, "")).filter(Boolean);
}

function parseWorldStateApprovalPayloadSummary(raw: Record<string, unknown>): WorldStateApprovalPayloadSummary {
  const summary: WorldStateApprovalPayloadSummary = {};
  const requestedAction = safeString(raw.requested_action, "");
  if (requestedAction) summary.requested_action = requestedAction;
  const pluginId = safeString(raw.plugin_id, "");
  if (pluginId) summary.plugin_id = pluginId;
  const scopeId = safeString(raw.scope_id, "");
  if (scopeId) summary.scope_id = scopeId;
  const provider = safeString(raw.provider, "");
  if (provider) summary.provider = provider;
  const credentialType = safeString(raw.credential_type, "");
  if (credentialType) summary.credential_type = credentialType;
  const label = safeString(raw.label, "");
  if (label) summary.label = label;
  const credentialId = safeString(raw.credential_id, "");
  if (credentialId) summary.credential_id = credentialId;
  const targetKind = safeString(raw.target_kind, "");
  if (targetKind) summary.target_kind = targetKind;
  const targetId = safeString(raw.target_id, "");
  if (targetId) summary.target_id = targetId;
  const twinId = safeString(raw.twin_id, "");
  if (twinId) summary.twin_id = twinId;
  const url = safeString(raw.url, "");
  if (url) summary.url = url;
  const domain = safeString(raw.domain, "");
  if (domain) summary.domain = domain;
  const actor = safeString(raw.actor, "");
  if (actor) summary.actor = actor;
  const risk = safeString(raw.risk, "");
  if (risk) summary.risk = risk;
  if (typeof raw.enabled === "boolean") summary.enabled = raw.enabled;
  if (typeof raw.dry_run === "boolean") summary.dry_run = raw.dry_run;
  const riskTier = safeString(raw.risk_tier, "");
  if (riskTier) summary.risk_tier = riskTier;
  if (typeof raw.required_trust === "number" && Number.isFinite(raw.required_trust)) {
    summary.required_trust = raw.required_trust;
  }
  const payloadKeys = safeStringList(raw.payload_keys);
  if (payloadKeys.length > 0) summary.payload_keys = payloadKeys;
  const inputKeys = safeStringList(raw.input_keys);
  if (inputKeys.length > 0) summary.input_keys = inputKeys;
  const metaKeys = safeStringList(raw.meta_keys);
  if (metaKeys.length > 0) summary.meta_keys = metaKeys;
  const paramsKeys = safeStringList(raw.params_keys);
  if (paramsKeys.length > 0) summary.params_keys = paramsKeys;
  return summary;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function safeStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map((item) => safeString(item, "").trim()).filter((item) => item.length > 0);
}

function parseWorldStateMissionDependencyItem(raw: unknown): WorldStateMissionDependencyItem | undefined {
  if (!isRecord(raw)) return undefined;
  return {
    id: safeString(raw.id, ""),
    kind: safeString(raw.kind, ""),
    state: safeString(raw.state, ""),
    status: safeString(raw.status, ""),
    result_status: safeString(raw.result_status, ""),
    gate: safeString(raw.gate, ""),
    approval_id: safeString(raw.approval_id, ""),
    objective: safeString(raw.objective, ""),
    detail: safeString(raw.detail, ""),
    updated_at: safeString(raw.updated_at, ""),
  };
}

function parseWorldStateMissionDependencyState(raw: unknown): WorldStateMissionDependencyState | undefined {
  if (!isRecord(raw)) return undefined;
  const items = Array.isArray(raw.items)
    ? raw.items
        .map(parseWorldStateMissionDependencyItem)
        .filter((item): item is WorldStateMissionDependencyItem => item !== undefined)
    : [];
  return {
    status: safeString(raw.status, ""),
    total: safeNumber(raw.total, 0),
    resolved: safeNumber(raw.resolved, 0),
    unresolved: safeNumber(raw.unresolved, 0),
    items,
    first_unresolved: parseWorldStateMissionDependencyItem(raw.first_unresolved),
  };
}

function normalizeUnixSeconds(ts: unknown): UnixSeconds | undefined {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return undefined;
  // Heuristic: if it looks like milliseconds, normalize to seconds.
  if (ts > 10_000_000_000) return Math.floor(ts / 1000);
  return Math.floor(ts);
}

function missionDeadletterTimestamp(item: MissionDeadletterPresentationItem): number {
  const updatedAt = Date.parse(safeString(item.updated_at, ""));
  if (Number.isFinite(updatedAt)) return updatedAt;
  const latestActivity = item.latest_activity;
  if (isRecord(latestActivity)) {
    const activityTs = latestActivity.ts;
    if (typeof activityTs === "number" && Number.isFinite(activityTs)) {
      return activityTs > 10_000_000_000 ? activityTs : activityTs * 1000;
    }
    const parsedActivityTs = Date.parse(safeString(activityTs, ""));
    if (Number.isFinite(parsedActivityTs)) return parsedActivityTs;
  }
  return 0;
}

export function presentMissionDeadletterItems(items: MissionDeadletterLike[], limit = 2): MissionDeadletterPresentation {
  const normalized = items
    .map((item, index) => ({
      item: {
        id: safeString(item.id, "").trim(),
        status: safeString(item.status, "").trim() || undefined,
        objective: safeString(item.objective, "") || undefined,
        reason: safeString(item.reason, "").trim() || safeString(item.deadletter_reason, "").trim() || undefined,
        recommended_action: safeString(item.recommended_action, "").trim() || undefined,
        updated_at: safeString(item.updated_at, "").trim() || undefined,
        latest_activity: isRecord(item.latest_activity) ? item.latest_activity : undefined,
        last_task_id: safeString(item.last_task_id, "").trim() || undefined,
      } satisfies MissionDeadletterPresentationItem,
      index,
    }))
    .filter((entry) => entry.item.id.length > 0)
    .sort((left, right) => {
      const leftActionable = left.item.recommended_action ? 0 : 1;
      const rightActionable = right.item.recommended_action ? 0 : 1;
      if (leftActionable !== rightActionable) return leftActionable - rightActionable;
      const leftReason = left.item.reason ? 0 : 1;
      const rightReason = right.item.reason ? 0 : 1;
      if (leftReason !== rightReason) return leftReason - rightReason;
      const timestampDelta = missionDeadletterTimestamp(right.item) - missionDeadletterTimestamp(left.item);
      if (timestampDelta !== 0) return timestampDelta;
      return left.index - right.index;
    });
  const ordered = normalized.map((entry) => entry.item);
  const safeLimit = Number.isFinite(limit) ? Math.max(0, Math.floor(limit)) : ordered.length;
  const visible = ordered.slice(0, safeLimit);
  return {
    ordered,
    visible,
    total: ordered.length,
    hiddenTotal: Math.max(0, ordered.length - visible.length),
  };
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function buildQuery(params: Record<string, unknown> | undefined): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) {
      for (const item of v) sp.append(k, String(item));
    } else {
      sp.set(k, String(v));
    }
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function readTextSnippet(res: Response, maxChars = 4096): Promise<string> {
  try {
    const txt = await res.text();
    return txt.length > maxChars ? `${txt.slice(0, maxChars)}…` : txt;
  } catch {
    return "";
  }
}

type TimeoutFetchInit = RequestInit & {
  timeoutMs?: number;
  /**
   * Optional auth token (bearer). Intentionally not stored anywhere by this module.
   * Prefer cookies in production; tokens are acceptable for local/internal consoles.
   */
  bearerToken?: string | null;

  /**
   * Extra headers (merged with defaults).
   */
  headersExtra?: Record<string, string>;
};

async function fetchWithTimeout(url: string, init?: TimeoutFetchInit): Promise<Response> {
  const { timeoutMs = 20_000, signal: externalSignal, bearerToken, headersExtra, ...fetchInit } = init ?? {};

  const controller = new AbortController();
  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null;

  if (timeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => {
      controller.abort();
    }, timeoutMs);
  }

  const onExternalAbort = () => controller.abort();

  if (externalSignal) {
    if (externalSignal.aborted) {
      onExternalAbort();
    } else {
      externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }
  }

  try {
    const headers = new Headers(fetchInit.headers ?? undefined);

    // Defaults: this module is JSON-centric.
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (fetchInit.method && fetchInit.method !== "GET" && fetchInit.method !== "HEAD") {
      if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    }

    if (bearerToken) {
      // NOTE: Token handling is caller-owned; do not persist in localStorage here.
      headers.set("Authorization", `Bearer ${bearerToken}`);
    }

    if (headersExtra) {
      for (const [k, v] of Object.entries(headersExtra)) headers.set(k, v);
    }

    return await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });
  } finally {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
    if (externalSignal && !externalSignal.aborted) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }
}

async function fetchJson(url: string, init?: TimeoutFetchInit): Promise<{ res: Response; json: unknown }> {
  const res = await fetchWithTimeout(url, init);

  if (!res.ok) {
    const snippet = await readTextSnippet(res);
    const requestId =
      res.headers.get("x-request-id") ??
      res.headers.get("x-correlation-id") ??
      res.headers.get("x-trace-id") ??
      undefined;

    throw new SettingsApiError(`HTTP ${res.status} for settings request`, {
      status: res.status,
      url,
      requestId,
      bodySnippet: snippet,
    });
  }

  const json = await res.json();
  return { res, json };
}

function parseSystemInfo(raw: unknown): SystemInfo {
  if (!isRecord(raw)) return {};

  // Accept alias shapes:
  //  - { service, version, env_profile, ... }
  //  - { info: { ... } }
  const obj = isRecord(raw.info) ? (raw.info as Record<string, unknown>) : raw;

  const info: SystemInfo = {
    service: safeString(obj.service, ""),
    instance_id: safeString(obj.instance_id, ""),
    version: safeString(obj.version, ""),
    build: safeString(obj.build, ""),
    git_sha: safeString(obj.git_sha, ""),

    env_profile: safeString(obj.env_profile, ""),
    run_mode: safeString(obj.run_mode, ""),

    started_ts: normalizeUnixSeconds(obj.started_ts),
    uptime_s: safeNumber(obj.uptime_s, 0),

    host: safeString(obj.host, ""),
    pid: safeNumber(obj.pid, 0),
  };

  // Clean up empties (keeps logs/UI tidy)
  if (!info.service) delete info.service;
  if (!info.instance_id) delete info.instance_id;
  if (!info.version) delete info.version;
  if (!info.build) delete info.build;
  if (!info.git_sha) delete info.git_sha;

  if (!info.env_profile) delete info.env_profile;
  if (!info.run_mode) delete info.run_mode;

  if (!info.started_ts) delete info.started_ts;
  if (!info.uptime_s) delete info.uptime_s;

  if (!info.host) delete info.host;
  if (!info.pid) delete info.pid;

  // Python info can appear as nested object or flattened fields.
  const py = isRecord(obj.python) ? (obj.python as Record<string, unknown>) : null;
  const pyInfo =
    py || isRecord(obj.py) ? ((obj.py as Record<string, unknown>) ?? {}) : (null as Record<string, unknown> | null);

  const pythonObj = pyInfo && isRecord(pyInfo) ? pyInfo : py;

  if (pythonObj && isRecord(pythonObj)) {
    const python: NonNullable<SystemInfo["python"]> = {};
    const v = safeString(pythonObj.version, "");
    const exe = safeString(pythonObj.executable, "");
    const impl = safeString(pythonObj.implementation, "");
    const plat = safeString(pythonObj.platform, "");

    if (v) python.version = v;
    if (exe) python.executable = exe;
    if (impl) python.implementation = impl;
    if (plat) python.platform = plat;

    if (Object.keys(python).length > 0) info.python = python;
  }

  if (isRecord(obj.meta)) info.meta = obj.meta as Record<string, unknown>;

  return info;
}

function parseHealthCheck(raw: unknown): HealthCheck | null {
  if (!isRecord(raw)) return null;

  const ok = safeBoolean(raw.ok, false);

  const hc: HealthCheck = {
    ok,
  };

  const name = safeString(raw.name, "");
  if (name) hc.name = name;

  const detail = safeString(raw.detail, "");
  if (detail) hc.detail = detail;

  const latency = safeNumber(raw.latency_ms, NaN);
  if (Number.isFinite(latency) && latency >= 0) hc.latency_ms = latency;

  const ts = normalizeUnixSeconds(raw.ts);
  if (ts) hc.ts = ts;

  if (isRecord(raw.meta)) hc.meta = raw.meta as Record<string, unknown>;

  return hc;
}

function parseSystemHealth(raw: unknown): SystemHealth {
  if (!isRecord(raw)) {
    // Some servers return a bare string "ok"
    if (typeof raw === "string") {
      const s = raw.toLowerCase();
      return { ok: s === "ok" || s === "healthy", status: raw };
    }
    return { ok: false };
  }

  // Accept aliases:
  //  - { ok, status, checks: [] }
  //  - { health: { ... } }
  //  - { ok, report: { ... } }
  const report = isRecord(raw.report) ? (raw.report as Record<string, unknown>) : null;
  const obj = isRecord(raw.health) ? (raw.health as Record<string, unknown>) : report ?? raw;

  const ok = safeBoolean(raw.ok, safeBoolean(obj.ok, false));
  const health: SystemHealth = {
    ok,
    status: safeString(raw.status, "") || safeString(obj.status, "") || (ok ? "ok" : ""),
    ts: normalizeUnixSeconds(raw.ts) ?? normalizeUnixSeconds(obj.ts),
  };

  if (!health.status) delete health.status;
  if (!health.ts) delete health.ts;

  const checksRaw = Array.isArray(obj.checks) ? (obj.checks as unknown[]) : [];
  const checks = checksRaw.map(parseHealthCheck).filter((c): c is HealthCheck => c !== null);
  if (checks.length > 0) health.checks = checks;

  const meta: Record<string, unknown> = {};
  if (isRecord(obj.meta)) Object.assign(meta, obj.meta as Record<string, unknown>);
  if (report) {
    for (const [key, value] of Object.entries(report)) {
      if (key === "ok" || key === "status" || key === "ts" || key === "checks" || key === "meta") continue;
      meta[key] = value;
    }
  }
  if (Object.keys(meta).length > 0) health.meta = meta;

  return health;
}

function parseFeatureFlag(raw: unknown): FeatureFlag | null {
  if (!isRecord(raw)) return null;

  // Accept: { key, enabled } or { name, enabled } or { id, enabled }
  const key = safeString(raw.key, "") || safeString(raw.name, "") || safeString(raw.id, "");
  if (!key) return null;

  const enabled = safeBoolean(raw.enabled, false);

  const f: FeatureFlag = { key, enabled };

  const desc = safeString(raw.description, "");
  if (desc) f.description = desc;

  const source = safeString(raw.source, "");
  if (source) f.source = source;

  const ts = normalizeUnixSeconds(raw.ts);
  if (ts) f.ts = ts;

  if (isRecord(raw.meta)) f.meta = raw.meta as Record<string, unknown>;

  return f;
}

function parseFeatureFlagsResponse(raw: unknown): FeatureFlagsResponse {
  if (!isRecord(raw)) return { items: [] };

  // Accept: { items: [...] } or { flags: [...] }
  const arr = Array.isArray(raw.items)
    ? (raw.items as unknown[])
    : Array.isArray(raw.flags)
      ? (raw.flags as unknown[])
      : [];

  const items = arr.map(parseFeatureFlag).filter((x): x is FeatureFlag => x !== null);
  return { items };
}

function parseEffectiveConfigSnapshot(raw: unknown): EffectiveConfigSnapshot {
  if (!isRecord(raw)) return { config: {} };

  // Accept: { config: {...} } or { effective: {...} } or { settings: {...} }
  const cfg =
    (isRecord(raw.config) ? (raw.config as Record<string, unknown>) : null) ??
    (isRecord(raw.effective) ? (raw.effective as Record<string, unknown>) : null) ??
    (isRecord(raw.settings) ? (raw.settings as Record<string, unknown>) : null) ??
    {};

  const snap: EffectiveConfigSnapshot = {
    config: cfg,
    ts: normalizeUnixSeconds(raw.ts),
    env_profile: safeString(raw.env_profile, ""),
    run_mode: safeString(raw.run_mode, ""),
  };

  if (!snap.ts) delete snap.ts;
  if (!snap.env_profile) delete snap.env_profile;
  if (!snap.run_mode) delete snap.run_mode;

  if (isRecord(raw.sources)) snap.sources = raw.sources as Record<string, string>;
  if (isRecord(raw.meta)) snap.meta = raw.meta as Record<string, unknown>;

  return snap;
}

function parseWorldStateMissionSummary(raw: unknown): WorldStateMissionSummary | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id, "").trim();
  if (!id) return null;

  return {
    id,
    status: safeString(raw.status, ""),
    objective: safeString(raw.objective, ""),
    summary: safeString(raw.summary, ""),
    next_step: safeString(raw.next_step, ""),
    requester_id: safeString(raw.requester_id, ""),
    owner_id: safeString(raw.owner_id, ""),
    priority: safeNumber(raw.priority, 0),
    risk_tier: safeString(raw.risk_tier, ""),
    dependency_ids: safeStringArray(raw.dependency_ids),
    dependency_count: safeNumber(raw.dependency_count, 0),
    escalation_path: safeString(raw.escalation_path, ""),
    linked_task_ids: Array.isArray(raw.linked_task_ids)
      ? raw.linked_task_ids.map((taskId) => safeString(taskId, "")).filter(Boolean)
      : [],
    linked_task_count: safeNumber(raw.linked_task_count, 0),
    deadletter_reason: safeString(raw.deadletter_reason, ""),
    last_task_id: safeString(raw.last_task_id, ""),
    last_task_status: safeString(raw.last_task_status, ""),
    last_task_result_status: safeString(raw.last_task_result_status, ""),
    last_task_reason: safeString(raw.last_task_reason, ""),
    last_task_gate: safeString(raw.last_task_gate, ""),
    last_task_next_step: safeString(raw.last_task_next_step, ""),
    last_task_updated_at: safeString(raw.last_task_updated_at, ""),
    created_at: safeString(raw.created_at, ""),
    updated_at: safeString(raw.updated_at, ""),
    terminal: safeBoolean(raw.terminal, false),
    latest_activity: isRecord(raw.latest_activity) ? (raw.latest_activity as Record<string, unknown>) : undefined,
  };
}

function parseWorldStateSnapshot(raw: unknown): WorldStateSnapshot {
  if (!isRecord(raw)) return { ok: false };

  const countsRaw = isRecord(raw.counts) ? (raw.counts as Record<string, unknown>) : {};
  const pathsRaw = isRecord(raw.paths) ? (raw.paths as Record<string, unknown>) : {};
  const overviewRaw = isRecord(raw.overview) ? (raw.overview as Record<string, unknown>) : {};

  const counts: WorldStateCounts = {
    pending_approvals: safeNumber(countsRaw.pending_approvals, 0),
    approved_approvals: safeNumber(countsRaw.approved_approvals, 0),
    rejected_approvals: safeNumber(countsRaw.rejected_approvals, 0),
    tasks: safeNumber(countsRaw.tasks, 0),
    queued_tasks: safeNumber(countsRaw.queued_tasks, 0),
    approval_pending_tasks: safeNumber(countsRaw.approval_pending_tasks, 0),
    blocked_tasks: safeNumber(countsRaw.blocked_tasks, 0),
    running_tasks: safeNumber(countsRaw.running_tasks, 0),
    missions: safeNumber(countsRaw.missions, 0),
    queued_missions: safeNumber(countsRaw.queued_missions, 0),
    active_missions: safeNumber(countsRaw.active_missions, 0),
    blocked_missions: safeNumber(countsRaw.blocked_missions, 0),
    deadlettered_missions: safeNumber(countsRaw.deadlettered_missions, 0),
    active_incidents: safeNumber(countsRaw.active_incidents, 0),
    generated_plugins: safeNumber(countsRaw.generated_plugins, 0),
  };

  const paths: Record<string, WorldStatePathState> = {};
  for (const [key, value] of Object.entries(pathsRaw)) {
    if (!isRecord(value)) continue;
    paths[key] = {
      path: safeString(value.path, ""),
      exists: safeBoolean(value.exists, false),
      is_dir: safeBoolean(value.is_dir, false),
    };
  }

  const approvalsRaw = Array.isArray(overviewRaw.pending_approvals) ? (overviewRaw.pending_approvals as unknown[]) : [];
  const recentTasksRaw = Array.isArray(overviewRaw.recent_tasks) ? (overviewRaw.recent_tasks as unknown[]) : [];
  const recentMissionsRaw = Array.isArray(overviewRaw.recent_missions) ? (overviewRaw.recent_missions as unknown[]) : [];
  const missionQueueRaw = Array.isArray(overviewRaw.mission_queue) ? (overviewRaw.mission_queue as unknown[]) : [];
  const deadletterMissionsRaw = Array.isArray(overviewRaw.deadletter_missions)
    ? (overviewRaw.deadletter_missions as unknown[])
    : [];
  const incidentsRaw = Array.isArray(overviewRaw.incidents) ? (overviewRaw.incidents as unknown[]) : [];
  const taskStatusCountsRaw = isRecord(overviewRaw.task_status_counts)
    ? (overviewRaw.task_status_counts as Record<string, unknown>)
    : {};
  const missionStatusCountsRaw = isRecord(overviewRaw.mission_status_counts)
    ? (overviewRaw.mission_status_counts as Record<string, unknown>)
    : {};

  const overview: WorldStateOverview = {
    pending_approvals: approvalsRaw
      .filter(isRecord)
      .map((item) => ({
        id: safeString(item.id, ""),
        action: safeString(item.action, ""),
        reason: safeString(item.reason, ""),
        status: safeString(item.status, ""),
        ts: normalizeUnixSeconds(item.ts),
        request_kind: safeString(item.request_kind, ""),
        previous_approval_id: safeString(item.previous_approval_id, ""),
        previous_approval_status: safeString(item.previous_approval_status, ""),
        payload_summary: isRecord(item.payload_summary)
          ? parseWorldStateApprovalPayloadSummary(item.payload_summary)
          : undefined,
      }))
      .filter((item) => item.id),
    task_status_counts: Object.fromEntries(
      Object.entries(taskStatusCountsRaw).map(([key, value]) => [key, safeNumber(value, 0)]),
    ),
    recent_tasks: recentTasksRaw
      .filter(isRecord)
      .map((item) => ({
        id: safeString(item.id, ""),
        status: safeString(item.status, ""),
        capability: safeString(item.capability, ""),
        objective: safeString(item.objective, ""),
        requester_id: safeString(item.requester_id, ""),
        assigned_to: safeString(item.assigned_to, ""),
        created_at: safeString(item.created_at, ""),
        updated_at: safeString(item.updated_at, ""),
        status_reason: safeString(item.status_reason, ""),
        terminal: safeBoolean(item.terminal, false),
      }))
      .filter((item) => item.id),
    mission_status_counts: Object.fromEntries(
      Object.entries(missionStatusCountsRaw).map(([key, value]) => [key, safeNumber(value, 0)]),
    ),
    recent_missions: recentMissionsRaw
      .map(parseWorldStateMissionSummary)
      .filter((item): item is WorldStateMissionSummary => item !== null),
    mission_queue: missionQueueRaw
      .filter(isRecord)
      .map((item) => ({
        id: safeString(item.id, ""),
        status: safeString(item.status, ""),
        objective: safeString(item.objective, ""),
        summary: safeString(item.summary, ""),
        next_step: safeString(item.next_step, ""),
        owner_id: safeString(item.owner_id, ""),
        priority: safeNumber(item.priority, 0),
        risk_tier: safeString(item.risk_tier, ""),
        dependency_ids: safeStringArray(item.dependency_ids),
        dependency_count: safeNumber(item.dependency_count, 0),
        dependency_state: parseWorldStateMissionDependencyState(item.dependency_state),
        escalation_path: safeString(item.escalation_path, ""),
        linked_task_count: safeNumber(item.linked_task_count, 0),
        linked_task_ids: Array.isArray(item.linked_task_ids)
          ? item.linked_task_ids.map((taskId) => safeString(taskId, "")).filter(Boolean)
          : [],
        last_task_id: safeString(item.last_task_id, ""),
        last_task_status: safeString(item.last_task_status, ""),
        last_task_result_status: safeString(item.last_task_result_status, ""),
        last_task_gate: safeString(item.last_task_gate, ""),
        last_task_approval_id: safeString(item.last_task_approval_id, ""),
        last_task_previous_approval_id: safeString(item.last_task_previous_approval_id, ""),
        last_task_approval_status: safeString(item.last_task_approval_status, ""),
        recommended_action: safeString(item.recommended_action, ""),
        operator_hint: safeString(item.operator_hint, ""),
        action_target_id: safeString(item.action_target_id, ""),
        advance: parseWorldStateMissionAdvanceProjection(item.advance),
        deadletter_reason: safeString(item.deadletter_reason, ""),
        updated_at: safeString(item.updated_at, ""),
        latest_activity: isRecord(item.latest_activity) ? (item.latest_activity as Record<string, unknown>) : undefined,
      }))
      .filter((item) => item.id),
    deadletter_missions: deadletterMissionsRaw
      .filter(isRecord)
      .map((item) => ({
        id: safeString(item.id, ""),
        status: safeString(item.status, ""),
        objective: safeString(item.objective, ""),
        summary: safeString(item.summary, ""),
        next_step: safeString(item.next_step, ""),
        owner_id: safeString(item.owner_id, ""),
        priority: safeNumber(item.priority, 0),
        risk_tier: safeString(item.risk_tier, ""),
        dependency_ids: safeStringArray(item.dependency_ids),
        dependency_count: safeNumber(item.dependency_count, 0),
        dependency_state: parseWorldStateMissionDependencyState(item.dependency_state),
        escalation_path: safeString(item.escalation_path, ""),
        linked_task_count: safeNumber(item.linked_task_count, 0),
        linked_task_ids: Array.isArray(item.linked_task_ids)
          ? item.linked_task_ids.map((taskId) => safeString(taskId, "")).filter(Boolean)
          : [],
        last_task_id: safeString(item.last_task_id, ""),
        last_task_status: safeString(item.last_task_status, ""),
        last_task_result_status: safeString(item.last_task_result_status, ""),
        last_task_gate: safeString(item.last_task_gate, ""),
        last_task_approval_id: safeString(item.last_task_approval_id, ""),
        last_task_previous_approval_id: safeString(item.last_task_previous_approval_id, ""),
        last_task_approval_status: safeString(item.last_task_approval_status, ""),
        recommended_action: safeString(item.recommended_action, ""),
        operator_hint: safeString(item.operator_hint, ""),
        action_target_id: safeString(item.action_target_id, ""),
        advance: parseWorldStateMissionAdvanceProjection(item.advance),
        deadletter_reason: safeString(item.deadletter_reason, ""),
        updated_at: safeString(item.updated_at, ""),
        latest_activity: isRecord(item.latest_activity) ? (item.latest_activity as Record<string, unknown>) : undefined,
      }))
      .filter((item) => item.id),
    incidents: incidentsRaw
      .map(parseWorldStateIncidentSummary)
      .filter((item): item is WorldStateIncidentSummary => item !== null),
  };

  const snapshot: WorldStateSnapshot = {
    ok: safeBoolean(raw.ok, false),
    subsystem: safeString(raw.subsystem, ""),
    generated_at: safeNumber(raw.generated_at, 0),
    repo_root: safeString(raw.repo_root, ""),
    data_dir: safeString(raw.data_dir, ""),
    counts,
    paths,
    overview,
  };

  if (!snapshot.subsystem) delete snapshot.subsystem;
  if (!snapshot.generated_at) delete snapshot.generated_at;
  if (!snapshot.repo_root) delete snapshot.repo_root;
  if (!snapshot.data_dir) delete snapshot.data_dir;
  if (isRecord(raw.trust)) snapshot.trust = raw.trust as Record<string, unknown>;
  if (isRecord(raw.stack)) snapshot.stack = raw.stack as Record<string, unknown>;
  if (isRecord(raw.services)) snapshot.services = raw.services as Record<string, unknown>;
  if (isRecord(raw.meta)) snapshot.meta = raw.meta as Record<string, unknown>;

  return snapshot;
}

function parseOrbPlaneSummary(raw: unknown): OrbPlaneSummary | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id, "").trim();
  if (!id) return null;

  const plane: OrbPlaneSummary = {
    id,
    name: safeString(raw.name, ""),
    category: safeString(raw.category, ""),
    purpose: safeString(raw.purpose, ""),
    side_effects_allowed: safeBoolean(raw.side_effects_allowed, false),
    default_risk_class: safeString(raw.default_risk_class, ""),
    primary_modules: safeStringArray(raw.primary_modules),
  };

  if (!plane.name) delete plane.name;
  if (!plane.category) delete plane.category;
  if (!plane.purpose) delete plane.purpose;
  if (!plane.default_risk_class) delete plane.default_risk_class;
  if (!plane.primary_modules?.length) delete plane.primary_modules;

  return plane;
}

function parseOrbGateSummary(raw: unknown): OrbGateSummary | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id, "").trim();
  if (!id) return null;
  const gate: OrbGateSummary = {
    id,
    description: safeString(raw.description, ""),
  };
  if (!gate.description) delete gate.description;
  return gate;
}

function parseOrbTransitionSummary(raw: unknown): OrbTransitionSummary | null {
  if (!isRecord(raw)) return null;
  const from = safeString(raw.from, "").trim();
  const to = safeString(raw.to, "").trim();
  if (!from || !to) return null;
  const transition: OrbTransitionSummary = {
    from,
    to,
    conditions: safeStringArray(raw.conditions),
    reason: safeString(raw.reason, ""),
  };
  if (!transition.reason) delete transition.reason;
  return transition;
}

function parseOrbStatusSnapshot(raw: unknown): OrbStatusSnapshot {
  if (!isRecord(raw)) return { ok: false };

  const modelRaw = isRecord(raw.model) ? (raw.model as Record<string, unknown>) : {};
  const transitionsRaw = isRecord(raw.transitions) ? (raw.transitions as Record<string, unknown>) : {};

  const snapshot: OrbStatusSnapshot = {
    ok: safeBoolean(raw.ok, false),
    subsystem: safeString(raw.subsystem, ""),
    generated_at: safeNumber(raw.generated_at, 0),
    repo_root: safeString(raw.repo_root, ""),
    model: {
      plane_map_id: safeString(modelRaw.plane_map_id, ""),
      plane_map_version: safeNumber(modelRaw.plane_map_version, 0),
      action_taxonomy_id: safeString(modelRaw.action_taxonomy_id, ""),
      action_taxonomy_version: safeNumber(modelRaw.action_taxonomy_version, 0),
    },
    core_loop: (Array.isArray(raw.core_loop) ? raw.core_loop : [])
      .map(parseOrbPlaneSummary)
      .filter((item): item is OrbPlaneSummary => item !== null),
    planes: (Array.isArray(raw.planes) ? raw.planes : [])
      .map(parseOrbPlaneSummary)
      .filter((item): item is OrbPlaneSummary => item !== null),
    gates: (Array.isArray(raw.gates) ? raw.gates : [])
      .map(parseOrbGateSummary)
      .filter((item): item is OrbGateSummary => item !== null),
    transitions: {
      allowed: (Array.isArray(transitionsRaw.allowed) ? transitionsRaw.allowed : [])
        .map(parseOrbTransitionSummary)
        .filter((item): item is OrbTransitionSummary => item !== null),
      forbidden: (Array.isArray(transitionsRaw.forbidden) ? transitionsRaw.forbidden : [])
        .map(parseOrbTransitionSummary)
        .filter((item): item is OrbTransitionSummary => item !== null),
    },
    state: isRecord(raw.state) ? (raw.state as Record<string, unknown>) : undefined,
  };

  if (!snapshot.subsystem) delete snapshot.subsystem;
  if (!snapshot.generated_at) delete snapshot.generated_at;
  if (!snapshot.repo_root) delete snapshot.repo_root;
  if (!snapshot.model?.plane_map_id && !snapshot.model?.action_taxonomy_id) delete snapshot.model;
  if (!snapshot.core_loop?.length) delete snapshot.core_loop;
  if (!snapshot.planes?.length) delete snapshot.planes;
  if (!snapshot.gates?.length) delete snapshot.gates;
  if (!snapshot.transitions?.allowed.length && !snapshot.transitions?.forbidden.length) delete snapshot.transitions;
  if (!snapshot.state) delete snapshot.state;
  if (isRecord(raw.meta)) snapshot.meta = raw.meta as Record<string, unknown>;

  return snapshot;
}

function parseOperatorModeSnapshot(raw: unknown): OperatorModeSnapshot {
  if (!isRecord(raw)) return { ok: false };

  const environmentRaw = isRecord(raw.environment) ? (raw.environment as Record<string, unknown>) : {};
  const postureRaw = isRecord(raw.posture) ? (raw.posture as Record<string, unknown>) : {};
  const controlModeRaw = isRecord(raw.control_mode) ? (raw.control_mode as Record<string, unknown>) : {};
  const availableModesRaw = Array.isArray(raw.available_modes) ? raw.available_modes : [];
  const focusRaw = isRecord(raw.focus) ? (raw.focus as Record<string, unknown>) : {};
  const backlogRaw = isRecord(raw.backlog) ? (raw.backlog as Record<string, unknown>) : {};

  const snapshot: OperatorModeSnapshot = {
    ok: safeBoolean(raw.ok, false),
    subsystem: safeString(raw.subsystem, ""),
    generated_at: safeNumber(raw.generated_at, 0),
    environment: {
      id: safeString(environmentRaw.id, ""),
      name: safeString(environmentRaw.name, ""),
      description: safeString(environmentRaw.description, ""),
      label: safeString(environmentRaw.label, ""),
      banner_text: safeString(environmentRaw.banner_text, ""),
      run_mode: safeString(environmentRaw.run_mode, ""),
      runtime_mode: safeString(environmentRaw.runtime_mode, ""),
      profile_path: safeString(environmentRaw.profile_path, ""),
    },
    posture: {
      governance_mode: safeString(postureRaw.governance_mode, ""),
      trust_posture: safeString(postureRaw.trust_posture, ""),
      trust_level: safeNumber(postureRaw.trust_level, 0),
      minimum_operational_trust: safeNumber(postureRaw.minimum_operational_trust, 0),
      web_access: safeString(postureRaw.web_access, ""),
      writes: safeString(postureRaw.writes, ""),
      network_egress: safeString(postureRaw.network_egress, ""),
    },
    control_mode: {
      id: safeString(controlModeRaw.id, ""),
      label: safeString(controlModeRaw.label, ""),
      summary: safeString(controlModeRaw.summary, ""),
      writes: safeString(controlModeRaw.writes, ""),
      implementation_status: safeString(controlModeRaw.implementation_status, ""),
      changed_at: safeNumber(controlModeRaw.changed_at, 0),
      changed_by: safeString(controlModeRaw.changed_by, ""),
      reason: safeString(controlModeRaw.reason, ""),
      source: safeString(controlModeRaw.source, ""),
    },
    available_modes: availableModesRaw
      .filter((item) => isRecord(item))
      .map((item) => {
        const mode = item as Record<string, unknown>;
        return {
          id: safeString(mode.id, ""),
          label: safeString(mode.label, ""),
          summary: safeString(mode.summary, ""),
          implementation_status: safeString(mode.implementation_status, ""),
          active: safeBoolean(mode.active, false),
        };
      })
      .filter((item) => item.id),
    focus: {
      plane_id: safeString(focusRaw.plane_id, ""),
      label: safeString(focusRaw.label, ""),
      reason: safeString(focusRaw.reason, ""),
    },
    backlog: {
      pending_approvals: safeNumber(backlogRaw.pending_approvals, 0),
      approval_pending_tasks: safeNumber(backlogRaw.approval_pending_tasks, 0),
      blocked_tasks: safeNumber(backlogRaw.blocked_tasks, 0),
      queued_tasks: safeNumber(backlogRaw.queued_tasks, 0),
      running_tasks: safeNumber(backlogRaw.running_tasks, 0),
    },
    notes: safeStringArray(raw.notes),
  };

  if (!snapshot.subsystem) delete snapshot.subsystem;
  if (!snapshot.generated_at) delete snapshot.generated_at;
  if (!snapshot.environment?.id) delete snapshot.environment;
  if (!snapshot.control_mode?.id) delete snapshot.control_mode;
  if (!snapshot.available_modes?.length) delete snapshot.available_modes;
  if (!snapshot.focus?.plane_id) delete snapshot.focus;
  if (isRecord(raw.meta)) snapshot.meta = raw.meta as Record<string, unknown>;

  return snapshot;
}

function parseNumberMap(raw: unknown): Record<string, number> {
  if (!isRecord(raw)) return {};
  const out: Record<string, number> = {};
  for (const [key, value] of Object.entries(raw)) {
    out[key] = safeNumber(value, 0);
  }
  return out;
}

function parseWorldStateMissionAdvanceProjection(raw: unknown): WorldStateMissionAdvanceProjection | undefined {
  if (!isRecord(raw)) return undefined;
  const projection: WorldStateMissionAdvanceProjection = {
    eligible: safeBoolean(raw["eligible"], false),
    action: safeString(raw["action"], ""),
    target_id: safeString(raw["target_id"], ""),
    reason: safeString(raw["reason"], ""),
  };
  if (!projection.eligible && !projection.action && !projection.target_id && !projection.reason) return undefined;
  return projection;
}

function parseContinuityFocusItem(raw: unknown): ContinuityBriefingFocusItem | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw["id"], "").trim();
  if (!id) return null;

  const item: ContinuityBriefingFocusItem = {
    id,
    status: safeString(raw["status"], ""),
    objective: safeString(raw["objective"], ""),
    summary: safeString(raw["summary"], ""),
    next_step: safeString(raw["next_step"], ""),
    priority: safeNumber(raw["priority"], 0),
    risk_tier: safeString(raw["risk_tier"], ""),
    dependency_ids: safeStringArray(raw["dependency_ids"]),
    dependency_count: safeNumber(raw["dependency_count"], 0),
    dependency_state: parseWorldStateMissionDependencyState(raw["dependency_state"]),
    escalation_path: safeString(raw["escalation_path"], ""),
    linked_task_count: safeNumber(raw["linked_task_count"], 0),
    recommended_action: safeString(raw["recommended_action"], ""),
    operator_hint: safeString(raw["operator_hint"], ""),
    action_target_id: safeString(raw["action_target_id"], ""),
    advance: parseWorldStateMissionAdvanceProjection(raw["advance"]),
    last_task_id: safeString(raw["last_task_id"], ""),
    last_task_status: safeString(raw["last_task_status"], ""),
    last_task_result_status: safeString(raw["last_task_result_status"], ""),
    last_task_gate: safeString(raw["last_task_gate"], ""),
    last_task_approval_id: safeString(raw["last_task_approval_id"], ""),
    last_task_previous_approval_id: safeString(raw["last_task_previous_approval_id"], ""),
    last_task_approval_status: safeString(raw["last_task_approval_status"], ""),
    last_advance_action: safeString(raw["last_advance_action"], ""),
    last_advance_outcome: safeString(raw["last_advance_outcome"], ""),
    last_advance_operation_id: safeString(raw["last_advance_operation_id"], ""),
    last_advance_operation_status: safeString(raw["last_advance_operation_status"], ""),
    last_advance_message: safeString(raw["last_advance_message"], ""),
    last_advance_actor: safeString(raw["last_advance_actor"], ""),
    last_advance_applied: safeBoolean(raw["last_advance_applied"], false),
    last_advance_at: safeString(raw["last_advance_at"], ""),
    deadletter_reason: safeString(raw["deadletter_reason"], ""),
    updated_at: safeString(raw["updated_at"], ""),
    latest_activity: isRecord(raw["latest_activity"]) ? (raw["latest_activity"] as Record<string, unknown>) : undefined,
  };

  return item;
}

function parseContinuityCompletedItem(raw: unknown): ContinuityBriefingCompletedItem | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw["id"], "").trim();
  if (!id) return null;

  return {
    id,
    objective: safeString(raw["objective"], ""),
    updated_at: safeString(raw["updated_at"], ""),
    last_task_id: safeString(raw["last_task_id"], ""),
    last_advance_action: safeString(raw["last_advance_action"], ""),
    last_advance_outcome: safeString(raw["last_advance_outcome"], ""),
    latest_activity: isRecord(raw["latest_activity"]) ? (raw["latest_activity"] as Record<string, unknown>) : undefined,
  };
}

function parseContinuityDeadletterItem(raw: unknown): ContinuityBriefingDeadletterItem | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw["id"], "").trim();
  if (!id) return null;

  return {
    id,
    objective: safeString(raw["objective"], ""),
    reason: safeString(raw["reason"], ""),
    recommended_action: safeString(raw["recommended_action"], ""),
    updated_at: safeString(raw["updated_at"], ""),
    latest_activity: isRecord(raw["latest_activity"]) ? (raw["latest_activity"] as Record<string, unknown>) : undefined,
  };
}

function parseWorldStateIncidentSummary(raw: unknown): WorldStateIncidentSummary | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw["id"], "").trim();
  if (!id) return null;

  const evidenceRaw = Array.isArray(raw["evidence"]) ? raw["evidence"] : [];
  const evidence = evidenceRaw
    .filter(isRecord)
    .map((item) => ({
      kind: safeString(item["kind"], ""),
      id: safeString(item["id"], ""),
      label: safeString(item["label"], ""),
      status: safeString(item["status"], ""),
      detail: safeString(item["detail"], ""),
      path: safeString(item["path"], ""),
      ts: safeNumber(item["ts"], 0),
    }))
    .filter((item) => Boolean(item.kind || item.id || item.label || item.status || item.detail || item.path || item.ts));

  const summary: WorldStateIncidentSummary = {
    id,
    severity: safeString(raw["severity"], ""),
    category: safeString(raw["category"], ""),
    status: safeString(raw["status"], ""),
    title: safeString(raw["title"], ""),
    detail: safeString(raw["detail"], ""),
    source: safeString(raw["source"], ""),
    count: safeNumber(raw["count"], 0),
    approval_id: safeString(raw["approval_id"], ""),
    task_id: safeString(raw["task_id"], ""),
    probe: safeString(raw["probe"], ""),
    observed_at: safeNumber(raw["observed_at"], 0),
    evidence,
  };

  if (!summary.observed_at) delete summary.observed_at;
  if (!summary.evidence?.length) delete summary.evidence;

  return summary;
}

function parseObserverScanReceiptSummary(raw: unknown): ObserverScanReceiptSummary | null {
  if (!isRecord(raw)) return null;

  const receiptId = safeString(raw["receipt_id"], "").trim();
  const headline = safeString(raw["headline"], "").trim();
  if (!receiptId && !headline) return null;

  const summary: ObserverScanReceiptSummary = {
    ts: safeNumber(raw["ts"], 0),
    receipt_id: receiptId,
    event: safeString(raw["event"], ""),
    status: safeString(raw["status"], ""),
    decision: safeString(raw["decision"], ""),
    headline,
    incident_count: safeNumber(raw["incident_count"], 0),
    counts: parseNumberMap(raw["counts"]),
    incident_ids: (Array.isArray(raw["incident_ids"]) ? raw["incident_ids"] : [])
      .map((item) => safeString(item, "").trim())
      .filter(Boolean),
    probes: (Array.isArray(raw["probes"]) ? raw["probes"] : [])
      .map((item) => safeString(item, "").trim())
      .filter(Boolean),
    focus: (Array.isArray(raw["focus"]) ? raw["focus"] : [])
      .map(parseWorldStateIncidentSummary)
      .filter((item): item is WorldStateIncidentSummary => item !== null),
    probe_statuses: (Array.isArray(raw["probe_statuses"]) ? raw["probe_statuses"] : [])
      .map(parseObserverProbeSummary)
      .filter((item): item is ObserverProbeSummary => item !== null),
    anomaly: parseObserverAnomalySummary(raw["anomaly"]),
    generated_at: safeNumber(raw["generated_at"], 0),
    reason: safeString(raw["reason"], ""),
    actor: safeString(raw["actor"], ""),
    trace_id: safeString(raw["trace_id"], ""),
    run_id: safeString(raw["run_id"], ""),
  };

  if (!summary.ts) delete summary.ts;
  if (!summary.counts || Object.keys(summary.counts).length === 0) delete summary.counts;
  if (!summary.incident_ids?.length) delete summary.incident_ids;
  if (!summary.probes?.length) delete summary.probes;
  if (!summary.focus?.length) delete summary.focus;
  if (!summary.probe_statuses?.length) delete summary.probe_statuses;
  if (!summary.generated_at) delete summary.generated_at;
  if (!summary.event) delete summary.event;
  if (!summary.status) delete summary.status;
  if (!summary.decision) delete summary.decision;
  if (!summary.reason) delete summary.reason;
  if (!summary.actor) delete summary.actor;
  if (!summary.trace_id) delete summary.trace_id;
  if (!summary.run_id) delete summary.run_id;

  return summary;
}

function parseObserverReadinessCriterion(raw: unknown): ObserverReadinessCriterion | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw["id"], "").trim();
  const label = safeString(raw["label"], "").trim();
  if (!id && !label) return null;

  const criterion: ObserverReadinessCriterion = {
    id,
    label,
    status: safeString(raw["status"], "").trim(),
    detail: safeString(raw["detail"], "").trim(),
    evidence: isRecord(raw["evidence"]) ? (raw["evidence"] as Record<string, unknown>) : undefined,
  };

  if (!criterion.id) delete criterion.id;
  if (!criterion.label) delete criterion.label;
  if (!criterion.status) delete criterion.status;
  if (!criterion.detail) delete criterion.detail;
  if (!criterion.evidence) delete criterion.evidence;

  return criterion;
}

function parseObserverReadinessSummary(raw: unknown): ObserverReadinessSummary | undefined {
  if (!isRecord(raw)) return undefined;

  const criteria = (Array.isArray(raw["criteria"]) ? raw["criteria"] : [])
    .map(parseObserverReadinessCriterion)
    .filter((item): item is ObserverReadinessCriterion => item !== null);
  const satisfied = safeNumber(raw["satisfied"], Number.NaN);
  const total = safeNumber(raw["total"], Number.NaN);
  const summary: ObserverReadinessSummary = {
    stage: safeString(raw["stage"], "").trim(),
    status: safeString(raw["status"], "").trim(),
    criteria,
    satisfied,
    total,
    next_action: safeString(raw["next_action"], "").trim(),
  };

  if (!summary.stage) delete summary.stage;
  if (!summary.status) delete summary.status;
  if (!summary.criteria?.length) delete summary.criteria;
  if (!Number.isFinite(satisfied)) delete summary.satisfied;
  if (!Number.isFinite(total)) delete summary.total;
  if (!summary.next_action) delete summary.next_action;

  return summary.status || summary.criteria?.length ? summary : undefined;
}

function parseObserverAnomalySummary(raw: unknown): ObserverAnomalySummary | undefined {
  if (!isRecord(raw)) return undefined;

  const score = safeNumber(raw["score"], 0);
  const level = safeString(raw["level"], "").trim();
  const reasons = (Array.isArray(raw["reasons"]) ? raw["reasons"] : [])
    .map((item) => safeString(item, "").trim())
    .filter(Boolean);

  if (!score && !level && reasons.length === 0) return undefined;

  const summary: ObserverAnomalySummary = {
    score,
    level,
    reasons,
  };

  if (!summary.score) delete summary.score;
  if (!summary.level) delete summary.level;
  if (!summary.reasons?.length) delete summary.reasons;

  return summary;
}

function parseObserverProbeSummary(raw: unknown): ObserverProbeSummary | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw["id"], "").trim();
  const headline = safeString(raw["headline"], "").trim();
  if (!id && !headline) return null;

  const summary: ObserverProbeSummary = {
    id,
    status: safeString(raw["status"], ""),
    severity: safeString(raw["severity"], ""),
    headline,
    detail: safeString(raw["detail"], ""),
    incident_count: safeNumber(raw["incident_count"], 0),
    observed_at: safeNumber(raw["observed_at"], 0),
  };

  if (!summary.id) delete summary.id;
  if (!summary.status) delete summary.status;
  if (!summary.severity) delete summary.severity;
  if (!summary.detail) delete summary.detail;
  if (!summary.incident_count) delete summary.incident_count;
  if (!summary.observed_at) delete summary.observed_at;

  return summary;
}

function parseContinuityLedgerEntry(raw: unknown): ContinuityLedgerEntry | null {
  if (!isRecord(raw)) return null;

  const role = safeString(raw["role"], "").trim();
  const content = safeString(raw["content"], "");
  if (!role && !content.trim()) return null;

  const entry: ContinuityLedgerEntry = {
    ts: normalizeUnixSeconds(raw["ts"]),
    role: role || "unknown",
    content,
    meta: isRecord(raw["meta"]) ? (raw["meta"] as Record<string, unknown>) : undefined,
  };

  if (!entry.ts) delete entry.ts;
  if (!entry.meta) delete entry.meta;

  return entry;
}

function parseContinuityLedgerSnapshot(raw: unknown): ContinuityLedgerSnapshot {
  if (!isRecord(raw)) return { entries: [] };

  const snapshot: ContinuityLedgerSnapshot = {
    entries: (Array.isArray(raw["entries"]) ? raw["entries"] : [])
      .map(parseContinuityLedgerEntry)
      .filter((item): item is ContinuityLedgerEntry => item !== null),
    error: safeString(raw["error"], ""),
  };

  if (!snapshot.error) delete snapshot.error;

  return snapshot;
}

function parseObserverEventsSnapshot(raw: unknown): ObserverEventsSnapshot {
  if (!isRecord(raw)) return { ok: false, items: [] };

  const sourceItems = Array.isArray(raw["items"])
    ? raw["items"]
    : Array.isArray(raw["history"])
      ? raw["history"]
      : [];

  const snapshot: ObserverEventsSnapshot = {
    ok: safeBoolean(raw["ok"], false),
    subsystem: safeString(raw["subsystem"], ""),
    items: sourceItems
      .map(parseObserverScanReceiptSummary)
      .filter((item): item is ObserverScanReceiptSummary => item !== null),
    total: safeNumber(raw["total"], 0),
    limit: safeNumber(raw["limit"], 0),
    error: safeString(raw["error"], ""),
  };

  if (!snapshot.subsystem) delete snapshot.subsystem;
  if (!snapshot.total) delete snapshot.total;
  if (!snapshot.limit) delete snapshot.limit;
  if (!snapshot.error) delete snapshot.error;

  return snapshot;
}

function parseContinuityOperatorSurface(raw: unknown): ContinuityOperatorSurface | undefined {
  if (!isRecord(raw)) return undefined;

  const controlModeRaw = isRecord(raw["control_mode"]) ? (raw["control_mode"] as Record<string, unknown>) : {};
  const focusRaw = isRecord(raw["focus"]) ? (raw["focus"] as Record<string, unknown>) : {};
  const postureRaw = isRecord(raw["posture"]) ? (raw["posture"] as Record<string, unknown>) : {};

  const surface: ContinuityOperatorSurface = {
    available: safeBoolean(raw["available"], false),
    error: safeString(raw["error"], ""),
    control_mode: {
      id: safeString(controlModeRaw["id"], ""),
      label: safeString(controlModeRaw["label"], ""),
      summary: safeString(controlModeRaw["summary"], ""),
      writes: safeString(controlModeRaw["writes"], ""),
      implementation_status: safeString(controlModeRaw["implementation_status"], ""),
      changed_at: safeNumber(controlModeRaw["changed_at"], 0),
      changed_by: safeString(controlModeRaw["changed_by"], ""),
      reason: safeString(controlModeRaw["reason"], ""),
      source: safeString(controlModeRaw["source"], ""),
    },
    focus: {
      plane_id: safeString(focusRaw["plane_id"], ""),
      label: safeString(focusRaw["label"], ""),
      reason: safeString(focusRaw["reason"], ""),
    },
    posture: {
      governance_mode: safeString(postureRaw["governance_mode"], ""),
      trust_posture: safeString(postureRaw["trust_posture"], ""),
      trust_level: safeNumber(postureRaw["trust_level"], 0),
      minimum_operational_trust: safeNumber(postureRaw["minimum_operational_trust"], 0),
      web_access: safeString(postureRaw["web_access"], ""),
      writes: safeString(postureRaw["writes"], ""),
      network_egress: safeString(postureRaw["network_egress"], ""),
    },
  };

  if (!surface.error) delete surface.error;
  if (!surface.control_mode?.id) delete surface.control_mode;
  if (!surface.focus?.plane_id) delete surface.focus;
  if (Object.keys(postureRaw).length === 0) {
    delete surface.posture;
  }

  return surface;
}

function parseContinuityOrbSurface(raw: unknown): ContinuityOrbSurface | undefined {
  if (!isRecord(raw)) return undefined;

  const surface: ContinuityOrbSurface = {
    available: safeBoolean(raw["available"], false),
    error: safeString(raw["error"], ""),
    state: isRecord(raw["state"]) ? (raw["state"] as Record<string, unknown>) : undefined,
  };

  if (!surface.error) delete surface.error;
  if (!surface.state) delete surface.state;

  return surface;
}

function parseContinuityBriefingSnapshot(raw: unknown): ContinuityBriefingSnapshot {
  if (!isRecord(raw)) return { ok: false };

  const briefingRaw = isRecord(raw["briefing"]) ? (raw["briefing"] as Record<string, unknown>) : {};

  const snapshot: ContinuityBriefingSnapshot = {
    ok: safeBoolean(raw["ok"], false),
    subsystem: safeString(raw["subsystem"], ""),
    generated_at: safeNumber(raw["generated_at"], 0),
    briefing: {
      headline: safeString(briefingRaw["headline"], ""),
      counts: parseNumberMap(briefingRaw["counts"]),
      focus: (Array.isArray(briefingRaw["focus"]) ? briefingRaw["focus"] : [])
        .map(parseContinuityFocusItem)
        .filter((item): item is ContinuityBriefingFocusItem => item !== null),
      recently_completed: (Array.isArray(briefingRaw["recently_completed"]) ? briefingRaw["recently_completed"] : [])
        .map(parseContinuityCompletedItem)
        .filter((item): item is ContinuityBriefingCompletedItem => item !== null),
      deadletter_preview: (Array.isArray(briefingRaw["deadletter_preview"]) ? briefingRaw["deadletter_preview"] : [])
        .map(parseContinuityDeadletterItem)
        .filter((item): item is ContinuityBriefingDeadletterItem => item !== null),
      readiness: parseObserverReadinessSummary(briefingRaw["readiness"]),
      observer: isRecord(briefingRaw["observer"])
        ? {
            headline: safeString((briefingRaw["observer"] as Record<string, unknown>)["headline"], ""),
            counts: parseNumberMap((briefingRaw["observer"] as Record<string, unknown>)["counts"]),
            focus: (
              Array.isArray((briefingRaw["observer"] as Record<string, unknown>)["focus"])
                ? ((briefingRaw["observer"] as Record<string, unknown>)["focus"] as unknown[])
                : []
            )
              .map(parseWorldStateIncidentSummary)
              .filter((item): item is WorldStateIncidentSummary => item !== null),
            probes: (
              Array.isArray((briefingRaw["observer"] as Record<string, unknown>)["probes"])
                ? ((briefingRaw["observer"] as Record<string, unknown>)["probes"] as unknown[])
                : []
            )
              .map(parseObserverProbeSummary)
              .filter((item): item is ObserverProbeSummary => item !== null),
            recent_scans: (
              Array.isArray((briefingRaw["observer"] as Record<string, unknown>)["recent_scans"])
                ? ((briefingRaw["observer"] as Record<string, unknown>)["recent_scans"] as unknown[])
                : []
            )
              .map(parseObserverScanReceiptSummary)
              .filter((item): item is ObserverScanReceiptSummary => item !== null),
            anomaly: parseObserverAnomalySummary((briefingRaw["observer"] as Record<string, unknown>)["anomaly"]),
            readiness: parseObserverReadinessSummary((briefingRaw["observer"] as Record<string, unknown>)["readiness"]),
            observed_at: safeNumber((briefingRaw["observer"] as Record<string, unknown>)["observed_at"], 0),
            error: safeString((briefingRaw["observer"] as Record<string, unknown>)["error"], ""),
          }
        : undefined,
    },
    mission_status_counts: parseNumberMap(raw["mission_status_counts"]),
    recent_missions: (Array.isArray(raw["recent_missions"]) ? raw["recent_missions"] : [])
      .map(parseWorldStateMissionSummary)
      .filter((item): item is WorldStateMissionSummary => item !== null),
    operator: parseContinuityOperatorSurface(raw["operator"]),
    orb: parseContinuityOrbSurface(raw["orb"]),
  };

  if (!snapshot.subsystem) delete snapshot.subsystem;
  if (!snapshot.generated_at) delete snapshot.generated_at;
  const hasBriefingContent =
    Boolean(snapshot.briefing?.headline) ||
    Boolean(snapshot.briefing?.focus?.length) ||
    Boolean(snapshot.briefing?.counts && Object.keys(snapshot.briefing.counts).length > 0) ||
    Boolean(snapshot.briefing?.recently_completed?.length) ||
    Boolean(snapshot.briefing?.deadletter_preview?.length) ||
    Boolean(snapshot.briefing?.readiness?.status) ||
    Boolean(snapshot.briefing?.observer?.headline) ||
    Boolean(snapshot.briefing?.observer?.focus?.length) ||
    Boolean(snapshot.briefing?.observer?.probes?.length) ||
    Boolean(snapshot.briefing?.observer?.anomaly?.score) ||
    Boolean(snapshot.briefing?.observer?.anomaly?.level) ||
    Boolean(snapshot.briefing?.observer?.readiness?.status) ||
    Boolean(snapshot.briefing?.observer?.recent_scans?.length);
  if (!hasBriefingContent) delete snapshot.briefing;
  if (!snapshot.mission_status_counts || Object.keys(snapshot.mission_status_counts).length === 0) {
    delete snapshot.mission_status_counts;
  }
  if (!snapshot.recent_missions?.length) delete snapshot.recent_missions;
  if (!snapshot.operator) delete snapshot.operator;
  if (!snapshot.orb) delete snapshot.orb;
  if (isRecord(raw["meta"])) snapshot.meta = raw["meta"] as Record<string, unknown>;

  return snapshot;
}

export type SettingsEndpoints = {
  /**
   * Each endpoint returns a *priority-ordered* list of candidate paths.
   * The client probes in order and tolerates 404/405 to allow route evolution.
   */
  info: () => string[];
  health: () => string[];
  worldState: () => string[];
  continuityLedger: () => string[];
  continuityBriefing: () => string[];
  observerEvents: () => string[];
  orbStatus: () => string[];
  operatorMode: () => string[];
  setOperatorMode: () => string[];
  observerScan: () => string[];
  featureFlags: () => string[];
  effectiveConfig: () => string[];

  /**
   * Mutations (opt-in).
   * If your backend doesn’t support mutations, leave defaults and keep mutationsDisabled.
   */
  mutateConfig: () => string[];
  setFeatureFlag: (key: string) => string[];
};

export function defaultSettingsEndpoints(): SettingsEndpoints {
  return {
    // Common candidates across FastAPI-style systems.
    info: () => ["/system/info", "/system/status", "/system", "/status"],
    health: () => ["/system/health", "/health", "/system/ping", "/ping"],
    worldState: () => ["/system/world_state", "/system/world-state"],
    continuityLedger: () => ["/continuity/ledger"],
    continuityBriefing: () => ["/continuity/briefing", "/continuity/shift_briefing", "/continuity/shift-briefing"],
    observerEvents: () => ["/system/observer/events", "/system/observer/log", "/system/observer/audit"],
    orbStatus: () => ["/system/orb_status", "/system/orb-status", "/system/orb"],
    operatorMode: () => ["/system/operator_mode", "/system/operator-mode"],
    setOperatorMode: () => ["/system/operator_mode", "/system/operator-mode"],
    observerScan: () => ["/system/observer/scan"],
    featureFlags: () => ["/system/flags", "/system/feature_flags", "/system/features", "/flags"],
    effectiveConfig: () => ["/system/config/effective", "/system/effective_config", "/system/config", "/config/effective"],

    mutateConfig: () => ["/system/config/mutate", "/system/config/patch", "/system/settings/mutate", "/system/settings"],
    setFeatureFlag: (key: string) => [
      `/system/flags/${encodeURIComponent(key)}`,
      `/system/feature_flags/${encodeURIComponent(key)}`,
      "/system/flags/set",
      "/system/feature_flags/set",
    ],
  };
}

export type SettingsClientOptions = {
  endpoints?: SettingsEndpoints;

  /**
   * Default timeout applied when per-call timeoutMs is not provided.
   */
  defaultTimeoutMs?: number;

  /**
   * Enable mutation methods. Defaults to false for safety.
   * Backend still must enforce approvals/policies.
   */
  mutationsEnabled?: boolean;

  /**
   * Optional bearer token supplier (caller-owned).
   */
  bearerTokenProvider?: () => string | null;

  /**
   * Extra headers (caller-owned).
   */
  headersExtra?: Record<string, string>;
};

export class SettingsClient {
  readonly baseUrl: string;
  readonly endpoints: SettingsEndpoints;
  readonly defaultTimeoutMs: number;
  readonly mutationsEnabled: boolean;

  private readonly bearerTokenProvider?: () => string | null;
  private readonly headersExtra?: Record<string, string>;

  constructor(baseUrl: string, opts?: SettingsClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("SettingsClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultSettingsEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
    this.mutationsEnabled = Boolean(opts?.mutationsEnabled ?? false);

    this.bearerTokenProvider = opts?.bearerTokenProvider;
    this.headersExtra = opts?.headersExtra;
  }

  private url(path: string): string {
    if (!path.startsWith("/")) path = `/${path}`;
    return `${this.baseUrl}${path}`;
  }

  private init(opts?: { signal?: AbortSignal; timeoutMs?: number }): TimeoutFetchInit {
    return {
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
      bearerToken: this.bearerTokenProvider?.() ?? null,
      headersExtra: this.headersExtra,
    };
  }

  private async fetchFirstOk(
    paths: string[],
    init: TimeoutFetchInit,
  ): Promise<{ url: string; json: unknown; res: Response }> {
    let lastErr: unknown = null;

    for (const p of paths) {
      const url = this.url(p);
      try {
        const { res, json } = await fetchJson(url, init);
        return { url, json, res };
      } catch (err) {
        lastErr = err;

        // If the route isn't found (or method not allowed), try next candidate.
        if (err instanceof SettingsApiError) {
          if (err.status === 404 || err.status === 405) continue;
        }

        // Otherwise fail fast: auth errors, 500s, network errors should surface.
        throw err;
      }
    }

    // No candidates worked.
    if (lastErr instanceof Error) throw lastErr;
    throw new Error("No settings endpoints responded successfully");
  }

  async getSystemInfo(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<SystemInfo> {
    const { json } = await this.fetchFirstOk(this.endpoints.info(), this.init(opts));
    return parseSystemInfo(json);
  }

  async getHealth(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<SystemHealth> {
    const { json } = await this.fetchFirstOk(this.endpoints.health(), this.init(opts));
    return parseSystemHealth(json);
  }

  async getWorldState(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<WorldStateSnapshot> {
    const { json } = await this.fetchFirstOk(this.endpoints.worldState(), this.init(opts));
    return parseWorldStateSnapshot(json);
  }

  async getContinuityLedger(opts?: {
    limit?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<ContinuityLedgerSnapshot> {
    const safeLimit = Math.max(1, Math.min(Math.floor(opts?.limit ?? 20), 500));
    const paths = this.endpoints.continuityLedger().map((path) => `${path}${buildQuery({ limit: safeLimit })}`);
    const { json } = await this.fetchFirstOk(paths, this.init(opts));
    return parseContinuityLedgerSnapshot(json);
  }

  async getContinuityBriefing(opts?: {
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<ContinuityBriefingSnapshot> {
    const { json } = await this.fetchFirstOk(this.endpoints.continuityBriefing(), this.init(opts));
    return parseContinuityBriefingSnapshot(json);
  }

  async getObserverEvents(opts?: {
    limit?: number;
    status?: string;
    decision?: string;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<ObserverEventsSnapshot> {
    const safeLimit = Math.max(1, Math.min(Math.floor(opts?.limit ?? 20), 100));
    const query = buildQuery({
      limit: safeLimit,
      status: safeString(opts?.status, "").trim() || undefined,
      decision: safeString(opts?.decision, "").trim() || undefined,
    });
    const paths = this.endpoints.observerEvents().map((path) => `${path}${query}`);
    const { json } = await this.fetchFirstOk(paths, this.init(opts));
    return parseObserverEventsSnapshot(json);
  }

  async getOrbStatus(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<OrbStatusSnapshot> {
    const { json } = await this.fetchFirstOk(this.endpoints.orbStatus(), this.init(opts));
    return parseOrbStatusSnapshot(json);
  }

  async getOperatorMode(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<OperatorModeSnapshot> {
    const { json } = await this.fetchFirstOk(this.endpoints.operatorMode(), this.init(opts));
    return parseOperatorModeSnapshot(json);
  }

  async setOperatorMode(
    req: OperatorModeMutationRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OperatorModeMutationResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("SettingsClient.setOperatorMode is disabled (mutationsEnabled=false).");
    }

    const { json } = await this.fetchFirstOk(this.endpoints.setOperatorMode(), {
      ...this.init(opts),
      method: "POST",
      body: JSON.stringify(req),
    });

    if (!isRecord(json)) return { ok: false };
    return {
      ok: safeBoolean(json.ok, false),
      applied: safeBoolean(json.applied, false),
      status: safeString(json.status, ""),
      message: safeString(json.message, ""),
      snapshot: parseOperatorModeSnapshot(json),
    };
  }

  async recordObserverScan(
    req: ObserverScanRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<ObserverScanResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("SettingsClient.recordObserverScan is disabled (mutationsEnabled=false).");
    }

    const { json } = await this.fetchFirstOk(this.endpoints.observerScan(), {
      ...this.init(opts),
      method: "POST",
      body: JSON.stringify(req),
    });

    if (!isRecord(json)) return { ok: false };
    const response: ObserverScanResponse = {
      ok: safeBoolean(json.ok, false),
      subsystem: safeString(json.subsystem, ""),
      headline: safeString(json.headline, ""),
      decision: safeString(json.decision, ""),
      observed_at: safeNumber(json.observed_at, 0),
      counts: parseNumberMap(json.counts),
      anomaly: parseObserverAnomalySummary(json.anomaly),
      receipt: parseObserverScanReceiptSummary(json.receipt),
      readiness: parseObserverReadinessSummary(json.readiness),
    };
    if (!response.observed_at) delete response.observed_at;
    return response;
  }

  async listFeatureFlags(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<FeatureFlagsResponse> {
    const { json } = await this.fetchFirstOk(this.endpoints.featureFlags(), this.init(opts));
    return parseFeatureFlagsResponse(json);
  }

  async getEffectiveConfig(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<EffectiveConfigSnapshot> {
    const { json } = await this.fetchFirstOk(this.endpoints.effectiveConfig(), this.init(opts));
    return parseEffectiveConfigSnapshot(json);
  }

  async mutateConfig(
    req: ConfigMutationRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<ConfigMutationResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("SettingsClient.mutateConfig is disabled (mutationsEnabled=false).");
    }

    const { json } = await this.fetchFirstOk(this.endpoints.mutateConfig(), {
      ...this.init(opts),
      method: "POST",
      body: JSON.stringify(req),
    });

    if (!isRecord(json)) return { ok: true };
    return {
      ok: safeBoolean(json.ok, true),
      approval_id: safeString(json.approval_id, ""),
      status: safeString(json.status, ""),
      applied: safeBoolean(json.applied, false),
      resulting_value: (json as Record<string, unknown>).resulting_value,
      message: safeString(json.message, ""),
      meta: isRecord(json.meta) ? (json.meta as Record<string, unknown>) : undefined,
    };
  }

  async setFeatureFlag(
    key: string,
    enabled: boolean,
    opts?: { reason?: string; signal?: AbortSignal; timeoutMs?: number },
  ): Promise<ConfigMutationResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("SettingsClient.setFeatureFlag is disabled (mutationsEnabled=false).");
    }

    const cleanedKey = (key || "").trim();
    if (!cleanedKey) throw new Error("setFeatureFlag requires a non-empty key");

    // Strategy:
    //  - Try REST-ish endpoints first: POST /system/flags/<key> with body { enabled, reason }
    //  - Fall back to generic setter endpoints: POST /system/flags/set with body { key, enabled, reason }
    const candidates = this.endpoints.setFeatureFlag(cleanedKey);

    const primaryPayload = { enabled, reason: (opts?.reason || "").trim() || undefined };
    const fallbackPayload = { key: cleanedKey, enabled, reason: (opts?.reason || "").trim() || undefined };

    let lastErr: unknown = null;

    for (const path of candidates) {
      const isGenericSetter = path.endsWith("/set");
      const body = JSON.stringify(isGenericSetter ? fallbackPayload : primaryPayload);

      try {
        const { json } = await this.fetchFirstOk([path], {
          ...this.init(opts),
          method: "POST",
          body,
        });

        if (!isRecord(json)) return { ok: true };

        return {
          ok: safeBoolean(json.ok, true),
          approval_id: safeString(json.approval_id, ""),
          status: safeString(json.status, ""),
          applied: safeBoolean(json.applied, false),
          resulting_value: (json as Record<string, unknown>).resulting_value,
          message: safeString(json.message, ""),
          meta: isRecord(json.meta) ? (json.meta as Record<string, unknown>) : undefined,
        };
      } catch (err) {
        lastErr = err;

        // Route mismatch? try next.
        if (err instanceof SettingsApiError && (err.status === 404 || err.status === 405)) continue;

        throw err;
      }
    }

    if (lastErr instanceof Error) throw lastErr;
    throw new Error("No feature flag endpoints responded successfully");
  }
}

/* -------------------------------------------------------------------------------------------------
 * UI Preferences (local)
 * ------------------------------------------------------------------------------------------------- */

export type UiTheme = "system" | "dark" | "light";
export type UiDensity = "comfortable" | "compact";

export type UiPreferencesV1 = {
  version: 1;

  theme: UiTheme;
  density: UiDensity;

  /**
   * If true, the UI can show more "operator-grade" toggles and diagnostics.
   * This is a UI-only preference (NOT a permission model).
   */
  show_advanced: boolean;

  /**
   * Refresh cadence hints (UI-only). Modules can read and decide what to do.
   */
  refresh: {
    approvals_ms: number; // 0 disables auto-refresh
    ledger_ms: number; // 0 disables auto-refresh
    health_ms: number; // 0 disables auto-refresh
  };

  /**
   * Last update for local auditing/debug.
   */
  updated_ts?: UnixSeconds;

  /**
   * Forward-compatible metadata.
   */
  meta?: Record<string, unknown>;
};

export type UiPreferences = UiPreferencesV1;

export const DEFAULT_UI_PREFERENCES: UiPreferences = {
  version: 1,
  theme: "system",
  density: "comfortable",
  show_advanced: false,
  refresh: {
    approvals_ms: 0,
    ledger_ms: 0,
    health_ms: 10_000,
  },
  updated_ts: Math.floor(Date.now() / 1000),
};

function hasStorage(): boolean {
  try {
    return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
  } catch {
    return false;
  }
}

function parseUiPreferences(raw: unknown): UiPreferences {
  if (!isRecord(raw)) return { ...DEFAULT_UI_PREFERENCES };

  // Versioned parsing (future-ready)
  const version = safeNumber(raw.version, 0);

  if (version !== 1) {
    // Unknown version: fall back safely.
    return { ...DEFAULT_UI_PREFERENCES };
  }

  const themeRaw = safeString(raw.theme, DEFAULT_UI_PREFERENCES.theme);
  const theme: UiTheme = themeRaw === "dark" || themeRaw === "light" || themeRaw === "system" ? themeRaw : "system";

  const densityRaw = safeString(raw.density, DEFAULT_UI_PREFERENCES.density);
  const density: UiDensity = densityRaw === "compact" || densityRaw === "comfortable" ? densityRaw : "comfortable";

  const showAdvanced = safeBoolean(raw.show_advanced, DEFAULT_UI_PREFERENCES.show_advanced);

  const refreshRaw = isRecord(raw.refresh) ? (raw.refresh as Record<string, unknown>) : {};
  const approvalsMs = Math.max(0, safeNumber(refreshRaw.approvals_ms, DEFAULT_UI_PREFERENCES.refresh.approvals_ms));
  const ledgerMs = Math.max(0, safeNumber(refreshRaw.ledger_ms, DEFAULT_UI_PREFERENCES.refresh.ledger_ms));
  const healthMs = Math.max(0, safeNumber(refreshRaw.health_ms, DEFAULT_UI_PREFERENCES.refresh.health_ms));

  const prefs: UiPreferences = {
    version: 1,
    theme,
    density,
    show_advanced: showAdvanced,
    refresh: {
      approvals_ms: approvalsMs,
      ledger_ms: ledgerMs,
      health_ms: healthMs,
    },
    updated_ts: normalizeUnixSeconds(raw.updated_ts) ?? Math.floor(Date.now() / 1000),
  };

  if (isRecord(raw.meta)) prefs.meta = raw.meta as Record<string, unknown>;

  return prefs;
}

/**
 * Local UI preference store:
 *  - versioned schema
 *  - safe parse + defaults
 *  - optional cross-tab subscription via `storage` event
 */
export class UiPreferencesStore {
  readonly storageKey: string;

  constructor(storageKey = "francis.ui.preferences") {
    this.storageKey = storageKey;
  }

  read(): UiPreferences {
    if (!hasStorage()) return { ...DEFAULT_UI_PREFERENCES };

    try {
      const raw = window.localStorage.getItem(this.storageKey);
      if (!raw) return { ...DEFAULT_UI_PREFERENCES };

      const parsed = JSON.parse(raw) as unknown;
      return parseUiPreferences(parsed);
    } catch {
      return { ...DEFAULT_UI_PREFERENCES };
    }
  }

  write(prefs: UiPreferences): void {
    if (!hasStorage()) return;

    const normalized: UiPreferences = {
      ...prefs,
      version: 1,
      updated_ts: Math.floor(Date.now() / 1000),
    };

    try {
      window.localStorage.setItem(this.storageKey, JSON.stringify(normalized));
    } catch {
      // ignore (quota, privacy mode, etc.)
    }
  }

  patch(patch: Partial<UiPreferences>): UiPreferences {
    const current = this.read();

    // Shallow merge + nested refresh merge
    const next: UiPreferences = {
      ...current,
      ...patch,
      version: 1,
      refresh: {
        ...current.refresh,
        ...(isRecord(patch.refresh) ? (patch.refresh as UiPreferences["refresh"]) : {}),
      },
      updated_ts: Math.floor(Date.now() / 1000),
    };

    // Normalize through parser to enforce constraints.
    const normalized = parseUiPreferences(next);
    this.write(normalized);
    return normalized;
  }

  /**
   * Cross-tab synchronization (optional).
   * Returns an unsubscribe function.
   */
  subscribe(cb: (prefs: UiPreferences) => void): () => void {
    if (typeof window === "undefined") return () => {};
    if (!hasStorage()) return () => {};

    const handler = (e: StorageEvent) => {
      if (e.key !== this.storageKey) return;
      cb(this.read());
    };

    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }
}

/**
 * Convenience: safe duration clamp for UI controls.
 */
export function clampMs(ms: number, minMs: number, maxMs: number): number {
  if (!Number.isFinite(ms)) return minMs;
  return Math.max(minMs, Math.min(maxMs, ms));
}

/**
 * Convenience: format seconds/ms-ish timestamps to local time.
 */
export function toLocaleTime(tsSeconds?: number): string {
  if (!tsSeconds || !Number.isFinite(tsSeconds)) return "";
  const ms = tsSeconds > 10_000_000_000 ? tsSeconds : tsSeconds * 1000;
  return new Date(ms).toLocaleString();
}

/**
 * Convenience: derive a reasonable default API base URL when not provided.
 * This is intentionally conservative and suitable for local dev.
 */
export function defaultApiBaseUrl(): string {
  return "http://127.0.0.1:8000";
}
