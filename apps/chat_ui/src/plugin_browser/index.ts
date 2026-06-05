/**
 * Plugin Browser module (UI).
 *
 * A typed, defensive, framework-agnostic client for Francis plugin inventory and lifecycle actions.
 *
 * Design contract
 * ---------------
 *  1) Framework-agnostic:
 *     - No React imports, no UI state, no DOM dependencies.
 *
 *  2) Defensive parsing:
 *     - Treat JSON as untrusted.
 *     - Accept backend drift by supporting common alias fields and response shapes.
 *
 *  3) Observability-first:
 *     - Rich error type includes HTTP status, URL, request id, and body snippet.
 *     - Optional hooks for request/response tracing (no dependencies).
 *
 *  4) Forward-compatible endpoints:
 *     - Endpoints are builder functions (overrideable) so API routes can evolve.
 *
 *  5) Governance-friendly:
 *     - Mutations accept optional "reason" and may return approval_id.
 *
 * Expected backend (typical; override with endpoints):
 *  - GET    /plugins/list
 *  - GET    /plugins/get?id=...
 *  - POST   /plugins/enable
 *  - POST   /plugins/disable
 *  - POST   /plugins/install
 *  - POST   /plugins/uninstall
 *  - POST   /plugins/run
 *  - POST   /plugins/reload
 *  - GET    /plugins/capabilities/packs/operator/review
 *  - GET    /plugins/capabilities/packs/operator/review/decisions
 *  - POST   /plugins/capabilities/packs/operator/review/decisions
 *  - POST   /plugins/capabilities/packs/operator/review/decisions/bulk-from-surface
 *
 * Notes
 * -----
 * - This client never handles secret material. If a plugin requires credentials,
 *   that should be handled by the credential manager + approvals system.
 * - "run" is intentionally generic: the plugin runtime contract may evolve.
 */

/* -------------------------------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------------------------------- */

const DEFAULT_PLUGIN_MUTATION_ACTOR = "chat_ui.plugins";

export type PluginStatus =
  | "enabled"
  | "disabled"
  | "error"
  | "installing"
  | "uninstalling"
  | "updating"
  | "unknown"
  | string;

export type PluginSourceKind =
  | "registry"
  | "git"
  | "url"
  | "path"
  | "local_archive"
  | "builtin"
  | string;

export type PluginCapabilityKind =
  | "tool"
  | "command"
  | "event_handler"
  | "memory_provider"
  | "vector_backend"
  | "ui_extension"
  | "transport"
  | string;

/**
 * Minimal capability descriptor. Backends may emit richer shapes; we keep it tolerant.
 */
export type PluginCapability = {
  id?: string;
  kind: PluginCapabilityKind;
  name: string;

  description?: string;

  // Optional I/O schema hints (opaque to UI unless rendered)
  input_schema?: unknown;
  output_schema?: unknown;

  meta?: Record<string, unknown>;
};

export type PluginRef = {
  id: string;

  name: string;
  version?: string;

  status?: PluginStatus;
  enabled?: boolean;

  description?: string;

  author?: string;
  homepage?: string;
  license?: string;

  source_kind?: PluginSourceKind;
  source_ref?: string;

  installed_ts?: number; // unix seconds
  updated_ts?: number;

  tags?: string[];

  /**
   * Optional trust / verification hints (backend-defined):
   *  - signed: plugin package has signature
   *  - verified: signature validated by system trust root
   */
  signed?: boolean;
  verified?: boolean;

  capabilities?: PluginCapability[];

  meta?: Record<string, unknown>;
};

export type PluginDetail = PluginRef & {
  /**
   * Opaque manifest (backend-defined).
   * UI may render selectively (safe viewing only).
   */
  manifest?: Record<string, unknown>;

  /**
   * Optional config schema (JSON Schema-like or backend-defined).
   */
  config_schema?: unknown;

  /**
   * Optional README / docs.
   */
  readme?: string;

  /**
   * Optional file inventory (paths only, no file contents).
   */
  files?: string[];

  /**
   * Optional runtime info (backend-defined).
   */
  runtime?: Record<string, unknown>;
};

export type PluginListParams = {
  // Pagination
  limit?: number;
  offset?: number;
  cursor?: string;

  // Filtering
  status?: string;
  enabled?: boolean;
  source_kind?: string;
  tag?: string;
  tags?: string[];
  kind?: string; // capability kind, backend-dependent

  // Identity / scoping
  domain?: string;
  actor?: string;

  // Search
  search?: string;

  // Optional payload flags (backend-dependent)
  include_capabilities?: boolean;
  include_manifest?: boolean;
};

export type PluginListResponse = {
  items: PluginRef[];
  total?: number;
  next_cursor?: string;
};

export type PluginGetResponse = {
  item: PluginDetail | null;
};

export type PluginToggleRequest = {
  id: string;
  reason?: string;
  actor?: string;
  meta?: Record<string, unknown>;
};

export type PluginToggleResponse = {
  ok: boolean;
  id?: string;
  status?: PluginStatus;
  enabled?: boolean;

  approval_id?: string; // if action is approval-gated
  message?: string;
  promotion_status?: string;
  promotion_receipt_id?: string;
  promotion_receipt_path?: string;
  promotion_receipt?: PluginForgePromotion;
};

export type PluginInstallRequest = {
  /**
   * Where to install from.
   * This is intentionally generic and backend-defined.
   */
  source_kind: PluginSourceKind;

  /**
   * A backend-understood reference:
   *  - registry: "org/name" (+ optional version)
   *  - git: repo URL (+ optional ref)
   *  - url: https://.../plugin.zip
   *  - path: local path on server
   */
  source_ref: string;

  version?: string;
  ref?: string; // git ref / tag / commit
  sha256?: string; // integrity hint (optional)

  /**
   * Human justification (audit + approvals).
   */
  reason?: string;
  actor?: string;

  /**
   * If true, backend may validate/fetch but not activate/install.
   */
  dry_run?: boolean;

  /**
   * If true, backend may overwrite/update existing install (policy-dependent).
   */
  force?: boolean;

  meta?: Record<string, unknown>;
};

export type PluginInstallResponse = {
  ok: boolean;

  plugin_id?: string;
  status?: PluginStatus;
  message?: string;

  approval_id?: string; // if install is approval-gated
  operation_id?: string; // if install is queued async
};

export type PluginUninstallRequest = {
  id: string;
  reason?: string;
  actor?: string;
  force?: boolean;
  meta?: Record<string, unknown>;
};

export type PluginUninstallResponse = {
  ok: boolean;
  id?: string;
  status?: PluginStatus;
  message?: string;

  approval_id?: string;
  operation_id?: string;
};

export type PluginRunRequest = {
  id: string;

  /**
   * Action identifier (backend/plugin-defined):
   *  - could be a tool name, command name, or capability id
   */
  action: string;

  /**
   * Optional payload input (untrusted/opaque to transport layer).
   */
  input?: unknown;

  /**
   * Optional governance justification (if run requires approval).
   */
  reason?: string;

  /**
   * Optional idempotency hint.
   */
  idempotency_key?: string;
  approval_id?: string;

  meta?: Record<string, unknown>;
};

export type PluginGovernanceResult = {
  plane?: string;
  gate?: string;
  next_step?: string;
  operator_hint?: string;
  action?: string;
  risk_tier?: string;
  required_trust?: number;
  current_trust?: number;
  approval_status?: string;
};

export type PluginRunResponse = {
  ok: boolean;

  /**
   * If backend executes immediately:
   */
  output?: unknown;

  /**
   * If backend queues work:
   */
  operation_id?: string;

  /**
   * If backend gates via approvals:
   */
  approval_id?: string;

  /**
   * Optional status/error fields.
   */
  status?: string;
  error?: string;
  message?: string;
  tool_id?: string;
  governance?: PluginGovernanceResult;

  meta?: Record<string, unknown>;
};

export type PluginReloadResponse = {
  ok: boolean;
  message?: string;
};

export type PluginToolRef = {
  id: string;
  plugin_id: string;
  plugin_name?: string;
  name: string;
  action: string;
  kind?: PluginCapabilityKind;
  description?: string;
  enabled?: boolean;
  status?: PluginStatus;
  source_kind?: PluginSourceKind;
  risk_tier?: string;
  required_trust?: number;
  approvals_required?: boolean;
  input_schema?: unknown;
  output_schema?: unknown;
  tags?: string[];
  meta?: Record<string, unknown>;
};

export type PluginToolListParams = {
  limit?: number;
  offset?: number;
  plugin_id?: string;
  enabled?: boolean;
  kind?: string;
  tag?: string;
  tags?: string[];
  search?: string;
};

export type PluginToolListResponse = {
  items: PluginToolRef[];
  total?: number;
  offset?: number;
  limit?: number;
};

export type PluginToolGetResponse = {
  item: PluginToolRef | null;
};

export type PluginToolRunRequest = {
  id: string;
  input?: unknown;
  reason?: string;
  idempotency_key?: string;
  approval_id?: string;
  meta?: Record<string, unknown>;
};

export type PluginToolsExportFormat = "json" | "jsonl" | "csv";

export type PluginPromotionReadinessListParams = {
  limit?: number;
  offset?: number;
  plugin_id?: string;
  proposal_id?: string;
  status?: string;
};

export type PluginPromotionReadinessPlugin = {
  id?: string;
  name?: string;
  status?: string;
  enabled?: boolean;
  source_kind?: string;
};

export type PluginPromotionReadinessEvidence = {
  proposal_review_status?: string;
  proposal_review_receipt_id?: string;
  proposal_evidence?: unknown[];
  tests?: unknown[];
  docs?: unknown[];
  risk_tier?: string;
  validation_receipt_id?: string;
  validation_receipt_path?: string;
};

export type PluginPromotionReadinessGovernance = {
  gate?: string;
  scope?: string;
  inspection_route?: string;
  promotion_route?: string;
  promotion_authority?: boolean;
  execution_authority?: boolean;
  next_step?: string;
};

export type PluginPromotionReadinessItem = {
  kind?: string;
  plugin_id: string;
  proposal_id?: string;
  ready: boolean;
  status: string;
  missing_requirements: string[];
  requirements: Record<string, boolean>;
  plugin?: PluginPromotionReadinessPlugin;
  evidence?: PluginPromotionReadinessEvidence;
  governance?: PluginPromotionReadinessGovernance;
};

export type PluginPromotionReadinessListResponse = {
  items: PluginPromotionReadinessItem[];
  total?: number;
  offset?: number;
  limit?: number;
};

export type PluginForgeArtifactListParams = {
  limit?: number;
  offset?: number;
  id?: string;
  plugin_id?: string;
  proposal_id?: string;
  status?: string;
};

export type PluginForgeProposalReviewSummary = {
  status?: string;
  decision?: string;
  reason?: string;
  notes?: string;
  actor?: string;
  decided_ts?: number;
  receipt_id?: string;
};

export type PluginForgeProposal = {
  id: string;
  proposal_id: string;
  plugin_id?: string;
  status?: string;
  kind?: string;
  created_ts?: number;
  updated_ts?: number;
  actor?: string;
  friction?: Record<string, unknown>;
  proposed_capability?: Record<string, unknown>;
  quality_requirements?: Record<string, unknown>;
  quality_analysis?: Record<string, unknown>;
  staged_implementation?: Record<string, unknown>;
  validation?: Record<string, unknown>;
  review?: PluginForgeProposalReviewSummary;
  review_receipt_id?: string;
  relative_path?: string;
  governance?: Record<string, unknown>;
};

export type PluginForgeProposalReview = {
  id: string;
  receipt_id: string;
  proposal_id?: string;
  plugin_id?: string;
  previous_status?: string;
  status?: string;
  decision?: string;
  decided_ts?: number;
  actor?: string;
  reason?: string;
  notes?: string;
  relative_path?: string;
  governance?: Record<string, unknown>;
};

export type PluginForgeProposalDecisionAction = "approve" | "reject" | "request_changes" | string;

export type PluginForgeProposalDecisionRequest = {
  id: string;
  action: PluginForgeProposalDecisionAction;
  actor?: string;
  reason?: string;
  notes?: string;
  meta?: Record<string, unknown>;
};

export type PluginForgeProposalDecisionResponse = {
  ok: boolean;
  applied?: boolean;
  status?: string;
  error?: string;
  allowed_actions?: string[];
  proposal_id?: string;
  plugin_id?: string;
  review_receipt_id?: string;
  review_receipt?: PluginForgeProposalReview;
  item?: PluginForgeProposal;
  governance?: Record<string, unknown>;
};

export type PluginForgePromotion = {
  id: string;
  receipt_id: string;
  plugin_id?: string;
  proposal_id?: string;
  previous_status?: string;
  promoted_status?: string;
  status?: string;
  promoted_ts?: number;
  actor?: string;
  reason?: string;
  path?: string;
  artifact_path?: string;
  relative_path?: string;
  proposal_review?: Record<string, unknown>;
  proposal_evidence?: unknown[];
  quality?: Record<string, unknown>;
  promotion_context?: Record<string, unknown>;
  governance?: Record<string, unknown>;
};

export type PluginForgeProposalListResponse = {
  items: PluginForgeProposal[];
  total?: number;
  offset?: number;
  limit?: number;
};

export type PluginForgeProposalReviewListResponse = {
  items: PluginForgeProposalReview[];
  total?: number;
  offset?: number;
  limit?: number;
};

export type PluginForgePromotionListResponse = {
  items: PluginForgePromotion[];
  total?: number;
  offset?: number;
  limit?: number;
};

export type PluginCapabilityPackReviewItem = {
  capability: string;
  version?: string;
  source?: string;
  status?: string;
  risk_tier?: string;
  proposal_id?: string;
  validation_receipt_id?: string;
  promotion_receipt_id?: string;
  gaps?: string[];
};

export type PluginCapabilityPackOperatorReviewPack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  status?: string;
  operator_review_ready?: boolean;
  decision_required?: boolean;
  decision_kind?: string;
  capability_count?: number;
  staged_capability_count?: number;
  promoted_capability_count?: number;
  blockers?: string[];
  operator_review_rule_declared?: boolean;
  operator_review_governance_declared?: boolean;
  quality_evidence_ready?: boolean;
  proposal_lineage_ready?: boolean;
  validation_receipts_ready?: boolean;
  promotion_receipts_ready?: boolean;
  review_items_sample?: PluginCapabilityPackReviewItem[];
  failing_capabilities_sample?: PluginCapabilityPackReviewItem[];
};

export type PluginCapabilityPackOperatorReviewResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  pack_total?: number;
  ready_pack_count?: number;
  blocked_pack_count?: number;
  decision_required_pack_count?: number;
  review_queue_count?: number;
  pending_review_queue_count?: number;
  decision_recorded_pack_count?: number;
  packs: PluginCapabilityPackOperatorReviewPack[];
  decision_routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityPackPromotionDisciplinePack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  status?: string;
  ready?: boolean;
  capability_count?: number;
  staged_capability_count?: number;
  promoted_capability_count?: number;
  blockers?: string[];
  promotion_rules_ready?: boolean;
  pack_governance_ready?: boolean;
  quality_evidence_ready?: boolean;
  validation_receipts_ready?: boolean;
  proposal_lineage_ready?: boolean;
  promotion_receipts_ready?: boolean;
  operator_review_rule_declared?: boolean;
  operator_review_governance_declared?: boolean;
  operator_review_approved?: boolean;
  lifecycle_mixed?: boolean;
  failing_capabilities_sample?: PluginCapabilityPackReviewItem[];
};

export type PluginCapabilityPackPromotionDisciplineResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  pack_total?: number;
  ready_pack_count?: number;
  blocked_pack_count?: number;
  unpacked_entry_count?: number;
  available_proposal_count?: number;
  available_validation_receipt_count?: number;
  available_promotion_receipt_count?: number;
  approved_pack_operator_review_count?: number;
  packs: PluginCapabilityPackPromotionDisciplinePack[];
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityPackPromotionRuleRemediationItem = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  status?: string;
  ready?: boolean;
  capability_count?: number;
  blockers?: string[];
  missing_promotion_rules?: string[];
  missing_governance_fields?: string[];
  missing_quality_evidence?: string[];
  missing_receipt_evidence?: string[];
  first_action?: string;
  promotion_rules?: string[];
  failing_capabilities_sample?: PluginCapabilityPackReviewItem[];
};

export type PluginCapabilityPackPromotionRuleRemediationResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  pack_total?: number;
  ready_pack_count?: number;
  blocked_pack_count?: number;
  unpacked_entry_count?: number;
  remediation_pack_count?: number;
  remediation_queue_count?: number;
  remediation_queue_truncated?: boolean;
  missing_rule_pack_count?: number;
  missing_governance_pack_count?: number;
  missing_quality_pack_count?: number;
  missing_receipt_pack_count?: number;
  canonical_promotion_rules?: string[];
  first_action?: string;
  remediation_queue: PluginCapabilityPackPromotionRuleRemediationItem[];
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryProposalEvidenceCapability = {
  capability: string;
  status?: string;
  proposal_id?: string;
  proposal_review_status?: string;
  proposal_review_receipt_id?: string;
  proposal_evidence_ready?: boolean;
  proposal_evidence_missing?: boolean;
  proposal_evidence?: unknown[];
  linked_proposal_artifact_evidence?: unknown[];
  evidence_source?: string;
  missing_requirements?: string[];
  blockers_before_evidence?: string[];
};

export type PluginCapabilityLibraryProposalEvidencePack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  staged_capability_count?: number;
  proposal_evidence_missing_count?: number;
  proposal_evidence_ready_count?: number;
  blocked_before_evidence_count?: number;
  capabilities: PluginCapabilityLibraryProposalEvidenceCapability[];
  capabilities_truncated?: boolean;
};

export type PluginCapabilityLibraryProposalEvidencePlanResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  proposal_evidence_plan_ready?: boolean;
  pack_total?: number;
  ready_pack_count?: number;
  blocked_pack_count?: number;
  candidate_pack_count?: number;
  candidate_capability_count?: number;
  unique_proposal_count?: number;
  proposal_evidence_missing_count?: number;
  proposal_evidence_ready_count?: number;
  missing_proposal_evidence_count?: number;
  evidence_ready_proposal_count?: number;
  proposal_id_missing_count?: number;
  proposal_review_missing_count?: number;
  blocked_before_evidence_count?: number;
  missing_requirement_counts?: Record<string, number>;
  packs: PluginCapabilityLibraryProposalEvidencePack[];
  packs_truncated?: boolean;
  capability_preview_limit?: number;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryPromotionCapability = {
  capability: string;
  status?: string;
  enabled?: boolean;
  promotion_ready?: boolean;
  missing_requirements?: string[];
  proposal_id?: string;
  proposal_review_status?: string;
  proposal_review_receipt_id?: string;
  validation_receipt_id?: string;
  pack_operator_review_required?: boolean;
  pack_operator_review_status?: string;
  pack_operator_review_receipt_id?: string;
  promotion_route?: string;
  promotion_would_write_receipt?: boolean;
  promotion_would_enable_capability?: boolean;
};

export type PluginCapabilityLibraryPromotionPack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  staged_capability_count?: number;
  promotable_capability_count?: number;
  blocked_capability_count?: number;
  capabilities: PluginCapabilityLibraryPromotionCapability[];
  capabilities_truncated?: boolean;
};

export type PluginCapabilityLibraryPromotionPlanResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  promotion_plan_ready?: boolean;
  pack_total?: number;
  ready_pack_count?: number;
  blocked_pack_count?: number;
  candidate_pack_count?: number;
  candidate_capability_count?: number;
  promotable_capability_count?: number;
  blocked_capability_count?: number;
  missing_requirement_counts?: Record<string, number>;
  packs: PluginCapabilityLibraryPromotionPack[];
  packs_truncated?: boolean;
  capability_preview_limit?: number;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryProposalReviewProposal = {
  capability: string;
  status?: string;
  proposal_id?: string;
  proposal_review_status?: string;
  proposal_review_receipt_id?: string;
  proposal_review_missing?: boolean;
  review_ready?: boolean;
  approved_review?: boolean;
  missing_requirements?: string[];
  blockers_before_review?: string[];
  proposal_review_route?: string;
  proposal_review_would_write_receipt?: boolean;
  proposal_review_would_promote_capability?: boolean;
  proposal_review_would_enable_capability?: boolean;
};

export type PluginCapabilityLibraryProposalReviewPack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  staged_capability_count?: number;
  reviewable_capability_count?: number;
  blocked_before_review_capability_count?: number;
  approved_proposal_review_count?: number;
  proposals: PluginCapabilityLibraryProposalReviewProposal[];
  proposals_truncated?: boolean;
};

export type PluginCapabilityLibraryProposalReviewPlanResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  proposal_review_plan_ready?: boolean;
  pack_total?: number;
  ready_pack_count?: number;
  blocked_pack_count?: number;
  candidate_pack_count?: number;
  candidate_capability_count?: number;
  unique_proposal_count?: number;
  proposal_review_missing_count?: number;
  approved_proposal_review_count?: number;
  reviewable_capability_count?: number;
  reviewable_proposal_count?: number;
  blocked_before_review_capability_count?: number;
  blocked_proposal_count?: number;
  approved_proposal_count?: number;
  missing_requirement_counts?: Record<string, number>;
  packs: PluginCapabilityLibraryProposalReviewPack[];
  packs_truncated?: boolean;
  proposal_preview_limit?: number;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryProposalReviewApplyReadinessEvidenceSource = {
  status?: string;
  proposal_evidence_missing_count?: number;
  proposal_evidence_ready_count?: number;
  proposal_review_missing_count?: number;
  next_smallest_truthful_gap?: string;
};

export type PluginCapabilityLibraryProposalReviewApplyReadinessOperatorAudit = {
  status?: string;
  operator_evidence_intake_audit_ready?: boolean;
  recorded_pack_count?: number;
  recorded_capability_count?: number;
  evidence_ref_count?: number;
  future_review_required_count?: number;
  next_smallest_truthful_gap?: string;
};

export type PluginCapabilityLibraryProposalReviewApplyReadinessReviewSource = {
  status?: string;
  proposal_review_plan_ready?: boolean;
  candidate_capability_count?: number;
  reviewable_capability_count?: number;
  blocked_before_review_capability_count?: number;
  proposal_review_missing_count?: number;
  approved_proposal_review_count?: number;
  next_smallest_truthful_gap?: string;
};

export type PluginCapabilityLibraryProposalReviewApplyReadinessResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  proposal_review_apply_ready?: boolean;
  reviewable_pack_count?: number;
  blocked_pack_count?: number;
  reviewable_capability_count?: number;
  proposal_review_missing_count?: number;
  blocked_before_review_capability_count?: number;
  approved_proposal_review_count?: number;
  source_proposal_evidence_plan?: PluginCapabilityLibraryProposalReviewApplyReadinessEvidenceSource;
  source_operator_evidence_intake_audit?: PluginCapabilityLibraryProposalReviewApplyReadinessOperatorAudit;
  source_proposal_review_plan?: PluginCapabilityLibraryProposalReviewApplyReadinessReviewSource;
  packs: PluginCapabilityLibraryProposalReviewPack[];
  packs_truncated?: boolean;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryProposalEvidenceRemediationCapability = {
  capability: string;
  status?: string;
  proposal_id?: string;
  metadata_proposal_evidence?: unknown[];
  linked_proposal_artifact_evidence?: unknown[];
  evidence_source?: string;
  writes_registry_metadata?: boolean;
  writes_proposals?: boolean;
  approves_proposals?: boolean;
  promotes_capability?: boolean;
};

export type PluginCapabilityLibraryProposalEvidenceRemediationPack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  staged_capability_count?: number;
  candidate_capability_count?: number;
  capabilities: PluginCapabilityLibraryProposalEvidenceRemediationCapability[];
  capabilities_truncated?: boolean;
};

export type PluginCapabilityLibraryProposalEvidenceRemediationSourcePlan = {
  status?: string;
  candidate_capability_count?: number;
  proposal_evidence_missing_count?: number;
  proposal_evidence_ready_count?: number;
  proposal_review_missing_count?: number;
  next_smallest_truthful_gap?: string;
};

export type PluginCapabilityLibraryProposalEvidenceRemediationResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  proposal_evidence_remediation_ready?: boolean;
  pack_total?: number;
  ready_pack_count?: number;
  blocked_pack_count?: number;
  candidate_pack_count?: number;
  candidate_capability_count?: number;
  existing_metadata_evidence_count?: number;
  proposal_id_missing_count?: number;
  plugin_record_missing_count?: number;
  source_proposal_evidence_plan?: PluginCapabilityLibraryProposalEvidenceRemediationSourcePlan;
  packs: PluginCapabilityLibraryProposalEvidenceRemediationPack[];
  packs_truncated?: boolean;
  capability_preview_limit?: number;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefCapability = {
  capability: string;
  status?: string;
  proposal_id?: string;
  metadata_proposal_evidence?: unknown[];
  friction_summary_field?: string;
  friction_summary_ref?: string;
  friction_summary_preview?: string;
  evidence_source?: string;
  writes_registry_metadata?: boolean;
  writes_proposals?: boolean;
  approves_proposals?: boolean;
  promotes_capability?: boolean;
  requires_future_review?: boolean;
};

