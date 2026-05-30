import assert from "node:assert/strict";
import test from "node:test";

import {
  TelemetryClient,
  parseTelemetryContextFeedbackRecord,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionReadback,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionRecord,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback,
  parseTelemetryContextFeedbackMemoryAssistanceActionQualitySignalReview,
  parseTelemetryContextFeedbackMemoryAssistanceGitContextSignal,
  parseTelemetryContextFeedbackMemoryAssistanceIdeContextSignal,
  parseTelemetryContextFeedbackMemoryAssistanceMemoryPoisoningReview,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorContextSurfaceReview,
  parseTelemetryContextFeedbackMemoryAssistancePrimaryLoopEvidenceReview,
  parseTelemetryContextFeedbackMemoryAssistanceSensingIndicatorSummary,
  parseTelemetryContextFeedbackMemoryAssistanceTerminalContextSignal,
  parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackReview,
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
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality preserves candidate posture", () => {
  const quality = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_quality",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "memory_candidate_ready",
    capture_mode: "explicit_feedback_memory_assistance_operator_feedback_memory_quality_review",
    target: "feedback_memory_assistance_prompt_integration",
    review: {
      reviewed_event_count: 2,
    },
    memory_write_candidate: {
      action_type: "telemetry.context_feedback.memory_assistance_operator_feedback_review",
    },
    memory_write_route: "/memory/timeline/record",
    memory_quality_record_route: "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
    required_scope: "memory.timeline.write",
    operator_decision_required: true,
    writes_memory: false,
    redacted: true,
    hidden_sensing: false,
    stores_prompt_body: false,
    stores_model_response: false,
    trains_model: false,
    calls_model: false,
    selects_tools: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: {
      candidate_only: true,
      target: "feedback_memory_assistance_prompt_integration",
    },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
  });

  assert.equal(quality.ok, true);
  assert.equal(quality.status, "memory_candidate_ready");
  assert.equal(quality.target, "feedback_memory_assistance_prompt_integration");
  assert.equal(quality.required_scope, "memory.timeline.write");
  assert.equal(quality.operator_decision_required, true);
  assert.equal(quality.writes_memory, false);
  assert.equal(quality.calls_model, false);
  assert.equal(quality.selects_tools, false);
  assert.equal(quality.review.reviewed_event_count, 2);
  assert.equal(
    quality.memory_write_candidate.action_type,
    "telemetry.context_feedback.memory_assistance_operator_feedback_review",
  );
  assert.equal(quality.governance.candidate_only, true);
});

test("TelemetryClient uses governed feedback-memory assistance memory-quality routes", async () => {
  const requests: Array<{ path: string; search: string; method: string; body?: Record<string, unknown> }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    const method = init?.method ?? "GET";
    const body = init?.body ? (JSON.parse(init.body.toString()) as Record<string, unknown>) : undefined;
    requests.push({ path: parsed.pathname, search: parsed.search, method, body });
    if (method === "POST") {
      return jsonResponse({
        ok: true,
        kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_quality.record",
        status: "recorded",
        source_id: "telemetry_context",
        memory_event_id: "evt-assistance-quality",
        writes_memory: true,
        quality: { status: "memory_candidate_ready" },
        memory_event: { id: "evt-assistance-quality" },
        governance: {
          required_scope: "memory.timeline.write",
          explicit_operator_decision: true,
        },
      });
    }
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_quality",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "memory_candidate_ready",
      capture_mode: "explicit_feedback_memory_assistance_operator_feedback_memory_quality_review",
      target: "feedback_memory_assistance_prompt_integration",
      review: { reviewed_event_count: 1 },
      memory_write_candidate: {
        action_type: "telemetry.context_feedback.memory_assistance_operator_feedback_review",
      },
      memory_write_route: "/memory/timeline/record",
      memory_quality_record_route: "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
      required_scope: "memory.timeline.write",
      operator_decision_required: true,
      writes_memory: false,
      redacted: true,
      hidden_sensing: false,
      stores_prompt_body: false,
      stores_model_response: false,
      trains_model: false,
      calls_model: false,
      selects_tools: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { candidate_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const quality = await client.getContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality({ limit: 25 });
    const record = await client.recordContextFeedbackMemoryAssistanceOperatorFeedbackMemoryQuality({
      actor: "chat_ui.system",
      reason: "record feedback memory assistance operator quality",
      limit: 25,
      event_id: "evt-assistance-quality",
    });

    assert.equal(quality.status, "memory_candidate_ready");
    assert.equal(record.status, "recorded");
    assert.equal(record.memory_event_id, "evt-assistance-quality");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
        search: "?limit=25",
        method: "GET",
        body: undefined,
      },
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
        search: "",
        method: "POST",
        body: {
          actor: "chat_ui.system",
          reason: "record feedback memory assistance operator quality",
          limit: 25,
          event_id: "evt-assistance-quality",
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
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback preserves targeted memory events", () => {
  const readback = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_readback",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "readback_ready",
    target: "feedback_memory_assistance_prompt_integration",
    count: 1,
    total: 1,
    skipped_count: 0,
    items: [
      {
        id: "evt-assistance-quality",
        kind: "telemetry_context_feedback_memory_assistance_operator_feedback_review",
        action_type: "telemetry.context_feedback.memory_assistance_operator_feedback_review",
        classification: "operator_feedback_memory_assistance_quality_signal",
        confidence: "0.76",
        retention: { policy: "stage7_feedback_memory_assistance_operator_feedback_quality" },
        payload: {
          target: "feedback_memory_assistance_prompt_integration",
          rating_counts: { useful: 1, not_useful: 0, neutral: 0 },
        },
      },
    ],
    reads_memory: true,
    writes_memory: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: {
      read_only: true,
      uses_assistance_policy_filters: true,
    },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
  });

  assert.equal(readback.status, "readback_ready");
  assert.equal(readback.target, "feedback_memory_assistance_prompt_integration");
  assert.equal(readback.count, 1);
  assert.equal(readback.items[0]?.kind, "telemetry_context_feedback_memory_assistance_operator_feedback_review");
  assert.equal(
    readback.items[0]?.action_type,
    "telemetry.context_feedback.memory_assistance_operator_feedback_review",
  );
  assert.equal(readback.reads_memory, true);
  assert.equal(readback.writes_memory, false);
  assert.equal(readback.calls_model, false);
  assert.equal(readback.selects_tools, false);
  assert.equal(readback.governance.uses_assistance_policy_filters, true);
});

