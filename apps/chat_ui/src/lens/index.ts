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
  url_entrypoint_ready?: boolean;
  url_entrypoint: Record<string, unknown>;
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

export type LensResidentRuntimeExecutionReceipts = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  execute_route?: string;
  host_supervision_execute_route?: string;
  host_supervision_executions_route?: string;
  limit: number;
  total: number;
  latest?: Record<string, unknown>;
  latest_receipt_id?: string;
  latest_status?: string;
  latest_supervision_mode?: string;
  latest_resident_host_process?: boolean;
  latest_resident_supervised_runtime?: boolean;
  latest_stop_command?: string;
  latest_next_smallest_truthful_gap?: string;
  resident_supervised_runtime_receipt_observed: boolean;
  resident_claim_allowed: boolean;
  items: Array<Record<string, unknown>>;
  governance: Record<string, unknown>;
};

export type LensResidentRuntimeAuthorityReadiness = {
  ok: boolean;
  kind?: string;
  status?: string;
  audit_status?: string;
  route?: string;
  preflight_route?: string;
  policy_route?: string;
  authority_grant_route?: string;
  authority_grants_route?: string;
  denials_route?: string;
  plan_route?: string;
  execute_route?: string;
  approval_id?: string;
  actor?: string;
  ready: boolean;
  grant_ready: boolean;
  authority_grant_ready: boolean;
  runtime_ready: boolean;
  resident_claim_allowed: boolean;
  boundary_observed: boolean;
  authority_granted: boolean;
  resident_runtime_execution_authority: boolean;
  denial_receipt_readback_ready: boolean;
  grant_receipt_readback_ready: boolean;
  receipt_count: number;
  latest_receipt_id?: string;
  denial_receipt_count: number;
  latest_denial_receipt_id?: string;
  requirements_total: number;
  requirements_ready_total: number;
  requirements_blocked_total: number;
  requirements: Array<Record<string, unknown>>;
  blocked_requirements: string[];
  operator_surface_readback_ready?: boolean;
  first_blocked_requirement?: string;
  first_blocked_requirement_handoff?: LensRuntimeLoopRequirementHandoff;
  blocked_requirement_handoffs: LensRuntimeLoopRequirementHandoff[];
  blockers: string[];
  source_readbacks: Record<string, string>;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
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
  operator_surface_readback_ready?: boolean;
  first_blocked_requirement?: string;
  first_blocked_requirement_handoff?: LensRuntimeLoopRequirementHandoff;
  blocked_requirement_handoffs: LensRuntimeLoopRequirementHandoff[];
  blockers: string[];
  source_readbacks: Record<string, string>;
  evidence: string[];
  governance: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  message?: string;
};

export type LensRuntimeLoopRequirementHandoff = {
  id?: string;
  label?: string;
  status?: string;
  route?: string;
  readiness_route?: string;
  request_route?: string;
  requests_route?: string;
  grant_route?: string;
  grants_route?: string;
  denials_route?: string;
  execution_readiness_route?: string;
  execution_request_route?: string;
  execution_requests_route?: string;
  execution_grant_route?: string;
  execution_grants_route?: string;
  summon_route?: string;
  tray_route?: string;
  overlay_route?: string;
  loop_route?: string;
  next_step?: string;
  authority_required?: string;
  authority_granted?: boolean;
  blockers: string[];
  would_execute?: boolean;
  would_mutate?: boolean;
};

export type LensHostSupervisionAuthorityRequests = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  request_route?: string;
  grant_route?: string;
  grants_route?: string;
  readiness_route?: string;
  active_grant_receipt_id?: string;
  decision_route?: string;
  approval_action?: string;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  emergency_count: number;
  total_count: number;
  latest?: Record<string, unknown>;
  items: Array<Record<string, unknown>>;
  by_status: Record<string, Array<Record<string, unknown>>>;
  authority_granted: boolean;
  resident_claim_allowed: boolean;
  governance: Record<string, unknown>;
};

export type LensResidentRuntimeAuthorityRequests = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  request_route?: string;
  grant_route?: string;
  grants_route?: string;
  readiness_route?: string;
  denials_route?: string;
  active_grant_receipt_id?: string;
  policy_route?: string;
  plan_route?: string;
  execute_route?: string;
  decision_route?: string;
  approval_action?: string;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  emergency_count: number;
  total_count: number;
  latest?: Record<string, unknown>;
  items: Array<Record<string, unknown>>;
  by_status: Record<string, Array<Record<string, unknown>>>;
  authority_granted: boolean;
  resident_runtime_execution_authority: boolean;
  resident_claim_allowed: boolean;
  execution_authority: boolean;
  local_process_launch_authority: boolean;
  process_supervision_authority: boolean;
  service_control_authority: boolean;
  receipt_write_authority: boolean;
  memory_write: boolean;
  governance: Record<string, unknown>;
};

export type LensTrayAuthorityRequests = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  request_route?: string;
  authority_route?: string;
  grants_route?: string;
  execute_route?: string;
  executions_route?: string;
  action?: string;
  approval_counts: Record<string, number>;
  latest?: Record<string, unknown>;
  pending: Array<Record<string, unknown>>;
  approved: Array<Record<string, unknown>>;
  rejected: Array<Record<string, unknown>>;
  emergency: Array<Record<string, unknown>>;
  active_authority_grant: Record<string, unknown>;
  authority_granted: boolean;
  tray_presence_authority: boolean;
  tray_presence: boolean;
  registers_tray: boolean;
  starts_tray: boolean;
  stops_tray: boolean;
  governance: Record<string, unknown>;
};

export type LensTrayExecutionReceipts = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  execute_route?: string;
  authority_route?: string;
  authority_grants_route?: string;
  limit: number;
  total: number;
  latest?: Record<string, unknown>;
  latest_status?: string;
  latest_tray_presence?: boolean;
  latest_next_smallest_truthful_gap?: string;
  items: Array<Record<string, unknown>>;
  governance: Record<string, unknown>;
};

export type LensOsBindingAuthorityRequests = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  request_route?: string;
  authority_route?: string;
  grants_route?: string;
  execute_route?: string;
  denials_route?: string;
  execution_readiness_route?: string;
  readiness_route?: string;
  plan_route?: string;
  active_grant_receipt_id?: string;
  approval_action?: string;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  emergency_count: number;
  total_count: number;
  latest?: Record<string, unknown>;
  items: Array<Record<string, unknown>>;
  by_status: Record<string, Array<Record<string, unknown>>>;
  authority_granted: boolean;
  os_level_command_palette_binding_authority: boolean;
  os_level_command_palette: boolean;
  registers_hotkey: boolean;
  governance: Record<string, unknown>;
};

export type LensOsBindingExecutionReadiness = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  ready: boolean;
  execution_ready: boolean;
  authority_granted: boolean;
  os_level_command_palette: boolean;
  blocked_requirements: string[];
  blockers: string[];
  next_smallest_truthful_gap?: string;
  active_grant_receipt_id?: string;
  governance: Record<string, unknown>;
};

export type LensOsBindingExecutionReceipts = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  execute_route?: string;
  authority_route?: string;
  authority_grants_route?: string;
  limit: number;
  total: number;
  latest?: Record<string, unknown>;
  latest_status?: string;
  latest_global_hotkey_binding?: boolean;
  latest_next_smallest_truthful_gap?: string;
  items: Array<Record<string, unknown>>;
  governance: Record<string, unknown>;
};

export type LensOverlayAuthorityRequests = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  request_route?: string;
  authority_route?: string;
  grants_route?: string;
  execute_route?: string;
  executions_route?: string;
  action?: string;
  approval_counts: Record<string, number>;
  latest?: Record<string, unknown>;
  pending: Array<Record<string, unknown>>;
  approved: Array<Record<string, unknown>>;
  rejected: Array<Record<string, unknown>>;
  emergency: Array<Record<string, unknown>>;
  active_authority_grant: Record<string, unknown>;
  authority_granted: boolean;
  overlay_window_authority: boolean;
  overlay_window: boolean;
  governance: Record<string, unknown>;
};

export type LensOverlayExecutionReceipts = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  execute_route?: string;
  authority_route?: string;
  authority_grants_route?: string;
  limit: number;
  total: number;
  latest?: Record<string, unknown>;
  latest_status?: string;
  latest_overlay_window?: boolean;
  latest_next_smallest_truthful_gap?: string;
  items: Array<Record<string, unknown>>;
  governance: Record<string, unknown>;
};

export type LensSummonAuthorityRequests = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  request_route?: string;
  authority_route?: string;
  grants_route?: string;
  execute_route?: string;
  executions_route?: string;
  action?: string;
  approval_counts: Record<string, number>;
  latest?: Record<string, unknown>;
  pending: Array<Record<string, unknown>>;
  approved: Array<Record<string, unknown>>;
  rejected: Array<Record<string, unknown>>;
  emergency: Array<Record<string, unknown>>;
  active_authority_grant: Record<string, unknown>;
  authority_granted: boolean;
  summon_binding: boolean;
  summon_anywhere: boolean;
  governance: Record<string, unknown>;
};

export type LensSummonExecutionReceipts = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  execute_route?: string;
  authority_route?: string;
  authority_grants_route?: string;
  limit: number;
  total: number;
  latest?: Record<string, unknown>;
  latest_status?: string;
  latest_summon_binding?: boolean;
  latest_summon_anywhere?: boolean;
  latest_next_smallest_truthful_gap?: string;
  items: Array<Record<string, unknown>>;
  governance: Record<string, unknown>;
};

export type LensPersistentSupervisionAuthorityRequests = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  request_route?: string;
  grant_route?: string;
  grants_route?: string;
  readiness_route?: string;
  preflight_route?: string;
  enablement_route?: string;
  execution_route?: string;
  decision_route?: string;
  approval_action?: string;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  emergency_count: number;
  total_count: number;
  latest?: Record<string, unknown>;
  items: Array<Record<string, unknown>>;
  by_status: Record<string, Array<Record<string, unknown>>>;
  authority_granted: boolean;
  service_config_write_authority: boolean;
  persistent_supervision_execution_authority: boolean;
  persistent_supervision_enablement_allowed: boolean;
  resident_claim_allowed: boolean;
  active_enablement_authority_grant_receipt_id?: string;
  active_execution_authority_grant_receipt_id?: string;
  governance: Record<string, unknown>;
};

export type LensPersistentSupervisionGrantReceipts = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  authority_route?: string;
  request_route?: string;
  requests_route?: string;
  readiness_route?: string;
  boundary_route?: string;
  limit: number;
  total: number;
  latest?: Record<string, unknown>;
  active_latest: Record<string, unknown>;
  authority_granted: boolean;
  service_config_write_authority: boolean;
  persistent_supervision_execution_authority: boolean;
  persistent_supervision_enablement_allowed: boolean;
  resident_claim_allowed: boolean;
  items: Array<Record<string, unknown>>;
  governance: Record<string, unknown>;
};

export type LensPersistentSupervisionExecutionReadiness = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  ready: boolean;
  approval_ready: boolean;
  request_readback_ready: boolean;
  request_pending_count: number;
  request_approved_count: number;
  request_total_count: number;
  latest_request_approval_id?: string;
  boundary_observed: boolean;
  enablement_authority_granted: boolean;
  active_enablement_authority_grant_receipt_id?: string;
  execution_authority_granted: boolean;
  active_execution_authority_grant_receipt_id?: string;
  persistent_supervision_enablement_allowed: boolean;
  service_config_updated: boolean;
  service_config_write_authority: boolean;
  persistent_supervision_execution_authority: boolean;
  receipt_write_authority: boolean;
  resident_claim_allowed: boolean;
  requirements_total: number;
  requirements_ready_total: number;
  requirements_blocked_total: number;
  blocked_requirements: string[];
  operator_surface_readback_ready: boolean;
  first_blocked_requirement?: string;
  first_blocked_requirement_handoff: Record<string, unknown>;
  blocked_requirement_handoffs: Array<Record<string, unknown>>;
  next_smallest_truthful_gap?: string;
  blockers: string[];
  governance: Record<string, unknown>;
};

export type LensPersistentSupervisionExecutionReceipts = {
  ok: boolean;
  kind?: string;
  status?: string;
  route?: string;
  execution_route?: string;
  readiness_route?: string;
  authority_grants_route?: string;
  limit: number;
  total: number;
  latest?: Record<string, unknown>;
  service_config_updated: boolean;
  persistent_supervision_enablement_allowed: boolean;
  persistent_supervision_ready: boolean;
  resident_claim_allowed: boolean;
  latest_service_config_path?: string;
  items: Array<Record<string, unknown>>;
  governance: Record<string, unknown>;
};

