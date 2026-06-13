export const DEFAULT_INGEST_READBACK_ACTOR = "chat_ui.ingest";

export type SourcePermissionProfile = {
  read: boolean;
  execute: boolean;
  network: boolean;
  write: boolean;
  destructive: boolean;
};

export type IngestSourceRecord = {
  id: string;
  type: string;
  original_path?: string;
  canonical_path?: string;
  created_at?: string;
  updated_at?: string;
  fingerprint?: string;
  status: string;
  permissions: SourcePermissionProfile;
  derived_artifacts: string[];
  receipts: string[];
};

export type RepoRiskSignal = {
  id: string;
  severity: string;
  path?: string;
  detail?: string;
};

export type IngestRepoMap = {
  source_id: string;
  repo_root: string;
  is_git_repo: boolean;
  detected_languages: string[];
  package_managers: string[];
  manifest_files: string[];
  test_files: string[];
  docs_readmes: string[];
  source_directories: string[];
  dependency_manifests: string[];
  license_file?: string;
  risk_signals: RepoRiskSignal[];
  suggested_validation_commands: Record<string, unknown>[];
  protected_sensitive_files: Record<string, unknown>[];
  files_inspected_count: number;
  warnings: string[];
};

export type IngestRepoMapReadback = {
  artifact_path: string;
  repo_map: IngestRepoMap;
};

export type IngestCapabilityCandidate = {
  id: string;
  name: string;
  source_id: string;
  source_type: string;
  status: string;
  description?: string;
  permissions_required: SourcePermissionProfile;
  risk_level: string;
  suggested_validation: string[];
  receipts: string[];
  promotion_requirements: string[];
};

export type IngestLabArtifactReadback = {
  artifact_path: string;
  preflight?: Record<string, unknown>;
  approval_consumption?: Record<string, unknown>;
  approval_consumption_record?: Record<string, unknown>;
  noop_runner_envelope?: Record<string, unknown>;
  noop_runner_transcript?: Record<string, unknown>;
  noop_runner_identity_binding?: Record<string, unknown>;
  source_mount_readiness?: Record<string, unknown>;
  source_mount_contract?: Record<string, unknown>;
  approval_handoff?: Record<string, unknown>;
  receipt_sink_reservation?: Record<string, unknown>;
  execution_receipt_write_readiness?: Record<string, unknown>;
  execution_receipt_prewrite_binding?: Record<string, unknown>;
  execution_receipt_writer_preflight?: Record<string, unknown>;
  run_boundary_preflight?: Record<string, unknown>;
  sandbox_provider_contract?: Record<string, unknown>;
  sandbox_provider_binding?: Record<string, unknown>;
  sandbox_provider_selection?: Record<string, unknown>;
  sandbox_provider_verifier?: Record<string, unknown>;
  sandbox_provider_runtime_probe?: Record<string, unknown>;
  sandbox_provider_runtime_probe_harness?: Record<string, unknown>;
  sandbox_provider_runtime_probe_runner_readiness?: Record<string, unknown>;
  sandbox_provider_runtime_probe_runner_binding?: Record<string, unknown>;
  sandbox_provider_runtime_probe_runner_enforcement?: Record<string, unknown>;
  sandbox_provider_runtime_probe_execution_boundary?: Record<string, unknown>;
  sandbox_provider_runtime_probe_refusal?: Record<string, unknown>;
  sandbox_provider_runtime_probe_approval_request?: Record<string, unknown>;
  sandbox_provider_runtime_probe_approval_consumption?: Record<string, unknown>;
  sandbox_provider_runtime_probe_invocation_boundary?: Record<string, unknown>;
  sandbox_provider_runtime_probe_runner_pre_execution_boundary?: Record<string, unknown>;
  sandbox_provider_runtime_probe_runner_control_binding?: Record<string, unknown>;
  sandboxed_rebuild_run_test_boundary?: Record<string, unknown>;
  sandboxed_rebuild_run_test_approval_request?: Record<string, unknown>;
  sandboxed_rebuild_run_test_approval_consumption?: Record<string, unknown>;
  sandboxed_rebuild_run_test_runner_binding?: Record<string, unknown>;
  sandboxed_rebuild_run_test_sandbox_policy?: Record<string, unknown>;
  execution_receipt?: Record<string, unknown>;
  runner_command_allowlist?: Record<string, unknown>;
  runner_command_allowlist_declaration?: Record<string, unknown>;
  runner_command_allowlist_enforcement?: Record<string, unknown>;
  runner_sandbox_readiness?: Record<string, unknown>;
  runner_contract?: Record<string, unknown>;
  runner_readiness?: Record<string, unknown>;
  runner_binding?: Record<string, unknown>;
  runner_enforcement?: Record<string, unknown>;
};

export type IngestReadbackCounts = {
  sources: number;
  repo_maps: number;
  capability_candidates: number;
  lab_preflights: number;
  approval_consumption_preflights: number;
  approval_consumptions: number;
  noop_runner_envelopes: number;
  noop_runner_transcripts: number;
  noop_runner_identity_bindings: number;
  source_mount_readiness: number;
  source_mount_contracts: number;
  approval_consumption_handoffs: number;
  execution_receipt_sink_reservations: number;
  execution_receipt_write_readiness: number;
  execution_receipt_prewrite_bindings: number;
  execution_receipt_writer_preflights: number;
  run_boundary_preflights: number;
  sandbox_provider_contracts: number;
  sandbox_provider_bindings: number;
  sandbox_provider_selections: number;
  sandbox_provider_verifier_preflights: number;
  sandbox_provider_runtime_probe_preflights: number;
  sandbox_provider_runtime_probe_harness_preflights: number;
  sandbox_provider_runtime_probe_runner_readiness: number;
  sandbox_provider_runtime_probe_runner_bindings: number;
  sandbox_provider_runtime_probe_runner_enforcements: number;
  sandbox_provider_runtime_probe_execution_boundaries: number;
  sandbox_provider_runtime_probe_refusals: number;
  sandbox_provider_runtime_probe_approval_requests: number;
  sandbox_provider_runtime_probe_approval_consumptions: number;
  sandbox_provider_runtime_probe_invocation_boundaries: number;
  sandbox_provider_runtime_probe_runner_pre_execution_boundaries: number;
  sandbox_provider_runtime_probe_runner_control_bindings: number;
  sandboxed_rebuild_run_test_boundaries: number;
  sandboxed_rebuild_run_test_approval_requests: number;
  sandboxed_rebuild_run_test_approval_consumptions: number;
  sandboxed_rebuild_run_test_runner_bindings: number;
  sandboxed_rebuild_run_test_sandbox_policies: number;
  execution_receipts: number;
  runner_command_allowlists: number;
  runner_command_allowlist_declarations: number;
  runner_command_allowlist_enforcements: number;
  runner_sandbox_readiness: number;
  runner_contracts: number;
  runner_readiness: number;
  runner_bindings: number;
  runner_enforcements: number;
};