export type PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefPack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  staged_capability_count?: number;
  candidate_capability_count?: number;
  capabilities: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefCapability[];
  capabilities_truncated?: boolean;
};

export type PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  proposal_evidence_friction_summary_refs_ready?: boolean;
  pack_total?: number;
  ready_pack_count?: number;
  blocked_pack_count?: number;
  candidate_pack_count?: number;
  candidate_capability_count?: number;
  existing_metadata_evidence_count?: number;
  friction_summary_missing_count?: number;
  proposal_id_missing_count?: number;
  plugin_record_missing_count?: number;
  source_proposal_evidence_plan?: PluginCapabilityLibraryProposalEvidenceRemediationSourcePlan;
  packs: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefPack[];
  packs_truncated?: boolean;
  capability_preview_limit?: number;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRequest = {
  actor?: string;
  reason?: string;
  pack_ids?: string[];
  max_pack_count?: number;
  max_total_capability_count?: number;
  max_capability_count_per_pack?: number;
  dry_run?: boolean;
  meta?: Record<string, unknown>;
};

export type PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlanCapability = {
  capability: string;
  proposal_id?: string;
  friction_summary_field?: string;
  friction_summary_ref?: string;
};

export type PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlan = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  capability_count?: number;
  evidence_source?: string;
  capabilities?: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlanCapability[];
  writes_registry_metadata?: boolean;
  writes_proposals?: boolean;
  approves_proposals?: boolean;
  promotes_capabilities?: boolean;
  enables_capabilities?: boolean;
  requires_future_review?: boolean;
};

export type PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  capability_count?: number;
  changed_capability_count?: number;
  changed_capability_ids?: string[];
  changed_capability_ids_truncated?: boolean;
  evidence_source?: string;
  writes_registry_metadata?: boolean;
  writes_proposals?: boolean;
  approves_proposals?: boolean;
  promotes_capabilities?: boolean;
  enables_capabilities?: boolean;
  requires_future_review?: boolean;
  status?: string;
  error?: string;
  capabilities?: unknown[];
};