export type LensResidentHost = {
  route?: string;
  status?: string;
  contract_status?: string;
  availability?: string;
  activation_denial_receipts_route?: string;
  activation_denial_receipts: LensActivationDenialReceipts;
  supervision_authority_request_route?: string;
  supervision_authority_requests_route?: string;
  supervision_authority_requests: LensHostSupervisionAuthorityRequests;
  resident_runtime_authority_request_route?: string;
  resident_runtime_authority_requests_route?: string;
  resident_runtime_authority_requests: LensResidentRuntimeAuthorityRequests;
  resident_runtime_authority_grant_route?: string;
  resident_runtime_authority_grant: Record<string, unknown>;
  resident_runtime_authority_grant_receipts_route?: string;
  resident_runtime_authority_grant_receipts: Record<string, unknown>;
  resident_runtime_authority_grant_readiness_route?: string;
  resident_runtime_authority_grant_readiness: LensResidentRuntimeAuthorityReadiness;
  resident_runtime_execution_receipts_route?: string;
  resident_runtime_execution_receipts: LensResidentRuntimeExecutionReceipts;
  runtime_loop_readiness_route?: string;
  runtime_loop_readiness: LensRuntimeLoopReadiness;
  persistent_supervision_enablement_authority_requests_route?: string;
  persistent_supervision_enablement_authority_requests: LensPersistentSupervisionAuthorityRequests;
  persistent_supervision_enablement_authority_grant_route?: string;
  persistent_supervision_enablement_authority_grants_route?: string;
  persistent_supervision_enablement_authority_grants: LensPersistentSupervisionGrantReceipts;
  persistent_supervision_enablement_execution_request_route?: string;
  persistent_supervision_enablement_execution_requests_route?: string;
  persistent_supervision_enablement_execution_requests: LensPersistentSupervisionAuthorityRequests;
  persistent_supervision_enablement_execution_authority_grant_route?: string;
  persistent_supervision_enablement_execution_authority_grants_route?: string;
  persistent_supervision_enablement_execution_authority_grants: LensPersistentSupervisionGrantReceipts;
  persistent_supervision_enablement_execution_apply_route?: string;
  persistent_supervision_enablement_execution_readiness_route?: string;
  persistent_supervision_enablement_execution_readiness: LensPersistentSupervisionExecutionReadiness;
  persistent_supervision_enablement_execution_receipts_route?: string;
  persistent_supervision_enablement_execution_receipts: LensPersistentSupervisionExecutionReceipts;
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

export type LensStage6ClosureHandoff = {
  next_step?: string;
  route?: string;
  readiness_route?: string;
  summon_route?: string;
  preflight_route?: string;
  status_route?: string;
  surface_route?: string;
  host_route?: string;
  runtime_loop_readiness_route?: string;
  runtime_loop_route?: string;
  resident_runtime_plan_route?: string;
  tray_route?: string;
  overlay_route?: string;
  proof_script?: string;
  child_proof_script?: string;
  authority_required?: string;
  next_smallest_truthful_gap?: string;
  first_blocker_family?: string;
  first_blocker_family_next_smallest_truthful_gap?: string;
  blocked_families: string[];
  read_only_contract?: boolean;
  diagnostic_only?: boolean;
  would_execute?: boolean;
  would_mutate?: boolean;
  first_blocker_family_handoff: Record<string, unknown>;
  first_blocker_family_completion_audit_handoff: Record<string, unknown>;
  summon_anywhere_family_chain_completion_audit_handoff: Record<string, unknown>;
  checkpoint_proof_handoff: Record<string, unknown>;
};

export type LensStage6ClosureCriterion = {
  id?: string;
  label?: string;
  ready?: boolean;
  status?: string;
  evidence: string[];
  blockers: string[];
  basis?: string;
  next_smallest_truthful_gap?: string;
  handoff?: LensStage6ClosureHandoff;
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

export type LensStage6NextHandoff = {
  kind?: string;
  status?: string;
  ready_to_close: boolean;
  stage_next_smallest_truthful_gap?: string;
  next_smallest_truthful_gap?: string;
  recommended_next_slice?: string;
  recommended_handoff_source?: string;
  recommended_proof_script?: string;
  recommended_route?: string;
  recommended_readiness_route?: string;
  recommended_request_route?: string;
  recommended_requests_route?: string;
  recommended_grant_route?: string;
  recommended_grants_route?: string;
  recommended_denials_route?: string;
  recommended_execution_readiness_route?: string;
  authority_required?: string;
  recommended_prerequisites_handoff_source?: string;
  recommended_prerequisites_next_slice?: string;
  recommended_prerequisites_proof_script?: string;
  recommended_prerequisites_route?: string;
  recommended_prerequisites_readiness_route?: string;
  recommended_prerequisites_authority_required?: string;
  recommended_first_missing_handoff_source?: string;
  recommended_first_missing_next_slice?: string;
  recommended_first_missing_proof_script?: string;
  recommended_first_missing_route?: string;
  recommended_first_missing_readiness_route?: string;
  recommended_first_missing_authority_required?: string;
  first_blocked_criterion?: string;
  first_blocked_criterion_next_smallest_truthful_gap?: string;
  persistent_supervision_required_prerequisites_observed: boolean;
  persistent_supervision_missing_required_before_enable: string[];
  persistent_supervision_first_missing_required_before_enable?: string;
  persistent_supervision_first_missing_requirement_handoff: Record<string, unknown>;
  persistent_supervision_required_prerequisites_handoff: Record<string, unknown>;
  activation_execution_handoff_observed: boolean;
  activation_execution_handoff: Record<string, unknown>;
  persistent_supervision_enablement_authority_handoff_observed: boolean;
  persistent_supervision_enablement_authority_handoff: Record<string, unknown>;
  resident_runtime_candidate_handoff_observed: boolean;
  resident_runtime_candidate_handoff: Record<string, unknown>;
  governance: Record<string, unknown>;
};

export type LensStage6OperatorAction = {
  id?: string;
  route?: string;
  method?: string;
  approval_action?: string;
  requires: string[];
  mode?: string;
  live_effect?: string;
  operator_supplied_values_required?: boolean;
  script_would_execute?: boolean;
  script_would_mutate?: boolean;
  approved_approval_id?: string;
  active_approval_id?: string;
  host_supervision_active_approval_id?: string;
  operator_command?: LensStage6OperatorCommand;
};

export type LensStage6OperatorCommand = {
  command?: string;
  mode?: string;
  requires_confirmation?: boolean;
  requires_approval_id?: boolean;
  requires_operator_approval_decision?: boolean;
  available_now?: boolean;
  preview_only?: boolean;
  availability_reason?: string;
};

export type LensStage6PrerequisiteStep = {
  id?: string;
  family?: string;
  route?: string;
  readiness_route?: string;
  ready?: boolean;
  status?: string;
  requirement_state?: string;
  blocker?: string;
  blocked_reason?: string;
  proof_script?: string;
  next_smallest_truthful_gap?: string;
  authority_state: Record<string, unknown>;
  actions: LensStage6OperatorAction[];
  next_operator_action: LensStage6OperatorAction;
  script_would_execute?: boolean;
  script_would_mutate?: boolean;
};

export type LensStage6PrerequisiteBringup = {
  ok: boolean;
  kind?: string;
  status?: string;
  mode?: string;
  stage?: string;
  stage_state?: string;
  ready_to_close: boolean;
  acceptance_criterion?: string;
  closure_next_smallest_truthful_gap?: string;
  persistent_supervision_next_smallest_truthful_gap?: string;
  current_truthful_gap?: string;
  current_truthful_gap_basis?: string;
  current_first_missing_requirement?: string;
  current_first_missing_truthful_gap?: string;
  raw_persistent_supervision_next_smallest_truthful_gap?: string;
  required_before_enable: string[];
  missing_required_before_enable: string[];
  required_before_enable_ready: boolean;
  first_missing_required_before_enable?: string;
  first_missing_requirement_handoff: Record<string, unknown>;
  ordered_prerequisite_steps: LensStage6PrerequisiteStep[];
  persistent_supervision_enablement_steps: LensStage6OperatorAction[];
  next_operator_action: LensStage6OperatorAction;
  next_operator_action_requirement?: string;
  next_operator_command: LensStage6OperatorCommand;
  operator_sequence: LensStage6OperatorAction[];
  operator_sequence_command_availability: Record<string, unknown>;
  checks: Array<Record<string, unknown>>;
  evidence: string[];
  governance: Record<string, unknown>;
};

export type LensStage6OperatorSequenceCommandAvailability = {
  availableNowCount: number;
  previewOnlyCount: number;
  sequenceLength: number;
  truthful: boolean;
};

export type LensStage6PrerequisiteCheckPresentation = {
  id: string;
  status: string;
  passed: boolean;
  evidence: string;
  reason: string;
};

export type LensStage6PrerequisiteBringupPresentation = {
  loaded: boolean;
  kind: string;
  status: string;
  currentGap: string;
  currentGapBasis: string;
  firstMissingRequirement: string;
  firstMissingGap: string;
  nextActionId: string;
  nextActionRoute: string;
  nextActionLiveEffect: string;
  approvedApprovalId: string;
  activeApprovalId: string;
  hostSupervisionActiveApprovalId: string;
  commandMode: string;
  command: string;
  requiresConfirmation: boolean;
  requiresApprovalId: boolean;
  requiresOperatorApprovalDecision: boolean;
  readOnlyContract: boolean;
  diagnosticOnly: boolean;
  planOnly: boolean;
  usesLensStatusReadback: boolean;
  wouldExecute: boolean;
  wouldMutate: boolean;
  approvalRequestWrite: boolean;
  authorityGrantReceiptWrite: boolean;
  executionReceiptWrite: boolean;
  mutationAuthorityGranted: boolean;
  canRequestNextResidentRuntimeAuthority: boolean;
  canGrantNextResidentRuntimeAuthority: boolean;
  canRequestNextHostSupervisionAuthority: boolean;
  canGrantNextHostSupervisionAuthority: boolean;
  canExecuteNextSupervisedResidentHostStart: boolean;
  canRequestNextTrayAuthority: boolean;
  canGrantNextTrayAuthority: boolean;
  canExecuteNextTrayPresence: boolean;
  canRequestNextOsBindingAuthority: boolean;
  canGrantNextOsBindingAuthority: boolean;
  canExecuteNextOsBinding: boolean;
  canRequestNextOverlayAuthority: boolean;
  canGrantNextOverlayAuthority: boolean;
  canExecuteNextOverlayWindow: boolean;
  canRequestNextSummonAuthority: boolean;
  canGrantNextSummonAuthority: boolean;
  canExecuteNextSummonAction: boolean;
  canRequestNextPersistentSupervisionEnablementAuthority: boolean;
  canGrantNextPersistentSupervisionEnablementAuthority: boolean;
  canRequestNextPersistentSupervisionExecutionAuthority: boolean;
  canGrantNextPersistentSupervisionExecutionAuthority: boolean;
  canApplyNextPersistentSupervisionEnablement: boolean;
  checks: LensStage6PrerequisiteCheckPresentation[];
  operatorSequence: LensStage6OperatorSequenceItem[];
  operatorSequenceCommandAvailability: LensStage6OperatorSequenceCommandAvailability;
  operatorSequenceCommandAvailabilityCheck: LensStage6PrerequisiteCheckPresentation;
};

export type LensStage6OperatorSequenceItem = {
  index: number;
  id: string;
  route: string;
  method: string;
  approvalAction: string;
  mode: string;
  liveEffect: string;
  command: string;
  commandMode: string;
  commandRequiresConfirmation: boolean;
  commandRequiresApprovalId: boolean;
  commandRequiresOperatorApprovalDecision: boolean;
  commandAvailableNow: boolean;
  commandPreviewOnly: boolean;
  commandAvailabilityReason: string;
  requires: string[];
  operatorSuppliedValuesRequired: boolean;
  wouldExecute: boolean;
  wouldMutate: boolean;
  current: boolean;
};

export type LensStage6NextHandoffPresentation = {
  loaded: boolean;
  kind: string;
  status: string;
  readyToClose: boolean;
  source: string;
  authority: string;
  readOnlyContract: boolean;
  diagnosticOnly: boolean;
  usesLensStatusReadback: boolean;
  executionAuthority: boolean;
  approvalDecisionAuthority: boolean;
  localProcessLaunchAuthority: boolean;
  processSupervisionAuthority: boolean;
  processRestartAuthority: boolean;
  serviceInstallAuthority: boolean;
  serviceControlAuthority: boolean;
  hotkeyRegistrationAuthority: boolean;
  trayRegistrationAuthority: boolean;
  overlayControlAuthority: boolean;
  summonAuthority: boolean;
  memoryWrite: boolean;
  receiptWriteAuthority: boolean;
  residentClaimAuthority: boolean;
  mutationAuthorityGranted: boolean;
  prerequisitesObserved: boolean;
  activationExecutionHandoffObserved: boolean;
  enablementAuthorityHandoffObserved: boolean;
  residentCandidateHandoffObserved: boolean;
  sourceHandoffLoaded: boolean;
  sourceHandoffId: string;
  sourceHandoffNextStep: string;
  sourceHandoffAcceptanceCriterion: string;
  sourceHandoffAuthorityRequired: string;
  sourceHandoffStatus: string;
  sourceHandoffReadOnlyContract: boolean;
  sourceHandoffDiagnosticOnly: boolean;
  sourceHandoffWouldExecute: boolean;
  sourceHandoffWouldMutate: boolean;
  sourceHandoffAuthorityGranted: boolean;
  sourceHandoffBlockers: string[];
  sourceHandoffPreviousGap: string;
  sourceHandoffConsumedAuditGap: string;
  sourceHandoffEnablementDenialObserved: boolean;
  sourceHandoffExecutionDenialObserved: boolean;
  sourceHandoffPersistentSupervisionEnablementAuthority: boolean;
  sourceHandoffServiceConfigWriteAuthority: boolean;
  sourceHandoffPersistentSupervisionExecutionAuthority: boolean;
  sourceHandoffReceiptWriteAuthority: boolean;
  sourceHandoffResidentClaimAuthority: boolean;
  sourceHandoffResidentClaimAllowed: boolean;
  sourceHandoffServiceConfigUpdated: boolean;
  sourceHandoffApplied: boolean;
  sourceHandoffExecuted: boolean;
  stageGap: string;
  currentGap: string;
  currentHandoff: string;
  currentProof: string;
  currentRoute: string;
  currentRequestRoute: string;
  currentRequestsRoute: string;
  currentGrantRoute: string;
  currentGrantsRoute: string;
  currentDenialsRoute: string;
  currentExecutionReadinessRoute: string;
  firstBlockedCriterion: string;
  firstBlockedCriterionGap: string;
  prerequisiteSource: string;
  prerequisiteHandoff: string;
  prerequisiteProof: string;
  prerequisiteRoute: string;
  prerequisiteAuthority: string;
  missingPrerequisites: string[];
  firstMissingPrerequisite: string;
  firstMissingSource: string;
  firstMissingHandoff: string;
  firstMissingProof: string;
  firstMissingRoute: string;
  firstMissingAuthority: string;
};

export type LensPersistentSupervisionReadback = {
  loaded: boolean;
  status: string;
  readOnlyContract: boolean;
  diagnosticOnly: boolean;
  wouldExecute: boolean;
  wouldMutate: boolean;
  prerequisitesObserved: boolean;
  prerequisitesReady: boolean;
  missingPrerequisites: string[];
  firstMissingPrerequisite: string;
  firstMissingHandoff: string;
  firstMissingProof: string;
  firstMissingRoute: string;
  firstMissingAuthority: string;
  enablementAuthorityHandoffObserved: boolean;
  enablementAuthorityGranted: boolean;
  executionAuthorityGranted: boolean;
  receiptWriteAuthority: boolean;
  residentClaimAllowed: boolean;
  serviceConfigUpdated: boolean;
  applied: boolean;
  executed: boolean;
  blockerCount: number;
  blockers: string[];
  currentGap: string;
  currentHandoff: string;
  currentProof: string;
  currentRoute: string;
  currentRequestRoute: string;
  currentGrantRoute: string;
  currentGrantsRoute: string;
  currentExecutionReadinessRoute: string;
  prerequisiteSource: string;
  prerequisiteHandoff: string;
  prerequisiteProof: string;
  prerequisiteRoute: string;
  prerequisiteAuthority: string;
};

export type LensStage6Readiness = {
  stage?: string;
  claim?: string;
  closure_readback: LensStage6ClosureReadback;
  next_handoff: LensStage6NextHandoff;
  prerequisite_bringup: LensStage6PrerequisiteBringup;
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

export type LensActionResponse = {
  ok: boolean;
  applied: boolean;
  executed: boolean;
  approval_requested: boolean;
  status?: string;
  action?: string;
  approval_id?: string;
  route?: string;
  authority_granted?: boolean;
  resident_claim_allowed?: boolean;
  blockers: string[];
  approval: Record<string, unknown>;
  governance: Record<string, unknown>;
  raw: Record<string, unknown>;
  error?: string;
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
  resident_runtime_authority_grant_readiness: LensResidentRuntimeAuthorityReadiness;
  resident_runtime_execution_receipts: LensResidentRuntimeExecutionReceipts;
  os_binding_authority_requests: LensOsBindingAuthorityRequests;
  os_binding_execution_readiness: LensOsBindingExecutionReadiness;
  os_binding_execution_receipts: LensOsBindingExecutionReceipts;
  tray_authority_requests: LensTrayAuthorityRequests;
  tray_execution_receipts: LensTrayExecutionReceipts;
  overlay_authority_requests: LensOverlayAuthorityRequests;
  overlay_execution_receipts: LensOverlayExecutionReceipts;
  summon_authority_requests: LensSummonAuthorityRequests;
  summon_execution_receipts: LensSummonExecutionReceipts;
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

function paramsFromLocationPart(value: string): URLSearchParams {
  const cleaned = safeString(value).trim().replace(/^[?#]/, "");
  if (!cleaned) return new URLSearchParams();
  return new URLSearchParams(cleaned.startsWith("?") ? cleaned.slice(1) : cleaned);
}

export function shouldOpenLensCommandPalette(search: string, hash = ""): boolean {
  const searchParams = paramsFromLocationPart(search);
  const hashText = safeString(hash).trim().replace(/^#/, "");
  const hashQuery = hashText.includes("?") ? hashText.slice(hashText.indexOf("?") + 1) : hashText;
  const hashParams = paramsFromLocationPart(hashQuery);

  const francisLens = (searchParams.get("francis_lens") || hashParams.get("francis_lens") || "")
    .trim()
    .toLowerCase();
  const lensPalette = (searchParams.get("lens_palette") || hashParams.get("lens_palette") || "")
    .trim()
    .toLowerCase();
  return francisLens === "command_palette" || lensPalette === "open" || lensPalette === "command_palette";
}

export function shouldOpenLensStatusPanel(search: string, hash = ""): boolean {
  const searchParams = paramsFromLocationPart(search);
  const hashText = safeString(hash).trim().replace(/^#/, "");
  const hashQuery = hashText.includes("?") ? hashText.slice(hashText.indexOf("?") + 1) : hashText;
  const hashParams = paramsFromLocationPart(hashQuery);

  const francisLens = (searchParams.get("francis_lens") || hashParams.get("francis_lens") || "")
    .trim()
    .toLowerCase();
  const lensPanel = (searchParams.get("lens_panel") || hashParams.get("lens_panel") || "").trim().toLowerCase();
  return francisLens === "status" || lensPanel === "status";
}

export function presentStage6PrerequisiteBringup(
  bringup?: LensStage6PrerequisiteBringup,
): LensStage6PrerequisiteBringupPresentation {
  const governance = safeRecord(bringup?.governance);
  const nextAction = safeRecord(bringup?.next_operator_action);
  const nextCommand = safeRecord(bringup?.next_operator_command);
  const commandAvailability = safeRecord(bringup?.operator_sequence_command_availability);
  const checks = safeRecordList(bringup?.checks)
    .map((item): LensStage6PrerequisiteCheckPresentation => ({
      id: safeString(item.id).trim(),
      status: safeString(item.status).trim(),
      passed: safeBoolean(item.passed, false),
      evidence: safeString(item.evidence).trim(),
      reason: safeString(item.reason).trim(),
    }))
    .filter((item) => item.id || item.status || item.reason || item.evidence);
  const availabilityCheck = checks.find((item) => item.id === "operator_sequence_command_availability");
  const kind = safeString(bringup?.kind).trim();
  const status = safeString(bringup?.status).trim() || "readback";
  const currentGap = safeString(bringup?.current_truthful_gap).trim();
  const currentGapBasis = safeString(bringup?.current_truthful_gap_basis).trim();
  const firstMissingRequirement = safeString(bringup?.current_first_missing_requirement).trim();
  const firstMissingGap = safeString(bringup?.current_first_missing_truthful_gap).trim();
  const nextActionId = safeString(nextAction.id).trim();
  const nextActionRoute = safeString(nextAction.route).trim();
  const nextActionLiveEffect = safeString(nextAction.live_effect).trim();
  const approvedApprovalId = safeString(nextAction.approved_approval_id).trim();
  const activeApprovalId = safeString(nextAction.active_approval_id).trim();
  const hostSupervisionActiveApprovalId = safeString(nextAction.host_supervision_active_approval_id).trim();
  const commandMode = safeString(nextCommand.mode).trim();
  const command = safeString(nextCommand.command).trim();
  const requiresConfirmation = safeBoolean(nextCommand.requires_confirmation, false);
  const requiresApprovalId = safeBoolean(nextCommand.requires_approval_id, false);
  const requiresOperatorApprovalDecision = safeBoolean(nextCommand.requires_operator_approval_decision, false);
  const readOnlyContract = safeBoolean(governance.read_only_contract, false);
  const diagnosticOnly = safeBoolean(governance.diagnostic_only, false);
  const planOnly = safeBoolean(governance.plan_only, false);
  const usesLensStatusReadback = safeBoolean(governance.uses_lens_status_readback, false);
  const wouldExecute = safeBoolean(nextAction.script_would_execute, false) || safeBoolean(governance.would_execute, false);
  const wouldMutate = safeBoolean(nextAction.script_would_mutate, false) || safeBoolean(governance.would_mutate, false);
  const approvalRequestWrite = safeBoolean(governance.approval_request_write, false);
  const authorityGrantReceiptWrite = safeBoolean(governance.authority_grant_receipt_write, false);
  const executionReceiptWrite = safeBoolean(governance.execution_receipt_write, false);
  const mutationAuthorityGranted = safeBoolean(governance.mutation_authority_granted, false);
  const readOnlyPlanGuard =
    readOnlyContract &&
    diagnosticOnly &&
    planOnly &&
    usesLensStatusReadback &&
    !wouldExecute &&
    !wouldMutate &&
    !approvalRequestWrite &&
    !authorityGrantReceiptWrite &&
    !executionReceiptWrite &&
    !mutationAuthorityGranted;
  const canRequestAction = (id: string, route: string, liveEffect: string) =>
    status === "blocked" &&
    nextActionId === id &&
    nextActionRoute === route &&
    commandMode === "RequestNext" &&
    nextActionLiveEffect === liveEffect &&
    readOnlyPlanGuard &&
    !requiresApprovalId &&
    !requiresOperatorApprovalDecision;
  const canGrantAction = (id: string, route: string, liveEffect: string) =>
    status === "blocked" &&
    nextActionId === id &&
    nextActionRoute === route &&
    commandMode === "GrantNext" &&
    nextActionLiveEffect === liveEffect &&
    Boolean(approvedApprovalId) &&
    readOnlyPlanGuard &&
    requiresApprovalId &&
    requiresOperatorApprovalDecision;
  const canExecuteAction = (id: string, route: string, liveEffect: string) =>
    status === "blocked" &&
    nextActionId === id &&
    nextActionRoute === route &&
    commandMode === "ExecuteNext" &&
    nextActionLiveEffect === liveEffect &&
    Boolean(activeApprovalId) &&
    readOnlyPlanGuard &&
    requiresApprovalId &&
    !requiresOperatorApprovalDecision;
  const canRequestNextResidentRuntimeAuthority =
    canRequestAction(
      "request_resident_runtime_execution_authority",
      "/lens/resident-runtime/authority-grant/request",
      "approval request receipt only",
    );
  const canGrantNextResidentRuntimeAuthority =
    canGrantAction(
      "grant_resident_runtime_execution_authority",
      "/lens/resident-runtime/authority-grant",
      "resident runtime authority grant receipt",
    );
  const canRequestNextHostSupervisionAuthority =
    canRequestAction(
      "request_host_supervision_authority",
      "/lens/host/supervision/authority/request",
      "host supervision authority request receipt only",
    );
  const canGrantNextHostSupervisionAuthority =
    canGrantAction(
      "grant_host_supervision_authority",
      "/lens/host/supervision/authority",
      "host supervision authority grant receipt",
    );
  const canExecuteNextSupervisedResidentHostStart =
    status === "blocked" &&
    nextActionId === "execute_supervised_resident_host_start" &&
    nextActionRoute === "/lens/resident-runtime/execute" &&
    commandMode === "ExecuteNext" &&
    nextActionLiveEffect === "bounded supervised resident host lease" &&
    Boolean(activeApprovalId) &&
    Boolean(hostSupervisionActiveApprovalId) &&
    readOnlyPlanGuard &&
    requiresApprovalId &&
    !requiresOperatorApprovalDecision;
  const canRequestNextTrayAuthority = canRequestAction(
    "request_tray_presence_authority",
    "/lens/tray/authority/request",
    "approval request receipt only",
  );
  const canGrantNextTrayAuthority = canGrantAction(
    "grant_tray_presence_authority",
    "/lens/tray/authority",
    "authority grant receipt",
  );
  const canExecuteNextTrayPresence = canExecuteAction(
    "execute_tray_presence",
    "/lens/tray/execute",
    "bounded tray presence lease",
  );
  const canRequestNextOsBindingAuthority = canRequestAction(
    "request_global_hotkey_binding_authority",
    "/lens/os-binding/authority/request",
    "approval request receipt only",
  );
  const canGrantNextOsBindingAuthority = canGrantAction(
    "grant_global_hotkey_binding_authority",
    "/lens/os-binding/authority",
    "authority grant receipt",
  );
  const canExecuteNextOsBinding = canExecuteAction(
    "execute_global_hotkey_binding",
    "/lens/os-binding/execute",
    "bounded global hotkey binding lease",
  );
  const canRequestNextOverlayAuthority = canRequestAction(
    "request_overlay_window_authority",
    "/lens/overlay/authority/request",
    "approval request receipt only",
  );
  const canGrantNextOverlayAuthority = canGrantAction(
    "grant_overlay_window_authority",
    "/lens/overlay/authority",
    "authority grant receipt",
  );
  const canExecuteNextOverlayWindow = canExecuteAction(
    "execute_overlay_window",
    "/lens/overlay/execute",
    "bounded overlay window lease",
  );
  const canRequestNextSummonAuthority = canRequestAction(
    "request_summon_binding_authority",
    "/lens/summon/authority/request",
    "approval request receipt only",
  );
  const canGrantNextSummonAuthority = canGrantAction(
    "grant_summon_binding_authority",
    "/lens/summon/authority",
    "authority grant receipt",
  );
  const canExecuteNextSummonAction = canExecuteAction(
    "execute_summon_binding",
    "/lens/summon/execute",
    "bounded summon handoff without summon-anywhere claim",
  );
  const canRequestNextPersistentSupervisionEnablementAuthority = canRequestAction(
    "request_persistent_supervision_enablement_authority",
    "/lens/host/persistent-supervision/enablement/authority/request",
    "persistent supervision enablement authority request receipt only",
  );
  const canGrantNextPersistentSupervisionEnablementAuthority = canGrantAction(
    "grant_persistent_supervision_enablement_authority",
    "/lens/host/persistent-supervision/enablement/authority",
    "persistent supervision enablement authority grant receipt",
  );
  const canRequestNextPersistentSupervisionExecutionAuthority = canRequestAction(
    "request_persistent_supervision_execution_authority",
    "/lens/host/persistent-supervision/enablement/execution/request",
    "persistent supervision execution authority request receipt only",
  );
  const canGrantNextPersistentSupervisionExecutionAuthority = canGrantAction(
    "grant_persistent_supervision_execution_authority",
    "/lens/host/persistent-supervision/enablement/execution/authority",
    "persistent supervision execution authority grant receipt",
  );
  const canApplyNextPersistentSupervisionEnablement = canExecuteAction(
    "apply_persistent_supervision_enablement",
    "/lens/host/persistent-supervision/enablement/execution/apply",
    "persistent supervision service config update and execution receipt",
  );
  const operatorSequence = (bringup?.operator_sequence ?? [])
    .map((action, index): LensStage6OperatorSequenceItem => {
      const id = safeString(action.id).trim();
      const route = safeString(action.route).trim();
      const operatorCommand = safeRecord(action.operator_command);
      return {
        index: index + 1,
        id,
        route,
        method: safeString(action.method).trim(),
        approvalAction: safeString(action.approval_action).trim(),
        mode: safeString(action.mode).trim(),
        liveEffect: safeString(action.live_effect).trim(),
        command: safeString(operatorCommand.command).trim(),
        commandMode: safeString(operatorCommand.mode).trim(),
        commandRequiresConfirmation: safeBoolean(operatorCommand.requires_confirmation, false),
        commandRequiresApprovalId: safeBoolean(operatorCommand.requires_approval_id, false),
        commandRequiresOperatorApprovalDecision: safeBoolean(
          operatorCommand.requires_operator_approval_decision,
          false,
        ),
        commandAvailableNow: safeBoolean(operatorCommand.available_now, false),
        commandPreviewOnly: safeBoolean(operatorCommand.preview_only, false),
        commandAvailabilityReason: safeString(operatorCommand.availability_reason).trim(),
        requires: safeStringList(action.requires),
        operatorSuppliedValuesRequired: safeBoolean(action.operator_supplied_values_required, false),
        wouldExecute: safeBoolean(action.script_would_execute, false),
        wouldMutate: safeBoolean(action.script_would_mutate, false),
        current: Boolean(id && route && id === nextActionId && route === nextActionRoute),
      };
    })
    .filter((item) => item.id || item.route || item.approvalAction || item.liveEffect);
  const operatorSequenceCommandAvailability: LensStage6OperatorSequenceCommandAvailability = {
    availableNowCount: safeNumber(commandAvailability.available_now_count, 0),
    previewOnlyCount: safeNumber(commandAvailability.preview_only_count, 0),
    sequenceLength: safeNumber(commandAvailability.sequence_length, operatorSequence.length),
    truthful: safeBoolean(commandAvailability.truthful, false),
  };
  const operatorSequenceCommandAvailabilityCheck: LensStage6PrerequisiteCheckPresentation = {
    id: safeString(availabilityCheck?.id).trim(),
    status: safeString(availabilityCheck?.status).trim(),
    passed: safeBoolean(availabilityCheck?.passed, false),
    evidence: safeString(availabilityCheck?.evidence).trim(),
    reason: safeString(availabilityCheck?.reason).trim(),
  };

  return {
    loaded: Boolean(kind || currentGap || nextActionId || commandMode),
    kind,
    status,
    currentGap,
    currentGapBasis,
    firstMissingRequirement,
    firstMissingGap,
    nextActionId,
    nextActionRoute,
    nextActionLiveEffect,
    approvedApprovalId,
    activeApprovalId,
    hostSupervisionActiveApprovalId,
    commandMode,
    command,
    requiresConfirmation,
    requiresApprovalId,
    requiresOperatorApprovalDecision,
    readOnlyContract,
    diagnosticOnly,
    planOnly,
    usesLensStatusReadback,
    wouldExecute,
    wouldMutate,
    approvalRequestWrite,
    authorityGrantReceiptWrite,
    executionReceiptWrite,
    mutationAuthorityGranted,
    canRequestNextResidentRuntimeAuthority,
    canGrantNextResidentRuntimeAuthority,
    canRequestNextHostSupervisionAuthority,
    canGrantNextHostSupervisionAuthority,
    canExecuteNextSupervisedResidentHostStart,
    canRequestNextTrayAuthority,
    canGrantNextTrayAuthority,
    canExecuteNextTrayPresence,
    canRequestNextOsBindingAuthority,
    canGrantNextOsBindingAuthority,
    canExecuteNextOsBinding,
    canRequestNextOverlayAuthority,
    canGrantNextOverlayAuthority,
    canExecuteNextOverlayWindow,
    canRequestNextSummonAuthority,
    canGrantNextSummonAuthority,
    canExecuteNextSummonAction,
    canRequestNextPersistentSupervisionEnablementAuthority,
    canGrantNextPersistentSupervisionEnablementAuthority,
    canRequestNextPersistentSupervisionExecutionAuthority,
    canGrantNextPersistentSupervisionExecutionAuthority,
    canApplyNextPersistentSupervisionEnablement,
    checks,
    operatorSequence,
    operatorSequenceCommandAvailability,
    operatorSequenceCommandAvailabilityCheck,
  };
}

export function stage6PrerequisiteConfirmationMessage(
  presentation: Pick<LensStage6PrerequisiteBringupPresentation, "nextActionId" | "commandMode" | "command">,
): string {
  const actionId = safeString(presentation.nextActionId).trim() || "next Stage 6 action";
  const commandMode = safeString(presentation.commandMode).trim();
  const command = safeString(presentation.command).trim();
  const prefix = commandMode ? `Confirm ${commandMode}` : "Confirm";
  return command ? `${prefix} for ${actionId}?\n\n${command}` : `${prefix} for ${actionId}?`;
}

export function presentStage6NextHandoff(handoff?: LensStage6NextHandoff): LensStage6NextHandoffPresentation {
  const governance = safeRecord(handoff?.governance);
  const kind = safeString(handoff?.kind).trim();
  const status = safeString(handoff?.status).trim() || "readback";
  const readyToClose = safeBoolean(handoff?.ready_to_close, false);
  const readOnlyContract = safeBoolean(governance.read_only_contract, false);
  const diagnosticOnly = safeBoolean(governance.diagnostic_only, false);
  const usesLensStatusReadback = safeBoolean(governance.uses_lens_status_readback, false);
  const executionAuthority = safeBoolean(governance.execution_authority, false);
  const approvalDecisionAuthority = safeBoolean(governance.approval_decision_authority, false);
  const localProcessLaunchAuthority = safeBoolean(governance.local_process_launch_authority, false);
  const processSupervisionAuthority = safeBoolean(governance.process_supervision_authority, false);
  const processRestartAuthority = safeBoolean(governance.process_restart_authority, false);
  const serviceInstallAuthority = safeBoolean(governance.service_install_authority, false);
  const serviceControlAuthority = safeBoolean(governance.service_control_authority, false);
  const hotkeyRegistrationAuthority = safeBoolean(governance.hotkey_registration_authority, false);
  const trayRegistrationAuthority = safeBoolean(governance.tray_registration_authority, false);
  const overlayControlAuthority = safeBoolean(governance.overlay_control_authority, false);
  const summonAuthority = safeBoolean(governance.summon_authority, false);
  const memoryWrite = safeBoolean(governance.memory_write, false);
  const receiptWriteAuthority = safeBoolean(governance.receipt_write_authority, false);
  const residentClaimAuthority = safeBoolean(governance.resident_claim_authority, false);
  const mutationAuthorityGranted = safeBoolean(governance.mutation_authority_granted, false);
  const prerequisitesObserved = safeBoolean(handoff?.persistent_supervision_required_prerequisites_observed, false);
  const activationExecutionHandoffObserved = safeBoolean(handoff?.activation_execution_handoff_observed, false);
  const enablementAuthorityHandoffObserved = safeBoolean(
    handoff?.persistent_supervision_enablement_authority_handoff_observed,
    false,
  );
  const residentCandidateHandoffObserved = safeBoolean(handoff?.resident_runtime_candidate_handoff_observed, false);
  const source = safeString(handoff?.recommended_handoff_source).trim();
  const sourceHandoff =
    source === "activation_execution_handoff"
      ? safeRecord(handoff?.activation_execution_handoff)
      : source === "persistent_supervision_enablement_authority_denial_handoff"
        ? safeRecord(handoff?.persistent_supervision_enablement_authority_handoff)
        : source === "persistent_supervision_first_missing_requirement_handoff"
          ? safeRecord(handoff?.persistent_supervision_first_missing_requirement_handoff)
          : source === "persistent_supervision_required_prerequisites_handoff"
            ? safeRecord(handoff?.persistent_supervision_required_prerequisites_handoff)
            : source === "resident_runtime_candidate_handoff"
              ? safeRecord(handoff?.resident_runtime_candidate_handoff)
              : {};
  const sourceHandoffLoaded = Object.keys(sourceHandoff).length > 0;
  const sourceHandoffId = safeString(sourceHandoff.id).trim();
  const sourceHandoffNextStep =
    safeString(sourceHandoff.next_step).trim() || safeString(sourceHandoff.recommended_next_slice).trim();
  const sourceHandoffAcceptanceCriterion = safeString(sourceHandoff.acceptance_criterion).trim();
  const sourceHandoffAuthorityRequired = safeString(sourceHandoff.authority_required).trim();
  const sourceHandoffStatus = safeString(sourceHandoff.status).trim();
  const sourceHandoffReadOnlyContract = safeBoolean(sourceHandoff.read_only_contract, false);
  const sourceHandoffDiagnosticOnly = safeBoolean(sourceHandoff.diagnostic_only, false);
  const sourceHandoffWouldExecute = safeBoolean(sourceHandoff.would_execute, false);
  const sourceHandoffWouldMutate = safeBoolean(sourceHandoff.would_mutate, false);
  const sourceHandoffAuthorityGranted = safeBoolean(sourceHandoff.authority_granted, false);
  const sourceHandoffBlockers = safeStringList(sourceHandoff.blockers);
  const sourceHandoffPreviousGap = safeString(sourceHandoff.previous_next_smallest_truthful_gap).trim();
  const sourceHandoffConsumedAuditGap = safeString(sourceHandoff.consumed_audit_next_smallest_truthful_gap).trim();
  const sourceHandoffEnablementDenialObserved = safeBoolean(sourceHandoff.enablement_denial_observed, false);
  const sourceHandoffExecutionDenialObserved = safeBoolean(sourceHandoff.execution_denial_observed, false);
  const sourceHandoffPersistentSupervisionEnablementAuthority = safeBoolean(
    sourceHandoff.persistent_supervision_enablement_authority,
    false,
  );
  const sourceHandoffServiceConfigWriteAuthority = safeBoolean(sourceHandoff.service_config_write_authority, false);
  const sourceHandoffPersistentSupervisionExecutionAuthority = safeBoolean(
    sourceHandoff.persistent_supervision_execution_authority,
    false,
  );
  const sourceHandoffReceiptWriteAuthority = safeBoolean(sourceHandoff.receipt_write_authority, false);
  const sourceHandoffResidentClaimAuthority = safeBoolean(sourceHandoff.resident_claim_authority, false);
  const sourceHandoffResidentClaimAllowed = safeBoolean(sourceHandoff.resident_claim_allowed, false);
  const sourceHandoffServiceConfigUpdated = safeBoolean(sourceHandoff.service_config_updated, false);
  const sourceHandoffApplied = safeBoolean(sourceHandoff.applied, false);
  const sourceHandoffExecuted = safeBoolean(sourceHandoff.executed, false);
  const stageGap = safeString(handoff?.stage_next_smallest_truthful_gap).trim();
  const currentGap = safeString(handoff?.next_smallest_truthful_gap).trim();
  const currentHandoff = safeString(handoff?.recommended_next_slice).trim();
  const currentProof = safeString(handoff?.recommended_proof_script).trim();
  const currentRoute =
    safeString(handoff?.recommended_readiness_route).trim() || safeString(handoff?.recommended_route).trim();
  const currentRequestRoute = safeString(handoff?.recommended_request_route).trim();
  const currentRequestsRoute = safeString(handoff?.recommended_requests_route).trim();
  const currentGrantRoute = safeString(handoff?.recommended_grant_route).trim();
  const currentGrantsRoute = safeString(handoff?.recommended_grants_route).trim();
  const currentDenialsRoute = safeString(handoff?.recommended_denials_route).trim();
  const currentExecutionReadinessRoute = safeString(handoff?.recommended_execution_readiness_route).trim();
  const authority = safeString(handoff?.authority_required).trim();
  const firstBlockedCriterion = safeString(handoff?.first_blocked_criterion).trim();
  const firstBlockedCriterionGap = safeString(handoff?.first_blocked_criterion_next_smallest_truthful_gap).trim();
  const prerequisiteSource = safeString(handoff?.recommended_prerequisites_handoff_source).trim();
  const prerequisiteHandoff = safeString(handoff?.recommended_prerequisites_next_slice).trim();
  const prerequisiteProof = safeString(handoff?.recommended_prerequisites_proof_script).trim();
  const prerequisiteRoute =
    safeString(handoff?.recommended_prerequisites_readiness_route).trim() ||
    safeString(handoff?.recommended_prerequisites_route).trim();
  const prerequisiteAuthority = safeString(handoff?.recommended_prerequisites_authority_required).trim();
  const missingPrerequisites = safeStringList(handoff?.persistent_supervision_missing_required_before_enable);
  const firstMissingPrerequisite = safeString(handoff?.persistent_supervision_first_missing_required_before_enable).trim();
  const firstMissingSource = safeString(handoff?.recommended_first_missing_handoff_source).trim();
  const firstMissingHandoff = safeString(handoff?.recommended_first_missing_next_slice).trim();
  const firstMissingProof = safeString(handoff?.recommended_first_missing_proof_script).trim();
  const firstMissingRoute =
    safeString(handoff?.recommended_first_missing_readiness_route).trim() ||
    safeString(handoff?.recommended_first_missing_route).trim();
  const firstMissingAuthority = safeString(handoff?.recommended_first_missing_authority_required).trim();

  return {
    loaded: Boolean(stageGap || currentGap || source || firstBlockedCriterion || missingPrerequisites.length),
    kind,
    status,
    readyToClose,
    source,
    authority,
    readOnlyContract,
    diagnosticOnly,
    usesLensStatusReadback,
    executionAuthority,
    approvalDecisionAuthority,
    localProcessLaunchAuthority,
    processSupervisionAuthority,
    processRestartAuthority,
    serviceInstallAuthority,
    serviceControlAuthority,
    hotkeyRegistrationAuthority,
    trayRegistrationAuthority,
    overlayControlAuthority,
    summonAuthority,
    memoryWrite,
    receiptWriteAuthority,
    residentClaimAuthority,
    mutationAuthorityGranted,
    prerequisitesObserved,
    activationExecutionHandoffObserved,
    enablementAuthorityHandoffObserved,
    residentCandidateHandoffObserved,
    sourceHandoffLoaded,
    sourceHandoffId,
    sourceHandoffNextStep,
    sourceHandoffAcceptanceCriterion,
    sourceHandoffAuthorityRequired,
    sourceHandoffStatus,
    sourceHandoffReadOnlyContract,
    sourceHandoffDiagnosticOnly,
    sourceHandoffWouldExecute,
    sourceHandoffWouldMutate,
    sourceHandoffAuthorityGranted,
    sourceHandoffBlockers,
    sourceHandoffPreviousGap,
    sourceHandoffConsumedAuditGap,
    sourceHandoffEnablementDenialObserved,
    sourceHandoffExecutionDenialObserved,
    sourceHandoffPersistentSupervisionEnablementAuthority,
    sourceHandoffServiceConfigWriteAuthority,
    sourceHandoffPersistentSupervisionExecutionAuthority,
    sourceHandoffReceiptWriteAuthority,
    sourceHandoffResidentClaimAuthority,
    sourceHandoffResidentClaimAllowed,
    sourceHandoffServiceConfigUpdated,
    sourceHandoffApplied,
    sourceHandoffExecuted,
    stageGap,
    currentGap,
    currentHandoff,
    currentProof,
    currentRoute,
    currentRequestRoute,
    currentRequestsRoute,
    currentGrantRoute,
    currentGrantsRoute,
    currentDenialsRoute,
    currentExecutionReadinessRoute,
    firstBlockedCriterion,
    firstBlockedCriterionGap,
    prerequisiteSource,
    prerequisiteHandoff,
    prerequisiteProof,
    prerequisiteRoute,
    prerequisiteAuthority,
    missingPrerequisites,
    firstMissingPrerequisite,
    firstMissingSource,
    firstMissingHandoff,
    firstMissingProof,
    firstMissingRoute,
    firstMissingAuthority,
  };
}

export function presentPersistentSupervisionReadback(
  handoff?: LensStage6NextHandoff,
): LensPersistentSupervisionReadback {
  const presentation = presentStage6NextHandoff(handoff);
  const prerequisitesReady = presentation.prerequisitesObserved && presentation.missingPrerequisites.length === 0;
  const blockers = [
    ...presentation.missingPrerequisites,
    ...presentation.sourceHandoffBlockers,
    presentation.currentGap,
  ].filter((value, index, items) => Boolean(value) && items.indexOf(value) === index);

  return {
    loaded: presentation.loaded,
    status: prerequisitesReady ? "prerequisites_ready" : presentation.status,
    readOnlyContract: presentation.readOnlyContract,
    diagnosticOnly: presentation.diagnosticOnly,
    wouldExecute: presentation.sourceHandoffWouldExecute,
    wouldMutate: presentation.sourceHandoffWouldMutate,
    prerequisitesObserved: presentation.prerequisitesObserved,
    prerequisitesReady,
    missingPrerequisites: presentation.missingPrerequisites,
    firstMissingPrerequisite: presentation.firstMissingPrerequisite,
    firstMissingHandoff: presentation.firstMissingHandoff,
    firstMissingProof: presentation.firstMissingProof,
    firstMissingRoute: presentation.firstMissingRoute,
    firstMissingAuthority: presentation.firstMissingAuthority,
    enablementAuthorityHandoffObserved: presentation.enablementAuthorityHandoffObserved,
    enablementAuthorityGranted: presentation.sourceHandoffPersistentSupervisionEnablementAuthority,
    executionAuthorityGranted: presentation.sourceHandoffPersistentSupervisionExecutionAuthority,
    receiptWriteAuthority: presentation.sourceHandoffReceiptWriteAuthority,
    residentClaimAllowed: presentation.sourceHandoffResidentClaimAllowed,
    serviceConfigUpdated: presentation.sourceHandoffServiceConfigUpdated,
    applied: presentation.sourceHandoffApplied,
    executed: presentation.sourceHandoffExecuted,
    blockerCount: blockers.length,
    blockers,
    currentGap: presentation.currentGap,
    currentHandoff: presentation.currentHandoff,
    currentProof: presentation.currentProof,
    currentRoute: presentation.currentRoute,
    currentRequestRoute: presentation.currentRequestRoute,
    currentGrantRoute: presentation.currentGrantRoute,
    currentGrantsRoute: presentation.currentGrantsRoute,
    currentExecutionReadinessRoute: presentation.currentExecutionReadinessRoute,
    prerequisiteSource: presentation.prerequisiteSource,
    prerequisiteHandoff: presentation.prerequisiteHandoff,
    prerequisiteProof: presentation.prerequisiteProof,
    prerequisiteRoute: presentation.prerequisiteRoute,
    prerequisiteAuthority: presentation.prerequisiteAuthority,
  };
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

function safeRecordList(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord);
}

function parseRecordListMap(value: unknown): Record<string, Array<Record<string, unknown>>> {
  if (!isRecord(value)) return {};
  const out: Record<string, Array<Record<string, unknown>>> = {};
  for (const [key, items] of Object.entries(value)) {
    const safeKey = key.trim();
    if (!safeKey) continue;
    out[safeKey] = safeRecordList(items);
  }
  return out;
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
    url_entrypoint_ready: safeBoolean(raw.url_entrypoint_ready, false),
    url_entrypoint: safeRecord(raw.url_entrypoint),
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

function parseResidentRuntimeExecutionReceipts(value: unknown): LensResidentRuntimeExecutionReceipts {
  const raw = safeRecord(value);
  const items = Array.isArray(raw.items) ? raw.items.filter(isRecord).map(safeRecord) : [];
  const latest = isRecord(raw.latest) ? safeRecord(raw.latest) : items[0];
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    host_supervision_execute_route: safeString(raw.host_supervision_execute_route).trim() || undefined,
    host_supervision_executions_route: safeString(raw.host_supervision_executions_route).trim() || undefined,
    limit: safeNumber(raw.limit, 0),
    total: safeNumber(raw.total, items.length),
    latest,
    latest_receipt_id: safeString(raw.latest_receipt_id).trim() || undefined,
    latest_status: safeString(raw.latest_status).trim() || undefined,
    latest_supervision_mode: safeString(raw.latest_supervision_mode).trim() || undefined,
    latest_resident_host_process:
      typeof raw.latest_resident_host_process === "boolean"
        ? safeBoolean(raw.latest_resident_host_process, false)
        : undefined,
    latest_resident_supervised_runtime:
      typeof raw.latest_resident_supervised_runtime === "boolean"
        ? safeBoolean(raw.latest_resident_supervised_runtime, false)
        : undefined,
    latest_stop_command: safeString(raw.latest_stop_command).trim() || undefined,
    latest_next_smallest_truthful_gap: safeString(raw.latest_next_smallest_truthful_gap).trim() || undefined,
    resident_supervised_runtime_receipt_observed: safeBoolean(raw.resident_supervised_runtime_receipt_observed, false),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    items,
    governance: safeRecord(raw.governance),
  };
}

function parseResidentRuntimeAuthorityReadiness(value: unknown): LensResidentRuntimeAuthorityReadiness {
  const raw = safeRecord(value);
  const requirements = Array.isArray(raw.requirements) ? raw.requirements.filter(isRecord) : [];
  const blockedRequirementHandoffs = Array.isArray(raw.blocked_requirement_handoffs)
    ? raw.blocked_requirement_handoffs
        .map(parseRuntimeLoopRequirementHandoff)
        .filter((item): item is LensRuntimeLoopRequirementHandoff => item !== null)
    : [];
  const firstBlockedRequirementHandoff =
    parseRuntimeLoopRequirementHandoff(raw.first_blocked_requirement_handoff) ?? blockedRequirementHandoffs[0];
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    audit_status: safeString(raw.audit_status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    preflight_route: safeString(raw.preflight_route).trim() || undefined,
    policy_route: safeString(raw.policy_route).trim() || undefined,
    authority_grant_route: safeString(raw.authority_grant_route).trim() || undefined,
    authority_grants_route: safeString(raw.authority_grants_route).trim() || undefined,
    denials_route: safeString(raw.denials_route).trim() || undefined,
    plan_route: safeString(raw.plan_route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    approval_id: safeString(raw.approval_id).trim() || undefined,
    actor: safeString(raw.actor).trim() || undefined,
    ready: safeBoolean(raw.ready, false),
    grant_ready: safeBoolean(raw.grant_ready, false),
    authority_grant_ready: safeBoolean(raw.authority_grant_ready, false),
    runtime_ready: safeBoolean(raw.runtime_ready, false),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    boundary_observed: safeBoolean(raw.boundary_observed, false),
    authority_granted: safeBoolean(raw.authority_granted, false),
    resident_runtime_execution_authority: safeBoolean(raw.resident_runtime_execution_authority, false),
    denial_receipt_readback_ready: safeBoolean(raw.denial_receipt_readback_ready, false),
    grant_receipt_readback_ready: safeBoolean(raw.grant_receipt_readback_ready, false),
    receipt_count: safeNumber(raw.receipt_count, 0),
    latest_receipt_id: safeString(raw.latest_receipt_id).trim() || undefined,
    denial_receipt_count: safeNumber(raw.denial_receipt_count, 0),
    latest_denial_receipt_id: safeString(raw.latest_denial_receipt_id).trim() || undefined,
    requirements_total: safeNumber(raw.requirements_total, requirements.length),
    requirements_ready_total: safeNumber(raw.requirements_ready_total, 0),
    requirements_blocked_total: safeNumber(raw.requirements_blocked_total, 0),
    requirements,
    blocked_requirements: safeStringList(raw.blocked_requirements),
    operator_surface_readback_ready:
      typeof raw.operator_surface_readback_ready === "boolean"
        ? safeBoolean(raw.operator_surface_readback_ready, false)
        : undefined,
    first_blocked_requirement: safeString(raw.first_blocked_requirement).trim() || undefined,
    first_blocked_requirement_handoff: firstBlockedRequirementHandoff,
    blocked_requirement_handoffs: blockedRequirementHandoffs,
    blockers: safeStringList(raw.blockers),
    source_readbacks: parseStringMap(raw.source_readbacks),
    governance: safeRecord(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap).trim() || undefined,
  };
}

function parseHostSupervisionAuthorityRequests(value: unknown): LensHostSupervisionAuthorityRequests {
  const raw = safeRecord(value);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    request_route: safeString(raw.request_route).trim() || undefined,
    grant_route: safeString(raw.grant_route).trim() || undefined,
    grants_route: safeString(raw.grants_route).trim() || undefined,
    readiness_route: safeString(raw.readiness_route).trim() || undefined,
    active_grant_receipt_id: safeString(raw.active_grant_receipt_id).trim() || undefined,
    decision_route: safeString(raw.decision_route).trim() || undefined,
    approval_action: safeString(raw.approval_action).trim() || undefined,
    pending_count: safeNumber(raw.pending_count, 0),
    approved_count: safeNumber(raw.approved_count, 0),
    rejected_count: safeNumber(raw.rejected_count, 0),
    emergency_count: safeNumber(raw.emergency_count, 0),
    total_count: safeNumber(raw.total_count, 0),
    latest: Object.keys(latest).length ? latest : undefined,
    items: safeRecordList(raw.items),
    by_status: parseRecordListMap(raw.by_status),
    authority_granted: safeBoolean(raw.authority_granted, false),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    governance: safeRecord(raw.governance),
  };
}

function parseResidentRuntimeAuthorityRequests(value: unknown): LensResidentRuntimeAuthorityRequests {
  const raw = safeRecord(value);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    request_route: safeString(raw.request_route).trim() || undefined,
    grant_route: safeString(raw.grant_route).trim() || undefined,
    grants_route: safeString(raw.grants_route).trim() || undefined,
    readiness_route: safeString(raw.readiness_route).trim() || undefined,
    denials_route: safeString(raw.denials_route).trim() || undefined,
    active_grant_receipt_id: safeString(raw.active_grant_receipt_id).trim() || undefined,
    policy_route: safeString(raw.policy_route).trim() || undefined,
    plan_route: safeString(raw.plan_route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    decision_route: safeString(raw.decision_route).trim() || undefined,
    approval_action: safeString(raw.approval_action).trim() || undefined,
    pending_count: safeNumber(raw.pending_count, 0),
    approved_count: safeNumber(raw.approved_count, 0),
    rejected_count: safeNumber(raw.rejected_count, 0),
    emergency_count: safeNumber(raw.emergency_count, 0),
    total_count: safeNumber(raw.total_count, 0),
    latest: Object.keys(latest).length ? latest : undefined,
    items: safeRecordList(raw.items),
    by_status: parseRecordListMap(raw.by_status),
    authority_granted: safeBoolean(raw.authority_granted, false),
    resident_runtime_execution_authority: safeBoolean(raw.resident_runtime_execution_authority, false),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    execution_authority: safeBoolean(raw.execution_authority, false),
    local_process_launch_authority: safeBoolean(raw.local_process_launch_authority, false),
    process_supervision_authority: safeBoolean(raw.process_supervision_authority, false),
    service_control_authority: safeBoolean(raw.service_control_authority, false),
    receipt_write_authority: safeBoolean(raw.receipt_write_authority, false),
    memory_write: safeBoolean(raw.memory_write, false),
    governance: safeRecord(raw.governance),
  };
}

function parseOsBindingAuthorityRequests(value: unknown): LensOsBindingAuthorityRequests {
  const raw = safeRecord(value);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    request_route: safeString(raw.request_route).trim() || undefined,
    authority_route: safeString(raw.authority_route).trim() || undefined,
    grants_route: safeString(raw.grants_route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    denials_route: safeString(raw.denials_route).trim() || undefined,
    execution_readiness_route: safeString(raw.execution_readiness_route).trim() || undefined,
    readiness_route: safeString(raw.readiness_route).trim() || undefined,
    plan_route: safeString(raw.plan_route).trim() || undefined,
    active_grant_receipt_id: safeString(raw.active_grant_receipt_id).trim() || undefined,
    approval_action: safeString(raw.approval_action).trim() || undefined,
    pending_count: safeNumber(raw.pending_count, 0),
    approved_count: safeNumber(raw.approved_count, 0),
    rejected_count: safeNumber(raw.rejected_count, 0),
    emergency_count: safeNumber(raw.emergency_count, 0),
    total_count: safeNumber(raw.total_count, 0),
    latest: Object.keys(latest).length ? latest : undefined,
    items: safeRecordList(raw.items),
    by_status: parseRecordListMap(raw.by_status),
    authority_granted: safeBoolean(raw.authority_granted, false),
    os_level_command_palette_binding_authority: safeBoolean(
      raw.os_level_command_palette_binding_authority,
      false,
    ),
    os_level_command_palette: safeBoolean(raw.os_level_command_palette, false),
    registers_hotkey: safeBoolean(raw.registers_hotkey, false),
    governance: safeRecord(raw.governance),
  };
}

function parseOsBindingExecutionReadiness(value: unknown): LensOsBindingExecutionReadiness {
  const raw = safeRecord(value);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    ready: safeBoolean(raw.ready, false),
    execution_ready: safeBoolean(raw.execution_ready, false),
    authority_granted: safeBoolean(raw.authority_granted, false),
    os_level_command_palette: safeBoolean(raw.os_level_command_palette, false),
    blocked_requirements: safeStringList(raw.blocked_requirements),
    blockers: safeStringList(raw.blockers),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap).trim() || undefined,
    active_grant_receipt_id: safeString(raw.active_grant_receipt_id).trim() || undefined,
    governance: safeRecord(raw.governance),
  };
}

function parseOsBindingExecutionReceipts(value: unknown): LensOsBindingExecutionReceipts {
  const raw = safeRecord(value);
  const items = safeRecordList(raw.items);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    authority_route: safeString(raw.authority_route).trim() || undefined,
    authority_grants_route: safeString(raw.authority_grants_route).trim() || undefined,
    limit: safeNumber(raw.limit, 0),
    total: safeNumber(raw.total, items.length),
    latest: Object.keys(latest).length ? latest : undefined,
    latest_status: safeString(raw.latest_status).trim() || undefined,
    latest_global_hotkey_binding:
      typeof raw.latest_global_hotkey_binding === "boolean"
        ? safeBoolean(raw.latest_global_hotkey_binding, false)
        : undefined,
    latest_next_smallest_truthful_gap: safeString(raw.latest_next_smallest_truthful_gap).trim() || undefined,
    items,
    governance: safeRecord(raw.governance),
  };
}

function parseTrayAuthorityRequests(value: unknown): LensTrayAuthorityRequests {
  const raw = safeRecord(value);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    request_route: safeString(raw.request_route).trim() || undefined,
    authority_route: safeString(raw.authority_route).trim() || undefined,
    grants_route: safeString(raw.grants_route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    executions_route: safeString(raw.executions_route).trim() || undefined,
    action: safeString(raw.action).trim() || undefined,
    approval_counts: parseNumberMap(raw.approval_counts),
    latest: Object.keys(latest).length ? latest : undefined,
    pending: safeRecordList(raw.pending),
    approved: safeRecordList(raw.approved),
    rejected: safeRecordList(raw.rejected),
    emergency: safeRecordList(raw.emergency),
    active_authority_grant: safeRecord(raw.active_authority_grant),
    authority_granted: safeBoolean(raw.authority_granted, false),
    tray_presence_authority: safeBoolean(raw.tray_presence_authority, false),
    tray_presence: safeBoolean(raw.tray_presence, false),
    registers_tray: safeBoolean(raw.registers_tray, false),
    starts_tray: safeBoolean(raw.starts_tray, false),
    stops_tray: safeBoolean(raw.stops_tray, false),
    governance: safeRecord(raw.governance),
  };
}

function parseTrayExecutionReceipts(value: unknown): LensTrayExecutionReceipts {
  const raw = safeRecord(value);
  const items = safeRecordList(raw.items);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    authority_route: safeString(raw.authority_route).trim() || undefined,
    authority_grants_route: safeString(raw.authority_grants_route).trim() || undefined,
    limit: safeNumber(raw.limit, 0),
    total: safeNumber(raw.total, items.length),
    latest: Object.keys(latest).length ? latest : undefined,
    latest_status: safeString(raw.latest_status).trim() || undefined,
    latest_tray_presence:
      typeof raw.latest_tray_presence === "boolean" ? safeBoolean(raw.latest_tray_presence, false) : undefined,
    latest_next_smallest_truthful_gap: safeString(raw.latest_next_smallest_truthful_gap).trim() || undefined,
    items,
    governance: safeRecord(raw.governance),
  };
}

function parseOverlayAuthorityRequests(value: unknown): LensOverlayAuthorityRequests {
  const raw = safeRecord(value);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    request_route: safeString(raw.request_route).trim() || undefined,
    authority_route: safeString(raw.authority_route).trim() || undefined,
    grants_route: safeString(raw.grants_route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    executions_route: safeString(raw.executions_route).trim() || undefined,
    action: safeString(raw.action).trim() || undefined,
    approval_counts: parseNumberMap(raw.approval_counts),
    latest: Object.keys(latest).length ? latest : undefined,
    pending: safeRecordList(raw.pending),
    approved: safeRecordList(raw.approved),
    rejected: safeRecordList(raw.rejected),
    emergency: safeRecordList(raw.emergency),
    active_authority_grant: safeRecord(raw.active_authority_grant),
    authority_granted: safeBoolean(raw.authority_granted, false),
    overlay_window_authority: safeBoolean(raw.overlay_window_authority, false),
    overlay_window: safeBoolean(raw.overlay_window, false),
    governance: safeRecord(raw.governance),
  };
}

function parseOverlayExecutionReceipts(value: unknown): LensOverlayExecutionReceipts {
  const raw = safeRecord(value);
  const items = safeRecordList(raw.items);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    authority_route: safeString(raw.authority_route).trim() || undefined,
    authority_grants_route: safeString(raw.authority_grants_route).trim() || undefined,
    limit: safeNumber(raw.limit, 0),
    total: safeNumber(raw.total, items.length),
    latest: Object.keys(latest).length ? latest : undefined,
    latest_status: safeString(raw.latest_status).trim() || undefined,
    latest_overlay_window:
      typeof raw.latest_overlay_window === "boolean" ? safeBoolean(raw.latest_overlay_window, false) : undefined,
    latest_next_smallest_truthful_gap: safeString(raw.latest_next_smallest_truthful_gap).trim() || undefined,
    items,
    governance: safeRecord(raw.governance),
  };
}

function parseSummonAuthorityRequests(value: unknown): LensSummonAuthorityRequests {
  const raw = safeRecord(value);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    request_route: safeString(raw.request_route).trim() || undefined,
    authority_route: safeString(raw.authority_route).trim() || undefined,
    grants_route: safeString(raw.grants_route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    executions_route: safeString(raw.executions_route).trim() || undefined,
    action: safeString(raw.action).trim() || undefined,
    approval_counts: parseNumberMap(raw.approval_counts),
    latest: Object.keys(latest).length ? latest : undefined,
    pending: safeRecordList(raw.pending),
    approved: safeRecordList(raw.approved),
    rejected: safeRecordList(raw.rejected),
    emergency: safeRecordList(raw.emergency),
    active_authority_grant: safeRecord(raw.active_authority_grant),
    authority_granted: safeBoolean(raw.authority_granted, false),
    summon_binding: safeBoolean(raw.summon_binding, false),
    summon_anywhere: safeBoolean(raw.summon_anywhere, false),
    governance: safeRecord(raw.governance),
  };
}

function parseSummonExecutionReceipts(value: unknown): LensSummonExecutionReceipts {
  const raw = safeRecord(value);
  const items = safeRecordList(raw.items);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    execute_route: safeString(raw.execute_route).trim() || undefined,
    authority_route: safeString(raw.authority_route).trim() || undefined,
    authority_grants_route: safeString(raw.authority_grants_route).trim() || undefined,
    limit: safeNumber(raw.limit, 0),
    total: safeNumber(raw.total, items.length),
    latest: Object.keys(latest).length ? latest : undefined,
    latest_status: safeString(raw.latest_status).trim() || undefined,
    latest_summon_binding:
      typeof raw.latest_summon_binding === "boolean" ? safeBoolean(raw.latest_summon_binding, false) : undefined,
    latest_summon_anywhere:
      typeof raw.latest_summon_anywhere === "boolean" ? safeBoolean(raw.latest_summon_anywhere, false) : undefined,
    latest_next_smallest_truthful_gap: safeString(raw.latest_next_smallest_truthful_gap).trim() || undefined,
    items,
    governance: safeRecord(raw.governance),
  };
}

function parsePersistentSupervisionAuthorityRequests(value: unknown): LensPersistentSupervisionAuthorityRequests {
  const raw = safeRecord(value);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    request_route: safeString(raw.request_route).trim() || undefined,
    grant_route: safeString(raw.grant_route).trim() || safeString(raw.authority_route).trim() || undefined,
    grants_route: safeString(raw.grants_route).trim() || safeString(raw.authority_grants_route).trim() || undefined,
    readiness_route: safeString(raw.readiness_route).trim() || undefined,
    preflight_route: safeString(raw.preflight_route).trim() || undefined,
    enablement_route: safeString(raw.enablement_route).trim() || undefined,
    execution_route: safeString(raw.boundary_route).trim() || undefined,
    decision_route: safeString(raw.decision_route).trim() || undefined,
    approval_action: safeString(raw.approval_action).trim() || undefined,
    pending_count: safeNumber(raw.pending_count, 0),
    approved_count: safeNumber(raw.approved_count, 0),
    rejected_count: safeNumber(raw.rejected_count, 0),
    emergency_count: safeNumber(raw.emergency_count, 0),
    total_count: safeNumber(raw.total_count, 0),
    latest: Object.keys(latest).length ? latest : undefined,
    items: safeRecordList(raw.items),
    by_status: parseRecordListMap(raw.by_status),
    authority_granted: safeBoolean(raw.authority_granted, false),
    service_config_write_authority: safeBoolean(raw.service_config_write_authority, false),
    persistent_supervision_execution_authority: safeBoolean(
      raw.persistent_supervision_execution_authority,
      false,
    ),
    persistent_supervision_enablement_allowed: safeBoolean(
      raw.persistent_supervision_enablement_allowed,
      false,
    ),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    active_enablement_authority_grant_receipt_id:
      safeString(raw.active_enablement_authority_grant_receipt_id).trim() || undefined,
    active_execution_authority_grant_receipt_id:
      safeString(raw.active_execution_authority_grant_receipt_id).trim() || undefined,
    governance: safeRecord(raw.governance),
  };
}

function parsePersistentSupervisionGrantReceipts(value: unknown): LensPersistentSupervisionGrantReceipts {
  const raw = safeRecord(value);
  const items = safeRecordList(raw.items);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    authority_route: safeString(raw.authority_route).trim() || undefined,
    request_route: safeString(raw.request_route).trim() || undefined,
    requests_route: safeString(raw.requests_route).trim() || undefined,
    readiness_route: safeString(raw.readiness_route).trim() || undefined,
    boundary_route: safeString(raw.boundary_route).trim() || undefined,
    limit: safeNumber(raw.limit, 0),
    total: safeNumber(raw.total, items.length),
    latest: Object.keys(latest).length ? latest : undefined,
    active_latest: safeRecord(raw.active_latest),
    authority_granted: safeBoolean(raw.authority_granted, false),
    service_config_write_authority: safeBoolean(raw.service_config_write_authority, false),
    persistent_supervision_execution_authority: safeBoolean(
      raw.persistent_supervision_execution_authority,
      false,
    ),
    persistent_supervision_enablement_allowed: safeBoolean(
      raw.persistent_supervision_enablement_allowed,
      false,
    ),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    items,
    governance: safeRecord(raw.governance),
  };
}

