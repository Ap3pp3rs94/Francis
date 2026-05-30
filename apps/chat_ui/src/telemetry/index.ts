export type TelemetrySourceStatus = {
  id: string;
  label: string;
  description: string;
  status: string;
  active: boolean;
  visible_indicator: boolean;
  hidden_sensing: boolean;
  scope: {
    status: string;
    allowed_paths: string[];
    allowed_processes: string[];
    denied_by_default: boolean;
  };
  redaction: Record<string, unknown>;
  retention: Record<string, unknown>;
  signals: unknown[];
  expected_signals: string[];
  blocked_by: string[];
  authority: Record<string, boolean>;
  latest_event?: TelemetryTerminalEventSummary | null;
  latest_snapshot?: TelemetryGitSnapshotSummary | null;
  latest_diagnostic?: TelemetryIdeDiagnosticSummary | null;
  routes: Record<string, string>;
};

export type TelemetryTerminalEventSummary = {
  event_id: string;
  recorded_ts?: number;
  exit_code?: number | null;
  cwd: string;
  command: string;
  operation_id: string;
  approval_id: string;
  trace_id: string;
  run_id: string;
  artifact_dir: string;
};

export type TelemetryGitSnapshotSummary = {
  branch: string;
  head: string;
  upstream: string;
  ahead: number;
  behind: number;
  dirty: boolean;
  changed_count: number;
  changed_paths: Array<{ status: string; path: string }>;
  ts?: number;
};

export type TelemetryIdeDiagnosticSummary = {
  event_id: string;
  recorded_ts?: number;
  source: string;
  workspace: string;
  file: string;
  diagnostic_count: number;
  highest_severity: string;
  operation_id: string;
  approval_id: string;
  trace_id: string;
  run_id: string;
};