export type PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyResponse = {
  ok: boolean;
  applied?: boolean;
  kind?: string;
  status?: string;
  dry_run?: boolean;
  error?: string;
  planned_pack_count?: number;
  planned_capability_count?: number;
  recorded_pack_count?: number;
  recorded_capability_count?: number;
  candidate_total?: number;
  limit?: number;
  capability_count?: number;
  planned?: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlan[];
  recorded?: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord[];
  failed?: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord[];
  skipped?: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord[];
  before?: Record<string, unknown>;
  remaining_candidate_pack_count?: number;
  remaining_candidate_capability_count?: number;
  next_smallest_truthful_gap?: string;
  governance?: Record<string, unknown>;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistCapability = {
  capability: string;
  status?: string;
  proposal_id?: string;
  proposal_review_status?: string;
  proposal_review_receipt_id?: string;
  missing_requirements?: string[];
  blockers_before_evidence?: string[];
  evidence_refs_required?: boolean;
  operator_supplied_evidence_not_independently_verified?: boolean;
  intake_apply_route?: string;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistPack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  staged_capability_count?: number;
  candidate_capability_count?: number;
  evidence_ref_required_count?: number;
  claim_scope?: string;
  capabilities: PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistCapability[];
  capabilities_truncated?: boolean;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistSourcePlan = {
  status?: string;
  candidate_capability_count?: number;
  proposal_evidence_missing_count?: number;
  proposal_evidence_ready_count?: number;
  proposal_review_missing_count?: number;
  next_smallest_truthful_gap?: string;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  operator_evidence_intake_checklist_ready?: boolean;
  candidate_pack_count?: number;
  candidate_capability_count?: number;
  evidence_ref_required_count?: number;
  source_proposal_evidence_plan?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistSourcePlan;
  packs: PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistPack[];
  packs_truncated?: boolean;
  capability_preview_limit?: number;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPayloadHint = {
  pack_ids?: string[];
  capability_ids?: string[];
  evidence_refs?: string[];
  dry_run?: boolean;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetRow = {
  capability: string;
  status?: string;
  proposal_id?: string;
  proposal_review_status?: string;
  proposal_review_receipt_id?: string;
  missing_requirements?: string[];
  blockers_before_evidence?: string[];
  operator_evidence_refs?: string[];
  operator_evidence_ref_count?: number;
  operator_evidence_refs_required?: boolean;
  evidence_ref_collection_status?: string;
  claim_scope?: string;
  apply_payload_hint?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPayloadHint;
  operator_supplied_evidence_not_independently_verified?: boolean;
  requires_future_proposal_review?: boolean;
  intake_apply_route?: string;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  staged_capability_count?: number;
  worksheet_row_count?: number;
  evidence_ref_required_count?: number;
  claim_scope?: string;
  rows: PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetRow[];
  rows_truncated?: boolean;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetSourcePlan = {
  status?: string;
  candidate_capability_count?: number;
  proposal_evidence_missing_count?: number;
  proposal_evidence_ready_count?: number;
  proposal_review_missing_count?: number;
  next_smallest_truthful_gap?: string;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  operator_evidence_intake_worksheet_ready?: boolean;
  worksheet_pack_count?: number;
  worksheet_row_count?: number;
  evidence_ref_required_count?: number;
  source_proposal_evidence_plan?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetSourcePlan;
  packs: PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPack[];
  packs_truncated?: boolean;
  row_preview_limit?: number;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportRow = {
  pack_id?: string;
  pack_version?: string;
  pack_name?: string;
  capability: string;
  status?: string;
  proposal_id?: string;
  proposal_review_status?: string;
  proposal_review_receipt_id?: string;
  missing_requirements?: string[];
  blockers_before_evidence?: string[];
  evidence_refs_input?: string;
  evidence_refs_input_format?: string;
  operator_evidence_refs_required?: boolean;
  evidence_ref_collection_status?: string;
  claim_scope?: string;
  dry_run_required?: boolean;
  apply_payload_hint?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPayloadHint;
  operator_supplied_evidence_not_independently_verified?: boolean;
  requires_future_proposal_review?: boolean;
  intake_apply_route?: string;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportPack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  staged_capability_count?: number;
  export_row_count?: number;
  exported_row_count?: number;
  evidence_ref_required_count?: number;
  claim_scope?: string;
  rows: PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportRow[];
  rows_truncated?: boolean;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportSourcePlan = {
  status?: string;
  candidate_capability_count?: number;
  proposal_evidence_missing_count?: number;
  proposal_evidence_ready_count?: number;
  proposal_review_missing_count?: number;
  next_smallest_truthful_gap?: string;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  operator_evidence_intake_export_ready?: boolean;
  export_pack_count?: number;
  export_row_count?: number;
  exported_row_count?: number;
  evidence_ref_required_count?: number;
  export_rows_truncated?: boolean;
  row_limit?: number;
  source_proposal_evidence_plan?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportSourcePlan;
  export_schema?: Record<string, unknown>;
  packs: PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportPack[];
  packs_truncated?: boolean;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRequest = {
  actor?: string;
  rows: Array<Record<string, unknown>>;
  max_row_count?: number;
  max_apply_group_count?: number;
  meta?: Record<string, unknown>;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow = {
  row_index: number;
  pack_id?: string;
  pack_version?: string;
  capability?: string;
  proposal_id?: string;
  status?: string;
  error?: string;
  evidence_refs?: string[];
  evidence_ref_count?: number;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewGroup = {
  pack_id: string;
  pack_version?: string;
  capability_count?: number;
  evidence_ref_count?: number;
  row_indexes?: number[];
  row_indexes_truncated?: boolean;
  preview_payload?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeRequest;
  apply_payload_hint?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeRequest & {
    dry_run_fingerprint_required?: boolean;
  };
  preview_route?: string;
  apply_route?: string;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  operator_evidence_intake_import_preview_ready?: boolean;
  input_row_count?: number;
  processed_row_count?: number;
  row_input_truncated?: boolean;
  ready_row_count?: number;
  pending_row_count?: number;
  invalid_row_count?: number;
  apply_group_count?: number;
  apply_groups_truncated?: boolean;
  row_limit?: number;
  apply_group_limit?: number;
  ready_rows?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow[];
  ready_rows_truncated?: boolean;
  pending_rows?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow[];
  pending_rows_truncated?: boolean;
  invalid_rows?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow[];
  invalid_rows_truncated?: boolean;
  apply_payload_groups?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewGroup[];
  source_proposal_evidence_plan?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportSourcePlan;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditCapability = {
  capability: string;
  status?: string;
  proposal_id?: string;
  evidence_ref_count?: number;
  evidence_refs?: string[];
  evidence_refs_truncated?: boolean;
  claim_scope?: string;
  operator_intake_actor?: string;
  operator_intake_reason?: string;
  operator_intake_ts?: number;
  operator_intake_route?: string;
  operator_supplied_evidence_not_independently_verified?: boolean;
  requires_future_proposal_review?: boolean;
  writes_proposals?: boolean;
  approval_claimed?: boolean;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditPack = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  staged_capability_count?: number;
  recorded_capability_count?: number;
  evidence_ref_count?: number;
  claim_scope?: string;
  capabilities: PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditCapability[];
  capabilities_truncated?: boolean;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditSourcePlan = {
  status?: string;
  candidate_capability_count?: number;
  proposal_evidence_missing_count?: number;
  proposal_evidence_ready_count?: number;
  proposal_review_missing_count?: number;
  next_smallest_truthful_gap?: string;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  operator_evidence_intake_audit_ready?: boolean;
  recorded_pack_count?: number;
  recorded_capability_count?: number;
  evidence_ref_count?: number;
  future_review_required_count?: number;
  source_proposal_evidence_plan?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditSourcePlan;
  packs: PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditPack[];
  packs_truncated?: boolean;
  capability_preview_limit?: number;
  routes?: Record<string, string>;
  requirements?: Record<string, boolean>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  catalog?: Record<string, unknown>;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeRequest = {
  actor?: string;
  reason?: string;
  pack_ids?: string[];
  capability_ids?: string[];
  evidence_refs: string[];
  max_pack_count?: number;
  max_total_capability_count?: number;
  max_capability_count_per_pack?: number;
  dry_run?: boolean;
  dry_run_fingerprint?: string;
  meta?: Record<string, unknown>;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeCapability = {
  capability: string;
  proposal_id?: string;
  missing_requirements?: string[];
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakePlan = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  capability_count?: number;
  evidence_ref_count?: number;
  claim_scope?: string;
  capabilities?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeCapability[];
  writes_registry_metadata?: boolean;
  writes_proposals?: boolean;
  approves_proposals?: boolean;
  promotes_capabilities?: boolean;
  enables_capabilities?: boolean;
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeRecord = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  capability_count?: number;
  changed_capability_count?: number;
  changed_capability_ids?: string[];
  changed_capability_ids_truncated?: boolean;
  evidence_ref_count?: number;
  claim_scope?: string;
  writes_registry_metadata?: boolean;
  writes_proposals?: boolean;
  approves_proposals?: boolean;
  promotes_capabilities?: boolean;
  enables_capabilities?: boolean;
  status?: string;
  error?: string;
  capabilities?: unknown[];
};

export type PluginCapabilityLibraryOperatorProposalEvidenceIntakeResponse = {
  ok: boolean;
  applied?: boolean;
  kind?: string;
  status?: string;
  dry_run?: boolean;
  error?: string;
  planned_pack_count?: number;
  planned_capability_count?: number;
  evidence_ref_count?: number;
  recorded_pack_count?: number;
  recorded_capability_count?: number;
  candidate_total?: number;
  limit?: number;
  capability_count?: number;
  dry_run_fingerprint?: string;
  dry_run_confirmation?: Record<string, unknown>;
  planned?: PluginCapabilityLibraryOperatorProposalEvidenceIntakePlan[];
  recorded?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeRecord[];
  failed?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeRecord[];
  skipped?: PluginCapabilityLibraryOperatorProposalEvidenceIntakeRecord[];
  before?: Record<string, unknown>;
  remaining_proposal_evidence_missing_count?: number;
  remaining_proposal_evidence_ready_count?: number;
  next_smallest_truthful_gap?: string;
  governance?: Record<string, unknown>;
};

export type PluginCapabilityPackOperatorReviewDecision = {
  id: string;
  receipt_id: string;
  status?: string;
  decision?: string;
  pack_id?: string;
  pack_version?: string;
  pack_name?: string;
  capability_ids?: string[];
  capability_count?: number;
  staged_capability_count?: number;
  actor?: string;
  reason?: string;
  notes?: string;
  decided_ts?: number;
  path?: string;
  relative_path?: string;
  review_snapshot?: Record<string, unknown>;
  governance?: Record<string, unknown>;
};

export type PluginCapabilityPackOperatorReviewDecisionListParams = {
  limit?: number;
  pack_id?: string;
  pack_version?: string;
};

export type PluginCapabilityPackOperatorReviewDecisionListResponse = {
  ok: boolean;
  kind?: string;
  stage?: string;
  items: PluginCapabilityPackOperatorReviewDecision[];
  total?: number;
  limit?: number;
  governance?: Record<string, unknown>;
  write_route?: string;
};

export type PluginCapabilityPackOperatorReviewDecisionAction = "approve" | "reject" | "request_changes" | string;

export type PluginCapabilityPackOperatorReviewDecisionRequest = {
  pack_id: string;
  pack_version: string;
  action: PluginCapabilityPackOperatorReviewDecisionAction;
  actor?: string;
  reason?: string;
  notes?: string;
  capability_ids?: string[];
  meta?: Record<string, unknown>;
};

export type PluginCapabilityPackOperatorReviewDecisionResponse = {
  ok: boolean;
  applied?: boolean;
  status?: string;
  error?: string;
  allowed_actions?: string[];
  pack_id?: string;
  pack_version?: string;
  receipt_id?: string;
  receipt_path?: string;
  receipt?: PluginCapabilityPackOperatorReviewDecision;
  pack?: PluginCapabilityPackOperatorReviewPack;
  governance?: Record<string, unknown>;
};

export type PluginCapabilityPackOperatorReviewBulkDecisionRequest = {
  action: PluginCapabilityPackOperatorReviewDecisionAction;
  actor?: string;
  reason?: string;
  notes?: string;
  pack_ids?: string[];
  max_pack_count?: number;
  max_total_capability_count?: number;
  dry_run?: boolean;
  meta?: Record<string, unknown>;
};

export type PluginCapabilityPackOperatorReviewBulkDecisionPlan = {
  pack_id: string;
  pack_version: string;
  pack_name?: string;
  action?: string;
  decision_status?: string;
  capability_count?: number;
  staged_capability_count?: number;
  quality_evidence_ready?: boolean;
  proposal_lineage_ready?: boolean;
  validation_receipts_ready?: boolean;
  operator_review_rule_declared?: boolean;
  operator_review_governance_declared?: boolean;
  writes_receipt?: boolean;
};

export type PluginCapabilityPackOperatorReviewBulkDecisionRecord = {
  pack_id: string;
  pack_version: string;
  receipt_id?: string;
  receipt_path?: string;
  capability_count?: number;
  status?: string;
  error?: string;
};

export type PluginCapabilityPackOperatorReviewBulkDecisionResponse = {
  ok: boolean;
  applied?: boolean;
  kind?: string;
  status?: string;
  dry_run?: boolean;
  error?: string;
  allowed_actions?: string[];
  batch_id?: string;
  planned_pack_count?: number;
  planned_capability_count?: number;
  recorded_pack_count?: number;
  recorded_capability_count?: number;
  planned?: PluginCapabilityPackOperatorReviewBulkDecisionPlan[];
  recorded?: PluginCapabilityPackOperatorReviewBulkDecisionRecord[];
  failed?: PluginCapabilityPackOperatorReviewBulkDecisionRecord[];
  skipped?: PluginCapabilityPackOperatorReviewBulkDecisionRecord[];
  before?: Record<string, unknown>;
  promotion_discipline?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
  governance?: Record<string, unknown>;
};

export type PluginCapabilityCatalogParams = {
  limit?: number;
  offset?: number;
  status?: string;
  risk_tier?: string;
  source?: string;
};

export type PluginCapabilityCatalogQuality = {
  tests?: string[];
  docs?: string[];
};

export type PluginCapabilityCatalogEntry = {
  capability: string;
  version?: string;
  status?: string;
  risk_tier?: string;
  source?: string;
  price?: number;
  proposal_id?: string;
  promotion_receipt_id?: string;
  quality?: PluginCapabilityCatalogQuality;
  metadata?: Record<string, unknown>;
};

export type PluginCapabilityCatalogSummary = {
  total?: number;
  status_counts?: Record<string, number>;
  risk_tier_counts?: Record<string, number>;
  source_counts?: Record<string, number>;
  tested_count?: number;
  documented_count?: number;
};

export type PluginCapabilityCatalogCoherence = {
  total?: number;
  duplicate_capabilities?: unknown[];
  duplicate_proposals?: unknown[];
  lineage_gaps?: unknown[];
  validation_lineage_gaps?: unknown[];
  quality_gaps?: unknown[];
};

export type PluginCapabilityCatalogResponse = {
  items: PluginCapabilityCatalogEntry[];
  total?: number;
  offset?: number;
  limit?: number;
  summary?: PluginCapabilityCatalogSummary;
  coherence?: PluginCapabilityCatalogCoherence;
  catalog?: Record<string, unknown>;
  filters?: Record<string, string>;
};

/* -------------------------------------------------------------------------------------------------
 * Errors
 * ------------------------------------------------------------------------------------------------- */

export class PluginBrowserApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly requestId?: string;
  readonly bodySnippet?: string;
  readonly timedOut?: boolean;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; requestId?: string; bodySnippet?: string; timedOut?: boolean; cause?: unknown },
  ) {
    super(message);
    this.name = "PluginBrowserApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.requestId = opts?.requestId;
    this.bodySnippet = opts?.bodySnippet;
    this.timedOut = opts?.timedOut;
    // @ts-expect-error - Error.cause not always in TS lib target
    this.cause = opts?.cause;
  }
}

/* -------------------------------------------------------------------------------------------------
 * Utilities (tiny, dependency-free)
 * ------------------------------------------------------------------------------------------------- */

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function pluginMutationActor(actor?: string): string {
  return actor?.trim() || DEFAULT_PLUGIN_MUTATION_ACTOR;
}

function assertPluginMutationAllowed(json: unknown, fallback: string, url: string): void {
  if (!isRecord(json)) return;
  const status = safeString(json.status, "");
  const error = safeString(json.error, "");
  if (status === "denied" || error === "api_permission_denied") {
    throw new PluginBrowserApiError(error || safeString(json.message, "") || fallback, { url });
  }
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function safeBool(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function safeStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out = v.map((x) => (typeof x === "string" ? x : "")).filter((s) => s.length > 0);
  return out.length ? out : undefined;
}

function safeUnknownArray(v: unknown): unknown[] | undefined {
  return Array.isArray(v) ? v : undefined;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function normalizeUnixSeconds(ts: unknown): number | undefined {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return undefined;
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : Math.floor(ts);
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

/**
 * Deterministic lightweight hash for synthesizing ids if backend omits them.
 * Not cryptographic; used only for stable UI keys.
 */
function fnv1a32(input: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h >>> 0;
}

function synthId(parts: Array<string | number | undefined>): string {
  const seed = parts.map((p) => (p === undefined ? "" : String(p))).join("|");
  return `pl_${fnv1a32(seed).toString(36)}`;
}

function headerRequestId(headers: Headers): string | undefined {
  const keys = ["x-request-id", "x-correlation-id", "x-trace-id", "request-id"];
  for (const k of keys) {
    const v = headers.get(k);
    if (v && v.trim()) return v.trim();
  }
  return undefined;
}

function encodeQuery(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();

  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;

    if (Array.isArray(v)) {
      for (const item of v) {
        if (item === undefined || item === null) continue;
        const s = String(item).trim();
        if (s) sp.append(k, s);
      }
      continue;
    }

    if (typeof v === "boolean") {
      sp.set(k, v ? "1" : "0");
      continue;
    }

    const s = String(v).trim();
    if (s) sp.set(k, s);
  }

  const qs = sp.toString();
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

function backoffMs(attempt: number, base = 250, cap = 5_000): number {
  const pow = 2 ** clamp(attempt, 0, 10);
  const raw = clamp(base * pow, base, cap);
  const jitter = Math.floor(Math.random() * clamp(raw * 0.2, 25, 500));
  return raw + jitter;
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return;
  await new Promise<void>((resolve, reject) => {
    const t = window.setTimeout(() => {
      cleanup();
      resolve();
    }, ms);

    const onAbort = () => {
      cleanup();
      reject(new DOMException("Aborted", "AbortError"));
    };

    const cleanup = () => {
      window.clearTimeout(t);
      if (signal) signal.removeEventListener("abort", onAbort);
    };

    if (signal) {
      if (signal.aborted) {
        cleanup();
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

/* -------------------------------------------------------------------------------------------------
 * Parsing (defensive + alias tolerant)
 * ------------------------------------------------------------------------------------------------- */

function parseCapability(raw: unknown): PluginCapability | null {
  if (!isRecord(raw)) return null;

  const kind = safeString(raw.kind, safeString(raw.type, ""));
  const name = safeString(raw.name, safeString(raw.id, ""));
  if (!kind || !name) return null;

  const c: PluginCapability = {
    kind,
    name,
  };

  const id = safeString(raw.id, "");
  if (id) c.id = id;

  const desc = safeString(raw.description, "");
  if (desc) c.description = desc;

  if ("input_schema" in raw) c.input_schema = raw.input_schema;
  else if ("inputSchema" in raw) c.input_schema = (raw as Record<string, unknown>).inputSchema;

  if ("output_schema" in raw) c.output_schema = raw.output_schema;
  else if ("outputSchema" in raw) c.output_schema = (raw as Record<string, unknown>).outputSchema;

  if (isRecord(raw.meta)) c.meta = raw.meta;

  return c;
}

function statusFromBooleans(raw: Record<string, unknown>): { status?: PluginStatus; enabled?: boolean } {
  const enabled =
    typeof raw.enabled === "boolean"
      ? raw.enabled
      : typeof raw.is_enabled === "boolean"
        ? raw.is_enabled
        : typeof raw.isEnabled === "boolean"
          ? raw.isEnabled
          : undefined;

  if (enabled === undefined) return {};

  return {
    enabled,
    status: enabled ? "enabled" : "disabled",
  };
}

function parsePluginRef(raw: unknown): PluginRef | null {
  if (!isRecord(raw)) return null;

  const id =
    safeString(raw.id) ||
    safeString(raw.plugin_id) ||
    safeString(raw.pluginId) ||
    safeString(raw.slug) ||
    safeString(raw.name) ||
    "";

  const name = safeString(raw.name, safeString(raw.title, id));
  if (!id || !name) return null;

  const status = safeString(raw.status, safeString(raw.state, ""));
  const boolStatus = statusFromBooleans(raw);

  const installedTs =
    normalizeUnixSeconds(raw.installed_ts) ??
    normalizeUnixSeconds(raw.installedAt) ??
    normalizeUnixSeconds(raw.created_ts) ??
    undefined;

  const updatedTs =
    normalizeUnixSeconds(raw.updated_ts) ??
    normalizeUnixSeconds(raw.updatedAt) ??
    normalizeUnixSeconds(raw.modified_ts) ??
    undefined;

  const ref: PluginRef = {
    id: id || synthId([name, installedTs, status]),
    name,
  };

  const version = safeString(raw.version, "");
  if (version) ref.version = version;

  const effectiveStatus = status || boolStatus.status;
  if (effectiveStatus) ref.status = effectiveStatus;

  if (typeof boolStatus.enabled === "boolean") ref.enabled = boolStatus.enabled;
  else if (typeof raw.enabled === "boolean") ref.enabled = raw.enabled;

  const desc = safeString(raw.description, safeString(raw.summary, ""));
  if (desc) ref.description = desc;

  const author = safeString(raw.author, "");
  if (author) ref.author = author;

  const homepage = safeString(raw.homepage, safeString(raw.url, ""));
  if (homepage) ref.homepage = homepage;

  const license = safeString(raw.license, "");
  if (license) ref.license = license;

  const sourceKind = safeString(raw.source_kind, safeString(raw.sourceKind, safeString(raw.source, "")));
  if (sourceKind) ref.source_kind = sourceKind;

  const sourceRef = safeString(raw.source_ref, safeString(raw.sourceRef, safeString(raw.ref, "")));
  if (sourceRef) ref.source_ref = sourceRef;

  if (installedTs !== undefined) ref.installed_ts = installedTs;
  if (updatedTs !== undefined) ref.updated_ts = updatedTs;

  const tags = safeStringArray(raw.tags);
  if (tags) ref.tags = tags;

  const signed = typeof raw.signed === "boolean" ? raw.signed : undefined;
  if (signed !== undefined) ref.signed = signed;

  const verified = typeof raw.verified === "boolean" ? raw.verified : undefined;
  if (verified !== undefined) ref.verified = verified;

  const capsRaw =
    Array.isArray(raw.capabilities) ? raw.capabilities :
    Array.isArray(raw.tools) ? raw.tools :
    Array.isArray(raw.commands) ? raw.commands :
    undefined;

  if (capsRaw) {
    const caps = capsRaw.map(parseCapability).filter((x): x is PluginCapability => x !== null);
    if (caps.length) ref.capabilities = caps;
  }

  if (isRecord(raw.meta)) ref.meta = raw.meta;

  return ref;
}

function parsePluginDetail(raw: unknown): PluginDetail | null {
  const base = parsePluginRef(raw);
  if (!base) return null;

  const r = raw as Record<string, unknown>;
  const detail: PluginDetail = { ...base };

  // Optional manifest
  const manifest =
    isRecord(r.manifest) ? (r.manifest as Record<string, unknown>) :
    isRecord(r.plugin_manifest) ? (r.plugin_manifest as Record<string, unknown>) :
    isRecord(r.pluginManifest) ? (r.pluginManifest as Record<string, unknown>) :
    undefined;

  if (manifest) detail.manifest = manifest;

  // Optional config schema
  if ("config_schema" in r) detail.config_schema = r.config_schema;
  else if ("configSchema" in r) detail.config_schema = r.configSchema;

  // Optional readme
  const readme = safeString(r.readme, safeString(r.README, ""));
  if (readme) detail.readme = readme;

  // Optional files list
  const filesRaw = Array.isArray(r.files) ? r.files : Array.isArray(r.file_paths) ? r.file_paths : undefined;
  if (filesRaw) {
    const files = filesRaw.map((x) => (typeof x === "string" ? x : "")).filter((s) => s.length > 0);
    if (files.length) detail.files = files;
  }

  // Optional runtime info
  if (isRecord(r.runtime)) detail.runtime = r.runtime;

  return detail;
}

function parsePluginTool(raw: unknown): PluginToolRef | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, "");
  const pluginId = safeString(raw.plugin_id, safeString(raw.pluginId, ""));
  const name = safeString(raw.name, safeString(raw.title, ""));
  const action = safeString(raw.action, safeString(raw.command, name));
  if (!id || !pluginId || !name || !action) return null;

  const out: PluginToolRef = {
    id,
    plugin_id: pluginId,
    name,
    action,
  };

  const pluginName = safeString(raw.plugin_name, safeString(raw.pluginName, ""));
  if (pluginName) out.plugin_name = pluginName;

  const kind = safeString(raw.kind, safeString(raw.type, ""));
  if (kind) out.kind = kind;

  const description = safeString(raw.description, "");
  if (description) out.description = description;

  if (typeof raw.enabled === "boolean") out.enabled = raw.enabled;

  const status = safeString(raw.status, "");
  if (status) out.status = status;

  const sourceKind = safeString(raw.source_kind, safeString(raw.sourceKind, ""));
  if (sourceKind) out.source_kind = sourceKind;

  const riskTier = safeString(raw.risk_tier, safeString(raw.riskTier, ""));
  if (riskTier) out.risk_tier = riskTier;
  if (typeof raw.required_trust === "number" && Number.isFinite(raw.required_trust)) {
    out.required_trust = raw.required_trust;
  }
  if (typeof raw.approvals_required === "boolean") out.approvals_required = raw.approvals_required;

  if ("input_schema" in raw) out.input_schema = raw.input_schema;
  else if ("inputSchema" in raw) out.input_schema = (raw as Record<string, unknown>).inputSchema;

  if ("output_schema" in raw) out.output_schema = raw.output_schema;
  else if ("outputSchema" in raw) out.output_schema = (raw as Record<string, unknown>).outputSchema;

  const tags = safeStringArray(raw.tags);
  if (tags) out.tags = tags;

  if (isRecord(raw.meta)) out.meta = raw.meta;

  return out;
}

function parsePromotionReadinessItem(raw: unknown): PluginPromotionReadinessItem | null {
  if (!isRecord(raw)) return null;

  const pluginRaw = isRecord(raw.plugin) ? raw.plugin : {};
  const pluginId = safeString(raw.plugin_id, safeString(pluginRaw.id, "")).trim();
  if (!pluginId) return null;

  const ready = safeBool(raw.ready, false);
  const status = safeString(raw.status, ready ? "ready" : "blocked") || (ready ? "ready" : "blocked");

  const requirements: Record<string, boolean> = {};
  if (isRecord(raw.requirements)) {
    for (const [key, value] of Object.entries(raw.requirements)) {
      if (typeof value === "boolean") requirements[key] = value;
    }
  }

  const item: PluginPromotionReadinessItem = {
    plugin_id: pluginId,
    ready,
    status,
    missing_requirements: safeStringArray(raw.missing_requirements) ?? [],
    requirements,
  };

  const kind = safeString(raw.kind, "");
  if (kind) item.kind = kind;

  const proposalId = safeString(raw.proposal_id, "");
  if (proposalId) item.proposal_id = proposalId;

  const plugin: PluginPromotionReadinessPlugin = {};
  const pluginName = safeString(pluginRaw.name, "");
  const pluginStatus = safeString(pluginRaw.status, "");
  const sourceKind = safeString(pluginRaw.source_kind, safeString(pluginRaw.sourceKind, ""));
  if (safeString(pluginRaw.id, "")) plugin.id = safeString(pluginRaw.id, "");
  if (pluginName) plugin.name = pluginName;
  if (pluginStatus) plugin.status = pluginStatus;
  if (typeof pluginRaw.enabled === "boolean") plugin.enabled = pluginRaw.enabled;
  if (sourceKind) plugin.source_kind = sourceKind;
  if (Object.keys(plugin).length > 0) item.plugin = plugin;

  const evidenceRaw = isRecord(raw.evidence) ? raw.evidence : {};
  const evidence: PluginPromotionReadinessEvidence = {};
  const reviewStatus = safeString(evidenceRaw.proposal_review_status, "");
  const reviewReceiptId = safeString(evidenceRaw.proposal_review_receipt_id, "");
  const riskTier = safeString(evidenceRaw.risk_tier, "");
  const validationReceiptId = safeString(evidenceRaw.validation_receipt_id, "");
  const validationReceiptPath = safeString(evidenceRaw.validation_receipt_path, "");
  const proposalEvidence = safeUnknownArray(evidenceRaw.proposal_evidence);
  const tests = safeUnknownArray(evidenceRaw.tests);
  const docs = safeUnknownArray(evidenceRaw.docs);
  if (reviewStatus) evidence.proposal_review_status = reviewStatus;
  if (reviewReceiptId) evidence.proposal_review_receipt_id = reviewReceiptId;
  if (proposalEvidence) evidence.proposal_evidence = proposalEvidence;
  if (tests) evidence.tests = tests;
  if (docs) evidence.docs = docs;
  if (riskTier) evidence.risk_tier = riskTier;
  if (validationReceiptId) evidence.validation_receipt_id = validationReceiptId;
  if (validationReceiptPath) evidence.validation_receipt_path = validationReceiptPath;
  if (Object.keys(evidence).length > 0) item.evidence = evidence;

  const governanceRaw = isRecord(raw.governance) ? raw.governance : {};
  const governance: PluginPromotionReadinessGovernance = {};
  const gate = safeString(governanceRaw.gate, "");
  const scope = safeString(governanceRaw.scope, "");
  const inspectionRoute = safeString(governanceRaw.inspection_route, "");
  const promotionRoute = safeString(governanceRaw.promotion_route, "");
  const nextStep = safeString(governanceRaw.next_step, "");
  if (gate) governance.gate = gate;
  if (scope) governance.scope = scope;
  if (inspectionRoute) governance.inspection_route = inspectionRoute;
  if (promotionRoute) governance.promotion_route = promotionRoute;
  if (typeof governanceRaw.promotion_authority === "boolean") {
    governance.promotion_authority = governanceRaw.promotion_authority;
  }
  if (typeof governanceRaw.execution_authority === "boolean") {
    governance.execution_authority = governanceRaw.execution_authority;
  }
  if (nextStep) governance.next_step = nextStep;
  if (Object.keys(governance).length > 0) item.governance = governance;

  return item;
}

function parseProposalReviewSummary(raw: unknown): PluginForgeProposalReviewSummary | undefined {
  if (!isRecord(raw)) return undefined;

  const summary: PluginForgeProposalReviewSummary = {};
  const status = safeString(raw.status, "");
  const decision = safeString(raw.decision, "");
  const reason = safeString(raw.reason, "");
  const notes = safeString(raw.notes, "");
  const actor = safeString(raw.actor, "");
  const receiptId = safeString(raw.receipt_id, safeString(raw.receiptId, ""));
  const decidedTs = normalizeUnixSeconds(raw.decided_ts) ?? normalizeUnixSeconds(raw.decidedAt);
  if (status) summary.status = status;
  if (decision) summary.decision = decision;
  if (reason) summary.reason = reason;
  if (notes) summary.notes = notes;
  if (actor) summary.actor = actor;
  if (decidedTs !== undefined) summary.decided_ts = decidedTs;
  if (receiptId) summary.receipt_id = receiptId;
  return Object.keys(summary).length > 0 ? summary : undefined;
}

function parseForgeProposal(raw: unknown): PluginForgeProposal | null {
  if (!isRecord(raw)) return null;

  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, safeString(raw.id, ""))).trim();
  if (!proposalId) return null;

  const item: PluginForgeProposal = {
    id: safeString(raw.id, proposalId) || proposalId,
    proposal_id: proposalId,
  };

  const pluginId = safeString(raw.plugin_id, safeString(raw.pluginId, ""));
  const status = safeString(raw.status, "");
  const kind = safeString(raw.kind, "");
  const actor = safeString(raw.actor, "");
  const reviewReceiptId = safeString(raw.review_receipt_id, safeString(raw.reviewReceiptId, ""));
  const relativePath = safeString(raw.relative_path, safeString(raw.relativePath, ""));
  const createdTs = normalizeUnixSeconds(raw.created_ts) ?? normalizeUnixSeconds(raw.createdAt);
  const updatedTs = normalizeUnixSeconds(raw.updated_ts) ?? normalizeUnixSeconds(raw.updatedAt);
  if (pluginId) item.plugin_id = pluginId;
  if (status) item.status = status;
  if (kind) item.kind = kind;
  if (actor) item.actor = actor;
  if (createdTs !== undefined) item.created_ts = createdTs;
  if (updatedTs !== undefined) item.updated_ts = updatedTs;
  if (isRecord(raw.friction)) item.friction = raw.friction;
  if (isRecord(raw.proposed_capability)) item.proposed_capability = raw.proposed_capability;
  else if (isRecord(raw.proposedCapability)) item.proposed_capability = raw.proposedCapability;
  if (isRecord(raw.quality_requirements)) item.quality_requirements = raw.quality_requirements;
  else if (isRecord(raw.qualityRequirements)) item.quality_requirements = raw.qualityRequirements;
  if (isRecord(raw.quality_analysis)) item.quality_analysis = raw.quality_analysis;
  else if (isRecord(raw.qualityAnalysis)) item.quality_analysis = raw.qualityAnalysis;
  if (isRecord(raw.staged_implementation)) item.staged_implementation = raw.staged_implementation;
  else if (isRecord(raw.stagedImplementation)) item.staged_implementation = raw.stagedImplementation;
  if (isRecord(raw.validation)) item.validation = raw.validation;
  const review = parseProposalReviewSummary(raw.review);
  if (review) item.review = review;
  if (reviewReceiptId) item.review_receipt_id = reviewReceiptId;
  if (relativePath) item.relative_path = relativePath;
  if (isRecord(raw.governance)) item.governance = raw.governance;

  return item;
}

function parseForgeProposalReview(raw: unknown): PluginForgeProposalReview | null {
  if (!isRecord(raw)) return null;

  const receiptId = safeString(raw.receipt_id, safeString(raw.receiptId, safeString(raw.id, ""))).trim();
  if (!receiptId) return null;

  const item: PluginForgeProposalReview = {
    id: safeString(raw.id, receiptId) || receiptId,
    receipt_id: receiptId,
  };

  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const pluginId = safeString(raw.plugin_id, safeString(raw.pluginId, ""));
  const previousStatus = safeString(raw.previous_status, safeString(raw.previousStatus, ""));
  const status = safeString(raw.status, "");
  const decision = safeString(raw.decision, "");
  const actor = safeString(raw.actor, "");
  const reason = safeString(raw.reason, "");
  const notes = safeString(raw.notes, "");
  const relativePath = safeString(raw.relative_path, safeString(raw.relativePath, ""));
  const decidedTs = normalizeUnixSeconds(raw.decided_ts) ?? normalizeUnixSeconds(raw.decidedAt);
  if (proposalId) item.proposal_id = proposalId;
  if (pluginId) item.plugin_id = pluginId;
  if (previousStatus) item.previous_status = previousStatus;
  if (status) item.status = status;
  if (decision) item.decision = decision;
  if (decidedTs !== undefined) item.decided_ts = decidedTs;
  if (actor) item.actor = actor;
  if (reason) item.reason = reason;
  if (notes) item.notes = notes;
  if (relativePath) item.relative_path = relativePath;
  if (isRecord(raw.governance)) item.governance = raw.governance;

  return item;
}

function parseForgePromotion(raw: unknown): PluginForgePromotion | null {
  if (!isRecord(raw)) return null;

  const receiptId = safeString(raw.receipt_id, safeString(raw.receiptId, safeString(raw.id, ""))).trim();
  if (!receiptId) return null;

  const item: PluginForgePromotion = {
    id: safeString(raw.id, receiptId) || receiptId,
    receipt_id: receiptId,
  };

  const pluginId = safeString(raw.plugin_id, safeString(raw.pluginId, ""));
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const previousStatus = safeString(raw.previous_status, safeString(raw.previousStatus, ""));
  const promotedStatus = safeString(raw.promoted_status, safeString(raw.promotedStatus, ""));
  const status = safeString(raw.status, "");
  const actor = safeString(raw.actor, "");
  const reason = safeString(raw.reason, "");
  const path = safeString(raw.path, "");
  const artifactPath = safeString(raw.artifact_path, safeString(raw.artifactPath, ""));
  const relativePath = safeString(raw.relative_path, safeString(raw.relativePath, ""));
  const promotedTs = normalizeUnixSeconds(raw.promoted_ts) ?? normalizeUnixSeconds(raw.promotedAt);
  const proposalEvidence = safeUnknownArray(raw.proposal_evidence);
  if (pluginId) item.plugin_id = pluginId;
  if (proposalId) item.proposal_id = proposalId;
  if (previousStatus) item.previous_status = previousStatus;
  if (promotedStatus) item.promoted_status = promotedStatus;
  if (status) item.status = status;
  if (promotedTs !== undefined) item.promoted_ts = promotedTs;
  if (actor) item.actor = actor;
  if (reason) item.reason = reason;
  if (path) item.path = path;
  if (artifactPath) item.artifact_path = artifactPath;
  if (relativePath) item.relative_path = relativePath;
  if (isRecord(raw.proposal_review)) item.proposal_review = raw.proposal_review;
  else if (isRecord(raw.proposalReview)) item.proposal_review = raw.proposalReview;
  if (proposalEvidence) item.proposal_evidence = proposalEvidence;
  if (isRecord(raw.quality)) item.quality = raw.quality;
  if (isRecord(raw.promotion_context)) item.promotion_context = raw.promotion_context;
  else if (isRecord(raw.promotionContext)) item.promotion_context = raw.promotionContext;
  if (isRecord(raw.governance)) item.governance = raw.governance;

  return item;
}

function parseCapabilityPackReviewItem(raw: unknown): PluginCapabilityPackReviewItem | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityPackReviewItem = { capability };
  const version = safeString(raw.version, "");
  const source = safeString(raw.source, "");
  const status = safeString(raw.status, "");
  const riskTier = safeString(raw.risk_tier, safeString(raw.riskTier, ""));
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const validationReceiptId = safeString(raw.validation_receipt_id, safeString(raw.validationReceiptId, ""));
  const promotionReceiptId = safeString(raw.promotion_receipt_id, safeString(raw.promotionReceiptId, ""));
  const gaps = safeStringArray(raw.gaps);
  if (version) item.version = version;
  if (source) item.source = source;
  if (status) item.status = status;
  if (riskTier) item.risk_tier = riskTier;
  if (proposalId) item.proposal_id = proposalId;
  if (validationReceiptId) item.validation_receipt_id = validationReceiptId;
  if (promotionReceiptId) item.promotion_receipt_id = promotionReceiptId;
  if (gaps) item.gaps = gaps;
  return item;
}

function parseCapabilityPackOperatorReviewPack(raw: unknown): PluginCapabilityPackOperatorReviewPack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const pack: PluginCapabilityPackOperatorReviewPack = {
    pack_id: packId,
    pack_version: packVersion,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const status = safeString(raw.status, "");
  const decisionKind = safeString(raw.decision_kind, safeString(raw.decisionKind, ""));
  const blockers = safeStringArray(raw.blockers);
  const reviewItems = safeUnknownArray(raw.review_items_sample)
    ?.map(parseCapabilityPackReviewItem)
    .filter((item): item is PluginCapabilityPackReviewItem => item !== null);
  const failingItems = safeUnknownArray(raw.failing_capabilities_sample)
    ?.map(parseCapabilityPackReviewItem)
    .filter((item): item is PluginCapabilityPackReviewItem => item !== null);
  if (packName) pack.pack_name = packName;
  if (status) pack.status = status;
  if (typeof raw.operator_review_ready === "boolean") pack.operator_review_ready = raw.operator_review_ready;
  if (typeof raw.decision_required === "boolean") pack.decision_required = raw.decision_required;
  if (decisionKind) pack.decision_kind = decisionKind;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) pack.capability_count = safeNumber(raw.capability_count);
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    pack.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.promoted_capability_count, NaN))) {
    pack.promoted_capability_count = safeNumber(raw.promoted_capability_count);
  }
  if (blockers) pack.blockers = blockers;
  if (typeof raw.operator_review_rule_declared === "boolean") {
    pack.operator_review_rule_declared = raw.operator_review_rule_declared;
  }
  if (typeof raw.operator_review_governance_declared === "boolean") {
    pack.operator_review_governance_declared = raw.operator_review_governance_declared;
  }
  if (typeof raw.quality_evidence_ready === "boolean") pack.quality_evidence_ready = raw.quality_evidence_ready;
  if (typeof raw.proposal_lineage_ready === "boolean") pack.proposal_lineage_ready = raw.proposal_lineage_ready;
  if (typeof raw.validation_receipts_ready === "boolean") pack.validation_receipts_ready = raw.validation_receipts_ready;
  if (typeof raw.promotion_receipts_ready === "boolean") pack.promotion_receipts_ready = raw.promotion_receipts_ready;
  if (reviewItems) pack.review_items_sample = reviewItems;
  if (failingItems) pack.failing_capabilities_sample = failingItems;
  return pack;
}

function parseCapabilityPackPromotionDisciplinePack(raw: unknown): PluginCapabilityPackPromotionDisciplinePack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const pack: PluginCapabilityPackPromotionDisciplinePack = {
    pack_id: packId,
    pack_version: packVersion,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const status = safeString(raw.status, "");
  const blockers = safeStringArray(raw.blockers);
  const failingItems = safeUnknownArray(raw.failing_capabilities_sample)
    ?.map(parseCapabilityPackReviewItem)
    .filter((item): item is PluginCapabilityPackReviewItem => item !== null);
  if (packName) pack.pack_name = packName;
  if (status) pack.status = status;
  if (typeof raw.ready === "boolean") pack.ready = raw.ready;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) pack.capability_count = safeNumber(raw.capability_count);
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    pack.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.promoted_capability_count, NaN))) {
    pack.promoted_capability_count = safeNumber(raw.promoted_capability_count);
  }
  if (blockers) pack.blockers = blockers;
  if (typeof raw.promotion_rules_ready === "boolean") pack.promotion_rules_ready = raw.promotion_rules_ready;
  if (typeof raw.pack_governance_ready === "boolean") pack.pack_governance_ready = raw.pack_governance_ready;
  if (typeof raw.quality_evidence_ready === "boolean") pack.quality_evidence_ready = raw.quality_evidence_ready;
  if (typeof raw.validation_receipts_ready === "boolean") pack.validation_receipts_ready = raw.validation_receipts_ready;
  if (typeof raw.proposal_lineage_ready === "boolean") pack.proposal_lineage_ready = raw.proposal_lineage_ready;
  if (typeof raw.promotion_receipts_ready === "boolean") pack.promotion_receipts_ready = raw.promotion_receipts_ready;
  if (typeof raw.operator_review_rule_declared === "boolean") {
    pack.operator_review_rule_declared = raw.operator_review_rule_declared;
  }
  if (typeof raw.operator_review_governance_declared === "boolean") {
    pack.operator_review_governance_declared = raw.operator_review_governance_declared;
  }
  if (typeof raw.operator_review_approved === "boolean") pack.operator_review_approved = raw.operator_review_approved;
  if (typeof raw.lifecycle_mixed === "boolean") pack.lifecycle_mixed = raw.lifecycle_mixed;
  if (failingItems) pack.failing_capabilities_sample = failingItems;
  return pack;
}

function parseCapabilityPackPromotionRuleRemediationItem(
  raw: unknown,
): PluginCapabilityPackPromotionRuleRemediationItem | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const item: PluginCapabilityPackPromotionRuleRemediationItem = {
    pack_id: packId,
    pack_version: packVersion,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const status = safeString(raw.status, "");
  const blockers = safeStringArray(raw.blockers);
  const missingPromotionRules = safeStringArray(raw.missing_promotion_rules);
  const missingGovernanceFields = safeStringArray(raw.missing_governance_fields);
  const missingQualityEvidence = safeStringArray(raw.missing_quality_evidence);
  const missingReceiptEvidence = safeStringArray(raw.missing_receipt_evidence);
  const firstAction = safeString(raw.first_action, safeString(raw.firstAction, ""));
  const promotionRules = safeStringArray(raw.promotion_rules);
  const failingItems = safeUnknownArray(raw.failing_capabilities_sample)
    ?.map(parseCapabilityPackReviewItem)
    .filter((entry): entry is PluginCapabilityPackReviewItem => entry !== null);
  if (packName) item.pack_name = packName;
  if (status) item.status = status;
  if (typeof raw.ready === "boolean") item.ready = raw.ready;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) item.capability_count = safeNumber(raw.capability_count);
  if (blockers) item.blockers = blockers;
  if (missingPromotionRules) item.missing_promotion_rules = missingPromotionRules;
  if (missingGovernanceFields) item.missing_governance_fields = missingGovernanceFields;
  if (missingQualityEvidence) item.missing_quality_evidence = missingQualityEvidence;
  if (missingReceiptEvidence) item.missing_receipt_evidence = missingReceiptEvidence;
  if (firstAction) item.first_action = firstAction;
  if (promotionRules) item.promotion_rules = promotionRules;
  if (failingItems) item.failing_capabilities_sample = failingItems;
  return item;
}

function parseCapabilityLibraryProposalEvidenceCapability(
  raw: unknown,
): PluginCapabilityLibraryProposalEvidenceCapability | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryProposalEvidenceCapability = { capability };
  const status = safeString(raw.status, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const proposalReviewStatus = safeString(raw.proposal_review_status, safeString(raw.proposalReviewStatus, ""));
  const proposalReviewReceiptId = safeString(
    raw.proposal_review_receipt_id,
    safeString(raw.proposalReviewReceiptId, ""),
  );
  const evidenceSource = safeString(raw.evidence_source, safeString(raw.evidenceSource, ""));
  const proposalEvidence = safeUnknownArray(raw.proposal_evidence);
  const linkedProposalArtifactEvidence = safeUnknownArray(raw.linked_proposal_artifact_evidence);
  const missingRequirements = safeStringArray(raw.missing_requirements);
  const blockersBeforeEvidence = safeStringArray(raw.blockers_before_evidence);
  if (status) item.status = status;
  if (proposalId) item.proposal_id = proposalId;
  if (proposalReviewStatus) item.proposal_review_status = proposalReviewStatus;
  if (proposalReviewReceiptId) item.proposal_review_receipt_id = proposalReviewReceiptId;
  if (typeof raw.proposal_evidence_ready === "boolean") item.proposal_evidence_ready = raw.proposal_evidence_ready;
  if (typeof raw.proposal_evidence_missing === "boolean") {
    item.proposal_evidence_missing = raw.proposal_evidence_missing;
  }
  if (proposalEvidence) item.proposal_evidence = proposalEvidence;
  if (linkedProposalArtifactEvidence) item.linked_proposal_artifact_evidence = linkedProposalArtifactEvidence;
  if (evidenceSource) item.evidence_source = evidenceSource;
  if (missingRequirements) item.missing_requirements = missingRequirements;
  if (blockersBeforeEvidence) item.blockers_before_evidence = blockersBeforeEvidence;
  return item;
}

function parseCapabilityLibraryProposalEvidencePack(
  raw: unknown,
): PluginCapabilityLibraryProposalEvidencePack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawCapabilities = safeUnknownArray(raw.capabilities) ?? [];
  const capabilities = rawCapabilities
    .map(parseCapabilityLibraryProposalEvidenceCapability)
    .filter((entry): entry is PluginCapabilityLibraryProposalEvidenceCapability => entry !== null);
  const pack: PluginCapabilityLibraryProposalEvidencePack = {
    pack_id: packId,
    pack_version: packVersion,
    capabilities,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  if (packName) pack.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    pack.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.proposal_evidence_missing_count, NaN))) {
    pack.proposal_evidence_missing_count = safeNumber(raw.proposal_evidence_missing_count);
  }
  if (Number.isFinite(safeNumber(raw.proposal_evidence_ready_count, NaN))) {
    pack.proposal_evidence_ready_count = safeNumber(raw.proposal_evidence_ready_count);
  }
  if (Number.isFinite(safeNumber(raw.blocked_before_evidence_count, NaN))) {
    pack.blocked_before_evidence_count = safeNumber(raw.blocked_before_evidence_count);
  }
  if (typeof raw.capabilities_truncated === "boolean") pack.capabilities_truncated = raw.capabilities_truncated;
  return pack;
}

function parseCapabilityLibraryPromotionCapability(raw: unknown): PluginCapabilityLibraryPromotionCapability | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryPromotionCapability = { capability };
  const status = safeString(raw.status, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const proposalReviewStatus = safeString(raw.proposal_review_status, safeString(raw.proposalReviewStatus, ""));
  const proposalReviewReceiptId = safeString(
    raw.proposal_review_receipt_id,
    safeString(raw.proposalReviewReceiptId, ""),
  );
  const validationReceiptId = safeString(raw.validation_receipt_id, safeString(raw.validationReceiptId, ""));
  const packOperatorReviewStatus = safeString(
    raw.pack_operator_review_status,
    safeString(raw.packOperatorReviewStatus, ""),
  );
  const packOperatorReviewReceiptId = safeString(
    raw.pack_operator_review_receipt_id,
    safeString(raw.packOperatorReviewReceiptId, ""),
  );
  const promotionRoute = safeString(raw.promotion_route, safeString(raw.promotionRoute, ""));
  const missingRequirements = safeStringArray(raw.missing_requirements);
  if (status) item.status = status;
  if (typeof raw.enabled === "boolean") item.enabled = raw.enabled;
  if (typeof raw.promotion_ready === "boolean") item.promotion_ready = raw.promotion_ready;
  if (missingRequirements) item.missing_requirements = missingRequirements;
  if (proposalId) item.proposal_id = proposalId;
  if (proposalReviewStatus) item.proposal_review_status = proposalReviewStatus;
  if (proposalReviewReceiptId) item.proposal_review_receipt_id = proposalReviewReceiptId;
  if (validationReceiptId) item.validation_receipt_id = validationReceiptId;
  if (typeof raw.pack_operator_review_required === "boolean") {
    item.pack_operator_review_required = raw.pack_operator_review_required;
  }
  if (packOperatorReviewStatus) item.pack_operator_review_status = packOperatorReviewStatus;
  if (packOperatorReviewReceiptId) item.pack_operator_review_receipt_id = packOperatorReviewReceiptId;
  if (promotionRoute) item.promotion_route = promotionRoute;
  if (typeof raw.promotion_would_write_receipt === "boolean") {
    item.promotion_would_write_receipt = raw.promotion_would_write_receipt;
  }
  if (typeof raw.promotion_would_enable_capability === "boolean") {
    item.promotion_would_enable_capability = raw.promotion_would_enable_capability;
  }
  return item;
}

function parseCapabilityLibraryPromotionPack(raw: unknown): PluginCapabilityLibraryPromotionPack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawCapabilities = safeUnknownArray(raw.capabilities) ?? [];
  const capabilities = rawCapabilities
    .map(parseCapabilityLibraryPromotionCapability)
    .filter((entry): entry is PluginCapabilityLibraryPromotionCapability => entry !== null);
  const pack: PluginCapabilityLibraryPromotionPack = {
    pack_id: packId,
    pack_version: packVersion,
    capabilities,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  if (packName) pack.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    pack.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.promotable_capability_count, NaN))) {
    pack.promotable_capability_count = safeNumber(raw.promotable_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.blocked_capability_count, NaN))) {
    pack.blocked_capability_count = safeNumber(raw.blocked_capability_count);
  }
  if (typeof raw.capabilities_truncated === "boolean") pack.capabilities_truncated = raw.capabilities_truncated;
  return pack;
}

