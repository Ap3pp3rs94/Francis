/**
 * Federation Hub module (UI).
 *
 * Framework-agnostic client + types for federation observability and governance-adjacent actions.
 *
 * Scope (UI-safe):
 *  - List federation instances (membership)
 *  - Get instance detail (metadata + health + capabilities)
 *  - Batch instance get (client-side fan-out; no new backend contract)
 *  - List delegations (who delegated what to whom)
 *  - List consensus logs (audit trail) with optional date range filtering
 *  - List shared knowledge metadata (no raw secrets)
 *
 * Non-goals:
 *  - No React imports
 *  - No direct secret handling
 *  - No direct remote "execute" or "health check action" from browser
 *
 * Endpoints:
 *  - Defaults are conventional and can be overridden via options to match backend contracts.
 */

export const DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR = "codex.builder";

export type FederationInstanceStatus =
  | "online"
  | "offline"
  | "degraded"
  | "joining"
  | "leaving"
  | "banned"
  | "unknown"
  | string;

export type FederationCapability =
  | "api"
  | "daemon"
  | "workers"
  | "memory"
  | "vectorstore"
  | "web_learning"
  | "industrial"
  | "simulation"
  | "plugins"
  | string;

export type FederationInstance = {
  id: string;
  name?: string;

  status?: FederationInstanceStatus;

  // Network/identity
  endpoint?: string; // e.g., https://host:port (metadata only)
  region?: string;
  role?: string;

  // Timestamps (unix seconds preferred; ms tolerated by consumers)
  first_seen_ts?: number;
  last_seen_ts?: number;

  // Capability surface (metadata)
  capabilities?: FederationCapability[];

  // Governance hints
  trust_level?: number;
  requires_approval?: boolean;

  // Forward-compatible metadata
  tags?: string[];
  meta?: Record<string, unknown>;
};

export type FederationInstanceDetail = FederationInstance & {
  // Optional health/status summary bags
  health?: Record<string, unknown>;
  inventory?: Record<string, unknown>;
};

export type FederationDelegationStatus = "pending" | "active" | "revoked" | "expired" | string;

export type FederationDelegation = {
  id: string;
  ts: number;

  from?: string;
  to?: string;

  scope?: string; // delegation scope label
  status?: FederationDelegationStatus;

  reason?: string;

  // Forward-compatible metadata
  meta?: Record<string, unknown>;
};

export type ConsensusLogLevel = "info" | "warning" | "error" | "critical" | string;

export type ConsensusLogEntry = {
  id?: string;
  ts: number;

  level?: ConsensusLogLevel;
  kind?: string;

  instance_id?: string;
  term?: number;
  index?: number;

  message?: string;

  // Forward-compatible payload
  meta?: Record<string, unknown>;
};

export type SharedKnowledgeKind = "document" | "fact" | "schema" | "policy" | "embedding_set" | string;

export type SharedKnowledgeItem = {
  id: string;
  ts?: number;

  kind?: SharedKnowledgeKind;
  title?: string;

  // Provenance
  source_instance_id?: string;
  domain?: string;

  // Forward-compatible metadata (never secrets)
  tags?: string[];
  meta?: Record<string, unknown>;
};