export type TelemetryStatusSnapshot = {
  ok: boolean;
  kind: string;
  stage: string;
  status: string;
  active: boolean;
  claim: string;
  ts?: number;
  source_total: number;
  active_source_total: number;
  sources: TelemetrySourceStatus[];
  redaction: Record<string, unknown>;
  retention: Record<string, unknown>;
  sensing: Record<string, unknown>;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackReview = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  capture_mode: string;
  reviewed_event_count: number;
  total: number;
  limit: number;
  truncated: boolean;
  rating_counts: Record<string, number>;
  source_counts: Record<string, number>;
  tag_counts: Record<string, number>;
  quality_signals: string[];
  latest_feedback: {
    feedback_id: string;
    context_id: string;
    surface: string;
    rating: string;
    source_ids: string[];
    tags: string[];
    recorded_ts?: number;
  } | null;
  redacted: boolean;
  hidden_sensing: boolean;
  stores_prompt_body: boolean;
  stores_model_response: boolean;
  trains_model: boolean;
  writes_memory: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackRecord = {
  ok: boolean;
  kind: string;
  status: string;
  source_id: string;
  item: {
    feedback_id: string;
    context_id: string;
    surface: string;
    rating: string;
    message_id: string;
    reply_mode: string;
    source_ids: string[];
    tags: string[];
    recorded_ts?: number;
  } | null;
  governance: Record<string, unknown>;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackReview = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  capture_mode: string;
  target: string;
  reviewed_event_count: number;
  limit: number;
  rating_counts: Record<string, number>;
  source_counts: Record<string, number>;
  tag_counts: Record<string, number>;
  quality_signals: string[];
  latest_feedback: {
    feedback_id: string;
    context_id: string;
    surface: string;
    rating: string;
    message_id: string;
    reply_mode: string;
    source_ids: string[];
    tags: string[];
    line_count: number;
    recorded_ts?: number;
  } | null;
  redacted: boolean;
  hidden_sensing: boolean;
  writes_memory: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryQualityRecord = {
  ok: boolean;
  kind: string;
  status: string;
  source_id: string;
  memory_event_id: string;
  writes_memory: boolean;
  quality: Record<string, unknown>;
  memory_event: Record<string, unknown> | null;
  governance: Record<string, unknown>;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  capture_mode: string;
  target: string;
  review: Record<string, unknown>;
  memory_write_candidate: Record<string, unknown>;
  memory_write_route: string;
  memory_quality_record_route: string;
  required_scope: string;
  operator_decision_required: boolean;
  writes_memory: boolean;
  redacted: boolean;
  hidden_sensing: boolean;
  stores_prompt_body: boolean;
  stores_model_response: boolean;
  trains_model: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryRetrievalEvent = {
  id: string;
  kind: string;
  action_type: string;
  classification: string;
  confidence?: number;
  retention: Record<string, unknown>;
  payload: Record<string, unknown>;
};

export type TelemetryContextFeedbackMemoryRetrievalReadback = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  count: number;
  total: number;
  skipped_count: number;
  items: TelemetryContextFeedbackMemoryRetrievalEvent[];
  reads_memory: boolean;
  writes_memory: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  count: number;
  total: number;
  skipped_count: number;
  items: TelemetryContextFeedbackMemoryRetrievalEvent[];
  reads_memory: boolean;
  writes_memory: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  requirements: Array<Record<string, unknown>>;
  ready_count: number;
  required_count: number;
  loop_observed: boolean;
  reviewed_event_count: number;
  memory_event_count: number;
  dry_run_event_count: number;
  chat_context_line_count: number;
  routes: Record<string, unknown>;
  reads_memory: boolean;
  writes_memory: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  sample_id: string;
  loop_observed: boolean;
  audit: Record<string, unknown>;
  chat_context: Record<string, unknown>;
  sample_chat_request: Record<string, unknown>;
  sample_feedback_request: Record<string, unknown>;
  sample_memory_record_request: Record<string, unknown>;
  reads_memory: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  sample_id: string;
  acceptance_ready: boolean;
  acceptance_criteria: Array<Record<string, unknown>>;
  ready_count: number;
  required_count: number;
  sample: Record<string, unknown>;
  reads_memory: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  live_sample_observed: boolean;
  criteria: Array<Record<string, unknown>>;
  ready_count: number;
  required_count: number;
  acceptance: Record<string, unknown>;
  chat: Record<string, unknown>;
  feedback: Record<string, unknown>;
  memory: Record<string, unknown>;
  reads_conversation_ledger: boolean;
  reads_feedback: boolean;
  reads_memory: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  operator_review_ready: boolean;
  live_sample_observed: boolean;
  ready_count: number;
  required_count: number;
  criteria: Array<Record<string, unknown>>;
  review_items: Array<Record<string, unknown>>;
  live_sample: Record<string, unknown>;
  evidence: Record<string, unknown>;
  operator_decision: Record<string, unknown>;
  reads_conversation_ledger: boolean;
  reads_feedback: boolean;
  reads_memory: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionRecord = {
  ok: boolean;
  kind: string;
  status: string;
  source_id: string;
  target: string;
  review: Record<string, unknown>;
  receipt: Record<string, unknown> | null;
  receipt_id: string;
  decision: string;
  writes_receipt: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionReadback = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  items: Array<Record<string, unknown>>;
  count: number;
  total: number;
  limit: number;
  truncated: boolean;
  latest_receipt: Record<string, unknown>;
  latest_receipt_id: string;
  latest_decision: string;
  latest_recorded_ts: number;
  decision_counts: Record<string, number>;
  receipt_readback_ready: boolean;
  redacted: boolean;
  reads_receipts: boolean;
  writes_receipts: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  outcome: string;
  outcome_review_ready: boolean;
  latest_decision: string;
  latest_receipt_id: string;
  latest_recorded_ts: number;
  receipt_readback: Record<string, unknown>;
  decision_counts: Record<string, number>;
  review: Record<string, unknown>;
  reads_receipts: boolean;
  writes_receipts: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceTerminalContextSignal = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  terminal_context_signal_ready: boolean;
  accepted_operator_outcome: boolean;
  outcome_review_ready: boolean;
  outcome: string;
  latest_decision: string;
  latest_receipt_id: string;
  terminal_event_count: number;
  terminal_context_line_count: number;
  terminal_context_items: Array<Record<string, unknown>>;
  terminal_context_lines: string[];
  latest_terminal_event: Record<string, unknown>;
  outcome_review: Record<string, unknown>;
  reads_terminal_context: boolean;
  reads_terminal_events: boolean;
  reads_receipts: boolean;
  writes_terminal_events: boolean;
  writes_receipts: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  captures_terminal_streams: boolean;
  stores_stdout_stderr: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceGitContextSignal = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  git_context_signal_ready: boolean;
  terminal_context_signal_ready: boolean;
  git_snapshot_ready: boolean;
  branch: string;
  head: string;
  upstream: string;
  dirty: boolean;
  changed_count: number;
  changed_paths: Array<{ status: string; path: string }>;
  git_context_line_count: number;
  git_context_items: Array<Record<string, unknown>>;
  git_context_lines: string[];
  git_snapshot: Record<string, unknown>;
  terminal_context_signal: Record<string, unknown>;
  reads_git_context: boolean;
  reads_git_status: boolean;
  reads_terminal_context_signal: boolean;
  writes_git_state: boolean;
  starts_git_watcher: boolean;
  runs_git_fetch: boolean;
  runs_git_pull: boolean;
  runs_git_push: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceIdeContextSignal = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  target: string;
  ide_context_signal_ready: boolean;
  git_context_signal_ready: boolean;
  ide_event_ready: boolean;
  ide_event_count: number;
  ide_context_line_count: number;
  ide_context_items: Array<Record<string, unknown>>;
  ide_context_lines: string[];
  latest_ide_diagnostic: Record<string, unknown>;
  git_context_signal: Record<string, unknown>;
  reads_ide_context: boolean;
  reads_ide_diagnostics: boolean;
  reads_git_context_signal: boolean;
  writes_ide_diagnostics: boolean;
  captures_file_contents: boolean;
  stores_file_contents: boolean;
  starts_ide_integration: boolean;
  writes_memory: boolean;
  writes_feedback: boolean;
  sends_chat: boolean;
  calls_model: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistancePolicy = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  policy_id: string;
  memory_readback_route: string;
  operator_feedback_memory_readback_route: string;
  memory_policy_route: string;
  allowed_memory_event_kinds: string[];
  allowed_action_types: string[];
  allowed_classifications: string[];
  allowed_influence: string[];
  forbidden_influence: string[];
  assistance_guards: Record<string, unknown>;
  reads_memory: boolean;
  writes_memory: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceDryRun = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  event_count: number;
  event_refs: Array<Record<string, unknown>>;
  rating_counts: Record<string, number>;
  source_attention: Array<Record<string, unknown>>;
  assistance_projection: Record<string, unknown>;
  dry_run_only: boolean;
  reads_memory: boolean;
  writes_memory: boolean;
  trains_model: boolean;
  calls_model: boolean;
  mutates_prompt: boolean;
  selects_tools: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistanceChatContextReadback = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  chat_context: {
    target: string;
    line_count: number;
    max_context_lines: number;
    lines: string[];
    visible_header_required: boolean;
    telemetry_is_untrusted_input: boolean;
  };
  would_change_chat_prompt: boolean;
  applies_to_chat_now: boolean;
  reads_memory: boolean;
  writes_memory: boolean;
  calls_model: boolean;
  mutates_prompt: boolean;
  selects_tools: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export class TelemetryApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(message: string, opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown }) {
    super(message);
    this.name = "TelemetryApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.bodySnippet = opts?.bodySnippet;
    if (opts?.cause !== undefined) this.cause = opts.cause;
  }
}

export function parseTelemetryStatus(value: unknown): TelemetryStatusSnapshot {
  const raw = isRecord(value) ? value : {};
  const sources = Array.isArray(raw.sources)
    ? raw.sources.map(parseTelemetrySource).filter((item): item is TelemetrySourceStatus => item !== null)
    : [];

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    status: safeString(raw.status, "unknown"),
    active: safeBoolean(raw.active, false),
    claim: safeString(raw.claim, ""),
    ts: safeNumberOrUndefined(raw.ts),
    source_total: safeNumber(raw.source_total, sources.length),
    active_source_total: safeNumber(raw.active_source_total, sources.filter((source) => source.active).length),
    sources,
    redaction: recordOrEmpty(raw.redaction),
    retention: recordOrEmpty(raw.retention),
    sensing: recordOrEmpty(raw.sensing),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackReview(value: unknown): TelemetryContextFeedbackReview {
  const raw = isRecord(value) ? value : {};
  const latest = parseTelemetryContextFeedbackReviewItem(raw.latest_feedback);

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    capture_mode: safeString(raw.capture_mode, ""),
    reviewed_event_count: safeNumber(raw.reviewed_event_count, 0),
    total: safeNumber(raw.total, 0),
    limit: safeNumber(raw.limit, 0),
    truncated: safeBoolean(raw.truncated, false),
    rating_counts: numberRecord(raw.rating_counts),
    source_counts: numberRecord(raw.source_counts),
    tag_counts: numberRecord(raw.tag_counts),
    quality_signals: safeStringArray(raw.quality_signals),
    latest_feedback: latest,
    redacted: safeBoolean(raw.redacted, false),
    hidden_sensing: safeBoolean(raw.hidden_sensing, false),
    stores_prompt_body: safeBoolean(raw.stores_prompt_body, true),
    stores_model_response: safeBoolean(raw.stores_model_response, true),
    trains_model: safeBoolean(raw.trains_model, true),
    writes_memory: safeBoolean(raw.writes_memory, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackRecord(value: unknown): TelemetryContextFeedbackRecord {
  const raw = isRecord(value) ? value : {};
  const itemRaw = recordOrEmpty(raw.item);
  const item =
    Object.keys(itemRaw).length > 0
      ? {
          feedback_id: safeString(itemRaw.feedback_id, ""),
          context_id: safeString(itemRaw.context_id, ""),
          surface: safeString(itemRaw.surface, ""),
          rating: safeString(itemRaw.rating, ""),
          message_id: safeString(itemRaw.message_id, ""),
          reply_mode: safeString(itemRaw.reply_mode, ""),
          source_ids: safeStringArray(itemRaw.source_ids),
          tags: safeStringArray(itemRaw.tags),
          recorded_ts: safeNumberOrUndefined(itemRaw.recorded_ts),
        }
      : null;

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    status: safeString(raw.status, "unknown"),
    source_id: safeString(raw.source_id, ""),
    item,
    governance: recordOrEmpty(raw.governance),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackReview(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackReview {
  const raw = isRecord(value) ? value : {};
  const latest = parseTelemetryContextFeedbackMemoryAssistanceLatestFeedback(raw.latest_feedback);

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    capture_mode: safeString(raw.capture_mode, ""),
    target: safeString(raw.target, ""),
    reviewed_event_count: safeNumber(raw.reviewed_event_count, 0),
    limit: safeNumber(raw.limit, 0),
    rating_counts: numberRecord(raw.rating_counts),
    source_counts: numberRecord(raw.source_counts),
    tag_counts: numberRecord(raw.tag_counts),
    quality_signals: safeStringArray(raw.quality_signals),
    latest_feedback: latest,
    redacted: safeBoolean(raw.redacted, false),
    hidden_sensing: safeBoolean(raw.hidden_sensing, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryQualityRecord(
  value: unknown,
): TelemetryContextFeedbackMemoryQualityRecord {
  const raw = isRecord(value) ? value : {};
  const memoryEvent = recordOrEmpty(raw.memory_event);

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    status: safeString(raw.status, "unknown"),
    source_id: safeString(raw.source_id, ""),
    memory_event_id: safeString(raw.memory_event_id, ""),
    writes_memory: safeBoolean(raw.writes_memory, false),
    quality: recordOrEmpty(raw.quality),
    memory_event: Object.keys(memoryEvent).length > 0 ? memoryEvent : null,
    governance: recordOrEmpty(raw.governance),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    capture_mode: safeString(raw.capture_mode, ""),
    target: safeString(raw.target, ""),
    review: recordOrEmpty(raw.review),
    memory_write_candidate: recordOrEmpty(raw.memory_write_candidate),
    memory_write_route: safeString(raw.memory_write_route, ""),
    memory_quality_record_route: safeString(raw.memory_quality_record_route, ""),
    required_scope: safeString(raw.required_scope, ""),
    operator_decision_required: safeBoolean(raw.operator_decision_required, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    redacted: safeBoolean(raw.redacted, false),
    hidden_sensing: safeBoolean(raw.hidden_sensing, false),
    stores_prompt_body: safeBoolean(raw.stores_prompt_body, true),
    stores_model_response: safeBoolean(raw.stores_model_response, true),
    trains_model: safeBoolean(raw.trains_model, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryRetrievalReadback(
  value: unknown,
): TelemetryContextFeedbackMemoryRetrievalReadback {
  const raw = isRecord(value) ? value : {};
  const items = Array.isArray(raw.items)
    ? raw.items
        .map(parseTelemetryContextFeedbackMemoryRetrievalEvent)
        .filter((item): item is TelemetryContextFeedbackMemoryRetrievalEvent => item !== null)
    : [];

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    count: safeNumber(raw.count, items.length),
    total: safeNumber(raw.total, items.length),
    skipped_count: safeNumber(raw.skipped_count, 0),
    items,
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback {
  const raw = isRecord(value) ? value : {};
  const items = Array.isArray(raw.items)
    ? raw.items
        .map(parseTelemetryContextFeedbackMemoryRetrievalEvent)
        .filter((item): item is TelemetryContextFeedbackMemoryRetrievalEvent => item !== null)
    : [];

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    count: safeNumber(raw.count, items.length),
    total: safeNumber(raw.total, items.length),
    skipped_count: safeNumber(raw.skipped_count, 0),
    items,
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    requirements: Array.isArray(raw.requirements) ? raw.requirements.filter(isRecord) : [],
    ready_count: safeNumber(raw.ready_count, 0),
    required_count: safeNumber(raw.required_count, 0),
    loop_observed: safeBoolean(raw.loop_observed, false),
    reviewed_event_count: safeNumber(raw.reviewed_event_count, 0),
    memory_event_count: safeNumber(raw.memory_event_count, 0),
    dry_run_event_count: safeNumber(raw.dry_run_event_count, 0),
    chat_context_line_count: safeNumber(raw.chat_context_line_count, 0),
    routes: recordOrEmpty(raw.routes),
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    sample_id: safeString(raw.sample_id, ""),
    loop_observed: safeBoolean(raw.loop_observed, false),
    audit: recordOrEmpty(raw.audit),
    chat_context: recordOrEmpty(raw.chat_context),
    sample_chat_request: recordOrEmpty(raw.sample_chat_request),
    sample_feedback_request: recordOrEmpty(raw.sample_feedback_request),
    sample_memory_record_request: recordOrEmpty(raw.sample_memory_record_request),
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    sample_id: safeString(raw.sample_id, ""),
    acceptance_ready: safeBoolean(raw.acceptance_ready, false),
    acceptance_criteria: Array.isArray(raw.acceptance_criteria) ? raw.acceptance_criteria.filter(isRecord) : [],
    ready_count: safeNumber(raw.ready_count, 0),
    required_count: safeNumber(raw.required_count, 0),
    sample: recordOrEmpty(raw.sample),
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    live_sample_observed: safeBoolean(raw.live_sample_observed, false),
    criteria: Array.isArray(raw.criteria) ? raw.criteria.filter(isRecord) : [],
    ready_count: safeNumber(raw.ready_count, 0),
    required_count: safeNumber(raw.required_count, 0),
    acceptance: recordOrEmpty(raw.acceptance),
    chat: recordOrEmpty(raw.chat),
    feedback: recordOrEmpty(raw.feedback),
    memory: recordOrEmpty(raw.memory),
    reads_conversation_ledger: safeBoolean(raw.reads_conversation_ledger, false),
    reads_feedback: safeBoolean(raw.reads_feedback, false),
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    operator_review_ready: safeBoolean(raw.operator_review_ready, false),
    live_sample_observed: safeBoolean(raw.live_sample_observed, false),
    ready_count: safeNumber(raw.ready_count, 0),
    required_count: safeNumber(raw.required_count, 0),
    criteria: Array.isArray(raw.criteria) ? raw.criteria.filter(isRecord) : [],
    review_items: Array.isArray(raw.review_items) ? raw.review_items.filter(isRecord) : [],
    live_sample: recordOrEmpty(raw.live_sample),
    evidence: recordOrEmpty(raw.evidence),
    operator_decision: recordOrEmpty(raw.operator_decision),
    reads_conversation_ledger: safeBoolean(raw.reads_conversation_ledger, false),
    reads_feedback: safeBoolean(raw.reads_feedback, false),
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionRecord(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionRecord {
  const raw = isRecord(value) ? value : {};
  const receipt = isRecord(raw.receipt) ? raw.receipt : null;

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    status: safeString(raw.status, "unknown"),
    source_id: safeString(raw.source_id, ""),
    target: safeString(raw.target, ""),
    review: recordOrEmpty(raw.review),
    receipt,
    receipt_id: safeString(raw.receipt_id, ""),
    decision: safeString(raw.decision, ""),
    writes_receipt: safeBoolean(raw.writes_receipt, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionReadback(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionReadback {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    items: Array.isArray(raw.items) ? raw.items.filter(isRecord) : [],
    count: safeNumber(raw.count, 0),
    total: safeNumber(raw.total, 0),
    limit: safeNumber(raw.limit, 20),
    truncated: safeBoolean(raw.truncated, false),
    latest_receipt: recordOrEmpty(raw.latest_receipt),
    latest_receipt_id: safeString(raw.latest_receipt_id, ""),
    latest_decision: safeString(raw.latest_decision, ""),
    latest_recorded_ts: safeNumber(raw.latest_recorded_ts, 0),
    decision_counts: safeNumberRecord(raw.decision_counts),
    receipt_readback_ready: safeBoolean(raw.receipt_readback_ready, false),
    redacted: safeBoolean(raw.redacted, false),
    reads_receipts: safeBoolean(raw.reads_receipts, false),
    writes_receipts: safeBoolean(raw.writes_receipts, true),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    outcome: safeString(raw.outcome, ""),
    outcome_review_ready: safeBoolean(raw.outcome_review_ready, false),
    latest_decision: safeString(raw.latest_decision, ""),
    latest_receipt_id: safeString(raw.latest_receipt_id, ""),
    latest_recorded_ts: safeNumber(raw.latest_recorded_ts, 0),
    receipt_readback: recordOrEmpty(raw.receipt_readback),
    decision_counts: safeNumberRecord(raw.decision_counts),
    review: recordOrEmpty(raw.review),
    reads_receipts: safeBoolean(raw.reads_receipts, false),
    writes_receipts: safeBoolean(raw.writes_receipts, true),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceTerminalContextSignal(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceTerminalContextSignal {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    terminal_context_signal_ready: safeBoolean(raw.terminal_context_signal_ready, false),
    accepted_operator_outcome: safeBoolean(raw.accepted_operator_outcome, false),
    outcome_review_ready: safeBoolean(raw.outcome_review_ready, false),
    outcome: safeString(raw.outcome, ""),
    latest_decision: safeString(raw.latest_decision, ""),
    latest_receipt_id: safeString(raw.latest_receipt_id, ""),
    terminal_event_count: safeNumber(raw.terminal_event_count, 0),
    terminal_context_line_count: safeNumber(raw.terminal_context_line_count, 0),
    terminal_context_items: Array.isArray(raw.terminal_context_items) ? raw.terminal_context_items.filter(isRecord) : [],
    terminal_context_lines: safeStringArray(raw.terminal_context_lines),
    latest_terminal_event: recordOrEmpty(raw.latest_terminal_event),
    outcome_review: recordOrEmpty(raw.outcome_review),
    reads_terminal_context: safeBoolean(raw.reads_terminal_context, false),
    reads_terminal_events: safeBoolean(raw.reads_terminal_events, false),
    reads_receipts: safeBoolean(raw.reads_receipts, false),
    writes_terminal_events: safeBoolean(raw.writes_terminal_events, true),
    writes_receipts: safeBoolean(raw.writes_receipts, true),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    captures_terminal_streams: safeBoolean(raw.captures_terminal_streams, true),
    stores_stdout_stderr: safeBoolean(raw.stores_stdout_stderr, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceGitContextSignal(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceGitContextSignal {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    git_context_signal_ready: safeBoolean(raw.git_context_signal_ready, false),
    terminal_context_signal_ready: safeBoolean(raw.terminal_context_signal_ready, false),
    git_snapshot_ready: safeBoolean(raw.git_snapshot_ready, false),
    branch: safeString(raw.branch, ""),
    head: safeString(raw.head, ""),
    upstream: safeString(raw.upstream, ""),
    dirty: safeBoolean(raw.dirty, false),
    changed_count: safeNumber(raw.changed_count, 0),
    changed_paths: Array.isArray(raw.changed_paths)
      ? raw.changed_paths.map(parseGitChangedPath).filter((item): item is { status: string; path: string } => item !== null)
      : [],
    git_context_line_count: safeNumber(raw.git_context_line_count, 0),
    git_context_items: Array.isArray(raw.git_context_items) ? raw.git_context_items.filter(isRecord) : [],
    git_context_lines: safeStringArray(raw.git_context_lines),
    git_snapshot: recordOrEmpty(raw.git_snapshot),
    terminal_context_signal: recordOrEmpty(raw.terminal_context_signal),
    reads_git_context: safeBoolean(raw.reads_git_context, false),
    reads_git_status: safeBoolean(raw.reads_git_status, false),
    reads_terminal_context_signal: safeBoolean(raw.reads_terminal_context_signal, false),
    writes_git_state: safeBoolean(raw.writes_git_state, true),
    starts_git_watcher: safeBoolean(raw.starts_git_watcher, true),
    runs_git_fetch: safeBoolean(raw.runs_git_fetch, true),
    runs_git_pull: safeBoolean(raw.runs_git_pull, true),
    runs_git_push: safeBoolean(raw.runs_git_push, true),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceIdeContextSignal(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceIdeContextSignal {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    target: safeString(raw.target, ""),
    ide_context_signal_ready: safeBoolean(raw.ide_context_signal_ready, false),
    git_context_signal_ready: safeBoolean(raw.git_context_signal_ready, false),
    ide_event_ready: safeBoolean(raw.ide_event_ready, false),
    ide_event_count: safeNumber(raw.ide_event_count, 0),
    ide_context_line_count: safeNumber(raw.ide_context_line_count, 0),
    ide_context_items: Array.isArray(raw.ide_context_items) ? raw.ide_context_items.filter(isRecord) : [],
    ide_context_lines: safeStringArray(raw.ide_context_lines),
    latest_ide_diagnostic: recordOrEmpty(raw.latest_ide_diagnostic),
    git_context_signal: recordOrEmpty(raw.git_context_signal),
    reads_ide_context: safeBoolean(raw.reads_ide_context, false),
    reads_ide_diagnostics: safeBoolean(raw.reads_ide_diagnostics, false),
    reads_git_context_signal: safeBoolean(raw.reads_git_context_signal, false),
    writes_ide_diagnostics: safeBoolean(raw.writes_ide_diagnostics, true),
    captures_file_contents: safeBoolean(raw.captures_file_contents, true),
    stores_file_contents: safeBoolean(raw.stores_file_contents, true),
    starts_ide_integration: safeBoolean(raw.starts_ide_integration, true),
    writes_memory: safeBoolean(raw.writes_memory, true),
    writes_feedback: safeBoolean(raw.writes_feedback, true),
    sends_chat: safeBoolean(raw.sends_chat, true),
    calls_model: safeBoolean(raw.calls_model, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistancePolicy(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistancePolicy {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    policy_id: safeString(raw.policy_id, ""),
    memory_readback_route: safeString(raw.memory_readback_route, ""),
    operator_feedback_memory_readback_route: safeString(raw.operator_feedback_memory_readback_route, ""),
    memory_policy_route: safeString(raw.memory_policy_route, ""),
    allowed_memory_event_kinds: safeStringArray(raw.allowed_memory_event_kinds),
    allowed_action_types: safeStringArray(raw.allowed_action_types),
    allowed_classifications: safeStringArray(raw.allowed_classifications),
    allowed_influence: safeStringArray(raw.allowed_influence),
    forbidden_influence: safeStringArray(raw.forbidden_influence),
    assistance_guards: recordOrEmpty(raw.assistance_guards),
    reads_memory: safeBoolean(raw.reads_memory, true),
    writes_memory: safeBoolean(raw.writes_memory, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceDryRun(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceDryRun {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    event_count: safeNumber(raw.event_count, 0),
    event_refs: Array.isArray(raw.event_refs) ? raw.event_refs.filter(isRecord) : [],
    rating_counts: numberRecord(raw.rating_counts),
    source_attention: Array.isArray(raw.source_attention) ? raw.source_attention.filter(isRecord) : [],
    assistance_projection: recordOrEmpty(raw.assistance_projection),
    dry_run_only: safeBoolean(raw.dry_run_only, false),
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    trains_model: safeBoolean(raw.trains_model, true),
    calls_model: safeBoolean(raw.calls_model, true),
    mutates_prompt: safeBoolean(raw.mutates_prompt, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistanceChatContextReadback(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceChatContextReadback {
  const raw = isRecord(value) ? value : {};
  const chatContext = recordOrEmpty(raw.chat_context);

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    chat_context: {
      target: safeString(chatContext.target, ""),
      line_count: safeNumber(chatContext.line_count, 0),
      max_context_lines: safeNumber(chatContext.max_context_lines, 0),
      lines: safeStringArray(chatContext.lines),
      visible_header_required: safeBoolean(chatContext.visible_header_required, false),
      telemetry_is_untrusted_input: safeBoolean(chatContext.telemetry_is_untrusted_input, true),
    },
    would_change_chat_prompt: safeBoolean(raw.would_change_chat_prompt, false),
    applies_to_chat_now: safeBoolean(raw.applies_to_chat_now, false),
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    calls_model: safeBoolean(raw.calls_model, true),
    mutates_prompt: safeBoolean(raw.mutates_prompt, true),
    selects_tools: safeBoolean(raw.selects_tools, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export class TelemetryClient {
  readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  async getStatus(opts?: { signal?: AbortSignal }): Promise<TelemetryStatusSnapshot> {
    const url = this.url("/telemetry/status");
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry status request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry status request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryStatus(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry status response was not valid JSON.", { url, cause: err });
    }
  }

  async getContextFeedbackReview(opts?: { limit?: number; signal?: AbortSignal }): Promise<TelemetryContextFeedbackReview> {
    const limit = clampLimit(opts?.limit, 100);
    const url = this.url(`/telemetry/context/feedback/review?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback review request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback review request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackReview(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback review response was not valid JSON.", { url, cause: err });
    }
  }

  async recordContextFeedback(opts: {
    actor: string;
    reason: string;
    rating: "useful" | "not_useful" | "neutral" | string;
    context_id?: string;
    surface?: string;
    message_id?: string;
    reply_mode?: string;
    notes?: string;
    source_ids?: string[];
    tags?: string[];
    meta?: Record<string, unknown>;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackRecord> {
    const url = this.url("/telemetry/context/feedback");
    const body: Record<string, unknown> = {
      actor: opts.actor,
      reason: opts.reason,
      rating: opts.rating,
      surface: opts.surface ?? "chat",
      source_ids: opts.source_ids ?? [],
      tags: opts.tags ?? [],
      meta: opts.meta ?? {},
    };
    if (opts.context_id?.trim()) body.context_id = opts.context_id.trim();
    if (opts.message_id?.trim()) body.message_id = opts.message_id.trim();
    if (opts.reply_mode?.trim()) body.reply_mode = opts.reply_mode.trim();
    if (opts.notes?.trim()) body.notes = opts.notes.trim();

    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: opts.signal,
      });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback record request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback record request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackRecord(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback record response was not valid JSON.", { url, cause: err });
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackReview(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackReview> {
    const limit = clampLimit(opts?.limit, 100);
    const url = this.url(`/telemetry/context/feedback/memory-assistance-feedback-review?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance operator review request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry feedback memory assistance operator review request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackReview(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance operator review response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality> {
    const limit = clampLimit(opts?.limit, 100);
    const url = this.url(`/telemetry/context/feedback/memory-assistance-feedback-memory-quality?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance memory-quality request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance memory-quality request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance memory-quality response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  async recordContextFeedbackMemoryQuality(opts: {
    actor: string;
    reason: string;
    limit?: number;
    event_id?: string;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryQualityRecord> {
    const url = this.url("/telemetry/context/feedback/memory-quality");
    const body: Record<string, unknown> = {
      actor: opts.actor,
      reason: opts.reason,
      limit: clampLimit(opts.limit, 25),
    };
    const eventId = opts.event_id?.trim();
    if (eventId) body.event_id = eventId;

    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: opts.signal,
      });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory-quality record request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback memory-quality record request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackMemoryQualityRecord(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory-quality record response was not valid JSON.", { url, cause: err });
    }
  }

  async recordContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality(opts: {
    actor: string;
    reason: string;
    limit?: number;
    event_id?: string;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryQualityRecord> {
    const url = this.url("/telemetry/context/feedback/memory-assistance-feedback-memory-quality");
    const body: Record<string, unknown> = {
      actor: opts.actor,
      reason: opts.reason,
      limit: clampLimit(opts.limit, 25),
    };
    const eventId = opts.event_id?.trim();
    if (eventId) body.event_id = eventId;

    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: opts.signal,
      });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance memory-quality record request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance memory-quality record request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryQualityRecord(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance memory-quality record response was not valid JSON.",
        { url, cause: err },
      );
    }
  }

  async getContextFeedbackMemoryRetrievalReadback(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryRetrievalReadback> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(`/telemetry/context/feedback/memory-retrieval-readback?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory retrieval readback request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback memory retrieval readback request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackMemoryRetrievalReadback(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory retrieval readback response was not valid JSON.", { url, cause: err });
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(`/telemetry/context/feedback/memory-assistance-feedback-memory-readback?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance memory readback request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance memory readback request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance memory readback response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(`/telemetry/context/feedback/memory-assistance-feedback-loop-audit?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance loop audit request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance loop audit request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance loop audit response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(`/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-sample?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance e2e sample request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance e2e sample request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample(
        text ? JSON.parse(text) : {},
      );
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance e2e sample response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(
      `/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-acceptance-audit?limit=${limit}`,
    );
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance e2e acceptance audit request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance e2e acceptance audit request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit(
        text ? JSON.parse(text) : {},
      );
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance e2e acceptance audit response was not valid JSON.",
        { url, cause: err },
      );
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(
      `/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-readback?limit=${limit}`,
    );
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance live sample readback request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance live sample readback request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback(
        text ? JSON.parse(text) : {},
      );
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance live sample readback response was not valid JSON.",
        { url, cause: err },
      );
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(
      `/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-review?limit=${limit}`,
    );
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance live sample operator review request failed.",
        {
          url,
          cause: err,
        },
      );
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance live sample operator review request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview(
        text ? JSON.parse(text) : {},
      );
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance live sample operator review response was not valid JSON.",
        { url, cause: err },
      );
    }
  }

  async recordContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecision(opts: {
    actor: string;
    reason: string;
    decision: "accepted" | "rejected" | "needs_more_evidence" | string;
    notes?: string;
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionRecord> {
    const url = this.url(
      "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision",
    );
    const body: Record<string, unknown> = {
      actor: opts.actor,
      reason: opts.reason,
      decision: opts.decision,
      notes: opts.notes ?? "",
      limit: clampLimit(opts.limit, 20),
    };
    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: opts.signal,
      });
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance live sample operator decision request failed.",
        { url, cause: err },
      );
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance live sample operator decision request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionRecord(
        text ? JSON.parse(text) : {},
      );
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance live sample operator decision response was not valid JSON.",
        { url, cause: err },
      );
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisions(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionReadback> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(
      `/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decisions?limit=${limit}`,
    );
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance live sample operator decisions request failed.",
        {
          url,
          cause: err,
        },
      );
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance live sample operator decisions request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionReadback(
        text ? JSON.parse(text) : {},
      );
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance live sample operator decisions response was not valid JSON.",
        { url, cause: err },
      );
    }
  }

  async getContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(
      `/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision-outcome-review?limit=${limit}`,
    );
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance live sample operator decision outcome review request failed.",
        {
          url,
          cause: err,
        },
      );
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance live sample operator decision outcome review request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview(
        text ? JSON.parse(text) : {},
      );
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance live sample operator decision outcome review response was not valid JSON.",
        { url, cause: err },
      );
    }
  }

  async getContextFeedbackMemoryAssistanceTerminalContextSignal(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceTerminalContextSignal> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(
      `/telemetry/context/feedback/memory-assistance-feedback-loop-terminal-context-signal?limit=${limit}`,
    );
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance terminal context signal request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance terminal context signal request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceTerminalContextSignal(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry feedback memory assistance terminal context signal response was not valid JSON.",
        { url, cause: err },
      );
    }
  }

  async getContextFeedbackMemoryAssistanceGitContextSignal(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceGitContextSignal> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(
      `/telemetry/context/feedback/memory-assistance-feedback-loop-git-context-signal?limit=${limit}`,
    );
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance git context signal request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance git context signal request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceGitContextSignal(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance git context signal response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  async getContextFeedbackMemoryAssistanceIdeContextSignal(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceIdeContextSignal> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(
      `/telemetry/context/feedback/memory-assistance-feedback-loop-ide-context-signal?limit=${limit}`,
    );
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance IDE context signal request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(
        `HTTP ${response.status} for telemetry feedback memory assistance IDE context signal request`,
        {
          status: response.status,
          url,
          bodySnippet: text.slice(0, 500),
        },
      );
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceIdeContextSignal(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry feedback memory assistance IDE context signal response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  async getContextFeedbackMemoryAssistancePolicy(opts?: {
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistancePolicy> {
    const url = this.url("/telemetry/context/feedback/memory-assistance-policy");
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory assistance policy request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback memory assistance policy request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistancePolicy(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory assistance policy response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  async getContextFeedbackMemoryAssistanceDryRun(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceDryRun> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(`/telemetry/context/feedback/memory-assistance-dry-run?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory assistance dry-run request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback memory assistance dry-run request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceDryRun(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory assistance dry-run response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  async getContextFeedbackMemoryAssistanceChatContextReadback(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistanceChatContextReadback> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(`/telemetry/context/feedback/memory-assistance-chat-context-readback?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory assistance chat-context readback request failed.", {
        url,
        cause: err,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback memory assistance chat-context readback request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistanceChatContextReadback(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError(
        "Telemetry context feedback memory assistance chat-context readback response was not valid JSON.",
        { url, cause: err },
      );
    }
  }

  private url(path: string): string {
    return `${this.baseUrl}${path}`;
  }
}

function parseTelemetrySource(value: unknown): TelemetrySourceStatus | null {
  if (!isRecord(value)) return null;
  const scope = recordOrEmpty(value.scope);

  return {
    id: safeString(value.id, ""),
    label: safeString(value.label, ""),
    description: safeString(value.description, ""),
    status: safeString(value.status, "unknown"),
    active: safeBoolean(value.active, false),
    visible_indicator: safeBoolean(value.visible_indicator, false),
    hidden_sensing: safeBoolean(value.hidden_sensing, false),
    scope: {
      status: safeString(scope.status, "unknown"),
      allowed_paths: safeStringArray(scope.allowed_paths),
      allowed_processes: safeStringArray(scope.allowed_processes),
      denied_by_default: safeBoolean(scope.denied_by_default, false),
    },
    redaction: recordOrEmpty(value.redaction),
    retention: recordOrEmpty(value.retention),
    signals: Array.isArray(value.signals) ? value.signals : [],
    expected_signals: safeStringArray(value.expected_signals),
    blocked_by: safeStringArray(value.blocked_by),
    authority: booleanRecord(value.authority),
    latest_event: parseTerminalEventSummary(value.latest_event),
    latest_snapshot: parseGitSnapshotSummary(value.latest_snapshot),
    latest_diagnostic: parseIdeDiagnosticSummary(value.latest_diagnostic),
    routes: stringRecord(value.routes),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function recordOrEmpty(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function booleanRecord(value: unknown): Record<string, boolean> {
  if (!isRecord(value)) return {};
  const out: Record<string, boolean> = {};
  for (const [key, raw] of Object.entries(value)) {
    out[key] = safeBoolean(raw, false);
  }
  return out;
}

function numberRecord(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {};
  const out: Record<string, number> = {};
  for (const [key, raw] of Object.entries(value)) {
    out[key] = safeNumber(raw, 0);
  }
  return out;
}

function stringRecord(value: unknown): Record<string, string> {
  if (!isRecord(value)) return {};
  const out: Record<string, string> = {};
  for (const [key, raw] of Object.entries(value)) {
    const text = safeString(raw, "").trim();
    if (text) out[key] = text;
  }
  return out;
}

function parseTelemetryContextFeedbackReviewItem(
  value: unknown,
): TelemetryContextFeedbackReview["latest_feedback"] {
  if (!isRecord(value)) return null;
  const item = {
    feedback_id: safeString(value.feedback_id, ""),
    context_id: safeString(value.context_id, ""),
    surface: safeString(value.surface, ""),
    rating: safeString(value.rating, ""),
    source_ids: safeStringArray(value.source_ids),
    tags: safeStringArray(value.tags),
    recorded_ts: safeNumberOrUndefined(value.recorded_ts),
  };
  if (!item.feedback_id && !item.context_id && !item.surface && !item.rating && item.source_ids.length === 0 && item.tags.length === 0) {
    return null;
  }
  return item;
}

function parseTelemetryContextFeedbackMemoryAssistanceLatestFeedback(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistanceOperatorFeedbackReview["latest_feedback"] {
  if (!isRecord(value)) return null;
  const item = {
    feedback_id: safeString(value.feedback_id, ""),
    context_id: safeString(value.context_id, ""),
    surface: safeString(value.surface, ""),
    rating: safeString(value.rating, ""),
    message_id: safeString(value.message_id, ""),
    reply_mode: safeString(value.reply_mode, ""),
    source_ids: safeStringArray(value.source_ids),
    tags: safeStringArray(value.tags),
    line_count: safeNumber(value.line_count, 0),
    recorded_ts: safeNumberOrUndefined(value.recorded_ts),
  };
  if (
    !item.feedback_id &&
    !item.context_id &&
    !item.message_id &&
    !item.reply_mode &&
    item.source_ids.length === 0 &&
    item.tags.length === 0
  ) {
    return null;
  }
  return item;
}

function parseTelemetryContextFeedbackMemoryRetrievalEvent(
  value: unknown,
): TelemetryContextFeedbackMemoryRetrievalEvent | null {
  if (!isRecord(value)) return null;
  const id = safeString(value.id, "").trim();
  const kind = safeString(value.kind, "").trim();
  if (!id && !kind) return null;
  return {
    id,
    kind,
    action_type: safeString(value.action_type, ""),
    classification: safeString(value.classification, ""),
    confidence: safeNumberOrUndefined(value.confidence),
    retention: recordOrEmpty(value.retention),
    payload: recordOrEmpty(value.payload),
  };
}

function parseTerminalEventSummary(value: unknown): TelemetryTerminalEventSummary | null {
  if (!isRecord(value)) return null;
  return {
    event_id: safeString(value.event_id, ""),
    recorded_ts: safeNumberOrUndefined(value.recorded_ts),
    exit_code: value.exit_code === null ? null : safeNumberOrUndefined(value.exit_code),
    cwd: safeString(value.cwd, ""),
    command: safeString(value.command, ""),
    operation_id: safeString(value.operation_id, ""),
    approval_id: safeString(value.approval_id, ""),
    trace_id: safeString(value.trace_id, ""),
    run_id: safeString(value.run_id, ""),
    artifact_dir: safeString(value.artifact_dir, ""),
  };
}

function parseGitSnapshotSummary(value: unknown): TelemetryGitSnapshotSummary | null {
  if (!isRecord(value)) return null;
  return {
    branch: safeString(value.branch, ""),
    head: safeString(value.head, ""),
    upstream: safeString(value.upstream, ""),
    ahead: safeNumber(value.ahead, 0),
    behind: safeNumber(value.behind, 0),
    dirty: safeBoolean(value.dirty, false),
    changed_count: safeNumber(value.changed_count, 0),
    changed_paths: Array.isArray(value.changed_paths)
      ? value.changed_paths.map(parseGitChangedPath).filter((item): item is { status: string; path: string } => item !== null)
      : [],
    ts: safeNumberOrUndefined(value.ts),
  };
}

function parseGitChangedPath(value: unknown): { status: string; path: string } | null {
  if (!isRecord(value)) return null;
  return {
    status: safeString(value.status, ""),
    path: safeString(value.path, ""),
  };
}

function parseIdeDiagnosticSummary(value: unknown): TelemetryIdeDiagnosticSummary | null {
  if (!isRecord(value)) return null;
  return {
    event_id: safeString(value.event_id, ""),
    recorded_ts: safeNumberOrUndefined(value.recorded_ts),
    source: safeString(value.source, ""),
    workspace: safeString(value.workspace, ""),
    file: safeString(value.file, ""),
    diagnostic_count: safeNumber(value.diagnostic_count, 0),
    highest_severity: safeString(value.highest_severity, ""),
    operation_id: safeString(value.operation_id, ""),
    approval_id: safeString(value.approval_id, ""),
    trace_id: safeString(value.trace_id, ""),
    run_id: safeString(value.run_id, ""),
  };
}

function safeString(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function safeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => safeString(item, "").trim()).filter(Boolean);
}

function safeBoolean(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true") return true;
    if (normalized === "false") return false;
  }
  return fallback;
}

function safeNumber(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function safeNumberRecord(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {};
  const result: Record<string, number> = {};
  for (const [key, item] of Object.entries(value)) {
    result[key] = safeNumber(item, 0);
  }
  return result;
}

function safeNumberOrUndefined(value: unknown): number | undefined {
  const parsed = safeNumber(value, Number.NaN);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function clampLimit(value: unknown, fallback: number): number {
  const parsed = safeNumber(value, fallback);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(Math.max(Math.trunc(parsed), 1), 500);
}