function parsePersistentSupervisionExecutionReadiness(value: unknown): LensPersistentSupervisionExecutionReadiness {
  const raw = safeRecord(value);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    ready: safeBoolean(raw.ready, false),
    approval_ready: safeBoolean(raw.approval_ready, false),
    request_readback_ready: safeBoolean(raw.request_readback_ready, false),
    request_pending_count: safeNumber(raw.request_pending_count, 0),
    request_approved_count: safeNumber(raw.request_approved_count, 0),
    request_total_count: safeNumber(raw.request_total_count, 0),
    latest_request_approval_id: safeString(raw.latest_request_approval_id).trim() || undefined,
    boundary_observed: safeBoolean(raw.boundary_observed, false),
    enablement_authority_granted: safeBoolean(raw.enablement_authority_granted, false),
    active_enablement_authority_grant_receipt_id:
      safeString(raw.active_enablement_authority_grant_receipt_id).trim() || undefined,
    execution_authority_granted: safeBoolean(raw.execution_authority_granted, false),
    active_execution_authority_grant_receipt_id:
      safeString(raw.active_execution_authority_grant_receipt_id).trim() || undefined,
    persistent_supervision_enablement_allowed: safeBoolean(
      raw.persistent_supervision_enablement_allowed,
      false,
    ),
    service_config_updated: safeBoolean(raw.service_config_updated, false),
    service_config_write_authority: safeBoolean(raw.service_config_write_authority, false),
    persistent_supervision_execution_authority: safeBoolean(
      raw.persistent_supervision_execution_authority,
      false,
    ),
    receipt_write_authority: safeBoolean(raw.receipt_write_authority, false),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    requirements_total: safeNumber(raw.requirements_total, 0),
    requirements_ready_total: safeNumber(raw.requirements_ready_total, 0),
    requirements_blocked_total: safeNumber(raw.requirements_blocked_total, 0),
    blocked_requirements: safeStringList(raw.blocked_requirements),
    operator_surface_readback_ready: safeBoolean(raw.operator_surface_readback_ready, false),
    first_blocked_requirement: safeString(raw.first_blocked_requirement).trim() || undefined,
    first_blocked_requirement_handoff: safeRecord(raw.first_blocked_requirement_handoff),
    blocked_requirement_handoffs: safeRecordList(raw.blocked_requirement_handoffs),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap).trim() || undefined,
    blockers: safeStringList(raw.blockers),
    governance: safeRecord(raw.governance),
  };
}