export type FederationStage16Status = {
  ok: boolean;
  status?: string;
  stage?: string;
  stage16_status?: string;
  stage16_completion_review_ready: boolean;
  live_runtime_readback_ready: boolean;
  completion_review_blockers: string[];
  sleep_continuity_status?: string;
  sleep_continuity_ready: boolean;
  pre_sleep_evidence_ready: boolean;
  post_resume_evidence_ready: boolean;
  post_resume_evidence_conflict: boolean;
  latest_pre_sleep_evidence?: Record<string, unknown>;
  latest_post_resume_evidence?: Record<string, unknown>;
  sleep_continuity_selected_action_id?: string;
  sleep_continuity_action_current_ready_to_run: boolean;
  sleep_continuity_operator_confirmation_pending: boolean;
  sleep_continuity_post_confirmation_ready_to_capture: boolean;
  sleep_continuity_confirmation_blocker?: string;
  sleep_continuity_blocked_reason?: string;
  sleep_continuity_sleep_resume_confirmation_is_current_blocker: boolean;
  sleep_continuity_confirmation_receipt_command_ready: boolean;
  sleep_continuity_confirmation_receipt_command_visible: boolean;
  sleep_continuity_confirmation_receipt_command?: string;
  sleep_continuity_confirmation_receipt_copyable_command?: string;
  sleep_continuity_confirmation_receipt_command_requires_scope?: string;
  sleep_continuity_confirmation_receipt_requested_actor?: string;
  sleep_continuity_confirmation_receipt_requested_actor_ready: boolean;
  sleep_continuity_confirmation_receipt_actor?: string;
  sleep_continuity_confirmation_receipt_actor_bound: boolean;
  sleep_continuity_confirmation_receipt_actor_placeholder?: string;
  sleep_continuity_confirmation_receipt_command_requires_actor_substitution: boolean;
  sleep_continuity_confirmation_receipt_command_next_readback_route?: string;
  sleep_continuity_confirmation_receipt_command_receipt_id_readback_field?: string;
  sleep_continuity_confirmation_receipt_command_records_receipt: boolean;
  sleep_continuity_confirmation_receipt_command_writes_evidence: boolean;
  sleep_continuity_confirmation_receipt_command_marks_stage16_closed: boolean;
  sleep_continuity_confirmation_receipt_command_projection_only: boolean;
  sleep_continuity_confirmation_receipt_record_prerequisites_ready: boolean;
  sleep_continuity_confirmation_receipt_record_blockers: string[];
  sleep_continuity_confirmation_receipt_record_current_pre_sleep_evidence_path?: string;
  sleep_continuity_confirmation_receipt_record_actor?: string;
  sleep_continuity_confirmation_receipt_record_command_ready: boolean;
  sleep_continuity_confirmation_receipt_record_actor_ready: boolean;
  sleep_continuity_confirmation_receipt_record_records_receipt: boolean;
  sleep_continuity_confirmation_receipt_record_writes_evidence: boolean;
  sleep_continuity_confirmation_receipt_record_writes_runtime_readback: boolean;
  sleep_continuity_confirmation_receipt_record_marks_stage16_closed: boolean;
  sleep_continuity_confirmation_receipt_record_grants_execution_authority: boolean;
  sleep_continuity_confirmation_receipt_record_grants_mutation_authority: boolean;
  sleep_continuity_confirmation_receipt_readback_status?: string;
  sleep_continuity_confirmation_receipt_readback_ready: boolean;
  sleep_continuity_confirmation_receipt_latest_receipt_id?: string;
  sleep_continuity_confirmation_receipt_latest_decision?: string;
  sleep_continuity_confirmation_receipt_latest_matches_current_pre_sleep: boolean;
  sleep_continuity_confirmation_receipt_usable_for_receipt_backed_sequence: boolean;
  sleep_continuity_receipt_backed_sequence_ready: boolean;
  sleep_continuity_receipt_backed_sequence_blockers: string[];
  sleep_continuity_receipt_backed_sequence_requires_confirmation_receipt: boolean;
  sleep_continuity_receipt_backed_sequence_next_step?: string;
  sleep_continuity_receipt_backed_sequence_blocked_until_current_matching_confirmation_receipt: boolean;
  sleep_continuity_receipt_backed_sequence_current_matching_confirmation_receipt_required: boolean;
  sleep_continuity_receipt_backed_sequence_available_after_current_matching_confirmation_receipt: boolean;
  sleep_continuity_receipt_backed_sequence_hidden_until_confirmation_receipt: boolean;
  sleep_continuity_receipt_backed_sequence_runs_after_physical_sleep_resume_receipt_only: boolean;
  sleep_continuity_receipt_backed_sequence_post_receipt_handoff?: Record<string, unknown>;
  sleep_continuity_receipt_backed_sequence_writes_evidence_when_run: boolean;
  sleep_continuity_receipt_backed_sequence_writes_receipts_when_run: boolean;
  sleep_continuity_next_step?: string;
  ready_count: number;
  required_count: number;
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationLiveRuntimeReadbackCheck = {
  id: string;
  passed: boolean;
  receipt_ready: boolean;
  completion_evidence: boolean;
  status?: string;
  receipt_id?: string;
  proof_kind?: string;
  source_node_id?: string;
  paired_node_id?: string;
  trace_id?: string;
  evidence?: string;
};

export type FederationLiveRuntimeReadbacks = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  count: number;
  receipt_ready_count: number;
  ready_count: number;
  required_count: number;
  completion_eligible_readback_count: number;
  readback_receipts_ready: boolean;
  live_runtime_readback_ready: boolean;
  missing_readbacks: string[];
  checks: FederationLiveRuntimeReadbackCheck[];
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationCompletionReview = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  contract_readiness_ready: boolean;
  live_runtime_readback_ready: boolean;
  stage16_completion_review_ready: boolean;
  ready_to_close: boolean;
  stage_closure_decision_required: boolean;
  blockers: string[];
  ready_count: number;
  required_count: number;
  live_ready_count: number;
  live_required_count: number;
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationStage16ClosureReceipt = {
  receipt_id: string;
  actor?: string;
  decision?: string;
  completion_review_ready: boolean;
  stage16_completion_review_ready: boolean;
  live_runtime_readback_ready: boolean;
  stage16_closed_by_receipt: boolean;
  recorded_ts?: number;
};

export type FederationStage16ClosureDecisions = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  count: number;
  total: number;
  latest_receipt_id?: string;
  latest_decision?: string;
  receipt_readback_ready: boolean;
  stage16_closed_by_receipt: boolean;
  marks_runtime_stage_state: boolean;
  reads_receipts: boolean;
  writes_receipts: boolean;
  writes_registry: boolean;
  writes_memory: boolean;
  runs_tools: boolean;
  runs_shell: boolean;
  runs_git: boolean;
  launches_browser: boolean;
  captures_screen: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  latest_receipt?: FederationStage16ClosureReceipt;
  items: FederationStage16ClosureReceipt[];
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepResumeConfirmationReceipt = {
  receipt_id: string;
  actor?: string;
  decision?: string;
  operator_confirmed_sleep_resume: boolean;
  pre_sleep_evidence_path?: string;
  pre_sleep_recorded_ts?: number;
  continuity_record_id?: string;
  trace_id?: string;
  recorded_ts?: number;
};

export type FederationSleepResumeConfirmationOperatorStep = {
  id?: string;
  order: number;
  status?: string;
  method?: string;
  route?: string;
  command_field?: string;
  readback_field?: string;
  required_scope?: string;
  required_readback_field?: string;
  requires_actor_substitution: boolean;
  requires_current_receipt: boolean;
  writes_receipts_when_run: boolean;
  writes_evidence_when_run: boolean;
  marks_stage16_closed_when_run: boolean;
  operator_action_required: boolean;
  read_only_projection: boolean;
};

export type FederationSleepResumeConfirmations = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  count: number;
  total: number;
  latest_receipt_id?: string;
  latest_actor?: string;
  latest_decision?: string;
  latest_pre_sleep_evidence_path?: string;
  latest_recorded_ts?: number;
  receipt_readback_ready: boolean;
  current_pre_sleep_evidence_present: boolean;
  current_pre_sleep_evidence_path?: string;
  current_pre_sleep_recorded_ts?: number;
  current_pre_sleep_age_seconds: number;
  current_pre_sleep_freshness_state?: string;
  current_pre_sleep_age_guidance?: string;
  current_pre_sleep_recapture_recommended: boolean;
  current_pre_sleep_age_warning?: string;
  current_pre_sleep_age_guidance_threshold_seconds: number;
  confirmation_receipt_requested_actor?: string;
  confirmation_receipt_requested_actor_ready: boolean;
  latest_receipt_is_operator_confirmed: boolean;
  latest_receipt_matches_current_pre_sleep: boolean;
  latest_receipt_usable_for_receipt_backed_sequence: boolean;
  receipt_backed_sequence_ready: boolean;
  receipt_backed_sequence_blockers: string[];
  receipt_backed_sequence_command?: string;
  receipt_backed_sequence_copyable_command?: string;
  confirmation_receipt_command_ready: boolean;
  confirmation_receipt_actor?: string;
  confirmation_receipt_actor_bound: boolean;
  confirmation_receipt_actor_placeholder?: string;
  confirmation_receipt_command?: string;
  confirmation_receipt_copyable_command?: string;
  confirmation_receipt_command_requires_scope?: string;
  confirmation_receipt_command_requires_actor_substitution: boolean;
  confirmation_receipt_command_actor_scope?: string;
  confirmation_receipt_actor_readiness_route?: string;
  confirmation_receipt_actor_readiness_query_param?: string;
  confirmation_receipt_command_next_readback_route?: string;
  confirmation_receipt_command_receipt_id_readback_field?: string;
  confirmation_receipt_command_next_operator_step?: string;
  confirmation_receipt_operator_steps: FederationSleepResumeConfirmationOperatorStep[];
  confirmation_receipt_command_records_receipt: boolean;
  confirmation_receipt_command_writes_evidence: boolean;
  confirmation_receipt_command_marks_stage16_closed: boolean;
  confirmation_receipt_command_projection_only: boolean;
  receipt_backed_sequence_requires_confirmation_receipt: boolean;
  receipt_backed_sequence_writes_evidence_when_run: boolean;
  receipt_backed_sequence_writes_receipts_when_run: boolean;
  reads_receipts: boolean;
  writes_receipts: boolean;
  writes_evidence: boolean;
  writes_runtime_readback: boolean;
  marks_stage16_closed: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  latest_receipt?: FederationSleepResumeConfirmationReceipt;
  items: FederationSleepResumeConfirmationReceipt[];
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepResumeConfirmationVisibleCommands = {
  confirmation_receipt_copyable_command?: string;
  receipt_backed_sequence_copyable_command?: string;
};

export type FederationSleepResumeConfirmationActorReadinessVisibleCommands = {
  confirmation_receipt_copyable_command?: string;
  scope_remediation_copyable_command?: string;
};

export type FederationSleepResumeReceiptBackedSequenceVisibleCommands = {
  receipt_backed_sequence_copyable_command?: string;
};

export type FederationSleepResumeConfirmationRecordResponse = {
  ok: boolean;
  kind?: string;
  status?: string;
  source_id?: string;
  target?: string;
  receipt_id?: string;
  decision?: string;
  writes_receipt: boolean;
  writes_evidence: boolean;
  writes_runtime_readback: boolean;
  marks_stage16_closed: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  receipt?: FederationSleepResumeConfirmationReceipt;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepResumeReceiptRecordReadiness = {
  ready: boolean;
  disabled: boolean;
  blockers: string[];
  current_pre_sleep_evidence_path?: string;
  actor?: string;
  operator_acknowledged: boolean;
  receipt_backed_sequence_ready: boolean;
  command_ready: boolean;
  actor_ready: boolean;
  records_receipt: boolean;
  writes_evidence: boolean;
  writes_runtime_readback: boolean;
  marks_stage16_closed: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
};

export type FederationSleepResumeOperatorChecklistItem = {
  id?: string;
  status?: string;
  passed: boolean;
  evidence?: string;
  required_scope?: string;
  writes_receipt: boolean;
  writes_evidence: boolean;
  writes_runtime_readback: boolean;
  marks_stage16_closed: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  operator_action_required: boolean;
};

export type FederationSleepResumeOperatorChecklist = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  target?: string;
  actor?: string;
  requested_actor_ready: boolean;
  required_scope?: string;
  current_pre_sleep_evidence_present: boolean;
  current_pre_sleep_evidence_path?: string;
  current_pre_sleep_recorded_ts?: number;
  current_pre_sleep_age_seconds: number;
  current_pre_sleep_freshness_state?: string;
  current_pre_sleep_age_guidance?: string;
  current_pre_sleep_recapture_recommended: boolean;
  current_pre_sleep_age_warning?: string;
  current_pre_sleep_age_guidance_threshold_seconds: number;
  preconditions_ready: boolean;
  ready_to_record_after_operator_confirmation: boolean;
  current_pre_sleep_marker_fresh_for_confirmation: boolean;
  confirmation_receipt_safe_after_physical_sleep_resume: boolean;
  physical_confirmation_next_step?: string;
  operator_must_not_record_receipt_before_sleep_resume: boolean;
  operator_must_not_record_receipt_for_stale_pre_sleep_marker: boolean;
  physical_confirmation_guard?: Record<string, unknown>;
  operator_physical_confirmation_required: boolean;
  operator_physical_confirmation_recorded: boolean;
  latest_confirmation_receipt_id?: string;
  receipt_backed_sequence_ready: boolean;
  blockers: string[];
  operator_actions_remaining: string[];
  checklist: FederationSleepResumeOperatorChecklistItem[];
  confirmation_receipt_route?: string;
  confirmation_receipt_readback_route?: string;
  confirmation_receipt_actor_readiness_route?: string;
  confirmation_receipt_payload_contract?: Record<string, unknown>;
  confirmation_receipt_command_ready: boolean;
  confirmation_receipt_command_visible_after_physical_sleep_resume: boolean;
  confirmation_receipt_command_after_physical_sleep_resume?: string;
  confirmation_receipt_copyable_command_after_physical_sleep_resume?: string;
  confirmation_receipt_command_runs_after_physical_sleep_resume_only: boolean;
  confirmation_receipt_command_records_receipt: boolean;
  confirmation_receipt_command_writes_evidence: boolean;
  confirmation_receipt_command_marks_stage16_closed: boolean;
  confirmation_receipt_command_projection_only: boolean;
  records_receipt: boolean;
  writes_receipts: boolean;
  writes_evidence: boolean;
  writes_runtime_readback: boolean;
  marks_stage16_closed: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance?: Record<string, unknown>;
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepResumeReceiptBackedSequenceReadiness = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  target?: string;
  actor?: string;
  current_pre_sleep_evidence_present: boolean;
  current_pre_sleep_evidence_path?: string;
  current_pre_sleep_recorded_ts?: number;
  current_pre_sleep_age_seconds: number;
  current_pre_sleep_freshness_state?: string;
  current_pre_sleep_age_guidance?: string;
  current_pre_sleep_recapture_recommended: boolean;
  current_pre_sleep_age_warning?: string;
  current_pre_sleep_age_guidance_threshold_seconds: number;
  latest_receipt_id?: string;
  latest_decision?: string;
  latest_actor?: string;
  latest_pre_sleep_evidence_path?: string;
  latest_receipt_is_operator_confirmed: boolean;
  latest_receipt_matches_current_pre_sleep: boolean;
  latest_receipt_usable_for_receipt_backed_sequence: boolean;
  receipt_backed_sequence_ready: boolean;
  receipt_backed_sequence_blockers: string[];
  receipt_backed_sequence_command_visible: boolean;
  receipt_backed_sequence_command?: string;
  receipt_backed_sequence_copyable_command?: string;
  receipt_backed_sequence_requires_confirmation_receipt: boolean;
  receipt_backed_sequence_confirmation_receipt_id?: string;
  receipt_backed_sequence_operator_step?: FederationSleepResumeConfirmationOperatorStep;
  receipt_backed_sequence_next_step?: string;
  receipt_backed_sequence_blocked_until_current_matching_confirmation_receipt: boolean;
  receipt_backed_sequence_current_matching_confirmation_receipt_required: boolean;
  receipt_backed_sequence_available_after_current_matching_confirmation_receipt: boolean;
  receipt_backed_sequence_hidden_until_confirmation_receipt: boolean;
  receipt_backed_sequence_runs_after_physical_sleep_resume_receipt_only: boolean;
  post_receipt_handoff?: Record<string, unknown>;
  operator_action_required: boolean;
  writes_evidence_when_run: boolean;
  writes_receipts_when_run: boolean;
  marks_stage16_closed_when_run: boolean;
  projection_only: boolean;
  reads_receipts: boolean;
  writes_receipts: boolean;
  writes_evidence: boolean;
  writes_runtime_readback: boolean;
  marks_stage16_closed: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  confirmation_receipt_readback_route?: string;
  operator_checklist_route?: string;
  sleep_continuity_action_route?: string;
  governance?: Record<string, unknown>;
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepResumeConfirmationActorReadiness = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  target?: string;
  actor?: string;
  actor_present: boolean;
  actor_placeholder_rejected: boolean;
  required_scope?: string;
  target_method?: string;
  target_route?: string;
  readiness_route?: string;
  current_pre_sleep_evidence_present: boolean;
  current_pre_sleep_evidence_path?: string;
  permission_allowed: boolean;
  permission_reason?: string;
  confirmation_receipt_actor_ready: boolean;
  safe_to_use_in_confirmation_command: boolean;
  next_step?: string;
  confirmation_receipt_command_ready: boolean;
  confirmation_receipt_actor?: string;
  confirmation_receipt_actor_bound: boolean;
  confirmation_receipt_actor_placeholder?: string;
  confirmation_receipt_command?: string;
  confirmation_receipt_copyable_command?: string;
  confirmation_receipt_command_requires_scope?: string;
  confirmation_receipt_command_requires_actor_substitution: boolean;
  confirmation_receipt_command_actor_scope?: string;
  confirmation_receipt_actor_readiness_route?: string;
  confirmation_receipt_actor_readiness_query_param?: string;
  confirmation_receipt_command_next_readback_route?: string;
  confirmation_receipt_command_receipt_id_readback_field?: string;
  confirmation_receipt_command_next_operator_step?: string;
  confirmation_receipt_command_records_receipt: boolean;
  confirmation_receipt_command_writes_evidence: boolean;
  confirmation_receipt_command_marks_stage16_closed: boolean;
  confirmation_receipt_command_projection_only: boolean;
  scope_remediation_required: boolean;
  scope_remediation_command_ready: boolean;
  scope_remediation_command_visible: boolean;
  scope_remediation_env_var?: string;
  scope_remediation_actor?: string;
  scope_remediation_required_scope?: string;
  scope_remediation_policy_fragment?: Record<string, unknown>;
  scope_remediation_command?: string;
  scope_remediation_copyable_command?: string;
  scope_remediation_projection_only: boolean;
  scope_remediation_writes_receipts: boolean;
  scope_remediation_writes_evidence: boolean;
  scope_remediation_marks_stage16_closed: boolean;
  scope_remediation_grants_authority: boolean;
  scope_remediation_would_mutate_process_environment_if_run: boolean;
  reads_permission_gate: boolean;
  writes_receipt: boolean;
  writes_evidence: boolean;
  writes_runtime_readback: boolean;
  marks_stage16_closed: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepContinuityRunbookStep = {
  id: string;
  title?: string;
  command?: string;
  latest_evidence_path?: string;
  pre_sleep_evidence_path?: string;
  post_resume_evidence_path?: string;
  method?: string;
  route?: string;
  required_scope?: string;
  expected_output?: string;
  pre_sleep_evidence_required: boolean;
  pre_sleep_evidence_available: boolean;
  post_resume_evidence_required: boolean;
  post_resume_evidence_available: boolean;
  operator_action_required: boolean;
  operator_confirmation_required: boolean;
  operator_confirmation_requirements: string[];
  writes_evidence_when_run: boolean;
  writes_receipts_when_run: boolean;
  payload_contract?: Record<string, unknown>;
};

export type FederationSleepContinuitySelectedActionSummary = {
  selected_action_id?: string;
  current_ready_to_run: boolean;
  operator_confirmation_pending: boolean;
  post_confirmation_ready_to_capture: boolean;
  sleep_resume_confirmation_is_current_blocker: boolean;
  confirmation_blocker?: string;
  blocked_reason?: string;
};

export type FederationSleepContinuityRunbook = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  runbook_only: boolean;
  prerequisite_readback_ids: string[];
  prerequisite_readbacks_ready: boolean;
  sleep_continuity_readback_id?: string;
  sleep_continuity_ready: boolean;
  pre_sleep_evidence?: Record<string, unknown>;
  pre_sleep_evidence_ready: boolean;
  pre_sleep_age_seconds: number;
  pre_sleep_freshness_state?: string;
  current_pre_sleep_age_guidance?: string;
  current_pre_sleep_recapture_recommended: boolean;
  current_pre_sleep_age_warning?: string;
  current_pre_sleep_age_guidance_threshold_seconds: number;
  pre_sleep_recapture_recommended: boolean;
  pre_sleep_recapture_reason?: string;
  pre_sleep_recapture_command_ready: boolean;
  pre_sleep_recapture_command_visible: boolean;
  pre_sleep_recapture_command?: string;
  pre_sleep_recapture_copyable_command?: string;
  pre_sleep_recapture_expected_output?: string;
  pre_sleep_recapture_after_run_next_step?: string;
  pre_sleep_recapture_writes_evidence_when_run: boolean;
  pre_sleep_recapture_writes_receipts_when_run: boolean;
  pre_sleep_recapture_marks_stage16_closed_when_run: boolean;
  pre_sleep_recapture_projection_only: boolean;
  post_resume_evidence?: Record<string, unknown>;
  post_resume_evidence_ready: boolean;
  post_resume_evidence_conflict: boolean;
  ready_to_close: boolean;
  stage16_closed_by_receipt: boolean;
  missing_readbacks: string[];
  current_readback?: Record<string, unknown>;
  completion_review?: Record<string, unknown>;
  stage_closure_decision?: Record<string, unknown>;
  selected_action_summary?: FederationSleepContinuitySelectedActionSummary;
  steps: FederationSleepContinuityRunbookStep[];
  writes_evidence: boolean;
  writes_receipts: boolean;
  writes_registry: boolean;
  writes_memory: boolean;
  runs_tools: boolean;
  runs_shell: boolean;
  runs_git: boolean;
  launches_browser: boolean;
  captures_screen: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  marks_stage16_closed: boolean;
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepContinuityActionState =
  | "blocked_on_prior_live_readbacks"
  | "capture_pre_sleep_evidence"
  | "capture_post_resume_evidence"
  | "run_sleep_continuity_runtime_proof"
  | "record_stage16_closure_decision"
  | "stage16_closed";

export type FederationSleepContinuitySelectedActionReadiness = {
  status?: string;
  ready_to_run: boolean;
  run_blockers: string[];
  remaining_evidence_gates: string[];
  met_conditions: string[];
  operator_terminal_command_ready: boolean;
  operator_terminal_command_visible: boolean;
  command_validation: string[];
  command_validation_blockers: string[];
  next_operator_step?: string;
  selected_step_id?: string;
  pre_sleep_evidence_ready: boolean;
  post_resume_evidence_ready: boolean;
  post_resume_evidence_conflict: boolean;
  operator_confirmation_required: boolean;
  writes_evidence_when_run: boolean;
  writes_receipts_when_run: boolean;
};

export type FederationSleepContinuityOperatorTerminalInvocation = {
  status?: string;
  shell?: string;
  working_directory?: string;
  command?: string;
  copyable_command?: string;
  selected_step_id?: string;
  operator_confirmation_required: boolean;
  operator_confirmation_pending: boolean;
  copyable_after_operator_confirmation: boolean;
  copyable_command_visible: boolean;
  should_not_run_before_confirmation: boolean;
  must_run_after_sleep_resume: boolean;
  preconditions: string[];
  command_validation: string[];
  command_validation_blockers: string[];
  run_blockers: string[];
  ready_to_run: boolean;
  operator_terminal_command_ready: boolean;
  operator_terminal_command_visible: boolean;
  manual_execution_writes_evidence: boolean;
  manual_execution_writes_receipts: boolean;
  projection_only: boolean;
  projection_runs_shell: boolean;
  projection_writes_evidence: boolean;
  projection_writes_receipts: boolean;
  projection_grants_authority: boolean;
};

export type FederationSleepContinuityOperatorSleepResumeGate = {
  status?: string;
  selected_step_id?: string;
  confirmation_required: boolean;
  required_confirmation_requirements: string[];
  confirmation_blocker?: string;
  operator_confirmation_blocker_present: boolean;
  operator_confirmation_pending: boolean;
  current_ready_to_run: boolean;
  pre_sleep_evidence_present: boolean;
  pre_sleep_evidence_path?: string;
  pre_sleep_file_name?: string;
  pre_sleep_recorded_ts: number;
  pre_sleep_age_seconds: number;
  pre_sleep_freshness_state?: string;
  continuity_record_id?: string;
  trace_id?: string;
  post_resume_evidence_present: boolean;
  post_resume_evidence_status?: string;
  post_resume_evidence_conflict: boolean;
  post_resume_candidate_evidence_path?: string;
  expected_pre_sleep_evidence_path?: string;
  candidate_pre_sleep_evidence_path?: string;
  must_sleep_after_pre_sleep_recorded_ts: boolean;
  must_resume_before_post_resume_capture: boolean;
  post_resume_capture_allowed_after_operator_confirmation: boolean;
  post_confirmation_ready_to_capture: boolean;
  sleep_resume_confirmation_is_current_blocker: boolean;
  operator_terminal_command_ready: boolean;
  operator_terminal_command_visible: boolean;
  ready_after_operator_confirmation: boolean;
  elapsed_time_is_not_confirmation: boolean;
  does_not_infer_sleep_from_delay: boolean;
  projection_only: boolean;
  projection_runs_shell: boolean;
  projection_writes_evidence: boolean;
  projection_writes_receipts: boolean;
  projection_marks_stage16_closed: boolean;
};

export type FederationSleepContinuityOperatorConfirmationHandoff = {
  status?: string;
  selected_step_id?: string;
  required_confirmation_requirements: string[];
  operator_confirmation_source_required?: string;
  operator_confirmation_pending: boolean;
  confirmation_blocker?: string;
  pre_sleep_evidence_path?: string;
  pre_sleep_recorded_ts: number;
  must_sleep_after_pre_sleep_recorded_ts: boolean;
  must_resume_before_post_resume_capture: boolean;
  post_resume_capture_command_ready_after_confirmation: boolean;
  post_resume_capture_command_visible: boolean;
  post_resume_capture_command?: string;
  post_resume_capture_copyable_command?: string;
  post_resume_sequence_available_after_confirmation: boolean;
  post_resume_sequence_command_visible: boolean;
  post_resume_sequence_command?: string;
  post_resume_sequence_copyable_command?: string;
  post_resume_receipt_backed_sequence_command?: string;
  post_resume_receipt_backed_sequence_command_visible: boolean;
  post_resume_receipt_backed_sequence_copyable_command?: string;
  post_resume_receipt_backed_sequence_requires_confirmation_receipt: boolean;
  post_resume_receipt_backed_sequence_confirmation_receipt_id_placeholder?: string;
  post_resume_sequence_writes_evidence_when_run: boolean;
  post_resume_sequence_writes_receipts_when_run: boolean;
  confirmation_receipt_route?: string;
  confirmation_receipt_readback_route?: string;
  confirmation_receipt_required_scope?: string;
  confirmation_receipt_requested_actor?: string;
  confirmation_receipt_requested_actor_ready: boolean;
  confirmation_receipt_payload_contract?: Record<string, unknown>;
  confirmation_receipt_command_ready: boolean;
  confirmation_receipt_actor?: string;
  confirmation_receipt_actor_bound: boolean;
  confirmation_receipt_actor_placeholder?: string;
  confirmation_receipt_command?: string;
  confirmation_receipt_copyable_command?: string;
  confirmation_receipt_command_visible: boolean;
  confirmation_receipt_command_requires_scope?: string;
  confirmation_receipt_command_requires_actor_substitution: boolean;
  confirmation_receipt_command_actor_scope?: string;
  confirmation_receipt_actor_readiness_route?: string;
  confirmation_receipt_actor_readiness_query_param?: string;
  confirmation_receipt_command_next_readback_route?: string;
  confirmation_receipt_command_receipt_id_readback_field?: string;
  confirmation_receipt_command_next_operator_step?: string;
  confirmation_receipt_operator_steps: FederationSleepResumeConfirmationOperatorStep[];
  confirmation_receipt_command_records_receipt: boolean;
  confirmation_receipt_command_writes_evidence: boolean;
  confirmation_receipt_command_marks_stage16_closed: boolean;
  confirmation_receipt_command_projection_only: boolean;
  confirmation_receipt_available_before_sequence: boolean;
  confirmation_receipt_required_for_receipt_backed_workflow: boolean;
  confirmation_receipt_writes_receipts: boolean;
  confirmation_receipt_writes_evidence: boolean;
  confirmation_receipt_marks_stage16_closed: boolean;
  should_not_run_before_confirmation: boolean;
  operator_terminal_command_ready: boolean;
  operator_terminal_command_visible: boolean;
  readback_routes: Record<string, string>;
  proof_boundary: Record<string, boolean>;
};

export type FederationSleepContinuityAfterManualExecutionReadback = {
  status?: string;
  selected_step_id?: string;
  expected_output?: string;
  operator_terminal_command_ready: boolean;
  operator_terminal_command_visible: boolean;
  ready_to_run: boolean;
  run_blockers: string[];
  operator_confirmation_pending: boolean;
  should_not_expect_success_before_confirmation: boolean;
  refresh_routes: Record<string, string>;
  manual_execution_writes_evidence: boolean;
  manual_execution_writes_receipts: boolean;
  projection_only: boolean;
  projection_runs_shell: boolean;
  projection_writes_evidence: boolean;
  projection_writes_receipts: boolean;
  projection_marks_stage16_closed: boolean;
  expected_artifact_root?: string;
  expected_artifact_prefix?: string;
  expected_artifact_kind?: string;
  expected_status_after_success?: string;
  expected_action_status_after_success?: string;
  expected_selected_step_id_after_success?: string;
  expected_next_step_after_success?: string;
};

export type FederationSleepContinuityPresentation = {
  state: FederationSleepContinuityActionState;
  status_label: string;
  selected_step_id?: string;
  selected_step_title?: string;
  primary_command?: string;
  primary_route?: string;
  readback_route?: string;
  runbook_route?: string;
  closure_decision_route?: string;
  method?: string;
  required_scope?: string;
  evidence_path?: string;
  pre_sleep_evidence_path?: string;
  post_resume_evidence_path?: string;
  blockers: string[];
  prior_live_readback_blockers: string[];
  pre_sleep_evidence_ready: boolean;
  post_resume_evidence_ready: boolean;
  post_resume_evidence_conflict: boolean;
  sleep_continuity_ready: boolean;
  ready_to_close: boolean;
  stage16_closed_by_receipt: boolean;
  operator_action_required: boolean;
  operator_confirmation_required: boolean;
  operator_confirmation_requirements: string[];
  current_ready_to_run: boolean;
  operator_confirmation_pending: boolean;
  post_confirmation_ready_to_capture: boolean;
  sleep_resume_confirmation_is_current_blocker: boolean;
  selected_action_readiness?: FederationSleepContinuitySelectedActionReadiness;
  operator_terminal_invocation?: FederationSleepContinuityOperatorTerminalInvocation;
  operator_sleep_resume_gate?: FederationSleepContinuityOperatorSleepResumeGate;
  operator_confirmation_handoff?: FederationSleepContinuityOperatorConfirmationHandoff;
  after_manual_execution_readback?: FederationSleepContinuityAfterManualExecutionReadback;
  pre_sleep_recapture_recommended: boolean;
  pre_sleep_recapture_command_visible: boolean;
  pre_sleep_recapture_copyable_command?: string;
  writes_evidence_when_run: boolean;
  writes_receipts_when_run: boolean;
  expected_output?: string;
  mutation_available_from_ui: boolean;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepContinuityVisibleOperatorCommands = {
  blocked_by_pending_confirmation: boolean;
  primary_command?: string;
  operator_terminal_copyable_command?: string;
  post_resume_capture_copyable_command?: string;
  post_resume_sequence_copyable_command?: string;
  post_resume_receipt_backed_sequence_copyable_command?: string;
  confirmation_receipt_copyable_command?: string;
  pre_sleep_recapture_copyable_command?: string;
};

export type FederationSleepContinuityActionReadback = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: FederationSleepContinuityActionState | string;
  action_projection_only: boolean;
  selected_step_id?: string;
  selected_step_title?: string;
  selected_action?: FederationSleepContinuityRunbookStep;
  primary_command?: string;
  primary_route?: string;
  method?: string;
  required_scope?: string;
  expected_output?: string;
  evidence_path?: string;
  pre_sleep_evidence_path?: string;
  post_resume_evidence_path?: string;
  blockers: string[];
  prior_live_readback_blockers: string[];
  pre_sleep_evidence_ready: boolean;
  pre_sleep_age_seconds: number;
  pre_sleep_freshness_state?: string;
  current_pre_sleep_age_guidance?: string;
  current_pre_sleep_recapture_recommended: boolean;
  current_pre_sleep_age_warning?: string;
  current_pre_sleep_age_guidance_threshold_seconds: number;
  pre_sleep_recapture_recommended: boolean;
  pre_sleep_recapture_reason?: string;
  pre_sleep_recapture_command_ready: boolean;
  pre_sleep_recapture_command_visible: boolean;
  pre_sleep_recapture_command?: string;
  pre_sleep_recapture_copyable_command?: string;
  pre_sleep_recapture_expected_output?: string;
  pre_sleep_recapture_after_run_next_step?: string;
  pre_sleep_recapture_writes_evidence_when_run: boolean;
  pre_sleep_recapture_writes_receipts_when_run: boolean;
  pre_sleep_recapture_marks_stage16_closed_when_run: boolean;
  pre_sleep_recapture_projection_only: boolean;
  post_resume_evidence_ready: boolean;
  post_resume_evidence_conflict: boolean;
  sleep_continuity_ready: boolean;
  ready_to_close: boolean;
  stage16_closed_by_receipt: boolean;
  operator_action_required: boolean;
  operator_confirmation_required: boolean;
  operator_confirmation_requirements: string[];
  current_ready_to_run: boolean;
  operator_confirmation_pending: boolean;
  post_confirmation_ready_to_capture: boolean;
  sleep_resume_confirmation_is_current_blocker: boolean;
  selected_action_readiness?: FederationSleepContinuitySelectedActionReadiness;
  operator_terminal_invocation?: FederationSleepContinuityOperatorTerminalInvocation;
  operator_sleep_resume_gate?: FederationSleepContinuityOperatorSleepResumeGate;
  operator_confirmation_handoff?: FederationSleepContinuityOperatorConfirmationHandoff;
  after_manual_execution_readback?: FederationSleepContinuityAfterManualExecutionReadback;
  writes_evidence_when_run: boolean;
  writes_receipts_when_run: boolean;
  mutation_available_from_ui: boolean;
  writes_evidence: boolean;
  writes_receipts: boolean;
  writes_registry: boolean;
  writes_memory: boolean;
  runs_tools: boolean;
  runs_shell: boolean;
  runs_git: boolean;
  launches_browser: boolean;
  captures_screen: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  marks_stage16_closed: boolean;
  routes: Record<string, string>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
};

export type FederationListResponse<T> = { items: T[] };

export class FederationApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown },
  ) {
    super(message);
    this.name = "FederationApiError";
    this.status = opts?.status;
    this.url = opts?.url;
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

function optionalString(v: unknown): string | undefined {
  const text = safeString(v);
  return text || undefined;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function normalizeTs(ts: number): number {
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : ts;
}

function safeBoolean(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function stringList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map((x) => safeString(x)).filter((x) => x.length > 0);
}

function federationMutationErrorMessage(json: FederationSleepResumeConfirmationRecordResponse, fallback: string): string {
  return json.status === "denied" || json.status === "blocked"
    ? `${fallback} Status: ${json.status}.`
    : fallback;
}

function assertFederationMutationAllowed(json: FederationSleepResumeConfirmationRecordResponse, fallback: string): void {
  if (json.ok === false || json.status === "denied" || json.status === "blocked") {
    throw new FederationApiError(federationMutationErrorMessage(json, fallback));
  }
}

function stringRecord(v: unknown): Record<string, string> {
  if (!isRecord(v)) return {};
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(v)) {
    const safeKey = safeString(key);
    const safeValue = safeString(value);
    if (safeKey && safeValue) out[safeKey] = safeValue;
  }
  return out;
}

function booleanRecord(v: unknown): Record<string, boolean> {
  if (!isRecord(v)) return {};
  const out: Record<string, boolean> = {};
  for (const [key, value] of Object.entries(v)) {
    const safeKey = safeString(key);
    if (safeKey && typeof value === "boolean") out[safeKey] = value;
  }
  return out;
}

function parseFederationSleepContinuitySelectedActionReadiness(
  raw: unknown,
): FederationSleepContinuitySelectedActionReadiness | undefined {
  if (!isRecord(raw)) return undefined;
  return {
    status: optionalString(raw.status),
    ready_to_run: safeBoolean(raw.ready_to_run),
    run_blockers: stringList(raw.run_blockers),
    remaining_evidence_gates: stringList(raw.remaining_evidence_gates),
    met_conditions: stringList(raw.met_conditions),
    operator_terminal_command_ready: safeBoolean(raw.operator_terminal_command_ready),
    operator_terminal_command_visible: safeBoolean(raw.operator_terminal_command_visible),
    command_validation: stringList(raw.command_validation),
    command_validation_blockers: stringList(raw.command_validation_blockers),
    next_operator_step: optionalString(raw.next_operator_step),
    selected_step_id: optionalString(raw.selected_step_id),
    pre_sleep_evidence_ready: safeBoolean(raw.pre_sleep_evidence_ready),
    post_resume_evidence_ready: safeBoolean(raw.post_resume_evidence_ready),
    post_resume_evidence_conflict: safeBoolean(raw.post_resume_evidence_conflict),
    operator_confirmation_required: safeBoolean(raw.operator_confirmation_required),
    writes_evidence_when_run: safeBoolean(raw.writes_evidence_when_run),
    writes_receipts_when_run: safeBoolean(raw.writes_receipts_when_run),
  };
}

function parseFederationSleepContinuityOperatorTerminalInvocation(
  raw: unknown,
): FederationSleepContinuityOperatorTerminalInvocation | undefined {
  if (!isRecord(raw)) return undefined;
  return {
    status: optionalString(raw.status),
    shell: optionalString(raw.shell),
    working_directory: optionalString(raw.working_directory),
    command: optionalString(raw.command),
    copyable_command: optionalString(raw.copyable_command),
    selected_step_id: optionalString(raw.selected_step_id),
    operator_confirmation_required: safeBoolean(raw.operator_confirmation_required),
    operator_confirmation_pending: safeBoolean(raw.operator_confirmation_pending),
    copyable_after_operator_confirmation: safeBoolean(raw.copyable_after_operator_confirmation),
    copyable_command_visible: safeBoolean(raw.copyable_command_visible),
    should_not_run_before_confirmation: safeBoolean(raw.should_not_run_before_confirmation),
    must_run_after_sleep_resume: safeBoolean(raw.must_run_after_sleep_resume),
    preconditions: stringList(raw.preconditions),
    command_validation: stringList(raw.command_validation),
    command_validation_blockers: stringList(raw.command_validation_blockers),
    run_blockers: stringList(raw.run_blockers),
    ready_to_run: safeBoolean(raw.ready_to_run),
    operator_terminal_command_ready: safeBoolean(raw.operator_terminal_command_ready),
    operator_terminal_command_visible: safeBoolean(raw.operator_terminal_command_visible),
    manual_execution_writes_evidence: safeBoolean(raw.manual_execution_writes_evidence),
    manual_execution_writes_receipts: safeBoolean(raw.manual_execution_writes_receipts),
    projection_only: safeBoolean(raw.projection_only),
    projection_runs_shell: safeBoolean(raw.projection_runs_shell),
    projection_writes_evidence: safeBoolean(raw.projection_writes_evidence),
    projection_writes_receipts: safeBoolean(raw.projection_writes_receipts),
    projection_grants_authority: safeBoolean(raw.projection_grants_authority),
  };
}

function parseFederationSleepContinuityOperatorSleepResumeGate(
  raw: unknown,
): FederationSleepContinuityOperatorSleepResumeGate | undefined {
  if (!isRecord(raw)) return undefined;
  return {
    status: optionalString(raw.status),
    selected_step_id: optionalString(raw.selected_step_id),
    confirmation_required: safeBoolean(raw.confirmation_required),
    required_confirmation_requirements: stringList(raw.required_confirmation_requirements),
    confirmation_blocker: optionalString(raw.confirmation_blocker),
    operator_confirmation_blocker_present: safeBoolean(raw.operator_confirmation_blocker_present),
    operator_confirmation_pending: safeBoolean(raw.operator_confirmation_pending),
    current_ready_to_run: safeBoolean(raw.current_ready_to_run),
    pre_sleep_evidence_present: safeBoolean(raw.pre_sleep_evidence_present),
    pre_sleep_evidence_path: optionalString(raw.pre_sleep_evidence_path),
    pre_sleep_file_name: optionalString(raw.pre_sleep_file_name),
    pre_sleep_recorded_ts: safeNumber(raw.pre_sleep_recorded_ts, 0),
    pre_sleep_age_seconds: safeNumber(raw.pre_sleep_age_seconds, 0),
    pre_sleep_freshness_state: optionalString(raw.pre_sleep_freshness_state),
    continuity_record_id: optionalString(raw.continuity_record_id),
    trace_id: optionalString(raw.trace_id),
    post_resume_evidence_present: safeBoolean(raw.post_resume_evidence_present),
    post_resume_evidence_status: optionalString(raw.post_resume_evidence_status),
    post_resume_evidence_conflict: safeBoolean(raw.post_resume_evidence_conflict),
    post_resume_candidate_evidence_path: optionalString(raw.post_resume_candidate_evidence_path),
    expected_pre_sleep_evidence_path: optionalString(raw.expected_pre_sleep_evidence_path),
    candidate_pre_sleep_evidence_path: optionalString(raw.candidate_pre_sleep_evidence_path),
    must_sleep_after_pre_sleep_recorded_ts: safeBoolean(raw.must_sleep_after_pre_sleep_recorded_ts),
    must_resume_before_post_resume_capture: safeBoolean(raw.must_resume_before_post_resume_capture),
    post_resume_capture_allowed_after_operator_confirmation: safeBoolean(
      raw.post_resume_capture_allowed_after_operator_confirmation,
    ),
    post_confirmation_ready_to_capture: safeBoolean(raw.post_confirmation_ready_to_capture),
    sleep_resume_confirmation_is_current_blocker: safeBoolean(raw.sleep_resume_confirmation_is_current_blocker),
    operator_terminal_command_ready: safeBoolean(raw.operator_terminal_command_ready),
    operator_terminal_command_visible: safeBoolean(raw.operator_terminal_command_visible),
    ready_after_operator_confirmation: safeBoolean(raw.ready_after_operator_confirmation),
    elapsed_time_is_not_confirmation: safeBoolean(raw.elapsed_time_is_not_confirmation),
    does_not_infer_sleep_from_delay: safeBoolean(raw.does_not_infer_sleep_from_delay),
    projection_only: safeBoolean(raw.projection_only),
    projection_runs_shell: safeBoolean(raw.projection_runs_shell),
    projection_writes_evidence: safeBoolean(raw.projection_writes_evidence),
    projection_writes_receipts: safeBoolean(raw.projection_writes_receipts),
    projection_marks_stage16_closed: safeBoolean(raw.projection_marks_stage16_closed),
  };
}

function parseFederationSleepContinuityOperatorConfirmationHandoff(
  raw: unknown,
): FederationSleepContinuityOperatorConfirmationHandoff | undefined {
  if (!isRecord(raw)) return undefined;
  return {
    status: optionalString(raw.status),
    selected_step_id: optionalString(raw.selected_step_id),
    required_confirmation_requirements: stringList(raw.required_confirmation_requirements),
    operator_confirmation_source_required: optionalString(raw.operator_confirmation_source_required),
    operator_confirmation_pending: safeBoolean(raw.operator_confirmation_pending),
    confirmation_blocker: optionalString(raw.confirmation_blocker),
    pre_sleep_evidence_path: optionalString(raw.pre_sleep_evidence_path),
    pre_sleep_recorded_ts: safeNumber(raw.pre_sleep_recorded_ts, 0),
    must_sleep_after_pre_sleep_recorded_ts: safeBoolean(raw.must_sleep_after_pre_sleep_recorded_ts),
    must_resume_before_post_resume_capture: safeBoolean(raw.must_resume_before_post_resume_capture),
    post_resume_capture_command_ready_after_confirmation: safeBoolean(
      raw.post_resume_capture_command_ready_after_confirmation,
    ),
    post_resume_capture_command_visible: safeBoolean(raw.post_resume_capture_command_visible),
    post_resume_capture_command: optionalString(raw.post_resume_capture_command),
    post_resume_capture_copyable_command: optionalString(raw.post_resume_capture_copyable_command),
    post_resume_sequence_available_after_confirmation: safeBoolean(
      raw.post_resume_sequence_available_after_confirmation,
    ),
    post_resume_sequence_command_visible: safeBoolean(raw.post_resume_sequence_command_visible),
    post_resume_sequence_command: optionalString(raw.post_resume_sequence_command),
    post_resume_sequence_copyable_command: optionalString(raw.post_resume_sequence_copyable_command),
    post_resume_receipt_backed_sequence_command: optionalString(raw.post_resume_receipt_backed_sequence_command),
    post_resume_receipt_backed_sequence_command_visible: safeBoolean(
      raw.post_resume_receipt_backed_sequence_command_visible,
    ),
    post_resume_receipt_backed_sequence_copyable_command: optionalString(
      raw.post_resume_receipt_backed_sequence_copyable_command,
    ),
    post_resume_receipt_backed_sequence_requires_confirmation_receipt: safeBoolean(
      raw.post_resume_receipt_backed_sequence_requires_confirmation_receipt,
    ),
    post_resume_receipt_backed_sequence_confirmation_receipt_id_placeholder: optionalString(
      raw.post_resume_receipt_backed_sequence_confirmation_receipt_id_placeholder,
    ),
    post_resume_sequence_writes_evidence_when_run: safeBoolean(raw.post_resume_sequence_writes_evidence_when_run),
    post_resume_sequence_writes_receipts_when_run: safeBoolean(raw.post_resume_sequence_writes_receipts_when_run),
    confirmation_receipt_route: optionalString(raw.confirmation_receipt_route),
    confirmation_receipt_readback_route: optionalString(raw.confirmation_receipt_readback_route),
    confirmation_receipt_required_scope: optionalString(raw.confirmation_receipt_required_scope),
    confirmation_receipt_requested_actor: optionalString(raw.confirmation_receipt_requested_actor),
    confirmation_receipt_requested_actor_ready: safeBoolean(raw.confirmation_receipt_requested_actor_ready),
    confirmation_receipt_payload_contract: isRecord(raw.confirmation_receipt_payload_contract)
      ? raw.confirmation_receipt_payload_contract
      : undefined,
    confirmation_receipt_command_ready: safeBoolean(raw.confirmation_receipt_command_ready),
    confirmation_receipt_actor: optionalString(raw.confirmation_receipt_actor),
    confirmation_receipt_actor_bound: safeBoolean(raw.confirmation_receipt_actor_bound),
    confirmation_receipt_actor_placeholder: optionalString(raw.confirmation_receipt_actor_placeholder),
    confirmation_receipt_command: optionalString(raw.confirmation_receipt_command),
    confirmation_receipt_copyable_command: optionalString(raw.confirmation_receipt_copyable_command),
    confirmation_receipt_command_visible: safeBoolean(raw.confirmation_receipt_command_visible),
    confirmation_receipt_command_requires_scope: optionalString(raw.confirmation_receipt_command_requires_scope),
    confirmation_receipt_command_requires_actor_substitution: safeBoolean(
      raw.confirmation_receipt_command_requires_actor_substitution,
    ),
    confirmation_receipt_command_actor_scope: optionalString(raw.confirmation_receipt_command_actor_scope),
    confirmation_receipt_actor_readiness_route: optionalString(raw.confirmation_receipt_actor_readiness_route),
    confirmation_receipt_actor_readiness_query_param: optionalString(
      raw.confirmation_receipt_actor_readiness_query_param,
    ),
    confirmation_receipt_command_next_readback_route: optionalString(
      raw.confirmation_receipt_command_next_readback_route,
    ),
    confirmation_receipt_command_receipt_id_readback_field: optionalString(
      raw.confirmation_receipt_command_receipt_id_readback_field,
    ),
    confirmation_receipt_command_next_operator_step: optionalString(
      raw.confirmation_receipt_command_next_operator_step,
    ),
    confirmation_receipt_operator_steps: Array.isArray(raw.confirmation_receipt_operator_steps)
      ? raw.confirmation_receipt_operator_steps
          .map(parseFederationSleepResumeConfirmationOperatorStep)
          .filter((x): x is FederationSleepResumeConfirmationOperatorStep => x !== null)
      : [],
    confirmation_receipt_command_records_receipt: safeBoolean(raw.confirmation_receipt_command_records_receipt),
    confirmation_receipt_command_writes_evidence: safeBoolean(raw.confirmation_receipt_command_writes_evidence),
    confirmation_receipt_command_marks_stage16_closed: safeBoolean(raw.confirmation_receipt_command_marks_stage16_closed),
    confirmation_receipt_command_projection_only: safeBoolean(raw.confirmation_receipt_command_projection_only),
    confirmation_receipt_available_before_sequence: safeBoolean(raw.confirmation_receipt_available_before_sequence),
    confirmation_receipt_required_for_receipt_backed_workflow: safeBoolean(
      raw.confirmation_receipt_required_for_receipt_backed_workflow,
    ),
    confirmation_receipt_writes_receipts: safeBoolean(raw.confirmation_receipt_writes_receipts),
    confirmation_receipt_writes_evidence: safeBoolean(raw.confirmation_receipt_writes_evidence),
    confirmation_receipt_marks_stage16_closed: safeBoolean(raw.confirmation_receipt_marks_stage16_closed),
    should_not_run_before_confirmation: safeBoolean(raw.should_not_run_before_confirmation),
    operator_terminal_command_ready: safeBoolean(raw.operator_terminal_command_ready),
    operator_terminal_command_visible: safeBoolean(raw.operator_terminal_command_visible),
    readback_routes: stringRecord(raw.readback_routes),
    proof_boundary: booleanRecord(raw.proof_boundary),
  };
}

function parseFederationSleepContinuityAfterManualExecutionReadback(
  raw: unknown,
): FederationSleepContinuityAfterManualExecutionReadback | undefined {
  if (!isRecord(raw)) return undefined;
  return {
    status: optionalString(raw.status),
    selected_step_id: optionalString(raw.selected_step_id),
    expected_output: optionalString(raw.expected_output),
    operator_terminal_command_ready: safeBoolean(raw.operator_terminal_command_ready),
    operator_terminal_command_visible: safeBoolean(raw.operator_terminal_command_visible),
    ready_to_run: safeBoolean(raw.ready_to_run),
    run_blockers: stringList(raw.run_blockers),
    operator_confirmation_pending: safeBoolean(raw.operator_confirmation_pending),
    should_not_expect_success_before_confirmation: safeBoolean(raw.should_not_expect_success_before_confirmation),
    refresh_routes: stringRecord(raw.refresh_routes),
    manual_execution_writes_evidence: safeBoolean(raw.manual_execution_writes_evidence),
    manual_execution_writes_receipts: safeBoolean(raw.manual_execution_writes_receipts),
    projection_only: safeBoolean(raw.projection_only),
    projection_runs_shell: safeBoolean(raw.projection_runs_shell),
    projection_writes_evidence: safeBoolean(raw.projection_writes_evidence),
    projection_writes_receipts: safeBoolean(raw.projection_writes_receipts),
    projection_marks_stage16_closed: safeBoolean(raw.projection_marks_stage16_closed),
    expected_artifact_root: optionalString(raw.expected_artifact_root),
    expected_artifact_prefix: optionalString(raw.expected_artifact_prefix),
    expected_artifact_kind: optionalString(raw.expected_artifact_kind),
    expected_status_after_success: optionalString(raw.expected_status_after_success),
    expected_action_status_after_success: optionalString(raw.expected_action_status_after_success),
    expected_selected_step_id_after_success: optionalString(raw.expected_selected_step_id_after_success),
    expected_next_step_after_success: optionalString(raw.expected_next_step_after_success),
  };
}

function buildQuery(params: Record<string, unknown>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (typeof v === "string" && v.trim() === "") continue;

    if (Array.isArray(v)) {
      const joined = v.map((x) => String(x)).filter((s) => s.length > 0).join(",");
      if (joined) usp.set(k, joined);
      continue;
    }

    usp.set(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

async function readTextSnippet(res: Response, maxChars = 2048): Promise<string> {
  try {
    const txt = await res.text();
    return txt.length > maxChars ? `${txt.slice(0, maxChars)}…` : txt;
  } catch {
    return "";
  }
}

type TimeoutMergedFetchInit = RequestInit & { timeoutMs?: number };

async function fetchWithTimeout(url: string, init?: TimeoutMergedFetchInit): Promise<Response> {
  const { timeoutMs = 20_000, signal: externalSignal, ...fetchInit } = init ?? {};

  const controller = new AbortController();

  let timeoutId: number | null = null;
  if (timeoutMs > 0) {
    timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  }

  const onExternalAbort = () => controller.abort();

  if (externalSignal) {
    if (externalSignal.aborted) onExternalAbort();
    else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
  }

  try {
    const headers = new Headers(fetchInit.headers ?? undefined);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (fetchInit.body !== undefined && fetchInit.body !== null) {
      if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    }

    return await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new FederationApiError("Federation request aborted/timed out", { url, cause: err });
    }
    throw new FederationApiError("Federation request failed", { url, cause: err });
  } finally {
    if (timeoutId !== null) window.clearTimeout(timeoutId);
    if (externalSignal && !externalSignal.aborted) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }
}

async function fetchJson(url: string, init?: TimeoutMergedFetchInit): Promise<unknown> {
  const res = await fetchWithTimeout(url, init);

  if (!res.ok) {
    const snippet = await readTextSnippet(res);
    throw new FederationApiError(`HTTP ${res.status} for federation request`, {
      status: res.status,
      url,
      bodySnippet: snippet,
    });
  }

  return await res.json();
}

function parseInstance(raw: unknown): FederationInstance | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, safeString(raw.instance_id, ""));
  if (!id) return null;

  const inst: FederationInstance = { id };

  const name = safeString(raw.name, "");
  if (name) inst.name = name;

  const status = safeString(raw.status, "");
  if (status) inst.status = status;

  const endpoint = safeString(raw.endpoint, safeString(raw.url, ""));
  if (endpoint) inst.endpoint = endpoint;

  const region = safeString(raw.region, "");
  if (region) inst.region = region;

  const role = safeString(raw.role, "");
  if (role) inst.role = role;

  const firstSeen = safeNumber(raw.first_seen_ts, 0);
  if (firstSeen > 0) inst.first_seen_ts = normalizeTs(firstSeen);

  const lastSeen = safeNumber(raw.last_seen_ts, 0);
  if (lastSeen > 0) inst.last_seen_ts = normalizeTs(lastSeen);

  if (Array.isArray(raw.capabilities)) {
    const caps = (raw.capabilities as unknown[]).map((x) => safeString(x)).filter((x) => x.length > 0);
    if (caps.length) inst.capabilities = caps;
  }

  const trust = safeNumber(raw.trust_level, NaN);
  if (Number.isFinite(trust)) inst.trust_level = trust;

  if (typeof raw.requires_approval === "boolean") inst.requires_approval = raw.requires_approval;

  if (Array.isArray(raw.tags)) {
    const tags = (raw.tags as unknown[]).map((x) => safeString(x)).filter((x) => x.length > 0);
    if (tags.length) inst.tags = tags;
  }

  if (isRecord(raw.meta)) inst.meta = raw.meta;

  return inst;
}