test("TelemetryClient requests the targeted feedback-memory assistance memory readback endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_readback",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "empty",
      target: "feedback_memory_assistance_prompt_integration",
      count: 0,
      total: 0,
      skipped_count: 0,
      items: [],
      reads_memory: true,
      writes_memory: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const readback = await client.getContextFeedbackMemoryAssistanceOperatorFeedbackMemoryReadback({ limit: 25 });
    assert.equal(readback.status, "empty");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-memory-readback",
        search: "?limit=25",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit preserves loop evidence", () => {
  const audit = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_audit",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "loop_observed",
    target: "feedback_memory_assistance_prompt_integration",
    requirements: [
      { id: "targeted_operator_feedback_review", ready: true },
      { id: "operator_ui_recording_surface", ready: true },
    ],
    ready_count: 6,
    required_count: 6,
    loop_observed: true,
    reviewed_event_count: 1,
    memory_event_count: 1,
    dry_run_event_count: 1,
    chat_context_line_count: 2,
    routes: {
      memory_quality: "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
    },
    reads_memory: true,
    writes_memory: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, audit_only: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
  });

  assert.equal(audit.status, "loop_observed");
  assert.equal(audit.loop_observed, true);
  assert.equal(audit.ready_count, 6);
  assert.equal(audit.required_count, 6);
  assert.equal(audit.requirements.length, 2);
  assert.equal(audit.memory_event_count, 1);
  assert.equal(audit.chat_context_line_count, 2);
  assert.equal(audit.writes_memory, false);
  assert.equal(audit.calls_model, false);
  assert.equal(audit.selects_tools, false);
  assert.equal(audit.governance.audit_only, true);
});

test("TelemetryClient requests the targeted feedback-memory assistance loop audit endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_audit",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "awaiting_feedback",
      target: "feedback_memory_assistance_prompt_integration",
      requirements: [],
      ready_count: 1,
      required_count: 6,
      loop_observed: false,
      reviewed_event_count: 0,
      memory_event_count: 0,
      dry_run_event_count: 0,
      chat_context_line_count: 0,
      routes: {},
      reads_memory: true,
      writes_memory: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, audit_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const audit = await client.getContextFeedbackMemoryAssistanceOperatorFeedbackLoopAudit({ limit: 25 });
    assert.equal(audit.status, "awaiting_feedback");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-audit",
        search: "?limit=25",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample preserves sample boundaries", () => {
  const sample = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_sample",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "sample_ready",
    target: "feedback_memory_assistance_prompt_integration",
    sample_id: "stage7_feedback_memory_assistance_operator_feedback_loop_e2e_sample",
    loop_observed: true,
    audit: { status: "loop_observed", ready_count: 6, required_count: 6 },
    chat_context: {
      status: "context_ready",
      line_count: 2,
      lines: ["feedback_memory_assistance.summary: bounded"],
    },
    sample_chat_request: { route: "/chat/send", executed_by_sample: false },
    sample_feedback_request: { route: "/telemetry/context/feedback", executed_by_sample: false },
    sample_memory_record_request: {
      route: "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
      executed_by_sample: false,
    },
    reads_memory: true,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, sample_only: true },
    next_smallest_truthful_gap:
      "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
  });

  assert.equal(sample.status, "sample_ready");
  assert.equal(sample.loop_observed, true);
  assert.equal(sample.audit.status, "loop_observed");
  assert.equal(sample.chat_context.line_count, 2);
  assert.equal(sample.sample_chat_request.route, "/chat/send");
  assert.equal(sample.sample_feedback_request.route, "/telemetry/context/feedback");
  assert.equal(sample.writes_memory, false);
  assert.equal(sample.writes_feedback, false);
  assert.equal(sample.sends_chat, false);
  assert.equal(sample.calls_model, false);
  assert.equal(sample.governance.sample_only, true);
});

test("TelemetryClient requests the targeted feedback-memory assistance loop e2e sample endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_sample",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "awaiting_loop_evidence",
      target: "feedback_memory_assistance_prompt_integration",
      sample_id: "stage7_feedback_memory_assistance_operator_feedback_loop_e2e_sample",
      loop_observed: false,
      audit: { status: "awaiting_feedback" },
      chat_context: { line_count: 0 },
      sample_chat_request: { route: "/chat/send" },
      sample_feedback_request: { route: "/telemetry/context/feedback" },
      sample_memory_record_request: {
        route: "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
      },
      reads_memory: true,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, sample_only: true },
      next_smallest_truthful_gap:
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const sample = await client.getContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eSample({ limit: 25 });
    assert.equal(sample.status, "awaiting_loop_evidence");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-sample",
        search: "?limit=25",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit preserves criteria", () => {
  const audit = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_acceptance_audit",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "acceptance_ready",
    target: "feedback_memory_assistance_prompt_integration",
    sample_id: "stage7_feedback_memory_assistance_operator_feedback_loop_e2e_sample",
    acceptance_ready: true,
    acceptance_criteria: [
      { id: "loop_audit_ready", ready: true },
      { id: "sample_non_execution_guarded", ready: true },
    ],
    ready_count: 6,
    required_count: 6,
    sample: { status: "sample_ready", loop_observed: true },
    reads_memory: true,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, acceptance_audit_only: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
  });

  assert.equal(audit.status, "acceptance_ready");
  assert.equal(audit.acceptance_ready, true);
  assert.equal(audit.ready_count, 6);
  assert.equal(audit.required_count, 6);
  assert.equal(audit.acceptance_criteria.length, 2);
  assert.equal(audit.sample.status, "sample_ready");
  assert.equal(audit.writes_memory, false);
  assert.equal(audit.writes_feedback, false);
  assert.equal(audit.sends_chat, false);
  assert.equal(audit.calls_model, false);
  assert.equal(audit.governance.acceptance_audit_only, true);
});

test("TelemetryClient requests the targeted feedback-memory assistance e2e acceptance audit endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_acceptance_audit",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "awaiting_sample_evidence",
      target: "feedback_memory_assistance_prompt_integration",
      sample_id: "stage7_feedback_memory_assistance_operator_feedback_loop_e2e_sample",
      acceptance_ready: false,
      acceptance_criteria: [],
      ready_count: 3,
      required_count: 6,
      sample: { status: "awaiting_loop_evidence" },
      reads_memory: true,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, acceptance_audit_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const audit = await client.getContextFeedbackMemoryAssistanceOperatorFeedbackLoopE2eAcceptanceAudit({ limit: 25 });
    assert.equal(audit.status, "awaiting_sample_evidence");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-acceptance-audit",
        search: "?limit=25",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback preserves observed evidence", () => {
  const readback = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_live_sample_readback",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "live_sample_observed",
    target: "feedback_memory_assistance_prompt_integration",
    live_sample_observed: true,
    criteria: [
      { id: "chat_send_ledger_readback", ready: true },
      { id: "memory_quality_readback", ready: true },
    ],
    ready_count: 4,
    required_count: 4,
    acceptance: { acceptance_ready: true },
    chat: { status: "applied", line_count: 2 },
    feedback: { rating: "useful" },
    memory: { event_id: "evt-feedback-memory-assistance-live-sample" },
    reads_conversation_ledger: true,
    reads_feedback: true,
    reads_memory: true,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, live_sample_readback_only: true },
    next_smallest_truthful_gap:
      "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_review",
  });

  assert.equal(readback.status, "live_sample_observed");
  assert.equal(readback.live_sample_observed, true);
  assert.equal(readback.ready_count, 4);
  assert.equal(readback.required_count, 4);
  assert.equal(readback.criteria.length, 2);
  assert.equal(readback.chat.status, "applied");
  assert.equal(readback.memory.event_id, "evt-feedback-memory-assistance-live-sample");
  assert.equal(readback.reads_conversation_ledger, true);
  assert.equal(readback.writes_memory, false);
  assert.equal(readback.writes_feedback, false);
  assert.equal(readback.sends_chat, false);
  assert.equal(readback.governance.live_sample_readback_only, true);
});