function parsePersistentSupervisionExecutionReceipts(value: unknown): LensPersistentSupervisionExecutionReceipts {
  const raw = safeRecord(value);
  const items = safeRecordList(raw.items);
  const latest = safeRecord(raw.latest);
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    execution_route: safeString(raw.execution_route).trim() || undefined,
    readiness_route: safeString(raw.readiness_route).trim() || undefined,
    authority_grants_route: safeString(raw.authority_grants_route).trim() || undefined,
    limit: safeNumber(raw.limit, 0),
    total: safeNumber(raw.total, items.length),
    latest: Object.keys(latest).length ? latest : undefined,
    service_config_updated: safeBoolean(raw.service_config_updated, false),
    persistent_supervision_enablement_allowed: safeBoolean(
      raw.persistent_supervision_enablement_allowed,
      false,
    ),
    persistent_supervision_ready: safeBoolean(raw.persistent_supervision_ready, false),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    latest_service_config_path: safeString(raw.latest_service_config_path).trim() || undefined,
    items,
    governance: safeRecord(raw.governance),
  };
}

function parseRuntimeLoopRequirementHandoff(value: unknown): LensRuntimeLoopRequirementHandoff | null {
  if (!isRecord(value)) return null;
  const id = safeString(value.id).trim();
  const status = safeString(value.status).trim();
  const nextStep = safeString(value.next_step).trim();
  if (!id && !status && !nextStep) return null;
  return {
    id: id || undefined,
    label: safeString(value.label).trim() || undefined,
    status: status || undefined,
    route: safeString(value.route).trim() || undefined,
    readiness_route: safeString(value.readiness_route).trim() || undefined,
    request_route: safeString(value.request_route).trim() || undefined,
    requests_route: safeString(value.requests_route).trim() || undefined,
    grant_route: safeString(value.grant_route).trim() || undefined,
    grants_route: safeString(value.grants_route).trim() || undefined,
    denials_route: safeString(value.denials_route).trim() || undefined,
    execution_readiness_route: safeString(value.execution_readiness_route).trim() || undefined,
    execution_request_route: safeString(value.execution_request_route).trim() || undefined,
    execution_requests_route: safeString(value.execution_requests_route).trim() || undefined,
    execution_grant_route: safeString(value.execution_grant_route).trim() || undefined,
    execution_grants_route: safeString(value.execution_grants_route).trim() || undefined,
    summon_route: safeString(value.summon_route).trim() || undefined,
    tray_route: safeString(value.tray_route).trim() || undefined,
    overlay_route: safeString(value.overlay_route).trim() || undefined,
    loop_route: safeString(value.loop_route).trim() || undefined,
    next_step: nextStep || undefined,
    authority_required: safeString(value.authority_required).trim() || undefined,
    authority_granted:
      typeof value.authority_granted === "boolean" ? safeBoolean(value.authority_granted, false) : undefined,
    blockers: safeStringList(value.blockers),
    would_execute: typeof value.would_execute === "boolean" ? safeBoolean(value.would_execute, false) : undefined,
    would_mutate: typeof value.would_mutate === "boolean" ? safeBoolean(value.would_mutate, false) : undefined,
  };
}