function parseInstanceDetail(raw: unknown): FederationInstanceDetail | null {
  if (!isRecord(raw)) return null;

  const baseRaw = isRecord(raw.item) ? raw.item : raw;
  const base = parseInstance(baseRaw);
  if (!base) return null;

  const detail: FederationInstanceDetail = { ...base };

  const health = (raw as Record<string, unknown>).health;
  if (isRecord(health)) detail.health = health;

  const inventory = (raw as Record<string, unknown>).inventory;
  if (isRecord(inventory)) detail.inventory = inventory;

  return detail;
}

function parseDelegation(raw: unknown): FederationDelegation | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const ts = safeNumber(raw.ts, safeNumber(raw.created_ts, 0));
  const d: FederationDelegation = { id, ts: ts ? normalizeTs(ts) : 0 };

  const from = safeString(raw.from, safeString(raw.from_instance_id, ""));
  if (from) d.from = from;

  const to = safeString(raw.to, safeString(raw.to_instance_id, ""));
  if (to) d.to = to;

  const scope = safeString(raw.scope, safeString(raw.scope_id, ""));
  if (scope) d.scope = scope;

  const status = safeString(raw.status, "");
  if (status) d.status = status;

  const reason = safeString(raw.reason, "");
  if (reason) d.reason = reason;

  if (isRecord(raw.meta)) d.meta = raw.meta;

  return d;
}

