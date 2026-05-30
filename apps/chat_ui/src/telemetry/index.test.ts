import assert from "node:assert/strict";
import test from "node:test";

import {
  TelemetryClient,
  parseTelemetryContextFeedbackRecord,
  parseTelemetryContextFeedbackMemoryAssistanceChatContextReadback,
  parseTelemetryContextFeedbackMemoryAssistanceDryRun,
  parseTelemetryContextFeedbackMemoryAssistancePolicy,
  parseTelemetryContextFeedbackMemoryQualityRecord,
  parseTelemetryContextFeedbackMemoryRetrievalReadback,
  parseTelemetryContextFeedbackReview,
  parseTelemetryStatus,
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

test("parseTelemetryStatus preserves Stage 7 source readback truth", () => {
  const status = parseTelemetryStatus({
    ok: true,
    kind: "francis.stage7.telemetry.status",
    stage: "Stage 7 / Telemetry MVP",
    status: "active",
    active: true,
    claim: "explicit_telemetry_events_recorded",
    ts: 123,
    source_total: 3,
    active_source_total: 2,
    sources: [
      {
        id: "terminal",
        label: "Terminal connector",
        description: "Command outcomes and shell context, once explicitly scoped.",
        status: "not_connected",
        active: false,
        visible_indicator: true,
        hidden_sensing: false,
        scope: {
          status: "not_granted",
          allowed_paths: [],
          allowed_processes: [],
          denied_by_default: true,
        },
        redaction: { redact_before_storage: true },
        retention: { stores_raw_events: false },
        signals: [],
        expected_signals: ["command", "cwd"],
        blocked_by: ["connector_not_configured", "operator_scope_not_granted"],
        authority: { telemetry_collection: false, execution_authority: false },
        latest_event: {
          event_id: "tel_terminal_123",
          recorded_ts: 123,
          exit_code: 0,
          cwd: "D:/Francis",
          command: "echo [REDACTED:secret]",
          operation_id: "op_terminal",
          approval_id: "apr_terminal",
          trace_id: "trace_terminal",
          run_id: "run_terminal",
          artifact_dir: "supervised_exec/apr_terminal",
        },
        routes: {
          record: "/telemetry/terminal/events",
        },
      },
      {
        id: "git",
        label: "Git watcher",
        description: "Repository state and file-change activity, once explicitly scoped.",
        status: "snapshot_ready",
        active: true,
        visible_indicator: true,
        hidden_sensing: false,
        scope: {
          status: "repo_root_only",
          allowed_paths: ["D:/Francis"],
          allowed_processes: ["git status"],
          denied_by_default: true,
        },
        redaction: { redact_before_storage: true },
        retention: { stores_raw_events: false },
        signals: ["branch", "dirty_state"],
        expected_signals: ["branch"],
        blocked_by: [],
        authority: { git_watch: false, execution_authority: false },
        latest_snapshot: {
          branch: "main",
          head: "abcdef123456",
          upstream: "origin/main",
          ahead: 0,
          behind: 0,
          dirty: true,
          changed_count: 1,
          changed_paths: [{ status: "M", path: "src/francis/telemetry/git.py" }],
          ts: 123,
        },
        routes: {
          status: "/telemetry/git/status",
        },
      },
      {
        id: "ide_diagnostics",
        label: "IDE diagnostics connector",
        description: "Editor diagnostics and focused file context, once explicitly scoped.",
        status: "explicit_diagnostics_recorded",
        active: true,
        visible_indicator: true,
        hidden_sensing: false,
        scope: {
          status: "write_scope_required",
          allowed_paths: [],
          allowed_processes: [],
          denied_by_default: true,
        },
        redaction: { redact_before_storage: true },
        retention: { stores_raw_events: false, event_count: 1 },
        signals: ["diagnostic_summary"],
        expected_signals: ["file", "diagnostic_code"],
        blocked_by: [],
        authority: { ide_diagnostics: false, execution_authority: false },
        latest_diagnostic: {
          event_id: "tel_ide_123",
          recorded_ts: 123,
          source: "vscode",
          workspace: "D:/Francis",
          file: "src/francis/telemetry/status.py",
          diagnostic_count: 2,
          highest_severity: "error",
          operation_id: "op_ide",
          approval_id: "apr_ide",
          trace_id: "trace_ide",
          run_id: "run_ide",
        },
        routes: {
          record: "/telemetry/ide-diagnostics/events",
          events: "/telemetry/ide-diagnostics/events",
        },
      },
    ],
    redaction: { status: "ready" },
    retention: { status: "bounded_redacted_events", stores_raw_events: false, event_count: 1 },
    sensing: { status: "explicit_events_recorded", hidden_sensing: false },
    governance: { read_only_contract: true, telemetry_collection: false },
    next_smallest_truthful_gap: "stage7_terminal_connector_scope_contract",
  });

  assert.equal(status.kind, "francis.stage7.telemetry.status");
  assert.equal(status.active, true);
  assert.equal(status.active_source_total, 2);
  assert.equal(status.claim, "explicit_telemetry_events_recorded");
  assert.equal(status.sources[0]?.id, "terminal");
  assert.equal(status.sources[0]?.active, false);
  assert.equal(status.sources[0]?.visible_indicator, true);
  assert.equal(status.sources[0]?.hidden_sensing, false);
  assert.equal(status.sources[0]?.scope.status, "not_granted");
  assert.deepEqual(status.sources[0]?.blocked_by, ["connector_not_configured", "operator_scope_not_granted"]);
  assert.equal(status.sources[0]?.latest_event?.event_id, "tel_terminal_123");
  assert.equal(status.sources[0]?.latest_event?.operation_id, "op_terminal");
  assert.equal(status.sources[0]?.routes.record, "/telemetry/terminal/events");
  assert.equal(status.sources[1]?.latest_snapshot?.branch, "main");
  assert.equal(status.sources[1]?.latest_snapshot?.dirty, true);
  assert.equal(status.sources[1]?.latest_snapshot?.changed_paths[0]?.path, "src/francis/telemetry/git.py");
  assert.equal(status.sources[1]?.routes.status, "/telemetry/git/status");
  assert.equal(status.sources[2]?.latest_diagnostic?.event_id, "tel_ide_123");
  assert.equal(status.sources[2]?.latest_diagnostic?.highest_severity, "error");
  assert.equal(status.sources[2]?.routes.record, "/telemetry/ide-diagnostics/events");
  assert.equal(status.governance.telemetry_collection, false);
});

test("TelemetryClient requests the Stage 7 status endpoint", async () => {
  const requests: Array<{ path: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.status",
      stage: "Stage 7 / Telemetry MVP",
      status: "inactive",
      active: false,
      claim: "telemetry_posture_contract_only",
      source_total: 0,
      active_source_total: 0,
      sources: [],
      redaction: {},
      retention: {},
      sensing: {},
      governance: {},
      next_smallest_truthful_gap: "stage7_terminal_connector_scope_contract",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const status = await client.getStatus();
    assert.equal(status.status, "inactive");
    assert.deepEqual(requests, [{ path: "/telemetry/status", method: "GET" }]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackReview preserves redacted feedback quality readback", () => {
  const review = parseTelemetryContextFeedbackReview({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_review",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "review_ready",
    capture_mode: "explicit_operator_feedback_review",
    reviewed_event_count: 3,
    total: 5,
    limit: 3,
    truncated: true,
    rating_counts: { useful: 1, not_useful: "1", neutral: 1 },
    source_counts: { terminal: 2, git: 1 },
    tag_counts: { accurate: 2 },
    quality_signals: ["operator_reported_useful_context", "operator_reported_context_misses"],
    latest_feedback: {
      feedback_id: "fb_123",
      context_id: "ctx_123",
      surface: "chat",
      rating: "not_useful",
      source_ids: ["terminal"],
      tags: ["missing"],
      recorded_ts: 456,
      notes: "must not be typed",
      meta: { prompt_body: "must not be typed" },
    },
    redacted: true,
    hidden_sensing: false,
    stores_prompt_body: false,
    stores_model_response: false,
    trains_model: false,
    writes_memory: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, uses_explicit_operator_feedback_only: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
  });

  assert.equal(review.kind, "francis.stage7.telemetry.context_feedback_review");
  assert.equal(review.status, "review_ready");
  assert.equal(review.reviewed_event_count, 3);
  assert.equal(review.total, 5);
  assert.equal(review.truncated, true);
  assert.equal(review.rating_counts.not_useful, 1);
  assert.deepEqual(review.quality_signals, [
    "operator_reported_useful_context",
    "operator_reported_context_misses",
  ]);
  assert.equal(review.latest_feedback?.context_id, "ctx_123");
  assert.equal(review.latest_feedback?.rating, "not_useful");
  assert.deepEqual(review.latest_feedback?.source_ids, ["terminal"]);
  assert.equal("notes" in (review.latest_feedback ?? {}), false);
  assert.equal("meta" in (review.latest_feedback ?? {}), false);
  assert.equal(review.redacted, true);
  assert.equal(review.hidden_sensing, false);
  assert.equal(review.stores_prompt_body, false);
  assert.equal(review.stores_model_response, false);
  assert.equal(review.trains_model, false);
  assert.equal(review.writes_memory, false);
  assert.equal(review.grants_execution_authority, false);
  assert.equal(review.grants_mutation_authority, false);
  assert.equal(review.governance.read_only, true);
});

test("TelemetryClient requests the Stage 7 context feedback review endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_review",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "empty",
      capture_mode: "explicit_operator_feedback_review",
      reviewed_event_count: 0,
      total: 0,
      limit: 25,
      truncated: false,
      rating_counts: { useful: 0, not_useful: 0, neutral: 0 },
      source_counts: {},
      tag_counts: {},
      quality_signals: ["no_explicit_context_feedback_recorded"],
      latest_feedback: {},
      redacted: true,
      hidden_sensing: false,
      stores_prompt_body: false,
      stores_model_response: false,
      trains_model: false,
      writes_memory: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const review = await client.getContextFeedbackReview({ limit: 25 });
    assert.equal(review.status, "empty");
    assert.deepEqual(requests, [
      { path: "/telemetry/context/feedback/review", search: "?limit=25", method: "GET" },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryQualityRecord preserves governed write readback", () => {
  const record = parseTelemetryContextFeedbackMemoryQualityRecord({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_quality.record",
    status: "recorded",
    source_id: "telemetry_context",
    memory_event_id: "evt-feedback-quality",
    writes_memory: true,
    quality: {
      status: "memory_candidate_ready",
      memory_write_candidate: {
        action_type: "telemetry.context_feedback.quality_review",
      },
    },
    memory_event: {
      id: "evt-feedback-quality",
      item: {
        action_type: "telemetry.context_feedback.quality_review",
      },
    },
    governance: {
      required_scope: "memory.timeline.write",
      explicit_operator_decision: true,
      memory_timeline_contract_enforced: true,
    },
  });

  assert.equal(record.ok, true);
  assert.equal(record.status, "recorded");
  assert.equal(record.source_id, "telemetry_context");
  assert.equal(record.memory_event_id, "evt-feedback-quality");
  assert.equal(record.writes_memory, true);
  assert.equal(record.governance.required_scope, "memory.timeline.write");
  assert.equal(record.governance.explicit_operator_decision, true);
  assert.equal(record.memory_event?.id, "evt-feedback-quality");
  assert.equal(record.quality.status, "memory_candidate_ready");
});

test("TelemetryClient records Stage 7 context feedback memory quality through the governed POST route", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(init?.body?.toString() ?? "{}") as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_quality.record",
      status: "recorded",
      source_id: "telemetry_context",
      memory_event_id: "evt-from-ui",
      writes_memory: true,
      quality: { status: "memory_candidate_ready" },
      memory_event: { id: "evt-from-ui" },
      governance: {
        required_scope: "memory.timeline.write",
        explicit_operator_decision: true,
        memory_timeline_contract_enforced: true,
      },
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const record = await client.recordContextFeedbackMemoryQuality({
      actor: "chat_ui.system",
      reason: "record telemetry context feedback memory quality from operator UI",
      limit: 25,
      event_id: "evt-from-ui",
    });
    assert.equal(record.status, "recorded");
    assert.equal(record.memory_event_id, "evt-from-ui");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-quality",
        method: "POST",
        body: {
          actor: "chat_ui.system",
          reason: "record telemetry context feedback memory quality from operator UI",
          limit: 25,
          event_id: "evt-from-ui",
        },
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryRetrievalReadback preserves filtered memory events", () => {
  const readback = parseTelemetryContextFeedbackMemoryRetrievalReadback({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_retrieval_readback",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "readback_ready",
    count: 1,
    total: 1,
    skipped_count: 0,
    items: [
      {
        id: "evt-feedback-quality",
        kind: "telemetry_context_feedback_quality_review",
        action_type: "telemetry.context_feedback.quality_review",
        classification: "operator_feedback_quality_signal",
        confidence: "0.75",
        retention: { policy: "stage7_context_feedback_quality" },
        payload: {
          rating_counts: { useful: 1, not_useful: 0, neutral: 0 },
          latest_feedback: { context_id: "ctx_123" },
        },
      },
    ],
    reads_memory: true,
    writes_memory: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: {
      read_only: true,
      uses_policy_filters: true,
    },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
  });

  assert.equal(readback.kind, "francis.stage7.telemetry.context_feedback_memory_retrieval_readback");
  assert.equal(readback.status, "readback_ready");
  assert.equal(readback.count, 1);
  assert.equal(readback.items[0]?.id, "evt-feedback-quality");
  assert.equal(readback.items[0]?.confidence, 0.75);
  assert.equal(readback.items[0]?.retention.policy, "stage7_context_feedback_quality");
  assert.equal(readback.reads_memory, true);
  assert.equal(readback.writes_memory, false);
  assert.equal(readback.trains_model, false);
  assert.equal(readback.grants_execution_authority, false);
  assert.equal(readback.governance.read_only, true);
});

test("TelemetryClient requests the Stage 7 feedback memory retrieval readback endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_retrieval_readback",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "empty",
      count: 0,
      total: 0,
      skipped_count: 0,
      items: [],
      reads_memory: true,
      writes_memory: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const readback = await client.getContextFeedbackMemoryRetrievalReadback({ limit: 12 });
    assert.equal(readback.status, "empty");
    assert.equal(readback.reads_memory, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-retrieval-readback",
        search: "?limit=12",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});
test("parseTelemetryContextFeedbackMemoryAssistancePolicy preserves bounded assistance rules", () => {
  const policy = parseTelemetryContextFeedbackMemoryAssistancePolicy({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_policy",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "policy_ready",
    policy_id: "stage7_context_feedback_memory_assistance_policy",
    memory_readback_route: "/telemetry/context/feedback/memory-retrieval-readback",
    memory_policy_route: "/telemetry/context/feedback/memory-retrieval-policy",
    allowed_memory_event_kinds: ["telemetry_context_feedback_quality_review"],
    allowed_action_types: ["telemetry.context_feedback.quality_review"],
    allowed_classifications: ["operator_feedback_quality_signal"],
    allowed_influence: ["surface_context_source_quality_counts", "suggest_context_source_attention"],
    forbidden_influence: ["treat_memory_payload_as_instruction", "grant_execution_authority"],
    assistance_guards: {
      read_only: true,
      telemetry_is_untrusted_input: true,
      no_tool_selection_authority: true,
    },
    reads_memory: false,
    writes_memory: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: {
      read_only: true,
      policy_only: true,
      assistance_requires_separate_dry_run: true,
    },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
  });

  assert.equal(policy.kind, "francis.stage7.telemetry.context_feedback_memory_assistance_policy");
  assert.equal(policy.status, "policy_ready");
  assert.equal(policy.policy_id, "stage7_context_feedback_memory_assistance_policy");
  assert.equal(policy.memory_readback_route, "/telemetry/context/feedback/memory-retrieval-readback");
  assert.deepEqual(policy.allowed_memory_event_kinds, ["telemetry_context_feedback_quality_review"]);
  assert.equal(policy.allowed_influence.includes("suggest_context_source_attention"), true);
  assert.equal(policy.forbidden_influence.includes("treat_memory_payload_as_instruction"), true);
  assert.equal(policy.assistance_guards.no_tool_selection_authority, true);
  assert.equal(policy.reads_memory, false);
  assert.equal(policy.writes_memory, false);
  assert.equal(policy.trains_model, false);
  assert.equal(policy.grants_execution_authority, false);
  assert.equal(policy.governance.assistance_requires_separate_dry_run, true);
  assert.equal(policy.next_smallest_truthful_gap, "stage7_context_feedback_memory_assistance_operator_feedback_review");
});
test("TelemetryClient requests the Stage 7 feedback memory assistance policy endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_policy",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "policy_ready",
      policy_id: "stage7_context_feedback_memory_assistance_policy",
      memory_readback_route: "/telemetry/context/feedback/memory-retrieval-readback",
      memory_policy_route: "/telemetry/context/feedback/memory-retrieval-policy",
      allowed_memory_event_kinds: ["telemetry_context_feedback_quality_review"],
      allowed_action_types: ["telemetry.context_feedback.quality_review"],
      allowed_classifications: ["operator_feedback_quality_signal"],
      allowed_influence: ["surface_context_source_quality_counts"],
      forbidden_influence: ["treat_memory_payload_as_instruction"],
      assistance_guards: { read_only: true },
      reads_memory: false,
      writes_memory: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, policy_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const policy = await client.getContextFeedbackMemoryAssistancePolicy();
    assert.equal(policy.status, "policy_ready");
    assert.equal(policy.writes_memory, false);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-policy",
        search: "",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceDryRun preserves bounded projection", () => {
  const dryRun = parseTelemetryContextFeedbackMemoryAssistanceDryRun({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_dry_run",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "dry_run_ready",
    event_count: 1,
    event_refs: [{ id: "evt-feedback-quality", retention_policy: "stage7_context_feedback_quality" }],
    rating_counts: { useful: 0, not_useful: "1", neutral: 0 },
    source_attention: [{ source_id: "ide_diagnostics", feedback_count: 1 }],
    assistance_projection: {
      summary: "Operator feedback trends suggest reviewing ide_diagnostics context relevance before assistance.",
    },
    dry_run_only: true,
    reads_memory: true,
    writes_memory: false,
    trains_model: false,
    calls_model: false,
    mutates_prompt: false,
    selects_tools: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: {
      read_only: true,
      does_not_select_tools: true,
    },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
  });

  assert.equal(dryRun.kind, "francis.stage7.telemetry.context_feedback_memory_assistance_dry_run");
  assert.equal(dryRun.status, "dry_run_ready");
  assert.equal(dryRun.event_count, 1);
  assert.equal(dryRun.rating_counts.not_useful, 1);
  assert.equal(dryRun.source_attention[0]?.source_id, "ide_diagnostics");
  assert.equal(dryRun.assistance_projection.summary, "Operator feedback trends suggest reviewing ide_diagnostics context relevance before assistance.");
  assert.equal(dryRun.dry_run_only, true);
  assert.equal(dryRun.reads_memory, true);
  assert.equal(dryRun.writes_memory, false);
  assert.equal(dryRun.calls_model, false);
  assert.equal(dryRun.mutates_prompt, false);
  assert.equal(dryRun.selects_tools, false);
  assert.equal(dryRun.governance.does_not_select_tools, true);
});

test("TelemetryClient requests the Stage 7 feedback memory assistance dry-run endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_dry_run",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "empty",
      event_count: 0,
      event_refs: [],
      rating_counts: { useful: 0, not_useful: 0, neutral: 0 },
      source_attention: [],
      assistance_projection: { summary: "No governed feedback-quality memory is available for assistance dry run." },
      dry_run_only: true,
      reads_memory: true,
      writes_memory: false,
      trains_model: false,
      calls_model: false,
      mutates_prompt: false,
      selects_tools: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, dry_run_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const dryRun = await client.getContextFeedbackMemoryAssistanceDryRun({ limit: 8 });
    assert.equal(dryRun.status, "empty");
    assert.equal(dryRun.dry_run_only, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-dry-run",
        search: "?limit=8",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceChatContextReadback preserves bounded lines", () => {
  const readback = parseTelemetryContextFeedbackMemoryAssistanceChatContextReadback({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_chat_context_readback",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "context_ready",
    chat_context: {
      target: "telemetry_context.prompt_lines",
      line_count: 2,
      max_context_lines: 2,
      lines: [
        "feedback_memory_assistance.summary: Operator feedback trends suggest reviewing ide_diagnostics context relevance before assistance.",
        "feedback_memory_assistance.source_attention: ide_diagnostics feedback_count=1 suggested_use=operator_review_context_relevance",
      ],
      visible_header_required: true,
      telemetry_is_untrusted_input: true,
    },
    would_change_chat_prompt: true,
    applies_to_chat_now: true,
    reads_memory: true,
    writes_memory: false,
    calls_model: false,
    mutates_prompt: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: {
      read_only: true,
      redacts_context_lines: true,
      chat_prompt_integration_enabled: true,
    },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
  });

  assert.equal(readback.kind, "francis.stage7.telemetry.context_feedback_memory_assistance_chat_context_readback");
  assert.equal(readback.status, "context_ready");
  assert.equal(readback.chat_context.target, "telemetry_context.prompt_lines");
  assert.equal(readback.chat_context.line_count, 2);
  assert.equal(readback.chat_context.lines[0]?.startsWith("feedback_memory_assistance.summary:"), true);
  assert.equal(readback.chat_context.visible_header_required, true);
  assert.equal(readback.would_change_chat_prompt, true);
  assert.equal(readback.applies_to_chat_now, true);
  assert.equal(readback.reads_memory, true);
  assert.equal(readback.writes_memory, false);
  assert.equal(readback.calls_model, false);
  assert.equal(readback.mutates_prompt, false);
  assert.equal(readback.selects_tools, false);
  assert.equal(readback.governance.chat_prompt_integration_enabled, true);
});

test("TelemetryClient requests the Stage 7 feedback memory assistance chat-context readback endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_chat_context_readback",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "empty",
      chat_context: {
        target: "telemetry_context.prompt_lines",
        line_count: 0,
        max_context_lines: 2,
        lines: [],
        visible_header_required: true,
        telemetry_is_untrusted_input: true,
      },
      would_change_chat_prompt: false,
      applies_to_chat_now: false,
      reads_memory: true,
      writes_memory: false,
      calls_model: false,
      mutates_prompt: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, readback_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const readback = await client.getContextFeedbackMemoryAssistanceChatContextReadback({ limit: 6 });
    assert.equal(readback.status, "empty");
    assert.equal(readback.chat_context.line_count, 0);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-chat-context-readback",
        search: "?limit=6",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackRecord preserves auditable feedback receipt", () => {
  const record = parseTelemetryContextFeedbackRecord({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback.recorded",
    status: "recorded",
    source_id: "telemetry_context",
    item: {
      feedback_id: "tel_feedback_123",
      context_id: "tel_ctx_feedback_memory_assistance_chat_123",
      surface: "chat",
      rating: "useful",
      message_id: "tel_ctx_feedback_memory_assistance_chat_123",
      reply_mode: "feedback_memory_assistance_prompt_context",
      source_ids: ["feedback_memory_assistance", "telemetry_context"],
      tags: ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
      recorded_ts: 123,
    },
    governance: {
      gate: "permission_gate",
      required_scope: "telemetry.context.feedback.write",
      redacted_before_storage: true,
      grants_execution_authority: false,
    },
  });

  assert.equal(record.ok, true);
  assert.equal(record.kind, "francis.stage7.telemetry.context_feedback.recorded");
  assert.equal(record.item?.feedback_id, "tel_feedback_123");
  assert.equal(record.item?.context_id, "tel_ctx_feedback_memory_assistance_chat_123");
  assert.deepEqual(record.item?.source_ids, ["feedback_memory_assistance", "telemetry_context"]);
  assert.equal(record.governance.required_scope, "telemetry.context.feedback.write");
});

test("TelemetryClient records chat feedback-memory assistance feedback through governed route", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    requests.push({ path: parsed.pathname, method: init?.method ?? "GET", body });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback.recorded",
      status: "recorded",
      source_id: "telemetry_context",
      item: {
        feedback_id: "tel_feedback_456",
        context_id: body.context_id,
        surface: body.surface,
        rating: body.rating,
        message_id: body.message_id,
        reply_mode: body.reply_mode,
        source_ids: body.source_ids,
        tags: body.tags,
      },
      governance: {
        gate: "permission_gate",
        required_scope: "telemetry.context.feedback.write",
        grants_execution_authority: false,
      },
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const record = await client.recordContextFeedback({
      actor: "chat_ui.system",
      reason: "record chat feedback memory assistance useful",
      context_id: "tel_ctx_feedback_memory_assistance_chat_456",
      surface: "chat",
      rating: "useful",
      message_id: "tel_ctx_feedback_memory_assistance_chat_456",
      reply_mode: "feedback_memory_assistance_prompt_context",
      source_ids: ["feedback_memory_assistance", "telemetry_context"],
      tags: ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
      meta: { feedback_target_kind: "feedback_memory_assistance_prompt_integration" },
    });

    assert.equal(record.ok, true);
    assert.equal(record.item?.feedback_id, "tel_feedback_456");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback",
        method: "POST",
        body: {
          actor: "chat_ui.system",
          reason: "record chat feedback memory assistance useful",
          rating: "useful",
          surface: "chat",
          source_ids: ["feedback_memory_assistance", "telemetry_context"],
          tags: ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
          meta: { feedback_target_kind: "feedback_memory_assistance_prompt_integration" },
          context_id: "tel_ctx_feedback_memory_assistance_chat_456",
          message_id: "tel_ctx_feedback_memory_assistance_chat_456",
          reply_mode: "feedback_memory_assistance_prompt_context",
        },
      },
    ]);
  } finally {
    restore();
  }
});
