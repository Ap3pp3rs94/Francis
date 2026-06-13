import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_INGEST_READBACK_ACTOR,
  IngestReadbackClient,
  parseIngestReadbackResponse,
  presentIngestReadback,
  trimTrailingSlashes,
} from "./index.ts";

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

function fixtureReadback(): unknown {
  return {
    ok: true,
    kind: "francis.ingest.readback",
    status: "readback",
    source_id: "src_repo",
    limit: 100,
    counts: {
      sources: 1,
      repo_maps: 1,
      capability_candidates: 2,
      lab_preflights: 1,
      approval_consumption_preflights: 1,
      approval_consumptions: 1,
      noop_runner_envelopes: 1,
      noop_runner_transcripts: 1,
      noop_runner_identity_bindings: 1,
      source_mount_readiness: 1,
      source_mount_contracts: 1,
      approval_consumption_handoffs: 1,
      execution_receipt_sink_reservations: 1,
      execution_receipt_write_readiness: 1,
      execution_receipt_prewrite_bindings: 1,
      execution_receipt_writer_preflights: 1,
      run_boundary_preflights: 1,
      sandbox_provider_contracts: 1,
      sandbox_provider_bindings: 1,
      sandbox_provider_selections: 1,
      sandbox_provider_verifier_preflights: 1,
      sandbox_provider_runtime_probe_preflights: 1,
      sandbox_provider_runtime_probe_harness_preflights: 1,
      sandbox_provider_runtime_probe_runner_readiness: 1,
      sandbox_provider_runtime_probe_runner_bindings: 1,
      sandbox_provider_runtime_probe_runner_enforcements: 1,
      sandbox_provider_runtime_probe_execution_boundaries: 1,
      sandbox_provider_runtime_probe_refusals: 1,
      sandbox_provider_runtime_probe_approval_requests: 1,
      sandbox_provider_runtime_probe_approval_consumptions: 1,
      sandbox_provider_runtime_probe_invocation_boundaries: 1,
      sandbox_provider_runtime_probe_runner_pre_execution_boundaries: 1,
      sandbox_provider_runtime_probe_runner_control_bindings: 1,
      sandboxed_rebuild_run_test_boundaries: 1,
      sandboxed_rebuild_run_test_approval_requests: 1,
      sandboxed_rebuild_run_test_approval_consumptions: 1,
      sandboxed_rebuild_run_test_runner_bindings: 1,
      sandboxed_rebuild_run_test_sandbox_policies: 1,
      execution_receipts: 1,
      runner_command_allowlists: 1,
      runner_command_allowlist_declarations: 1,
      runner_command_allowlist_enforcements: 1,
      runner_sandbox_readiness: 1,
      runner_contracts: 1,
      runner_readiness: 1,
      runner_bindings: 1,
      runner_enforcements: 1,
    },
    sources: [
      {
        id: "src_repo",
        type: "repo",
        canonical_path: "D:/Francis",
        status: "indexed",
        permissions: { read: true, execute: false, network: false, write: false, destructive: false },
        derived_artifacts: ["data/artifacts/ingest/repo_maps/src_repo.json"],
        receipts: ["data/artifacts/ingest/receipts/receipt.json"],
      },
    ],
    repo_maps: [
      {
        artifact_path: "data/artifacts/ingest/repo_maps/src_repo.json",
        repo_map: {
          source_id: "src_repo",
          repo_root: "D:/Francis",
          is_git_repo: true,
          detected_languages: ["TypeScript", "Python"],
          package_managers: ["npm"],
          manifest_files: ["package.json"],
          test_files: ["tests/test_api_ingest.py"],
          docs_readmes: ["README.md"],
          source_directories: ["src"],
          dependency_manifests: ["package.json"],
          license_file: "LICENSE",
          risk_signals: [
            {
              id: "package_postinstall_script",
              severity: "high",
              path: "package.json",
              detail: "postinstall script declared",
            },
          ],
          suggested_validation_commands: [{ name: "tests", command: "npm test", requires_execution: true }],
          protected_sensitive_files: [{ path: ".env", kind: "env_file_present" }],
          files_inspected_count: 25,
          warnings: [],
        },
      },
    ],
    capability_candidates: [
      {
        id: "cand_read",
        name: "explain_repo_architecture",
        source_id: "src_repo",
        source_type: "repo",
        status: "drafted",
        description: "Summarize repository architecture from inspected files.",
        permissions_required: { read: true, execute: false, network: false, write: false, destructive: false },
        risk_level: "low",
        suggested_validation: [],
        receipts: [],
        promotion_requirements: ["source map exists"],
      },
      {
        id: "cand_test",
        name: "run_project_tests",
        source_id: "src_repo",
        source_type: "repo",
        status: "discovered",
        description: "Run project tests in a future governed lab.",
        permissions_required: { read: true, execute: true, network: false, write: true, destructive: false },
        risk_level: "medium",
        suggested_validation: ["npm test"],
        receipts: [],
        promotion_requirements: ["run in Francis Lab"],
      },
    ],
    lab_preflights: [
      {
        artifact_path: "data/artifacts/ingest/lab_preflights/preflight.json",
        preflight: { blockers: ["unknown_repo_execution_not_supported"] },
      },
    ],
    approval_consumption_preflights: [
      {
        artifact_path: "data/artifacts/ingest/lab_approval_consumption_preflights/approval.json",
        approval_consumption: { blockers: ["approval_not_approved"], approval_consumed: false },
      },
    ],
    approval_consumptions: [
      {
        artifact_path: "data/artifacts/ingest/lab_approval_consumptions/consumed.json",
        approval_consumption_record: {
          id: "lab_approval_consumed_fixture",
          status: "consumed",
          approval_consumed: true,
          single_use_enforced: true,
          execution_authority: false,
          executed: false,
          ran_repo_scripts: false,
          network_accessed: false,
        },
      },
    ],
    noop_runner_envelopes: [
      {
        artifact_path: "data/artifacts/ingest/lab_noop_runner_envelopes/noop.json",
        noop_runner_envelope: {
          id: "lab_noop_runner_envelope_fixture",
          status: "completed",
          noop_performed: true,
          approval_consumed: true,
          execution_authority: false,
          executed: false,
          commands_executed: false,
          repo_code_executed: false,
          ran_repo_scripts: false,
          network_accessed: false,
        },
      },
    ],
    noop_runner_transcripts: [
      {
        artifact_path: "data/artifacts/ingest/lab_noop_runner_transcripts/transcript.json",
        noop_runner_transcript: {
          id: "lab_noop_runner_transcript_fixture",
          status: "completed",
          noop_performed: true,
          builtin_noop_output_captured: true,
          real_process_output_captured: false,
          stdout_content_stored: false,
          stderr_content_stored: false,
          output_content_stored: false,
          executed: false,
          commands_executed: false,
          repo_code_executed: false,
          network_accessed: false,
          stdout: { bytes: 0, content_stored: false },
          stderr: { bytes: 0, content_stored: false },
        },
      },
    ],
    noop_runner_identity_bindings: [
      {
        artifact_path: "data/artifacts/ingest/lab_noop_runner_identity_bindings/identity.json",
        noop_runner_identity_binding: {
          id: "lab_noop_runner_identity_fixture",
          status: "completed",
          runner_id: "francis.lab.runner.builtin_noop.v0",
          runner_identity_bound: true,
          builtin_noop_only: true,
          live_runner_bound: false,
          sandbox_runner_bound: false,
          execution_authority: false,
          executed: false,
          commands_executed: false,
          repo_code_executed: false,
          candidate_validated: false,
          capability_promoted: false,
        },
      },
    ],
    source_mount_readiness: [
      {
        artifact_path: "data/artifacts/ingest/lab_source_mount_readiness/source_mount.json",
        source_mount_readiness: {
          id: "lab_source_mount_readiness_fixture",
          status: "ready",
          source_mount_mode: "reference_only_read_only",
          source_reference_ready: true,
          read_only_reference_confirmed: true,
          read_only_mount_bound: false,
          source_mount_enforced: false,
          source_copied: false,
          source_write_allowed: false,
          runner_identity_verified: true,
          live_runner_bound: false,
          sandbox_runner_bound: false,
          execution_authority: false,
          executed: false,
          commands_executed: false,
          repo_code_executed: false,
          network_accessed: false,
          candidate_validated: false,
          capability_promoted: false,
          blockers: [],
        },
      },
    ],
    source_mount_contracts: [
      {
        artifact_path: "data/artifacts/ingest/lab_source_mount_contracts/source_mount_contract.json",
        source_mount_contract: {
          id: "lab_source_mount_contract_fixture",
          status: "ready",
          contract_kind: "francis.lab.source_mount_contract",
          contract_mode: "contract_only_no_live_mount",
          mount_mode: "future_read_only_source_mount",
          contract_declared: true,
          live_mount_bound: false,
          mount_enforced: false,
          read_only_mount_bound: false,
          source_copied: false,
          source_write_allowed: false,
          live_runner_bound: false,
          sandbox_runner_bound: false,
          execution_authority: false,
          executed: false,
          commands_executed: false,
          repo_code_executed: false,
          network_accessed: false,
          candidate_validated: false,
          capability_promoted: false,
          blockers: [],
        },
      },
    ],
    approval_consumption_handoffs: [
      {
        artifact_path: "data/artifacts/ingest/lab_approval_consumption_handoffs/handoff.json",
        approval_handoff: {
          blockers: ["approval_consumption_handoff_preflight_blocked"],
          missing_checks: ["approval_consumption_not_disabled"],
          approval_consumed: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    execution_receipt_sink_reservations: [
      {
        artifact_path: "data/artifacts/ingest/lab_execution_receipt_sink_reservations/reservation.json",
        receipt_sink_reservation: {
          blockers: ["execution_receipt_sink_reservation_preflight_blocked"],
          missing_checks: ["execution_receipt_prewrite_bound"],
          execution_receipt_written: false,
          prewrite_bound: false,
          final_write_bound: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    execution_receipt_write_readiness: [
      {
        artifact_path: "data/artifacts/ingest/lab_receipt_write_readiness/write.json",
        execution_receipt_write_readiness: {
          blockers: ["execution_receipt_write_readiness_preflight_blocked"],
          missing_checks: ["receipt_prewrite_writer_bound", "receipt_final_writer_bound"],
          receipt_schema_bound: false,
          prewrite_bound: false,
          final_write_bound: false,
          execution_receipt_prewritten: false,
          execution_receipt_finalized: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    execution_receipt_prewrite_bindings: [
      {
        artifact_path: "data/artifacts/ingest/lab_receipt_prewrite_bindings/prewrite.json",
        execution_receipt_prewrite_binding: {
          blockers: ["execution_receipt_prewrite_binding_preflight_blocked"],
          missing_checks: ["prewrite_writer_bound", "final_writer_bound"],
          receipt_schema_bound: true,
          prewrite_contract_bound: true,
          final_write_contract_bound: true,
          prewrite_writer_bound: false,
          final_write_writer_bound: false,
          execution_receipt_prewritten: false,
          execution_receipt_finalized: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    execution_receipt_writer_preflights: [
      {
        artifact_path: "data/artifacts/ingest/lab_receipt_writer_preflights/writer.json",
        execution_receipt_writer_preflight: {
          blockers: ["execution_receipt_writer_preflight_blocked"],
          missing_checks: ["writer_implementation_bound", "prewrite_writer_bound", "final_writer_bound"],
          writer_interface_declared: true,
          writer_implementation_bound: false,
          writer_path_within_sink: true,
          prewrite_writer_bound: false,
          final_write_writer_bound: false,
          execution_receipt_prewritten: false,
          execution_receipt_finalized: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    run_boundary_preflights: [
      {
        artifact_path: "data/artifacts/ingest/lab_run_boundary_preflights/run_boundary.json",
        run_boundary_preflight: {
          id: "lab_run_boundary_fixture",
          status: "blocked",
          boundary_kind: "francis.lab.run_boundary_preflight",
          boundary_mode: "preflight_only_no_execution",
          run_mode: "future_sandboxed_rebuild_run_test",
          source_mount_contract_declared: true,
          sandbox_provider_runtime_probe_harness_id: "lab_sandbox_provider_runtime_probe_harness_fixture",
          sandbox_provider_runtime_probe_runner_enforcement_id: "lab_runtime_probe_runner_enforcement_fixture",
          sandbox_provider_runtime_probe_harness_ready: false,
          sandbox_provider_runtime_probe_runner_enforcement_ready: false,
          runtime_probe_harness_contract_declared: true,
          runtime_probe_runner_enforcement_contract_declared: true,
          runtime_probe_runner_enforcement_bound: false,
          runtime_probe_runner_bound: false,
          runtime_probe_sandbox_bound: false,
          runtime_probe_service_query_guard_bound: false,
          runtime_probe_output_capture_bound: false,
          runtime_probe_kill_switch_bound: false,
          read_only_mount_bound: false,
          mount_enforced: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          command_allowlist_enforced: false,
          writer_implementation_bound: false,
          receipt_prewrite_bound: false,
          receipt_final_write_bound: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          commands_executed: false,
          repo_code_executed: false,
          network_accessed: false,
          candidate_validated: false,
          capability_promoted: false,
          missing_checks: [
            "sandbox_bound",
            "sandbox_provider_runtime_probe_harness_ready",
            "sandbox_provider_runtime_probe_runner_enforcement_ready",
            "runtime_probe_runner_enforcement_bound",
            "runtime_probe_runner_bound",
          ],
          blockers: ["sandbox_bound", "runtime_probe_runner_enforcement_bound", "runtime_probe_runner_bound"],
        },
      },
    ],
    sandbox_provider_contracts: [
      {
        artifact_path: "data/artifacts/ingest/lab_sandbox_provider_contracts/provider.json",
        sandbox_provider_contract: {
          id: "lab_sandbox_provider_contract_fixture",
          status: "blocked",
          contract_kind: "francis.lab.sandbox_provider_contract",
          contract_mode: "provider_contract_preflight_only_no_execution",
          provider_kind: "unbound",
          provider_contract_declared: true,
          sandbox_provider_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          workspace_isolation_bound: false,
          filesystem_write_policy_bound: false,
          network_policy_bound: true,
          resource_limits_bound: false,
          timeout_policy_bound: false,
          stdout_stderr_capture_bound: false,
          kill_switch_bound: false,
          command_allowlist_enforced: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          repo_code_executed: false,
          network_accessed: false,
          blockers: ["sandbox_provider_bound"],
        },
      },
    ],
    sandbox_provider_bindings: [
      {
        artifact_path: "data/artifacts/ingest/lab_sandbox_provider_bindings/binding.json",
        sandbox_provider_binding: {
          id: "lab_sandbox_provider_binding_fixture",
          status: "blocked",
          binding_kind: "francis.lab.sandbox_provider_binding_preflight",
          binding_mode: "binding_preflight_only_no_execution",
          provider_kind: "unbound",
          provider_contract_present: true,
          provider_contract_declared: true,
          provider_kind_selected: false,
          provider_binary_or_service_verified: false,
          provider_policy_manifest_bound: false,
          sandbox_provider_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          command_allowlist_enforced: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          repo_code_executed: false,
          network_accessed: false,
          blockers: ["provider_kind_selected"],
        },
      },
    ],
    sandbox_provider_selections: [
      {
        artifact_path: "data/artifacts/ingest/lab_sandbox_provider_selections/selection.json",
        sandbox_provider_selection: {
          id: "lab_sandbox_provider_selection_fixture",
          status: "blocked",
          selection_kind: "francis.lab.sandbox_provider_selection_preflight",
          selection_mode: "selection_verification_preflight_only_no_execution",
          requested_provider_kind: "unselected",
          selected_provider_kind: "unselected",
          provider_kind_selected: false,
          provider_reference_verified: false,
          provider_binary_or_service_verified: false,
          provider_policy_manifest_bound: false,
          sandbox_provider_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          repo_code_executed: false,
          network_accessed: false,
          blockers: ["provider_kind_selected"],
        },
      },
    ],
    sandbox_provider_verifier_preflights: [
      {
        artifact_path: "data/artifacts/ingest/lab_sandbox_provider_verifier_preflights/verifier.json",
        sandbox_provider_verifier: {
          id: "lab_sandbox_provider_verifier_fixture",
          status: "blocked",
          verifier_kind: "francis.lab.sandbox_provider_verifier_preflight",
          verifier_mode: "static_identity_policy_verification_no_execution",
          provider_kind: "local_process_sandbox",
          verifier_contract_declared: true,
          verifier_implementation_bound: true,
          verifier_identity_bound: true,
          verifier_policy_bound: true,
          verifier_receipt_contract_bound: true,
          static_identity_verification_performed: true,
          provider_reference_fingerprint_captured: true,
          provider_policy_manifest_hash_captured: true,
          provider_binary_or_service_verified: true,
          provider_runtime_probe_performed: false,
          provider_version_captured: true,
          provider_identity_fingerprint_captured: true,
          provider_identity: {
            provider_reference_fingerprint: "sha256:provider-reference",
            provider_identity_fingerprint: "sha256:provider-identity",
            provider_version: "0.1.0",
          },
          provider_policy_manifest: {
            manifest_hash: "sha256:provider-policy",
            network_disabled_by_manifest: true,
            direct_execution_disabled_by_manifest: true,
          },
          provider_runtime_probe: {
            status: "not_performed",
          },
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          sandbox_provider_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          repo_code_executed: false,
          network_accessed: false,
          blockers: ["provider_runtime_probe_performed"],
        },
      },
    ],
    sandbox_provider_runtime_probe_preflights: [
      {
        artifact_path: "data/artifacts/ingest/lab_sandbox_provider_runtime_probe_preflights/probe.json",
        sandbox_provider_runtime_probe: {
          id: "lab_sandbox_provider_runtime_probe_fixture",
          status: "blocked",
          probe_kind: "francis.lab.sandbox_provider_runtime_probe_preflight",
          probe_mode: "runtime_probe_contract_preflight_only_no_provider_execution",
          verifier_static_identity_ready: true,
          provider_identity_fingerprint_captured: true,
          provider_binary_or_service_verified: true,
          runtime_probe_contract_declared: true,
          runtime_probe_authorization_required: true,
          runtime_probe_network_blocked_by_contract: true,
          runtime_probe_receipt_contract_declared: true,
          runtime_probe_repo_execution_separated: true,
          runtime_probe_runner_bound: false,
          runtime_probe_sandbox_bound: false,
          runtime_probe_service_query_guard_bound: false,
          provider_runtime_probe_performed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          sandbox_provider_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          repo_code_executed: false,
          network_accessed: false,
          blockers: ["provider_runtime_probe_performed"],
        },
      },
    ],
    sandbox_provider_runtime_probe_harness_preflights: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_harness_preflights/harness.json",
        sandbox_provider_runtime_probe_harness: {
          id: "lab_sandbox_provider_runtime_probe_harness_fixture",
          status: "blocked",
          harness_kind: "francis.lab.sandbox_provider_runtime_probe_harness_preflight",
          harness_mode: "runtime_probe_harness_preflight_only_no_provider_execution",
          runtime_probe_preflight_present: true,
          runtime_probe_contract_declared: true,
          runtime_probe_runner_contract_declared: true,
          runtime_probe_runner_bound: false,
          runtime_probe_sandbox_contract_declared: true,
          runtime_probe_sandbox_bound: false,
          runtime_probe_service_query_guard_declared: true,
          runtime_probe_service_query_guard_bound: false,
          runtime_probe_output_capture_declared: true,
          runtime_probe_output_capture_bound: false,
          runtime_probe_kill_switch_declared: true,
          runtime_probe_kill_switch_bound: false,
          provider_runtime_probe_performed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          sandbox_provider_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          repo_code_executed: false,
          network_accessed: false,
          blockers: ["runtime_probe_runner_bound"],
        },
      },
    ],
    sandbox_provider_runtime_probe_runner_readiness: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_runner_readiness/runner.json",
        sandbox_provider_runtime_probe_runner_readiness: {
          id: "lab_runtime_probe_runner_ready_fixture",
          status: "blocked",
          runner_kind: "francis.lab.sandbox_provider_runtime_probe_runner_readiness",
          runner_mode: "probe_runner_interface_readiness_only_no_provider_execution",
          sandbox_provider_runtime_probe_harness_id: "lab_sandbox_provider_runtime_probe_harness_fixture",
          runtime_probe_harness_present: true,
          runtime_probe_harness_contract_declared: true,
          probe_runner_interface_declared: true,
          probe_runner_implementation_bound: false,
          probe_runner_identity_bound: false,
          probe_runner_policy_bound: false,
          probe_runner_sandbox_bound: false,
          probe_runner_network_blocked: false,
          probe_runner_workspace_isolated: false,
          probe_runner_timeout_bound: false,
          probe_runner_output_capture_bound: false,
          probe_runner_kill_switch_bound: false,
          probe_runner_receipt_contract_bound: false,
          provider_runtime_probe_performed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          sandbox_provider_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          repo_code_executed: false,
          network_accessed: false,
          blockers: ["probe_runner_implementation_bound"],
        },
      },
    ],
    sandbox_provider_runtime_probe_runner_bindings: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_runner_bindings/binding.json",
        sandbox_provider_runtime_probe_runner_binding: {
          id: "lab_runtime_probe_runner_binding_fixture",
          status: "blocked",
          runner_kind: "francis.lab.sandbox_provider_runtime_probe_runner_binding_preflight",
          binding_mode: "probe_runner_binding_preflight_no_provider_execution",
          sandbox_provider_runtime_probe_runner_readiness_id: "lab_runtime_probe_runner_ready_fixture",
          runner_readiness_present: true,
          probe_runner_interface_declared: true,
          probe_runner_binding_contract_declared: true,
          probe_runner_readiness_ready: false,
          probe_runner_implementation_bound: false,
          probe_runner_identity_bound: false,
          probe_runner_policy_bound: false,
          probe_runner_sandbox_bound: false,
          probe_runner_network_blocked: false,
          probe_runner_workspace_isolated: false,
          probe_runner_timeout_bound: false,
          probe_runner_output_capture_bound: false,
          probe_runner_kill_switch_bound: false,
          probe_runner_receipt_contract_bound: false,
          probe_runner_bound: false,
          runtime_probe_bound: false,
          provider_runtime_probe_performed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          sandbox_provider_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          repo_code_executed: false,
          network_accessed: false,
          blockers: ["probe_runner_bound"],
        },
      },
    ],
    sandbox_provider_runtime_probe_runner_enforcements: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_runner_enforcements/enforcement.json",
        sandbox_provider_runtime_probe_runner_enforcement: {
          id: "lab_runtime_probe_runner_enforcement_fixture",
          status: "blocked",
          runner_kind: "francis.lab.sandbox_provider_runtime_probe_runner_enforcement_preflight",
          enforcement_mode: "probe_runner_enforcement_preflight_no_provider_execution",
          sandbox_provider_runtime_probe_runner_binding_id: "lab_runtime_probe_runner_binding_fixture",
          runner_binding_present: true,
          probe_runner_binding_contract_declared: true,
          probe_runner_binding_ready: false,
          probe_runner_enforcement_contract_declared: true,
          probe_runner_enforcement_bound: false,
          probe_runner_bound: false,
          runtime_probe_bound: false,
          probe_runner_identity_bound: false,
          probe_runner_policy_bound: false,
          probe_runner_sandbox_bound: false,
          probe_runner_network_blocked: false,
          probe_runner_workspace_isolated: false,
          probe_runner_timeout_bound: false,
          probe_runner_output_capture_bound: false,
          probe_runner_kill_switch_bound: false,
          probe_runner_receipt_contract_bound: false,
          provider_runtime_probe_performed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          repo_code_executed: false,
          network_accessed: false,
          blockers: ["probe_runner_enforcement_bound"],
        },
      },
    ],
    sandbox_provider_runtime_probe_execution_boundaries: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_execution_boundaries/boundary.json",
        sandbox_provider_runtime_probe_execution_boundary: {
          id: "lab_runtime_probe_execution_boundary_fixture",
          status: "blocked",
          boundary_kind: "francis.lab.sandbox_provider_runtime_probe_execution_boundary",
          boundary_mode: "execution_boundary_preflight_only_no_provider_execution",
          probe_mode: "future_sandbox_provider_runtime_probe",
          run_boundary_preflight_id: "lab_run_boundary_fixture",
          run_boundary_present: true,
          run_boundary_ready: false,
          runtime_probe_runner_enforcement_present: true,
          runtime_probe_runner_enforcement_ready: false,
          runtime_probe_runner_enforcement_bound: false,
          runtime_probe_runner_bound: false,
          runtime_probe_bound: false,
          provider_probe_execution_boundary_declared: true,
          provider_probe_execution_boundary_bound: false,
          provider_runtime_probe_performed: false,
          execution_receipt_writer_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          network_blocked_or_policy_bound: true,
          workspace_isolated: false,
          timeout_policy_bound: false,
          kill_switch_bound: false,
          output_capture_bound: false,
          approval_not_consumed: true,
          execution_authority_absent: true,
          provider_binary_not_executed: true,
          service_query_not_performed: true,
          process_not_launched: true,
          container_not_launched: true,
          repo_code_not_executed: true,
          network_not_accessed: true,
          repo_write_not_performed: true,
          execution_receipt_not_written: true,
          execution_authority: false,
          executed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          repo_code_executed: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          missing_checks: [
            "run_boundary_ready",
            "runtime_probe_runner_enforcement_bound",
            "provider_probe_execution_boundary_bound",
            "provider_runtime_probe_performed",
          ],
          blockers: ["provider_probe_execution_boundary_bound"],
        },
      },
    ],
    sandbox_provider_runtime_probe_refusals: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_refusals/refusal.json",
        sandbox_provider_runtime_probe_refusal: {
          id: "lab_runtime_probe_refusal_fixture",
          status: "blocked",
          refusal_kind: "francis.lab.sandbox_provider_runtime_probe_refusal",
          refusal_mode: "refusal_only_no_provider_execution",
          execution_boundary_id: "lab_runtime_probe_execution_boundary_fixture",
          permission_scope: "ingest.lab.sandbox.provider_runtime_probe.refuse",
          provider_runtime_probe_performed: false,
          provider_binary_executed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          repo_code_executed: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          blockers: ["sandbox_provider_runtime_probe_refused_in_v0"],
        },
      },
    ],
    sandbox_provider_runtime_probe_approval_requests: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_approval_requests/request.json",
        sandbox_provider_runtime_probe_approval_request: {
          id: "lab_runtime_probe_approval_request_fixture",
          status: "needs_approval",
          action: "francis.lab.sandbox_provider_runtime_probe",
          approval_id: "approval_provider_probe_fixture",
          upstream_approval_id: "approval_lab_execute_fixture",
          execution_boundary_id: "lab_runtime_probe_execution_boundary_fixture",
          permission_scope: "ingest.lab.sandbox.provider_runtime_probe.request_approval",
          approval_created: true,
          approval_consumed: false,
          upstream_approval_consumed: false,
          provider_runtime_probe_performed: false,
          provider_binary_executed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          repo_code_executed: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          execution_authority: false,
          executed: false,
          blockers: ["sandbox_provider_runtime_probe_requires_operator_approval"],
        },
      },
    ],
    sandbox_provider_runtime_probe_approval_consumptions: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_approval_consumptions/consumed.json",
        sandbox_provider_runtime_probe_approval_consumption: {
          id: "lab_runtime_probe_approval_consumed_fixture",
          status: "consumed",
          action: "francis.lab.sandbox_provider_runtime_probe",
          approval_id: "approval_provider_probe_fixture",
          approval_request_id: "lab_runtime_probe_approval_request_fixture",
          upstream_approval_id: "approval_lab_execute_fixture",
          execution_boundary_id: "lab_runtime_probe_execution_boundary_fixture",
          permission_scope: "ingest.lab.sandbox.provider_runtime_probe.consume_approval",
          approval_consumed: true,
          single_use_enforced: true,
          upstream_approval_consumed: false,
          provider_runtime_probe_performed: false,
          provider_binary_executed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          repo_code_executed: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          execution_authority: false,
          executed: false,
          blockers: [],
        },
      },
    ],
    sandbox_provider_runtime_probe_invocation_boundaries: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_invocation_boundaries/boundary.json",
        sandbox_provider_runtime_probe_invocation_boundary: {
          id: "lab_runtime_probe_invocation_boundary_fixture",
          status: "blocked",
          boundary_kind: "francis.lab.sandbox_provider_runtime_probe_invocation_boundary",
          boundary_mode: "invocation_boundary_preflight_only_no_provider_execution",
          invocation_mode: "future_sandbox_provider_runtime_probe_invocation",
          action: "francis.lab.sandbox_provider_runtime_probe",
          approval_id: "approval_provider_probe_fixture",
          approval_consumption_id: "lab_runtime_probe_approval_consumed_fixture",
          approval_request_id: "lab_runtime_probe_approval_request_fixture",
          execution_boundary_id: "lab_runtime_probe_execution_boundary_fixture",
          permission_scope: "ingest.lab.sandbox.provider_runtime_probe.invocation_boundary",
          approval_consumed: true,
          single_use_consumption_found: true,
          single_use_enforced: true,
          exact_action_binding_verified: true,
          upstream_approval_consumed: false,
          execution_boundary_present: true,
          execution_boundary_recorded: true,
          execution_boundary_ready: false,
          provider_probe_execution_boundary_bound: false,
          probe_runner_bound: false,
          probe_runner_policy_bound: false,
          probe_runner_sandbox_bound: false,
          probe_runner_network_blocked: true,
          probe_runner_workspace_isolated: false,
          probe_runner_timeout_bound: false,
          probe_runner_output_capture_bound: false,
          probe_runner_kill_switch_bound: false,
          probe_runner_receipt_writer_bound: false,
          provider_runtime_probe_performed: false,
          provider_binary_executed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          repo_code_executed: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          execution_authority: false,
          executed: false,
          missing_checks: [
            "execution_boundary_ready",
            "provider_probe_execution_boundary_bound",
            "probe_runner_bound",
            "probe_runner_policy_bound",
          ],
          blockers: ["provider_runtime_probe_invocation_blocked_until_governed_runner_bound"],
        },
      },
    ],
    sandbox_provider_runtime_probe_runner_pre_execution_boundaries: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_preexec_boundaries/boundary.json",
        sandbox_provider_runtime_probe_runner_pre_execution_boundary: {
          id: "lab_runtime_probe_runner_pre_execution_boundary_fixture",
          status: "blocked",
          boundary_kind: "francis.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary",
          boundary_mode: "runner_pre_execution_boundary_no_provider_execution",
          pre_execution_mode: "future_sandbox_provider_runtime_probe_runner_pre_execution",
          action: "francis.lab.sandbox_provider_runtime_probe",
          approval_id: "approval_provider_probe_fixture",
          approval_consumption_id: "lab_runtime_probe_approval_consumed_fixture",
          invocation_boundary_id: "lab_runtime_probe_invocation_boundary_fixture",
          approval_request_id: "lab_runtime_probe_approval_request_fixture",
          execution_boundary_id: "lab_runtime_probe_execution_boundary_fixture",
          permission_scope: "ingest.lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary",
          invocation_boundary_found: true,
          invocation_boundary_recorded: true,
          invocation_boundary_ready: false,
          approval_consumed: true,
          single_use_consumption_found: true,
          single_use_enforced: true,
          exact_action_binding_verified: true,
          runner_identity_declared: true,
          runner_identity_bound: false,
          runner_policy_declared: true,
          runner_policy_bound: false,
          sandbox_policy_declared: true,
          sandbox_policy_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          network_block_declared: true,
          network_block_bound: false,
          timeout_policy_declared: true,
          timeout_policy_bound: false,
          output_capture_declared: true,
          output_capture_bound: false,
          kill_switch_declared: true,
          kill_switch_bound: false,
          execution_receipt_writer_declared: true,
          execution_receipt_writer_bound: false,
          provider_runtime_probe_performed: false,
          provider_binary_executed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          repo_code_executed: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          execution_authority: false,
          executed: false,
          missing_checks: [
            "invocation_boundary_ready",
            "runner_identity_bound",
            "runner_policy_bound",
            "sandbox_policy_bound",
            "network_block_bound",
            "execution_receipt_writer_bound",
          ],
          blockers: [
            "provider_runtime_probe_runner_pre_execution_boundary_blocked_until_live_runner_controls_bound",
          ],
        },
      },
    ],
    sandbox_provider_runtime_probe_runner_control_bindings: [
      {
        artifact_path: "data/artifacts/ingest/lab_runtime_probe_control_bindings/binding.json",
        sandbox_provider_runtime_probe_runner_control_binding: {
          id: "lab_runtime_probe_ctrl_binding_fixture",
          status: "blocked",
          binding_kind: "francis.lab.sandbox_provider_runtime_probe_runner_control_binding",
          binding_mode: "control_binding_preflight_only_no_provider_execution",
          control_binding_mode: "future_sandbox_provider_runtime_probe_runner_control_binding",
          action: "francis.lab.sandbox_provider_runtime_probe",
          approval_id: "approval_provider_probe_fixture",
          approval_consumption_id: "lab_runtime_probe_approval_consumed_fixture",
          invocation_boundary_id: "lab_runtime_probe_invocation_boundary_fixture",
          pre_execution_boundary_id: "lab_runtime_probe_runner_pre_execution_boundary_fixture",
          approval_request_id: "lab_runtime_probe_approval_request_fixture",
          execution_boundary_id: "lab_runtime_probe_execution_boundary_fixture",
          permission_scope: "ingest.lab.sandbox.provider_runtime_probe.runner_control_binding",
          pre_execution_boundary_found: true,
          pre_execution_boundary_recorded: true,
          pre_execution_boundary_ready: false,
          invocation_boundary_found: true,
          invocation_boundary_recorded: true,
          invocation_boundary_ready: false,
          approval_consumed: true,
          single_use_consumption_found: true,
          single_use_enforced: true,
          exact_action_binding_verified: true,
          control_binding_recorded: true,
          runner_identity_declared: true,
          runner_identity_binding_recorded: true,
          runner_identity_bound: false,
          runner_policy_declared: true,
          runner_policy_binding_recorded: true,
          runner_policy_bound: false,
          sandbox_policy_declared: true,
          sandbox_policy_binding_recorded: true,
          sandbox_policy_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          network_block_declared: true,
          network_block_binding_recorded: true,
          network_block_bound: false,
          timeout_policy_declared: true,
          timeout_policy_binding_recorded: true,
          timeout_policy_bound: false,
          output_capture_declared: true,
          output_capture_binding_recorded: true,
          output_capture_bound: false,
          kill_switch_declared: true,
          kill_switch_binding_recorded: true,
          kill_switch_bound: false,
          execution_receipt_writer_declared: true,
          execution_receipt_writer_binding_recorded: true,
          execution_receipt_writer_bound: false,
          provider_runtime_probe_performed: false,
          provider_binary_executed: false,
          service_query_performed: false,
          process_launched: false,
          container_launched: false,
          repo_code_executed: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          execution_authority: false,
          executed: false,
          missing_checks: [
            "pre_execution_boundary_ready",
            "runner_identity_bound",
            "runner_policy_bound",
            "sandbox_policy_bound",
            "network_block_bound",
            "execution_receipt_writer_bound",
          ],
          blockers: ["provider_runtime_probe_runner_control_binding_blocked_until_live_runner_enforced"],
        },
      },
    ],
    sandboxed_rebuild_run_test_boundaries: [
      {
        artifact_path: "data/artifacts/ingest/lab_sandboxed_rebuild_run_test_boundaries/boundary.json",
        sandboxed_rebuild_run_test_boundary: {
          id: "lab_sandboxed_run_boundary_fixture",
          status: "blocked",
          boundary_kind: "francis.lab.sandboxed_rebuild_run_test_boundary",
          boundary_mode: "sandboxed_rebuild_run_test_boundary_no_execution",
          run_mode: "future_sandboxed_rebuild_run_test",
          approval_id: "approval_provider_probe_fixture",
          approval_consumption_id: "lab_runtime_probe_approval_consumed_fixture",
          invocation_boundary_id: "lab_runtime_probe_invocation_boundary_fixture",
          pre_execution_boundary_id: "lab_runtime_probe_runner_pre_execution_boundary_fixture",
          control_binding_id: "lab_runtime_probe_ctrl_binding_fixture",
          approval_request_id: "lab_runtime_probe_approval_request_fixture",
          execution_boundary_id: "lab_runtime_probe_execution_boundary_fixture",
          permission_scope: "ingest.lab.sandboxed_rebuild_run_test.boundary",
          control_binding_found: true,
          control_binding_recorded: true,
          control_binding_ready: false,
          approval_consumed: true,
          single_use_consumption_found: true,
          single_use_enforced: true,
          exact_action_binding_verified: true,
          execution_approval_required: true,
          execution_approval_consumed: false,
          runner_identity_bound: false,
          runner_policy_bound: false,
          sandbox_policy_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          network_block_bound: false,
          timeout_policy_bound: false,
          output_capture_bound: false,
          kill_switch_bound: false,
          execution_receipt_writer_bound: false,
          rebuild_declared: true,
          run_declared: true,
          test_declared: true,
          execution_authority: false,
          executed: false,
          process_launched: false,
          container_launched: false,
          commands_executed: false,
          repo_code_executed: false,
          ran_install: false,
          ran_build: false,
          ran_tests: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          candidate_validated: false,
          capability_promoted: false,
          missing_checks: [
            "control_binding_ready",
            "execution_approval_consumed",
            "runner_identity_bound",
            "sandbox_enforced",
            "execution_receipt_writer_bound",
          ],
          blockers: ["sandboxed_rebuild_run_test_boundary_blocked_until_live_runner_enforced"],
        },
      },
    ],
    sandboxed_rebuild_run_test_approval_requests: [
      {
        artifact_path:
          "data/artifacts/ingest/lab_sandboxed_rebuild_run_test_approval_requests/request.json",
        sandboxed_rebuild_run_test_approval_request: {
          id: "lab_sandboxed_run_approval_request_fixture",
          status: "needs_approval",
          action: "francis.lab.sandboxed_rebuild_run_test",
          approval_created: true,
          approval_id: "approval_sandboxed_run_fixture",
          upstream_approval_id: "approval_provider_probe_fixture",
          sandboxed_boundary_id: "lab_sandboxed_run_boundary_fixture",
          control_binding_id: "lab_runtime_probe_ctrl_binding_fixture",
          pre_execution_boundary_id: "lab_runtime_probe_runner_pre_execution_boundary_fixture",
          invocation_boundary_id: "lab_runtime_probe_invocation_boundary_fixture",
          approval_consumption_id: "lab_runtime_probe_approval_consumed_fixture",
          approval_request_id: "lab_runtime_probe_approval_request_fixture",
          execution_boundary_id: "lab_runtime_probe_execution_boundary_fixture",
          permission_scope: "ingest.lab.sandboxed_rebuild_run_test.request_approval",
          approval_consumed: false,
          upstream_approval_consumed: false,
          boundary_recorded: true,
          boundary_ready: false,
          execution_authority: false,
          executed: false,
          process_launched: false,
          container_launched: false,
          commands_executed: false,
          repo_code_executed: false,
          ran_install: false,
          ran_build: false,
          ran_tests: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          candidate_validated: false,
          capability_promoted: false,
          blockers: ["sandboxed_rebuild_run_test_requires_operator_execution_approval"],
        },
      },
    ],
    sandboxed_rebuild_run_test_approval_consumptions: [
      {
        artifact_path:
          "data/artifacts/ingest/lab_sandboxed_rebuild_run_test_approval_consumptions/consumed.json",
        sandboxed_rebuild_run_test_approval_consumption: {
          id: "lab_sandboxed_run_approval_consumed_fixture",
          status: "consumed",
          action: "francis.lab.sandboxed_rebuild_run_test",
          approval_id: "approval_sandboxed_run_fixture",
          approval_request_id: "lab_sandboxed_run_approval_request_fixture",
          upstream_approval_id: "approval_provider_probe_fixture",
          upstream_approval_consumption_id: "lab_runtime_probe_approval_consumed_fixture",
          sandboxed_boundary_id: "lab_sandboxed_run_boundary_fixture",
          control_binding_id: "lab_runtime_probe_ctrl_binding_fixture",
          permission_scope: "ingest.lab.sandboxed_rebuild_run_test.consume_approval",
          approval_status: "approved",
          approval_consumed: true,
          single_use_enforced: true,
          upstream_approval_consumed: false,
          boundary_recorded: true,
          boundary_ready: false,
          execution_authority: false,
          executed: false,
          process_launched: false,
          container_launched: false,
          commands_executed: false,
          repo_code_executed: false,
          ran_install: false,
          ran_build: false,
          ran_tests: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          candidate_validated: false,
          capability_promoted: false,
          blockers: ["sandboxed_rebuild_run_test_still_blocked_after_approval_consumption"],
        },
      },
    ],
    sandboxed_rebuild_run_test_runner_bindings: [
      {
        artifact_path: "data/artifacts/ingest/lab_sandboxed_rebuild_run_test_runner_bindings/binding.json",
        sandboxed_rebuild_run_test_runner_binding: {
          id: "lab_sandboxed_run_runner_binding_fixture",
          status: "blocked",
          action: "francis.lab.sandboxed_rebuild_run_test",
          approval_id: "approval_sandboxed_run_fixture",
          approval_consumption_id: "lab_sandboxed_run_approval_consumed_fixture",
          approval_request_id: "lab_sandboxed_run_approval_request_fixture",
          sandboxed_boundary_id: "lab_sandboxed_run_boundary_fixture",
          control_binding_id: "lab_runtime_probe_ctrl_binding_fixture",
          permission_scope: "ingest.lab.sandboxed_rebuild_run_test.runner_binding",
          binding_kind: "sandboxed_rebuild_run_test_runner_binding_preflight",
          binding_mode: "static_provider_reference_only_no_live_runner",
          selected_provider_kind: "local_process_sandbox",
          approval_consumed: true,
          single_use_enforced: true,
          static_provider_reference_bound: true,
          provider_reference_verified: true,
          provider_policy_manifest_bound: true,
          runner_binding_declared: true,
          live_runner_bound: false,
          sandbox_runner_bound: false,
          sandbox_bound: false,
          sandbox_enforced: false,
          provider_binary_executed: false,
          provider_service_queried: false,
          execution_authority: false,
          executed: false,
          process_launched: false,
          container_launched: false,
          commands_executed: false,
          repo_code_executed: false,
          ran_install: false,
          ran_build: false,
          ran_tests: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          candidate_validated: false,
          capability_promoted: false,
          missing_checks: ["live_runner_bound", "sandbox_runner_bound", "sandbox_enforced"],
          blockers: ["sandboxed_rebuild_run_test_runner_binding_preflight_only"],
        },
      },
    ],
    sandboxed_rebuild_run_test_sandbox_policies: [
      {
        artifact_path: "data/artifacts/ingest/lab_sandboxed_rebuild_run_test_sandbox_policies/policy.json",
        sandboxed_rebuild_run_test_sandbox_policy: {
          id: "lab_sandboxed_run_sandbox_policy_fixture",
          status: "blocked",
          action: "francis.lab.sandboxed_rebuild_run_test",
          approval_id: "approval_sandboxed_run_fixture",
          approval_consumption_id: "lab_sandboxed_run_approval_consumed_fixture",
          runner_binding_id: "lab_sandboxed_run_runner_binding_fixture",
          approval_request_id: "lab_sandboxed_run_approval_request_fixture",
          sandboxed_boundary_id: "lab_sandboxed_run_boundary_fixture",
          control_binding_id: "lab_runtime_probe_ctrl_binding_fixture",
          permission_scope: "ingest.lab.sandboxed_rebuild_run_test.sandbox_policy",
          policy_kind: "sandboxed_rebuild_run_test_sandbox_policy_preflight",
          policy_mode: "policy_preflight_no_live_sandbox",
          approval_consumed: true,
          single_use_enforced: true,
          runner_binding_present: true,
          static_provider_reference_bound: true,
          provider_kind_selected: true,
          sandbox_policy_declared: true,
          network_default_deny: true,
          network_allowed: false,
          repo_write_allowed: false,
          destructive_allowed: false,
          secret_storage_allowed: false,
          source_read_only_reference: true,
          command_execution_enabled: false,
          command_allowlist_bound: false,
          execution_receipt_writer_bound: false,
          live_sandbox_bound: false,
          sandbox_enforced: false,
          execution_authority: false,
          executed: false,
          process_launched: false,
          container_launched: false,
          commands_executed: false,
          repo_code_executed: false,
          ran_install: false,
          ran_build: false,
          ran_tests: false,
          network_accessed: false,
          wrote_to_repo: false,
          execution_receipt_written: false,
          candidate_validated: false,
          capability_promoted: false,
          missing_checks: [
            "command_allowlist_bound",
            "execution_receipt_writer_bound",
            "live_sandbox_bound",
            "sandbox_enforced",
          ],
          blockers: ["sandboxed_rebuild_run_test_sandbox_policy_preflight_only"],
        },
      },
    ],
    execution_receipts: [
      {
        artifact_path: "data/artifacts/ingest/lab_execution_receipts/receipt.json",
        execution_receipt: {
          id: "lab_execution_receipt_fixture",
          mode: "synthetic_noop_execution_receipt",
          status: "blocked",
          synthetic: true,
          noop: true,
          prewritten: true,
          finalized: true,
          approval_consumed: false,
          execution_authority: false,
          executed: false,
          ran_repo_scripts: false,
          network_accessed: false,
        },
      },
    ],
    runner_command_allowlists: [
      {
        artifact_path: "data/artifacts/ingest/lab_runner_command_allowlists/allowlist.json",
        runner_command_allowlist: {
          blockers: ["runner_command_allowlist_binding_preflight_blocked"],
          missing_checks: ["command_allowlist_bound"],
          allowlist_declared: false,
          allowlist_bound: false,
          command_execution_enabled: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    runner_command_allowlist_declarations: [
      {
        artifact_path: "data/artifacts/ingest/lab_runner_command_allowlist_declarations/declaration.json",
        runner_command_allowlist_declaration: {
          blockers: ["runner_command_allowlist_declaration_preflight_blocked"],
          missing_checks: ["command_allowlist_bound"],
          allowlist_declared: true,
          allowlist_bound: false,
          command_execution_enabled: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    runner_command_allowlist_enforcements: [
      {
        artifact_path: "data/artifacts/ingest/lab_cmd_allowlist_enforcements/enforcement.json",
        runner_command_allowlist_enforcement: {
          blockers: ["runner_command_allowlist_enforcement_preflight_blocked"],
          missing_checks: ["command_allowlist_enforced"],
          allowlist_declared: true,
          allowlist_bound: false,
          allowlist_enforced: false,
          command_execution_enabled: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    runner_sandbox_readiness: [
      {
        artifact_path: "data/artifacts/ingest/lab_sandbox_readiness/sandbox.json",
        runner_sandbox_readiness: {
          blockers: ["runner_sandbox_readiness_preflight_blocked"],
          missing_checks: ["sandbox_provider_bound", "command_allowlist_enforced"],
          sandbox_bound: false,
          sandbox_enforced: false,
          runner_bound: false,
          allowlist_enforced: false,
          receipt_prewrite_bound: false,
          receipt_final_write_bound: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    runner_contracts: [
      {
        artifact_path: "data/artifacts/ingest/lab_runner_contracts/runner.json",
        runner_contract: { blockers: ["governed_runner_not_bound"], runner_bound: false },
      },
    ],
    runner_readiness: [
      {
        artifact_path: "data/artifacts/ingest/lab_runner_readiness/readiness.json",
        runner_readiness: {
          blockers: ["runner_readiness_blocked"],
          missing_controls: ["governed_runner_bound", "network_isolation_enforced"],
          execution_authority: false,
          executed: false,
        },
      },
    ],
    runner_bindings: [
      {
        artifact_path: "data/artifacts/ingest/lab_runner_bindings/binding.json",
        runner_binding: {
          blockers: ["runner_binding_preflight_blocked"],
          missing_controls: ["governed_runner_bound", "execution_receipt_sink_bound"],
          runner_bound: false,
          receipt_sink_bound: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    runner_enforcements: [
      {
        artifact_path: "data/artifacts/ingest/lab_runner_enforcement_preflights/enforcement.json",
        runner_enforcement: {
          blockers: ["runner_enforcement_preflight_blocked"],
          missing_checks: ["runner_identity_verified", "execution_receipt_prewrite_bound"],
          runner_bound: false,
          receipt_sink_bound: false,
          execution_authority: false,
          executed: false,
        },
      },
    ],
    execution: {
      executed: false,
      execution_authority: false,
      ran_repo_scripts: false,
      network_accessed: false,
      reason: "readback_only_no_execution",
    },
    receipts_written: false,
    artifacts_written: false,
  };
}

test("trimTrailingSlashes uses bounded scanning", () => {
  assert.equal(trimTrailingSlashes("http://127.0.0.1:8000///"), "http://127.0.0.1:8000");
  assert.equal(trimTrailingSlashes("http://127.0.0.1:8000/path"), "http://127.0.0.1:8000/path");
});

test("parseIngestReadbackResponse preserves source, risk, candidate, and no-execution truth", () => {
  const parsed = parseIngestReadbackResponse(fixtureReadback());

  assert.equal(parsed.ok, true);
  assert.equal(parsed.status, "readback");
  assert.equal(parsed.sources[0]?.id, "src_repo");
  assert.equal(parsed.sources[0]?.permissions.execute, false);
  assert.equal(parsed.repo_maps[0]?.repo_map.risk_signals[0]?.id, "package_postinstall_script");
  assert.equal(parsed.repo_maps[0]?.repo_map.protected_sensitive_files.length, 1);
  assert.equal(parsed.capability_candidates[1]?.name, "run_project_tests");
  assert.equal(parsed.capability_candidates[1]?.permissions_required.execute, true);
  assert.equal(parsed.counts.runner_readiness, 1);
  assert.equal(parsed.counts.runner_bindings, 1);
  assert.equal(parsed.counts.runner_enforcements, 1);
  assert.equal(parsed.counts.approval_consumptions, 1);
  assert.equal(parsed.counts.noop_runner_envelopes, 1);
  assert.equal(parsed.counts.noop_runner_transcripts, 1);
  assert.equal(parsed.counts.noop_runner_identity_bindings, 1);
  assert.equal(parsed.counts.source_mount_readiness, 1);
  assert.equal(parsed.counts.source_mount_contracts, 1);
  assert.equal(parsed.counts.approval_consumption_handoffs, 1);
  assert.equal(parsed.counts.execution_receipt_sink_reservations, 1);
  assert.equal(parsed.counts.execution_receipt_write_readiness, 1);
  assert.equal(parsed.counts.execution_receipt_prewrite_bindings, 1);
  assert.equal(parsed.counts.execution_receipt_writer_preflights, 1);
  assert.equal(parsed.counts.run_boundary_preflights, 1);
  assert.equal(parsed.counts.sandbox_provider_contracts, 1);
  assert.equal(parsed.counts.sandbox_provider_bindings, 1);
  assert.equal(parsed.counts.sandbox_provider_selections, 1);
  assert.equal(parsed.counts.sandbox_provider_verifier_preflights, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_preflights, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_harness_preflights, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_runner_readiness, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_runner_bindings, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_runner_enforcements, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_execution_boundaries, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_refusals, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_approval_requests, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_approval_consumptions, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_invocation_boundaries, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_runner_pre_execution_boundaries, 1);
  assert.equal(parsed.counts.sandbox_provider_runtime_probe_runner_control_bindings, 1);
  assert.equal(parsed.counts.sandboxed_rebuild_run_test_boundaries, 1);
  assert.equal(parsed.counts.sandboxed_rebuild_run_test_approval_requests, 1);
  assert.equal(parsed.counts.sandboxed_rebuild_run_test_approval_consumptions, 1);
  assert.equal(parsed.counts.sandboxed_rebuild_run_test_runner_bindings, 1);
  assert.equal(parsed.counts.sandboxed_rebuild_run_test_sandbox_policies, 1);
  assert.equal(parsed.counts.execution_receipts, 1);
  assert.equal(parsed.counts.runner_command_allowlists, 1);
  assert.equal(parsed.counts.runner_command_allowlist_declarations, 1);
  assert.equal(parsed.counts.runner_command_allowlist_enforcements, 1);
  assert.equal(parsed.counts.runner_sandbox_readiness, 1);
  assert.equal(parsed.runner_readiness[0]?.runner_readiness?.execution_authority, false);
  assert.equal(parsed.runner_bindings[0]?.runner_binding?.receipt_sink_bound, false);
  assert.equal(parsed.runner_enforcements[0]?.runner_enforcement?.runner_bound, false);
  assert.equal(parsed.approval_consumptions[0]?.approval_consumption_record?.approval_consumed, true);
  assert.equal(parsed.approval_consumptions[0]?.approval_consumption_record?.single_use_enforced, true);
  assert.equal(parsed.approval_consumptions[0]?.approval_consumption_record?.executed, false);
  assert.equal(
    parsed.sandbox_provider_runtime_probe_invocation_boundaries[0]
      ?.sandbox_provider_runtime_probe_invocation_boundary?.approval_consumed,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_invocation_boundaries[0]
      ?.sandbox_provider_runtime_probe_invocation_boundary?.probe_runner_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_invocation_boundaries[0]
      ?.sandbox_provider_runtime_probe_invocation_boundary?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.approval_consumed,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.runner_identity_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.runner_identity_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.control_binding_recorded,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.runner_identity_binding_recorded,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.runner_identity_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.control_binding_recorded,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.control_binding_ready,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.execution_approval_required,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.execution_approval_consumed,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.commands_executed,
    false,
  );
  assert.equal(parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.ran_build, false);
  assert.equal(parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.ran_tests, false);
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_requests[0]?.sandboxed_rebuild_run_test_approval_request
      ?.approval_created,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_requests[0]?.sandboxed_rebuild_run_test_approval_request
      ?.approval_consumed,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_requests[0]?.sandboxed_rebuild_run_test_approval_request
      ?.boundary_recorded,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_requests[0]?.sandboxed_rebuild_run_test_approval_request
      ?.boundary_ready,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_requests[0]?.sandboxed_rebuild_run_test_approval_request
      ?.commands_executed,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_requests[0]?.sandboxed_rebuild_run_test_approval_request?.ran_build,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_requests[0]?.sandboxed_rebuild_run_test_approval_request?.ran_tests,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_consumptions[0]
      ?.sandboxed_rebuild_run_test_approval_consumption?.approval_consumed,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_consumptions[0]
      ?.sandboxed_rebuild_run_test_approval_consumption?.single_use_enforced,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_consumptions[0]
      ?.sandboxed_rebuild_run_test_approval_consumption?.execution_authority,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_consumptions[0]
      ?.sandboxed_rebuild_run_test_approval_consumption?.commands_executed,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_consumptions[0]
      ?.sandboxed_rebuild_run_test_approval_consumption?.ran_build,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_approval_consumptions[0]
      ?.sandboxed_rebuild_run_test_approval_consumption?.ran_tests,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_runner_bindings[0]?.sandboxed_rebuild_run_test_runner_binding
      ?.static_provider_reference_bound,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_runner_bindings[0]?.sandboxed_rebuild_run_test_runner_binding
      ?.provider_reference_verified,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_runner_bindings[0]?.sandboxed_rebuild_run_test_runner_binding
      ?.provider_policy_manifest_bound,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_runner_bindings[0]?.sandboxed_rebuild_run_test_runner_binding
      ?.live_runner_bound,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_runner_bindings[0]?.sandboxed_rebuild_run_test_runner_binding
      ?.sandbox_enforced,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_runner_bindings[0]?.sandboxed_rebuild_run_test_runner_binding?.ran_build,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_runner_bindings[0]?.sandboxed_rebuild_run_test_runner_binding?.ran_tests,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_runner_bindings[0]?.sandboxed_rebuild_run_test_runner_binding?.executed,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_sandbox_policies[0]?.sandboxed_rebuild_run_test_sandbox_policy
      ?.runner_binding_present,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_sandbox_policies[0]?.sandboxed_rebuild_run_test_sandbox_policy
      ?.network_default_deny,
    true,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_sandbox_policies[0]?.sandboxed_rebuild_run_test_sandbox_policy
      ?.repo_write_allowed,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_sandbox_policies[0]?.sandboxed_rebuild_run_test_sandbox_policy
      ?.command_execution_enabled,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_sandbox_policies[0]?.sandboxed_rebuild_run_test_sandbox_policy
      ?.live_sandbox_bound,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_sandbox_policies[0]?.sandboxed_rebuild_run_test_sandbox_policy
      ?.sandbox_enforced,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_sandbox_policies[0]?.sandboxed_rebuild_run_test_sandbox_policy?.executed,
    false,
  );
  assert.equal(parsed.noop_runner_envelopes[0]?.noop_runner_envelope?.noop_performed, true);
  assert.equal(parsed.noop_runner_envelopes[0]?.noop_runner_envelope?.repo_code_executed, false);
  assert.equal(parsed.noop_runner_transcripts[0]?.noop_runner_transcript?.builtin_noop_output_captured, true);
  assert.equal(parsed.noop_runner_transcripts[0]?.noop_runner_transcript?.output_content_stored, false);
  assert.equal(parsed.noop_runner_transcripts[0]?.noop_runner_transcript?.real_process_output_captured, false);
  assert.equal(parsed.noop_runner_identity_bindings[0]?.noop_runner_identity_binding?.runner_identity_bound, true);
  assert.equal(parsed.noop_runner_identity_bindings[0]?.noop_runner_identity_binding?.live_runner_bound, false);
  assert.equal(parsed.noop_runner_identity_bindings[0]?.noop_runner_identity_binding?.candidate_validated, false);
  assert.equal(parsed.source_mount_readiness[0]?.source_mount_readiness?.source_mount_mode, "reference_only_read_only");
  assert.equal(parsed.source_mount_readiness[0]?.source_mount_readiness?.source_mount_enforced, false);
  assert.equal(parsed.source_mount_readiness[0]?.source_mount_readiness?.read_only_mount_bound, false);
  assert.equal(parsed.source_mount_readiness[0]?.source_mount_readiness?.executed, false);
  assert.equal(parsed.source_mount_contracts[0]?.source_mount_contract?.contract_mode, "contract_only_no_live_mount");
  assert.equal(parsed.source_mount_contracts[0]?.source_mount_contract?.mount_mode, "future_read_only_source_mount");
  assert.equal(parsed.source_mount_contracts[0]?.source_mount_contract?.live_mount_bound, false);
  assert.equal(parsed.source_mount_contracts[0]?.source_mount_contract?.mount_enforced, false);
  assert.equal(parsed.source_mount_contracts[0]?.source_mount_contract?.executed, false);
  assert.equal(parsed.approval_consumption_handoffs[0]?.approval_handoff?.approval_consumed, false);
  assert.equal(parsed.execution_receipt_sink_reservations[0]?.receipt_sink_reservation?.execution_receipt_written, false);
  assert.equal(
    parsed.execution_receipt_write_readiness[0]?.execution_receipt_write_readiness?.execution_receipt_prewritten,
    false,
  );
  assert.equal(
    parsed.execution_receipt_prewrite_bindings[0]?.execution_receipt_prewrite_binding?.receipt_schema_bound,
    true,
  );
  assert.equal(
    parsed.execution_receipt_prewrite_bindings[0]?.execution_receipt_prewrite_binding?.execution_receipt_prewritten,
    false,
  );
  assert.equal(
    parsed.execution_receipt_writer_preflights[0]?.execution_receipt_writer_preflight?.writer_implementation_bound,
    false,
  );
  assert.equal(
    parsed.execution_receipt_writer_preflights[0]?.execution_receipt_writer_preflight?.writer_path_within_sink,
    true,
  );
  assert.equal(
    parsed.execution_receipt_writer_preflights[0]?.execution_receipt_writer_preflight?.execution_receipt_prewritten,
    false,
  );
  assert.equal(parsed.run_boundary_preflights[0]?.run_boundary_preflight?.boundary_mode, "preflight_only_no_execution");
  assert.equal(
    parsed.run_boundary_preflights[0]?.run_boundary_preflight?.run_mode,
    "future_sandboxed_rebuild_run_test",
  );
  assert.equal(parsed.run_boundary_preflights[0]?.run_boundary_preflight?.sandbox_bound, false);
  assert.equal(
    parsed.run_boundary_preflights[0]?.run_boundary_preflight?.sandbox_provider_runtime_probe_harness_id,
    "lab_sandbox_provider_runtime_probe_harness_fixture",
  );
  assert.equal(
    parsed.run_boundary_preflights[0]?.run_boundary_preflight?.sandbox_provider_runtime_probe_runner_enforcement_id,
    "lab_runtime_probe_runner_enforcement_fixture",
  );
  assert.equal(
    parsed.run_boundary_preflights[0]?.run_boundary_preflight?.sandbox_provider_runtime_probe_harness_ready,
    false,
  );
  assert.equal(
    parsed.run_boundary_preflights[0]?.run_boundary_preflight
      ?.sandbox_provider_runtime_probe_runner_enforcement_ready,
    false,
  );
  assert.equal(
    parsed.run_boundary_preflights[0]?.run_boundary_preflight?.runtime_probe_harness_contract_declared,
    true,
  );
  assert.equal(
    parsed.run_boundary_preflights[0]?.run_boundary_preflight?.runtime_probe_runner_enforcement_contract_declared,
    true,
  );
  assert.equal(
    parsed.run_boundary_preflights[0]?.run_boundary_preflight?.runtime_probe_runner_enforcement_bound,
    false,
  );
  assert.equal(parsed.run_boundary_preflights[0]?.run_boundary_preflight?.runtime_probe_runner_bound, false);
  assert.equal(parsed.run_boundary_preflights[0]?.run_boundary_preflight?.runtime_probe_sandbox_bound, false);
  assert.equal(
    parsed.run_boundary_preflights[0]?.run_boundary_preflight?.runtime_probe_service_query_guard_bound,
    false,
  );
  assert.equal(parsed.run_boundary_preflights[0]?.run_boundary_preflight?.runtime_probe_output_capture_bound, false);
  assert.equal(parsed.run_boundary_preflights[0]?.run_boundary_preflight?.runtime_probe_kill_switch_bound, false);
  assert.equal(parsed.run_boundary_preflights[0]?.run_boundary_preflight?.command_allowlist_enforced, false);
  assert.equal(parsed.run_boundary_preflights[0]?.run_boundary_preflight?.executed, false);
  assert.equal(
    parsed.sandbox_provider_contracts[0]?.sandbox_provider_contract?.contract_mode,
    "provider_contract_preflight_only_no_execution",
  );
  assert.equal(parsed.sandbox_provider_contracts[0]?.sandbox_provider_contract?.sandbox_provider_bound, false);
  assert.equal(parsed.sandbox_provider_contracts[0]?.sandbox_provider_contract?.sandbox_bound, false);
  assert.equal(parsed.sandbox_provider_contracts[0]?.sandbox_provider_contract?.executed, false);
  assert.equal(
    parsed.sandbox_provider_bindings[0]?.sandbox_provider_binding?.binding_mode,
    "binding_preflight_only_no_execution",
  );
  assert.equal(parsed.sandbox_provider_bindings[0]?.sandbox_provider_binding?.provider_kind_selected, false);
  assert.equal(parsed.sandbox_provider_bindings[0]?.sandbox_provider_binding?.sandbox_provider_bound, false);
  assert.equal(parsed.sandbox_provider_bindings[0]?.sandbox_provider_binding?.executed, false);
  assert.equal(
    parsed.sandbox_provider_selections[0]?.sandbox_provider_selection?.selection_mode,
    "selection_verification_preflight_only_no_execution",
  );
  assert.equal(parsed.sandbox_provider_selections[0]?.sandbox_provider_selection?.provider_kind_selected, false);
  assert.equal(
    parsed.sandbox_provider_selections[0]?.sandbox_provider_selection?.provider_binary_or_service_verified,
    false,
  );
  assert.equal(parsed.sandbox_provider_selections[0]?.sandbox_provider_selection?.sandbox_provider_bound, false);
  assert.equal(parsed.sandbox_provider_selections[0]?.sandbox_provider_selection?.executed, false);
  assert.equal(
    parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.verifier_mode,
    "static_identity_policy_verification_no_execution",
  );
  assert.equal(
    parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.verifier_contract_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.verifier_implementation_bound,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.provider_binary_or_service_verified,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.provider_identity_fingerprint_captured,
    true,
  );
  assert.equal(parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.process_launched, false);
  assert.equal(parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.container_launched, false);
  assert.equal(parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.sandbox_provider_bound, false);
  assert.equal(parsed.sandbox_provider_verifier_preflights[0]?.sandbox_provider_verifier?.executed, false);
  assert.equal(
    parsed.sandbox_provider_runtime_probe_preflights[0]?.sandbox_provider_runtime_probe?.probe_mode,
    "runtime_probe_contract_preflight_only_no_provider_execution",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_preflights[0]?.sandbox_provider_runtime_probe
      ?.runtime_probe_contract_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_preflights[0]?.sandbox_provider_runtime_probe
      ?.runtime_probe_network_blocked_by_contract,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_preflights[0]?.sandbox_provider_runtime_probe?.runtime_probe_runner_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_preflights[0]?.sandbox_provider_runtime_probe?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_preflights[0]?.sandbox_provider_runtime_probe?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_preflights[0]?.sandbox_provider_runtime_probe?.container_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_preflights[0]?.sandbox_provider_runtime_probe?.executed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_harness_preflights[0]?.sandbox_provider_runtime_probe_harness?.harness_mode,
    "runtime_probe_harness_preflight_only_no_provider_execution",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_harness_preflights[0]?.sandbox_provider_runtime_probe_harness
      ?.runtime_probe_runner_contract_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_harness_preflights[0]?.sandbox_provider_runtime_probe_harness
      ?.runtime_probe_runner_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_harness_preflights[0]?.sandbox_provider_runtime_probe_harness
      ?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_harness_preflights[0]?.sandbox_provider_runtime_probe_harness
      ?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_harness_preflights[0]?.sandbox_provider_runtime_probe_harness?.executed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_readiness[0]?.sandbox_provider_runtime_probe_runner_readiness
      ?.runner_mode,
    "probe_runner_interface_readiness_only_no_provider_execution",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_readiness[0]?.sandbox_provider_runtime_probe_runner_readiness
      ?.probe_runner_interface_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_readiness[0]?.sandbox_provider_runtime_probe_runner_readiness
      ?.probe_runner_implementation_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_readiness[0]?.sandbox_provider_runtime_probe_runner_readiness
      ?.probe_runner_sandbox_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_readiness[0]?.sandbox_provider_runtime_probe_runner_readiness
      ?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_readiness[0]?.sandbox_provider_runtime_probe_runner_readiness
      ?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_readiness[0]?.sandbox_provider_runtime_probe_runner_readiness?.executed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_bindings[0]?.sandbox_provider_runtime_probe_runner_binding
      ?.binding_mode,
    "probe_runner_binding_preflight_no_provider_execution",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_bindings[0]?.sandbox_provider_runtime_probe_runner_binding
      ?.probe_runner_binding_contract_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_bindings[0]?.sandbox_provider_runtime_probe_runner_binding
      ?.probe_runner_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_bindings[0]?.sandbox_provider_runtime_probe_runner_binding
      ?.runtime_probe_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_bindings[0]?.sandbox_provider_runtime_probe_runner_binding
      ?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_bindings[0]?.sandbox_provider_runtime_probe_runner_binding?.executed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_enforcements[0]?.sandbox_provider_runtime_probe_runner_enforcement
      ?.enforcement_mode,
    "probe_runner_enforcement_preflight_no_provider_execution",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_enforcements[0]?.sandbox_provider_runtime_probe_runner_enforcement
      ?.probe_runner_enforcement_contract_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_enforcements[0]?.sandbox_provider_runtime_probe_runner_enforcement
      ?.probe_runner_enforcement_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_enforcements[0]?.sandbox_provider_runtime_probe_runner_enforcement
      ?.probe_runner_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_enforcements[0]?.sandbox_provider_runtime_probe_runner_enforcement
      ?.runtime_probe_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_enforcements[0]?.sandbox_provider_runtime_probe_runner_enforcement
      ?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_enforcements[0]?.sandbox_provider_runtime_probe_runner_enforcement
      ?.executed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_execution_boundary?.boundary_mode,
    "execution_boundary_preflight_only_no_provider_execution",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_execution_boundary?.provider_probe_execution_boundary_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_execution_boundary?.provider_probe_execution_boundary_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_execution_boundary?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_execution_boundary?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_execution_boundary?.execution_receipt_written,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_refusals[0]?.sandbox_provider_runtime_probe_refusal?.refusal_mode,
    "refusal_only_no_provider_execution",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_refusals[0]?.sandbox_provider_runtime_probe_refusal
      ?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_refusals[0]?.sandbox_provider_runtime_probe_refusal
      ?.provider_binary_executed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_refusals[0]?.sandbox_provider_runtime_probe_refusal?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_refusals[0]?.sandbox_provider_runtime_probe_refusal
      ?.execution_receipt_written,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_requests[0]?.sandbox_provider_runtime_probe_approval_request
      ?.action,
    "francis.lab.sandbox_provider_runtime_probe",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_requests[0]?.sandbox_provider_runtime_probe_approval_request
      ?.approval_created,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_requests[0]?.sandbox_provider_runtime_probe_approval_request
      ?.approval_consumed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_requests[0]?.sandbox_provider_runtime_probe_approval_request
      ?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_requests[0]?.sandbox_provider_runtime_probe_approval_request
      ?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_consumptions[0]
      ?.sandbox_provider_runtime_probe_approval_consumption?.action,
    "francis.lab.sandbox_provider_runtime_probe",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_consumptions[0]
      ?.sandbox_provider_runtime_probe_approval_consumption?.approval_consumed,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_consumptions[0]
      ?.sandbox_provider_runtime_probe_approval_consumption?.single_use_enforced,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_consumptions[0]
      ?.sandbox_provider_runtime_probe_approval_consumption?.provider_runtime_probe_performed,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_consumptions[0]
      ?.sandbox_provider_runtime_probe_approval_consumption?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_approval_consumptions[0]
      ?.sandbox_provider_runtime_probe_approval_consumption?.execution_receipt_written,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.boundary_mode,
    "runner_pre_execution_boundary_no_provider_execution",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.runner_policy_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.runner_policy_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.network_block_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.network_block_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.execution_receipt_writer_declared,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.execution_receipt_writer_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_pre_execution_boundaries[0]
      ?.sandbox_provider_runtime_probe_runner_pre_execution_boundary?.execution_receipt_written,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.binding_mode,
    "control_binding_preflight_only_no_provider_execution",
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.runner_policy_binding_recorded,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.runner_policy_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.network_block_binding_recorded,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.network_block_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.execution_receipt_writer_binding_recorded,
    true,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.execution_receipt_writer_bound,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.process_launched,
    false,
  );
  assert.equal(
    parsed.sandbox_provider_runtime_probe_runner_control_bindings[0]
      ?.sandbox_provider_runtime_probe_runner_control_binding?.execution_receipt_written,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.boundary_mode,
    "sandboxed_rebuild_run_test_boundary_no_execution",
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.sandbox_enforced,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary
      ?.execution_receipt_writer_bound,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary
      ?.execution_receipt_written,
    false,
  );
  assert.equal(
    parsed.sandboxed_rebuild_run_test_boundaries[0]?.sandboxed_rebuild_run_test_boundary?.capability_promoted,
    false,
  );
  assert.equal(parsed.execution_receipts[0]?.execution_receipt?.synthetic, true);
  assert.equal(parsed.execution_receipts[0]?.execution_receipt?.finalized, true);
  assert.equal(parsed.execution_receipts[0]?.execution_receipt?.executed, false);
  assert.equal(parsed.execution_receipts[0]?.execution_receipt?.approval_consumed, false);
  assert.equal(parsed.runner_command_allowlists[0]?.runner_command_allowlist?.allowlist_bound, false);
  assert.equal(
    parsed.runner_command_allowlist_declarations[0]?.runner_command_allowlist_declaration?.allowlist_declared,
    true,
  );
  assert.equal(
    parsed.runner_command_allowlist_enforcements[0]?.runner_command_allowlist_enforcement?.allowlist_enforced,
    false,
  );
  assert.equal(parsed.runner_sandbox_readiness[0]?.runner_sandbox_readiness?.sandbox_bound, false);
  assert.equal(parsed.execution.executed, false);
  assert.equal(parsed.execution.network_accessed, false);
  assert.equal(parsed.receipts_written, false);
  assert.equal(parsed.artifacts_written, false);
});

test("presentIngestReadback keeps guards and lab blockers visible", () => {
  const model = presentIngestReadback(parseIngestReadbackResponse(fixtureReadback()));

  assert.equal(model.sourceCount, 1);
  assert.equal(model.repoMapCount, 1);
  assert.equal(model.candidateCount, 2);
  assert.equal(model.runnerReadinessCount, 1);
  assert.equal(model.runnerBindingCount, 1);
  assert.equal(model.runnerEnforcementCount, 1);
  assert.equal(model.approvalConsumptionCount, 1);
  assert.equal(model.noopRunnerEnvelopeCount, 1);
  assert.equal(model.noopRunnerTranscriptCount, 1);
  assert.equal(model.noopRunnerIdentityBindingCount, 1);
  assert.equal(model.sourceMountReadinessCount, 1);
  assert.equal(model.sourceMountContractCount, 1);
  assert.equal(model.approvalConsumptionHandoffCount, 1);
  assert.equal(model.executionReceiptSinkReservationCount, 1);
  assert.equal(model.executionReceiptWriteReadinessCount, 1);
  assert.equal(model.executionReceiptPrewriteBindingCount, 1);
  assert.equal(model.executionReceiptWriterPreflightCount, 1);
  assert.equal(model.runBoundaryPreflightCount, 1);
  assert.equal(model.sandboxProviderContractCount, 1);
  assert.equal(model.sandboxProviderBindingCount, 1);
  assert.equal(model.sandboxProviderSelectionCount, 1);
  assert.equal(model.sandboxProviderVerifierCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeHarnessCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeRunnerReadinessCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeRunnerBindingCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeRunnerEnforcementCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeExecutionBoundaryCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeRefusalCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeApprovalRequestCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeApprovalConsumptionCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeInvocationBoundaryCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeRunnerPreExecutionBoundaryCount, 1);
  assert.equal(model.sandboxProviderRuntimeProbeRunnerControlBindingCount, 1);
  assert.equal(model.sandboxedRebuildRunTestBoundaryCount, 1);
  assert.equal(model.sandboxedRebuildRunTestApprovalRequestCount, 1);
  assert.equal(model.sandboxedRebuildRunTestApprovalConsumptionCount, 1);
  assert.equal(model.sandboxedRebuildRunTestRunnerBindingCount, 1);
  assert.equal(model.sandboxedRebuildRunTestSandboxPolicyCount, 1);
  assert.equal(model.executionReceiptCount, 1);
  assert.equal(model.runnerCommandAllowlistCount, 1);
  assert.equal(model.runnerCommandAllowlistDeclarationCount, 1);
  assert.equal(model.runnerCommandAllowlistEnforcementCount, 1);
  assert.equal(model.runnerSandboxReadinessCount, 1);
  assert.equal(model.sensitiveFileCount, 1);
  assert.deepEqual(model.riskSignals.map((signal) => signal.id), ["package_postinstall_script"]);
  assert.ok(model.guardLines.includes("no execution reported"));
  assert.ok(model.guardLines.includes("execution authority absent"));
  assert.ok(model.guardLines.includes("repo scripts not run"));
  assert.ok(model.guardLines.includes("network access not reported"));
  assert.ok(model.guardLines.includes("readback wrote no receipts"));
  assert.ok(model.guardLines.includes("readback wrote no artifacts"));
  assert.deepEqual(model.blockers, [
    "unknown_repo_execution_not_supported",
    "approval_not_approved",
    "approval_consumption_handoff_preflight_blocked",
    "execution_receipt_sink_reservation_preflight_blocked",
    "execution_receipt_write_readiness_preflight_blocked",
    "execution_receipt_prewrite_binding_preflight_blocked",
    "execution_receipt_writer_preflight_blocked",
    "sandbox_bound",
    "runtime_probe_runner_enforcement_bound",
    "runtime_probe_runner_bound",
  ]);
});

test("IngestReadbackClient calls the bounded readback route with the UI actor", async () => {
  const requests: Array<{ path: string; method: string; actor: string | null; sourceId: string | null; limit: string | null }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      actor: parsed.searchParams.get("actor"),
      sourceId: parsed.searchParams.get("source_id"),
      limit: parsed.searchParams.get("limit"),
    });
    return jsonResponse(fixtureReadback());
  });

  try {
    const client = new IngestReadbackClient("http://127.0.0.1:8000/");
    const response = await client.getReadback({ sourceId: "src_repo", limit: 25 });

    assert.deepEqual(requests, [
      {
        path: "/ingest/readback",
        method: "GET",
        actor: DEFAULT_INGEST_READBACK_ACTOR,
        sourceId: "src_repo",
        limit: "25",
      },
    ]);
    assert.equal(response.kind, "francis.ingest.readback");
  } finally {
    restoreFetch();
  }
});