export type IngestExecutionReadback = {
  executed: boolean;
  execution_authority: boolean;
  ran_repo_scripts: boolean;
  ran_install?: boolean;
  ran_build?: boolean;
  ran_tests?: boolean;
  network_accessed: boolean;
  wrote_to_repo?: boolean;
  reason?: string;
};

export type IngestGovernanceReadback = {
  gate?: string;
  reason?: string;
  next_step?: string;
};

export type IngestReadbackResponse = {
  ok: boolean;
  kind?: string;
  status: string;
  error?: string;
  source_id?: string;
  limit: number;
  sources: IngestSourceRecord[];
  repo_maps: IngestRepoMapReadback[];
  capability_candidates: IngestCapabilityCandidate[];
  lab_preflights: IngestLabArtifactReadback[];
  approval_consumption_preflights: IngestLabArtifactReadback[];
  approval_consumptions: IngestLabArtifactReadback[];
  noop_runner_envelopes: IngestLabArtifactReadback[];
  noop_runner_transcripts: IngestLabArtifactReadback[];
  noop_runner_identity_bindings: IngestLabArtifactReadback[];
  source_mount_readiness: IngestLabArtifactReadback[];
  source_mount_contracts: IngestLabArtifactReadback[];
  approval_consumption_handoffs: IngestLabArtifactReadback[];
  execution_receipt_sink_reservations: IngestLabArtifactReadback[];
  execution_receipt_write_readiness: IngestLabArtifactReadback[];
  execution_receipt_prewrite_bindings: IngestLabArtifactReadback[];
  execution_receipt_writer_preflights: IngestLabArtifactReadback[];
  run_boundary_preflights: IngestLabArtifactReadback[];
  sandbox_provider_contracts: IngestLabArtifactReadback[];
  sandbox_provider_bindings: IngestLabArtifactReadback[];
  sandbox_provider_selections: IngestLabArtifactReadback[];
  sandbox_provider_verifier_preflights: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_preflights: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_harness_preflights: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_runner_readiness: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_runner_bindings: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_runner_enforcements: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_execution_boundaries: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_refusals: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_approval_requests: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_approval_consumptions: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_invocation_boundaries: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_runner_pre_execution_boundaries: IngestLabArtifactReadback[];
  sandbox_provider_runtime_probe_runner_control_bindings: IngestLabArtifactReadback[];
  sandboxed_rebuild_run_test_boundaries: IngestLabArtifactReadback[];
  sandboxed_rebuild_run_test_approval_requests: IngestLabArtifactReadback[];
  sandboxed_rebuild_run_test_approval_consumptions: IngestLabArtifactReadback[];
  sandboxed_rebuild_run_test_runner_bindings: IngestLabArtifactReadback[];
  sandboxed_rebuild_run_test_sandbox_policies: IngestLabArtifactReadback[];
  execution_receipts: IngestLabArtifactReadback[];
  runner_command_allowlists: IngestLabArtifactReadback[];
  runner_command_allowlist_declarations: IngestLabArtifactReadback[];
  runner_command_allowlist_enforcements: IngestLabArtifactReadback[];
  runner_sandbox_readiness: IngestLabArtifactReadback[];
  runner_contracts: IngestLabArtifactReadback[];
  runner_readiness: IngestLabArtifactReadback[];
  runner_bindings: IngestLabArtifactReadback[];
  runner_enforcements: IngestLabArtifactReadback[];
  counts: IngestReadbackCounts;
  execution: IngestExecutionReadback;
  governance?: IngestGovernanceReadback;
  receipts_written: boolean;
  artifacts_written: boolean;
};

export type IngestReadbackPanelModel = {
  status: string;
  sourceCount: number;
  repoMapCount: number;
  candidateCount: number;
  labPreflightCount: number;
  approvalConsumptionCount: number;
  noopRunnerEnvelopeCount: number;
  noopRunnerTranscriptCount: number;
  noopRunnerIdentityBindingCount: number;
  sourceMountReadinessCount: number;
  sourceMountContractCount: number;
  approvalConsumptionHandoffCount: number;
  executionReceiptSinkReservationCount: number;
  executionReceiptWriteReadinessCount: number;
  executionReceiptPrewriteBindingCount: number;
  executionReceiptWriterPreflightCount: number;
  runBoundaryPreflightCount: number;
  sandboxProviderContractCount: number;
  sandboxProviderBindingCount: number;
  sandboxProviderSelectionCount: number;
  sandboxProviderVerifierCount: number;
  sandboxProviderRuntimeProbeCount: number;
  sandboxProviderRuntimeProbeHarnessCount: number;
  sandboxProviderRuntimeProbeRunnerReadinessCount: number;
  sandboxProviderRuntimeProbeRunnerBindingCount: number;
  sandboxProviderRuntimeProbeRunnerEnforcementCount: number;
  sandboxProviderRuntimeProbeExecutionBoundaryCount: number;
  sandboxProviderRuntimeProbeRefusalCount: number;
  sandboxProviderRuntimeProbeApprovalRequestCount: number;
  sandboxProviderRuntimeProbeApprovalConsumptionCount: number;
  sandboxProviderRuntimeProbeInvocationBoundaryCount: number;
  sandboxProviderRuntimeProbeRunnerPreExecutionBoundaryCount: number;
  sandboxProviderRuntimeProbeRunnerControlBindingCount: number;
  sandboxedRebuildRunTestBoundaryCount: number;
  sandboxedRebuildRunTestApprovalRequestCount: number;
  sandboxedRebuildRunTestApprovalConsumptionCount: number;
  sandboxedRebuildRunTestRunnerBindingCount: number;
  sandboxedRebuildRunTestSandboxPolicyCount: number;
  executionReceiptCount: number;
  runnerCommandAllowlistCount: number;
  runnerCommandAllowlistDeclarationCount: number;
  runnerCommandAllowlistEnforcementCount: number;
  runnerSandboxReadinessCount: number;
  runnerContractCount: number;
  runnerReadinessCount: number;
  runnerBindingCount: number;
  runnerEnforcementCount: number;
  guardLines: string[];
  sources: IngestSourceRecord[];
  riskSignals: RepoRiskSignal[];
  candidates: IngestCapabilityCandidate[];
  blockers: string[];
  sensitiveFileCount: number;
  latestArtifactPaths: string[];
};

export class IngestApiError extends Error {
  readonly status?: number;
  readonly url?: string;

  constructor(message: string, opts?: { status?: number; url?: string }) {
    super(message);
    this.name = "IngestApiError";
    this.status = opts?.status;
    this.url = opts?.url;
  }
}

export function trimTrailingSlashes(value: string): string {
  let end = value.length;
  while (end > 0 && value.charCodeAt(end - 1) === 47) {
    end -= 1;
  }
  return value.slice(0, end);
}

function safeString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function safeNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function safeBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => safeString(item).trim()).filter(Boolean);
}

function safeRecordList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord);
}

function parsePermissions(raw: unknown): SourcePermissionProfile {
  const data = isRecord(raw) ? raw : {};
  return {
    read: safeBoolean(data.read, true),
    execute: safeBoolean(data.execute),
    network: safeBoolean(data.network),
    write: safeBoolean(data.write),
    destructive: safeBoolean(data.destructive),
  };
}