function parseCapabilityLibraryProposalReviewProposal(
  raw: unknown,
): PluginCapabilityLibraryProposalReviewProposal | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryProposalReviewProposal = { capability };
  const status = safeString(raw.status, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const proposalReviewStatus = safeString(raw.proposal_review_status, safeString(raw.proposalReviewStatus, ""));
  const proposalReviewReceiptId = safeString(
    raw.proposal_review_receipt_id,
    safeString(raw.proposalReviewReceiptId, ""),
  );
  const missingRequirements = safeStringArray(raw.missing_requirements);
  const blockersBeforeReview = safeStringArray(raw.blockers_before_review);
  const proposalReviewRoute = safeString(raw.proposal_review_route, safeString(raw.proposalReviewRoute, ""));
  if (status) item.status = status;
  if (proposalId) item.proposal_id = proposalId;
  if (proposalReviewStatus) item.proposal_review_status = proposalReviewStatus;
  if (proposalReviewReceiptId) item.proposal_review_receipt_id = proposalReviewReceiptId;
  if (typeof raw.proposal_review_missing === "boolean") item.proposal_review_missing = raw.proposal_review_missing;
  if (typeof raw.review_ready === "boolean") item.review_ready = raw.review_ready;
  if (typeof raw.approved_review === "boolean") item.approved_review = raw.approved_review;
  if (missingRequirements) item.missing_requirements = missingRequirements;
  if (blockersBeforeReview) item.blockers_before_review = blockersBeforeReview;
  if (proposalReviewRoute) item.proposal_review_route = proposalReviewRoute;
  if (typeof raw.proposal_review_would_write_receipt === "boolean") {
    item.proposal_review_would_write_receipt = raw.proposal_review_would_write_receipt;
  }
  if (typeof raw.proposal_review_would_promote_capability === "boolean") {
    item.proposal_review_would_promote_capability = raw.proposal_review_would_promote_capability;
  }
  if (typeof raw.proposal_review_would_enable_capability === "boolean") {
    item.proposal_review_would_enable_capability = raw.proposal_review_would_enable_capability;
  }
  return item;
}

function parseCapabilityLibraryProposalReviewPack(
  raw: unknown,
): PluginCapabilityLibraryProposalReviewPack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawProposals = safeUnknownArray(raw.proposals) ?? [];
  const proposals = rawProposals
    .map(parseCapabilityLibraryProposalReviewProposal)
    .filter((entry): entry is PluginCapabilityLibraryProposalReviewProposal => entry !== null);
  const pack: PluginCapabilityLibraryProposalReviewPack = {
    pack_id: packId,
    pack_version: packVersion,
    proposals,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  if (packName) pack.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    pack.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.reviewable_capability_count, NaN))) {
    pack.reviewable_capability_count = safeNumber(raw.reviewable_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.blocked_before_review_capability_count, NaN))) {
    pack.blocked_before_review_capability_count = safeNumber(raw.blocked_before_review_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.approved_proposal_review_count, NaN))) {
    pack.approved_proposal_review_count = safeNumber(raw.approved_proposal_review_count);
  }
  if (typeof raw.proposals_truncated === "boolean") pack.proposals_truncated = raw.proposals_truncated;
  return pack;
}

function parseCapabilityLibraryProposalEvidenceRemediationCapability(
  raw: unknown,
): PluginCapabilityLibraryProposalEvidenceRemediationCapability | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryProposalEvidenceRemediationCapability = { capability };
  const status = safeString(raw.status, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const metadataProposalEvidence = safeUnknownArray(raw.metadata_proposal_evidence);
  const linkedProposalArtifactEvidence = safeUnknownArray(raw.linked_proposal_artifact_evidence);
  const evidenceSource = safeString(raw.evidence_source, safeString(raw.evidenceSource, ""));
  if (status) item.status = status;
  if (proposalId) item.proposal_id = proposalId;
  if (metadataProposalEvidence) item.metadata_proposal_evidence = metadataProposalEvidence;
  if (linkedProposalArtifactEvidence) item.linked_proposal_artifact_evidence = linkedProposalArtifactEvidence;
  if (evidenceSource) item.evidence_source = evidenceSource;
  if (typeof raw.writes_registry_metadata === "boolean") {
    item.writes_registry_metadata = raw.writes_registry_metadata;
  }
  if (typeof raw.writes_proposals === "boolean") item.writes_proposals = raw.writes_proposals;
  if (typeof raw.approves_proposals === "boolean") item.approves_proposals = raw.approves_proposals;
  if (typeof raw.promotes_capability === "boolean") item.promotes_capability = raw.promotes_capability;
  return item;
}

function parseCapabilityLibraryProposalEvidenceRemediationPack(
  raw: unknown,
): PluginCapabilityLibraryProposalEvidenceRemediationPack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawCapabilities = safeUnknownArray(raw.capabilities) ?? [];
  const capabilities = rawCapabilities
    .map(parseCapabilityLibraryProposalEvidenceRemediationCapability)
    .filter((entry): entry is PluginCapabilityLibraryProposalEvidenceRemediationCapability => entry !== null);
  const pack: PluginCapabilityLibraryProposalEvidenceRemediationPack = {
    pack_id: packId,
    pack_version: packVersion,
    capabilities,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  if (packName) pack.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    pack.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.candidate_capability_count, NaN))) {
    pack.candidate_capability_count = safeNumber(raw.candidate_capability_count);
  }
  if (typeof raw.capabilities_truncated === "boolean") pack.capabilities_truncated = raw.capabilities_truncated;
  return pack;
}

function parseCapabilityLibraryProposalEvidenceFrictionSummaryRefCapability(
  raw: unknown,
): PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefCapability | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefCapability = { capability };
  const status = safeString(raw.status, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const metadataProposalEvidence = safeUnknownArray(raw.metadata_proposal_evidence);
  const frictionSummaryField = safeString(raw.friction_summary_field, safeString(raw.frictionSummaryField, ""));
  const frictionSummaryRef = safeString(raw.friction_summary_ref, safeString(raw.frictionSummaryRef, ""));
  const frictionSummaryPreview = safeString(raw.friction_summary_preview, safeString(raw.frictionSummaryPreview, ""));
  const evidenceSource = safeString(raw.evidence_source, safeString(raw.evidenceSource, ""));
  if (status) item.status = status;
  if (proposalId) item.proposal_id = proposalId;
  if (metadataProposalEvidence) item.metadata_proposal_evidence = metadataProposalEvidence;
  if (frictionSummaryField) item.friction_summary_field = frictionSummaryField;
  if (frictionSummaryRef) item.friction_summary_ref = frictionSummaryRef;
  if (frictionSummaryPreview) item.friction_summary_preview = frictionSummaryPreview;
  if (evidenceSource) item.evidence_source = evidenceSource;
  if (typeof raw.writes_registry_metadata === "boolean") {
    item.writes_registry_metadata = raw.writes_registry_metadata;
  }
  if (typeof raw.writes_proposals === "boolean") item.writes_proposals = raw.writes_proposals;
  if (typeof raw.approves_proposals === "boolean") item.approves_proposals = raw.approves_proposals;
  if (typeof raw.promotes_capability === "boolean") item.promotes_capability = raw.promotes_capability;
  if (typeof raw.requires_future_review === "boolean") item.requires_future_review = raw.requires_future_review;
  return item;
}

function parseCapabilityLibraryProposalEvidenceFrictionSummaryRefPack(
  raw: unknown,
): PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefPack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawCapabilities = safeUnknownArray(raw.capabilities) ?? [];
  const capabilities = rawCapabilities
    .map(parseCapabilityLibraryProposalEvidenceFrictionSummaryRefCapability)
    .filter(
      (entry): entry is PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefCapability => entry !== null,
    );
  const pack: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefPack = {
    pack_id: packId,
    pack_version: packVersion,
    capabilities,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  if (packName) pack.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    pack.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.candidate_capability_count, NaN))) {
    pack.candidate_capability_count = safeNumber(raw.candidate_capability_count);
  }
  if (typeof raw.capabilities_truncated === "boolean") pack.capabilities_truncated = raw.capabilities_truncated;
  return pack;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeChecklistCapability(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistCapability | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistCapability = { capability };
  const status = safeString(raw.status, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const proposalReviewStatus = safeString(raw.proposal_review_status, safeString(raw.proposalReviewStatus, ""));
  const proposalReviewReceiptId = safeString(
    raw.proposal_review_receipt_id,
    safeString(raw.proposalReviewReceiptId, ""),
  );
  const missingRequirements = safeStringArray(raw.missing_requirements);
  const blockersBeforeEvidence = safeStringArray(raw.blockers_before_evidence);
  const intakeApplyRoute = safeString(raw.intake_apply_route, safeString(raw.intakeApplyRoute, ""));
  if (status) item.status = status;
  if (proposalId) item.proposal_id = proposalId;
  if (proposalReviewStatus) item.proposal_review_status = proposalReviewStatus;
  if (proposalReviewReceiptId) item.proposal_review_receipt_id = proposalReviewReceiptId;
  if (missingRequirements) item.missing_requirements = missingRequirements;
  if (blockersBeforeEvidence) item.blockers_before_evidence = blockersBeforeEvidence;
  if (typeof raw.evidence_refs_required === "boolean") item.evidence_refs_required = raw.evidence_refs_required;
  if (typeof raw.operator_supplied_evidence_not_independently_verified === "boolean") {
    item.operator_supplied_evidence_not_independently_verified =
      raw.operator_supplied_evidence_not_independently_verified;
  }
  if (intakeApplyRoute) item.intake_apply_route = intakeApplyRoute;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeChecklistPack(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistPack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawCapabilities = safeUnknownArray(raw.capabilities) ?? [];
  const capabilities = rawCapabilities
    .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeChecklistCapability)
    .filter(
      (entry): entry is PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistCapability => entry !== null,
    );
  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistPack = {
    pack_id: packId,
    pack_version: packVersion,
    capabilities,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const claimScope = safeString(raw.claim_scope, safeString(raw.claimScope, ""));
  if (packName) item.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    item.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.candidate_capability_count, NaN))) {
    item.candidate_capability_count = safeNumber(raw.candidate_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.evidence_ref_required_count, NaN))) {
    item.evidence_ref_required_count = safeNumber(raw.evidence_ref_required_count);
  }
  if (claimScope) item.claim_scope = claimScope;
  if (typeof raw.capabilities_truncated === "boolean") item.capabilities_truncated = raw.capabilities_truncated;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPayloadHint(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPayloadHint | undefined {
  if (!isRecord(raw)) return undefined;
  const hint: PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPayloadHint = {};
  const packIds = safeStringArray(raw.pack_ids);
  const capabilityIds = safeStringArray(raw.capability_ids);
  const evidenceRefs = safeStringArray(raw.evidence_refs);
  if (packIds) hint.pack_ids = packIds;
  if (capabilityIds) hint.capability_ids = capabilityIds;
  if (evidenceRefs) hint.evidence_refs = evidenceRefs;
  if (typeof raw.dry_run === "boolean") hint.dry_run = raw.dry_run;
  return hint;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetRow(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetRow | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetRow = { capability };
  const status = safeString(raw.status, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const proposalReviewStatus = safeString(raw.proposal_review_status, safeString(raw.proposalReviewStatus, ""));
  const proposalReviewReceiptId = safeString(
    raw.proposal_review_receipt_id,
    safeString(raw.proposalReviewReceiptId, ""),
  );
  const missingRequirements = safeStringArray(raw.missing_requirements);
  const blockersBeforeEvidence = safeStringArray(raw.blockers_before_evidence);
  const operatorEvidenceRefs = safeStringArray(raw.operator_evidence_refs) ?? [];
  const collectionStatus = safeString(raw.evidence_ref_collection_status, safeString(raw.evidenceRefCollectionStatus, ""));
  const claimScope = safeString(raw.claim_scope, safeString(raw.claimScope, ""));
  const intakeApplyRoute = safeString(raw.intake_apply_route, safeString(raw.intakeApplyRoute, ""));
  const applyPayloadHint = parseCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPayloadHint(
    raw.apply_payload_hint,
  );
  if (status) item.status = status;
  if (proposalId) item.proposal_id = proposalId;
  if (proposalReviewStatus) item.proposal_review_status = proposalReviewStatus;
  if (proposalReviewReceiptId) item.proposal_review_receipt_id = proposalReviewReceiptId;
  if (missingRequirements) item.missing_requirements = missingRequirements;
  if (blockersBeforeEvidence) item.blockers_before_evidence = blockersBeforeEvidence;
  item.operator_evidence_refs = operatorEvidenceRefs;
  if (Number.isFinite(safeNumber(raw.operator_evidence_ref_count, NaN))) {
    item.operator_evidence_ref_count = safeNumber(raw.operator_evidence_ref_count);
  }
  if (typeof raw.operator_evidence_refs_required === "boolean") {
    item.operator_evidence_refs_required = raw.operator_evidence_refs_required;
  }
  if (collectionStatus) item.evidence_ref_collection_status = collectionStatus;
  if (claimScope) item.claim_scope = claimScope;
  if (applyPayloadHint) item.apply_payload_hint = applyPayloadHint;
  if (typeof raw.operator_supplied_evidence_not_independently_verified === "boolean") {
    item.operator_supplied_evidence_not_independently_verified =
      raw.operator_supplied_evidence_not_independently_verified;
  }
  if (typeof raw.requires_future_proposal_review === "boolean") {
    item.requires_future_proposal_review = raw.requires_future_proposal_review;
  }
  if (intakeApplyRoute) item.intake_apply_route = intakeApplyRoute;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPack(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawRows = safeUnknownArray(raw.rows) ?? [];
  const rows = rawRows
    .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetRow)
    .filter((entry): entry is PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetRow => entry !== null);
  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPack = {
    pack_id: packId,
    pack_version: packVersion,
    rows,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const claimScope = safeString(raw.claim_scope, safeString(raw.claimScope, ""));
  if (packName) item.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    item.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.worksheet_row_count, NaN))) {
    item.worksheet_row_count = safeNumber(raw.worksheet_row_count);
  }
  if (Number.isFinite(safeNumber(raw.evidence_ref_required_count, NaN))) {
    item.evidence_ref_required_count = safeNumber(raw.evidence_ref_required_count);
  }
  if (claimScope) item.claim_scope = claimScope;
  if (typeof raw.rows_truncated === "boolean") item.rows_truncated = raw.rows_truncated;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeExportRow(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportRow | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportRow = { capability };
  const packId = safeString(raw.pack_id, safeString(raw.packId, ""));
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, ""));
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const status = safeString(raw.status, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const proposalReviewStatus = safeString(raw.proposal_review_status, safeString(raw.proposalReviewStatus, ""));
  const proposalReviewReceiptId = safeString(
    raw.proposal_review_receipt_id,
    safeString(raw.proposalReviewReceiptId, ""),
  );
  const missingRequirements = safeStringArray(raw.missing_requirements);
  const blockersBeforeEvidence = safeStringArray(raw.blockers_before_evidence);
  const evidenceRefsInput = safeString(raw.evidence_refs_input, safeString(raw.evidenceRefsInput, ""));
  const evidenceRefsInputFormat = safeString(
    raw.evidence_refs_input_format,
    safeString(raw.evidenceRefsInputFormat, ""),
  );
  const collectionStatus = safeString(raw.evidence_ref_collection_status, safeString(raw.evidenceRefCollectionStatus, ""));
  const claimScope = safeString(raw.claim_scope, safeString(raw.claimScope, ""));
  const intakeApplyRoute = safeString(raw.intake_apply_route, safeString(raw.intakeApplyRoute, ""));
  const applyPayloadHint = parseCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPayloadHint(
    raw.apply_payload_hint,
  );
  if (packId) item.pack_id = packId;
  if (packVersion) item.pack_version = packVersion;
  if (packName) item.pack_name = packName;
  if (status) item.status = status;
  if (proposalId) item.proposal_id = proposalId;
  if (proposalReviewStatus) item.proposal_review_status = proposalReviewStatus;
  if (proposalReviewReceiptId) item.proposal_review_receipt_id = proposalReviewReceiptId;
  if (missingRequirements) item.missing_requirements = missingRequirements;
  if (blockersBeforeEvidence) item.blockers_before_evidence = blockersBeforeEvidence;
  item.evidence_refs_input = evidenceRefsInput;
  if (evidenceRefsInputFormat) item.evidence_refs_input_format = evidenceRefsInputFormat;
  if (typeof raw.operator_evidence_refs_required === "boolean") {
    item.operator_evidence_refs_required = raw.operator_evidence_refs_required;
  }
  if (collectionStatus) item.evidence_ref_collection_status = collectionStatus;
  if (claimScope) item.claim_scope = claimScope;
  if (typeof raw.dry_run_required === "boolean") item.dry_run_required = raw.dry_run_required;
  if (applyPayloadHint) item.apply_payload_hint = applyPayloadHint;
  if (typeof raw.operator_supplied_evidence_not_independently_verified === "boolean") {
    item.operator_supplied_evidence_not_independently_verified =
      raw.operator_supplied_evidence_not_independently_verified;
  }
  if (typeof raw.requires_future_proposal_review === "boolean") {
    item.requires_future_proposal_review = raw.requires_future_proposal_review;
  }
  if (intakeApplyRoute) item.intake_apply_route = intakeApplyRoute;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeExportPack(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportPack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawRows = safeUnknownArray(raw.rows) ?? [];
  const rows = rawRows
    .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeExportRow)
    .filter((entry): entry is PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportRow => entry !== null);
  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportPack = {
    pack_id: packId,
    pack_version: packVersion,
    rows,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const claimScope = safeString(raw.claim_scope, safeString(raw.claimScope, ""));
  if (packName) item.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    item.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.export_row_count, NaN))) {
    item.export_row_count = safeNumber(raw.export_row_count);
  }
  if (Number.isFinite(safeNumber(raw.exported_row_count, NaN))) {
    item.exported_row_count = safeNumber(raw.exported_row_count);
  }
  if (Number.isFinite(safeNumber(raw.evidence_ref_required_count, NaN))) {
    item.evidence_ref_required_count = safeNumber(raw.evidence_ref_required_count);
  }
  if (claimScope) item.claim_scope = claimScope;
  if (typeof raw.rows_truncated === "boolean") item.rows_truncated = raw.rows_truncated;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow | null {
  if (!isRecord(raw)) return null;
  const rowIndex = safeNumber(raw.row_index, NaN);
  if (!Number.isFinite(rowIndex)) return null;
  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow = { row_index: rowIndex };
  const packId = safeString(raw.pack_id, safeString(raw.packId, ""));
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, ""));
  const capability = safeString(raw.capability, safeString(raw.capability_id, ""));
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const status = safeString(raw.status, "");
  const error = safeString(raw.error, "");
  const evidenceRefs = safeStringArray(raw.evidence_refs);
  if (packId) item.pack_id = packId;
  if (packVersion) item.pack_version = packVersion;
  if (capability) item.capability = capability;
  if (proposalId) item.proposal_id = proposalId;
  if (status) item.status = status;
  if (error) item.error = error;
  if (evidenceRefs) item.evidence_refs = evidenceRefs;
  if (Number.isFinite(safeNumber(raw.evidence_ref_count, NaN))) {
    item.evidence_ref_count = safeNumber(raw.evidence_ref_count);
  }
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakePayload(raw: unknown) {
  if (!isRecord(raw)) return undefined;
  return {
    pack_ids: safeStringArray(raw.pack_ids) ?? [],
    capability_ids: safeStringArray(raw.capability_ids) ?? [],
    evidence_refs: safeStringArray(raw.evidence_refs) ?? [],
    dry_run: typeof raw.dry_run === "boolean" ? raw.dry_run : true,
    dry_run_fingerprint: safeString(raw.dry_run_fingerprint, "") || undefined,
    max_pack_count: Number.isFinite(safeNumber(raw.max_pack_count, NaN)) ? safeNumber(raw.max_pack_count) : undefined,
    max_total_capability_count: Number.isFinite(safeNumber(raw.max_total_capability_count, NaN))
      ? safeNumber(raw.max_total_capability_count)
      : undefined,
    max_capability_count_per_pack: Number.isFinite(safeNumber(raw.max_capability_count_per_pack, NaN))
      ? safeNumber(raw.max_capability_count_per_pack)
      : undefined,
    dry_run_fingerprint_required:
      typeof raw.dry_run_fingerprint_required === "boolean" ? raw.dry_run_fingerprint_required : undefined,
  };
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewGroup(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewGroup | null {
  if (!isRecord(raw)) return null;
  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  if (!packId) return null;
  const rowIndexesRaw = safeUnknownArray(raw.row_indexes) ?? [];
  const rowIndexes = rowIndexesRaw.map((item) => safeNumber(item, NaN)).filter((item) => Number.isFinite(item));
  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewGroup = { pack_id: packId };
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, ""));
  if (packVersion) item.pack_version = packVersion;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) {
    item.capability_count = safeNumber(raw.capability_count);
  }
  if (Number.isFinite(safeNumber(raw.evidence_ref_count, NaN))) {
    item.evidence_ref_count = safeNumber(raw.evidence_ref_count);
  }
  if (rowIndexes.length) item.row_indexes = rowIndexes;
  if (typeof raw.row_indexes_truncated === "boolean") item.row_indexes_truncated = raw.row_indexes_truncated;
  const previewPayload = parseCapabilityLibraryOperatorProposalEvidenceIntakePayload(raw.preview_payload);
  const applyPayloadHint = parseCapabilityLibraryOperatorProposalEvidenceIntakePayload(raw.apply_payload_hint);
  if (previewPayload) item.preview_payload = previewPayload;
  if (applyPayloadHint) item.apply_payload_hint = applyPayloadHint;
  const previewRoute = safeString(raw.preview_route, safeString(raw.previewRoute, ""));
  const applyRoute = safeString(raw.apply_route, safeString(raw.applyRoute, ""));
  if (previewRoute) item.preview_route = previewRoute;
  if (applyRoute) item.apply_route = applyRoute;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeAuditCapability(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditCapability | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditCapability = { capability };
  const status = safeString(raw.status, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const evidenceRefs = safeStringArray(raw.evidence_refs);
  const claimScope = safeString(raw.claim_scope, safeString(raw.claimScope, ""));
  const operatorIntakeActor = safeString(raw.operator_intake_actor, safeString(raw.operatorIntakeActor, ""));
  const operatorIntakeReason = safeString(raw.operator_intake_reason, safeString(raw.operatorIntakeReason, ""));
  const operatorIntakeRoute = safeString(raw.operator_intake_route, safeString(raw.operatorIntakeRoute, ""));
  const operatorIntakeTs =
    normalizeUnixSeconds(raw.operator_intake_ts) ?? normalizeUnixSeconds(raw.operatorIntakeTs);
  if (status) item.status = status;
  if (proposalId) item.proposal_id = proposalId;
  if (Number.isFinite(safeNumber(raw.evidence_ref_count, NaN))) {
    item.evidence_ref_count = safeNumber(raw.evidence_ref_count);
  }
  if (evidenceRefs) item.evidence_refs = evidenceRefs;
  if (typeof raw.evidence_refs_truncated === "boolean") item.evidence_refs_truncated = raw.evidence_refs_truncated;
  if (claimScope) item.claim_scope = claimScope;
  if (operatorIntakeActor) item.operator_intake_actor = operatorIntakeActor;
  if (operatorIntakeReason) item.operator_intake_reason = operatorIntakeReason;
  if (Number.isFinite(operatorIntakeTs)) item.operator_intake_ts = operatorIntakeTs;
  if (operatorIntakeRoute) item.operator_intake_route = operatorIntakeRoute;
  if (typeof raw.operator_supplied_evidence_not_independently_verified === "boolean") {
    item.operator_supplied_evidence_not_independently_verified =
      raw.operator_supplied_evidence_not_independently_verified;
  }
  if (typeof raw.requires_future_proposal_review === "boolean") {
    item.requires_future_proposal_review = raw.requires_future_proposal_review;
  }
  if (typeof raw.writes_proposals === "boolean") item.writes_proposals = raw.writes_proposals;
  if (typeof raw.approval_claimed === "boolean") item.approval_claimed = raw.approval_claimed;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeAuditPack(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditPack | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawCapabilities = safeUnknownArray(raw.capabilities) ?? [];
  const capabilities = rawCapabilities
    .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeAuditCapability)
    .filter((entry): entry is PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditCapability => entry !== null);
  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditPack = {
    pack_id: packId,
    pack_version: packVersion,
    capabilities,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const claimScope = safeString(raw.claim_scope, safeString(raw.claimScope, ""));
  if (packName) item.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    item.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.recorded_capability_count, NaN))) {
    item.recorded_capability_count = safeNumber(raw.recorded_capability_count);
  }
  if (Number.isFinite(safeNumber(raw.evidence_ref_count, NaN))) {
    item.evidence_ref_count = safeNumber(raw.evidence_ref_count);
  }
  if (claimScope) item.claim_scope = claimScope;
  if (typeof raw.capabilities_truncated === "boolean") item.capabilities_truncated = raw.capabilities_truncated;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeCapability(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeCapability | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;

  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeCapability = { capability };
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const missingRequirements = safeStringArray(raw.missing_requirements);
  if (proposalId) item.proposal_id = proposalId;
  if (missingRequirements) item.missing_requirements = missingRequirements;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakePlan(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakePlan | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const rawCapabilities = safeUnknownArray(raw.capabilities) ?? [];
  const capabilities = rawCapabilities
    .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeCapability)
    .filter((entry): entry is PluginCapabilityLibraryOperatorProposalEvidenceIntakeCapability => entry !== null);
  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakePlan = {
    pack_id: packId,
    pack_version: packVersion,
    capabilities,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const claimScope = safeString(raw.claim_scope, safeString(raw.claimScope, ""));
  if (packName) item.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) item.capability_count = safeNumber(raw.capability_count);
  if (Number.isFinite(safeNumber(raw.evidence_ref_count, NaN))) {
    item.evidence_ref_count = safeNumber(raw.evidence_ref_count);
  }
  if (claimScope) item.claim_scope = claimScope;
  if (typeof raw.writes_registry_metadata === "boolean") {
    item.writes_registry_metadata = raw.writes_registry_metadata;
  }
  if (typeof raw.writes_proposals === "boolean") item.writes_proposals = raw.writes_proposals;
  if (typeof raw.approves_proposals === "boolean") item.approves_proposals = raw.approves_proposals;
  if (typeof raw.promotes_capabilities === "boolean") item.promotes_capabilities = raw.promotes_capabilities;
  if (typeof raw.enables_capabilities === "boolean") item.enables_capabilities = raw.enables_capabilities;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeRecord(
  raw: unknown,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeRecord | null {
  if (!isRecord(raw)) return null;

  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId) return null;

  const item: PluginCapabilityLibraryOperatorProposalEvidenceIntakeRecord = {
    pack_id: packId,
    pack_version: packVersion,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const claimScope = safeString(raw.claim_scope, safeString(raw.claimScope, ""));
  const status = safeString(raw.status, "");
  const error = safeString(raw.error, "");
  const changedCapabilityIds = safeStringArray(raw.changed_capability_ids);
  const capabilities = safeUnknownArray(raw.capabilities);
  if (packName) item.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) item.capability_count = safeNumber(raw.capability_count);
  if (Number.isFinite(safeNumber(raw.changed_capability_count, NaN))) {
    item.changed_capability_count = safeNumber(raw.changed_capability_count);
  }
  if (changedCapabilityIds) item.changed_capability_ids = changedCapabilityIds;
  if (typeof raw.changed_capability_ids_truncated === "boolean") {
    item.changed_capability_ids_truncated = raw.changed_capability_ids_truncated;
  }
  if (Number.isFinite(safeNumber(raw.evidence_ref_count, NaN))) {
    item.evidence_ref_count = safeNumber(raw.evidence_ref_count);
  }
  if (claimScope) item.claim_scope = claimScope;
  if (typeof raw.writes_registry_metadata === "boolean") {
    item.writes_registry_metadata = raw.writes_registry_metadata;
  }
  if (typeof raw.writes_proposals === "boolean") item.writes_proposals = raw.writes_proposals;
  if (typeof raw.approves_proposals === "boolean") item.approves_proposals = raw.approves_proposals;
  if (typeof raw.promotes_capabilities === "boolean") item.promotes_capabilities = raw.promotes_capabilities;
  if (typeof raw.enables_capabilities === "boolean") item.enables_capabilities = raw.enables_capabilities;
  if (status) item.status = status;
  if (error) item.error = error;
  if (capabilities) item.capabilities = capabilities;
  return item;
}

function parseCapabilityLibraryOperatorProposalEvidenceIntakeResponse(
  json: unknown,
  fallbackDryRun: boolean,
  fallbackEvidenceRefCount: number,
): PluginCapabilityLibraryOperatorProposalEvidenceIntakeResponse {
  if (!isRecord(json)) return { ok: true, applied: false, dry_run: fallbackDryRun };

  const plannedRaw = safeUnknownArray((json as Record<string, unknown>).planned) ?? [];
  const recordedRaw = safeUnknownArray((json as Record<string, unknown>).recorded) ?? [];
  const failedRaw = safeUnknownArray((json as Record<string, unknown>).failed) ?? [];
  const skippedRaw = safeUnknownArray((json as Record<string, unknown>).skipped) ?? [];
  const planned = plannedRaw
    .map(parseCapabilityLibraryOperatorProposalEvidenceIntakePlan)
    .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakePlan => item !== null);
  const recorded = recordedRaw
    .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeRecord)
    .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeRecord => item !== null);
  const failed = failedRaw
    .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeRecord)
    .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeRecord => item !== null);
  const skipped = skippedRaw
    .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeRecord)
    .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeRecord => item !== null);
  return {
    ok: Boolean((json as Record<string, unknown>).ok ?? false),
    applied:
      typeof (json as Record<string, unknown>).applied === "boolean"
        ? Boolean((json as Record<string, unknown>).applied)
        : undefined,
    kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
    status: safeString((json as Record<string, unknown>).status, "") || undefined,
    dry_run:
      typeof (json as Record<string, unknown>).dry_run === "boolean"
        ? Boolean((json as Record<string, unknown>).dry_run)
        : fallbackDryRun,
    error: safeString((json as Record<string, unknown>).error, "") || undefined,
    planned_pack_count: safeNumber((json as Record<string, unknown>).planned_pack_count, planned.length),
    planned_capability_count: safeNumber((json as Record<string, unknown>).planned_capability_count, 0),
    evidence_ref_count: safeNumber((json as Record<string, unknown>).evidence_ref_count, fallbackEvidenceRefCount),
    recorded_pack_count: safeNumber((json as Record<string, unknown>).recorded_pack_count, recorded.length),
    recorded_capability_count: safeNumber((json as Record<string, unknown>).recorded_capability_count, 0),
    candidate_total: safeNumber((json as Record<string, unknown>).candidate_total, 0) || undefined,
    limit: safeNumber((json as Record<string, unknown>).limit, 0) || undefined,
    capability_count: safeNumber((json as Record<string, unknown>).capability_count, 0) || undefined,
    dry_run_fingerprint: safeString((json as Record<string, unknown>).dry_run_fingerprint, "") || undefined,
    dry_run_confirmation: isRecord((json as Record<string, unknown>).dry_run_confirmation)
      ? ((json as Record<string, unknown>).dry_run_confirmation as Record<string, unknown>)
      : undefined,
    planned,
    recorded,
    failed,
    skipped,
    before: isRecord((json as Record<string, unknown>).before)
      ? ((json as Record<string, unknown>).before as Record<string, unknown>)
      : undefined,
    remaining_proposal_evidence_missing_count: Number.isFinite(
      safeNumber((json as Record<string, unknown>).remaining_proposal_evidence_missing_count, NaN),
    )
      ? safeNumber((json as Record<string, unknown>).remaining_proposal_evidence_missing_count)
      : undefined,
    remaining_proposal_evidence_ready_count: Number.isFinite(
      safeNumber((json as Record<string, unknown>).remaining_proposal_evidence_ready_count, NaN),
    )
      ? safeNumber((json as Record<string, unknown>).remaining_proposal_evidence_ready_count)
      : undefined,
    next_smallest_truthful_gap:
      safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
    governance: isRecord((json as Record<string, unknown>).governance)
      ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
      : undefined,
  };
}

function parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlanCapability(
  raw: unknown,
): PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlanCapability | null {
  if (!isRecord(raw)) return null;
  const capability = safeString(raw.capability, safeString(raw.id, "")).trim();
  if (!capability) return null;
  const item: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlanCapability = { capability };
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const frictionSummaryField = safeString(raw.friction_summary_field, safeString(raw.frictionSummaryField, ""));
  const frictionSummaryRef = safeString(raw.friction_summary_ref, safeString(raw.frictionSummaryRef, ""));
  if (proposalId) item.proposal_id = proposalId;
  if (frictionSummaryField) item.friction_summary_field = frictionSummaryField;
  if (frictionSummaryRef) item.friction_summary_ref = frictionSummaryRef;
  return item;
}

function parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlan(
  raw: unknown,
): PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlan | null {
  if (!isRecord(raw)) return null;
  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;
  const capabilitiesRaw = safeUnknownArray(raw.capabilities) ?? [];
  const capabilities = capabilitiesRaw
    .map(parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlanCapability)
    .filter(
      (item): item is PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlanCapability => item !== null,
    );
  const item: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlan = {
    pack_id: packId,
    pack_version: packVersion,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const evidenceSource = safeString(raw.evidence_source, safeString(raw.evidenceSource, ""));
  if (packName) item.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) item.capability_count = safeNumber(raw.capability_count);
  if (evidenceSource) item.evidence_source = evidenceSource;
  if (capabilities.length) item.capabilities = capabilities;
  if (typeof raw.writes_registry_metadata === "boolean") {
    item.writes_registry_metadata = raw.writes_registry_metadata;
  }
  if (typeof raw.writes_proposals === "boolean") item.writes_proposals = raw.writes_proposals;
  if (typeof raw.approves_proposals === "boolean") item.approves_proposals = raw.approves_proposals;
  if (typeof raw.promotes_capabilities === "boolean") item.promotes_capabilities = raw.promotes_capabilities;
  if (typeof raw.enables_capabilities === "boolean") item.enables_capabilities = raw.enables_capabilities;
  if (typeof raw.requires_future_review === "boolean") item.requires_future_review = raw.requires_future_review;
  return item;
}

function parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord(
  raw: unknown,
): PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord | null {
  if (!isRecord(raw)) return null;
  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;
  const item: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord = {
    pack_id: packId,
    pack_version: packVersion,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const evidenceSource = safeString(raw.evidence_source, safeString(raw.evidenceSource, ""));
  const status = safeString(raw.status, "");
  const error = safeString(raw.error, "");
  const changedCapabilityIds = safeStringArray(raw.changed_capability_ids);
  const capabilities = safeUnknownArray(raw.capabilities);
  if (packName) item.pack_name = packName;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) item.capability_count = safeNumber(raw.capability_count);
  if (Number.isFinite(safeNumber(raw.changed_capability_count, NaN))) {
    item.changed_capability_count = safeNumber(raw.changed_capability_count);
  }
  if (changedCapabilityIds) item.changed_capability_ids = changedCapabilityIds;
  if (typeof raw.changed_capability_ids_truncated === "boolean") {
    item.changed_capability_ids_truncated = raw.changed_capability_ids_truncated;
  }
  if (evidenceSource) item.evidence_source = evidenceSource;
  if (typeof raw.writes_registry_metadata === "boolean") {
    item.writes_registry_metadata = raw.writes_registry_metadata;
  }
  if (typeof raw.writes_proposals === "boolean") item.writes_proposals = raw.writes_proposals;
  if (typeof raw.approves_proposals === "boolean") item.approves_proposals = raw.approves_proposals;
  if (typeof raw.promotes_capabilities === "boolean") item.promotes_capabilities = raw.promotes_capabilities;
  if (typeof raw.enables_capabilities === "boolean") item.enables_capabilities = raw.enables_capabilities;
  if (typeof raw.requires_future_review === "boolean") item.requires_future_review = raw.requires_future_review;
  if (status) item.status = status;
  if (error) item.error = error;
  if (capabilities) item.capabilities = capabilities;
  return item;
}

function parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyResponse(
  json: unknown,
  fallbackDryRun: boolean,
): PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyResponse {
  if (!isRecord(json)) return { ok: true, applied: false, dry_run: fallbackDryRun };

  const plannedRaw = safeUnknownArray((json as Record<string, unknown>).planned) ?? [];
  const recordedRaw = safeUnknownArray((json as Record<string, unknown>).recorded) ?? [];
  const failedRaw = safeUnknownArray((json as Record<string, unknown>).failed) ?? [];
  const skippedRaw = safeUnknownArray((json as Record<string, unknown>).skipped) ?? [];
  const planned = plannedRaw
    .map(parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlan)
    .filter(
      (item): item is PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyPlan => item !== null,
    );
  const recorded = recordedRaw
    .map(parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord)
    .filter(
      (item): item is PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord => item !== null,
    );
  const failed = failedRaw
    .map(parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord)
    .filter(
      (item): item is PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord => item !== null,
    );
  const skipped = skippedRaw
    .map(parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord)
    .filter(
      (item): item is PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRecord => item !== null,
    );
  return {
    ok: Boolean((json as Record<string, unknown>).ok ?? false),
    applied:
      typeof (json as Record<string, unknown>).applied === "boolean"
        ? Boolean((json as Record<string, unknown>).applied)
        : undefined,
    kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
    status: safeString((json as Record<string, unknown>).status, "") || undefined,
    dry_run:
      typeof (json as Record<string, unknown>).dry_run === "boolean"
        ? Boolean((json as Record<string, unknown>).dry_run)
        : fallbackDryRun,
    error: safeString((json as Record<string, unknown>).error, "") || undefined,
    planned_pack_count: safeNumber((json as Record<string, unknown>).planned_pack_count, planned.length),
    planned_capability_count: safeNumber((json as Record<string, unknown>).planned_capability_count, 0),
    recorded_pack_count: safeNumber((json as Record<string, unknown>).recorded_pack_count, recorded.length),
    recorded_capability_count: safeNumber((json as Record<string, unknown>).recorded_capability_count, 0),
    candidate_total: safeNumber((json as Record<string, unknown>).candidate_total, 0) || undefined,
    limit: safeNumber((json as Record<string, unknown>).limit, 0) || undefined,
    capability_count: safeNumber((json as Record<string, unknown>).capability_count, 0) || undefined,
    planned,
    recorded,
    failed,
    skipped,
    before: isRecord((json as Record<string, unknown>).before)
      ? ((json as Record<string, unknown>).before as Record<string, unknown>)
      : undefined,
    remaining_candidate_pack_count: Number.isFinite(
      safeNumber((json as Record<string, unknown>).remaining_candidate_pack_count, NaN),
    )
      ? safeNumber((json as Record<string, unknown>).remaining_candidate_pack_count)
      : undefined,
    remaining_candidate_capability_count: Number.isFinite(
      safeNumber((json as Record<string, unknown>).remaining_candidate_capability_count, NaN),
    )
      ? safeNumber((json as Record<string, unknown>).remaining_candidate_capability_count)
      : undefined,
    next_smallest_truthful_gap:
      safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
    governance: isRecord((json as Record<string, unknown>).governance)
      ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
      : undefined,
  };
}

function parseCapabilityPackOperatorReviewDecision(raw: unknown): PluginCapabilityPackOperatorReviewDecision | null {
  if (!isRecord(raw)) return null;

  const receiptId = safeString(raw.receipt_id, safeString(raw.receiptId, safeString(raw.id, ""))).trim();
  if (!receiptId) return null;

  const item: PluginCapabilityPackOperatorReviewDecision = {
    id: safeString(raw.id, receiptId) || receiptId,
    receipt_id: receiptId,
  };
  const status = safeString(raw.status, "");
  const decision = safeString(raw.decision, "");
  const packId = safeString(raw.pack_id, safeString(raw.packId, ""));
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, ""));
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const actor = safeString(raw.actor, "");
  const reason = safeString(raw.reason, "");
  const notes = safeString(raw.notes, "");
  const path = safeString(raw.path, "");
  const relativePath = safeString(raw.relative_path, safeString(raw.relativePath, ""));
  const capabilityIds = safeStringArray(raw.capability_ids);
  const decidedTs = normalizeUnixSeconds(raw.decided_ts) ?? normalizeUnixSeconds(raw.decidedAt);
  if (status) item.status = status;
  if (decision) item.decision = decision;
  if (packId) item.pack_id = packId;
  if (packVersion) item.pack_version = packVersion;
  if (packName) item.pack_name = packName;
  if (capabilityIds) item.capability_ids = capabilityIds;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) item.capability_count = safeNumber(raw.capability_count);
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    item.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (actor) item.actor = actor;
  if (reason) item.reason = reason;
  if (notes) item.notes = notes;
  if (decidedTs !== undefined) item.decided_ts = decidedTs;
  if (path) item.path = path;
  if (relativePath) item.relative_path = relativePath;
  if (isRecord(raw.review_snapshot)) item.review_snapshot = raw.review_snapshot;
  if (isRecord(raw.governance)) item.governance = raw.governance;
  return item;
}

function parseCapabilityPackOperatorReviewBulkDecisionPlan(
  raw: unknown,
): PluginCapabilityPackOperatorReviewBulkDecisionPlan | null {
  if (!isRecord(raw)) return null;
  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  const packVersion = safeString(raw.pack_version, safeString(raw.packVersion, "")).trim();
  if (!packId || !packVersion) return null;

  const item: PluginCapabilityPackOperatorReviewBulkDecisionPlan = {
    pack_id: packId,
    pack_version: packVersion,
  };
  const packName = safeString(raw.pack_name, safeString(raw.packName, ""));
  const action = safeString(raw.action, "");
  const decisionStatus = safeString(raw.decision_status, safeString(raw.decisionStatus, ""));
  if (packName) item.pack_name = packName;
  if (action) item.action = action;
  if (decisionStatus) item.decision_status = decisionStatus;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) item.capability_count = safeNumber(raw.capability_count);
  if (Number.isFinite(safeNumber(raw.staged_capability_count, NaN))) {
    item.staged_capability_count = safeNumber(raw.staged_capability_count);
  }
  if (typeof raw.quality_evidence_ready === "boolean") item.quality_evidence_ready = raw.quality_evidence_ready;
  if (typeof raw.proposal_lineage_ready === "boolean") item.proposal_lineage_ready = raw.proposal_lineage_ready;
  if (typeof raw.validation_receipts_ready === "boolean") item.validation_receipts_ready = raw.validation_receipts_ready;
  if (typeof raw.operator_review_rule_declared === "boolean") {
    item.operator_review_rule_declared = raw.operator_review_rule_declared;
  }
  if (typeof raw.operator_review_governance_declared === "boolean") {
    item.operator_review_governance_declared = raw.operator_review_governance_declared;
  }
  if (typeof raw.writes_receipt === "boolean") item.writes_receipt = raw.writes_receipt;
  return item;
}

function parseCapabilityPackOperatorReviewBulkDecisionRecord(
  raw: unknown,
): PluginCapabilityPackOperatorReviewBulkDecisionRecord | null {
  if (!isRecord(raw)) return null;
  const packId = safeString(raw.pack_id, safeString(raw.packId, "")).trim();
  if (!packId) return null;
  const item: PluginCapabilityPackOperatorReviewBulkDecisionRecord = {
    pack_id: packId,
    pack_version: safeString(raw.pack_version, safeString(raw.packVersion, "")),
  };
  const receiptId = safeString(raw.receipt_id, safeString(raw.receiptId, ""));
  const receiptPath = safeString(raw.receipt_path, safeString(raw.receiptPath, ""));
  const status = safeString(raw.status, "");
  const error = safeString(raw.error, "");
  if (receiptId) item.receipt_id = receiptId;
  if (receiptPath) item.receipt_path = receiptPath;
  if (Number.isFinite(safeNumber(raw.capability_count, NaN))) item.capability_count = safeNumber(raw.capability_count);
  if (status) item.status = status;
  if (error) item.error = error;
  return item;
}

function parseCapabilityCatalogEntry(raw: unknown): PluginCapabilityCatalogEntry | null {
  if (!isRecord(raw)) return null;

  const capability = safeString(raw.capability, safeString(raw.id, safeString(raw.plugin_id, ""))).trim();
  if (!capability) return null;

  const entry: PluginCapabilityCatalogEntry = { capability };
  const version = safeString(raw.version, "");
  const status = safeString(raw.status, "");
  const riskTier = safeString(raw.risk_tier, safeString(raw.riskTier, ""));
  const source = safeString(raw.source, "");
  const proposalId = safeString(raw.proposal_id, safeString(raw.proposalId, ""));
  const promotionReceiptId = safeString(raw.promotion_receipt_id, safeString(raw.promotionReceiptId, ""));
  if (version) entry.version = version;
  if (status) entry.status = status;
  if (riskTier) entry.risk_tier = riskTier;
  if (source) entry.source = source;
  if (typeof raw.price === "number" && Number.isFinite(raw.price)) entry.price = raw.price;
  if (proposalId) entry.proposal_id = proposalId;
  if (promotionReceiptId) entry.promotion_receipt_id = promotionReceiptId;

  const qualityRaw = isRecord(raw.quality) ? raw.quality : {};
  const quality: PluginCapabilityCatalogQuality = {};
  const tests = safeStringArray(qualityRaw.tests);
  const docs = safeStringArray(qualityRaw.docs);
  if (tests) quality.tests = tests;
  if (docs) quality.docs = docs;
  if (Object.keys(quality).length > 0) entry.quality = quality;

  if (isRecord(raw.metadata)) entry.metadata = raw.metadata;

  return entry;
}