test("TelemetryClient requests the targeted feedback-memory assistance live sample readback endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_live_sample_readback",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "awaiting_live_sample_evidence",
      target: "feedback_memory_assistance_prompt_integration",
      live_sample_observed: false,
      criteria: [],
      ready_count: 0,
      required_count: 4,
      acceptance: { acceptance_ready: false },
      chat: {},
      feedback: {},
      memory: {},
      reads_conversation_ledger: true,
      reads_feedback: true,
      reads_memory: true,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, live_sample_readback_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const readback = await client.getContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleReadback({
      limit: 25,
    });
    assert.equal(readback.status, "awaiting_live_sample_evidence");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-readback",
        search: "?limit=25",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview preserves operator gate", () => {
  const review = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_review",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "operator_review_ready",
    target: "feedback_memory_assistance_prompt_integration",
    operator_review_ready: true,
    live_sample_observed: true,
    ready_count: 4,
    required_count: 4,
    criteria: [{ id: "chat_send_ledger_readback", ready: true }],
    review_items: [{ id: "memory_quality_readback", ready: true }],
    live_sample: { status: "live_sample_observed" },
    evidence: { chat: { status: "applied" }, memory: { event_id: "evt-live" } },
    operator_decision: { required: true, recorded: false },
    reads_conversation_ledger: true,
    reads_feedback: true,
    reads_memory: true,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, operator_review_projection_only: true },
    next_smallest_truthful_gap:
      "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_decision",
  });

  assert.equal(review.status, "operator_review_ready");
  assert.equal(review.operator_review_ready, true);
  assert.equal(review.live_sample_observed, true);
  assert.equal(review.ready_count, 4);
  assert.equal(review.required_count, 4);
  assert.equal(review.criteria.length, 1);
  assert.equal(review.review_items.length, 1);
  assert.equal(review.live_sample.status, "live_sample_observed");
  assert.equal((review.evidence.memory as Record<string, unknown>).event_id, "evt-live");
  assert.equal(review.operator_decision.required, true);
  assert.equal(review.operator_decision.recorded, false);
  assert.equal(review.reads_conversation_ledger, true);
  assert.equal(review.writes_memory, false);
  assert.equal(review.sends_chat, false);
  assert.equal(review.governance.operator_review_projection_only, true);
  assert.equal(
    review.next_smallest_truthful_gap,
    "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_decision",
  );
});

test("TelemetryClient requests the targeted feedback-memory assistance live sample operator review endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_review",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "awaiting_live_sample_evidence",
      target: "feedback_memory_assistance_prompt_integration",
      operator_review_ready: false,
      live_sample_observed: false,
      ready_count: 0,
      required_count: 4,
      criteria: [],
      review_items: [],
      live_sample: { status: "awaiting_live_sample_evidence" },
      evidence: {},
      operator_decision: { required: false, recorded: false },
      reads_conversation_ledger: true,
      reads_feedback: true,
      reads_memory: true,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, operator_review_projection_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const review = await client.getContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorReview({
      limit: 30,
    });
    assert.equal(review.status, "awaiting_live_sample_evidence");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-review",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionRecord preserves receipt guards", () => {
  const record = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionRecord({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision.record",
    status: "recorded",
    source_id: "telemetry_context",
    target: "feedback_memory_assistance_prompt_integration",
    review: { status: "operator_review_ready" },
    receipt: { receipt_id: "tel_fma_live_decision_123", decision: "accepted" },
    receipt_id: "tel_fma_live_decision_123",
    decision: "accepted",
    writes_receipt: true,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { required_scope: "telemetry.context.feedback.write", explicit_operator_decision: true },
    next_smallest_truthful_gap:
      "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_receipt_readback",
  });

  assert.equal(record.status, "recorded");
  assert.equal(record.receipt_id, "tel_fma_live_decision_123");
  assert.equal(record.decision, "accepted");
  assert.equal(record.writes_receipt, true);
  assert.equal(record.writes_memory, false);
  assert.equal(record.sends_chat, false);
  assert.equal(record.receipt?.decision, "accepted");
  assert.equal(record.governance.required_scope, "telemetry.context.feedback.write");
  assert.equal(record.grants_execution_authority, false);
});

test("TelemetryClient records the live sample operator decision through the governed POST route", async () => {
  const requests: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: init?.method ?? "GET",
      body: JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>,
    });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision.record",
      status: "recorded",
      source_id: "telemetry_context",
      target: "feedback_memory_assistance_prompt_integration",
      review: { status: "operator_review_ready" },
      receipt: { receipt_id: "tel_fma_live_decision_123", decision: "accepted" },
      receipt_id: "tel_fma_live_decision_123",
      decision: "accepted",
      writes_receipt: true,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { required_scope: "telemetry.context.feedback.write", explicit_operator_decision: true },
      next_smallest_truthful_gap:
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_receipt_readback",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const record = await client.recordContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecision({
      actor: "chat_ui.system",
      reason: "operator accepts live sample",
      decision: "accepted",
      notes: "reviewed",
      limit: 30,
    });

    assert.equal(record.status, "recorded");
    assert.equal(record.receipt_id, "tel_fma_live_decision_123");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision",
        method: "POST",
        body: {
          actor: "chat_ui.system",
          reason: "operator accepts live sample",
          decision: "accepted",
          notes: "reviewed",
          limit: 30,
        },
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionReadback preserves latest receipt readback", () => {
  const readback =
    parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionReadback({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision_receipts",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "decision_receipt_readback_ready",
      target: "feedback_memory_assistance_prompt_integration",
      items: [{ receipt_id: "tel_fma_live_decision_123", decision: "accepted" }],
      count: 1,
      total: 1,
      limit: 20,
      truncated: false,
      latest_receipt: { receipt_id: "tel_fma_live_decision_123", decision: "accepted" },
      latest_receipt_id: "tel_fma_live_decision_123",
      latest_decision: "accepted",
      latest_recorded_ts: 123,
      decision_counts: { accepted: 1, rejected: 0, needs_more_evidence: 0 },
      receipt_readback_ready: true,
      redacted: true,
      reads_receipts: true,
      writes_receipts: false,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, receipt_readback_ready: true },
      next_smallest_truthful_gap:
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_outcome_review",
    });

  assert.equal(readback.status, "decision_receipt_readback_ready");
  assert.equal(readback.count, 1);
  assert.equal(readback.latest_receipt_id, "tel_fma_live_decision_123");
  assert.equal(readback.latest_decision, "accepted");
  assert.equal(readback.decision_counts.accepted, 1);
  assert.equal(readback.receipt_readback_ready, true);
  assert.equal(readback.writes_receipts, false);
  assert.equal(readback.writes_memory, false);
  assert.equal(readback.sends_chat, false);
  assert.equal(readback.grants_execution_authority, false);
});