function parseSource(raw: unknown): IngestSourceRecord | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id).trim();
  if (!id) return null;
  return {
    id,
    type: safeString(raw.type).trim() || "unknown",
    original_path: safeString(raw.original_path).trim() || undefined,
    canonical_path: safeString(raw.canonical_path).trim() || undefined,
    created_at: safeString(raw.created_at).trim() || undefined,
    updated_at: safeString(raw.updated_at).trim() || undefined,
    fingerprint: safeString(raw.fingerprint).trim() || undefined,
    status: safeString(raw.status).trim() || "incoming",
    permissions: parsePermissions(raw.permissions),
    derived_artifacts: safeStringList(raw.derived_artifacts),
    receipts: safeStringList(raw.receipts),
  };
}

function parseRiskSignal(raw: unknown): RepoRiskSignal | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id).trim();
  if (!id) return null;
  return {
    id,
    severity: safeString(raw.severity).trim() || "medium",
    path: safeString(raw.path).trim() || undefined,
    detail: safeString(raw.detail).trim() || undefined,
  };
}

function parseRepoMap(raw: unknown): IngestRepoMap {
  const data = isRecord(raw) ? raw : {};
  return {
    source_id: safeString(data.source_id).trim(),
    repo_root: safeString(data.repo_root).trim(),
    is_git_repo: safeBoolean(data.is_git_repo),
    detected_languages: safeStringList(data.detected_languages),
    package_managers: safeStringList(data.package_managers),
    manifest_files: safeStringList(data.manifest_files),
    test_files: safeStringList(data.test_files),
    docs_readmes: safeStringList(data.docs_readmes),
    source_directories: safeStringList(data.source_directories),
    dependency_manifests: safeStringList(data.dependency_manifests),
    license_file: safeString(data.license_file).trim() || undefined,
    risk_signals: Array.isArray(data.risk_signals)
      ? data.risk_signals.map(parseRiskSignal).filter((item): item is RepoRiskSignal => item !== null)
      : [],
    suggested_validation_commands: safeRecordList(data.suggested_validation_commands),
    protected_sensitive_files: safeRecordList(data.protected_sensitive_files),
    files_inspected_count: safeNumber(data.files_inspected_count),
    warnings: safeStringList(data.warnings),
  };
}

function parseRepoMapReadback(raw: unknown): IngestRepoMapReadback | null {
  if (!isRecord(raw)) return null;
  const repoMap = parseRepoMap(raw.repo_map);
  if (!repoMap.source_id && !repoMap.repo_root) return null;
  return {
    artifact_path: safeString(raw.artifact_path).trim(),
    repo_map: repoMap,
  };
}

function parseCapabilityCandidate(raw: unknown): IngestCapabilityCandidate | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id).trim();
  const name = safeString(raw.name).trim();
  const sourceId = safeString(raw.source_id).trim();
  if (!id || !name || !sourceId) return null;
  return {
    id,
    name,
    source_id: sourceId,
    source_type: safeString(raw.source_type).trim() || "unknown",
    status: safeString(raw.status).trim() || "discovered",
    description: safeString(raw.description).trim() || undefined,
    permissions_required: parsePermissions(raw.permissions_required),
    risk_level: safeString(raw.risk_level).trim() || "low",
    suggested_validation: safeStringList(raw.suggested_validation),
    receipts: safeStringList(raw.receipts),
    promotion_requirements: safeStringList(raw.promotion_requirements),
  };
}

function parseLabArtifactReadback(
  raw: unknown,
  key:
    | "preflight"
    | "approval_consumption"
    | "approval_consumption_record"
    | "noop_runner_envelope"
    | "noop_runner_transcript"
    | "noop_runner_identity_binding"
    | "source_mount_readiness"
    | "source_mount_contract"
    | "approval_handoff"
    | "receipt_sink_reservation"
    | "execution_receipt_write_readiness"
    | "execution_receipt_prewrite_binding"
    | "execution_receipt_writer_preflight"
    | "run_boundary_preflight"
    | "sandbox_provider_contract"
    | "sandbox_provider_binding"
    | "sandbox_provider_selection"
    | "sandbox_provider_verifier"
    | "sandbox_provider_runtime_probe"
    | "sandbox_provider_runtime_probe_harness"
    | "sandbox_provider_runtime_probe_runner_readiness"
    | "sandbox_provider_runtime_probe_runner_binding"
    | "sandbox_provider_runtime_probe_runner_enforcement"
    | "sandbox_provider_runtime_probe_execution_boundary"
    | "sandbox_provider_runtime_probe_refusal"
    | "sandbox_provider_runtime_probe_approval_request"
    | "sandbox_provider_runtime_probe_approval_consumption"
    | "sandbox_provider_runtime_probe_invocation_boundary"
    | "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
    | "sandbox_provider_runtime_probe_runner_control_binding"
    | "sandboxed_rebuild_run_test_boundary"
    | "sandboxed_rebuild_run_test_approval_request"
    | "sandboxed_rebuild_run_test_approval_consumption"
    | "sandboxed_rebuild_run_test_runner_binding"
    | "sandboxed_rebuild_run_test_sandbox_policy"
    | "execution_receipt"
    | "runner_command_allowlist"
    | "runner_command_allowlist_declaration"
    | "runner_command_allowlist_enforcement"
    | "runner_sandbox_readiness"
    | "runner_contract"
    | "runner_readiness"
    | "runner_binding"
    | "runner_enforcement",
): IngestLabArtifactReadback | null {
  if (!isRecord(raw)) return null;
  const record = isRecord(raw[key]) ? raw[key] : {};
  return {
    artifact_path: safeString(raw.artifact_path).trim(),
    [key]: record,
  };
}