function parseCapabilityCatalogSummary(raw: unknown): PluginCapabilityCatalogSummary | undefined {
  if (!isRecord(raw)) return undefined;

  const summary: PluginCapabilityCatalogSummary = {};
  const total = safeNumber(raw.total, NaN);
  const testedCount = safeNumber(raw.tested_count, NaN);
  const documentedCount = safeNumber(raw.documented_count, NaN);
  if (Number.isFinite(total)) summary.total = total;
  if (Number.isFinite(testedCount)) summary.tested_count = testedCount;
  if (Number.isFinite(documentedCount)) summary.documented_count = documentedCount;
  if (isRecord(raw.status_counts)) summary.status_counts = numericRecord(raw.status_counts);
  if (isRecord(raw.risk_tier_counts)) summary.risk_tier_counts = numericRecord(raw.risk_tier_counts);
  if (isRecord(raw.source_counts)) summary.source_counts = numericRecord(raw.source_counts);

  return Object.keys(summary).length > 0 ? summary : undefined;
}

function parseCapabilityCatalogCoherence(raw: unknown): PluginCapabilityCatalogCoherence | undefined {
  if (!isRecord(raw)) return undefined;

  const coherence: PluginCapabilityCatalogCoherence = {};
  const total = safeNumber(raw.total, NaN);
  if (Number.isFinite(total)) coherence.total = total;
  if (Array.isArray(raw.duplicate_capabilities)) coherence.duplicate_capabilities = raw.duplicate_capabilities;
  if (Array.isArray(raw.duplicate_proposals)) coherence.duplicate_proposals = raw.duplicate_proposals;
  if (Array.isArray(raw.lineage_gaps)) coherence.lineage_gaps = raw.lineage_gaps;
  if (Array.isArray(raw.validation_lineage_gaps)) coherence.validation_lineage_gaps = raw.validation_lineage_gaps;
  if (Array.isArray(raw.quality_gaps)) coherence.quality_gaps = raw.quality_gaps;

  return Object.keys(coherence).length > 0 ? coherence : undefined;
}

function numericRecord(raw: Record<string, unknown>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (typeof value === "number" && Number.isFinite(value)) out[key] = value;
  }
  return out;
}

/* -------------------------------------------------------------------------------------------------
 * Endpoints (overrideable)
 * ------------------------------------------------------------------------------------------------- */

export type PluginBrowserEndpoints = {
  list: (q?: PluginListParams) => string;
  get: (id: string) => string;
  capabilityCatalog: (q?: PluginCapabilityCatalogParams) => string;
  capabilityPackPromotionDiscipline: () => string;
  capabilityPackPromotionRuleRemediation: () => string;
  capabilityLibraryPromotionPlan: () => string;
  capabilityLibraryProposalEvidencePlan: () => string;
  capabilityLibraryProposalReviewPlan: () => string;
  capabilityLibraryProposalReviewApplyReadiness: () => string;
  capabilityLibraryProposalEvidenceRemediation: () => string;
  capabilityLibraryProposalEvidenceFrictionSummaryRefs: () => string;
  capabilityLibraryProposalEvidenceFrictionSummaryRefsApply: () => string;
  capabilityLibraryOperatorProposalEvidenceIntakeChecklist: () => string;
  capabilityLibraryOperatorProposalEvidenceIntakeWorksheet: () => string;
  capabilityLibraryOperatorProposalEvidenceIntakeExport: () => string;
  capabilityLibraryOperatorProposalEvidenceIntakeImportPreview: () => string;
  capabilityLibraryOperatorProposalEvidenceIntakeAudit: () => string;
  capabilityLibraryOperatorProposalEvidenceIntakePreview: () => string;
  capabilityLibraryOperatorProposalEvidenceIntake: () => string;
  capabilityPackOperatorReview: () => string;
  capabilityPackOperatorReviewDecisions: (q?: PluginCapabilityPackOperatorReviewDecisionListParams) => string;
  capabilityPackOperatorReviewDecision: () => string;
  capabilityPackOperatorReviewBulkDecision: () => string;
  promotionReadinessList: (q?: PluginPromotionReadinessListParams) => string;
  proposalsList: (q?: PluginForgeArtifactListParams) => string;
  proposalReviewsList: (q?: PluginForgeArtifactListParams) => string;
  proposalDecision: () => string;
  promotionsList: (q?: PluginForgeArtifactListParams) => string;
  toolsList: (q?: PluginToolListParams) => string;
  toolsGet: (id: string) => string;
  toolsExport: (format: PluginToolsExportFormat, q?: PluginToolListParams) => string;
  toolsRun: () => string;

  enable: () => string;
  disable: () => string;

  install: () => string;
  uninstall: () => string;

  run: () => string;

  reload?: () => string;
};

export function defaultPluginBrowserEndpoints(): PluginBrowserEndpoints {
  return {
    list: (q) =>
      `/plugins/list${encodeQuery({
        limit: q?.limit,
        offset: q?.offset,
        cursor: q?.cursor,
        status: q?.status,
        enabled: q?.enabled,
        source_kind: q?.source_kind,
        tag: q?.tag,
        tags: q?.tags,
        kind: q?.kind,
        domain: q?.domain,
        actor: q?.actor,
        search: q?.search,
        include_capabilities: q?.include_capabilities ? true : undefined,
        include_manifest: q?.include_manifest ? true : undefined,
      })}`,

    get: (id: string) => `/plugins/get${encodeQuery({ id })}`,
    capabilityCatalog: (q) =>
      `/plugins/capabilities/catalog${encodeQuery({
        limit: q?.limit,
        offset: q?.offset,
        status: q?.status,
        risk_tier: q?.risk_tier,
        source: q?.source,
      })}`,
    capabilityPackPromotionDiscipline: () => "/plugins/capabilities/packs/promotion/discipline",
    capabilityPackPromotionRuleRemediation: () => "/plugins/capabilities/packs/promotion/rules/remediation",
    capabilityLibraryPromotionPlan: () => "/plugins/capabilities/library/promotion/plan",
    capabilityLibraryProposalEvidencePlan: () => "/plugins/capabilities/library/proposal-evidence/plan",
    capabilityLibraryProposalReviewPlan: () => "/plugins/capabilities/library/proposal-review/plan",
    capabilityLibraryProposalReviewApplyReadiness: () =>
      "/plugins/capabilities/library/proposal-review/apply-readiness",
    capabilityLibraryProposalEvidenceRemediation: () => "/plugins/capabilities/library/proposal-evidence/remediation",
    capabilityLibraryProposalEvidenceFrictionSummaryRefs: () =>
      "/plugins/capabilities/library/proposal-evidence/friction-summary-refs",
    capabilityLibraryProposalEvidenceFrictionSummaryRefsApply: () =>
      "/plugins/capabilities/library/proposal-evidence/friction-summary-refs/apply",
    capabilityLibraryOperatorProposalEvidenceIntakeChecklist: () =>
      "/plugins/capabilities/library/proposal-evidence/operator-intake/checklist",
    capabilityLibraryOperatorProposalEvidenceIntakeWorksheet: () =>
      "/plugins/capabilities/library/proposal-evidence/operator-intake/worksheet",
    capabilityLibraryOperatorProposalEvidenceIntakeExport: () =>
      "/plugins/capabilities/library/proposal-evidence/operator-intake/export",
    capabilityLibraryOperatorProposalEvidenceIntakeImportPreview: () =>
      "/plugins/capabilities/library/proposal-evidence/operator-intake/import-preview",
    capabilityLibraryOperatorProposalEvidenceIntakeAudit: () =>
      "/plugins/capabilities/library/proposal-evidence/operator-intake/audit",
    capabilityLibraryOperatorProposalEvidenceIntakePreview: () =>
      "/plugins/capabilities/library/proposal-evidence/operator-intake/preview",
    capabilityLibraryOperatorProposalEvidenceIntake: () =>
      "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
    capabilityPackOperatorReview: () => "/plugins/capabilities/packs/operator/review",
    capabilityPackOperatorReviewDecisions: (q) =>
      `/plugins/capabilities/packs/operator/review/decisions${encodeQuery({
        limit: q?.limit,
        pack_id: q?.pack_id,
        pack_version: q?.pack_version,
      })}`,
    capabilityPackOperatorReviewDecision: () => "/plugins/capabilities/packs/operator/review/decisions",
    capabilityPackOperatorReviewBulkDecision: () =>
      "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
    promotionReadinessList: (q) =>
      `/forge/promotion_readiness/list${encodeQuery({
        limit: q?.limit,
        offset: q?.offset,
        plugin_id: q?.plugin_id,
        proposal_id: q?.proposal_id,
        status: q?.status,
      })}`,
    proposalsList: (q) =>
      `/forge/proposals/list${encodeQuery({
        limit: q?.limit,
        offset: q?.offset,
        id: q?.id,
        plugin_id: q?.plugin_id,
        proposal_id: q?.proposal_id,
        status: q?.status,
      })}`,
    proposalReviewsList: (q) =>
      `/forge/proposal_reviews/list${encodeQuery({
        limit: q?.limit,
        offset: q?.offset,
        id: q?.id,
        plugin_id: q?.plugin_id,
        proposal_id: q?.proposal_id,
        status: q?.status,
      })}`,
    proposalDecision: () => "/forge/proposals/decision",
    promotionsList: (q) =>
      `/forge/promotions/list${encodeQuery({
        limit: q?.limit,
        offset: q?.offset,
        id: q?.id,
        plugin_id: q?.plugin_id,
        proposal_id: q?.proposal_id,
        status: q?.status,
      })}`,
    toolsList: (q) =>
      `/plugins/tools/list${encodeQuery({
        limit: q?.limit,
        offset: q?.offset,
        plugin_id: q?.plugin_id,
        enabled: q?.enabled,
        kind: q?.kind,
        tag: q?.tag,
        tags: q?.tags,
        search: q?.search,
      })}`,
    toolsGet: (id: string) => `/plugins/tools/get${encodeQuery({ id })}`,
    toolsExport: (format: PluginToolsExportFormat, q) =>
      `/plugins/tools/export${encodeQuery({
        format,
        plugin_id: q?.plugin_id,
        enabled: q?.enabled,
        kind: q?.kind,
        tag: q?.tag,
        tags: q?.tags,
        search: q?.search,
      })}`,
    toolsRun: () => "/plugins/tools/run",

    enable: () => "/plugins/enable",
    disable: () => "/plugins/disable",

    install: () => "/plugins/install",
    uninstall: () => "/plugins/uninstall",

    run: () => "/plugins/run",

    reload: () => "/plugins/reload",
  };
}

/* -------------------------------------------------------------------------------------------------
 * Client
 * ------------------------------------------------------------------------------------------------- */

export type PluginBrowserClientHooks = {
  onRequest?: (info: { url: string; method: string; attempt: number; timeoutMs: number }) => void;
  onResponse?: (info: { url: string; method: string; status: number; elapsedMs: number; requestId?: string; attempt: number }) => void;
};

export type RetryPolicy = {
  retries?: number; // default 0
  retryMethods?: string[]; // default ["GET", "HEAD"]
  retryStatusCodes?: number[]; // default [429, 502, 503, 504]
};

export type PluginBrowserClientOptions = {
  endpoints?: PluginBrowserEndpoints;
  defaultTimeoutMs?: number;
  hooks?: PluginBrowserClientHooks;
  retry?: RetryPolicy;
};

type TimeoutMergedFetchInit = RequestInit & { timeoutMs?: number };

export class PluginBrowserClient {
  readonly baseUrl: string;
  readonly endpoints: PluginBrowserEndpoints;
  readonly defaultTimeoutMs: number;
  readonly hooks?: PluginBrowserClientHooks;
  readonly retry: Required<RetryPolicy>;