test("TelemetryClient requests the live sample operator decision receipt readback endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision_receipts",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "decision_receipt_readback_ready",
      target: "feedback_memory_assistance_prompt_integration",
      items: [{ receipt_id: "tel_fma_live_decision_123", decision: "accepted" }],
      count: 1,
      total: 1,
      limit: 30,
      truncated: false,
      latest_receipt: { receipt_id: "tel_fma_live_decision_123", decision: "accepted" },
      latest_receipt_id: "tel_fma_live_decision_123",
      latest_decision: "accepted",
      latest_recorded_ts: 123,
      decision_counts: { accepted: 1, rejected: 0, needs_more_evidence: 0 },
      receipt_readback_ready: true,
      redacted: true,
      reads_receipts: true,
      writes_receipts: false,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, receipt_readback_ready: true },
      next_smallest_truthful_gap:
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_outcome_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const readback = await client.getContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisions({
      limit: 30,
    });

    assert.equal(readback.latest_receipt_id, "tel_fma_live_decision_123");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decisions",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview preserves outcome guards", () => {
  const review = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision_outcome_review",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "outcome_review_ready",
    target: "feedback_memory_assistance_prompt_integration",
    outcome: "operator_accepted_current_live_sample",
    outcome_review_ready: true,
    latest_decision: "accepted",
    latest_receipt_id: "tel_fma_live_decision_123",
    latest_recorded_ts: 123,
    receipt_readback: { latest_receipt_id: "tel_fma_live_decision_123" },
    decision_counts: { accepted: 1, rejected: 0, needs_more_evidence: 0 },
    review: { accepted_current_sample: true, receipt_readback_ready: true },
    reads_receipts: true,
    writes_receipts: false,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, operator_decision_outcome_review: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_terminal_context_signal",
  });

  assert.equal(review.status, "outcome_review_ready");
  assert.equal(review.outcome, "operator_accepted_current_live_sample");
  assert.equal(review.outcome_review_ready, true);
  assert.equal(review.latest_receipt_id, "tel_fma_live_decision_123");
  assert.equal(review.decision_counts.accepted, 1);
  assert.equal(review.writes_receipts, false);
  assert.equal(review.writes_memory, false);
  assert.equal(review.sends_chat, false);
  assert.equal(review.grants_execution_authority, false);
  assert.equal(review.governance.operator_decision_outcome_review, true);
});

test("TelemetryClient requests the live sample operator decision outcome review endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision_outcome_review",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "outcome_review_ready",
      target: "feedback_memory_assistance_prompt_integration",
      outcome: "operator_accepted_current_live_sample",
      outcome_review_ready: true,
      latest_decision: "accepted",
      latest_receipt_id: "tel_fma_live_decision_123",
      latest_recorded_ts: 123,
      receipt_readback: { latest_receipt_id: "tel_fma_live_decision_123" },
      decision_counts: { accepted: 1, rejected: 0, needs_more_evidence: 0 },
      review: { accepted_current_sample: true, receipt_readback_ready: true },
      reads_receipts: true,
      writes_receipts: false,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, operator_decision_outcome_review: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_terminal_context_signal",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const review =
      await client.getContextFeedbackMemoryAssistanceOperatorFeedbackLoopLiveSampleOperatorDecisionOutcomeReview({
        limit: 30,
      });

    assert.equal(review.outcome, "operator_accepted_current_live_sample");
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision-outcome-review",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceTerminalContextSignal preserves terminal guards", () => {
  const signal = parseTelemetryContextFeedbackMemoryAssistanceTerminalContextSignal({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_terminal_context_signal",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "terminal_context_signal_ready",
    target: "feedback_memory_assistance_prompt_integration",
    terminal_context_signal_ready: true,
    accepted_operator_outcome: true,
    outcome_review_ready: true,
    outcome: "operator_accepted_current_live_sample",
    latest_decision: "accepted",
    latest_receipt_id: "tel_fma_live_decision_123",
    terminal_event_count: 1,
    terminal_context_line_count: 1,
    terminal_context_items: [{ source_id: "terminal", event_id: "tel_terminal_123" }],
    terminal_context_lines: ["terminal: latest terminal event tel_terminal_123; exit 0"],
    latest_terminal_event: { event_id: "tel_terminal_123", exit_code: 0 },
    outcome_review: { latest_receipt_id: "tel_fma_live_decision_123" },
    reads_terminal_context: true,
    reads_terminal_events: true,
    reads_receipts: true,
    writes_terminal_events: false,
    writes_receipts: false,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    captures_terminal_streams: false,
    stores_stdout_stderr: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, terminal_context_signal_projection: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_git_context_signal",
  });

  assert.equal(signal.status, "terminal_context_signal_ready");
  assert.equal(signal.terminal_context_signal_ready, true);
  assert.equal(signal.terminal_event_count, 1);
  assert.equal(signal.terminal_context_line_count, 1);
  assert.equal(signal.terminal_context_items[0]?.event_id, "tel_terminal_123");
  assert.equal(signal.terminal_context_lines[0]?.startsWith("terminal:"), true);
  assert.equal(signal.reads_terminal_context, true);
  assert.equal(signal.writes_terminal_events, false);
  assert.equal(signal.writes_memory, false);
  assert.equal(signal.captures_terminal_streams, false);
  assert.equal(signal.stores_stdout_stderr, false);
  assert.equal(signal.grants_execution_authority, false);
  assert.equal(signal.governance.terminal_context_signal_projection, true);
});