function parseRuntimeLoopReadiness(value: unknown): LensRuntimeLoopReadiness {
  const raw = safeRecord(value);
  const requirements = Array.isArray(raw.requirements) ? raw.requirements.filter(isRecord) : [];
  const blockedRequirementHandoffs = Array.isArray(raw.blocked_requirement_handoffs)
    ? raw.blocked_requirement_handoffs
        .map(parseRuntimeLoopRequirementHandoff)
        .filter((item): item is LensRuntimeLoopRequirementHandoff => item !== null)
    : [];
  const firstBlockedRequirementHandoff =
    parseRuntimeLoopRequirementHandoff(raw.first_blocked_requirement_handoff) ?? blockedRequirementHandoffs[0];
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
    operator_surface_readback_ready:
      typeof raw.operator_surface_readback_ready === "boolean"
        ? safeBoolean(raw.operator_surface_readback_ready, false)
        : undefined,
    first_blocked_requirement: safeString(raw.first_blocked_requirement).trim() || undefined,
    first_blocked_requirement_handoff: firstBlockedRequirementHandoff,
    blocked_requirement_handoffs: blockedRequirementHandoffs,
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
    supervision_authority_request_route: safeString(raw.supervision_authority_request_route).trim(),
    supervision_authority_requests_route: safeString(raw.supervision_authority_requests_route).trim(),
    supervision_authority_requests: parseHostSupervisionAuthorityRequests(raw.supervision_authority_requests),
    resident_runtime_authority_request_route: safeString(raw.resident_runtime_authority_request_route).trim(),
    resident_runtime_authority_requests_route: safeString(raw.resident_runtime_authority_requests_route).trim(),
    resident_runtime_authority_requests: parseResidentRuntimeAuthorityRequests(raw.resident_runtime_authority_requests),
    resident_runtime_authority_grant_route: safeString(raw.resident_runtime_authority_grant_route).trim(),
    resident_runtime_authority_grant: safeRecord(raw.resident_runtime_authority_grant),
    resident_runtime_authority_grant_receipts_route: safeString(
      raw.resident_runtime_authority_grant_receipts_route,
    ).trim(),
    resident_runtime_authority_grant_receipts: safeRecord(raw.resident_runtime_authority_grant_receipts),
    resident_runtime_authority_grant_readiness_route: safeString(
      raw.resident_runtime_authority_grant_readiness_route,
    ).trim(),
    resident_runtime_authority_grant_readiness: parseResidentRuntimeAuthorityReadiness(
      raw.resident_runtime_authority_grant_readiness,
    ),
    resident_runtime_execution_receipts_route: safeString(raw.resident_runtime_execution_receipts_route).trim(),
    resident_runtime_execution_receipts: parseResidentRuntimeExecutionReceipts(raw.resident_runtime_execution_receipts),
    runtime_loop_readiness_route: safeString(raw.runtime_loop_readiness_route).trim(),
    runtime_loop_readiness: parseRuntimeLoopReadiness(raw.runtime_loop_readiness),
    persistent_supervision_enablement_authority_requests_route: safeString(
      raw.persistent_supervision_enablement_authority_requests_route,
    ).trim(),
    persistent_supervision_enablement_authority_requests: parsePersistentSupervisionAuthorityRequests(
      raw.persistent_supervision_enablement_authority_requests,
    ),
    persistent_supervision_enablement_authority_grant_route: safeString(
      raw.persistent_supervision_enablement_authority_grant_route,
    ).trim(),
    persistent_supervision_enablement_authority_grants_route: safeString(
      raw.persistent_supervision_enablement_authority_grants_route,
    ).trim(),
    persistent_supervision_enablement_authority_grants: parsePersistentSupervisionGrantReceipts(
      raw.persistent_supervision_enablement_authority_grants,
    ),
    persistent_supervision_enablement_execution_request_route: safeString(
      raw.persistent_supervision_enablement_execution_request_route,
    ).trim(),
    persistent_supervision_enablement_execution_requests_route: safeString(
      raw.persistent_supervision_enablement_execution_requests_route,
    ).trim(),
    persistent_supervision_enablement_execution_requests: parsePersistentSupervisionAuthorityRequests(
      raw.persistent_supervision_enablement_execution_requests,
    ),
    persistent_supervision_enablement_execution_authority_grant_route: safeString(
      raw.persistent_supervision_enablement_execution_authority_grant_route,
    ).trim(),
    persistent_supervision_enablement_execution_authority_grants_route: safeString(
      raw.persistent_supervision_enablement_execution_authority_grants_route,
    ).trim(),
    persistent_supervision_enablement_execution_authority_grants: parsePersistentSupervisionGrantReceipts(
      raw.persistent_supervision_enablement_execution_authority_grants,
    ),
    persistent_supervision_enablement_execution_apply_route: safeString(
      raw.persistent_supervision_enablement_execution_apply_route,
    ).trim(),
    persistent_supervision_enablement_execution_readiness_route: safeString(
      raw.persistent_supervision_enablement_execution_readiness_route,
    ).trim(),
    persistent_supervision_enablement_execution_readiness: parsePersistentSupervisionExecutionReadiness(
      raw.persistent_supervision_enablement_execution_readiness,
    ),
    persistent_supervision_enablement_execution_receipts_route: safeString(
      raw.persistent_supervision_enablement_execution_receipts_route,
    ).trim(),
    persistent_supervision_enablement_execution_receipts: parsePersistentSupervisionExecutionReceipts(
      raw.persistent_supervision_enablement_execution_receipts,
    ),
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

function parseStage6ClosureHandoff(value: unknown): LensStage6ClosureHandoff | undefined {
  if (!isRecord(value)) return undefined;
  const fields = [
    "next_step",
    "route",
    "readiness_route",
    "summon_route",
    "preflight_route",
    "status_route",
    "surface_route",
    "host_route",
    "runtime_loop_readiness_route",
    "runtime_loop_route",
    "resident_runtime_plan_route",
    "tray_route",
    "overlay_route",
    "proof_script",
    "child_proof_script",
    "authority_required",
    "next_smallest_truthful_gap",
    "first_blocker_family",
    "first_blocker_family_next_smallest_truthful_gap",
  ];
  const hasStringField = fields.some((field) => Boolean(safeString(value[field]).trim()));
  const hasNestedHandoff =
    isRecord(value.first_blocker_family_handoff) ||
    isRecord(value.first_blocker_family_completion_audit_handoff) ||
    isRecord(value.summon_anywhere_family_chain_completion_audit_handoff) ||
    isRecord(value.checkpoint_proof_handoff);
  const hasBooleanField =
    typeof value.read_only_contract === "boolean" ||
    typeof value.diagnostic_only === "boolean" ||
    typeof value.would_execute === "boolean" ||
    typeof value.would_mutate === "boolean";
  const blockedFamilies = safeStringList(value.blocked_families);

  if (!hasStringField && !hasNestedHandoff && !hasBooleanField && blockedFamilies.length === 0) {
    return undefined;
  }

  return {
    next_step: safeString(value.next_step).trim() || undefined,
    route: safeString(value.route).trim() || undefined,
    readiness_route: safeString(value.readiness_route).trim() || undefined,
    summon_route: safeString(value.summon_route).trim() || undefined,
    preflight_route: safeString(value.preflight_route).trim() || undefined,
    status_route: safeString(value.status_route).trim() || undefined,
    surface_route: safeString(value.surface_route).trim() || undefined,
    host_route: safeString(value.host_route).trim() || undefined,
    runtime_loop_readiness_route: safeString(value.runtime_loop_readiness_route).trim() || undefined,
    runtime_loop_route: safeString(value.runtime_loop_route).trim() || undefined,
    resident_runtime_plan_route: safeString(value.resident_runtime_plan_route).trim() || undefined,
    tray_route: safeString(value.tray_route).trim() || undefined,
    overlay_route: safeString(value.overlay_route).trim() || undefined,
    proof_script: safeString(value.proof_script).trim() || undefined,
    child_proof_script: safeString(value.child_proof_script).trim() || undefined,
    authority_required: safeString(value.authority_required).trim() || undefined,
    next_smallest_truthful_gap: safeString(value.next_smallest_truthful_gap).trim() || undefined,
    first_blocker_family: safeString(value.first_blocker_family).trim() || undefined,
    first_blocker_family_next_smallest_truthful_gap:
      safeString(value.first_blocker_family_next_smallest_truthful_gap).trim() || undefined,
    blocked_families: blockedFamilies,
    read_only_contract:
      typeof value.read_only_contract === "boolean" ? safeBoolean(value.read_only_contract, false) : undefined,
    diagnostic_only: typeof value.diagnostic_only === "boolean" ? safeBoolean(value.diagnostic_only, false) : undefined,
    would_execute: typeof value.would_execute === "boolean" ? safeBoolean(value.would_execute, false) : undefined,
    would_mutate: typeof value.would_mutate === "boolean" ? safeBoolean(value.would_mutate, false) : undefined,
    first_blocker_family_handoff: safeRecord(value.first_blocker_family_handoff),
    first_blocker_family_completion_audit_handoff: safeRecord(value.first_blocker_family_completion_audit_handoff),
    summon_anywhere_family_chain_completion_audit_handoff: safeRecord(
      value.summon_anywhere_family_chain_completion_audit_handoff,
    ),
    checkpoint_proof_handoff: safeRecord(value.checkpoint_proof_handoff),
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
    next_smallest_truthful_gap: safeString(value.next_smallest_truthful_gap).trim() || undefined,
    handoff: parseStage6ClosureHandoff(value.handoff),
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

function parseStage6NextHandoff(value: unknown): LensStage6NextHandoff {
  const raw = safeRecord(value);
  return {
    kind: safeString(raw.kind).trim(),
    status: safeString(raw.status).trim(),
    ready_to_close: safeBoolean(raw.ready_to_close, false),
    stage_next_smallest_truthful_gap: safeString(raw.stage_next_smallest_truthful_gap).trim() || undefined,
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap).trim() || undefined,
    recommended_next_slice: safeString(raw.recommended_next_slice).trim() || undefined,
    recommended_handoff_source: safeString(raw.recommended_handoff_source).trim() || undefined,
    recommended_proof_script: safeString(raw.recommended_proof_script).trim() || undefined,
    recommended_route: safeString(raw.recommended_route).trim() || undefined,
    recommended_readiness_route: safeString(raw.recommended_readiness_route).trim() || undefined,
    recommended_request_route: safeString(raw.recommended_request_route).trim() || undefined,
    recommended_requests_route: safeString(raw.recommended_requests_route).trim() || undefined,
    recommended_grant_route: safeString(raw.recommended_grant_route).trim() || undefined,
    recommended_grants_route: safeString(raw.recommended_grants_route).trim() || undefined,
    recommended_denials_route: safeString(raw.recommended_denials_route).trim() || undefined,
    recommended_execution_readiness_route: safeString(raw.recommended_execution_readiness_route).trim() || undefined,
    authority_required: safeString(raw.authority_required).trim() || undefined,
    recommended_prerequisites_handoff_source:
      safeString(raw.recommended_prerequisites_handoff_source).trim() || undefined,
    recommended_prerequisites_next_slice: safeString(raw.recommended_prerequisites_next_slice).trim() || undefined,
    recommended_prerequisites_proof_script: safeString(raw.recommended_prerequisites_proof_script).trim() || undefined,
    recommended_prerequisites_route: safeString(raw.recommended_prerequisites_route).trim() || undefined,
    recommended_prerequisites_readiness_route:
      safeString(raw.recommended_prerequisites_readiness_route).trim() || undefined,
    recommended_prerequisites_authority_required:
      safeString(raw.recommended_prerequisites_authority_required).trim() || undefined,
    recommended_first_missing_handoff_source:
      safeString(raw.recommended_first_missing_handoff_source).trim() || undefined,
    recommended_first_missing_next_slice: safeString(raw.recommended_first_missing_next_slice).trim() || undefined,
    recommended_first_missing_proof_script: safeString(raw.recommended_first_missing_proof_script).trim() || undefined,
    recommended_first_missing_route: safeString(raw.recommended_first_missing_route).trim() || undefined,
    recommended_first_missing_readiness_route:
      safeString(raw.recommended_first_missing_readiness_route).trim() || undefined,
    recommended_first_missing_authority_required:
      safeString(raw.recommended_first_missing_authority_required).trim() || undefined,
    first_blocked_criterion: safeString(raw.first_blocked_criterion).trim() || undefined,
    first_blocked_criterion_next_smallest_truthful_gap:
      safeString(raw.first_blocked_criterion_next_smallest_truthful_gap).trim() || undefined,
    persistent_supervision_required_prerequisites_observed: safeBoolean(
      raw.persistent_supervision_required_prerequisites_observed,
      false,
    ),
    persistent_supervision_missing_required_before_enable: safeStringList(
      raw.persistent_supervision_missing_required_before_enable,
    ),
    persistent_supervision_first_missing_required_before_enable:
      safeString(raw.persistent_supervision_first_missing_required_before_enable).trim() || undefined,
    persistent_supervision_first_missing_requirement_handoff: safeRecord(
      raw.persistent_supervision_first_missing_requirement_handoff,
    ),
    persistent_supervision_required_prerequisites_handoff: safeRecord(
      raw.persistent_supervision_required_prerequisites_handoff,
    ),
    activation_execution_handoff_observed: safeBoolean(raw.activation_execution_handoff_observed, false),
    activation_execution_handoff: safeRecord(raw.activation_execution_handoff),
    persistent_supervision_enablement_authority_handoff_observed: safeBoolean(
      raw.persistent_supervision_enablement_authority_handoff_observed,
      false,
    ),
    persistent_supervision_enablement_authority_handoff: safeRecord(
      raw.persistent_supervision_enablement_authority_handoff,
    ),
    resident_runtime_candidate_handoff_observed: safeBoolean(raw.resident_runtime_candidate_handoff_observed, false),
    resident_runtime_candidate_handoff: safeRecord(raw.resident_runtime_candidate_handoff),
    governance: safeRecord(raw.governance),
  };
}

function parseStage6OperatorAction(value: unknown): LensStage6OperatorAction {
  const raw = safeRecord(value);
  return {
    id: safeString(raw.id).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    method: safeString(raw.method).trim() || undefined,
    approval_action: safeString(raw.approval_action).trim() || undefined,
    requires: safeStringList(raw.requires),
    mode: safeString(raw.mode).trim() || undefined,
    live_effect: safeString(raw.live_effect).trim() || undefined,
    operator_supplied_values_required: safeBoolean(raw.operator_supplied_values_required, false),
    script_would_execute: safeBoolean(raw.script_would_execute, false),
    script_would_mutate: safeBoolean(raw.script_would_mutate, false),
    approved_approval_id: safeString(raw.approved_approval_id).trim() || undefined,
    active_approval_id: safeString(raw.active_approval_id).trim() || undefined,
    operator_command: parseStage6OperatorCommand(raw.operator_command),
  };
}

function parseStage6OperatorCommand(value: unknown): LensStage6OperatorCommand {
  const raw = safeRecord(value);
  return {
    command: safeString(raw.command).trim() || undefined,
    mode: safeString(raw.mode).trim() || undefined,
    requires_confirmation: safeBoolean(raw.requires_confirmation, false),
    requires_approval_id: safeBoolean(raw.requires_approval_id, false),
    requires_operator_approval_decision: safeBoolean(raw.requires_operator_approval_decision, false),
    available_now: safeBoolean(raw.available_now, false),
    preview_only: safeBoolean(raw.preview_only, false),
    availability_reason: safeString(raw.availability_reason).trim() || undefined,
  };
}

function parseStage6PrerequisiteStep(value: unknown): LensStage6PrerequisiteStep | null {
  const raw = safeRecord(value);
  const id = safeString(raw.id).trim();
  if (!id) return null;
  const actions = Array.isArray(raw.actions) ? raw.actions.map(parseStage6OperatorAction) : [];
  return {
    id,
    family: safeString(raw.family).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    readiness_route: safeString(raw.readiness_route).trim() || undefined,
    ready: safeBoolean(raw.ready, false),
    status: safeString(raw.status).trim() || undefined,
    requirement_state: safeString(raw.requirement_state).trim() || undefined,
    blocker: safeString(raw.blocker).trim() || undefined,
    blocked_reason: safeString(raw.blocked_reason).trim() || undefined,
    proof_script: safeString(raw.proof_script).trim() || undefined,
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap).trim() || undefined,
    authority_state: safeRecord(raw.authority_state),
    actions,
    next_operator_action: parseStage6OperatorAction(raw.next_operator_action),
    script_would_execute: safeBoolean(raw.script_would_execute, false),
    script_would_mutate: safeBoolean(raw.script_would_mutate, false),
  };
}

function parseStage6PrerequisiteBringup(value: unknown): LensStage6PrerequisiteBringup {
  const raw = safeRecord(value);
  const orderedSteps = Array.isArray(raw.ordered_prerequisite_steps)
    ? raw.ordered_prerequisite_steps
        .map(parseStage6PrerequisiteStep)
        .filter((item): item is LensStage6PrerequisiteStep => item !== null)
    : [];
  const enablementSteps = Array.isArray(raw.persistent_supervision_enablement_steps)
    ? raw.persistent_supervision_enablement_steps.map(parseStage6OperatorAction)
    : [];
  const operatorSequence = Array.isArray(raw.operator_sequence)
    ? raw.operator_sequence.map(parseStage6OperatorAction)
    : [];
  const checks = Array.isArray(raw.checks) ? raw.checks.map(safeRecord) : [];
  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    mode: safeString(raw.mode).trim() || undefined,
    stage: safeString(raw.stage).trim() || undefined,
    stage_state: safeString(raw.stage_state).trim() || undefined,
    ready_to_close: safeBoolean(raw.ready_to_close, false),
    acceptance_criterion: safeString(raw.acceptance_criterion).trim() || undefined,
    closure_next_smallest_truthful_gap: safeString(raw.closure_next_smallest_truthful_gap).trim() || undefined,
    persistent_supervision_next_smallest_truthful_gap:
      safeString(raw.persistent_supervision_next_smallest_truthful_gap).trim() || undefined,
    current_truthful_gap: safeString(raw.current_truthful_gap).trim() || undefined,
    current_truthful_gap_basis: safeString(raw.current_truthful_gap_basis).trim() || undefined,
    current_first_missing_requirement: safeString(raw.current_first_missing_requirement).trim() || undefined,
    current_first_missing_truthful_gap: safeString(raw.current_first_missing_truthful_gap).trim() || undefined,
    raw_persistent_supervision_next_smallest_truthful_gap:
      safeString(raw.raw_persistent_supervision_next_smallest_truthful_gap).trim() || undefined,
    required_before_enable: safeStringList(raw.required_before_enable),
    missing_required_before_enable: safeStringList(raw.missing_required_before_enable),
    required_before_enable_ready: safeBoolean(raw.required_before_enable_ready, false),
    first_missing_required_before_enable: safeString(raw.first_missing_required_before_enable).trim() || undefined,
    first_missing_requirement_handoff: safeRecord(raw.first_missing_requirement_handoff),
    ordered_prerequisite_steps: orderedSteps,
    persistent_supervision_enablement_steps: enablementSteps,
    next_operator_action: parseStage6OperatorAction(raw.next_operator_action),
    next_operator_action_requirement: safeString(raw.next_operator_action_requirement).trim() || undefined,
    next_operator_command: parseStage6OperatorCommand(raw.next_operator_command),
    operator_sequence: operatorSequence,
    operator_sequence_command_availability: safeRecord(raw.operator_sequence_command_availability),
    checks,
    evidence: safeStringList(raw.evidence),
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
    next_handoff: parseStage6NextHandoff(raw.next_handoff),
    prerequisite_bringup: parseStage6PrerequisiteBringup(raw.prerequisite_bringup),
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

export function parseLensActionResponse(value: unknown): LensActionResponse {
  const raw = safeRecord(value);
  const supervisionAuthority = safeRecord(raw.supervision_authority);
  const residentRuntimeAuthority = safeRecord(raw.resident_runtime_execution_authority);
  return {
    ok: safeBoolean(raw.ok, false),
    applied: safeBoolean(raw.applied, false),
    executed: safeBoolean(raw.executed, false),
    approval_requested: safeBoolean(raw.approval_requested, false),
    status: safeString(raw.status).trim() || undefined,
    action: safeString(raw.action).trim() || undefined,
    approval_id: safeString(raw.approval_id).trim() || undefined,
    route:
      safeString(raw.route).trim() ||
      safeString(supervisionAuthority.route).trim() ||
      safeString(residentRuntimeAuthority.route).trim() ||
      safeString(safeRecord(raw.governance).route).trim() ||
      undefined,
    authority_granted: safeBoolean(raw.authority_granted, false),
    resident_claim_allowed: safeBoolean(raw.resident_claim_allowed, false),
    blockers: safeStringList(raw.blockers),
    approval: safeRecord(raw.approval),
    governance: safeRecord(raw.governance),
    raw,
    error: safeString(raw.error).trim() || undefined,
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
    resident_runtime_authority_grant_readiness: parseResidentRuntimeAuthorityReadiness(
      raw.resident_runtime_authority_grant_readiness,
    ),
    resident_runtime_execution_receipts: parseResidentRuntimeExecutionReceipts(raw.resident_runtime_execution_receipts),
    os_binding_authority_requests: parseOsBindingAuthorityRequests(raw.os_binding_authority_requests),
    os_binding_execution_readiness: parseOsBindingExecutionReadiness(raw.os_binding_execution_readiness),
    os_binding_execution_receipts: parseOsBindingExecutionReceipts(raw.os_binding_execution_receipts),
    tray_authority_requests: parseTrayAuthorityRequests(raw.tray_authority_requests),
    tray_execution_receipts: parseTrayExecutionReceipts(raw.tray_execution_receipts),
    overlay_authority_requests: parseOverlayAuthorityRequests(raw.overlay_authority_requests),
    overlay_execution_receipts: parseOverlayExecutionReceipts(raw.overlay_execution_receipts),
    summon_authority_requests: parseSummonAuthorityRequests(raw.summon_authority_requests),
    summon_execution_receipts: parseSummonExecutionReceipts(raw.summon_execution_receipts),
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

  async requestPersistentSupervisionEnablementAuthority(opts?: {
    actor?: string;
    reason?: string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/host/persistent-supervision/enablement/authority/request`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts?.signal,
      body: JSON.stringify({
        actor: opts?.actor ?? "chat_ui.system",
        reason: opts?.reason ?? "request Lens persistent supervision enablement authority from operator UI",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async grantPersistentSupervisionEnablementAuthority(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    leaseSeconds?: number;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/host/persistent-supervision/enablement/authority`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "grant Lens persistent supervision enablement authority from operator UI",
        lease_seconds: opts.leaseSeconds ?? 3600,
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async requestPersistentSupervisionExecutionAuthority(opts?: {
    actor?: string;
    reason?: string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/host/persistent-supervision/enablement/execution/request`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts?.signal,
      body: JSON.stringify({
        actor: opts?.actor ?? "chat_ui.system",
        reason: opts?.reason ?? "request Lens persistent supervision execution authority from operator UI",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async grantPersistentSupervisionExecutionAuthority(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    leaseSeconds?: number;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/host/persistent-supervision/enablement/execution/authority`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "grant Lens persistent supervision execution authority from operator UI",
        lease_seconds: opts.leaseSeconds ?? 3600,
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async applyPersistentSupervisionEnablement(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/host/persistent-supervision/enablement/execution/apply`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "apply Lens persistent supervision enablement from operator UI",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async requestHostSupervisionAuthority(opts?: {
    actor?: string;
    reason?: string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/host/supervision/authority/request`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts?.signal,
      body: JSON.stringify({
        actor: opts?.actor ?? "chat_ui.system",
        reason: opts?.reason ?? "request Lens host supervision authority from operator UI",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async grantHostSupervisionAuthority(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    leaseSeconds?: number;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/host/supervision/authority`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "grant Lens host supervision authority from operator UI",
        lease_seconds: opts.leaseSeconds ?? 3600,
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async executeHostSupervision(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    runSeconds?: number;
    mode?: "bounded_candidate" | "resident_start" | "resident_stop" | string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const safeRunSeconds = Math.max(1, Math.min(Math.floor(opts.runSeconds ?? 2), 10));
    const url = `${this.baseUrl}/lens/host/supervision/execute`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "execute Lens host supervision from operator UI",
        run_seconds: safeRunSeconds,
        mode: opts.mode ?? "bounded_candidate",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async requestOsBindingAuthority(opts?: {
    actor?: string;
    reason?: string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/os-binding/authority/request`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts?.signal,
      body: JSON.stringify({
        actor: opts?.actor ?? "chat_ui.system",
        reason: opts?.reason ?? "request Lens OS-binding hotkey authority from operator UI",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async grantOsBindingAuthority(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    leaseSeconds?: number;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/os-binding/authority`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "grant Lens OS-binding hotkey authority from operator UI",
        lease_seconds: opts.leaseSeconds ?? 3600,
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async executeOsBinding(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    runSeconds?: number;
    mode?: "bind" | "stop" | string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const safeRunSeconds = Math.max(1, Math.min(Math.floor(opts.runSeconds ?? 2), 10));
    const url = `${this.baseUrl}/lens/os-binding/execute`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "execute Lens OS-binding hotkey action from operator UI",
        run_seconds: safeRunSeconds,
        mode: opts.mode ?? "bind",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async requestTrayAuthority(opts?: {
    actor?: string;
    reason?: string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/tray/authority/request`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts?.signal,
      body: JSON.stringify({
        actor: opts?.actor ?? "chat_ui.system",
        reason: opts?.reason ?? "request Lens tray presence authority from operator UI",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async grantTrayAuthority(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    leaseSeconds?: number;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/tray/authority`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "grant Lens tray presence authority from operator UI",
        lease_seconds: opts.leaseSeconds ?? 3600,
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async executeTrayPresence(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    runSeconds?: number;
    mode?: "start" | "stop" | string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const safeRunSeconds = Math.max(1, Math.min(Math.floor(opts.runSeconds ?? 2), 10));
    const url = `${this.baseUrl}/lens/tray/execute`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "execute Lens tray presence from operator UI",
        run_seconds: safeRunSeconds,
        mode: opts.mode ?? "start",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async requestOverlayAuthority(opts?: {
    actor?: string;
    reason?: string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/overlay/authority/request`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts?.signal,
      body: JSON.stringify({
        actor: opts?.actor ?? "chat_ui.system",
        reason: opts?.reason ?? "request Lens overlay window authority from operator UI",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async grantOverlayAuthority(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    leaseSeconds?: number;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/overlay/authority`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "grant Lens overlay window authority from operator UI",
        lease_seconds: opts.leaseSeconds ?? 3600,
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async executeOverlayWindow(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    runSeconds?: number;
    mode?: "start" | "stop" | string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const safeRunSeconds = Math.max(1, Math.min(Math.floor(opts.runSeconds ?? 2), 10));
    const url = `${this.baseUrl}/lens/overlay/execute`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "execute Lens overlay window from operator UI",
        run_seconds: safeRunSeconds,
        mode: opts.mode ?? "start",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async requestSummonAuthority(opts?: {
    actor?: string;
    reason?: string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/summon/authority/request`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts?.signal,
      body: JSON.stringify({
        actor: opts?.actor ?? "chat_ui.system",
        reason: opts?.reason ?? "request Lens summon action authority from operator UI",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async grantSummonAuthority(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    leaseSeconds?: number;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/summon/authority`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "grant Lens summon action authority from operator UI",
        lease_seconds: opts.leaseSeconds ?? 3600,
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async executeSummonAction(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    runSeconds?: number;
    mode?: "launch" | "status" | string;
    allowLaunch?: boolean;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const safeRunSeconds = Math.max(1, Math.min(Math.floor(opts.runSeconds ?? 2), 10));
    const url = `${this.baseUrl}/lens/summon/execute`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "execute Lens summon action from operator UI",
        run_seconds: safeRunSeconds,
        mode: opts.mode ?? "launch",
        allow_launch: opts.allowLaunch ?? false,
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async requestResidentRuntimeAuthority(opts?: {
    actor?: string;
    reason?: string;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/resident-runtime/authority-grant/request`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts?.signal,
      body: JSON.stringify({
        actor: opts?.actor ?? "chat_ui.system",
        reason: opts?.reason ?? "request Lens resident runtime execution authority from operator UI",
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async grantResidentRuntimeAuthority(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    leaseSeconds?: number;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const url = `${this.baseUrl}/lens/resident-runtime/authority-grant`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "grant Lens resident runtime execution authority from operator UI",
        lease_seconds: opts.leaseSeconds ?? 3600,
      }),
    });
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
    return parseLensActionResponse(json);
  }

  async executeResidentRuntimeActivation(opts: {
    approvalId: string;
    actor?: string;
    reason?: string;
    runSeconds?: number;
    signal?: AbortSignal;
  }): Promise<LensActionResponse> {
    const safeRunSeconds = Math.max(1, Math.min(Math.floor(opts.runSeconds ?? 2), 10));
    const url = `${this.baseUrl}/lens/resident-runtime/execute`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: opts.signal,
      body: JSON.stringify({
        approval_id: opts.approvalId,
        actor: opts.actor ?? "chat_ui.system",
        reason: opts.reason ?? "start bounded Lens resident runtime from operator UI",
        run_seconds: safeRunSeconds,
      }),
    });
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
    return parseLensActionResponse(json);
  }
}