  constructor(baseUrl: string, opts?: PluginBrowserClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("PluginBrowserClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultPluginBrowserEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;

    const r = opts?.retry ?? {};
    this.retry = {
      retries: typeof r.retries === "number" ? r.retries : 0,
      retryMethods: Array.isArray(r.retryMethods) && r.retryMethods.length ? r.retryMethods : ["GET", "HEAD"],
      retryStatusCodes: Array.isArray(r.retryStatusCodes) && r.retryStatusCodes.length ? r.retryStatusCodes : [429, 502, 503, 504],
    };

    this.hooks = opts?.hooks;
  }

  private url(path: string): string {
    const p = path.startsWith("/") ? path : `/${path}`;
    return `${this.baseUrl}${p}`;
  }

  private async fetchWithTimeout(url: string, init?: TimeoutMergedFetchInit): Promise<{ res: Response; elapsedMs: number }> {
    const timeoutMs = init?.timeoutMs ?? this.defaultTimeoutMs;
    const { signal: externalSignal, ...fetchInit } = init ?? {};

    const controller = new AbortController();
    let timedOut = false;

    let timeoutId: number | null = null;
    if (timeoutMs > 0) {
      timeoutId = window.setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);
    }

    const onExternalAbort = () => controller.abort();
    if (externalSignal) {
      if (externalSignal.aborted) onExternalAbort();
      else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }

    const start = performance.now();

    try {
      const headers = new Headers(fetchInit.headers ?? undefined);
      if (!headers.has("Accept")) headers.set("Accept", "application/json");

      const method = safeString(fetchInit.method, "GET").toUpperCase();
      const hasBody = "body" in fetchInit && fetchInit.body !== undefined && fetchInit.body !== null;
      if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

      const res = await fetch(url, { ...fetchInit, headers, signal: controller.signal });
      const elapsedMs = Math.max(0, Math.round(performance.now() - start));
      return { res, elapsedMs };
    } catch (err) {
      if (timedOut) {
        throw new PluginBrowserApiError(`Request timed out after ${timeoutMs}ms`, { url, timedOut: true, cause: err });
      }
      throw err;
    } finally {
      if (timeoutId !== null) window.clearTimeout(timeoutId);
      if (externalSignal && !externalSignal.aborted) externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }

  private async fetchJson(url: string, init?: TimeoutMergedFetchInit): Promise<unknown> {
    const method = safeString(init?.method, "GET").toUpperCase();
    const retries = this.retry.retries;
    const canRetry = this.retry.retryMethods.map((m) => m.toUpperCase()).includes(method);

    let lastErr: unknown;

    for (let attempt = 0; attempt <= retries; attempt++) {
      this.hooks?.onRequest?.({ url, method, attempt, timeoutMs: init?.timeoutMs ?? this.defaultTimeoutMs });

      try {
        const { res, elapsedMs } = await this.fetchWithTimeout(url, init);
        const reqId = headerRequestId(res.headers);

        this.hooks?.onResponse?.({ url, method, status: res.status, elapsedMs, requestId: reqId, attempt });

        if (!res.ok) {
          const snippet = await readTextSnippet(res);
          const apiErr = new PluginBrowserApiError(`HTTP ${res.status} for plugin browser request`, {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
          });

          const shouldRetry = this.retry.retryStatusCodes.includes(res.status);
          if (attempt < retries && canRetry && shouldRetry) {
            lastErr = apiErr;
            await sleep(backoffMs(attempt), init?.signal);
            continue;
          }

          throw apiErr;
        }

        try {
          return await res.json();
        } catch (err) {
          const snippet = await readTextSnippet(res);
          throw new PluginBrowserApiError("Failed to parse JSON response", {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
            cause: err,
          });
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") throw err;
        if (err instanceof PluginBrowserApiError && err.timedOut) throw err;

        lastErr = err;

        if (attempt < retries && canRetry) {
          await sleep(backoffMs(attempt), init?.signal);
          continue;
        }

        throw err;
      }
    }

    throw lastErr instanceof Error ? lastErr : new Error("Plugin browser request failed");
  }

  private async fetchBlob(url: string, init?: TimeoutMergedFetchInit): Promise<Blob> {
    const method = safeString(init?.method, "GET").toUpperCase();
    this.hooks?.onRequest?.({ url, method, attempt: 0, timeoutMs: init?.timeoutMs ?? this.defaultTimeoutMs });

    const { res, elapsedMs } = await this.fetchWithTimeout(url, init);
    const reqId = headerRequestId(res.headers);
    this.hooks?.onResponse?.({ url, method, status: res.status, elapsedMs, requestId: reqId, attempt: 0 });

    if (!res.ok) {
      const snippet = await readTextSnippet(res);
      throw new PluginBrowserApiError(`HTTP ${res.status} for plugin browser request`, {
        status: res.status,
        url,
        requestId: reqId,
        bodySnippet: snippet,
      });
    }
    return await res.blob();
  }

  private parseRunResponse(json: unknown): PluginRunResponse {
    if (!isRecord(json)) {
      return {
        ok: true,
        output: json,
        status: "ok",
      };
    }
    const record = json as Record<string, unknown>;
    const governanceRaw = isRecord(record.governance) ? (record.governance as Record<string, unknown>) : null;
    const governance =
      governanceRaw
        ? {
            plane: safeString(governanceRaw.plane, "") || undefined,
            gate: safeString(governanceRaw.gate, "") || undefined,
            next_step: safeString(governanceRaw.next_step, "") || undefined,
            operator_hint: safeString(governanceRaw.operator_hint, "") || undefined,
            action: safeString(governanceRaw.action, "") || undefined,
            risk_tier: safeString(governanceRaw.risk_tier, "") || undefined,
            required_trust: safeNumber(governanceRaw.required_trust, NaN),
            current_trust: safeNumber(governanceRaw.current_trust, NaN),
            approval_status: safeString(governanceRaw.approval_status, "") || undefined,
          }
        : undefined;

    return {
      ok: Boolean(record.ok ?? true),
      output: record.output,
      operation_id: safeString(record.operation_id, "") || undefined,
      approval_id: safeString(record.approval_id, "") || undefined,
      tool_id: safeString(record.tool_id, "") || undefined,
      status: safeString(record.status, "") || undefined,
      error: safeString(record.error, "") || undefined,
      message: safeString(record.message, "") || undefined,
      governance: governance
        ? {
            ...governance,
            required_trust:
              typeof governance.required_trust === "number" && Number.isFinite(governance.required_trust)
                ? governance.required_trust
                : undefined,
            current_trust:
              typeof governance.current_trust === "number" && Number.isFinite(governance.current_trust)
                ? governance.current_trust
                : undefined,
          }
        : undefined,
      meta: isRecord(record.meta) ? (record.meta as Record<string, unknown>) : undefined,
    };
  }

  /**
   * List plugins with filters/pagination.
   */
  async list(
    params?: PluginListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginListResponse> {
    const url = this.url(this.endpoints.list(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).plugins)
          ? ((json as Record<string, unknown>).plugins as unknown[])
          : Array.isArray((json as Record<string, unknown>).entries)
            ? ((json as Record<string, unknown>).entries as unknown[])
            : [];

    const items = raw.map(parsePluginRef).filter((x): x is PluginRef => x !== null);

    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const nextCursor = safeString(
      (json as Record<string, unknown>).next_cursor,
      safeString((json as Record<string, unknown>).cursor, ""),
    );

    return {
      items,
      total: total > 0 ? total : undefined,
      next_cursor: nextCursor || undefined,
    };
  }

  /**
   * List read-only Forge promotion readiness for staged generated plugins.
   */
  async listPromotionReadiness(
    params?: PluginPromotionReadinessListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginPromotionReadinessListResponse> {
    const url = this.url(this.endpoints.promotionReadinessList(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).readiness)
          ? ((json as Record<string, unknown>).readiness as unknown[])
          : Array.isArray((json as Record<string, unknown>).candidates)
            ? ((json as Record<string, unknown>).candidates as unknown[])
            : [];

    const items = raw.map(parsePromotionReadinessItem).filter((x): x is PluginPromotionReadinessItem => x !== null);
    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const offset = safeNumber((json as Record<string, unknown>).offset, 0);
    const limit = safeNumber((json as Record<string, unknown>).limit, 0);

    return {
      items,
      total: total > 0 ? total : undefined,
      offset: offset >= 0 ? offset : undefined,
      limit: limit > 0 ? limit : undefined,
    };
  }

  /**
   * List read-only capability-pack operator review readiness.
   */
  async listCapabilityPackOperatorReview(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityPackOperatorReviewResponse> {
    const url = this.url(this.endpoints.capabilityPackOperatorReview());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityPackOperatorReviewPack)
      .filter((item): item is PluginCapabilityPackOperatorReviewPack => item !== null);
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      pack_total: safeNumber((json as Record<string, unknown>).pack_total, packs.length),
      ready_pack_count: safeNumber((json as Record<string, unknown>).ready_pack_count, 0),
      blocked_pack_count: safeNumber((json as Record<string, unknown>).blocked_pack_count, 0),
      decision_required_pack_count: safeNumber((json as Record<string, unknown>).decision_required_pack_count, 0),
      review_queue_count: safeNumber((json as Record<string, unknown>).review_queue_count, 0),
      pending_review_queue_count: safeNumber((json as Record<string, unknown>).pending_review_queue_count, 0),
      decision_recorded_pack_count: safeNumber((json as Record<string, unknown>).decision_recorded_pack_count, 0),
      packs,
      decision_routes: isRecord((json as Record<string, unknown>).decision_routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).decision_routes as Record<string, unknown>).map(
              ([key, value]) => [key, safeString(value, "")],
            ),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only capability-pack promotion discipline.
   */
  async listCapabilityPackPromotionDiscipline(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityPackPromotionDisciplineResponse> {
    const url = this.url(this.endpoints.capabilityPackPromotionDiscipline());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityPackPromotionDisciplinePack)
      .filter((item): item is PluginCapabilityPackPromotionDisciplinePack => item !== null);
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      pack_total: safeNumber((json as Record<string, unknown>).pack_total, packs.length),
      ready_pack_count: safeNumber((json as Record<string, unknown>).ready_pack_count, 0),
      blocked_pack_count: safeNumber((json as Record<string, unknown>).blocked_pack_count, 0),
      unpacked_entry_count: safeNumber((json as Record<string, unknown>).unpacked_entry_count, 0),
      available_proposal_count: safeNumber((json as Record<string, unknown>).available_proposal_count, 0),
      available_validation_receipt_count: safeNumber(
        (json as Record<string, unknown>).available_validation_receipt_count,
        0,
      ),
      available_promotion_receipt_count: safeNumber(
        (json as Record<string, unknown>).available_promotion_receipt_count,
        0,
      ),
      approved_pack_operator_review_count: safeNumber(
        (json as Record<string, unknown>).approved_pack_operator_review_count,
        0,
      ),
      packs,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only capability-pack promotion rule remediation backlog.
   */
  async listCapabilityPackPromotionRuleRemediation(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityPackPromotionRuleRemediationResponse> {
    const url = this.url(this.endpoints.capabilityPackPromotionRuleRemediation());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, remediation_queue: [] };

    const raw = Array.isArray((json as Record<string, unknown>).remediation_queue)
      ? ((json as Record<string, unknown>).remediation_queue as unknown[])
      : [];
    const remediationQueue = raw
      .map(parseCapabilityPackPromotionRuleRemediationItem)
      .filter((item): item is PluginCapabilityPackPromotionRuleRemediationItem => item !== null);
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      pack_total: safeNumber((json as Record<string, unknown>).pack_total, 0),
      ready_pack_count: safeNumber((json as Record<string, unknown>).ready_pack_count, 0),
      blocked_pack_count: safeNumber((json as Record<string, unknown>).blocked_pack_count, 0),
      unpacked_entry_count: safeNumber((json as Record<string, unknown>).unpacked_entry_count, 0),
      remediation_pack_count: safeNumber((json as Record<string, unknown>).remediation_pack_count, remediationQueue.length),
      remediation_queue_count: safeNumber(
        (json as Record<string, unknown>).remediation_queue_count,
        remediationQueue.length,
      ),
      remediation_queue_truncated: Boolean((json as Record<string, unknown>).remediation_queue_truncated ?? false),
      missing_rule_pack_count: safeNumber((json as Record<string, unknown>).missing_rule_pack_count, 0),
      missing_governance_pack_count: safeNumber((json as Record<string, unknown>).missing_governance_pack_count, 0),
      missing_quality_pack_count: safeNumber((json as Record<string, unknown>).missing_quality_pack_count, 0),
      missing_receipt_pack_count: safeNumber((json as Record<string, unknown>).missing_receipt_pack_count, 0),
      canonical_promotion_rules: safeStringArray((json as Record<string, unknown>).canonical_promotion_rules),
      first_action: safeString((json as Record<string, unknown>).first_action, "") || undefined,
      remediation_queue: remediationQueue,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only capability-library explicit promotion readiness before promotion apply.
   */
  async listCapabilityLibraryPromotionPlan(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryPromotionPlanResponse> {
    const url = this.url(this.endpoints.capabilityLibraryPromotionPlan());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryPromotionPack)
      .filter((item): item is PluginCapabilityLibraryPromotionPack => item !== null);
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      promotion_plan_ready:
        typeof (json as Record<string, unknown>).promotion_plan_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).promotion_plan_ready)
          : undefined,
      pack_total: safeNumber((json as Record<string, unknown>).pack_total, 0),
      ready_pack_count: safeNumber((json as Record<string, unknown>).ready_pack_count, 0),
      blocked_pack_count: safeNumber((json as Record<string, unknown>).blocked_pack_count, 0),
      candidate_pack_count: safeNumber((json as Record<string, unknown>).candidate_pack_count, packs.length),
      candidate_capability_count: safeNumber((json as Record<string, unknown>).candidate_capability_count, 0),
      promotable_capability_count: safeNumber((json as Record<string, unknown>).promotable_capability_count, 0),
      blocked_capability_count: safeNumber((json as Record<string, unknown>).blocked_capability_count, 0),
      missing_requirement_counts: isRecord((json as Record<string, unknown>).missing_requirement_counts)
        ? numericRecord((json as Record<string, unknown>).missing_requirement_counts as Record<string, unknown>)
        : undefined,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      capability_preview_limit: safeNumber((json as Record<string, unknown>).capability_preview_limit, 0) || undefined,
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only proposal-evidence blockers before proposal review or promotion.
   */
  async listCapabilityLibraryProposalEvidencePlan(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryProposalEvidencePlanResponse> {
    const url = this.url(this.endpoints.capabilityLibraryProposalEvidencePlan());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryProposalEvidencePack)
      .filter((item): item is PluginCapabilityLibraryProposalEvidencePack => item !== null);
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      proposal_evidence_plan_ready:
        typeof (json as Record<string, unknown>).proposal_evidence_plan_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).proposal_evidence_plan_ready)
          : undefined,
      pack_total: safeNumber((json as Record<string, unknown>).pack_total, 0),
      ready_pack_count: safeNumber((json as Record<string, unknown>).ready_pack_count, 0),
      blocked_pack_count: safeNumber((json as Record<string, unknown>).blocked_pack_count, 0),
      candidate_pack_count: safeNumber((json as Record<string, unknown>).candidate_pack_count, packs.length),
      candidate_capability_count: safeNumber((json as Record<string, unknown>).candidate_capability_count, 0),
      unique_proposal_count: safeNumber((json as Record<string, unknown>).unique_proposal_count, 0),
      proposal_evidence_missing_count: safeNumber(
        (json as Record<string, unknown>).proposal_evidence_missing_count,
        0,
      ),
      proposal_evidence_ready_count: safeNumber((json as Record<string, unknown>).proposal_evidence_ready_count, 0),
      missing_proposal_evidence_count: safeNumber(
        (json as Record<string, unknown>).missing_proposal_evidence_count,
        0,
      ),
      evidence_ready_proposal_count: safeNumber(
        (json as Record<string, unknown>).evidence_ready_proposal_count,
        0,
      ),
      proposal_id_missing_count: safeNumber((json as Record<string, unknown>).proposal_id_missing_count, 0),
      proposal_review_missing_count: safeNumber((json as Record<string, unknown>).proposal_review_missing_count, 0),
      blocked_before_evidence_count: safeNumber((json as Record<string, unknown>).blocked_before_evidence_count, 0),
      missing_requirement_counts: isRecord((json as Record<string, unknown>).missing_requirement_counts)
        ? numericRecord((json as Record<string, unknown>).missing_requirement_counts as Record<string, unknown>)
        : undefined,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      capability_preview_limit: safeNumber((json as Record<string, unknown>).capability_preview_limit, 0) || undefined,
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only proposal-review readiness after proposal evidence and quality gates.
   */
  async listCapabilityLibraryProposalReviewPlan(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryProposalReviewPlanResponse> {
    const url = this.url(this.endpoints.capabilityLibraryProposalReviewPlan());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryProposalReviewPack)
      .filter((item): item is PluginCapabilityLibraryProposalReviewPack => item !== null);
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      proposal_review_plan_ready:
        typeof (json as Record<string, unknown>).proposal_review_plan_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).proposal_review_plan_ready)
          : undefined,
      pack_total: safeNumber((json as Record<string, unknown>).pack_total, 0),
      ready_pack_count: safeNumber((json as Record<string, unknown>).ready_pack_count, 0),
      blocked_pack_count: safeNumber((json as Record<string, unknown>).blocked_pack_count, 0),
      candidate_pack_count: safeNumber((json as Record<string, unknown>).candidate_pack_count, packs.length),
      candidate_capability_count: safeNumber((json as Record<string, unknown>).candidate_capability_count, 0),
      unique_proposal_count: safeNumber((json as Record<string, unknown>).unique_proposal_count, 0),
      proposal_review_missing_count: safeNumber((json as Record<string, unknown>).proposal_review_missing_count, 0),
      approved_proposal_review_count: safeNumber(
        (json as Record<string, unknown>).approved_proposal_review_count,
        0,
      ),
      reviewable_capability_count: safeNumber((json as Record<string, unknown>).reviewable_capability_count, 0),
      reviewable_proposal_count: safeNumber((json as Record<string, unknown>).reviewable_proposal_count, 0),
      blocked_before_review_capability_count: safeNumber(
        (json as Record<string, unknown>).blocked_before_review_capability_count,
        0,
      ),
      blocked_proposal_count: safeNumber((json as Record<string, unknown>).blocked_proposal_count, 0),
      approved_proposal_count: safeNumber((json as Record<string, unknown>).approved_proposal_count, 0),
      missing_requirement_counts: isRecord((json as Record<string, unknown>).missing_requirement_counts)
        ? numericRecord((json as Record<string, unknown>).missing_requirement_counts as Record<string, unknown>)
        : undefined,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      proposal_preview_limit: safeNumber((json as Record<string, unknown>).proposal_preview_limit, 0) || undefined,
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only proposal-review apply readiness before any Forge decision receipt is written.
   */
  async listCapabilityLibraryProposalReviewApplyReadiness(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryProposalReviewApplyReadinessResponse> {
    const url = this.url(this.endpoints.capabilityLibraryProposalReviewApplyReadiness());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryProposalReviewPack)
      .filter((item): item is PluginCapabilityLibraryProposalReviewPack => item !== null);
    const evidenceRaw = (json as Record<string, unknown>).source_proposal_evidence_plan;
    const auditRaw = (json as Record<string, unknown>).source_operator_evidence_intake_audit;
    const reviewRaw = (json as Record<string, unknown>).source_proposal_review_plan;
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      proposal_review_apply_ready:
        typeof (json as Record<string, unknown>).proposal_review_apply_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).proposal_review_apply_ready)
          : undefined,
      reviewable_pack_count: safeNumber((json as Record<string, unknown>).reviewable_pack_count, 0),
      blocked_pack_count: safeNumber((json as Record<string, unknown>).blocked_pack_count, 0),
      reviewable_capability_count: safeNumber((json as Record<string, unknown>).reviewable_capability_count, 0),
      proposal_review_missing_count: safeNumber((json as Record<string, unknown>).proposal_review_missing_count, 0),
      blocked_before_review_capability_count: safeNumber(
        (json as Record<string, unknown>).blocked_before_review_capability_count,
        0,
      ),
      approved_proposal_review_count: safeNumber(
        (json as Record<string, unknown>).approved_proposal_review_count,
        0,
      ),
      source_proposal_evidence_plan: isRecord(evidenceRaw)
        ? {
            status: safeString(evidenceRaw.status, "") || undefined,
            proposal_evidence_missing_count: safeNumber(evidenceRaw.proposal_evidence_missing_count, 0),
            proposal_evidence_ready_count: safeNumber(evidenceRaw.proposal_evidence_ready_count, 0),
            proposal_review_missing_count: safeNumber(evidenceRaw.proposal_review_missing_count, 0),
            next_smallest_truthful_gap: safeString(evidenceRaw.next_smallest_truthful_gap, "") || undefined,
          }
        : undefined,
      source_operator_evidence_intake_audit: isRecord(auditRaw)
        ? {
            status: safeString(auditRaw.status, "") || undefined,
            operator_evidence_intake_audit_ready:
              typeof auditRaw.operator_evidence_intake_audit_ready === "boolean"
                ? Boolean(auditRaw.operator_evidence_intake_audit_ready)
                : undefined,
            recorded_pack_count: safeNumber(auditRaw.recorded_pack_count, 0),
            recorded_capability_count: safeNumber(auditRaw.recorded_capability_count, 0),
            evidence_ref_count: safeNumber(auditRaw.evidence_ref_count, 0),
            future_review_required_count: safeNumber(auditRaw.future_review_required_count, 0),
            next_smallest_truthful_gap: safeString(auditRaw.next_smallest_truthful_gap, "") || undefined,
          }
        : undefined,
      source_proposal_review_plan: isRecord(reviewRaw)
        ? {
            status: safeString(reviewRaw.status, "") || undefined,
            proposal_review_plan_ready:
              typeof reviewRaw.proposal_review_plan_ready === "boolean"
                ? Boolean(reviewRaw.proposal_review_plan_ready)
                : undefined,
            candidate_capability_count: safeNumber(reviewRaw.candidate_capability_count, 0),
            reviewable_capability_count: safeNumber(reviewRaw.reviewable_capability_count, 0),
            blocked_before_review_capability_count: safeNumber(reviewRaw.blocked_before_review_capability_count, 0),
            proposal_review_missing_count: safeNumber(reviewRaw.proposal_review_missing_count, 0),
            approved_proposal_review_count: safeNumber(reviewRaw.approved_proposal_review_count, 0),
            next_smallest_truthful_gap: safeString(reviewRaw.next_smallest_truthful_gap, "") || undefined,
          }
        : undefined,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only proposal-evidence remediation candidates backed by existing proposal artifacts.
   */
  async listCapabilityLibraryProposalEvidenceRemediation(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryProposalEvidenceRemediationResponse> {
    const url = this.url(this.endpoints.capabilityLibraryProposalEvidenceRemediation());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryProposalEvidenceRemediationPack)
      .filter((item): item is PluginCapabilityLibraryProposalEvidenceRemediationPack => item !== null);
    const sourcePlanRaw = (json as Record<string, unknown>).source_proposal_evidence_plan;
    const sourcePlan = isRecord(sourcePlanRaw)
      ? {
          status: safeString(sourcePlanRaw.status, "") || undefined,
          candidate_capability_count: safeNumber(sourcePlanRaw.candidate_capability_count, 0),
          proposal_evidence_missing_count: safeNumber(sourcePlanRaw.proposal_evidence_missing_count, 0),
          proposal_evidence_ready_count: safeNumber(sourcePlanRaw.proposal_evidence_ready_count, 0),
          proposal_review_missing_count: safeNumber(sourcePlanRaw.proposal_review_missing_count, 0),
          next_smallest_truthful_gap:
            safeString(sourcePlanRaw.next_smallest_truthful_gap, "") || undefined,
        }
      : undefined;
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      proposal_evidence_remediation_ready:
        typeof (json as Record<string, unknown>).proposal_evidence_remediation_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).proposal_evidence_remediation_ready)
          : undefined,
      pack_total: safeNumber((json as Record<string, unknown>).pack_total, 0),
      ready_pack_count: safeNumber((json as Record<string, unknown>).ready_pack_count, 0),
      blocked_pack_count: safeNumber((json as Record<string, unknown>).blocked_pack_count, 0),
      candidate_pack_count: safeNumber((json as Record<string, unknown>).candidate_pack_count, packs.length),
      candidate_capability_count: safeNumber((json as Record<string, unknown>).candidate_capability_count, 0),
      existing_metadata_evidence_count: safeNumber(
        (json as Record<string, unknown>).existing_metadata_evidence_count,
        0,
      ),
      proposal_id_missing_count: safeNumber((json as Record<string, unknown>).proposal_id_missing_count, 0),
      plugin_record_missing_count: safeNumber((json as Record<string, unknown>).plugin_record_missing_count, 0),
      source_proposal_evidence_plan: sourcePlan,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      capability_preview_limit: safeNumber((json as Record<string, unknown>).capability_preview_limit, 0) || undefined,
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List proposal-evidence candidates backed by existing registry friction-summary references.
   */
  async listCapabilityLibraryProposalEvidenceFrictionSummaryRefs(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefResponse> {
    const url = this.url(this.endpoints.capabilityLibraryProposalEvidenceFrictionSummaryRefs());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryProposalEvidenceFrictionSummaryRefPack)
      .filter((item): item is PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefPack => item !== null);
    const sourcePlanRaw = (json as Record<string, unknown>).source_proposal_evidence_plan;
    const sourcePlan = isRecord(sourcePlanRaw)
      ? {
          status: safeString(sourcePlanRaw.status, "") || undefined,
          candidate_capability_count: safeNumber(sourcePlanRaw.candidate_capability_count, 0),
          proposal_evidence_missing_count: safeNumber(sourcePlanRaw.proposal_evidence_missing_count, 0),
          proposal_evidence_ready_count: safeNumber(sourcePlanRaw.proposal_evidence_ready_count, 0),
          proposal_review_missing_count: safeNumber(sourcePlanRaw.proposal_review_missing_count, 0),
          next_smallest_truthful_gap:
            safeString(sourcePlanRaw.next_smallest_truthful_gap, "") || undefined,
        }
      : undefined;
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      proposal_evidence_friction_summary_refs_ready:
        typeof (json as Record<string, unknown>).proposal_evidence_friction_summary_refs_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).proposal_evidence_friction_summary_refs_ready)
          : undefined,
      pack_total: safeNumber((json as Record<string, unknown>).pack_total, 0),
      ready_pack_count: safeNumber((json as Record<string, unknown>).ready_pack_count, 0),
      blocked_pack_count: safeNumber((json as Record<string, unknown>).blocked_pack_count, 0),
      candidate_pack_count: safeNumber((json as Record<string, unknown>).candidate_pack_count, packs.length),
      candidate_capability_count: safeNumber((json as Record<string, unknown>).candidate_capability_count, 0),
      existing_metadata_evidence_count: safeNumber(
        (json as Record<string, unknown>).existing_metadata_evidence_count,
        0,
      ),
      friction_summary_missing_count: safeNumber(
        (json as Record<string, unknown>).friction_summary_missing_count,
        0,
      ),
      proposal_id_missing_count: safeNumber((json as Record<string, unknown>).proposal_id_missing_count, 0),
      plugin_record_missing_count: safeNumber((json as Record<string, unknown>).plugin_record_missing_count, 0),
      source_proposal_evidence_plan: sourcePlan,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      capability_preview_limit: safeNumber((json as Record<string, unknown>).capability_preview_limit, 0) || undefined,
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * Dry-run or write proposal-evidence refs for existing registry friction summaries.
   */
  async applyCapabilityLibraryProposalEvidenceFrictionSummaryRefs(
    req: PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyResponse> {
    const url = this.url(this.endpoints.capabilityLibraryProposalEvidenceFrictionSummaryRefsApply());
    const body = {
      ...req,
      actor: pluginMutationActor(req.actor),
      pack_ids: safeStringArray(req.pack_ids) ?? [],
      dry_run: req.dry_run !== false,
    };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Proposal evidence friction-summary refs denied.", url);
    return parseCapabilityLibraryProposalEvidenceFrictionSummaryRefApplyResponse(json, body.dry_run);
  }

  /**
   * List read-only operator proposal-evidence intake candidates before dry-run/apply.
   */
  async listCapabilityLibraryOperatorProposalEvidenceIntakeChecklist(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistResponse> {
    const url = this.url(this.endpoints.capabilityLibraryOperatorProposalEvidenceIntakeChecklist());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeChecklistPack)
      .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeChecklistPack => item !== null);
    const sourcePlanRaw = (json as Record<string, unknown>).source_proposal_evidence_plan;
    const sourcePlan = isRecord(sourcePlanRaw)
      ? {
          status: safeString(sourcePlanRaw.status, "") || undefined,
          candidate_capability_count: safeNumber(sourcePlanRaw.candidate_capability_count, 0),
          proposal_evidence_missing_count: safeNumber(sourcePlanRaw.proposal_evidence_missing_count, 0),
          proposal_evidence_ready_count: safeNumber(sourcePlanRaw.proposal_evidence_ready_count, 0),
          proposal_review_missing_count: safeNumber(sourcePlanRaw.proposal_review_missing_count, 0),
          next_smallest_truthful_gap:
            safeString(sourcePlanRaw.next_smallest_truthful_gap, "") || undefined,
        }
      : undefined;
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      operator_evidence_intake_checklist_ready:
        typeof (json as Record<string, unknown>).operator_evidence_intake_checklist_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).operator_evidence_intake_checklist_ready)
          : undefined,
      candidate_pack_count: safeNumber((json as Record<string, unknown>).candidate_pack_count, packs.length),
      candidate_capability_count: safeNumber((json as Record<string, unknown>).candidate_capability_count, 0),
      evidence_ref_required_count: safeNumber((json as Record<string, unknown>).evidence_ref_required_count, 0),
      source_proposal_evidence_plan: sourcePlan,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      capability_preview_limit: safeNumber((json as Record<string, unknown>).capability_preview_limit, 0) || undefined,
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only operator proposal-evidence worksheet rows with blank evidence-ref slots.
   */
  async listCapabilityLibraryOperatorProposalEvidenceIntakeWorksheet(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetResponse> {
    const url = this.url(this.endpoints.capabilityLibraryOperatorProposalEvidenceIntakeWorksheet());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPack)
      .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeWorksheetPack => item !== null);
    const sourcePlanRaw = (json as Record<string, unknown>).source_proposal_evidence_plan;
    const sourcePlan = isRecord(sourcePlanRaw)
      ? {
          status: safeString(sourcePlanRaw.status, "") || undefined,
          candidate_capability_count: safeNumber(sourcePlanRaw.candidate_capability_count, 0),
          proposal_evidence_missing_count: safeNumber(sourcePlanRaw.proposal_evidence_missing_count, 0),
          proposal_evidence_ready_count: safeNumber(sourcePlanRaw.proposal_evidence_ready_count, 0),
          proposal_review_missing_count: safeNumber(sourcePlanRaw.proposal_review_missing_count, 0),
          next_smallest_truthful_gap:
            safeString(sourcePlanRaw.next_smallest_truthful_gap, "") || undefined,
        }
      : undefined;
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      operator_evidence_intake_worksheet_ready:
        typeof (json as Record<string, unknown>).operator_evidence_intake_worksheet_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).operator_evidence_intake_worksheet_ready)
          : undefined,
      worksheet_pack_count: safeNumber((json as Record<string, unknown>).worksheet_pack_count, packs.length),
      worksheet_row_count: safeNumber((json as Record<string, unknown>).worksheet_row_count, 0),
      evidence_ref_required_count: safeNumber((json as Record<string, unknown>).evidence_ref_required_count, 0),
      source_proposal_evidence_plan: sourcePlan,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      row_preview_limit: safeNumber((json as Record<string, unknown>).row_preview_limit, 0) || undefined,
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only operator proposal-evidence export rows for offline evidence-ref collection.
   */
  async listCapabilityLibraryOperatorProposalEvidenceIntakeExport(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportResponse> {
    const url = this.url(this.endpoints.capabilityLibraryOperatorProposalEvidenceIntakeExport());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeExportPack)
      .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeExportPack => item !== null);
    const sourcePlanRaw = (json as Record<string, unknown>).source_proposal_evidence_plan;
    const sourcePlan = isRecord(sourcePlanRaw)
      ? {
          status: safeString(sourcePlanRaw.status, "") || undefined,
          candidate_capability_count: safeNumber(sourcePlanRaw.candidate_capability_count, 0),
          proposal_evidence_missing_count: safeNumber(sourcePlanRaw.proposal_evidence_missing_count, 0),
          proposal_evidence_ready_count: safeNumber(sourcePlanRaw.proposal_evidence_ready_count, 0),
          proposal_review_missing_count: safeNumber(sourcePlanRaw.proposal_review_missing_count, 0),
          next_smallest_truthful_gap:
            safeString(sourcePlanRaw.next_smallest_truthful_gap, "") || undefined,
        }
      : undefined;
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      operator_evidence_intake_export_ready:
        typeof (json as Record<string, unknown>).operator_evidence_intake_export_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).operator_evidence_intake_export_ready)
          : undefined,
      export_pack_count: safeNumber((json as Record<string, unknown>).export_pack_count, packs.length),
      export_row_count: safeNumber((json as Record<string, unknown>).export_row_count, 0),
      exported_row_count: safeNumber((json as Record<string, unknown>).exported_row_count, 0),
      evidence_ref_required_count: safeNumber((json as Record<string, unknown>).evidence_ref_required_count, 0),
      export_rows_truncated: Boolean((json as Record<string, unknown>).export_rows_truncated ?? false),
      row_limit: safeNumber((json as Record<string, unknown>).row_limit, 0) || undefined,
      source_proposal_evidence_plan: sourcePlan,
      export_schema: isRecord((json as Record<string, unknown>).export_schema)
        ? ((json as Record<string, unknown>).export_schema as Record<string, unknown>)
        : undefined,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * Preview operator-filled proposal-evidence export rows without mutating registry metadata.
   */
  async previewCapabilityLibraryOperatorProposalEvidenceIntakeImport(
    req: PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewResponse> {
    const rows = Array.isArray(req?.rows) ? req.rows : [];
    const url = this.url(this.endpoints.capabilityLibraryOperatorProposalEvidenceIntakeImportPreview());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({
        ...req,
        actor: pluginMutationActor(req.actor),
        rows,
      }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
    if (!isRecord(json)) return { ok: false, ready_rows: [], pending_rows: [], invalid_rows: [], apply_payload_groups: [] };

    const readyRowsRaw = safeUnknownArray((json as Record<string, unknown>).ready_rows) ?? [];
    const pendingRowsRaw = safeUnknownArray((json as Record<string, unknown>).pending_rows) ?? [];
    const invalidRowsRaw = safeUnknownArray((json as Record<string, unknown>).invalid_rows) ?? [];
    const groupsRaw = safeUnknownArray((json as Record<string, unknown>).apply_payload_groups) ?? [];
    const readyRows = readyRowsRaw
      .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow)
      .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow => item !== null);
    const pendingRows = pendingRowsRaw
      .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow)
      .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow => item !== null);
    const invalidRows = invalidRowsRaw
      .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow)
      .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewRow => item !== null);
    const groups = groupsRaw
      .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewGroup)
      .filter(
        (item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeImportPreviewGroup => item !== null,
      );
    const sourcePlanRaw = (json as Record<string, unknown>).source_proposal_evidence_plan;
    const sourcePlan = isRecord(sourcePlanRaw)
      ? {
          status: safeString(sourcePlanRaw.status, "") || undefined,
          candidate_capability_count: safeNumber(sourcePlanRaw.candidate_capability_count, 0),
          proposal_evidence_missing_count: safeNumber(sourcePlanRaw.proposal_evidence_missing_count, 0),
          proposal_evidence_ready_count: safeNumber(sourcePlanRaw.proposal_evidence_ready_count, 0),
          proposal_review_missing_count: safeNumber(sourcePlanRaw.proposal_review_missing_count, 0),
          next_smallest_truthful_gap:
            safeString(sourcePlanRaw.next_smallest_truthful_gap, "") || undefined,
        }
      : undefined;
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      operator_evidence_intake_import_preview_ready:
        typeof (json as Record<string, unknown>).operator_evidence_intake_import_preview_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).operator_evidence_intake_import_preview_ready)
          : undefined,
      input_row_count: safeNumber((json as Record<string, unknown>).input_row_count, rows.length),
      processed_row_count: safeNumber((json as Record<string, unknown>).processed_row_count, 0),
      row_input_truncated: Boolean((json as Record<string, unknown>).row_input_truncated ?? false),
      ready_row_count: safeNumber((json as Record<string, unknown>).ready_row_count, readyRows.length),
      pending_row_count: safeNumber((json as Record<string, unknown>).pending_row_count, pendingRows.length),
      invalid_row_count: safeNumber((json as Record<string, unknown>).invalid_row_count, invalidRows.length),
      apply_group_count: safeNumber((json as Record<string, unknown>).apply_group_count, groups.length),
      apply_groups_truncated: Boolean((json as Record<string, unknown>).apply_groups_truncated ?? false),
      row_limit: safeNumber((json as Record<string, unknown>).row_limit, 0) || undefined,
      apply_group_limit: safeNumber((json as Record<string, unknown>).apply_group_limit, 0) || undefined,
      ready_rows: readyRows,
      ready_rows_truncated: Boolean((json as Record<string, unknown>).ready_rows_truncated ?? false),
      pending_rows: pendingRows,
      pending_rows_truncated: Boolean((json as Record<string, unknown>).pending_rows_truncated ?? false),
      invalid_rows: invalidRows,
      invalid_rows_truncated: Boolean((json as Record<string, unknown>).invalid_rows_truncated ?? false),
      apply_payload_groups: groups,
      source_proposal_evidence_plan: sourcePlan,
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * Audit read-only operator-supplied proposal-evidence refs already recorded by governed apply.
   */
  async listCapabilityLibraryOperatorProposalEvidenceIntakeAudit(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditResponse> {
    const url = this.url(this.endpoints.capabilityLibraryOperatorProposalEvidenceIntakeAudit());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, packs: [] };

    const raw = Array.isArray((json as Record<string, unknown>).packs)
      ? ((json as Record<string, unknown>).packs as unknown[])
      : [];
    const packs = raw
      .map(parseCapabilityLibraryOperatorProposalEvidenceIntakeAuditPack)
      .filter((item): item is PluginCapabilityLibraryOperatorProposalEvidenceIntakeAuditPack => item !== null);
    const sourcePlanRaw = (json as Record<string, unknown>).source_proposal_evidence_plan;
    const sourcePlan = isRecord(sourcePlanRaw)
      ? {
          status: safeString(sourcePlanRaw.status, "") || undefined,
          candidate_capability_count: safeNumber(sourcePlanRaw.candidate_capability_count, 0),
          proposal_evidence_missing_count: safeNumber(sourcePlanRaw.proposal_evidence_missing_count, 0),
          proposal_evidence_ready_count: safeNumber(sourcePlanRaw.proposal_evidence_ready_count, 0),
          proposal_review_missing_count: safeNumber(sourcePlanRaw.proposal_review_missing_count, 0),
          next_smallest_truthful_gap:
            safeString(sourcePlanRaw.next_smallest_truthful_gap, "") || undefined,
        }
      : undefined;
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      operator_evidence_intake_audit_ready:
        typeof (json as Record<string, unknown>).operator_evidence_intake_audit_ready === "boolean"
          ? Boolean((json as Record<string, unknown>).operator_evidence_intake_audit_ready)
          : undefined,
      recorded_pack_count: safeNumber((json as Record<string, unknown>).recorded_pack_count, packs.length),
      recorded_capability_count: safeNumber((json as Record<string, unknown>).recorded_capability_count, 0),
      evidence_ref_count: safeNumber((json as Record<string, unknown>).evidence_ref_count, 0),
      future_review_required_count: safeNumber(
        (json as Record<string, unknown>).future_review_required_count,
        0,
      ),
      source_proposal_evidence_plan: sourcePlan,
      packs,
      packs_truncated: Boolean((json as Record<string, unknown>).packs_truncated ?? false),
      capability_preview_limit: safeNumber((json as Record<string, unknown>).capability_preview_limit, 0) || undefined,
      routes: isRecord((json as Record<string, unknown>).routes)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).routes as Record<string, unknown>).map(([key, value]) => [
              key,
              safeString(value, ""),
            ]),
          )
        : undefined,
      requirements: isRecord((json as Record<string, unknown>).requirements)
        ? Object.fromEntries(
            Object.entries((json as Record<string, unknown>).requirements as Record<string, unknown>)
              .filter(([, value]) => typeof value === "boolean")
              .map(([key, value]) => [key, Boolean(value)]),
          )
        : undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * Preview operator-supplied proposal-evidence references without apply authority.
   */
  async previewCapabilityLibraryOperatorProposalEvidenceIntake(
    req: PluginCapabilityLibraryOperatorProposalEvidenceIntakeRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryOperatorProposalEvidenceIntakeResponse> {
    const evidenceRefs = safeStringArray(req?.evidence_refs) ?? [];
    if (!evidenceRefs.length) {
      throw new Error(
        "PluginBrowserClient.previewCapabilityLibraryOperatorProposalEvidenceIntake requires req.evidence_refs",
      );
    }

    const url = this.url(this.endpoints.capabilityLibraryOperatorProposalEvidenceIntakePreview());
    const body = {
      ...req,
      actor: pluginMutationActor(req.actor),
      pack_ids: safeStringArray(req.pack_ids) ?? [],
      capability_ids: safeStringArray(req.capability_ids) ?? [],
      evidence_refs: evidenceRefs,
      dry_run: true,
      dry_run_fingerprint: undefined,
    };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    return parseCapabilityLibraryOperatorProposalEvidenceIntakeResponse(json, true, evidenceRefs.length);
  }

  /**
   * Dry-run or write governed operator-supplied proposal-evidence references for selected packs.
   */
  async applyCapabilityLibraryOperatorProposalEvidenceIntake(
    req: PluginCapabilityLibraryOperatorProposalEvidenceIntakeRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityLibraryOperatorProposalEvidenceIntakeResponse> {
    const evidenceRefs = safeStringArray(req?.evidence_refs) ?? [];
    if (!evidenceRefs.length) {
      throw new Error(
        "PluginBrowserClient.applyCapabilityLibraryOperatorProposalEvidenceIntake requires req.evidence_refs",
      );
    }

    const url = this.url(this.endpoints.capabilityLibraryOperatorProposalEvidenceIntake());
    const body = {
      ...req,
      actor: pluginMutationActor(req.actor),
      pack_ids: safeStringArray(req.pack_ids) ?? [],
      capability_ids: safeStringArray(req.capability_ids) ?? [],
      evidence_refs: evidenceRefs,
      dry_run: req.dry_run !== false,
    };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Operator proposal-evidence intake denied.", url);
    return parseCapabilityLibraryOperatorProposalEvidenceIntakeResponse(json, body.dry_run, evidenceRefs.length);
  }

  /**
   * List read-only capability-pack operator review decision receipts.
   */
  async listCapabilityPackOperatorReviewDecisions(
    params?: PluginCapabilityPackOperatorReviewDecisionListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityPackOperatorReviewDecisionListResponse> {
    const url = this.url(this.endpoints.capabilityPackOperatorReviewDecisions(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { ok: false, items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : [];
    const items = raw
      .map(parseCapabilityPackOperatorReviewDecision)
      .filter((item): item is PluginCapabilityPackOperatorReviewDecision => item !== null);
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      stage: safeString((json as Record<string, unknown>).stage, "") || undefined,
      items,
      total: safeNumber((json as Record<string, unknown>).total, items.length),
      limit: safeNumber((json as Record<string, unknown>).limit, 0) || undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
      write_route: safeString((json as Record<string, unknown>).write_route, "") || undefined,
    };
  }

  /**
   * Write a governed capability-pack operator review decision receipt.
   */
  async decideCapabilityPackOperatorReview(
    req: PluginCapabilityPackOperatorReviewDecisionRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityPackOperatorReviewDecisionResponse> {
    const packId = (req?.pack_id || "").trim();
    const packVersion = (req?.pack_version || "").trim();
    const action = (req?.action || "").trim();
    if (!packId || !packVersion || !action) {
      throw new Error(
        "PluginBrowserClient.decideCapabilityPackOperatorReview requires req.pack_id, req.pack_version, and req.action",
      );
    }

    const url = this.url(this.endpoints.capabilityPackOperatorReviewDecision());
    const body = { ...req, pack_id: packId, pack_version: packVersion, action, actor: pluginMutationActor(req.actor) };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Capability pack operator review decision denied.", url);
    if (!isRecord(json)) return { ok: true, applied: true, pack_id: packId, pack_version: packVersion };

    const receipt = parseCapabilityPackOperatorReviewDecision((json as Record<string, unknown>).receipt);
    const pack = parseCapabilityPackOperatorReviewPack((json as Record<string, unknown>).pack);
    const allowedActions = safeStringArray((json as Record<string, unknown>).allowed_actions);
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      applied:
        typeof (json as Record<string, unknown>).applied === "boolean"
          ? Boolean((json as Record<string, unknown>).applied)
          : undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      error: safeString((json as Record<string, unknown>).error, "") || undefined,
      allowed_actions: allowedActions,
      pack_id: safeString((json as Record<string, unknown>).pack_id, packId) || packId,
      pack_version: safeString((json as Record<string, unknown>).pack_version, packVersion) || packVersion,
      receipt_id: safeString((json as Record<string, unknown>).receipt_id, "") || undefined,
      receipt_path: safeString((json as Record<string, unknown>).receipt_path, "") || undefined,
      receipt: receipt ?? undefined,
      pack: pack ?? undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * Dry-run or write governed capability-pack operator review decision receipts from the current surface.
   */
  async decideCapabilityPackOperatorReviewBulkFromSurface(
    req: PluginCapabilityPackOperatorReviewBulkDecisionRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityPackOperatorReviewBulkDecisionResponse> {
    const action = (req?.action || "").trim();
    if (!action) {
      throw new Error("PluginBrowserClient.decideCapabilityPackOperatorReviewBulkFromSurface requires req.action");
    }

    const url = this.url(this.endpoints.capabilityPackOperatorReviewBulkDecision());
    const body = {
      ...req,
      action,
      actor: pluginMutationActor(req.actor),
      pack_ids: safeStringArray(req.pack_ids) ?? [],
      dry_run: req.dry_run !== false,
    };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Capability pack bulk operator review decision denied.", url);
    if (!isRecord(json)) return { ok: true, applied: false, dry_run: body.dry_run };

    const plannedRaw = safeUnknownArray((json as Record<string, unknown>).planned) ?? [];
    const recordedRaw = safeUnknownArray((json as Record<string, unknown>).recorded) ?? [];
    const failedRaw = safeUnknownArray((json as Record<string, unknown>).failed) ?? [];
    const skippedRaw = safeUnknownArray((json as Record<string, unknown>).skipped) ?? [];
    const planned = plannedRaw
      .map(parseCapabilityPackOperatorReviewBulkDecisionPlan)
      .filter((item): item is PluginCapabilityPackOperatorReviewBulkDecisionPlan => item !== null);
    const recorded = recordedRaw
      .map(parseCapabilityPackOperatorReviewBulkDecisionRecord)
      .filter((item): item is PluginCapabilityPackOperatorReviewBulkDecisionRecord => item !== null);
    const failed = failedRaw
      .map(parseCapabilityPackOperatorReviewBulkDecisionRecord)
      .filter((item): item is PluginCapabilityPackOperatorReviewBulkDecisionRecord => item !== null);
    const skipped = skippedRaw
      .map(parseCapabilityPackOperatorReviewBulkDecisionRecord)
      .filter((item): item is PluginCapabilityPackOperatorReviewBulkDecisionRecord => item !== null);
    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      applied:
        typeof (json as Record<string, unknown>).applied === "boolean"
          ? Boolean((json as Record<string, unknown>).applied)
          : undefined,
      kind: safeString((json as Record<string, unknown>).kind, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      dry_run:
        typeof (json as Record<string, unknown>).dry_run === "boolean"
          ? Boolean((json as Record<string, unknown>).dry_run)
          : undefined,
      error: safeString((json as Record<string, unknown>).error, "") || undefined,
      allowed_actions: safeStringArray((json as Record<string, unknown>).allowed_actions),
      batch_id: safeString((json as Record<string, unknown>).batch_id, "") || undefined,
      planned_pack_count: safeNumber((json as Record<string, unknown>).planned_pack_count, planned.length),
      planned_capability_count: safeNumber((json as Record<string, unknown>).planned_capability_count, 0),
      recorded_pack_count: safeNumber((json as Record<string, unknown>).recorded_pack_count, recorded.length),
      recorded_capability_count: safeNumber((json as Record<string, unknown>).recorded_capability_count, 0),
      planned,
      recorded,
      failed,
      skipped,
      before: isRecord((json as Record<string, unknown>).before)
        ? ((json as Record<string, unknown>).before as Record<string, unknown>)
        : undefined,
      promotion_discipline: isRecord((json as Record<string, unknown>).promotion_discipline)
        ? ((json as Record<string, unknown>).promotion_discipline as Record<string, unknown>)
        : undefined,
      next_smallest_truthful_gap:
        safeString((json as Record<string, unknown>).next_smallest_truthful_gap, "") || undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only Forge proposal records.
   */
  async listForgeProposals(
    params?: PluginForgeArtifactListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginForgeProposalListResponse> {
    const url = this.url(this.endpoints.proposalsList(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).proposals)
          ? ((json as Record<string, unknown>).proposals as unknown[])
          : [];

    const items = raw.map(parseForgeProposal).filter((x): x is PluginForgeProposal => x !== null);
    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const offset = safeNumber((json as Record<string, unknown>).offset, 0);
    const limit = safeNumber((json as Record<string, unknown>).limit, 0);

    return {
      items,
      total: total > 0 ? total : undefined,
      offset: offset >= 0 ? offset : undefined,
      limit: limit > 0 ? limit : undefined,
    };
  }

  /**
   * List read-only Forge proposal review receipts.
   */
  async listForgeProposalReviews(
    params?: PluginForgeArtifactListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginForgeProposalReviewListResponse> {
    const url = this.url(this.endpoints.proposalReviewsList(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).reviews)
          ? ((json as Record<string, unknown>).reviews as unknown[])
          : [];

    const items = raw.map(parseForgeProposalReview).filter((x): x is PluginForgeProposalReview => x !== null);
    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const offset = safeNumber((json as Record<string, unknown>).offset, 0);
    const limit = safeNumber((json as Record<string, unknown>).limit, 0);

    return {
      items,
      total: total > 0 ? total : undefined,
      offset: offset >= 0 ? offset : undefined,
      limit: limit > 0 ? limit : undefined,
    };
  }

  /**
   * Apply a governed Forge proposal decision.
   */
  async decideForgeProposal(
    req: PluginForgeProposalDecisionRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginForgeProposalDecisionResponse> {
    const id = (req?.id || "").trim();
    const action = (req?.action || "").trim();
    if (!id || !action) throw new Error("PluginBrowserClient.decideForgeProposal requires req.id and req.action");

    const url = this.url(this.endpoints.proposalDecision());
    const body = { ...req, id, action, actor: pluginMutationActor(req.actor) };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Forge proposal decision denied.", url);
    if (!isRecord(json)) return { ok: true, applied: true, proposal_id: id };

    const reviewReceipt = parseForgeProposalReview((json as Record<string, unknown>).review_receipt);
    const item = parseForgeProposal((json as Record<string, unknown>).item);
    const allowedActions = safeStringArray((json as Record<string, unknown>).allowed_actions);

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? false),
      applied:
        typeof (json as Record<string, unknown>).applied === "boolean"
          ? Boolean((json as Record<string, unknown>).applied)
          : undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      error: safeString((json as Record<string, unknown>).error, "") || undefined,
      allowed_actions: allowedActions,
      proposal_id: safeString((json as Record<string, unknown>).proposal_id, id) || id,
      plugin_id: safeString((json as Record<string, unknown>).plugin_id, "") || undefined,
      review_receipt_id: safeString((json as Record<string, unknown>).review_receipt_id, "") || undefined,
      review_receipt: reviewReceipt ?? undefined,
      item: item ?? undefined,
      governance: isRecord((json as Record<string, unknown>).governance)
        ? ((json as Record<string, unknown>).governance as Record<string, unknown>)
        : undefined,
    };
  }

  /**
   * List read-only Forge promotion receipts.
   */
  async listForgePromotions(
    params?: PluginForgeArtifactListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginForgePromotionListResponse> {
    const url = this.url(this.endpoints.promotionsList(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).promotions)
          ? ((json as Record<string, unknown>).promotions as unknown[])
          : [];

    const items = raw.map(parseForgePromotion).filter((x): x is PluginForgePromotion => x !== null);
    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const offset = safeNumber((json as Record<string, unknown>).offset, 0);
    const limit = safeNumber((json as Record<string, unknown>).limit, 0);

    return {
      items,
      total: total > 0 ? total : undefined,
      offset: offset >= 0 ? offset : undefined,
      limit: limit > 0 ? limit : undefined,
    };
  }

  /**
   * List read-only Forge capability catalog entries and coherence evidence.
   */
  async listCapabilityCatalog(
    params?: PluginCapabilityCatalogParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginCapabilityCatalogResponse> {
    const url = this.url(this.endpoints.capabilityCatalog(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).capabilities)
          ? ((json as Record<string, unknown>).capabilities as unknown[])
          : [];

    const items = raw.map(parseCapabilityCatalogEntry).filter((x): x is PluginCapabilityCatalogEntry => x !== null);
    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const offset = safeNumber((json as Record<string, unknown>).offset, 0);
    const limit = safeNumber((json as Record<string, unknown>).limit, 0);
    const filters = isRecord((json as Record<string, unknown>).filters)
      ? Object.fromEntries(
          Object.entries((json as Record<string, unknown>).filters as Record<string, unknown>).map(([key, value]) => [
            key,
            safeString(value, ""),
          ]),
        )
      : undefined;

    return {
      items,
      total: total > 0 ? total : undefined,
      offset: offset >= 0 ? offset : undefined,
      limit: limit > 0 ? limit : undefined,
      summary: parseCapabilityCatalogSummary((json as Record<string, unknown>).summary),
      coherence: parseCapabilityCatalogCoherence((json as Record<string, unknown>).coherence),
      catalog: isRecord((json as Record<string, unknown>).catalog)
        ? ((json as Record<string, unknown>).catalog as Record<string, unknown>)
        : undefined,
      filters,
    };
  }

  /**
   * Get a single plugin detail by id.
   */
  async get(
    id: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginGetResponse> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("PluginBrowserClient.get requires a non-empty id");

    const url = this.url(this.endpoints.get(clean));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    // Accept { item }, { plugin }, or direct object
    const raw =
      isRecord(json) && (json as Record<string, unknown>).item !== undefined
        ? (json as Record<string, unknown>).item
        : isRecord(json) && (json as Record<string, unknown>).plugin !== undefined
          ? (json as Record<string, unknown>).plugin
          : json;

    return { item: parsePluginDetail(raw) };
  }

  /**
   * List plugin tools/actions with filtering/pagination.
   */
  async listTools(
    params?: PluginToolListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginToolListResponse> {
    const url = this.url(this.endpoints.toolsList(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).tools)
          ? ((json as Record<string, unknown>).tools as unknown[])
          : [];

    const items = raw.map(parsePluginTool).filter((x): x is PluginToolRef => x !== null);
    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const offset = safeNumber((json as Record<string, unknown>).offset, 0);
    const limit = safeNumber((json as Record<string, unknown>).limit, 0);

    return {
      items,
      total: total > 0 ? total : undefined,
      offset: offset >= 0 ? offset : undefined,
      limit: limit > 0 ? limit : undefined,
    };
  }

  /**
   * Get a single plugin tool/action detail by id.
   */
  async getTool(
    id: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginToolGetResponse> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("PluginBrowserClient.getTool requires a non-empty id");

    const url = this.url(this.endpoints.toolsGet(clean));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    const raw =
      isRecord(json) && (json as Record<string, unknown>).item !== undefined
        ? (json as Record<string, unknown>).item
        : isRecord(json) && (json as Record<string, unknown>).tool !== undefined
          ? (json as Record<string, unknown>).tool
          : json;

    return { item: parsePluginTool(raw) };
  }

  /**
   * Export plugin tools catalog as a blob.
   */
  async exportTools(
    format: PluginToolsExportFormat,
    params?: PluginToolListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<Blob> {
    const url = this.url(this.endpoints.toolsExport(format, params));
    return await this.fetchBlob(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
  }

  /**
   * Run a plugin tool/action by tool id.
   */
  async runTool(
    req: PluginToolRunRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginRunResponse> {
    const id = (req?.id || "").trim();
    if (!id) throw new Error("PluginBrowserClient.runTool requires req.id");

    const url = this.url(this.endpoints.toolsRun());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({ ...req, id }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
    return this.parseRunResponse(json);
  }

  /**
   * Batch get (dedupe + bounded concurrency; preserves input order; drops nulls).
   */
  async getMany(
    ids: string[],
    opts?: { signal?: AbortSignal; timeoutMs?: number; concurrency?: number; tolerateFailures?: boolean },
  ): Promise<PluginDetail[]> {
    const original = (ids ?? []).map((s) => (s || "").trim()).filter((s) => s.length > 0);
    if (!original.length) return [];

    const unique: string[] = [];
    const seen = new Set<string>();
    for (const id of original) {
      if (!seen.has(id)) {
        seen.add(id);
        unique.push(id);
      }
    }

    const concurrency = clamp(Math.floor(opts?.concurrency ?? 6), 1, 16);
    const tolerateFailures = opts?.tolerateFailures ?? true;

    const map = new Map<string, PluginDetail | null>();
    for (const id of unique) map.set(id, null);

    let cursor = 0;
    const worker = async (): Promise<void> => {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const i = cursor++;
        if (i >= unique.length) return;
        const id = unique[i];

        try {
          const r = await this.get(id, { signal: opts?.signal, timeoutMs: opts?.timeoutMs });
          map.set(id, r.item);
        } catch (err) {
          if (!tolerateFailures) throw err;
          map.set(id, null);
        }
      }
    };

    await Promise.all(Array.from({ length: Math.min(concurrency, unique.length) }, () => worker()));

    const out: PluginDetail[] = [];
    for (const id of original) {
      const v = map.get(id) ?? null;
      if (v) out.push(v);
    }
    return out;
  }

  /**
   * Enable a plugin (may be policy/approval gated).
   */
  async enable(
    req: PluginToggleRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginToggleResponse> {
    const id = (req?.id || "").trim();
    if (!id) throw new Error("PluginBrowserClient.enable requires req.id");

    const url = this.url(this.endpoints.enable());
    const body = { ...req, id, actor: pluginMutationActor(req.actor) };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Plugin enable denied.", url);
    if (!isRecord(json)) return { ok: true, id, enabled: true, status: "enabled" };

    const enabled = safeBool((json as Record<string, unknown>).enabled, true);
    const status = safeString((json as Record<string, unknown>).status, enabled ? "enabled" : "disabled");
    const promotionReceipt = parseForgePromotion((json as Record<string, unknown>).promotion_receipt);

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, id),
      enabled,
      status,
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
      promotion_status: safeString((json as Record<string, unknown>).promotion_status, "") || undefined,
      promotion_receipt_id: safeString((json as Record<string, unknown>).promotion_receipt_id, "") || undefined,
      promotion_receipt_path: safeString((json as Record<string, unknown>).promotion_receipt_path, "") || undefined,
      promotion_receipt: promotionReceipt ?? undefined,
    };
  }

  /**
   * Disable a plugin (may be policy/approval gated).
   */
  async disable(
    req: PluginToggleRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginToggleResponse> {
    const id = (req?.id || "").trim();
    if (!id) throw new Error("PluginBrowserClient.disable requires req.id");

    const url = this.url(this.endpoints.disable());
    const body = { ...req, id, actor: pluginMutationActor(req.actor) };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Plugin disable denied.", url);
    if (!isRecord(json)) return { ok: true, id, enabled: false, status: "disabled" };

    const enabled = safeBool((json as Record<string, unknown>).enabled, false);
    const status = safeString((json as Record<string, unknown>).status, enabled ? "enabled" : "disabled");

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, id),
      enabled,
      status,
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
    };
  }

  /**
   * Install a plugin (approval-gated / queued installs supported).
   */
  async install(
    req: PluginInstallRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginInstallResponse> {
    const kind = (req?.source_kind || "").trim();
    const ref = (req?.source_ref || "").trim();
    if (!kind || !ref) throw new Error("PluginBrowserClient.install requires source_kind and source_ref");

    const url = this.url(this.endpoints.install());
    const body = { ...req, source_kind: kind, source_ref: ref, actor: pluginMutationActor(req.actor) };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Plugin install denied.", url);
    if (!isRecord(json)) return { ok: true };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      plugin_id:
        safeString((json as Record<string, unknown>).plugin_id, "") ||
        safeString((json as Record<string, unknown>).id, "") ||
        undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      operation_id: safeString((json as Record<string, unknown>).operation_id, "") || undefined,
    };
  }

  /**
   * Uninstall a plugin.
   */
  async uninstall(
    req: PluginUninstallRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginUninstallResponse> {
    const id = (req?.id || "").trim();
    if (!id) throw new Error("PluginBrowserClient.uninstall requires req.id");

    const url = this.url(this.endpoints.uninstall());
    const body = { ...req, id, actor: pluginMutationActor(req.actor) };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Plugin uninstall denied.", url);
    if (!isRecord(json)) return { ok: true, id, status: "uninstalling" };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, id) || id,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      operation_id: safeString((json as Record<string, unknown>).operation_id, "") || undefined,
    };
  }

  /**
   * Run a plugin action (generic).
   *
   * This is intentionally loose:
   * - Some backends may run synchronously and return output immediately.
   * - Others may enqueue work and return an operation_id.
   * - Some may require approvals and return approval_id.
   */
  async run(
    req: PluginRunRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginRunResponse> {
    const id = (req?.id || "").trim();
    const action = (req?.action || "").trim();
    if (!id || !action) throw new Error("PluginBrowserClient.run requires req.id and req.action");

    const url = this.url(this.endpoints.run());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({ ...req, id, action }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
    return this.parseRunResponse(json);
  }

  /**
   * Reload plugin registry / re-scan (optional endpoint).
   */
  async reload(
    opts?: { reason?: string; actor?: string; signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginReloadResponse> {
    const ep = this.endpoints.reload;
    if (!ep) {
      throw new Error("PluginBrowserClient.reload is not configured (endpoints.reload missing)");
    }

    const url = this.url(ep());
    const body = {
      actor: pluginMutationActor(opts?.actor),
      reason: opts?.reason?.trim() || "reload",
    };
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    assertPluginMutationAllowed(json, "Plugin reload denied.", url);
    if (!isRecord(json)) return { ok: true };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
    };
  }
}