function parseConsensusLog(raw: unknown): ConsensusLogEntry | null {
  if (!isRecord(raw)) return null;

  const ts = safeNumber(raw.ts, safeNumber(raw.created_ts, 0));
  if (!ts) return null;

  const e: ConsensusLogEntry = { ts: normalizeTs(ts) };

  const id = safeString(raw.id, "");
  if (id) e.id = id;

  const level = safeString(raw.level, safeString(raw.severity, ""));
  if (level) e.level = level;

  const kind = safeString(raw.kind, "");
  if (kind) e.kind = kind;

  const instanceId = safeString(raw.instance_id, "");
  if (instanceId) e.instance_id = instanceId;

  const term = safeNumber(raw.term, NaN);
  if (Number.isFinite(term)) e.term = term;

  const index = safeNumber(raw.index, NaN);
  if (Number.isFinite(index)) e.index = index;

  const msg = safeString(raw.message, safeString(raw.msg, ""));
  if (msg) e.message = msg;

  if (isRecord(raw.meta)) e.meta = raw.meta;

  return e;
}

function parseSharedKnowledge(raw: unknown): SharedKnowledgeItem | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const item: SharedKnowledgeItem = { id };

  const ts = safeNumber(raw.ts, safeNumber(raw.created_ts, 0));
  if (ts > 0) item.ts = normalizeTs(ts);

  const kind = safeString(raw.kind, "");
  if (kind) item.kind = kind;

  const title = safeString(raw.title, safeString(raw.name, ""));
  if (title) item.title = title;

  const src = safeString(raw.source_instance_id, safeString(raw.source, ""));
  if (src) item.source_instance_id = src;

  const domain = safeString(raw.domain, "");
  if (domain) item.domain = domain;

  if (Array.isArray(raw.tags)) {
    const tags = (raw.tags as unknown[]).map((x) => safeString(x)).filter((x) => x.length > 0);
    if (tags.length) item.tags = tags;
  }

  if (isRecord(raw.meta)) item.meta = raw.meta;

  return item;
}

export function parseFederationStage16Status(raw: unknown): FederationStage16Status {
  const body = isRecord(raw) ? raw : {};
  return {
    ok: safeBoolean(body.ok),
    status: optionalString(body.status),
    stage: optionalString(body.stage),
    stage16_status: optionalString(body.stage16_status),
    stage16_completion_review_ready: safeBoolean(body.stage16_completion_review_ready),
    live_runtime_readback_ready: safeBoolean(body.live_runtime_readback_ready),
    completion_review_blockers: stringList(body.completion_review_blockers),
    sleep_continuity_status: optionalString(body.sleep_continuity_status),
    sleep_continuity_ready: safeBoolean(body.sleep_continuity_ready),
    pre_sleep_evidence_ready: safeBoolean(body.pre_sleep_evidence_ready),
    post_resume_evidence_ready: safeBoolean(body.post_resume_evidence_ready),
    post_resume_evidence_conflict: safeBoolean(body.post_resume_evidence_conflict),
    latest_pre_sleep_evidence: isRecord(body.latest_pre_sleep_evidence)
      ? body.latest_pre_sleep_evidence
      : undefined,
    latest_post_resume_evidence: isRecord(body.latest_post_resume_evidence)
      ? body.latest_post_resume_evidence
      : undefined,
    sleep_continuity_selected_action_id: optionalString(body.sleep_continuity_selected_action_id),
    sleep_continuity_action_current_ready_to_run: safeBoolean(body.sleep_continuity_action_current_ready_to_run),
    sleep_continuity_operator_confirmation_pending: safeBoolean(body.sleep_continuity_operator_confirmation_pending),
    sleep_continuity_post_confirmation_ready_to_capture: safeBoolean(
      body.sleep_continuity_post_confirmation_ready_to_capture,
    ),
    sleep_continuity_confirmation_blocker: optionalString(body.sleep_continuity_confirmation_blocker),
    sleep_continuity_blocked_reason: optionalString(body.sleep_continuity_blocked_reason),
    sleep_continuity_sleep_resume_confirmation_is_current_blocker: safeBoolean(
      body.sleep_continuity_sleep_resume_confirmation_is_current_blocker,
    ),
    sleep_continuity_confirmation_receipt_command_ready: safeBoolean(
      body.sleep_continuity_confirmation_receipt_command_ready,
    ),
    sleep_continuity_confirmation_receipt_command_visible: safeBoolean(
      body.sleep_continuity_confirmation_receipt_command_visible,
    ),
    sleep_continuity_confirmation_receipt_command: optionalString(
      body.sleep_continuity_confirmation_receipt_command,
    ),
    sleep_continuity_confirmation_receipt_copyable_command: optionalString(
      body.sleep_continuity_confirmation_receipt_copyable_command,
    ),
    sleep_continuity_confirmation_receipt_command_requires_scope: optionalString(
      body.sleep_continuity_confirmation_receipt_command_requires_scope,
    ),
    sleep_continuity_confirmation_receipt_requested_actor: optionalString(
      body.sleep_continuity_confirmation_receipt_requested_actor,
    ),
    sleep_continuity_confirmation_receipt_requested_actor_ready: safeBoolean(
      body.sleep_continuity_confirmation_receipt_requested_actor_ready,
    ),
    sleep_continuity_confirmation_receipt_actor: optionalString(
      body.sleep_continuity_confirmation_receipt_actor,
    ),
    sleep_continuity_confirmation_receipt_actor_bound: safeBoolean(
      body.sleep_continuity_confirmation_receipt_actor_bound,
    ),
    sleep_continuity_confirmation_receipt_actor_placeholder: optionalString(
      body.sleep_continuity_confirmation_receipt_actor_placeholder,
    ),
    sleep_continuity_confirmation_receipt_command_requires_actor_substitution: safeBoolean(
      body.sleep_continuity_confirmation_receipt_command_requires_actor_substitution,
    ),
    sleep_continuity_confirmation_receipt_command_next_readback_route: optionalString(
      body.sleep_continuity_confirmation_receipt_command_next_readback_route,
    ),
    sleep_continuity_confirmation_receipt_command_receipt_id_readback_field: optionalString(
      body.sleep_continuity_confirmation_receipt_command_receipt_id_readback_field,
    ),
    sleep_continuity_confirmation_receipt_command_records_receipt: safeBoolean(
      body.sleep_continuity_confirmation_receipt_command_records_receipt,
    ),
    sleep_continuity_confirmation_receipt_command_writes_evidence: safeBoolean(
      body.sleep_continuity_confirmation_receipt_command_writes_evidence,
    ),
    sleep_continuity_confirmation_receipt_command_marks_stage16_closed: safeBoolean(
      body.sleep_continuity_confirmation_receipt_command_marks_stage16_closed,
    ),
    sleep_continuity_confirmation_receipt_command_projection_only: safeBoolean(
      body.sleep_continuity_confirmation_receipt_command_projection_only,
    ),
    sleep_continuity_confirmation_receipt_record_prerequisites_ready: safeBoolean(
      body.sleep_continuity_confirmation_receipt_record_prerequisites_ready,
    ),
    sleep_continuity_confirmation_receipt_record_blockers: stringList(
      body.sleep_continuity_confirmation_receipt_record_blockers,
    ),
    sleep_continuity_confirmation_receipt_record_current_pre_sleep_evidence_path: optionalString(
      body.sleep_continuity_confirmation_receipt_record_current_pre_sleep_evidence_path,
    ),
    sleep_continuity_confirmation_receipt_record_actor: optionalString(
      body.sleep_continuity_confirmation_receipt_record_actor,
    ),
    sleep_continuity_confirmation_receipt_record_command_ready: safeBoolean(
      body.sleep_continuity_confirmation_receipt_record_command_ready,
    ),
    sleep_continuity_confirmation_receipt_record_actor_ready: safeBoolean(
      body.sleep_continuity_confirmation_receipt_record_actor_ready,
    ),
    sleep_continuity_confirmation_receipt_record_records_receipt: safeBoolean(
      body.sleep_continuity_confirmation_receipt_record_records_receipt,
    ),
    sleep_continuity_confirmation_receipt_record_writes_evidence: safeBoolean(
      body.sleep_continuity_confirmation_receipt_record_writes_evidence,
    ),
    sleep_continuity_confirmation_receipt_record_writes_runtime_readback: safeBoolean(
      body.sleep_continuity_confirmation_receipt_record_writes_runtime_readback,
    ),
    sleep_continuity_confirmation_receipt_record_marks_stage16_closed: safeBoolean(
      body.sleep_continuity_confirmation_receipt_record_marks_stage16_closed,
    ),
    sleep_continuity_confirmation_receipt_record_grants_execution_authority: safeBoolean(
      body.sleep_continuity_confirmation_receipt_record_grants_execution_authority,
    ),
    sleep_continuity_confirmation_receipt_record_grants_mutation_authority: safeBoolean(
      body.sleep_continuity_confirmation_receipt_record_grants_mutation_authority,
    ),
    sleep_continuity_confirmation_receipt_readback_status: optionalString(
      body.sleep_continuity_confirmation_receipt_readback_status,
    ),
    sleep_continuity_confirmation_receipt_readback_ready: safeBoolean(
      body.sleep_continuity_confirmation_receipt_readback_ready,
    ),
    sleep_continuity_confirmation_receipt_latest_receipt_id: optionalString(
      body.sleep_continuity_confirmation_receipt_latest_receipt_id,
    ),
    sleep_continuity_confirmation_receipt_latest_decision: optionalString(
      body.sleep_continuity_confirmation_receipt_latest_decision,
    ),
    sleep_continuity_confirmation_receipt_latest_matches_current_pre_sleep: safeBoolean(
      body.sleep_continuity_confirmation_receipt_latest_matches_current_pre_sleep,
    ),
    sleep_continuity_confirmation_receipt_usable_for_receipt_backed_sequence: safeBoolean(
      body.sleep_continuity_confirmation_receipt_usable_for_receipt_backed_sequence,
    ),
    sleep_continuity_receipt_backed_sequence_ready: safeBoolean(
      body.sleep_continuity_receipt_backed_sequence_ready,
    ),
    sleep_continuity_receipt_backed_sequence_blockers: stringList(
      body.sleep_continuity_receipt_backed_sequence_blockers,
    ),
    sleep_continuity_receipt_backed_sequence_requires_confirmation_receipt: safeBoolean(
      body.sleep_continuity_receipt_backed_sequence_requires_confirmation_receipt,
    ),
    sleep_continuity_receipt_backed_sequence_next_step: optionalString(
      body.sleep_continuity_receipt_backed_sequence_next_step,
    ),
    sleep_continuity_receipt_backed_sequence_blocked_until_current_matching_confirmation_receipt: safeBoolean(
      body.sleep_continuity_receipt_backed_sequence_blocked_until_current_matching_confirmation_receipt,
    ),
    sleep_continuity_receipt_backed_sequence_current_matching_confirmation_receipt_required: safeBoolean(
      body.sleep_continuity_receipt_backed_sequence_current_matching_confirmation_receipt_required,
    ),
    sleep_continuity_receipt_backed_sequence_available_after_current_matching_confirmation_receipt: safeBoolean(
      body.sleep_continuity_receipt_backed_sequence_available_after_current_matching_confirmation_receipt,
    ),
    sleep_continuity_receipt_backed_sequence_hidden_until_confirmation_receipt: safeBoolean(
      body.sleep_continuity_receipt_backed_sequence_hidden_until_confirmation_receipt,
    ),
    sleep_continuity_receipt_backed_sequence_runs_after_physical_sleep_resume_receipt_only: safeBoolean(
      body.sleep_continuity_receipt_backed_sequence_runs_after_physical_sleep_resume_receipt_only,
    ),
    sleep_continuity_receipt_backed_sequence_post_receipt_handoff: isRecord(
      body.sleep_continuity_receipt_backed_sequence_post_receipt_handoff,
    )
      ? body.sleep_continuity_receipt_backed_sequence_post_receipt_handoff
      : undefined,
    sleep_continuity_receipt_backed_sequence_writes_evidence_when_run: safeBoolean(
      body.sleep_continuity_receipt_backed_sequence_writes_evidence_when_run,
    ),
    sleep_continuity_receipt_backed_sequence_writes_receipts_when_run: safeBoolean(
      body.sleep_continuity_receipt_backed_sequence_writes_receipts_when_run,
    ),
    sleep_continuity_next_step: optionalString(body.sleep_continuity_next_step),
    ready_count: safeNumber(body.ready_count, 0),
    required_count: safeNumber(body.required_count, 0),
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function parseLiveRuntimeReadbackCheck(raw: unknown): FederationLiveRuntimeReadbackCheck | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id);
  if (!id) return null;
  return {
    id,
    passed: safeBoolean(raw.passed),
    receipt_ready: safeBoolean(raw.receipt_ready),
    completion_evidence: safeBoolean(raw.completion_evidence),
    status: optionalString(raw.status),
    receipt_id: optionalString(raw.receipt_id),
    proof_kind: optionalString(raw.proof_kind),
    source_node_id: optionalString(raw.source_node_id),
    paired_node_id: optionalString(raw.paired_node_id),
    trace_id: optionalString(raw.trace_id),
    evidence: optionalString(raw.evidence),
  };
}