function parseCounts(raw: unknown): IngestReadbackCounts {
  const data = isRecord(raw) ? raw : {};
  return {
    sources: safeNumber(data.sources),
    repo_maps: safeNumber(data.repo_maps),
    capability_candidates: safeNumber(data.capability_candidates),
    lab_preflights: safeNumber(data.lab_preflights),
    approval_consumption_preflights: safeNumber(data.approval_consumption_preflights),
    approval_consumptions: safeNumber(data.approval_consumptions),
    noop_runner_envelopes: safeNumber(data.noop_runner_envelopes),
    noop_runner_transcripts: safeNumber(data.noop_runner_transcripts),
    noop_runner_identity_bindings: safeNumber(data.noop_runner_identity_bindings),
    source_mount_readiness: safeNumber(data.source_mount_readiness),
    source_mount_contracts: safeNumber(data.source_mount_contracts),
    approval_consumption_handoffs: safeNumber(data.approval_consumption_handoffs),
    execution_receipt_sink_reservations: safeNumber(data.execution_receipt_sink_reservations),
    execution_receipt_write_readiness: safeNumber(data.execution_receipt_write_readiness),
    execution_receipt_prewrite_bindings: safeNumber(data.execution_receipt_prewrite_bindings),
    execution_receipt_writer_preflights: safeNumber(data.execution_receipt_writer_preflights),
    run_boundary_preflights: safeNumber(data.run_boundary_preflights),
    sandbox_provider_contracts: safeNumber(data.sandbox_provider_contracts),
    sandbox_provider_bindings: safeNumber(data.sandbox_provider_bindings),
    sandbox_provider_selections: safeNumber(data.sandbox_provider_selections),
    sandbox_provider_verifier_preflights: safeNumber(data.sandbox_provider_verifier_preflights),
    sandbox_provider_runtime_probe_preflights: safeNumber(data.sandbox_provider_runtime_probe_preflights),
    sandbox_provider_runtime_probe_harness_preflights: safeNumber(
      data.sandbox_provider_runtime_probe_harness_preflights,
    ),
    sandbox_provider_runtime_probe_runner_readiness: safeNumber(
      data.sandbox_provider_runtime_probe_runner_readiness,
    ),
    sandbox_provider_runtime_probe_runner_bindings: safeNumber(
      data.sandbox_provider_runtime_probe_runner_bindings,
    ),
    sandbox_provider_runtime_probe_runner_enforcements: safeNumber(
      data.sandbox_provider_runtime_probe_runner_enforcements,
    ),
    sandbox_provider_runtime_probe_execution_boundaries: safeNumber(
      data.sandbox_provider_runtime_probe_execution_boundaries,
    ),
    sandbox_provider_runtime_probe_refusals: safeNumber(data.sandbox_provider_runtime_probe_refusals),
    sandbox_provider_runtime_probe_approval_requests: safeNumber(
      data.sandbox_provider_runtime_probe_approval_requests,
    ),
    sandbox_provider_runtime_probe_approval_consumptions: safeNumber(
      data.sandbox_provider_runtime_probe_approval_consumptions,
    ),
    sandbox_provider_runtime_probe_invocation_boundaries: safeNumber(
      data.sandbox_provider_runtime_probe_invocation_boundaries,
    ),
    sandbox_provider_runtime_probe_runner_pre_execution_boundaries: safeNumber(
      data.sandbox_provider_runtime_probe_runner_pre_execution_boundaries,
    ),
    sandbox_provider_runtime_probe_runner_control_bindings: safeNumber(
      data.sandbox_provider_runtime_probe_runner_control_bindings,
    ),
    sandboxed_rebuild_run_test_boundaries: safeNumber(data.sandboxed_rebuild_run_test_boundaries),
    sandboxed_rebuild_run_test_approval_requests: safeNumber(data.sandboxed_rebuild_run_test_approval_requests),
    sandboxed_rebuild_run_test_approval_consumptions: safeNumber(
      data.sandboxed_rebuild_run_test_approval_consumptions,
    ),
    sandboxed_rebuild_run_test_runner_bindings: safeNumber(data.sandboxed_rebuild_run_test_runner_bindings),
    sandboxed_rebuild_run_test_sandbox_policies: safeNumber(data.sandboxed_rebuild_run_test_sandbox_policies),
    execution_receipts: safeNumber(data.execution_receipts),
    runner_command_allowlists: safeNumber(data.runner_command_allowlists),
    runner_command_allowlist_declarations: safeNumber(data.runner_command_allowlist_declarations),
    runner_command_allowlist_enforcements: safeNumber(data.runner_command_allowlist_enforcements),
    runner_sandbox_readiness: safeNumber(data.runner_sandbox_readiness),
    runner_contracts: safeNumber(data.runner_contracts),
    runner_readiness: safeNumber(data.runner_readiness),
    runner_bindings: safeNumber(data.runner_bindings),
    runner_enforcements: safeNumber(data.runner_enforcements),
  };
}

function parseExecution(raw: unknown): IngestExecutionReadback {
  const data = isRecord(raw) ? raw : {};
  return {
    executed: safeBoolean(data.executed),
    execution_authority: safeBoolean(data.execution_authority),
    ran_repo_scripts: safeBoolean(data.ran_repo_scripts),
    ran_install: safeBoolean(data.ran_install),
    ran_build: safeBoolean(data.ran_build),
    ran_tests: safeBoolean(data.ran_tests),
    network_accessed: safeBoolean(data.network_accessed),
    wrote_to_repo: safeBoolean(data.wrote_to_repo),
    reason: safeString(data.reason).trim() || undefined,
  };
}