test("TelemetryClient requests the terminal context signal endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_terminal_context_signal",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "terminal_context_signal_ready",
      target: "feedback_memory_assistance_prompt_integration",
      terminal_context_signal_ready: true,
      accepted_operator_outcome: true,
      outcome_review_ready: true,
      outcome: "operator_accepted_current_live_sample",
      latest_decision: "accepted",
      latest_receipt_id: "tel_fma_live_decision_123",
      terminal_event_count: 1,
      terminal_context_line_count: 1,
      terminal_context_items: [{ source_id: "terminal", event_id: "tel_terminal_123" }],
      terminal_context_lines: ["terminal: latest terminal event tel_terminal_123; exit 0"],
      latest_terminal_event: { event_id: "tel_terminal_123", exit_code: 0 },
      outcome_review: { latest_receipt_id: "tel_fma_live_decision_123" },
      reads_terminal_context: true,
      reads_terminal_events: true,
      reads_receipts: true,
      writes_terminal_events: false,
      writes_receipts: false,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      captures_terminal_streams: false,
      stores_stdout_stderr: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, terminal_context_signal_projection: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_git_context_signal",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const signal = await client.getContextFeedbackMemoryAssistanceTerminalContextSignal({ limit: 30 });

    assert.equal(signal.terminal_context_signal_ready, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-terminal-context-signal",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceGitContextSignal preserves git guards", () => {
  const signal = parseTelemetryContextFeedbackMemoryAssistanceGitContextSignal({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_git_context_signal",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "git_context_signal_ready",
    target: "feedback_memory_assistance_prompt_integration",
    git_context_signal_ready: true,
    terminal_context_signal_ready: true,
    git_snapshot_ready: true,
    branch: "main",
    head: "abc123",
    upstream: "origin/main",
    dirty: true,
    changed_count: 1,
    changed_paths: [{ status: "M", path: "src/francis/telemetry/git.py" }],
    git_context_line_count: 1,
    git_context_items: [{ source_id: "git", branch: "main" }],
    git_context_lines: ["git: git branch main, changed 1; dirty"],
    git_snapshot: { source_id: "git", status: "snapshot_ready" },
    terminal_context_signal: { terminal_context_signal_ready: true },
    reads_git_context: true,
    reads_git_status: true,
    reads_terminal_context_signal: true,
    writes_git_state: false,
    starts_git_watcher: false,
    runs_git_fetch: false,
    runs_git_pull: false,
    runs_git_push: false,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, git_context_signal_projection: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_ide_context_signal",
  });

  assert.equal(signal.status, "git_context_signal_ready");
  assert.equal(signal.git_context_signal_ready, true);
  assert.equal(signal.git_snapshot_ready, true);
  assert.equal(signal.branch, "main");
  assert.equal(signal.changed_paths[0]?.path, "src/francis/telemetry/git.py");
  assert.equal(signal.git_context_lines[0]?.startsWith("git:"), true);
  assert.equal(signal.reads_git_context, true);
  assert.equal(signal.writes_git_state, false);
  assert.equal(signal.starts_git_watcher, false);
  assert.equal(signal.runs_git_fetch, false);
  assert.equal(signal.runs_git_pull, false);
  assert.equal(signal.runs_git_push, false);
  assert.equal(signal.grants_execution_authority, false);
  assert.equal(signal.governance.git_context_signal_projection, true);
});

test("TelemetryClient requests the git context signal endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_git_context_signal",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "git_context_signal_ready",
      target: "feedback_memory_assistance_prompt_integration",
      git_context_signal_ready: true,
      terminal_context_signal_ready: true,
      git_snapshot_ready: true,
      branch: "main",
      head: "abc123",
      upstream: "origin/main",
      dirty: true,
      changed_count: 1,
      changed_paths: [{ status: "M", path: "src/francis/telemetry/git.py" }],
      git_context_line_count: 1,
      git_context_items: [{ source_id: "git", branch: "main" }],
      git_context_lines: ["git: git branch main, changed 1; dirty"],
      git_snapshot: { source_id: "git", status: "snapshot_ready" },
      terminal_context_signal: { terminal_context_signal_ready: true },
      reads_git_context: true,
      reads_git_status: true,
      reads_terminal_context_signal: true,
      writes_git_state: false,
      starts_git_watcher: false,
      runs_git_fetch: false,
      runs_git_pull: false,
      runs_git_push: false,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, git_context_signal_projection: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_ide_context_signal",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const signal = await client.getContextFeedbackMemoryAssistanceGitContextSignal({ limit: 30 });

    assert.equal(signal.git_context_signal_ready, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-git-context-signal",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceIdeContextSignal preserves IDE guards", () => {
  const signal = parseTelemetryContextFeedbackMemoryAssistanceIdeContextSignal({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_ide_context_signal",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "ide_context_signal_ready",
    target: "feedback_memory_assistance_prompt_integration",
    ide_context_signal_ready: true,
    git_context_signal_ready: true,
    ide_event_ready: true,
    ide_event_count: 1,
    ide_context_line_count: 1,
    ide_context_items: [{ source_id: "ide_diagnostics", event_id: "tel_ide_123" }],
    ide_context_lines: ["ide_diagnostics: IDE diagnostics warning, count 1"],
    latest_ide_diagnostic: { event_id: "tel_ide_123", highest_severity: "warning" },
    git_context_signal: { git_context_signal_ready: true },
    reads_ide_context: true,
    reads_ide_diagnostics: true,
    reads_git_context_signal: true,
    writes_ide_diagnostics: false,
    captures_file_contents: false,
    stores_file_contents: false,
    starts_ide_integration: false,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, ide_context_signal_projection: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_sensing_indicator_summary",
  });

  assert.equal(signal.status, "ide_context_signal_ready");
  assert.equal(signal.ide_context_signal_ready, true);
  assert.equal(signal.ide_event_count, 1);
  assert.equal(signal.latest_ide_diagnostic.event_id, "tel_ide_123");
  assert.equal(signal.ide_context_lines[0]?.startsWith("ide_diagnostics:"), true);
  assert.equal(signal.reads_ide_context, true);
  assert.equal(signal.writes_ide_diagnostics, false);
  assert.equal(signal.captures_file_contents, false);
  assert.equal(signal.stores_file_contents, false);
  assert.equal(signal.starts_ide_integration, false);
  assert.equal(signal.grants_execution_authority, false);
  assert.equal(signal.governance.ide_context_signal_projection, true);
});

test("TelemetryClient requests the IDE context signal endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_ide_context_signal",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "ide_context_signal_ready",
      target: "feedback_memory_assistance_prompt_integration",
      ide_context_signal_ready: true,
      git_context_signal_ready: true,
      ide_event_ready: true,
      ide_event_count: 1,
      ide_context_line_count: 1,
      ide_context_items: [{ source_id: "ide_diagnostics", event_id: "tel_ide_123" }],
      ide_context_lines: ["ide_diagnostics: IDE diagnostics warning, count 1"],
      latest_ide_diagnostic: { event_id: "tel_ide_123", highest_severity: "warning" },
      git_context_signal: { git_context_signal_ready: true },
      reads_ide_context: true,
      reads_ide_diagnostics: true,
      reads_git_context_signal: true,
      writes_ide_diagnostics: false,
      captures_file_contents: false,
      stores_file_contents: false,
      starts_ide_integration: false,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, ide_context_signal_projection: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_sensing_indicator_summary",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const signal = await client.getContextFeedbackMemoryAssistanceIdeContextSignal({ limit: 30 });

    assert.equal(signal.ide_context_signal_ready, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-ide-context-signal",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceSensingIndicatorSummary preserves sensing guards", () => {
  const summary = parseTelemetryContextFeedbackMemoryAssistanceSensingIndicatorSummary({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_sensing_indicator_summary",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "sensing_indicators_ready",
    target: "feedback_memory_assistance_visible_sensing",
    sensing_indicator_summary_ready: true,
    visible_sensing_indicators_ready: true,
    indicator_count: 3,
    ready_indicator_count: 3,
    visible_indicator_count: 3,
    indicators: [
      { id: "terminal_context", ready: true, visible: true },
      { id: "git_context", ready: true, visible: true },
      { id: "ide_context", ready: true, visible: true },
    ],
    ide_context_signal: { ide_context_signal_ready: true },
    reads_terminal_context_signal: true,
    reads_git_context_signal: true,
    reads_ide_context_signal: true,
    hidden_sensing: false,
    captures_background_activity: false,
    captures_terminal_streams: false,
    captures_file_contents: false,
    starts_terminal_capture: false,
    starts_git_watcher: false,
    starts_ide_integration: false,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, visible_sensing_indicator_projection: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_context_surface_review",
  });

  assert.equal(summary.status, "sensing_indicators_ready");
  assert.equal(summary.sensing_indicator_summary_ready, true);
  assert.equal(summary.indicator_count, 3);
  assert.equal(summary.indicators.length, 3);
  assert.equal(summary.hidden_sensing, false);
  assert.equal(summary.captures_background_activity, false);
  assert.equal(summary.starts_git_watcher, false);
  assert.equal(summary.starts_ide_integration, false);
  assert.equal(summary.writes_memory, false);
  assert.equal(summary.grants_execution_authority, false);
  assert.equal(summary.governance.visible_sensing_indicator_projection, true);
});

test("TelemetryClient requests the sensing indicator summary endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_sensing_indicator_summary",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "sensing_indicators_ready",
      target: "feedback_memory_assistance_visible_sensing",
      sensing_indicator_summary_ready: true,
      visible_sensing_indicators_ready: true,
      indicator_count: 3,
      ready_indicator_count: 3,
      visible_indicator_count: 3,
      indicators: [
        { id: "terminal_context", ready: true, visible: true },
        { id: "git_context", ready: true, visible: true },
        { id: "ide_context", ready: true, visible: true },
      ],
      ide_context_signal: { ide_context_signal_ready: true },
      reads_terminal_context_signal: true,
      reads_git_context_signal: true,
      reads_ide_context_signal: true,
      hidden_sensing: false,
      captures_background_activity: false,
      captures_terminal_streams: false,
      captures_file_contents: false,
      starts_terminal_capture: false,
      starts_git_watcher: false,
      starts_ide_integration: false,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, visible_sensing_indicator_projection: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_context_surface_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const summary = await client.getContextFeedbackMemoryAssistanceSensingIndicatorSummary({ limit: 30 });

    assert.equal(summary.sensing_indicator_summary_ready, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-sensing-indicator-summary",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorContextSurfaceReview preserves visible surface guards", () => {
  const review = parseTelemetryContextFeedbackMemoryAssistanceOperatorContextSurfaceReview({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_context_surface_review",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "operator_context_surface_ready",
    target: "feedback_memory_assistance_operator_surface",
    operator_context_surface_ready: true,
    sensing_indicator_summary_ready: true,
    surface_id: "telemetry_continuation_panel",
    surface_label: "Telemetry & Continuation",
    surface_source: "apps/chat_ui/src/App.tsx",
    visible_section_count: 5,
    surface_section_count: 5,
    visible_sections: [{ id: "sensing_indicator_summary_card", visible: true }],
    indicator_ids: ["terminal_context", "git_context", "ide_context"],
    sensing_indicator_summary: { sensing_indicator_summary_ready: true },
    read_only: true,
    hidden_sensing: false,
    writes_memory: false,
    writes_feedback: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, operator_surface_review: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_action_quality_signal_review",
  });

  assert.equal(review.status, "operator_context_surface_ready");
  assert.equal(review.operator_context_surface_ready, true);
  assert.equal(review.surface_id, "telemetry_continuation_panel");
  assert.deepEqual(review.indicator_ids, ["terminal_context", "git_context", "ide_context"]);
  assert.equal(review.visible_section_count, 5);
  assert.equal(review.hidden_sensing, false);
  assert.equal(review.writes_memory, false);
  assert.equal(review.calls_model, false);
  assert.equal(review.grants_execution_authority, false);
  assert.equal(review.governance.operator_surface_review, true);
});

test("TelemetryClient requests the operator context surface review endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_context_surface_review",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "operator_context_surface_ready",
      target: "feedback_memory_assistance_operator_surface",
      operator_context_surface_ready: true,
      sensing_indicator_summary_ready: true,
      surface_id: "telemetry_continuation_panel",
      surface_label: "Telemetry & Continuation",
      surface_source: "apps/chat_ui/src/App.tsx",
      visible_section_count: 5,
      surface_section_count: 5,
      visible_sections: [{ id: "sensing_indicator_summary_card", visible: true }],
      indicator_ids: ["terminal_context", "git_context", "ide_context"],
      sensing_indicator_summary: { sensing_indicator_summary_ready: true },
      read_only: true,
      hidden_sensing: false,
      writes_memory: false,
      writes_feedback: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, operator_surface_review: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_action_quality_signal_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const review = await client.getContextFeedbackMemoryAssistanceOperatorContextSurfaceReview({ limit: 30 });

    assert.equal(review.operator_context_surface_ready, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-operator-context-surface-review",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceActionQualitySignalReview preserves explicit signal guards", () => {
  const review = parseTelemetryContextFeedbackMemoryAssistanceActionQualitySignalReview({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_action_quality_signal_review",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "action_quality_signals_ready",
    target: "feedback_memory_assistance_prompt_integration",
    action_quality_signal_review_ready: true,
    ready_signal_count: 4,
    signal_count: 4,
    action_quality_signals: [
      { id: "visible_operator_context_surface", ready: true },
      { id: "accepted_live_sample_operator_decision", ready: true },
      { id: "explicit_operator_feedback_quality_signal", ready: true },
      { id: "governed_memory_quality_signal_readback", ready: true },
    ],
    quality_signals: ["operator_reported_useful_feedback_memory_assistance"],
    reviewed_event_count: 2,
    memory_quality_event_count: 1,
    latest_memory_quality_event_id: "evt-feedback-memory-assistance-live-sample",
    rating_counts: { useful: 2, not_useful: 0, neutral: 0 },
    operator_surface_ready: true,
    accepted_live_sample: true,
    operator_surface_review: { operator_context_surface_ready: true },
    feedback_review: { reviewed_event_count: 2 },
    memory_readback: { count: 1 },
    outcome_review: { outcome: "operator_accepted_current_live_sample" },
    capture_mode: "explicit_operator_feedback_and_receipt_readback",
    read_only: true,
    model_scored_quality: false,
    writes_memory: false,
    writes_feedback: false,
    mutates_prompt: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, action_quality_signal_review: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_primary_loop_evidence_review",
  });

  assert.equal(review.status, "action_quality_signals_ready");
  assert.equal(review.action_quality_signal_review_ready, true);
  assert.equal(review.ready_signal_count, 4);
  assert.equal(review.action_quality_signals.length, 4);
  assert.deepEqual(review.quality_signals, ["operator_reported_useful_feedback_memory_assistance"]);
  assert.equal(review.latest_memory_quality_event_id, "evt-feedback-memory-assistance-live-sample");
  assert.equal(review.operator_surface_ready, true);
  assert.equal(review.accepted_live_sample, true);
  assert.equal(review.model_scored_quality, false);
  assert.equal(review.writes_memory, false);
  assert.equal(review.mutates_prompt, false);
  assert.equal(review.calls_model, false);
  assert.equal(review.grants_execution_authority, false);
  assert.equal(review.governance.action_quality_signal_review, true);
});

test("TelemetryClient requests the action quality signal review endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_action_quality_signal_review",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "action_quality_signals_ready",
      target: "feedback_memory_assistance_prompt_integration",
      action_quality_signal_review_ready: true,
      ready_signal_count: 4,
      signal_count: 4,
      action_quality_signals: [
        { id: "visible_operator_context_surface", ready: true },
        { id: "accepted_live_sample_operator_decision", ready: true },
        { id: "explicit_operator_feedback_quality_signal", ready: true },
        { id: "governed_memory_quality_signal_readback", ready: true },
      ],
      quality_signals: ["operator_reported_useful_feedback_memory_assistance"],
      reviewed_event_count: 2,
      memory_quality_event_count: 1,
      latest_memory_quality_event_id: "evt-feedback-memory-assistance-live-sample",
      rating_counts: { useful: 2, not_useful: 0, neutral: 0 },
      operator_surface_ready: true,
      accepted_live_sample: true,
      operator_surface_review: { operator_context_surface_ready: true },
      feedback_review: { reviewed_event_count: 2 },
      memory_readback: { count: 1 },
      outcome_review: { outcome: "operator_accepted_current_live_sample" },
      capture_mode: "explicit_operator_feedback_and_receipt_readback",
      read_only: true,
      model_scored_quality: false,
      writes_memory: false,
      writes_feedback: false,
      mutates_prompt: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, action_quality_signal_review: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_primary_loop_evidence_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const review = await client.getContextFeedbackMemoryAssistanceActionQualitySignalReview({ limit: 30 });

    assert.equal(review.action_quality_signal_review_ready, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-action-quality-signal-review",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistancePrimaryLoopEvidenceReview preserves primary loop guards", () => {
  const review = parseTelemetryContextFeedbackMemoryAssistancePrimaryLoopEvidenceReview({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_primary_loop_evidence_review",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "primary_loop_evidence_ready",
    target: "feedback_memory_assistance_prompt_integration",
    primary_loop_evidence_ready: true,
    ready_count: 8,
    required_count: 8,
    primary_loop_evidence: [
      { id: "interface", ready: true },
      { id: "plan", ready: true },
      { id: "governance", ready: true },
      { id: "identity", ready: true },
      { id: "execution", ready: true },
      { id: "receipt_trace", ready: true },
      { id: "memory", ready: true },
      { id: "ui_return", ready: true },
    ],
    receipt_trace_kind: "receipt_backed_readback",
    true_execution_trace_observed: false,
    operator_decision_receipt_id: "opdec-feedback-memory-assistance-live-sample",
    memory_quality_event_id: "evt-feedback-memory-assistance-live-sample",
    action_quality_review: { action_quality_signal_review_ready: true },
    live_sample_readback: { live_sample_observed: true },
    operator_review: { operator_review_ready: true },
    outcome_review: { outcome: "operator_accepted_current_live_sample" },
    read_only: true,
    writes_memory: false,
    writes_feedback: false,
    mutates_prompt: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: {
      read_only: true,
      primary_loop_evidence_review: true,
      receipt_trace_not_true_execution_trace: true,
    },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_memory_poisoning_review",
  });

  assert.equal(review.status, "primary_loop_evidence_ready");
  assert.equal(review.primary_loop_evidence_ready, true);
  assert.equal(review.ready_count, 8);
  assert.equal(review.required_count, 8);
  assert.deepEqual(
    review.primary_loop_evidence.map((item) => item.id),
    ["interface", "plan", "governance", "identity", "execution", "receipt_trace", "memory", "ui_return"],
  );
  assert.equal(review.receipt_trace_kind, "receipt_backed_readback");
  assert.equal(review.true_execution_trace_observed, false);
  assert.equal(review.operator_decision_receipt_id, "opdec-feedback-memory-assistance-live-sample");
  assert.equal(review.memory_quality_event_id, "evt-feedback-memory-assistance-live-sample");
  assert.equal(review.read_only, true);
  assert.equal(review.writes_memory, false);
  assert.equal(review.writes_feedback, false);
  assert.equal(review.calls_model, false);
  assert.equal(review.grants_execution_authority, false);
  assert.equal(review.governance.receipt_trace_not_true_execution_trace, true);
});

test("TelemetryClient requests the primary loop evidence review endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_primary_loop_evidence_review",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "primary_loop_evidence_ready",
      target: "feedback_memory_assistance_prompt_integration",
      primary_loop_evidence_ready: true,
      ready_count: 8,
      required_count: 8,
      primary_loop_evidence: [
        { id: "interface", ready: true },
        { id: "plan", ready: true },
        { id: "governance", ready: true },
        { id: "identity", ready: true },
        { id: "execution", ready: true },
        { id: "receipt_trace", ready: true },
        { id: "memory", ready: true },
        { id: "ui_return", ready: true },
      ],
      receipt_trace_kind: "receipt_backed_readback",
      true_execution_trace_observed: false,
      operator_decision_receipt_id: "opdec-feedback-memory-assistance-live-sample",
      memory_quality_event_id: "evt-feedback-memory-assistance-live-sample",
      action_quality_review: { action_quality_signal_review_ready: true },
      live_sample_readback: { live_sample_observed: true },
      operator_review: { operator_review_ready: true },
      outcome_review: { outcome: "operator_accepted_current_live_sample" },
      read_only: true,
      writes_memory: false,
      writes_feedback: false,
      mutates_prompt: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, primary_loop_evidence_review: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_memory_poisoning_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const review = await client.getContextFeedbackMemoryAssistancePrimaryLoopEvidenceReview({ limit: 30 });

    assert.equal(review.primary_loop_evidence_ready, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-primary-loop-evidence-review",
        search: "?limit=30",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});

test("parseTelemetryContextFeedbackMemoryAssistanceMemoryPoisoningReview preserves poisoning guards", () => {
  const review = parseTelemetryContextFeedbackMemoryAssistanceMemoryPoisoningReview({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_memory_poisoning_review",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "memory_poisoning_review_ready",
    target: "feedback_memory_assistance_prompt_integration",
    memory_poisoning_review_ready: true,
    ready_count: 5,
    required_count: 5,
    poisoning_controls: [
      { id: "memory_timeline_write_contract", ready: true },
      { id: "poison_pattern_detection", ready: true },
      { id: "untrusted_payload_influence_blocked", ready: true },
      { id: "existing_memory_readback_clean", ready: true },
      { id: "primary_loop_receipt_trace_bounded", ready: true },
    ],
    poison_pattern_samples: [
      { id: "ignore_previous_instructions", detected_pattern: "ignore previous instructions" },
      { id: "system_prompt_override", detected_pattern: "system prompt override" },
    ],
    detected_poisoned_memory_items: [],
    detected_poisoned_memory_item_count: 0,
    primary_loop_evidence: { primary_loop_evidence_ready: true },
    memory_readback: { count: 1 },
    read_only: true,
    executes_poison_probe: false,
    writes_memory: false,
    writes_feedback: false,
    mutates_prompt: false,
    sends_chat: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: { read_only: true, memory_poisoning_review: true },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_true_execution_trace_review",
  });

  assert.equal(review.status, "memory_poisoning_review_ready");
  assert.equal(review.memory_poisoning_review_ready, true);
  assert.equal(review.ready_count, 5);
  assert.equal(review.required_count, 5);
  assert.deepEqual(
    review.poisoning_controls.map((item) => item.id),
    [
      "memory_timeline_write_contract",
      "poison_pattern_detection",
      "untrusted_payload_influence_blocked",
      "existing_memory_readback_clean",
      "primary_loop_receipt_trace_bounded",
    ],
  );
  assert.equal(review.poison_pattern_samples.length, 2);
  assert.equal(review.detected_poisoned_memory_item_count, 0);
  assert.equal(review.executes_poison_probe, false);
  assert.equal(review.writes_memory, false);
  assert.equal(review.calls_model, false);
  assert.equal(review.grants_execution_authority, false);
  assert.equal(review.governance.memory_poisoning_review, true);
});

test("TelemetryClient requests the memory poisoning review endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_memory_poisoning_review",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "memory_poisoning_review_ready",
      target: "feedback_memory_assistance_prompt_integration",
      memory_poisoning_review_ready: true,
      ready_count: 5,
      required_count: 5,
      poisoning_controls: [
        { id: "memory_timeline_write_contract", ready: true },
        { id: "poison_pattern_detection", ready: true },
        { id: "untrusted_payload_influence_blocked", ready: true },
        { id: "existing_memory_readback_clean", ready: true },
        { id: "primary_loop_receipt_trace_bounded", ready: true },
      ],
      poison_pattern_samples: [
        { id: "ignore_previous_instructions", detected_pattern: "ignore previous instructions" },
        { id: "system_prompt_override", detected_pattern: "system prompt override" },
      ],
      detected_poisoned_memory_items: [],
      detected_poisoned_memory_item_count: 0,
      primary_loop_evidence: { primary_loop_evidence_ready: true },
      memory_readback: { count: 1 },
      read_only: true,
      executes_poison_probe: false,
      writes_memory: false,
      writes_feedback: false,
      mutates_prompt: false,
      sends_chat: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true, memory_poisoning_review: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_true_execution_trace_review",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const review = await client.getContextFeedbackMemoryAssistanceMemoryPoisoningReview({ limit: 30 });

    assert.equal(review.memory_poisoning_review_ready, true);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-loop-memory-poisoning-review",
        search: "?limit=30",
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
    operator_feedback_memory_readback_route: "/telemetry/context/feedback/memory-assistance-feedback-memory-readback",
    memory_policy_route: "/telemetry/context/feedback/memory-retrieval-policy",
    allowed_memory_event_kinds: [
      "telemetry_context_feedback_quality_review",
      "telemetry_context_feedback_memory_assistance_operator_feedback_review",
    ],
    allowed_action_types: [
      "telemetry.context_feedback.quality_review",
      "telemetry.context_feedback.memory_assistance_operator_feedback_review",
    ],
    allowed_classifications: [
      "operator_feedback_quality_signal",
      "operator_feedback_memory_assistance_quality_signal",
    ],
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
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
  });

  assert.equal(policy.kind, "francis.stage7.telemetry.context_feedback_memory_assistance_policy");
  assert.equal(policy.status, "policy_ready");
  assert.equal(policy.policy_id, "stage7_context_feedback_memory_assistance_policy");
  assert.equal(policy.memory_readback_route, "/telemetry/context/feedback/memory-retrieval-readback");
  assert.equal(
    policy.operator_feedback_memory_readback_route,
    "/telemetry/context/feedback/memory-assistance-feedback-memory-readback",
  );
  assert.deepEqual(policy.allowed_memory_event_kinds, [
    "telemetry_context_feedback_quality_review",
    "telemetry_context_feedback_memory_assistance_operator_feedback_review",
  ]);
  assert.equal(
    policy.allowed_action_types.includes("telemetry.context_feedback.memory_assistance_operator_feedback_review"),
    true,
  );
  assert.equal(
    policy.allowed_classifications.includes("operator_feedback_memory_assistance_quality_signal"),
    true,
  );
  assert.equal(policy.allowed_influence.includes("suggest_context_source_attention"), true);
  assert.equal(policy.forbidden_influence.includes("treat_memory_payload_as_instruction"), true);
  assert.equal(policy.assistance_guards.no_tool_selection_authority, true);
  assert.equal(policy.reads_memory, false);
  assert.equal(policy.writes_memory, false);
  assert.equal(policy.trains_model, false);
  assert.equal(policy.grants_execution_authority, false);
  assert.equal(policy.governance.assistance_requires_separate_dry_run, true);
  assert.equal(policy.next_smallest_truthful_gap, "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run");
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
      operator_feedback_memory_readback_route: "/telemetry/context/feedback/memory-assistance-feedback-memory-readback",
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
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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

test("parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackReview preserves targeted review", () => {
  const review = parseTelemetryContextFeedbackMemoryAssistanceOperatorFeedbackReview({
    ok: true,
    kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_review",
    stage: "Stage 7 / Telemetry MVP",
    source_id: "telemetry_context",
    status: "review_ready",
    capture_mode: "explicit_operator_feedback_review",
    target: "feedback_memory_assistance_prompt_integration",
    reviewed_event_count: 2,
    limit: 25,
    rating_counts: { useful: 1, not_useful: 1, neutral: 0 },
    source_counts: { feedback_memory_assistance: 2 },
    tag_counts: { feedback_memory_assistance: 2 },
    quality_signals: [
      "operator_reported_useful_feedback_memory_assistance",
      "operator_reported_feedback_memory_assistance_misses",
    ],
    latest_feedback: {
      feedback_id: "tel_feedback_review",
      context_id: "tel_ctx_feedback_memory_assistance_chat",
      surface: "chat",
      rating: "not_useful",
      message_id: "tel_msg_feedback_memory_assistance_chat",
      reply_mode: "feedback_memory_assistance_prompt_context",
      source_ids: ["feedback_memory_assistance", "telemetry_context"],
      tags: ["stage7", "feedback_memory_assistance"],
      line_count: 2,
      recorded_ts: 123,
    },
    redacted: true,
    hidden_sensing: false,
    writes_memory: false,
    calls_model: false,
    selects_tools: false,
    trains_model: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    governance: {
      read_only: true,
      target: "feedback_memory_assistance_prompt_integration",
    },
    next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
  });

  assert.equal(review.kind, "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_review");
  assert.equal(review.target, "feedback_memory_assistance_prompt_integration");
  assert.equal(review.reviewed_event_count, 2);
  assert.equal(review.rating_counts.useful, 1);
  assert.equal(review.latest_feedback?.reply_mode, "feedback_memory_assistance_prompt_context");
  assert.equal(review.latest_feedback?.line_count, 2);
  assert.equal(review.writes_memory, false);
  assert.equal(review.calls_model, false);
  assert.equal(review.grants_execution_authority, false);
});

test("TelemetryClient requests feedback-memory assistance operator review endpoint", async () => {
  const requests: Array<{ path: string; search: string; method: string }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({ path: parsed.pathname, search: parsed.search, method: init?.method ?? "GET" });
    return jsonResponse({
      ok: true,
      kind: "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_review",
      stage: "Stage 7 / Telemetry MVP",
      source_id: "telemetry_context",
      status: "empty",
      capture_mode: "explicit_operator_feedback_review",
      target: "feedback_memory_assistance_prompt_integration",
      reviewed_event_count: 0,
      limit: 9,
      rating_counts: { useful: 0, not_useful: 0, neutral: 0 },
      source_counts: {},
      tag_counts: {},
      quality_signals: ["no_feedback_memory_assistance_operator_feedback_recorded"],
      latest_feedback: {},
      redacted: true,
      hidden_sensing: false,
      writes_memory: false,
      calls_model: false,
      selects_tools: false,
      trains_model: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: { read_only: true },
      next_smallest_truthful_gap: "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    });
  });

  try {
    const client = new TelemetryClient("http://127.0.0.1:8000/");
    const review = await client.getContextFeedbackMemoryAssistanceOperatorFeedbackReview({ limit: 9 });
    assert.equal(review.status, "empty");
    assert.equal(review.reviewed_event_count, 0);
    assert.deepEqual(requests, [
      {
        path: "/telemetry/context/feedback/memory-assistance-feedback-review",
        search: "?limit=9",
        method: "GET",
      },
    ]);
  } finally {
    restore();
  }
});