export function parseFederationLiveRuntimeReadbacks(raw: unknown): FederationLiveRuntimeReadbacks {
  const body = isRecord(raw) ? raw : {};
  const checks = Array.isArray(body.checks)
    ? body.checks.map(parseLiveRuntimeReadbackCheck).filter((x): x is FederationLiveRuntimeReadbackCheck => x !== null)
    : [];
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    count: safeNumber(body.count, 0),
    receipt_ready_count: safeNumber(body.receipt_ready_count, 0),
    ready_count: safeNumber(body.ready_count, 0),
    required_count: safeNumber(body.required_count, 0),
    completion_eligible_readback_count: safeNumber(body.completion_eligible_readback_count, 0),
    readback_receipts_ready: safeBoolean(body.readback_receipts_ready),
    live_runtime_readback_ready: safeBoolean(body.live_runtime_readback_ready),
    missing_readbacks: stringList(body.missing_readbacks),
    checks,
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

export function parseFederationCompletionReview(raw: unknown): FederationCompletionReview {
  const body = isRecord(raw) ? raw : {};
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    contract_readiness_ready: safeBoolean(body.contract_readiness_ready),
    live_runtime_readback_ready: safeBoolean(body.live_runtime_readback_ready),
    stage16_completion_review_ready: safeBoolean(body.stage16_completion_review_ready),
    ready_to_close: safeBoolean(body.ready_to_close),
    stage_closure_decision_required: safeBoolean(body.stage_closure_decision_required),
    blockers: stringList(body.blockers),
    ready_count: safeNumber(body.ready_count, 0),
    required_count: safeNumber(body.required_count, 0),
    live_ready_count: safeNumber(body.live_ready_count, 0),
    live_required_count: safeNumber(body.live_required_count, 0),
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function parseFederationStage16ClosureReceipt(raw: unknown): FederationStage16ClosureReceipt | null {
  if (!isRecord(raw)) return null;
  const receiptId = safeString(raw.receipt_id);
  if (!receiptId) return null;
  const recordedTs = safeNumber(raw.recorded_ts, 0);
  return {
    receipt_id: receiptId,
    actor: optionalString(raw.actor),
    decision: optionalString(raw.decision),
    completion_review_ready: safeBoolean(raw.completion_review_ready),
    stage16_completion_review_ready: safeBoolean(raw.stage16_completion_review_ready),
    live_runtime_readback_ready: safeBoolean(raw.live_runtime_readback_ready),
    stage16_closed_by_receipt: safeBoolean(raw.stage16_closed_by_receipt),
    recorded_ts: recordedTs > 0 ? normalizeTs(recordedTs) : undefined,
  };
}

export function parseFederationStage16ClosureDecisions(raw: unknown): FederationStage16ClosureDecisions {
  const body = isRecord(raw) ? raw : {};
  const items = Array.isArray(body.items)
    ? body.items
        .map(parseFederationStage16ClosureReceipt)
        .filter((x): x is FederationStage16ClosureReceipt => x !== null)
    : [];
  const latestReceipt = parseFederationStage16ClosureReceipt(body.latest_receipt);
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    count: safeNumber(body.count, 0),
    total: safeNumber(body.total, 0),
    latest_receipt_id: optionalString(body.latest_receipt_id),
    latest_decision: optionalString(body.latest_decision),
    receipt_readback_ready: safeBoolean(body.receipt_readback_ready),
    stage16_closed_by_receipt: safeBoolean(body.stage16_closed_by_receipt),
    marks_runtime_stage_state: safeBoolean(body.marks_runtime_stage_state),
    reads_receipts: safeBoolean(body.reads_receipts),
    writes_receipts: safeBoolean(body.writes_receipts),
    writes_registry: safeBoolean(body.writes_registry),
    writes_memory: safeBoolean(body.writes_memory),
    runs_tools: safeBoolean(body.runs_tools),
    runs_shell: safeBoolean(body.runs_shell),
    runs_git: safeBoolean(body.runs_git),
    launches_browser: safeBoolean(body.launches_browser),
    captures_screen: safeBoolean(body.captures_screen),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    latest_receipt: latestReceipt ?? undefined,
    items,
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function parseFederationSleepResumeConfirmationReceipt(
  raw: unknown,
): FederationSleepResumeConfirmationReceipt | null {
  if (!isRecord(raw)) return null;
  const receiptId = safeString(raw.receipt_id);
  if (!receiptId) return null;
  const preSleepRecordedTs = safeNumber(raw.pre_sleep_recorded_ts, 0);
  const recordedTs = safeNumber(raw.recorded_ts, 0);
  return {
    receipt_id: receiptId,
    actor: optionalString(raw.actor),
    decision: optionalString(raw.decision),
    operator_confirmed_sleep_resume: safeBoolean(raw.operator_confirmed_sleep_resume),
    pre_sleep_evidence_path: optionalString(raw.pre_sleep_evidence_path),
    pre_sleep_recorded_ts: preSleepRecordedTs > 0 ? normalizeTs(preSleepRecordedTs) : undefined,
    continuity_record_id: optionalString(raw.continuity_record_id),
    trace_id: optionalString(raw.trace_id),
    recorded_ts: recordedTs > 0 ? normalizeTs(recordedTs) : undefined,
  };
}

export function parseFederationSleepResumeConfirmationRecordResponse(
  raw: unknown,
): FederationSleepResumeConfirmationRecordResponse {
  const body = isRecord(raw) ? raw : {};
  const receipt = parseFederationSleepResumeConfirmationReceipt(body.receipt);
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    status: optionalString(body.status),
    source_id: optionalString(body.source_id),
    target: optionalString(body.target),
    receipt_id: optionalString(body.receipt_id),
    decision: optionalString(body.decision),
    writes_receipt: safeBoolean(body.writes_receipt),
    writes_evidence: safeBoolean(body.writes_evidence),
    writes_runtime_readback: safeBoolean(body.writes_runtime_readback),
    marks_stage16_closed: safeBoolean(body.marks_stage16_closed),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    receipt: receipt ?? undefined,
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function parseFederationSleepResumeOperatorChecklistItem(
  raw: unknown,
): FederationSleepResumeOperatorChecklistItem | null {
  if (!isRecord(raw)) return null;
  const id = optionalString(raw.id);
  if (!id) return null;
  return {
    id,
    status: optionalString(raw.status),
    passed: safeBoolean(raw.passed),
    evidence: optionalString(raw.evidence),
    required_scope: optionalString(raw.required_scope),
    writes_receipt: safeBoolean(raw.writes_receipt),
    writes_evidence: safeBoolean(raw.writes_evidence),
    writes_runtime_readback: safeBoolean(raw.writes_runtime_readback),
    marks_stage16_closed: safeBoolean(raw.marks_stage16_closed),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority),
    operator_action_required: safeBoolean(raw.operator_action_required),
  };
}

export function parseFederationSleepResumeOperatorChecklist(
  raw: unknown,
): FederationSleepResumeOperatorChecklist {
  const body = isRecord(raw) ? raw : {};
  const currentPreSleepRecordedTs = safeNumber(body.current_pre_sleep_recorded_ts, 0);
  const checklist = Array.isArray(body.checklist)
    ? body.checklist
        .map(parseFederationSleepResumeOperatorChecklistItem)
        .filter((x): x is FederationSleepResumeOperatorChecklistItem => x !== null)
    : [];
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    target: optionalString(body.target),
    actor: optionalString(body.actor),
    requested_actor_ready: safeBoolean(body.requested_actor_ready),
    required_scope: optionalString(body.required_scope),
    current_pre_sleep_evidence_present: safeBoolean(body.current_pre_sleep_evidence_present),
    current_pre_sleep_evidence_path: optionalString(body.current_pre_sleep_evidence_path),
    current_pre_sleep_recorded_ts:
      currentPreSleepRecordedTs > 0 ? normalizeTs(currentPreSleepRecordedTs) : undefined,
    current_pre_sleep_age_seconds: safeNumber(body.current_pre_sleep_age_seconds, 0),
    current_pre_sleep_freshness_state: optionalString(body.current_pre_sleep_freshness_state),
    current_pre_sleep_age_guidance: optionalString(body.current_pre_sleep_age_guidance),
    current_pre_sleep_recapture_recommended: safeBoolean(body.current_pre_sleep_recapture_recommended),
    current_pre_sleep_age_warning: optionalString(body.current_pre_sleep_age_warning),
    current_pre_sleep_age_guidance_threshold_seconds: safeNumber(
      body.current_pre_sleep_age_guidance_threshold_seconds,
      0,
    ),
    preconditions_ready: safeBoolean(body.preconditions_ready),
    ready_to_record_after_operator_confirmation: safeBoolean(
      body.ready_to_record_after_operator_confirmation,
    ),
    current_pre_sleep_marker_fresh_for_confirmation: safeBoolean(
      body.current_pre_sleep_marker_fresh_for_confirmation,
    ),
    confirmation_receipt_safe_after_physical_sleep_resume: safeBoolean(
      body.confirmation_receipt_safe_after_physical_sleep_resume,
    ),
    physical_confirmation_next_step: optionalString(body.physical_confirmation_next_step),
    operator_must_not_record_receipt_before_sleep_resume: safeBoolean(
      body.operator_must_not_record_receipt_before_sleep_resume,
    ),
    operator_must_not_record_receipt_for_stale_pre_sleep_marker: safeBoolean(
      body.operator_must_not_record_receipt_for_stale_pre_sleep_marker,
    ),
    physical_confirmation_guard: isRecord(body.physical_confirmation_guard)
      ? body.physical_confirmation_guard
      : undefined,
    operator_physical_confirmation_required: safeBoolean(body.operator_physical_confirmation_required),
    operator_physical_confirmation_recorded: safeBoolean(body.operator_physical_confirmation_recorded),
    latest_confirmation_receipt_id: optionalString(body.latest_confirmation_receipt_id),
    receipt_backed_sequence_ready: safeBoolean(body.receipt_backed_sequence_ready),
    blockers: stringList(body.blockers),
    operator_actions_remaining: stringList(body.operator_actions_remaining),
    checklist,
    confirmation_receipt_route: optionalString(body.confirmation_receipt_route),
    confirmation_receipt_readback_route: optionalString(body.confirmation_receipt_readback_route),
    confirmation_receipt_actor_readiness_route: optionalString(
      body.confirmation_receipt_actor_readiness_route,
    ),
    confirmation_receipt_payload_contract: isRecord(body.confirmation_receipt_payload_contract)
      ? body.confirmation_receipt_payload_contract
      : undefined,
    confirmation_receipt_command_ready: safeBoolean(body.confirmation_receipt_command_ready),
    confirmation_receipt_command_visible_after_physical_sleep_resume: safeBoolean(
      body.confirmation_receipt_command_visible_after_physical_sleep_resume,
    ),
    confirmation_receipt_command_after_physical_sleep_resume: optionalString(
      body.confirmation_receipt_command_after_physical_sleep_resume,
    ),
    confirmation_receipt_copyable_command_after_physical_sleep_resume: optionalString(
      body.confirmation_receipt_copyable_command_after_physical_sleep_resume,
    ),
    confirmation_receipt_command_runs_after_physical_sleep_resume_only: safeBoolean(
      body.confirmation_receipt_command_runs_after_physical_sleep_resume_only,
    ),
    confirmation_receipt_command_records_receipt: safeBoolean(body.confirmation_receipt_command_records_receipt),
    confirmation_receipt_command_writes_evidence: safeBoolean(body.confirmation_receipt_command_writes_evidence),
    confirmation_receipt_command_marks_stage16_closed: safeBoolean(
      body.confirmation_receipt_command_marks_stage16_closed,
    ),
    confirmation_receipt_command_projection_only: safeBoolean(body.confirmation_receipt_command_projection_only),
    records_receipt: safeBoolean(body.records_receipt),
    writes_receipts: safeBoolean(body.writes_receipts),
    writes_evidence: safeBoolean(body.writes_evidence),
    writes_runtime_readback: safeBoolean(body.writes_runtime_readback),
    marks_stage16_closed: safeBoolean(body.marks_stage16_closed),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    governance: isRecord(body.governance) ? body.governance : undefined,
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

export function parseFederationSleepResumeReceiptBackedSequenceReadiness(
  raw: unknown,
): FederationSleepResumeReceiptBackedSequenceReadiness {
  const body = isRecord(raw) ? raw : {};
  const currentPreSleepRecordedTs = safeNumber(body.current_pre_sleep_recorded_ts, 0);
  const sequenceOperatorStep = parseFederationSleepResumeConfirmationOperatorStep(
    body.receipt_backed_sequence_operator_step,
  );
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    target: optionalString(body.target),
    actor: optionalString(body.actor),
    current_pre_sleep_evidence_present: safeBoolean(body.current_pre_sleep_evidence_present),
    current_pre_sleep_evidence_path: optionalString(body.current_pre_sleep_evidence_path),
    current_pre_sleep_recorded_ts:
      currentPreSleepRecordedTs > 0 ? normalizeTs(currentPreSleepRecordedTs) : undefined,
    current_pre_sleep_age_seconds: safeNumber(body.current_pre_sleep_age_seconds, 0),
    current_pre_sleep_freshness_state: optionalString(body.current_pre_sleep_freshness_state),
    current_pre_sleep_age_guidance: optionalString(body.current_pre_sleep_age_guidance),
    current_pre_sleep_recapture_recommended: safeBoolean(body.current_pre_sleep_recapture_recommended),
    current_pre_sleep_age_warning: optionalString(body.current_pre_sleep_age_warning),
    current_pre_sleep_age_guidance_threshold_seconds: safeNumber(
      body.current_pre_sleep_age_guidance_threshold_seconds,
      0,
    ),
    latest_receipt_id: optionalString(body.latest_receipt_id),
    latest_decision: optionalString(body.latest_decision),
    latest_actor: optionalString(body.latest_actor),
    latest_pre_sleep_evidence_path: optionalString(body.latest_pre_sleep_evidence_path),
    latest_receipt_is_operator_confirmed: safeBoolean(body.latest_receipt_is_operator_confirmed),
    latest_receipt_matches_current_pre_sleep: safeBoolean(body.latest_receipt_matches_current_pre_sleep),
    latest_receipt_usable_for_receipt_backed_sequence: safeBoolean(
      body.latest_receipt_usable_for_receipt_backed_sequence,
    ),
    receipt_backed_sequence_ready: safeBoolean(body.receipt_backed_sequence_ready),
    receipt_backed_sequence_blockers: stringList(body.receipt_backed_sequence_blockers),
    receipt_backed_sequence_command_visible: safeBoolean(body.receipt_backed_sequence_command_visible),
    receipt_backed_sequence_command: optionalString(body.receipt_backed_sequence_command),
    receipt_backed_sequence_copyable_command: optionalString(body.receipt_backed_sequence_copyable_command),
    receipt_backed_sequence_requires_confirmation_receipt: safeBoolean(
      body.receipt_backed_sequence_requires_confirmation_receipt,
    ),
    receipt_backed_sequence_confirmation_receipt_id: optionalString(
      body.receipt_backed_sequence_confirmation_receipt_id,
    ),
    receipt_backed_sequence_operator_step: sequenceOperatorStep ?? undefined,
    receipt_backed_sequence_next_step: optionalString(body.receipt_backed_sequence_next_step),
    receipt_backed_sequence_blocked_until_current_matching_confirmation_receipt: safeBoolean(
      body.receipt_backed_sequence_blocked_until_current_matching_confirmation_receipt,
    ),
    receipt_backed_sequence_current_matching_confirmation_receipt_required: safeBoolean(
      body.receipt_backed_sequence_current_matching_confirmation_receipt_required,
    ),
    receipt_backed_sequence_available_after_current_matching_confirmation_receipt: safeBoolean(
      body.receipt_backed_sequence_available_after_current_matching_confirmation_receipt,
    ),
    receipt_backed_sequence_hidden_until_confirmation_receipt: safeBoolean(
      body.receipt_backed_sequence_hidden_until_confirmation_receipt,
    ),
    receipt_backed_sequence_runs_after_physical_sleep_resume_receipt_only: safeBoolean(
      body.receipt_backed_sequence_runs_after_physical_sleep_resume_receipt_only,
    ),
    post_receipt_handoff: isRecord(body.post_receipt_handoff) ? body.post_receipt_handoff : undefined,
    operator_action_required: safeBoolean(body.operator_action_required),
    writes_evidence_when_run: safeBoolean(body.writes_evidence_when_run),
    writes_receipts_when_run: safeBoolean(body.writes_receipts_when_run),
    marks_stage16_closed_when_run: safeBoolean(body.marks_stage16_closed_when_run),
    projection_only: safeBoolean(body.projection_only),
    reads_receipts: safeBoolean(body.reads_receipts),
    writes_receipts: safeBoolean(body.writes_receipts),
    writes_evidence: safeBoolean(body.writes_evidence),
    writes_runtime_readback: safeBoolean(body.writes_runtime_readback),
    marks_stage16_closed: safeBoolean(body.marks_stage16_closed),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    confirmation_receipt_readback_route: optionalString(body.confirmation_receipt_readback_route),
    operator_checklist_route: optionalString(body.operator_checklist_route),
    sleep_continuity_action_route: optionalString(body.sleep_continuity_action_route),
    governance: isRecord(body.governance) ? body.governance : undefined,
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function parseFederationSleepResumeConfirmationOperatorStep(
  raw: unknown,
): FederationSleepResumeConfirmationOperatorStep | null {
  if (!isRecord(raw)) return null;
  const id = optionalString(raw.id);
  if (!id) return null;
  return {
    id,
    order: safeNumber(raw.order, 0),
    status: optionalString(raw.status),
    method: optionalString(raw.method),
    route: optionalString(raw.route),
    command_field: optionalString(raw.command_field),
    readback_field: optionalString(raw.readback_field),
    required_scope: optionalString(raw.required_scope),
    required_readback_field: optionalString(raw.required_readback_field),
    requires_actor_substitution: safeBoolean(raw.requires_actor_substitution),
    requires_current_receipt: safeBoolean(raw.requires_current_receipt),
    writes_receipts_when_run: safeBoolean(raw.writes_receipts_when_run),
    writes_evidence_when_run: safeBoolean(raw.writes_evidence_when_run),
    marks_stage16_closed_when_run: safeBoolean(raw.marks_stage16_closed_when_run),
    operator_action_required: safeBoolean(raw.operator_action_required),
    read_only_projection: safeBoolean(raw.read_only_projection),
  };
}

export function parseFederationSleepResumeConfirmations(raw: unknown): FederationSleepResumeConfirmations {
  const body = isRecord(raw) ? raw : {};
  const items = Array.isArray(body.items)
    ? body.items
        .map(parseFederationSleepResumeConfirmationReceipt)
        .filter((x): x is FederationSleepResumeConfirmationReceipt => x !== null)
    : [];
  const latestReceipt = parseFederationSleepResumeConfirmationReceipt(body.latest_receipt);
  const latestRecordedTs = safeNumber(body.latest_recorded_ts, 0);
  const currentPreSleepRecordedTs = safeNumber(body.current_pre_sleep_recorded_ts, 0);
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    count: safeNumber(body.count, 0),
    total: safeNumber(body.total, 0),
    latest_receipt_id: optionalString(body.latest_receipt_id),
    latest_actor: optionalString(body.latest_actor),
    latest_decision: optionalString(body.latest_decision),
    latest_pre_sleep_evidence_path: optionalString(body.latest_pre_sleep_evidence_path),
    latest_recorded_ts: latestRecordedTs > 0 ? normalizeTs(latestRecordedTs) : undefined,
    receipt_readback_ready: safeBoolean(body.receipt_readback_ready),
    current_pre_sleep_evidence_present: safeBoolean(body.current_pre_sleep_evidence_present),
    current_pre_sleep_evidence_path: optionalString(body.current_pre_sleep_evidence_path),
    current_pre_sleep_recorded_ts:
      currentPreSleepRecordedTs > 0 ? normalizeTs(currentPreSleepRecordedTs) : undefined,
    current_pre_sleep_age_seconds: safeNumber(body.current_pre_sleep_age_seconds, 0),
    current_pre_sleep_freshness_state: optionalString(body.current_pre_sleep_freshness_state),
    current_pre_sleep_age_guidance: optionalString(body.current_pre_sleep_age_guidance),
    current_pre_sleep_recapture_recommended: safeBoolean(body.current_pre_sleep_recapture_recommended),
    current_pre_sleep_age_warning: optionalString(body.current_pre_sleep_age_warning),
    current_pre_sleep_age_guidance_threshold_seconds: safeNumber(
      body.current_pre_sleep_age_guidance_threshold_seconds,
      0,
    ),
    confirmation_receipt_requested_actor: optionalString(body.confirmation_receipt_requested_actor),
    confirmation_receipt_requested_actor_ready: safeBoolean(body.confirmation_receipt_requested_actor_ready),
    latest_receipt_is_operator_confirmed: safeBoolean(body.latest_receipt_is_operator_confirmed),
    latest_receipt_matches_current_pre_sleep: safeBoolean(body.latest_receipt_matches_current_pre_sleep),
    latest_receipt_usable_for_receipt_backed_sequence: safeBoolean(
      body.latest_receipt_usable_for_receipt_backed_sequence,
    ),
    receipt_backed_sequence_ready: safeBoolean(body.receipt_backed_sequence_ready),
    receipt_backed_sequence_blockers: stringList(body.receipt_backed_sequence_blockers),
    receipt_backed_sequence_command: optionalString(body.receipt_backed_sequence_command),
    receipt_backed_sequence_copyable_command: optionalString(body.receipt_backed_sequence_copyable_command),
    confirmation_receipt_command_ready: safeBoolean(body.confirmation_receipt_command_ready),
    confirmation_receipt_actor: optionalString(body.confirmation_receipt_actor),
    confirmation_receipt_actor_bound: safeBoolean(body.confirmation_receipt_actor_bound),
    confirmation_receipt_actor_placeholder: optionalString(body.confirmation_receipt_actor_placeholder),
    confirmation_receipt_command: optionalString(body.confirmation_receipt_command),
    confirmation_receipt_copyable_command: optionalString(body.confirmation_receipt_copyable_command),
    confirmation_receipt_command_requires_scope: optionalString(body.confirmation_receipt_command_requires_scope),
    confirmation_receipt_command_requires_actor_substitution: safeBoolean(
      body.confirmation_receipt_command_requires_actor_substitution,
    ),
    confirmation_receipt_command_actor_scope: optionalString(body.confirmation_receipt_command_actor_scope),
    confirmation_receipt_actor_readiness_route: optionalString(body.confirmation_receipt_actor_readiness_route),
    confirmation_receipt_actor_readiness_query_param: optionalString(
      body.confirmation_receipt_actor_readiness_query_param,
    ),
    confirmation_receipt_command_next_readback_route: optionalString(
      body.confirmation_receipt_command_next_readback_route,
    ),
    confirmation_receipt_command_receipt_id_readback_field: optionalString(
      body.confirmation_receipt_command_receipt_id_readback_field,
    ),
    confirmation_receipt_command_next_operator_step: optionalString(
      body.confirmation_receipt_command_next_operator_step,
    ),
    confirmation_receipt_operator_steps: Array.isArray(body.confirmation_receipt_operator_steps)
      ? body.confirmation_receipt_operator_steps
          .map(parseFederationSleepResumeConfirmationOperatorStep)
          .filter((x): x is FederationSleepResumeConfirmationOperatorStep => x !== null)
      : [],
    confirmation_receipt_command_records_receipt: safeBoolean(body.confirmation_receipt_command_records_receipt),
    confirmation_receipt_command_writes_evidence: safeBoolean(body.confirmation_receipt_command_writes_evidence),
    confirmation_receipt_command_marks_stage16_closed: safeBoolean(body.confirmation_receipt_command_marks_stage16_closed),
    confirmation_receipt_command_projection_only: safeBoolean(body.confirmation_receipt_command_projection_only),
    receipt_backed_sequence_requires_confirmation_receipt: safeBoolean(
      body.receipt_backed_sequence_requires_confirmation_receipt,
    ),
    receipt_backed_sequence_writes_evidence_when_run: safeBoolean(
      body.receipt_backed_sequence_writes_evidence_when_run,
    ),
    receipt_backed_sequence_writes_receipts_when_run: safeBoolean(
      body.receipt_backed_sequence_writes_receipts_when_run,
    ),
    reads_receipts: safeBoolean(body.reads_receipts),
    writes_receipts: safeBoolean(body.writes_receipts),
    writes_evidence: safeBoolean(body.writes_evidence),
    writes_runtime_readback: safeBoolean(body.writes_runtime_readback),
    marks_stage16_closed: safeBoolean(body.marks_stage16_closed),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    latest_receipt: latestReceipt ?? undefined,
    items,
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

export function federationSleepResumeConfirmationVisibleCommands(
  confirmations: FederationSleepResumeConfirmations | null | undefined,
): FederationSleepResumeConfirmationVisibleCommands {
  if (!confirmations) return {};
  const receiptBackedSequenceVisible =
    confirmations.receipt_backed_sequence_ready &&
    confirmations.latest_receipt_usable_for_receipt_backed_sequence &&
    confirmations.receipt_backed_sequence_blockers.length === 0;
  return {
    confirmation_receipt_copyable_command: confirmations.confirmation_receipt_command_ready
      ? confirmations.confirmation_receipt_copyable_command
      : undefined,
    receipt_backed_sequence_copyable_command: receiptBackedSequenceVisible
      ? confirmations.receipt_backed_sequence_copyable_command
      : undefined,
  };
}

export function federationSleepResumeReceiptBackedSequenceVisibleCommands(
  readiness: FederationSleepResumeReceiptBackedSequenceReadiness | null | undefined,
): FederationSleepResumeReceiptBackedSequenceVisibleCommands {
  const sequenceVisible = Boolean(
    readiness?.receipt_backed_sequence_ready &&
      readiness.receipt_backed_sequence_command_visible &&
      readiness.latest_receipt_usable_for_receipt_backed_sequence &&
      readiness.receipt_backed_sequence_blockers.length === 0,
  );
  return {
    receipt_backed_sequence_copyable_command: sequenceVisible
      ? readiness?.receipt_backed_sequence_copyable_command
      : undefined,
  };
}

export function federationSleepResumeConfirmationActorReadinessVisibleCommands(
  readiness: FederationSleepResumeConfirmationActorReadiness | null | undefined,
): FederationSleepResumeConfirmationActorReadinessVisibleCommands {
  const confirmationVisible = Boolean(
    readiness?.confirmation_receipt_actor_ready &&
      readiness.confirmation_receipt_command_ready &&
      readiness.confirmation_receipt_actor_bound &&
      !readiness.confirmation_receipt_command_requires_actor_substitution &&
      readiness.confirmation_receipt_copyable_command &&
      !readiness.writes_receipt &&
      !readiness.writes_evidence &&
      !readiness.marks_stage16_closed &&
      !readiness.grants_execution_authority &&
      !readiness.grants_mutation_authority,
  );
  const scopeRemediationVisible = Boolean(
    readiness?.scope_remediation_required &&
      readiness.scope_remediation_command_ready &&
      readiness.scope_remediation_command_visible &&
      readiness.scope_remediation_copyable_command &&
      readiness.scope_remediation_projection_only &&
      !readiness.scope_remediation_writes_receipts &&
      !readiness.scope_remediation_writes_evidence &&
      !readiness.scope_remediation_marks_stage16_closed &&
      !readiness.scope_remediation_grants_authority,
  );
  return {
    confirmation_receipt_copyable_command: confirmationVisible
      ? readiness?.confirmation_receipt_copyable_command
      : undefined,
    scope_remediation_copyable_command: scopeRemediationVisible
      ? readiness?.scope_remediation_copyable_command
      : undefined,
  };
}

export function shouldAutoCheckFederationSleepResumeConfirmationActorReadiness(opts: {
  confirmations: FederationSleepResumeConfirmations | null | undefined;
  actor: string;
  readiness: FederationSleepResumeConfirmationActorReadiness | null | undefined;
}): boolean {
  const actor = opts.actor.trim();
  const confirmations = opts.confirmations;
  if (!actor || !confirmations) return false;
  if (isFederationSleepResumeConfirmationActorReadinessCurrent(opts.readiness, actor)) return false;
  return Boolean(
    confirmations.current_pre_sleep_evidence_present &&
      confirmations.confirmation_receipt_command_ready &&
      confirmations.confirmation_receipt_command_requires_actor_substitution &&
      !confirmations.confirmation_receipt_actor_bound &&
      confirmations.confirmation_receipt_actor_placeholder &&
      confirmations.confirmation_receipt_actor_readiness_route &&
      confirmations.confirmation_receipt_actor_readiness_query_param === "actor" &&
      confirmations.confirmation_receipt_command_projection_only &&
      !confirmations.confirmation_receipt_command_writes_evidence &&
      !confirmations.confirmation_receipt_command_marks_stage16_closed &&
      !confirmations.writes_receipts &&
      !confirmations.writes_evidence &&
      !confirmations.marks_stage16_closed &&
      !confirmations.grants_execution_authority &&
      !confirmations.grants_mutation_authority,
  );
}

export function federationSleepResumeReceiptRecordReadiness(opts: {
  status: FederationStage16Status | null | undefined;
  confirmations: FederationSleepResumeConfirmations | null | undefined;
  operatorAcknowledged: boolean;
}): FederationSleepResumeReceiptRecordReadiness {
  const status = opts.status;
  const confirmations = opts.confirmations;
  const currentPreSleepEvidencePath =
    status?.sleep_continuity_confirmation_receipt_record_current_pre_sleep_evidence_path ??
    confirmations?.current_pre_sleep_evidence_path ??
    optionalString(status?.latest_pre_sleep_evidence?.evidence_path);
  const commandReady = Boolean(
    status?.sleep_continuity_confirmation_receipt_record_command_ready ||
    status?.sleep_continuity_confirmation_receipt_command_ready ||
      confirmations?.confirmation_receipt_command_ready,
  );
  const actorReady = Boolean(
    status?.sleep_continuity_confirmation_receipt_record_actor_ready ||
    status?.sleep_continuity_confirmation_receipt_requested_actor_ready ||
      confirmations?.confirmation_receipt_requested_actor_ready,
  );
  const recordsReceipt = Boolean(
    status?.sleep_continuity_confirmation_receipt_record_records_receipt ||
    status?.sleep_continuity_confirmation_receipt_command_records_receipt ||
      confirmations?.confirmation_receipt_command_records_receipt,
  );
  const writesEvidence = Boolean(
    status?.sleep_continuity_confirmation_receipt_record_writes_evidence ||
    status?.sleep_continuity_confirmation_receipt_command_writes_evidence ||
      confirmations?.confirmation_receipt_command_writes_evidence,
  );
  const marksStage16Closed = Boolean(
    status?.sleep_continuity_confirmation_receipt_record_marks_stage16_closed ||
    status?.sleep_continuity_confirmation_receipt_command_marks_stage16_closed ||
      confirmations?.confirmation_receipt_command_marks_stage16_closed,
  );
  const receiptBackedSequenceReady = Boolean(
    status?.sleep_continuity_receipt_backed_sequence_ready || confirmations?.receipt_backed_sequence_ready,
  );
  const actor =
    status?.sleep_continuity_confirmation_receipt_record_actor ??
    status?.sleep_continuity_confirmation_receipt_actor ?? confirmations?.confirmation_receipt_actor;
  const blockers: string[] = [...(status?.sleep_continuity_confirmation_receipt_record_blockers ?? [])];
  const pushBlocker = (blocker: string) => {
    if (!blockers.includes(blocker)) blockers.push(blocker);
  };
  if (!commandReady) pushBlocker("confirmation_receipt_command_not_ready");
  if (!actorReady) pushBlocker("confirmation_receipt_actor_not_ready");
  if (!currentPreSleepEvidencePath) pushBlocker("current_pre_sleep_evidence_path_missing");
  if (!recordsReceipt) pushBlocker("confirmation_receipt_command_does_not_record_receipt");
  if (writesEvidence) pushBlocker("confirmation_receipt_command_writes_evidence");
  if (marksStage16Closed) pushBlocker("confirmation_receipt_command_marks_stage16_closed");
  if (receiptBackedSequenceReady) pushBlocker("receipt_backed_sequence_already_ready");
  if (!opts.operatorAcknowledged) pushBlocker("operator_sleep_resume_acknowledgement_missing");
  return {
    ready: blockers.length === 0,
    disabled: blockers.length > 0,
    blockers,
    current_pre_sleep_evidence_path: currentPreSleepEvidencePath,
    actor,
    operator_acknowledged: opts.operatorAcknowledged,
    receipt_backed_sequence_ready: receiptBackedSequenceReady,
    command_ready: commandReady,
    actor_ready: actorReady,
    records_receipt: recordsReceipt,
    writes_evidence: writesEvidence,
    writes_runtime_readback: false,
    marks_stage16_closed: marksStage16Closed,
    grants_execution_authority: false,
    grants_mutation_authority: false,
  };
}

export function parseFederationSleepResumeConfirmationActorReadiness(
  raw: unknown,
): FederationSleepResumeConfirmationActorReadiness {
  const body = isRecord(raw) ? raw : {};
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    target: optionalString(body.target),
    actor: optionalString(body.actor),
    actor_present: safeBoolean(body.actor_present),
    actor_placeholder_rejected: safeBoolean(body.actor_placeholder_rejected),
    required_scope: optionalString(body.required_scope),
    target_method: optionalString(body.target_method),
    target_route: optionalString(body.target_route),
    readiness_route: optionalString(body.readiness_route),
    current_pre_sleep_evidence_present: safeBoolean(body.current_pre_sleep_evidence_present),
    current_pre_sleep_evidence_path: optionalString(body.current_pre_sleep_evidence_path),
    permission_allowed: safeBoolean(body.permission_allowed),
    permission_reason: optionalString(body.permission_reason),
    confirmation_receipt_actor_ready: safeBoolean(body.confirmation_receipt_actor_ready),
    safe_to_use_in_confirmation_command: safeBoolean(body.safe_to_use_in_confirmation_command),
    next_step: optionalString(body.next_step),
    confirmation_receipt_command_ready: safeBoolean(body.confirmation_receipt_command_ready),
    confirmation_receipt_actor: optionalString(body.confirmation_receipt_actor),
    confirmation_receipt_actor_bound: safeBoolean(body.confirmation_receipt_actor_bound),
    confirmation_receipt_actor_placeholder: optionalString(body.confirmation_receipt_actor_placeholder),
    confirmation_receipt_command: optionalString(body.confirmation_receipt_command),
    confirmation_receipt_copyable_command: optionalString(body.confirmation_receipt_copyable_command),
    confirmation_receipt_command_requires_scope: optionalString(body.confirmation_receipt_command_requires_scope),
    confirmation_receipt_command_requires_actor_substitution: safeBoolean(
      body.confirmation_receipt_command_requires_actor_substitution,
    ),
    confirmation_receipt_command_actor_scope: optionalString(body.confirmation_receipt_command_actor_scope),
    confirmation_receipt_actor_readiness_route: optionalString(body.confirmation_receipt_actor_readiness_route),
    confirmation_receipt_actor_readiness_query_param: optionalString(
      body.confirmation_receipt_actor_readiness_query_param,
    ),
    confirmation_receipt_command_next_readback_route: optionalString(
      body.confirmation_receipt_command_next_readback_route,
    ),
    confirmation_receipt_command_receipt_id_readback_field: optionalString(
      body.confirmation_receipt_command_receipt_id_readback_field,
    ),
    confirmation_receipt_command_next_operator_step: optionalString(
      body.confirmation_receipt_command_next_operator_step,
    ),
    confirmation_receipt_command_records_receipt: safeBoolean(body.confirmation_receipt_command_records_receipt),
    confirmation_receipt_command_writes_evidence: safeBoolean(body.confirmation_receipt_command_writes_evidence),
    confirmation_receipt_command_marks_stage16_closed: safeBoolean(body.confirmation_receipt_command_marks_stage16_closed),
    confirmation_receipt_command_projection_only: safeBoolean(body.confirmation_receipt_command_projection_only),
    scope_remediation_required: safeBoolean(body.scope_remediation_required),
    scope_remediation_command_ready: safeBoolean(body.scope_remediation_command_ready),
    scope_remediation_command_visible: safeBoolean(body.scope_remediation_command_visible),
    scope_remediation_env_var: optionalString(body.scope_remediation_env_var),
    scope_remediation_actor: optionalString(body.scope_remediation_actor),
    scope_remediation_required_scope: optionalString(body.scope_remediation_required_scope),
    scope_remediation_policy_fragment: isRecord(body.scope_remediation_policy_fragment)
      ? body.scope_remediation_policy_fragment
      : undefined,
    scope_remediation_command: optionalString(body.scope_remediation_command),
    scope_remediation_copyable_command: optionalString(body.scope_remediation_copyable_command),
    scope_remediation_projection_only: safeBoolean(body.scope_remediation_projection_only),
    scope_remediation_writes_receipts: safeBoolean(body.scope_remediation_writes_receipts),
    scope_remediation_writes_evidence: safeBoolean(body.scope_remediation_writes_evidence),
    scope_remediation_marks_stage16_closed: safeBoolean(body.scope_remediation_marks_stage16_closed),
    scope_remediation_grants_authority: safeBoolean(body.scope_remediation_grants_authority),
    scope_remediation_would_mutate_process_environment_if_run: safeBoolean(
      body.scope_remediation_would_mutate_process_environment_if_run,
    ),
    reads_permission_gate: safeBoolean(body.reads_permission_gate),
    writes_receipt: safeBoolean(body.writes_receipt),
    writes_evidence: safeBoolean(body.writes_evidence),
    writes_runtime_readback: safeBoolean(body.writes_runtime_readback),
    marks_stage16_closed: safeBoolean(body.marks_stage16_closed),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

export function isFederationSleepResumeConfirmationActorReadinessCurrent(
  readiness: FederationSleepResumeConfirmationActorReadiness | null | undefined,
  actor: string,
): boolean {
  if (!readiness) return false;
  const expectedActor = actor.trim();
  const readinessActor = (readiness.actor ?? "").trim();
  if (!expectedActor) {
    return !readiness.actor_present && !readinessActor;
  }
  return readinessActor === expectedActor;
}

export function isFederationSleepContinuityOperatorCommandBlockedByPendingConfirmation(
  presentation: FederationSleepContinuityPresentation | null | undefined,
): boolean {
  if (!presentation) return false;
  return (
    presentation.operator_confirmation_pending ||
    presentation.sleep_resume_confirmation_is_current_blocker ||
    presentation.operator_terminal_invocation?.operator_confirmation_pending === true ||
    presentation.operator_sleep_resume_gate?.operator_confirmation_pending === true ||
    presentation.operator_confirmation_handoff?.operator_confirmation_pending === true
  );
}

export function federationSleepContinuityVisibleOperatorCommands(
  presentation: FederationSleepContinuityPresentation | null | undefined,
): FederationSleepContinuityVisibleOperatorCommands {
  const blockedByPendingConfirmation =
    isFederationSleepContinuityOperatorCommandBlockedByPendingConfirmation(presentation);
  const handoff = presentation?.operator_confirmation_handoff;
  return {
    blocked_by_pending_confirmation: blockedByPendingConfirmation,
    pre_sleep_recapture_copyable_command: presentation?.pre_sleep_recapture_copyable_command,
    primary_command: blockedByPendingConfirmation ? undefined : presentation?.primary_command,
    operator_terminal_copyable_command: blockedByPendingConfirmation
      ? undefined
      : presentation?.operator_terminal_invocation?.copyable_command,
    post_resume_capture_copyable_command: blockedByPendingConfirmation
      ? undefined
      : handoff?.post_resume_capture_copyable_command,
    post_resume_sequence_copyable_command: blockedByPendingConfirmation
      ? undefined
      : handoff?.post_resume_sequence_copyable_command,
    post_resume_receipt_backed_sequence_copyable_command: blockedByPendingConfirmation
      ? undefined
      : handoff?.post_resume_receipt_backed_sequence_copyable_command,
    confirmation_receipt_copyable_command: handoff?.confirmation_receipt_copyable_command,
  };
}

function parseFederationSleepContinuityRunbookStep(raw: unknown): FederationSleepContinuityRunbookStep | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id);
  if (!id) return null;
  return {
    id,
    title: optionalString(raw.title),
    command: optionalString(raw.command),
    latest_evidence_path: optionalString(raw.latest_evidence_path),
    pre_sleep_evidence_path: optionalString(raw.pre_sleep_evidence_path),
    post_resume_evidence_path: optionalString(raw.post_resume_evidence_path),
    method: optionalString(raw.method),
    route: optionalString(raw.route),
    required_scope: optionalString(raw.required_scope),
    expected_output: optionalString(raw.expected_output),
    pre_sleep_evidence_required: safeBoolean(raw.pre_sleep_evidence_required),
    pre_sleep_evidence_available: safeBoolean(raw.pre_sleep_evidence_available),
    post_resume_evidence_required: safeBoolean(raw.post_resume_evidence_required),
    post_resume_evidence_available: safeBoolean(raw.post_resume_evidence_available),
    operator_action_required: safeBoolean(raw.operator_action_required),
    operator_confirmation_required: safeBoolean(raw.operator_confirmation_required),
    writes_evidence_when_run: safeBoolean(raw.writes_evidence_when_run),
    writes_receipts_when_run: safeBoolean(raw.writes_receipts_when_run),
    payload_contract: isRecord(raw.payload_contract) ? raw.payload_contract : undefined,
  };
}

function parseFederationSleepContinuitySelectedActionSummary(
  raw: unknown,
): FederationSleepContinuitySelectedActionSummary | undefined {
  if (!isRecord(raw)) return undefined;
  return {
    selected_action_id: optionalString(raw.selected_action_id),
    current_ready_to_run: safeBoolean(raw.current_ready_to_run),
    operator_confirmation_pending: safeBoolean(raw.operator_confirmation_pending),
    post_confirmation_ready_to_capture: safeBoolean(raw.post_confirmation_ready_to_capture),
    sleep_resume_confirmation_is_current_blocker: safeBoolean(raw.sleep_resume_confirmation_is_current_blocker),
    confirmation_blocker: optionalString(raw.confirmation_blocker),
    blocked_reason: optionalString(raw.blocked_reason),
  };
}

export function parseFederationSleepContinuityRunbook(raw: unknown): FederationSleepContinuityRunbook {
  const body = isRecord(raw) ? raw : {};
  const steps = Array.isArray(body.steps)
    ? body.steps
        .map(parseFederationSleepContinuityRunbookStep)
        .filter((x): x is FederationSleepContinuityRunbookStep => x !== null)
    : [];
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    runbook_only: safeBoolean(body.runbook_only),
    prerequisite_readback_ids: stringList(body.prerequisite_readback_ids),
    prerequisite_readbacks_ready: safeBoolean(body.prerequisite_readbacks_ready),
    sleep_continuity_readback_id: optionalString(body.sleep_continuity_readback_id),
    sleep_continuity_ready: safeBoolean(body.sleep_continuity_ready),
    pre_sleep_evidence: isRecord(body.pre_sleep_evidence) ? body.pre_sleep_evidence : undefined,
    pre_sleep_evidence_ready: safeBoolean(body.pre_sleep_evidence_ready),
    pre_sleep_age_seconds: safeNumber(body.pre_sleep_age_seconds, 0),
    pre_sleep_freshness_state: optionalString(body.pre_sleep_freshness_state),
    current_pre_sleep_age_guidance: optionalString(body.current_pre_sleep_age_guidance),
    current_pre_sleep_recapture_recommended: safeBoolean(body.current_pre_sleep_recapture_recommended),
    current_pre_sleep_age_warning: optionalString(body.current_pre_sleep_age_warning),
    current_pre_sleep_age_guidance_threshold_seconds: safeNumber(
      body.current_pre_sleep_age_guidance_threshold_seconds,
      0,
    ),
    pre_sleep_recapture_recommended: safeBoolean(body.pre_sleep_recapture_recommended),
    pre_sleep_recapture_reason: optionalString(body.pre_sleep_recapture_reason),
    pre_sleep_recapture_command_ready: safeBoolean(body.pre_sleep_recapture_command_ready),
    pre_sleep_recapture_command_visible: safeBoolean(body.pre_sleep_recapture_command_visible),
    pre_sleep_recapture_command: optionalString(body.pre_sleep_recapture_command),
    pre_sleep_recapture_copyable_command: optionalString(body.pre_sleep_recapture_copyable_command),
    pre_sleep_recapture_expected_output: optionalString(body.pre_sleep_recapture_expected_output),
    pre_sleep_recapture_after_run_next_step: optionalString(body.pre_sleep_recapture_after_run_next_step),
    pre_sleep_recapture_writes_evidence_when_run: safeBoolean(
      body.pre_sleep_recapture_writes_evidence_when_run,
    ),
    pre_sleep_recapture_writes_receipts_when_run: safeBoolean(
      body.pre_sleep_recapture_writes_receipts_when_run,
    ),
    pre_sleep_recapture_marks_stage16_closed_when_run: safeBoolean(
      body.pre_sleep_recapture_marks_stage16_closed_when_run,
    ),
    pre_sleep_recapture_projection_only: safeBoolean(body.pre_sleep_recapture_projection_only),
    post_resume_evidence: isRecord(body.post_resume_evidence) ? body.post_resume_evidence : undefined,
    post_resume_evidence_ready: safeBoolean(body.post_resume_evidence_ready),
    post_resume_evidence_conflict: safeBoolean(body.post_resume_evidence_conflict),
    ready_to_close: safeBoolean(body.ready_to_close),
    stage16_closed_by_receipt: safeBoolean(body.stage16_closed_by_receipt),
    missing_readbacks: stringList(body.missing_readbacks),
    current_readback: isRecord(body.current_readback) ? body.current_readback : undefined,
    completion_review: isRecord(body.completion_review) ? body.completion_review : undefined,
    stage_closure_decision: isRecord(body.stage_closure_decision) ? body.stage_closure_decision : undefined,
    selected_action_summary: parseFederationSleepContinuitySelectedActionSummary(body.selected_action_summary),
    steps,
    writes_evidence: safeBoolean(body.writes_evidence),
    writes_receipts: safeBoolean(body.writes_receipts),
    writes_registry: safeBoolean(body.writes_registry),
    writes_memory: safeBoolean(body.writes_memory),
    runs_tools: safeBoolean(body.runs_tools),
    runs_shell: safeBoolean(body.runs_shell),
    runs_git: safeBoolean(body.runs_git),
    launches_browser: safeBoolean(body.launches_browser),
    captures_screen: safeBoolean(body.captures_screen),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    marks_stage16_closed: safeBoolean(body.marks_stage16_closed),
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

export function parseFederationSleepContinuityAction(raw: unknown): FederationSleepContinuityActionReadback {
  const body = isRecord(raw) ? raw : {};
  const selectedAction = parseFederationSleepContinuityRunbookStep(body.selected_action);
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    action_projection_only: safeBoolean(body.action_projection_only),
    selected_step_id: optionalString(body.selected_step_id),
    selected_step_title: optionalString(body.selected_step_title),
    selected_action: selectedAction ?? undefined,
    primary_command: optionalString(body.primary_command),
    primary_route: optionalString(body.primary_route),
    method: optionalString(body.method),
    required_scope: optionalString(body.required_scope),
    expected_output: optionalString(body.expected_output),
    evidence_path: optionalString(body.evidence_path),
    pre_sleep_evidence_path: optionalString(body.pre_sleep_evidence_path),
    post_resume_evidence_path: optionalString(body.post_resume_evidence_path),
    blockers: stringList(body.blockers),
    prior_live_readback_blockers: stringList(body.prior_live_readback_blockers),
    pre_sleep_evidence_ready: safeBoolean(body.pre_sleep_evidence_ready),
    pre_sleep_age_seconds: safeNumber(body.pre_sleep_age_seconds, 0),
    pre_sleep_freshness_state: optionalString(body.pre_sleep_freshness_state),
    current_pre_sleep_age_guidance: optionalString(body.current_pre_sleep_age_guidance),
    current_pre_sleep_recapture_recommended: safeBoolean(body.current_pre_sleep_recapture_recommended),
    current_pre_sleep_age_warning: optionalString(body.current_pre_sleep_age_warning),
    current_pre_sleep_age_guidance_threshold_seconds: safeNumber(
      body.current_pre_sleep_age_guidance_threshold_seconds,
      0,
    ),
    pre_sleep_recapture_recommended: safeBoolean(body.pre_sleep_recapture_recommended),
    pre_sleep_recapture_reason: optionalString(body.pre_sleep_recapture_reason),
    pre_sleep_recapture_command_ready: safeBoolean(body.pre_sleep_recapture_command_ready),
    pre_sleep_recapture_command_visible: safeBoolean(body.pre_sleep_recapture_command_visible),
    pre_sleep_recapture_command: optionalString(body.pre_sleep_recapture_command),
    pre_sleep_recapture_copyable_command: optionalString(body.pre_sleep_recapture_copyable_command),
    pre_sleep_recapture_expected_output: optionalString(body.pre_sleep_recapture_expected_output),
    pre_sleep_recapture_after_run_next_step: optionalString(body.pre_sleep_recapture_after_run_next_step),
    pre_sleep_recapture_writes_evidence_when_run: safeBoolean(
      body.pre_sleep_recapture_writes_evidence_when_run,
    ),
    pre_sleep_recapture_writes_receipts_when_run: safeBoolean(
      body.pre_sleep_recapture_writes_receipts_when_run,
    ),
    pre_sleep_recapture_marks_stage16_closed_when_run: safeBoolean(
      body.pre_sleep_recapture_marks_stage16_closed_when_run,
    ),
    pre_sleep_recapture_projection_only: safeBoolean(body.pre_sleep_recapture_projection_only),
    post_resume_evidence_ready: safeBoolean(body.post_resume_evidence_ready),
    post_resume_evidence_conflict: safeBoolean(body.post_resume_evidence_conflict),
    sleep_continuity_ready: safeBoolean(body.sleep_continuity_ready),
    ready_to_close: safeBoolean(body.ready_to_close),
    stage16_closed_by_receipt: safeBoolean(body.stage16_closed_by_receipt),
    operator_action_required: safeBoolean(body.operator_action_required),
    operator_confirmation_required: safeBoolean(body.operator_confirmation_required),
    operator_confirmation_requirements: stringList(body.operator_confirmation_requirements),
    current_ready_to_run: safeBoolean(body.current_ready_to_run),
    operator_confirmation_pending: safeBoolean(body.operator_confirmation_pending),
    post_confirmation_ready_to_capture: safeBoolean(body.post_confirmation_ready_to_capture),
    sleep_resume_confirmation_is_current_blocker: safeBoolean(body.sleep_resume_confirmation_is_current_blocker),
    selected_action_readiness: parseFederationSleepContinuitySelectedActionReadiness(body.selected_action_readiness),
    operator_terminal_invocation: parseFederationSleepContinuityOperatorTerminalInvocation(
      body.operator_terminal_invocation,
    ),
    operator_sleep_resume_gate: parseFederationSleepContinuityOperatorSleepResumeGate(body.operator_sleep_resume_gate),
    operator_confirmation_handoff: parseFederationSleepContinuityOperatorConfirmationHandoff(
      body.operator_confirmation_handoff,
    ),
    after_manual_execution_readback: parseFederationSleepContinuityAfterManualExecutionReadback(
      body.after_manual_execution_readback,
    ),
    writes_evidence_when_run: safeBoolean(body.writes_evidence_when_run),
    writes_receipts_when_run: safeBoolean(body.writes_receipts_when_run),
    mutation_available_from_ui: safeBoolean(body.mutation_available_from_ui),
    writes_evidence: safeBoolean(body.writes_evidence),
    writes_receipts: safeBoolean(body.writes_receipts),
    writes_registry: safeBoolean(body.writes_registry),
    writes_memory: safeBoolean(body.writes_memory),
    runs_tools: safeBoolean(body.runs_tools),
    runs_shell: safeBoolean(body.runs_shell),
    runs_git: safeBoolean(body.runs_git),
    launches_browser: safeBoolean(body.launches_browser),
    captures_screen: safeBoolean(body.captures_screen),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    marks_stage16_closed: safeBoolean(body.marks_stage16_closed),
    routes: stringRecord(body.routes),
    governance: isRecord(body.governance) ? body.governance : undefined,
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function findFederationSleepContinuityStep(
  runbook: FederationSleepContinuityRunbook | undefined,
  id: string,
): FederationSleepContinuityRunbookStep | undefined {
  return runbook?.steps.find((step) => step.id === id);
}

function singleSleepContinuityBlocker(blockers: string[]): boolean {
  return blockers.length === 1 && blockers[0] === "workstation_sleep_continuity_validated";
}

function hasPriorLiveReadbackBlocker(blockers: string[]): boolean {
  return blockers.some((blocker) => blocker !== "workstation_sleep_continuity_validated");
}

const federationSleepContinuityLabelByState: Record<FederationSleepContinuityActionState, string> = {
  blocked_on_prior_live_readbacks: "Blocked on prior live readbacks",
  capture_pre_sleep_evidence: "Capture pre-sleep evidence",
  capture_post_resume_evidence: "Capture post-resume evidence",
  run_sleep_continuity_runtime_proof: "Run sleep-continuity runtime proof",
  record_stage16_closure_decision: "Record Stage 16 closure decision",
  stage16_closed: "Stage 16 closed by receipt",
};

function federationSleepContinuityActionState(value: unknown): FederationSleepContinuityActionState {
  const state = safeString(value);
  if (state in federationSleepContinuityLabelByState) return state as FederationSleepContinuityActionState;
  return "blocked_on_prior_live_readbacks";
}

function labelForFederationSleepContinuityState(state: FederationSleepContinuityActionState): string {
  return federationSleepContinuityLabelByState[state];
}

function buildFederationSleepContinuityPresentation(
  state: FederationSleepContinuityActionState,
  opts: {
    status: FederationStage16Status;
    runbook?: FederationSleepContinuityRunbook;
    closure?: FederationStage16ClosureDecisions;
    selectedStep?: FederationSleepContinuityRunbookStep;
    blockers: string[];
    preSleepEvidenceReady: boolean;
    postResumeEvidenceReady: boolean;
    postResumeEvidenceConflict: boolean;
    sleepContinuityReady: boolean;
    readyToClose: boolean;
    stage16ClosedByReceipt: boolean;
  },
): FederationSleepContinuityPresentation {
  const selectedStep = opts.selectedStep;
  return {
    state,
    status_label: labelForFederationSleepContinuityState(state),
    selected_step_id: selectedStep?.id,
    selected_step_title: selectedStep?.title,
    primary_command: selectedStep?.command,
    primary_route: selectedStep?.route,
    method: selectedStep?.method,
    required_scope: selectedStep?.required_scope,
    evidence_path: selectedStep?.latest_evidence_path,
    pre_sleep_evidence_path: selectedStep?.pre_sleep_evidence_path,
    post_resume_evidence_path: selectedStep?.post_resume_evidence_path,
    blockers: opts.blockers,
    prior_live_readback_blockers: [],
    pre_sleep_evidence_ready: opts.preSleepEvidenceReady,
    post_resume_evidence_ready: opts.postResumeEvidenceReady,
    post_resume_evidence_conflict: opts.postResumeEvidenceConflict,
    sleep_continuity_ready: opts.sleepContinuityReady,
    ready_to_close: opts.readyToClose,
    stage16_closed_by_receipt: opts.stage16ClosedByReceipt,
    operator_action_required: selectedStep?.operator_action_required ?? false,
    operator_confirmation_required: selectedStep?.operator_confirmation_required ?? false,
    operator_confirmation_requirements: [],
    current_ready_to_run: opts.status.sleep_continuity_action_current_ready_to_run,
    operator_confirmation_pending: opts.status.sleep_continuity_operator_confirmation_pending,
    post_confirmation_ready_to_capture: opts.status.sleep_continuity_post_confirmation_ready_to_capture,
    sleep_resume_confirmation_is_current_blocker:
      opts.status.sleep_continuity_sleep_resume_confirmation_is_current_blocker,
    selected_action_readiness: undefined,
    operator_terminal_invocation: undefined,
    operator_sleep_resume_gate: undefined,
    operator_confirmation_handoff: undefined,
    after_manual_execution_readback: undefined,
    pre_sleep_recapture_recommended: opts.runbook?.pre_sleep_recapture_recommended === true,
    pre_sleep_recapture_command_visible: opts.runbook?.pre_sleep_recapture_command_visible === true,
    pre_sleep_recapture_copyable_command: opts.runbook?.pre_sleep_recapture_copyable_command,
    writes_evidence_when_run: selectedStep?.writes_evidence_when_run ?? false,
    writes_receipts_when_run: selectedStep?.writes_receipts_when_run ?? false,
    expected_output: selectedStep?.expected_output,
    mutation_available_from_ui: false,
    next_smallest_truthful_gap:
      opts.status.next_smallest_truthful_gap ??
      opts.runbook?.next_smallest_truthful_gap ??
      opts.closure?.next_smallest_truthful_gap,
  };
}

export function presentFederationSleepContinuity(
  status: FederationStage16Status,
  runbook?: FederationSleepContinuityRunbook,
  closure?: FederationStage16ClosureDecisions,
): FederationSleepContinuityPresentation {
  const preSleepEvidenceReady = status.pre_sleep_evidence_ready || runbook?.pre_sleep_evidence_ready === true;
  const postResumeEvidenceReady = status.post_resume_evidence_ready || runbook?.post_resume_evidence_ready === true;
  const postResumeEvidenceConflict =
    status.post_resume_evidence_conflict || runbook?.post_resume_evidence_conflict === true;
  const sleepContinuityReady = status.sleep_continuity_ready || runbook?.sleep_continuity_ready === true;
  const readyToClose = status.stage16_completion_review_ready || runbook?.ready_to_close === true;
  const stage16ClosedByReceipt =
    closure?.stage16_closed_by_receipt === true ||
    runbook?.stage16_closed_by_receipt === true ||
    status.stage16_status === "stage16_closed_by_receipt";
  const blockers =
    status.completion_review_blockers.length > 0 ? status.completion_review_blockers : runbook?.missing_readbacks ?? [];

  let state: FederationSleepContinuityActionState = "blocked_on_prior_live_readbacks";
  let selectedStep: FederationSleepContinuityRunbookStep | undefined;
  if (stage16ClosedByReceipt) {
    state = "stage16_closed";
  } else if (hasPriorLiveReadbackBlocker(blockers)) {
    state = "blocked_on_prior_live_readbacks";
  } else if (readyToClose) {
    state = "record_stage16_closure_decision";
    selectedStep = findFederationSleepContinuityStep(runbook, "record_operator_stage_closure_decision");
  } else if (postResumeEvidenceReady) {
    state = "run_sleep_continuity_runtime_proof";
    selectedStep = findFederationSleepContinuityStep(runbook, "commit_sleep_continuity_readback");
  } else if (preSleepEvidenceReady) {
    state = "capture_post_resume_evidence";
    selectedStep = findFederationSleepContinuityStep(runbook, "capture_post_resume_evidence");
  } else if (
    singleSleepContinuityBlocker(blockers) ||
    runbook?.status === "ready_for_operator_sleep_resume" ||
    runbook?.status === "ready_for_pre_sleep_evidence"
  ) {
    state = "capture_pre_sleep_evidence";
    selectedStep = findFederationSleepContinuityStep(runbook, "capture_pre_sleep_evidence");
  }

  return buildFederationSleepContinuityPresentation(state, {
    status,
    runbook,
    closure,
    selectedStep,
    blockers,
    preSleepEvidenceReady,
    postResumeEvidenceReady,
    postResumeEvidenceConflict,
    sleepContinuityReady,
    readyToClose,
    stage16ClosedByReceipt,
  });
}

export function presentFederationSleepContinuityAction(
  action: FederationSleepContinuityActionReadback,
): FederationSleepContinuityPresentation {
  const state = federationSleepContinuityActionState(action.status);
  const selectedStep = action.selected_action;
  return {
    state,
    status_label: labelForFederationSleepContinuityState(state),
    selected_step_id: action.selected_step_id,
    selected_step_title: action.selected_step_title ?? selectedStep?.title,
    primary_command: action.primary_command ?? selectedStep?.command,
    primary_route: action.primary_route ?? selectedStep?.route,
    readback_route: action.routes.sleep_continuity_action,
    runbook_route: action.routes.sleep_continuity_runbook,
    closure_decision_route: action.routes.stage_closure_decision,
    method: action.method ?? selectedStep?.method,
    required_scope: action.required_scope ?? selectedStep?.required_scope,
    evidence_path: action.evidence_path ?? selectedStep?.latest_evidence_path,
    pre_sleep_evidence_path: action.pre_sleep_evidence_path ?? selectedStep?.pre_sleep_evidence_path,
    post_resume_evidence_path: action.post_resume_evidence_path ?? selectedStep?.post_resume_evidence_path,
    blockers: action.blockers,
    prior_live_readback_blockers: action.prior_live_readback_blockers,
    pre_sleep_evidence_ready: action.pre_sleep_evidence_ready,
    pre_sleep_recapture_recommended: action.pre_sleep_recapture_recommended,
    pre_sleep_recapture_command_visible: action.pre_sleep_recapture_command_visible,
    pre_sleep_recapture_copyable_command: action.pre_sleep_recapture_copyable_command,
    post_resume_evidence_ready: action.post_resume_evidence_ready,
    post_resume_evidence_conflict: action.post_resume_evidence_conflict,
    sleep_continuity_ready: action.sleep_continuity_ready,
    ready_to_close: action.ready_to_close,
    stage16_closed_by_receipt: action.stage16_closed_by_receipt,
    operator_action_required: action.operator_action_required || selectedStep?.operator_action_required === true,
    operator_confirmation_required:
      action.operator_confirmation_required || selectedStep?.operator_confirmation_required === true,
    operator_confirmation_requirements: action.operator_confirmation_requirements,
    current_ready_to_run: action.current_ready_to_run,
    operator_confirmation_pending: action.operator_confirmation_pending,
    post_confirmation_ready_to_capture: action.post_confirmation_ready_to_capture,
    sleep_resume_confirmation_is_current_blocker: action.sleep_resume_confirmation_is_current_blocker,
    selected_action_readiness: action.selected_action_readiness,
    operator_terminal_invocation: action.operator_terminal_invocation,
    operator_sleep_resume_gate: action.operator_sleep_resume_gate,
    operator_confirmation_handoff: action.operator_confirmation_handoff,
    after_manual_execution_readback: action.after_manual_execution_readback,
    writes_evidence_when_run: action.writes_evidence_when_run || selectedStep?.writes_evidence_when_run === true,
    writes_receipts_when_run: action.writes_receipts_when_run || selectedStep?.writes_receipts_when_run === true,
    expected_output: action.expected_output ?? selectedStep?.expected_output,
    mutation_available_from_ui: false,
    next_smallest_truthful_gap: action.next_smallest_truthful_gap,
  };
}

export type FederationEndpoints = {
  status: (q?: { actor?: string }) => string;
  completionReview: () => string;
  sleepContinuityRunbook: () => string;
  sleepContinuityAction: (q?: { actor?: string }) => string;
  sleepResumeConfirmations: (q?: { limit?: number; actor?: string }) => string;
  sleepResumeConfirmation: () => string;
  sleepResumeConfirmationActorReadiness: (q?: { actor?: string }) => string;
  sleepResumeConfirmationOperatorChecklist: (q?: { actor?: string }) => string;
  sleepResumeReceiptBackedSequenceReadiness: (q?: { actor?: string }) => string;
  stageClosureDecisions: (q?: { limit?: number }) => string;
  liveRuntimeReadbacks: (q?: { limit?: number }) => string;

  instancesList: (q?: { status?: string; limit?: number; offset?: number; tags?: string[] }) => string;
  instanceGet: (id: string) => string;

  delegationsList: (q?: { status?: string; limit?: number; offset?: number }) => string;

  consensusLogsList: (q?: {
    level?: string;
    instance_id?: string;
    limit?: number;
    offset?: number;
    start_ts?: number;
    end_ts?: number;
  }) => string;

  sharedKnowledgeList: (q?: { kind?: string; domain?: string; limit?: number; offset?: number; tags?: string[] }) => string;
};

export function defaultFederationEndpoints(): FederationEndpoints {
  return {
    status: (q) => `/federation/status${buildQuery({ actor: q?.actor })}`,
    completionReview: () => "/federation/completion-review",
    sleepContinuityRunbook: () => "/federation/sleep-continuity-runbook",
    sleepContinuityAction: (q) => `/federation/sleep-continuity-action${buildQuery({ actor: q?.actor })}`,
    sleepResumeConfirmations: (q) =>
      `/federation/sleep-resume-confirmations${buildQuery({ limit: q?.limit, actor: q?.actor })}`,
    sleepResumeConfirmation: () => "/federation/sleep-resume-confirmation",
    sleepResumeConfirmationActorReadiness: (q) =>
      `/federation/sleep-resume-confirmation/actor-readiness${buildQuery({ actor: q?.actor })}`,
    sleepResumeConfirmationOperatorChecklist: (q) =>
      `/federation/sleep-resume-confirmation/operator-checklist${buildQuery({ actor: q?.actor })}`,
    sleepResumeReceiptBackedSequenceReadiness: (q) =>
      `/federation/sleep-resume-confirmation/receipt-backed-sequence-readiness${buildQuery({ actor: q?.actor })}`,
    stageClosureDecisions: (q) => `/federation/stage-closure-decisions${buildQuery({ limit: q?.limit })}`,
    liveRuntimeReadbacks: (q) => `/federation/live-runtime-readbacks${buildQuery({ limit: q?.limit })}`,

    instancesList: (q) =>
      `/federation/instances/list${buildQuery({
        status: q?.status,
        limit: q?.limit,
        offset: q?.offset,
        tags: q?.tags,
      })}`,
    instanceGet: (id) => `/federation/instances/get${buildQuery({ id })}`,

    delegationsList: (q) =>
      `/federation/delegations/list${buildQuery({
        status: q?.status,
        limit: q?.limit,
        offset: q?.offset,
      })}`,

    consensusLogsList: (q) =>
      `/federation/consensus_logs/list${buildQuery({
        level: q?.level,
        instance_id: q?.instance_id,
        limit: q?.limit,
        offset: q?.offset,
        start_ts: typeof q?.start_ts === "number" ? normalizeTs(q.start_ts) : undefined,
        end_ts: typeof q?.end_ts === "number" ? normalizeTs(q.end_ts) : undefined,
      })}`,

    sharedKnowledgeList: (q) =>
      `/federation/shared_knowledge/list${buildQuery({
        kind: q?.kind,
        domain: q?.domain,
        limit: q?.limit,
        offset: q?.offset,
        tags: q?.tags,
      })}`,
  };
}

export type FederationClientOptions = {
  endpoints?: FederationEndpoints;
  defaultTimeoutMs?: number;
};

export class FederationClient {
  readonly baseUrl: string;
  readonly endpoints: FederationEndpoints;
  readonly defaultTimeoutMs: number;

  constructor(baseUrl: string, opts?: FederationClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("FederationClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultFederationEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
  }

  private url(path: string): string {
    if (!path.startsWith("/")) path = `/${path}`;
    return `${this.baseUrl}${path}`;
  }

  async getStatus(opts?: { actor?: string; signal?: AbortSignal; timeoutMs?: number }): Promise<FederationStage16Status> {
    const json = await fetchJson(this.url(this.endpoints.status({ actor: opts?.actor })), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationStage16Status(json);
  }

  async getLiveRuntimeReadbacks(opts?: {
    limit?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationLiveRuntimeReadbacks> {
    const json = await fetchJson(this.url(this.endpoints.liveRuntimeReadbacks({ limit: opts?.limit })), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationLiveRuntimeReadbacks(json);
  }

  async getCompletionReview(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<FederationCompletionReview> {
    const json = await fetchJson(this.url(this.endpoints.completionReview()), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationCompletionReview(json);
  }

  async getSleepContinuityRunbook(opts?: {
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepContinuityRunbook> {
    const json = await fetchJson(this.url(this.endpoints.sleepContinuityRunbook()), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationSleepContinuityRunbook(json);
  }

  async getSleepContinuityAction(opts?: {
    actor?: string;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepContinuityActionReadback> {
    const json = await fetchJson(this.url(this.endpoints.sleepContinuityAction({ actor: opts?.actor })), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationSleepContinuityAction(json);
  }

  async getSleepResumeConfirmations(opts?: {
    limit?: number;
    actor?: string;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepResumeConfirmations> {
    const json = await fetchJson(
      this.url(this.endpoints.sleepResumeConfirmations({ limit: opts?.limit, actor: opts?.actor })),
      {
        method: "GET",
        signal: opts?.signal,
        timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
      },
    );
    return parseFederationSleepResumeConfirmations(json);
  }

  async getSleepResumeConfirmationActorReadiness(opts?: {
    actor?: string;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepResumeConfirmationActorReadiness> {
    const json = await fetchJson(
      this.url(this.endpoints.sleepResumeConfirmationActorReadiness({ actor: opts?.actor })),
      {
        method: "GET",
        signal: opts?.signal,
        timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
      },
    );
    return parseFederationSleepResumeConfirmationActorReadiness(json);
  }

  async getSleepResumeConfirmationOperatorChecklist(opts?: {
    actor?: string;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepResumeOperatorChecklist> {
    const json = await fetchJson(
      this.url(this.endpoints.sleepResumeConfirmationOperatorChecklist({ actor: opts?.actor })),
      {
        method: "GET",
        signal: opts?.signal,
        timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
      },
    );
    return parseFederationSleepResumeOperatorChecklist(json);
  }

  async getSleepResumeReceiptBackedSequenceReadiness(opts?: {
    actor?: string;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepResumeReceiptBackedSequenceReadiness> {
    const json = await fetchJson(
      this.url(this.endpoints.sleepResumeReceiptBackedSequenceReadiness({ actor: opts?.actor })),
      {
        method: "GET",
        signal: opts?.signal,
        timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
      },
    );
    return parseFederationSleepResumeReceiptBackedSequenceReadiness(json);
  }

  async recordSleepResumeConfirmation(opts: {
    actor: string;
    reason: string;
    preSleepEvidencePath?: string;
    operatorConfirmedSleepResume: true;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepResumeConfirmationRecordResponse> {
    const json = await fetchJson(this.url(this.endpoints.sleepResumeConfirmation()), {
      method: "POST",
      signal: opts.signal,
      timeoutMs: opts.timeoutMs ?? this.defaultTimeoutMs,
      body: JSON.stringify({
        actor: opts.actor,
        reason: opts.reason,
        operator_confirmed_sleep_resume: opts.operatorConfirmedSleepResume,
        pre_sleep_evidence_path: opts.preSleepEvidencePath,
      }),
    });
    const parsed = parseFederationSleepResumeConfirmationRecordResponse(json);
    assertFederationMutationAllowed(parsed, "Sleep/resume confirmation receipt was denied.");
    return parsed;
  }

  async getStageClosureDecisions(opts?: {
    limit?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationStage16ClosureDecisions> {
    const json = await fetchJson(this.url(this.endpoints.stageClosureDecisions({ limit: opts?.limit })), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationStage16ClosureDecisions(json);
  }

  async getSleepContinuityPresentation(opts?: {
    actor?: string;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepContinuityPresentation> {
    const action = await this.getSleepContinuityAction(opts);
    return presentFederationSleepContinuityAction(action);
  }

  async listInstances(opts?: {
    status?: FederationInstanceStatus;
    limit?: number;
    offset?: number;
    tags?: string[];
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationListResponse<FederationInstance>> {
    const url = this.url(
      this.endpoints.instancesList({
        status: opts?.status as string | undefined,
        limit: opts?.limit,
        offset: opts?.offset,
        tags: opts?.tags,
      }),
    );

    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).instances)
        ? ((json as Record<string, unknown>).instances as unknown[])
        : [];

    const items = raw.map(parseInstance).filter((x): x is FederationInstance => x !== null);
    return { items };
  }

  async getInstance(
    id: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<FederationInstanceDetail | null> {
    const safeId = (id || "").trim();
    if (!safeId) return null;

    const url = this.url(this.endpoints.instanceGet(safeId));
    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    return parseInstanceDetail(json);
  }

  /**
   * Batch instance get (client-side fan-out).
   * No new backend contract required.
   *
   * - Dedupes ids
   * - Concurrency-limited
   * - Preserves original order; omits nulls
   */
  async getInstances(
    ids: string[],
    opts?: {
      signal?: AbortSignal;
      timeoutMs?: number;
      concurrency?: number;
      tolerateFailures?: boolean;
    },
  ): Promise<FederationInstanceDetail[]> {
    const original = (ids ?? []).map((s) => (s || "").trim()).filter((s) => s.length > 0);
    if (original.length === 0) return [];

    const unique: string[] = [];
    const seen = new Set<string>();
    for (const id of original) {
      if (!seen.has(id)) {
        seen.add(id);
        unique.push(id);
      }
    }

    const concurrency = Math.min(Math.max(Math.floor(opts?.concurrency ?? 6), 1), 16);
    const tolerateFailures = Boolean(opts?.tolerateFailures ?? true);

    const resultMap = new Map<string, FederationInstanceDetail | null>();
    for (const id of unique) resultMap.set(id, null);

    let cursor = 0;
    const worker = async () => {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const i = cursor++;
        if (i >= unique.length) return;

        const id = unique[i];
        try {
          const d = await this.getInstance(id, { signal: opts?.signal, timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs });
          resultMap.set(id, d);
        } catch (err) {
          if (!tolerateFailures) throw err;
          resultMap.set(id, null);
        }
      }
    };

    await Promise.all(Array.from({ length: Math.min(concurrency, unique.length) }, () => worker()));

    const out: FederationInstanceDetail[] = [];
    for (const id of original) {
      const v = resultMap.get(id) ?? null;
      if (v) out.push(v);
    }
    return out;
  }

  async listDelegations(opts?: {
    status?: FederationDelegationStatus;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationListResponse<FederationDelegation>> {
    const url = this.url(
      this.endpoints.delegationsList({
        status: opts?.status as string | undefined,
        limit: opts?.limit,
        offset: opts?.offset,
      }),
    );

    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).delegations)
        ? ((json as Record<string, unknown>).delegations as unknown[])
        : [];

    const items = raw.map(parseDelegation).filter((x): x is FederationDelegation => x !== null);
    return { items };
  }

  async listConsensusLogs(opts?: {
    level?: ConsensusLogLevel;
    instance_id?: string;
    start_ts?: number;
    end_ts?: number;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationListResponse<ConsensusLogEntry>> {
    const url = this.url(
      this.endpoints.consensusLogsList({
        level: opts?.level as string | undefined,
        instance_id: opts?.instance_id,
        start_ts: opts?.start_ts,
        end_ts: opts?.end_ts,
        limit: opts?.limit,
        offset: opts?.offset,
      }),
    );

    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).logs)
        ? ((json as Record<string, unknown>).logs as unknown[])
        : [];

    const items = raw.map(parseConsensusLog).filter((x): x is ConsensusLogEntry => x !== null);
    return { items };
  }

  async listSharedKnowledge(opts?: {
    kind?: SharedKnowledgeKind;
    domain?: string;
    tags?: string[];
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationListResponse<SharedKnowledgeItem>> {
    const url = this.url(
      this.endpoints.sharedKnowledgeList({
        kind: opts?.kind as string | undefined,
        domain: opts?.domain,
        tags: opts?.tags,
        limit: opts?.limit,
        offset: opts?.offset,
      }),
    );

    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).knowledge)
        ? ((json as Record<string, unknown>).knowledge as unknown[])
        : [];

    const items = raw.map(parseSharedKnowledge).filter((x): x is SharedKnowledgeItem => x !== null);
    return { items };
  }
}