export function parseIngestReadbackResponse(raw: unknown): IngestReadbackResponse {
  const data = isRecord(raw) ? raw : {};
  return {
    ok: Boolean(data.ok),
    kind: safeString(data.kind).trim() || undefined,
    status: safeString(data.status).trim() || (data.ok ? "readback" : "unknown"),
    error: safeString(data.error).trim() || undefined,
    source_id: safeString(data.source_id).trim() || undefined,
    limit: safeNumber(data.limit, 100),
    sources: Array.isArray(data.sources)
      ? data.sources.map(parseSource).filter((item): item is IngestSourceRecord => item !== null)
      : [],
    repo_maps: Array.isArray(data.repo_maps)
      ? data.repo_maps.map(parseRepoMapReadback).filter((item): item is IngestRepoMapReadback => item !== null)
      : [],
    capability_candidates: Array.isArray(data.capability_candidates)
      ? data.capability_candidates
          .map(parseCapabilityCandidate)
          .filter((item): item is IngestCapabilityCandidate => item !== null)
      : [],
    lab_preflights: Array.isArray(data.lab_preflights)
      ? data.lab_preflights
          .map((item) => parseLabArtifactReadback(item, "preflight"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    approval_consumption_preflights: Array.isArray(data.approval_consumption_preflights)
      ? data.approval_consumption_preflights
          .map((item) => parseLabArtifactReadback(item, "approval_consumption"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    approval_consumptions: Array.isArray(data.approval_consumptions)
      ? data.approval_consumptions
          .map((item) => parseLabArtifactReadback(item, "approval_consumption_record"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    noop_runner_envelopes: Array.isArray(data.noop_runner_envelopes)
      ? data.noop_runner_envelopes
          .map((item) => parseLabArtifactReadback(item, "noop_runner_envelope"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    noop_runner_transcripts: Array.isArray(data.noop_runner_transcripts)
      ? data.noop_runner_transcripts
          .map((item) => parseLabArtifactReadback(item, "noop_runner_transcript"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    noop_runner_identity_bindings: Array.isArray(data.noop_runner_identity_bindings)
      ? data.noop_runner_identity_bindings
          .map((item) => parseLabArtifactReadback(item, "noop_runner_identity_binding"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    source_mount_readiness: Array.isArray(data.source_mount_readiness)
      ? data.source_mount_readiness
          .map((item) => parseLabArtifactReadback(item, "source_mount_readiness"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    source_mount_contracts: Array.isArray(data.source_mount_contracts)
      ? data.source_mount_contracts
          .map((item) => parseLabArtifactReadback(item, "source_mount_contract"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    approval_consumption_handoffs: Array.isArray(data.approval_consumption_handoffs)
      ? data.approval_consumption_handoffs
          .map((item) => parseLabArtifactReadback(item, "approval_handoff"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    execution_receipt_sink_reservations: Array.isArray(data.execution_receipt_sink_reservations)
      ? data.execution_receipt_sink_reservations
          .map((item) => parseLabArtifactReadback(item, "receipt_sink_reservation"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    execution_receipt_write_readiness: Array.isArray(data.execution_receipt_write_readiness)
      ? data.execution_receipt_write_readiness
          .map((item) => parseLabArtifactReadback(item, "execution_receipt_write_readiness"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    execution_receipt_prewrite_bindings: Array.isArray(data.execution_receipt_prewrite_bindings)
      ? data.execution_receipt_prewrite_bindings
          .map((item) => parseLabArtifactReadback(item, "execution_receipt_prewrite_binding"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    execution_receipt_writer_preflights: Array.isArray(data.execution_receipt_writer_preflights)
      ? data.execution_receipt_writer_preflights
          .map((item) => parseLabArtifactReadback(item, "execution_receipt_writer_preflight"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    run_boundary_preflights: Array.isArray(data.run_boundary_preflights)
      ? data.run_boundary_preflights
          .map((item) => parseLabArtifactReadback(item, "run_boundary_preflight"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_contracts: Array.isArray(data.sandbox_provider_contracts)
      ? data.sandbox_provider_contracts
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_contract"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_bindings: Array.isArray(data.sandbox_provider_bindings)
      ? data.sandbox_provider_bindings
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_binding"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_selections: Array.isArray(data.sandbox_provider_selections)
      ? data.sandbox_provider_selections
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_selection"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_verifier_preflights: Array.isArray(data.sandbox_provider_verifier_preflights)
      ? data.sandbox_provider_verifier_preflights
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_verifier"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_preflights: Array.isArray(data.sandbox_provider_runtime_probe_preflights)
      ? data.sandbox_provider_runtime_probe_preflights
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_harness_preflights: Array.isArray(
      data.sandbox_provider_runtime_probe_harness_preflights,
    )
      ? data.sandbox_provider_runtime_probe_harness_preflights
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_harness"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_runner_readiness: Array.isArray(
      data.sandbox_provider_runtime_probe_runner_readiness,
    )
      ? data.sandbox_provider_runtime_probe_runner_readiness
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_runner_readiness"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_runner_bindings: Array.isArray(
      data.sandbox_provider_runtime_probe_runner_bindings,
    )
      ? data.sandbox_provider_runtime_probe_runner_bindings
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_runner_binding"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_runner_enforcements: Array.isArray(
      data.sandbox_provider_runtime_probe_runner_enforcements,
    )
      ? data.sandbox_provider_runtime_probe_runner_enforcements
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_runner_enforcement"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_execution_boundaries: Array.isArray(
      data.sandbox_provider_runtime_probe_execution_boundaries,
    )
      ? data.sandbox_provider_runtime_probe_execution_boundaries
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_execution_boundary"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_refusals: Array.isArray(data.sandbox_provider_runtime_probe_refusals)
      ? data.sandbox_provider_runtime_probe_refusals
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_refusal"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_approval_requests: Array.isArray(
      data.sandbox_provider_runtime_probe_approval_requests,
    )
      ? data.sandbox_provider_runtime_probe_approval_requests
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_approval_request"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_approval_consumptions: Array.isArray(
      data.sandbox_provider_runtime_probe_approval_consumptions,
    )
      ? data.sandbox_provider_runtime_probe_approval_consumptions
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_approval_consumption"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_invocation_boundaries: Array.isArray(
      data.sandbox_provider_runtime_probe_invocation_boundaries,
    )
      ? data.sandbox_provider_runtime_probe_invocation_boundaries
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_invocation_boundary"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_runner_pre_execution_boundaries: Array.isArray(
      data.sandbox_provider_runtime_probe_runner_pre_execution_boundaries,
    )
      ? data.sandbox_provider_runtime_probe_runner_pre_execution_boundaries
          .map((item) =>
            parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_runner_pre_execution_boundary"),
          )
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandbox_provider_runtime_probe_runner_control_bindings: Array.isArray(
      data.sandbox_provider_runtime_probe_runner_control_bindings,
    )
      ? data.sandbox_provider_runtime_probe_runner_control_bindings
          .map((item) => parseLabArtifactReadback(item, "sandbox_provider_runtime_probe_runner_control_binding"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandboxed_rebuild_run_test_boundaries: Array.isArray(data.sandboxed_rebuild_run_test_boundaries)
      ? data.sandboxed_rebuild_run_test_boundaries
          .map((item) => parseLabArtifactReadback(item, "sandboxed_rebuild_run_test_boundary"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandboxed_rebuild_run_test_approval_requests: Array.isArray(
      data.sandboxed_rebuild_run_test_approval_requests,
    )
      ? data.sandboxed_rebuild_run_test_approval_requests
          .map((item) => parseLabArtifactReadback(item, "sandboxed_rebuild_run_test_approval_request"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandboxed_rebuild_run_test_approval_consumptions: Array.isArray(
      data.sandboxed_rebuild_run_test_approval_consumptions,
    )
      ? data.sandboxed_rebuild_run_test_approval_consumptions
          .map((item) => parseLabArtifactReadback(item, "sandboxed_rebuild_run_test_approval_consumption"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandboxed_rebuild_run_test_runner_bindings: Array.isArray(data.sandboxed_rebuild_run_test_runner_bindings)
      ? data.sandboxed_rebuild_run_test_runner_bindings
          .map((item) => parseLabArtifactReadback(item, "sandboxed_rebuild_run_test_runner_binding"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    sandboxed_rebuild_run_test_sandbox_policies: Array.isArray(data.sandboxed_rebuild_run_test_sandbox_policies)
      ? data.sandboxed_rebuild_run_test_sandbox_policies
          .map((item) => parseLabArtifactReadback(item, "sandboxed_rebuild_run_test_sandbox_policy"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    execution_receipts: Array.isArray(data.execution_receipts)
      ? data.execution_receipts
          .map((item) => parseLabArtifactReadback(item, "execution_receipt"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    runner_command_allowlists: Array.isArray(data.runner_command_allowlists)
      ? data.runner_command_allowlists
          .map((item) => parseLabArtifactReadback(item, "runner_command_allowlist"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    runner_command_allowlist_declarations: Array.isArray(data.runner_command_allowlist_declarations)
      ? data.runner_command_allowlist_declarations
          .map((item) => parseLabArtifactReadback(item, "runner_command_allowlist_declaration"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    runner_command_allowlist_enforcements: Array.isArray(data.runner_command_allowlist_enforcements)
      ? data.runner_command_allowlist_enforcements
          .map((item) => parseLabArtifactReadback(item, "runner_command_allowlist_enforcement"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    runner_sandbox_readiness: Array.isArray(data.runner_sandbox_readiness)
      ? data.runner_sandbox_readiness
          .map((item) => parseLabArtifactReadback(item, "runner_sandbox_readiness"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    runner_contracts: Array.isArray(data.runner_contracts)
      ? data.runner_contracts
          .map((item) => parseLabArtifactReadback(item, "runner_contract"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    runner_readiness: Array.isArray(data.runner_readiness)
      ? data.runner_readiness
          .map((item) => parseLabArtifactReadback(item, "runner_readiness"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    runner_bindings: Array.isArray(data.runner_bindings)
      ? data.runner_bindings
          .map((item) => parseLabArtifactReadback(item, "runner_binding"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    runner_enforcements: Array.isArray(data.runner_enforcements)
      ? data.runner_enforcements
          .map((item) => parseLabArtifactReadback(item, "runner_enforcement"))
          .filter((item): item is IngestLabArtifactReadback => item !== null)
      : [],
    counts: parseCounts(data.counts),
    execution: parseExecution(data.execution),
    governance: isRecord(data.governance)
      ? {
          gate: safeString(data.governance.gate).trim() || undefined,
          reason: safeString(data.governance.reason).trim() || undefined,
          next_step: safeString(data.governance.next_step).trim() || undefined,
        }
      : undefined,
    receipts_written: safeBoolean(data.receipts_written),
    artifacts_written: safeBoolean(data.artifacts_written),
  };
}

function firstStrings(values: string[], limit: number): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const cleaned = value.trim();
    if (!cleaned || seen.has(cleaned)) continue;
    seen.add(cleaned);
    out.push(cleaned);
    if (out.length >= limit) break;
  }
  return out;
}

function recordStringList(record: Record<string, unknown> | undefined, key: string): string[] {
  if (!record) return [];
  return safeStringList(record[key]);
}

export function presentIngestReadback(readback: IngestReadbackResponse | null | undefined): IngestReadbackPanelModel {
  const emptyExecution = parseExecution({});
  const execution = readback?.execution ?? emptyExecution;
  const status = readback?.ok
    ? readback.status || "readback"
    : readback?.error || readback?.status || "unavailable";
  const riskSignals = (readback?.repo_maps ?? []).flatMap((item) => item.repo_map.risk_signals).slice(0, 10);
  const sensitiveFileCount = (readback?.repo_maps ?? []).reduce(
    (total, item) => total + item.repo_map.protected_sensitive_files.length,
    0,
  );
  const blockers = firstStrings(
    [
      ...(readback?.lab_preflights ?? []).flatMap((item) => recordStringList(item.preflight, "blockers")),
      ...(readback?.approval_consumption_preflights ?? []).flatMap((item) =>
        recordStringList(item.approval_consumption, "blockers"),
      ),
      ...(readback?.approval_consumptions ?? []).flatMap((item) =>
        recordStringList(item.approval_consumption_record, "blockers"),
      ),
      ...(readback?.noop_runner_envelopes ?? []).flatMap((item) =>
        recordStringList(item.noop_runner_envelope, "blockers"),
      ),
      ...(readback?.noop_runner_transcripts ?? []).flatMap((item) =>
        recordStringList(item.noop_runner_transcript, "blockers"),
      ),
      ...(readback?.noop_runner_identity_bindings ?? []).flatMap((item) =>
        recordStringList(item.noop_runner_identity_binding, "blockers"),
      ),
      ...(readback?.source_mount_readiness ?? []).flatMap((item) =>
        recordStringList(item.source_mount_readiness, "blockers"),
      ),
      ...(readback?.source_mount_contracts ?? []).flatMap((item) =>
        recordStringList(item.source_mount_contract, "blockers"),
      ),
      ...(readback?.approval_consumption_handoffs ?? []).flatMap((item) =>
        recordStringList(item.approval_handoff, "blockers"),
      ),
      ...(readback?.execution_receipt_sink_reservations ?? []).flatMap((item) =>
        recordStringList(item.receipt_sink_reservation, "blockers"),
      ),
      ...(readback?.execution_receipt_write_readiness ?? []).flatMap((item) =>
        recordStringList(item.execution_receipt_write_readiness, "blockers"),
      ),
      ...(readback?.execution_receipt_prewrite_bindings ?? []).flatMap((item) =>
        recordStringList(item.execution_receipt_prewrite_binding, "blockers"),
      ),
      ...(readback?.execution_receipt_writer_preflights ?? []).flatMap((item) =>
        recordStringList(item.execution_receipt_writer_preflight, "blockers"),
      ),
      ...(readback?.run_boundary_preflights ?? []).flatMap((item) =>
        recordStringList(item.run_boundary_preflight, "blockers"),
      ),
      ...(readback?.sandbox_provider_contracts ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_contract, "blockers"),
      ),
      ...(readback?.sandbox_provider_bindings ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_binding, "blockers"),
      ),
      ...(readback?.sandbox_provider_selections ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_selection, "blockers"),
      ),
      ...(readback?.sandbox_provider_verifier_preflights ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_verifier, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_preflights ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_harness_preflights ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_harness, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_runner_readiness ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_runner_readiness, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_runner_bindings ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_runner_binding, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_runner_enforcements ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_runner_enforcement, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_execution_boundaries ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_execution_boundary, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_refusals ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_refusal, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_approval_requests ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_approval_request, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_approval_consumptions ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_approval_consumption, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_invocation_boundaries ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_invocation_boundary, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_runner_pre_execution_boundaries ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_runner_pre_execution_boundary, "blockers"),
      ),
      ...(readback?.sandbox_provider_runtime_probe_runner_control_bindings ?? []).flatMap((item) =>
        recordStringList(item.sandbox_provider_runtime_probe_runner_control_binding, "blockers"),
      ),
      ...(readback?.sandboxed_rebuild_run_test_boundaries ?? []).flatMap((item) =>
        recordStringList(item.sandboxed_rebuild_run_test_boundary, "blockers"),
      ),
      ...(readback?.sandboxed_rebuild_run_test_approval_requests ?? []).flatMap((item) =>
        recordStringList(item.sandboxed_rebuild_run_test_approval_request, "blockers"),
      ),
      ...(readback?.sandboxed_rebuild_run_test_approval_consumptions ?? []).flatMap((item) =>
        recordStringList(item.sandboxed_rebuild_run_test_approval_consumption, "blockers"),
      ),
      ...(readback?.sandboxed_rebuild_run_test_runner_bindings ?? []).flatMap((item) =>
        recordStringList(item.sandboxed_rebuild_run_test_runner_binding, "blockers"),
      ),
      ...(readback?.sandboxed_rebuild_run_test_sandbox_policies ?? []).flatMap((item) =>
        recordStringList(item.sandboxed_rebuild_run_test_sandbox_policy, "blockers"),
      ),
      ...(readback?.execution_receipts ?? []).flatMap((item) => recordStringList(item.execution_receipt, "blockers")),
      ...(readback?.runner_command_allowlists ?? []).flatMap((item) =>
        recordStringList(item.runner_command_allowlist, "blockers"),
      ),
      ...(readback?.runner_command_allowlist_declarations ?? []).flatMap((item) =>
        recordStringList(item.runner_command_allowlist_declaration, "blockers"),
      ),
      ...(readback?.runner_command_allowlist_enforcements ?? []).flatMap((item) =>
        recordStringList(item.runner_command_allowlist_enforcement, "blockers"),
      ),
      ...(readback?.runner_sandbox_readiness ?? []).flatMap((item) =>
        recordStringList(item.runner_sandbox_readiness, "blockers"),
      ),
      ...(readback?.runner_contracts ?? []).flatMap((item) => recordStringList(item.runner_contract, "blockers")),
      ...(readback?.runner_readiness ?? []).flatMap((item) => recordStringList(item.runner_readiness, "blockers")),
      ...(readback?.runner_bindings ?? []).flatMap((item) => recordStringList(item.runner_binding, "blockers")),
      ...(readback?.runner_enforcements ?? []).flatMap((item) =>
        recordStringList(item.runner_enforcement, "blockers"),
      ),
    ],
    10,
  );
  const latestArtifactPaths = firstStrings(
    [
      ...(readback?.repo_maps ?? []).map((item) => item.artifact_path),
      ...(readback?.lab_preflights ?? []).map((item) => item.artifact_path),
      ...(readback?.approval_consumption_preflights ?? []).map((item) => item.artifact_path),
      ...(readback?.approval_consumptions ?? []).map((item) => item.artifact_path),
      ...(readback?.noop_runner_envelopes ?? []).map((item) => item.artifact_path),
      ...(readback?.noop_runner_transcripts ?? []).map((item) => item.artifact_path),
      ...(readback?.noop_runner_identity_bindings ?? []).map((item) => item.artifact_path),
      ...(readback?.source_mount_readiness ?? []).map((item) => item.artifact_path),
      ...(readback?.source_mount_contracts ?? []).map((item) => item.artifact_path),
      ...(readback?.approval_consumption_handoffs ?? []).map((item) => item.artifact_path),
      ...(readback?.execution_receipt_sink_reservations ?? []).map((item) => item.artifact_path),
      ...(readback?.execution_receipt_write_readiness ?? []).map((item) => item.artifact_path),
      ...(readback?.execution_receipt_prewrite_bindings ?? []).map((item) => item.artifact_path),
      ...(readback?.execution_receipt_writer_preflights ?? []).map((item) => item.artifact_path),
      ...(readback?.run_boundary_preflights ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_contracts ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_bindings ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_selections ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_verifier_preflights ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_preflights ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_harness_preflights ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_runner_readiness ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_runner_bindings ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_runner_enforcements ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_execution_boundaries ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_refusals ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_approval_requests ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_approval_consumptions ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_invocation_boundaries ?? []).map((item) => item.artifact_path),
      ...(readback?.sandbox_provider_runtime_probe_runner_pre_execution_boundaries ?? []).map(
        (item) => item.artifact_path,
      ),
      ...(readback?.sandbox_provider_runtime_probe_runner_control_bindings ?? []).map((item) => item.artifact_path),
      ...(readback?.sandboxed_rebuild_run_test_boundaries ?? []).map((item) => item.artifact_path),
      ...(readback?.sandboxed_rebuild_run_test_approval_requests ?? []).map((item) => item.artifact_path),
      ...(readback?.sandboxed_rebuild_run_test_approval_consumptions ?? []).map((item) => item.artifact_path),
      ...(readback?.sandboxed_rebuild_run_test_runner_bindings ?? []).map((item) => item.artifact_path),
      ...(readback?.sandboxed_rebuild_run_test_sandbox_policies ?? []).map((item) => item.artifact_path),
      ...(readback?.execution_receipts ?? []).map((item) => item.artifact_path),
      ...(readback?.runner_command_allowlists ?? []).map((item) => item.artifact_path),
      ...(readback?.runner_command_allowlist_declarations ?? []).map((item) => item.artifact_path),
      ...(readback?.runner_command_allowlist_enforcements ?? []).map((item) => item.artifact_path),
      ...(readback?.runner_sandbox_readiness ?? []).map((item) => item.artifact_path),
      ...(readback?.runner_contracts ?? []).map((item) => item.artifact_path),
      ...(readback?.runner_readiness ?? []).map((item) => item.artifact_path),
      ...(readback?.runner_bindings ?? []).map((item) => item.artifact_path),
      ...(readback?.runner_enforcements ?? []).map((item) => item.artifact_path),
    ],
    6,
  );

  return {
    status,
    sourceCount: readback?.counts.sources ?? readback?.sources.length ?? 0,
    repoMapCount: readback?.counts.repo_maps ?? readback?.repo_maps.length ?? 0,
    candidateCount: readback?.counts.capability_candidates ?? readback?.capability_candidates.length ?? 0,
    labPreflightCount: readback?.counts.lab_preflights ?? readback?.lab_preflights.length ?? 0,
    approvalConsumptionCount: readback?.counts.approval_consumptions ?? readback?.approval_consumptions.length ?? 0,
    noopRunnerEnvelopeCount: readback?.counts.noop_runner_envelopes ?? readback?.noop_runner_envelopes.length ?? 0,
    noopRunnerTranscriptCount:
      readback?.counts.noop_runner_transcripts ?? readback?.noop_runner_transcripts.length ?? 0,
    noopRunnerIdentityBindingCount:
      readback?.counts.noop_runner_identity_bindings ?? readback?.noop_runner_identity_bindings.length ?? 0,
    sourceMountReadinessCount:
      readback?.counts.source_mount_readiness ?? readback?.source_mount_readiness.length ?? 0,
    sourceMountContractCount: readback?.counts.source_mount_contracts ?? readback?.source_mount_contracts.length ?? 0,
    approvalConsumptionHandoffCount:
      readback?.counts.approval_consumption_handoffs ?? readback?.approval_consumption_handoffs.length ?? 0,
    executionReceiptSinkReservationCount:
      readback?.counts.execution_receipt_sink_reservations ??
      readback?.execution_receipt_sink_reservations.length ??
      0,
    executionReceiptWriteReadinessCount:
      readback?.counts.execution_receipt_write_readiness ?? readback?.execution_receipt_write_readiness.length ?? 0,
    executionReceiptPrewriteBindingCount:
      readback?.counts.execution_receipt_prewrite_bindings ?? readback?.execution_receipt_prewrite_bindings.length ?? 0,
    executionReceiptWriterPreflightCount:
      readback?.counts.execution_receipt_writer_preflights ??
      readback?.execution_receipt_writer_preflights.length ??
      0,
    runBoundaryPreflightCount:
      readback?.counts.run_boundary_preflights ?? readback?.run_boundary_preflights.length ?? 0,
    sandboxProviderContractCount:
      readback?.counts.sandbox_provider_contracts ?? readback?.sandbox_provider_contracts.length ?? 0,
    sandboxProviderBindingCount:
      readback?.counts.sandbox_provider_bindings ?? readback?.sandbox_provider_bindings.length ?? 0,
    sandboxProviderSelectionCount:
      readback?.counts.sandbox_provider_selections ?? readback?.sandbox_provider_selections.length ?? 0,
    sandboxProviderVerifierCount:
      readback?.counts.sandbox_provider_verifier_preflights ??
      readback?.sandbox_provider_verifier_preflights.length ??
      0,
    sandboxProviderRuntimeProbeCount:
      readback?.counts.sandbox_provider_runtime_probe_preflights ??
      readback?.sandbox_provider_runtime_probe_preflights.length ??
      0,
    sandboxProviderRuntimeProbeHarnessCount:
      readback?.counts.sandbox_provider_runtime_probe_harness_preflights ??
      readback?.sandbox_provider_runtime_probe_harness_preflights.length ??
      0,
    sandboxProviderRuntimeProbeRunnerReadinessCount:
      readback?.counts.sandbox_provider_runtime_probe_runner_readiness ??
      readback?.sandbox_provider_runtime_probe_runner_readiness.length ??
      0,
    sandboxProviderRuntimeProbeRunnerBindingCount:
      readback?.counts.sandbox_provider_runtime_probe_runner_bindings ??
      readback?.sandbox_provider_runtime_probe_runner_bindings.length ??
      0,
    sandboxProviderRuntimeProbeRunnerEnforcementCount:
      readback?.counts.sandbox_provider_runtime_probe_runner_enforcements ??
      readback?.sandbox_provider_runtime_probe_runner_enforcements.length ??
      0,
    sandboxProviderRuntimeProbeExecutionBoundaryCount:
      readback?.counts.sandbox_provider_runtime_probe_execution_boundaries ??
      readback?.sandbox_provider_runtime_probe_execution_boundaries.length ??
      0,
    sandboxProviderRuntimeProbeRefusalCount:
      readback?.counts.sandbox_provider_runtime_probe_refusals ??
      readback?.sandbox_provider_runtime_probe_refusals.length ??
      0,
    sandboxProviderRuntimeProbeApprovalRequestCount:
      readback?.counts.sandbox_provider_runtime_probe_approval_requests ??
      readback?.sandbox_provider_runtime_probe_approval_requests.length ??
      0,
    sandboxProviderRuntimeProbeApprovalConsumptionCount:
      readback?.counts.sandbox_provider_runtime_probe_approval_consumptions ??
      readback?.sandbox_provider_runtime_probe_approval_consumptions.length ??
      0,
    sandboxProviderRuntimeProbeInvocationBoundaryCount:
      readback?.counts.sandbox_provider_runtime_probe_invocation_boundaries ??
      readback?.sandbox_provider_runtime_probe_invocation_boundaries.length ??
      0,
    sandboxProviderRuntimeProbeRunnerPreExecutionBoundaryCount:
      readback?.counts.sandbox_provider_runtime_probe_runner_pre_execution_boundaries ??
      readback?.sandbox_provider_runtime_probe_runner_pre_execution_boundaries.length ??
      0,
    sandboxProviderRuntimeProbeRunnerControlBindingCount:
      readback?.counts.sandbox_provider_runtime_probe_runner_control_bindings ??
      readback?.sandbox_provider_runtime_probe_runner_control_bindings.length ??
      0,
    sandboxedRebuildRunTestBoundaryCount:
      readback?.counts.sandboxed_rebuild_run_test_boundaries ??
      readback?.sandboxed_rebuild_run_test_boundaries.length ??
      0,
    sandboxedRebuildRunTestApprovalRequestCount:
      readback?.counts.sandboxed_rebuild_run_test_approval_requests ??
      readback?.sandboxed_rebuild_run_test_approval_requests.length ??
      0,
    sandboxedRebuildRunTestApprovalConsumptionCount:
      readback?.counts.sandboxed_rebuild_run_test_approval_consumptions ??
      readback?.sandboxed_rebuild_run_test_approval_consumptions.length ??
      0,
    sandboxedRebuildRunTestRunnerBindingCount:
      readback?.counts.sandboxed_rebuild_run_test_runner_bindings ??
      readback?.sandboxed_rebuild_run_test_runner_bindings.length ??
      0,
    sandboxedRebuildRunTestSandboxPolicyCount:
      readback?.counts.sandboxed_rebuild_run_test_sandbox_policies ??
      readback?.sandboxed_rebuild_run_test_sandbox_policies.length ??
      0,
    executionReceiptCount: readback?.counts.execution_receipts ?? readback?.execution_receipts.length ?? 0,
    runnerCommandAllowlistCount:
      readback?.counts.runner_command_allowlists ?? readback?.runner_command_allowlists.length ?? 0,
    runnerCommandAllowlistDeclarationCount:
      readback?.counts.runner_command_allowlist_declarations ??
      readback?.runner_command_allowlist_declarations.length ??
      0,
    runnerCommandAllowlistEnforcementCount:
      readback?.counts.runner_command_allowlist_enforcements ??
      readback?.runner_command_allowlist_enforcements.length ??
      0,
    runnerSandboxReadinessCount:
      readback?.counts.runner_sandbox_readiness ?? readback?.runner_sandbox_readiness.length ?? 0,
    runnerContractCount: readback?.counts.runner_contracts ?? readback?.runner_contracts.length ?? 0,
    runnerReadinessCount: readback?.counts.runner_readiness ?? readback?.runner_readiness.length ?? 0,
    runnerBindingCount: readback?.counts.runner_bindings ?? readback?.runner_bindings.length ?? 0,
    runnerEnforcementCount: readback?.counts.runner_enforcements ?? readback?.runner_enforcements.length ?? 0,
    guardLines: [
      execution.executed ? "execution reported by backend" : "no execution reported",
      execution.execution_authority ? "execution authority reported" : "execution authority absent",
      execution.ran_repo_scripts ? "repo scripts reported as run" : "repo scripts not run",
      execution.network_accessed ? "network access reported" : "network access not reported",
      readback?.receipts_written ? "readback wrote receipts" : "readback wrote no receipts",
      readback?.artifacts_written ? "readback wrote artifacts" : "readback wrote no artifacts",
    ],
    sources: (readback?.sources ?? []).slice(0, 6),
    riskSignals,
    candidates: (readback?.capability_candidates ?? []).slice(0, 8),
    blockers,
    sensitiveFileCount,
    latestArtifactPaths,
  };
}

export class IngestReadbackClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = trimTrailingSlashes(baseUrl || "");
  }

  async getReadback(opts?: {
    actor?: string;
    sourceId?: string;
    limit?: number;
    signal?: AbortSignal;
  }): Promise<IngestReadbackResponse> {
    const params = new URLSearchParams();
    params.set("actor", opts?.actor?.trim() || DEFAULT_INGEST_READBACK_ACTOR);
    const sourceId = opts?.sourceId?.trim();
    if (sourceId) params.set("source_id", sourceId);
    params.set("limit", String(typeof opts?.limit === "number" ? opts.limit : 100));

    const url = `${this.baseUrl}/ingest/readback?${params.toString()}`;
    const res = await fetch(url, { method: "GET", signal: opts?.signal });
    if (!res.ok) {
      throw new IngestApiError("Failed to load ingest readback.", { status: res.status, url });
    }
    return parseIngestReadbackResponse(await res.json());
  }
}
