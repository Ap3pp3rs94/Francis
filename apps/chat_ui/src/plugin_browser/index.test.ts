import assert from "node:assert/strict";
import test from "node:test";

import {
  PluginBrowserApiError,
  PluginBrowserClient,
  operatorEvidenceBatchToImportPreviewText,
  operatorEvidenceExportRowsToImportPreviewText,
  summarizeOperatorEvidenceIntakeResponseGuards,
  summarizeOperatorEvidenceImportPreviewGuards,
  summarizeOperatorEvidenceImportRowsText,
  summarizeOperatorEvidenceRefsText,
} from "./index.ts";

type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function installFetch(handler: FetchHandler): () => void {
  const globals = globalThis as typeof globalThis & {
    fetch?: typeof fetch;
    window?: { setTimeout: typeof setTimeout; clearTimeout: typeof clearTimeout };
  };
  const originalFetch = globals.fetch;
  const originalWindow = globals.window;

  globals.window = {
    setTimeout,
    clearTimeout,
  };
  globals.fetch = (async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = input instanceof Request ? input.url : input.toString();
    return await handler(url, init);
  }) as typeof fetch;

  return () => {
    if (originalFetch) {
      globals.fetch = originalFetch;
    } else {
      delete globals.fetch;
    }
    if (originalWindow) {
      globals.window = originalWindow;
    } else {
      delete globals.window;
    }
  };
}

test("operatorEvidenceExportRowsToImportPreviewText preserves blank evidence slots", () => {
  const text = operatorEvidenceExportRowsToImportPreviewText([
    {
      pack_id: "legacy.generated.ops",
      pack_version: "1.0.0",
      pack_name: "Generated Ops",
      capability: "generated.ops.run",
      proposal_id: "plugin_proposal_generated_ops_run",
      evidence_refs_input: "",
      evidence_refs_input_format: "comma_separated_or_json_array",
      operator_evidence_refs_required: true,
    },
    {
      pack_id: "legacy.generated.ops",
      pack_version: "1.0.0",
      capability: "",
      proposal_id: "ignored",
      evidence_refs_input: "mission.ignored",
    },
  ]);

  assert.deepEqual(JSON.parse(text), [
    {
      pack_id: "legacy.generated.ops",
      pack_version: "1.0.0",
      capability: "generated.ops.run",
      proposal_id: "plugin_proposal_generated_ops_run",
      evidence_refs_input: "",
    },
  ]);
});

test("operatorEvidenceExportRowsToImportPreviewText fills explicit operator refs", () => {
  const text = operatorEvidenceExportRowsToImportPreviewText(
    [
      {
        pack_id: "legacy.generated.ops",
        pack_version: "1.0.0",
        capability: "generated.ops.run",
        proposal_id: "plugin_proposal_generated_ops_run",
        evidence_refs_input: "",
      },
    ],
    ["mission.operator.ref", "", "mission.operator.ref.2"],
  );

  assert.deepEqual(JSON.parse(text), [
    {
      pack_id: "legacy.generated.ops",
      pack_version: "1.0.0",
      capability: "generated.ops.run",
      proposal_id: "plugin_proposal_generated_ops_run",
      evidence_refs_input: JSON.stringify(["mission.operator.ref", "mission.operator.ref.2"]),
    },
  ]);
});

test("operatorEvidenceBatchToImportPreviewText converts next batch capabilities without refs", () => {
  const text = operatorEvidenceBatchToImportPreviewText({
    status: "ready_for_operator_evidence_batch",
    pack_id: "legacy.generated.ops",
    pack_version: "1.0.0",
    capabilities: [
      {
        capability: "generated.ops.run",
        proposal_id: "plugin_proposal_generated_ops_run",
      },
      {
        capability: "",
        proposal_id: "ignored",
      },
    ],
  });

  assert.deepEqual(JSON.parse(text), [
    {
      pack_id: "legacy.generated.ops",
      pack_version: "1.0.0",
      capability: "generated.ops.run",
      proposal_id: "plugin_proposal_generated_ops_run",
      evidence_refs_input: "",
    },
  ]);
});

test("operatorEvidenceBatchToImportPreviewText can fill typed refs from payload hint scope", () => {
  const text = operatorEvidenceBatchToImportPreviewText(
    {
      status: "ready_for_operator_evidence_batch",
      apply_payload_hint: {
        pack_ids: ["legacy.generated.ops"],
        capability_ids: ["generated.ops.run"],
      },
    },
    ["mission.operator.ref", "", "mission.operator.ref.2"],
  );

  assert.deepEqual(JSON.parse(text), [
    {
      pack_id: "legacy.generated.ops",
      pack_version: "",
      capability: "generated.ops.run",
      proposal_id: "",
      evidence_refs_input: JSON.stringify(["mission.operator.ref", "mission.operator.ref.2"]),
    },
  ]);
});

test("summarizeOperatorEvidenceRefsText reports local typed-ref readiness", () => {
  assert.deepEqual(summarizeOperatorEvidenceRefsText(""), {
    raw_ref_count: 0,
    unique_ref_count: 0,
    duplicate_ref_count: 0,
    blank_entry_count: 0,
    ready_for_row_fill: false,
  });

  assert.deepEqual(summarizeOperatorEvidenceRefsText(" mission.one, mission.two\nmission.one,, "), {
    raw_ref_count: 3,
    unique_ref_count: 2,
    duplicate_ref_count: 1,
    blank_entry_count: 2,
    ready_for_row_fill: true,
  });
});

test("summarizeOperatorEvidenceImportRowsText reports local import readiness", () => {
  const summary = summarizeOperatorEvidenceImportRowsText(
    JSON.stringify([
      {
        pack_id: "legacy.generated.ops",
        capability: "generated.ops.run",
        evidence_refs_input: JSON.stringify(["mission.operator.ref"]),
      },
      {
        pack_id: "legacy.generated.ops",
        capability: "generated.ops.plan",
        evidence_refs_input: "",
      },
      {
        pack_id: "legacy.generated.ops",
        capability: "",
        evidence_refs_input: "mission.invalid",
      },
    ]),
  );

  assert.deepEqual(summary, {
    row_count: 3,
    filled_row_count: 1,
    pending_row_count: 1,
    invalid_row_count: 1,
    ready_for_import_preview: true,
  });
});

test("summarizeOperatorEvidenceImportRowsText keeps blank and malformed rows unready", () => {
  assert.deepEqual(summarizeOperatorEvidenceImportRowsText(""), {
    row_count: 0,
    filled_row_count: 0,
    pending_row_count: 0,
    invalid_row_count: 0,
    ready_for_import_preview: false,
  });

  const malformed = summarizeOperatorEvidenceImportRowsText("{");
  assert.equal(malformed.ready_for_import_preview, false);
  assert.equal(malformed.invalid_row_count, 1);
  assert.ok(malformed.parse_error);
});

test("summarizeOperatorEvidenceImportPreviewGuards preserves backend preview guards", () => {
  assert.deepEqual(
    summarizeOperatorEvidenceImportPreviewGuards({
      ok: true,
      requirements: {
        no_synthetic_evidence: true,
        does_not_validate_evidence_truth: true,
      },
      governance: {
        read_only: true,
        preview_only: true,
        write_authority: false,
        writes_registry_metadata: false,
        writes_operator_evidence_metadata: false,
        memory_write: false,
      },
    }),
    {
      read_only: "true",
      preview_only: "true",
      write_authority: "false",
      writes_registry_metadata: "false",
      writes_operator_evidence_metadata: "false",
      does_not_validate_evidence_truth: "true",
      no_synthetic_evidence: "true",
      memory_write: "false",
    },
  );

  assert.equal(summarizeOperatorEvidenceImportPreviewGuards(null).read_only, "unknown");
});

test("summarizeOperatorEvidenceIntakeResponseGuards preserves backend intake authority flags", () => {
  assert.deepEqual(
    summarizeOperatorEvidenceIntakeResponseGuards({
      ok: true,
      applied: false,
      status: "dry_run",
      dry_run: true,
      dry_run_fingerprint: "abc123dryrunfingerprint",
      dry_run_confirmation: {
        required_for_apply: true,
      },
      governance: {
        writes_registry_metadata: false,
        writes_proposals: false,
        dry_run_required_before_apply: true,
        operator_supplied_evidence_not_independently_verified: true,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      planned: [],
      recorded: [],
      failed: [],
      skipped: [],
    }),
    {
      status: "dry_run",
      dry_run: "true",
      applied: "false",
      dry_run_required_for_apply: "true",
      dry_run_required_before_apply: "true",
      dry_run_fingerprint_present: "true",
      writes_registry_metadata: "false",
      writes_proposals: "false",
      does_not_approve_proposals: "true",
      does_not_promote_capabilities: "true",
      operator_supplied_evidence_not_independently_verified: "true",
      memory_write: "false",
    },
  );

  const unknown = summarizeOperatorEvidenceIntakeResponseGuards({ ok: false });
  assert.equal(unknown.dry_run_required_for_apply, "unknown");
  assert.equal(unknown.dry_run_fingerprint_present, "false");
  assert.equal(unknown.does_not_approve_proposals, "unknown");
});

test("PluginBrowserClient lifecycle mutations send an explicit plugin actor", async () => {
  const captured: Record<string, Record<string, unknown>> = {};
  const restoreFetch = installFetch(async (url, init) => {
    captured[new URL(url).pathname] = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({ ok: true, id: "pl_echo", plugin_id: "pl_echo", enabled: true, status: "enabled" });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    await client.enable({ id: "pl_echo" });
    await client.disable({ id: "pl_echo" });
    await client.install({ source_kind: "registry", source_ref: "acme/echo" });
    await client.uninstall({ id: "pl_echo" });
    await client.decideForgeProposal({ id: "proposal_pl_echo", action: "approve" });
    await client.decideCapabilityPackOperatorReview({
      pack_id: "ops.echo",
      pack_version: "1.0.0",
      action: "approve",
    });
    await client.reload();

    assert.equal(captured["/plugins/enable"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/disable"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/install"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/uninstall"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/forge/proposals/decision"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/capabilities/packs/operator/review/decisions"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/reload"]?.actor, "chat_ui.plugins");
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient preserves Forge promotion receipts from enable responses", async () => {
  const captured: Record<string, unknown>[] = [];
  const restoreFetch = installFetch(async (_url, init) => {
    captured.push(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>);
    return jsonResponse({
      ok: true,
      id: "pl_stage",
      enabled: true,
      status: "enabled",
      promotion_status: "promoted",
      promotion_receipt_id: "promotion_pl_stage_1710000000",
      promotion_receipt: {
        kind: "plugin.promotion.receipt",
        receipt_id: "promotion_pl_stage_1710000000",
        plugin_id: "pl_stage",
        proposal_id: "proposal_pl_stage_1",
        previous_status: "staged",
        promoted_status: "enabled",
        promoted_ts: 1710000000,
        proposal_review: {
          status: "approved",
          receipt_id: "review_1",
        },
        quality: {
          risk_tier: "normal",
          tests: ["tests/test_api_plugins.py::test_plugins_build_lifecycle_and_run"],
        },
        governance: {
          gate: "permission_gate",
          explicit: true,
        },
        path: "D:/Francis/data/artifacts/plugins/promotions/promotion_pl_stage_1710000000.json",
      },
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const res = await client.enable({ id: "pl_stage", reason: "operator promotion" });

    assert.equal(captured[0]?.actor, "chat_ui.plugins");
    assert.equal(res.promotion_status, "promoted");
    assert.equal(res.promotion_receipt_id, "promotion_pl_stage_1710000000");
    assert.equal(res.promotion_receipt?.receipt_id, "promotion_pl_stage_1710000000");
    assert.equal(res.promotion_receipt?.plugin_id, "pl_stage");
    assert.equal(res.promotion_receipt?.proposal_id, "proposal_pl_stage_1");
    assert.equal(res.promotion_receipt?.proposal_review?.receipt_id, "review_1");
    assert.equal(res.promotion_receipt?.quality?.risk_tier, "normal");
    assert.equal(res.promotion_receipt?.governance?.explicit, true);
    assert.equal(
      res.promotion_receipt?.path,
      "D:/Francis/data/artifacts/plugins/promotions/promotion_pl_stage_1710000000.json",
    );
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient treats backend permission denials as mutation errors", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({ ok: false, status: "denied", error: "api_permission_denied" }),
  );

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    await assert.rejects(
      () => client.install({ source_kind: "registry", source_ref: "acme/echo", actor: "chat_ui.plugins" }),
      (err: unknown) => err instanceof PluginBrowserApiError && err.message === "api_permission_denied",
    );
    await assert.rejects(
      () => client.decideForgeProposal({ id: "proposal_pl_stage_1", action: "approve", actor: "chat_ui.plugins" }),
      (err: unknown) => err instanceof PluginBrowserApiError && err.message === "api_permission_denied",
    );
    await assert.rejects(
      () =>
        client.decideCapabilityPackOperatorReview({
          pack_id: "ops.stage",
          pack_version: "1.0.0",
          action: "approve",
          actor: "chat_ui.plugins",
        }),
      (err: unknown) => err instanceof PluginBrowserApiError && err.message === "api_permission_denied",
    );
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists Forge promotion readiness with filters", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(`${parsed.pathname}${parsed.search}`);
    return jsonResponse({
      ok: true,
      total: 1,
      items: [
        {
          kind: "plugin.promotion.readiness",
          plugin_id: "pl_stage",
          proposal_id: "proposal_pl_stage_1",
          ready: false,
          status: "blocked",
          missing_requirements: ["proposal_review"],
          requirements: {
            proposal_id: true,
            proposal_review: false,
            proposal_evidence: true,
            tests: true,
            docs: true,
            risk_tier: true,
          },
          plugin: {
            id: "pl_stage",
            name: "Stage Helper",
            status: "staged",
            enabled: false,
            source_kind: "generated",
          },
          evidence: {
            proposal_review_status: "staged",
            proposal_review_receipt_id: "",
            proposal_evidence: [{ source: "operator" }],
            tests: ["tests/test_api_plugins.py"],
            docs: ["README.md"],
            risk_tier: "medium",
            validation_receipt_id: "plugin_validation_pl_stage_1",
            validation_receipt_path: "data/artifacts/plugins/validations/plugin_validation_pl_stage_1.json",
          },
          governance: {
            gate: "forge_promotion_readiness",
            scope: "plugins.write",
            inspection_route: "/forge/promotion_readiness/list",
            promotion_route: "/plugins/enable",
            promotion_authority: false,
            execution_authority: false,
            next_step: "satisfy_missing_requirements_before_promotion",
          },
        },
      ],
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const res = await client.listPromotionReadiness({
      limit: 10,
      plugin_id: "pl_stage",
      status: "blocked",
    });

    assert.deepEqual(requests, ["/forge/promotion_readiness/list?limit=10&plugin_id=pl_stage&status=blocked"]);
    assert.equal(res.total, 1);
    assert.equal(res.items[0]?.plugin_id, "pl_stage");
    assert.equal(res.items[0]?.ready, false);
    assert.deepEqual(res.items[0]?.missing_requirements, ["proposal_review"]);
    assert.equal(res.items[0]?.plugin?.status, "staged");
    assert.equal(res.items[0]?.evidence?.proposal_review_status, "staged");
    assert.equal(res.items[0]?.evidence?.validation_receipt_id, "plugin_validation_pl_stage_1");
    assert.equal(
      res.items[0]?.evidence?.validation_receipt_path,
      "data/artifacts/plugins/validations/plugin_validation_pl_stage_1.json",
    );
    assert.equal(res.items[0]?.governance?.promotion_authority, false);
    assert.equal(res.items[0]?.governance?.execution_authority, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists Forge proposals and review receipts", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(`${parsed.pathname}${parsed.search}`);
    if (parsed.pathname === "/forge/proposals/list") {
      return jsonResponse({
        total: 1,
        items: [
          {
            id: "proposal_pl_stage_1",
            proposal_id: "proposal_pl_stage_1",
            plugin_id: "pl_stage",
            status: "approved",
            friction: {
              summary: "Repeated review friction",
              evidence: ["mission.forge.review"],
            },
            quality_requirements: {
              risk_tier: "medium",
              tests: ["tests/test_api_forge.py"],
              docs: ["README.md"],
            },
            quality_analysis: {
              evidence: {
                validation_receipt_id: "plugin_validation_pl_stage_1",
                validation_receipt_path: "data/artifacts/plugins/validations/plugin_validation_pl_stage_1.json",
                validation_receipt_present: true,
              },
            },
            review_receipt_id: "review_1",
            review: {
              status: "approved",
              decision: "approve",
              receipt_id: "review_1",
            },
            relative_path: "proposals/proposal_pl_stage_1.json",
          },
        ],
      });
    }
    return jsonResponse({
      total: 1,
      items: [
        {
          id: "review_1",
          receipt_id: "review_1",
          proposal_id: "proposal_pl_stage_1",
          plugin_id: "pl_stage",
          previous_status: "staged",
          status: "approved",
          decision: "approve",
          reason: "approved after review",
          relative_path: "proposal_reviews/review_1.json",
        },
      ],
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const proposals = await client.listForgeProposals({ plugin_id: "pl_stage", limit: 5 });
    const reviews = await client.listForgeProposalReviews({ proposal_id: "proposal_pl_stage_1", limit: 5 });

    assert.deepEqual(requests, [
      "/forge/proposals/list?limit=5&plugin_id=pl_stage",
      "/forge/proposal_reviews/list?limit=5&proposal_id=proposal_pl_stage_1",
    ]);
    assert.equal(proposals.items[0]?.proposal_id, "proposal_pl_stage_1");
    assert.equal(proposals.items[0]?.review?.receipt_id, "review_1");
    assert.equal(proposals.items[0]?.quality_requirements?.risk_tier, "medium");
    assert.deepEqual(proposals.items[0]?.quality_analysis?.evidence, {
      validation_receipt_id: "plugin_validation_pl_stage_1",
      validation_receipt_path: "data/artifacts/plugins/validations/plugin_validation_pl_stage_1.json",
      validation_receipt_present: true,
    });
    assert.equal(reviews.items[0]?.receipt_id, "review_1");
    assert.equal(reviews.items[0]?.decision, "approve");
    assert.equal(reviews.items[0]?.previous_status, "staged");
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient decides Forge proposals through the governed review route", async () => {
  let captured: Record<string, unknown> = {};
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/forge/proposals/decision");
    captured = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({
      ok: true,
      applied: true,
      status: "approved",
      proposal_id: "proposal_pl_stage_1",
      plugin_id: "pl_stage",
      review_receipt_id: "review_1",
      review_receipt: {
        id: "review_1",
        receipt_id: "review_1",
        proposal_id: "proposal_pl_stage_1",
        plugin_id: "pl_stage",
        previous_status: "staged",
        status: "approved",
        decision: "approve",
        reason: "operator review",
        relative_path: "proposal_reviews/review_1.json",
      },
      item: {
        id: "proposal_pl_stage_1",
        proposal_id: "proposal_pl_stage_1",
        plugin_id: "pl_stage",
        status: "approved",
      },
      governance: {
        gate: "forge_proposal_review",
        promotion_authority: false,
        execution_authority: false,
      },
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const res = await client.decideForgeProposal({
      id: "proposal_pl_stage_1",
      action: "approve",
      reason: "operator review",
    });

    assert.equal(captured.id, "proposal_pl_stage_1");
    assert.equal(captured.action, "approve");
    assert.equal(captured.actor, "chat_ui.plugins");
    assert.equal(captured.reason, "operator review");
    assert.equal(res.ok, true);
    assert.equal(res.applied, true);
    assert.equal(res.status, "approved");
    assert.equal(res.proposal_id, "proposal_pl_stage_1");
    assert.equal(res.review_receipt?.receipt_id, "review_1");
    assert.equal(res.item?.status, "approved");
    assert.equal(res.governance?.promotion_authority, false);
    assert.equal(res.governance?.execution_authority, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists Forge promotion receipts", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(`${parsed.pathname}${parsed.search}`);
    return jsonResponse({
      total: 1,
      items: [
        {
          id: "promotion_1",
          receipt_id: "promotion_1",
          plugin_id: "pl_stage",
          proposal_id: "proposal_pl_stage_1",
          previous_status: "staged",
          promoted_status: "enabled",
          promoted_ts: 1710000000,
          reason: "explicit operator promotion",
          proposal_review: {
            status: "approved",
            receipt_id: "review_1",
          },
          proposal_evidence: ["mission.forge.review"],
          quality: {
            risk_tier: "medium",
            tests: ["tests/test_api_forge.py"],
            validation: {
              validation_receipt_id: "plugin_validation_pl_stage_1",
            },
          },
          relative_path: "promotions/promotion_1.json",
          governance: {
            promotion_authority: false,
            execution_authority: false,
          },
        },
      ],
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const res = await client.listForgePromotions({ plugin_id: "pl_stage", limit: 5 });

    assert.deepEqual(requests, ["/forge/promotions/list?limit=5&plugin_id=pl_stage"]);
    assert.equal(res.total, 1);
    assert.equal(res.items[0]?.receipt_id, "promotion_1");
    assert.equal(res.items[0]?.plugin_id, "pl_stage");
    assert.equal(res.items[0]?.proposal_id, "proposal_pl_stage_1");
    assert.equal(res.items[0]?.promoted_status, "enabled");
    assert.equal(res.items[0]?.proposal_review?.receipt_id, "review_1");
    assert.deepEqual(res.items[0]?.proposal_evidence, ["mission.forge.review"]);
    assert.equal(res.items[0]?.quality?.risk_tier, "medium");
    assert.equal(res.items[0]?.relative_path, "promotions/promotion_1.json");
    assert.equal(res.items[0]?.governance?.promotion_authority, false);
    assert.equal(res.items[0]?.governance?.execution_authority, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists capability pack operator review queue and decision receipts", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(`${parsed.pathname}${parsed.search}`);
    if (parsed.pathname === "/plugins/capabilities/packs/operator/review") {
      return jsonResponse({
        ok: true,
        kind: "plugin.capability_pack.operator_review",
        stage: "Stage 17 / Capability Economy",
        status: "ready_for_operator_review",
        pack_total: 1,
        ready_pack_count: 1,
        blocked_pack_count: 0,
        decision_required_pack_count: 1,
        review_queue_count: 1,
        packs: [
          {
            pack_id: "ops.review",
            pack_version: "1.0.0",
            pack_name: "Ops Review",
            status: "ready_for_operator_review",
            operator_review_ready: true,
            decision_required: true,
            decision_kind: "staged_pack_promotion_review",
            capability_count: 1,
            staged_capability_count: 1,
            blockers: [],
            operator_review_rule_declared: true,
            operator_review_governance_declared: true,
            quality_evidence_ready: true,
            proposal_lineage_ready: true,
            validation_receipts_ready: true,
            promotion_receipts_ready: true,
            review_items_sample: [
              {
                capability: "generated.review",
                version: "0.1.0",
                source: "generated",
                status: "staged",
                risk_tier: "normal",
                proposal_id: "plugin_proposal_review",
                validation_receipt_id: "plugin_validation_review",
                gaps: [],
              },
            ],
          },
        ],
        decision_routes: {
          pack_review_decision_route: "/plugins/capabilities/packs/operator/review/decisions",
          promotion_route_after_review: "/plugins/enable",
        },
        requirements: {
          pack_review_receipt_required_before_pack_promotion: true,
        },
        governance: {
          read_only: true,
          operator_facing: true,
          promotion_authority: false,
          execution_authority: false,
        },
        next_smallest_truthful_gap: "stage17_capability_pack_review_decisions",
      });
    }
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_pack.operator_review.decisions",
      stage: "Stage 17 / Capability Economy",
      total: 1,
      limit: 5,
      items: [
        {
          receipt_id: "capability_pack_operator_review_1710000000_ops_review",
          status: "approved",
          decision: "approve",
          pack_id: "ops.review",
          pack_version: "1.0.0",
          pack_name: "Ops Review",
          capability_ids: ["generated.review"],
          capability_count: 1,
          actor: "chat_ui.plugins",
          reason: "operator reviewed pack",
          decided_ts: 1710000000,
          path: "data/artifacts/plugins/capability_packs/operator_review_decisions/receipt.json",
          governance: {
            writes_receipt: true,
            promotion_authority: false,
            execution_authority: false,
          },
        },
      ],
      governance: {
        read_only: true,
        promotion_authority: false,
      },
      write_route: "/plugins/capabilities/packs/operator/review/decisions",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const review = await client.listCapabilityPackOperatorReview();
    const decisions = await client.listCapabilityPackOperatorReviewDecisions({
      limit: 5,
      pack_id: "ops.review",
      pack_version: "1.0.0",
    });

    assert.deepEqual(requests, [
      "/plugins/capabilities/packs/operator/review",
      "/plugins/capabilities/packs/operator/review/decisions?limit=5&pack_id=ops.review&pack_version=1.0.0",
    ]);
    assert.equal(review.status, "ready_for_operator_review");
    assert.equal(review.review_queue_count, 1);
    assert.equal(review.packs[0]?.pack_id, "ops.review");
    assert.equal(review.packs[0]?.decision_required, true);
    assert.equal(review.packs[0]?.review_items_sample?.[0]?.capability, "generated.review");
    assert.equal(review.governance?.promotion_authority, false);
    assert.equal(review.decision_routes?.pack_review_decision_route, "/plugins/capabilities/packs/operator/review/decisions");
    assert.equal(decisions.total, 1);
    assert.equal(decisions.items[0]?.receipt_id, "capability_pack_operator_review_1710000000_ops_review");
    assert.equal(decisions.items[0]?.status, "approved");
    assert.equal(decisions.items[0]?.governance?.promotion_authority, false);
    assert.equal(decisions.write_route, "/plugins/capabilities/packs/operator/review/decisions");
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists capability pack promotion discipline", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(`${parsed.pathname}${parsed.search}`);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_pack.promotion_discipline",
      stage: "Stage 17 / Capability Economy",
      status: "blocked",
      pack_total: 1,
      ready_pack_count: 0,
      blocked_pack_count: 1,
      unpacked_entry_count: 0,
      available_proposal_count: 1,
      available_validation_receipt_count: 1,
      available_promotion_receipt_count: 0,
      approved_pack_operator_review_count: 1,
      packs: [
        {
          pack_id: "ops.discipline",
          pack_version: "1.0.0",
          pack_name: "Ops Discipline",
          status: "blocked",
          ready: false,
          capability_count: 2,
          staged_capability_count: 1,
          promoted_capability_count: 1,
          blockers: ["mixed_staged_and_promoted_pack"],
          promotion_rules_ready: true,
          pack_governance_ready: true,
          quality_evidence_ready: true,
          validation_receipts_ready: true,
          proposal_lineage_ready: true,
          promotion_receipts_ready: false,
          operator_review_rule_declared: true,
          operator_review_governance_declared: true,
          operator_review_approved: true,
          lifecycle_mixed: true,
          failing_capabilities_sample: [
            {
              capability: "generated.promoted",
              version: "0.1.0",
              source: "generated",
              status: "promoted",
              risk_tier: "normal",
              promotion_receipt_id: "plugin_promotion_missing",
              gaps: ["promotion_receipt_not_found"],
            },
          ],
        },
      ],
      requirements: {
        promotion_discipline_is_read_only: true,
      },
      governance: {
        read_only: true,
        operator_facing: true,
        promotion_authority: false,
        execution_authority: false,
      },
      next_smallest_truthful_gap: "stage17_capability_pack_promotion_coherence",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const discipline = await client.listCapabilityPackPromotionDiscipline();

    assert.deepEqual(requests, ["/plugins/capabilities/packs/promotion/discipline"]);
    assert.equal(discipline.status, "blocked");
    assert.equal(discipline.blocked_pack_count, 1);
    assert.equal(discipline.available_proposal_count, 1);
    assert.equal(discipline.available_validation_receipt_count, 1);
    assert.equal(discipline.approved_pack_operator_review_count, 1);
    assert.equal(discipline.governance?.promotion_authority, false);
    assert.equal(discipline.requirements?.promotion_discipline_is_read_only, true);
    assert.equal(discipline.next_smallest_truthful_gap, "stage17_capability_pack_promotion_coherence");
    assert.equal(discipline.packs[0]?.pack_id, "ops.discipline");
    assert.equal(discipline.packs[0]?.ready, false);
    assert.equal(discipline.packs[0]?.lifecycle_mixed, true);
    assert.equal(discipline.packs[0]?.operator_review_approved, true);
    assert.equal(discipline.packs[0]?.failing_capabilities_sample?.[0]?.capability, "generated.promoted");
    assert.deepEqual(discipline.packs[0]?.failing_capabilities_sample?.[0]?.gaps, ["promotion_receipt_not_found"]);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists capability pack promotion rule remediation", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(`${parsed.pathname}${parsed.search}`);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_pack.promotion_rules.remediation",
      stage: "Stage 17 / Capability Economy",
      status: "blocked",
      pack_total: 1,
      ready_pack_count: 0,
      blocked_pack_count: 1,
      unpacked_entry_count: 0,
      remediation_pack_count: 1,
      remediation_queue_count: 1,
      remediation_queue_truncated: false,
      missing_rule_pack_count: 1,
      missing_governance_pack_count: 1,
      missing_quality_pack_count: 1,
      missing_receipt_pack_count: 1,
      canonical_promotion_rules: [
        "metadata_receipt_before_promotion",
        "quality_standards_before_promotion",
        "operator_review_before_promotion",
      ],
      first_action: "declare_canonical_promotion_rules",
      remediation_queue: [
        {
          pack_id: "ops.rules",
          pack_version: "1.0.0",
          pack_name: "Ops Rules",
          status: "blocked",
          ready: false,
          capability_count: 2,
          blockers: ["canonical_promotion_rules_missing"],
          missing_promotion_rules: ["quality_standards_before_promotion", "operator_review_before_promotion"],
          missing_governance_fields: ["operator_review_required"],
          missing_quality_evidence: ["docs"],
          missing_receipt_evidence: ["validation_receipt"],
          first_action: "declare_canonical_promotion_rules",
          promotion_rules: ["metadata_receipt_before_promotion"],
          failing_capabilities_sample: [
            {
              capability: "generated.rules",
              version: "0.1.0",
              source: "generated",
              status: "staged",
              risk_tier: "normal",
              gaps: ["promotion_rules_missing"],
            },
          ],
        },
      ],
      requirements: {
        read_only_remediation_queue: true,
        remediation_does_not_write_registry: true,
      },
      governance: {
        read_only: true,
        operator_facing: true,
        promotion_authority: false,
        execution_authority: false,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_pack_promotion_rule_backlog_execution",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const remediation = await client.listCapabilityPackPromotionRuleRemediation();

    assert.deepEqual(requests, ["/plugins/capabilities/packs/promotion/rules/remediation"]);
    assert.equal(remediation.status, "blocked");
    assert.equal(remediation.remediation_queue_count, 1);
    assert.equal(remediation.missing_rule_pack_count, 1);
    assert.equal(remediation.governance?.promotion_authority, false);
    assert.equal(remediation.governance?.memory_write, false);
    assert.equal(remediation.requirements?.read_only_remediation_queue, true);
    assert.equal(remediation.first_action, "declare_canonical_promotion_rules");
    assert.deepEqual(remediation.canonical_promotion_rules, [
      "metadata_receipt_before_promotion",
      "quality_standards_before_promotion",
      "operator_review_before_promotion",
    ]);
    assert.equal(remediation.remediation_queue[0]?.pack_id, "ops.rules");
    assert.deepEqual(remediation.remediation_queue[0]?.missing_promotion_rules, [
      "quality_standards_before_promotion",
      "operator_review_before_promotion",
    ]);
    assert.equal(
      remediation.remediation_queue[0]?.failing_capabilities_sample?.[0]?.capability,
      "generated.rules",
    );
    assert.equal(
      remediation.next_smallest_truthful_gap,
      "stage17_capability_pack_promotion_rule_backlog_execution",
    );
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists capability library promotion plan", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.promotion_plan",
      stage: "Stage 17 / Capability Economy",
      status: "blocked",
      promotion_plan_ready: false,
      pack_total: 47,
      ready_pack_count: 47,
      blocked_pack_count: 0,
      candidate_pack_count: 47,
      candidate_capability_count: 2265,
      promotable_capability_count: 0,
      blocked_capability_count: 2265,
      missing_requirement_counts: {
        proposal_evidence: 2265,
        proposal_review: 2265,
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          staged_capability_count: 2,
          promotable_capability_count: 0,
          blocked_capability_count: 2,
          capabilities_truncated: false,
          capabilities: [
            {
              capability: "generated.ops.run",
              status: "staged",
              enabled: false,
              promotion_ready: false,
              missing_requirements: ["proposal_evidence", "proposal_review"],
              proposal_id: "plugin_proposal_generated_ops_run",
              proposal_review_status: "staged",
              proposal_review_receipt_id: "",
              validation_receipt_id: "validation_generated_ops_run",
              pack_operator_review_required: true,
              pack_operator_review_status: "approved",
              pack_operator_review_receipt_id: "capability_pack_operator_review_1",
              promotion_route: "/plugins/enable",
              promotion_would_write_receipt: true,
              promotion_would_enable_capability: true,
            },
          ],
        },
      ],
      routes: {
        proposal_evidence_plan_route: "/plugins/capabilities/library/proposal-evidence/plan",
        proposal_review_route: "/forge/proposals/decision",
        promotion_route: "/plugins/enable",
      },
      requirements: {
        uses_existing_plugin_promotion_readiness: true,
        proposal_review_required_before_promotion: true,
        promotion_requires_plugins_write_scope: true,
        explicit_operator_action_required: true,
        no_auto_promotion: true,
      },
      governance: {
        read_only: true,
        does_not_write_promotion_receipts: true,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        does_not_enable_capabilities: true,
        promotion_authority: false,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_promotion_readiness",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const plan = await client.listCapabilityLibraryPromotionPlan();

    assert.deepEqual(requests, ["/plugins/capabilities/library/promotion/plan"]);
    assert.equal(plan.status, "blocked");
    assert.equal(plan.promotion_plan_ready, false);
    assert.equal(plan.candidate_capability_count, 2265);
    assert.equal(plan.promotable_capability_count, 0);
    assert.equal(plan.blocked_capability_count, 2265);
    assert.equal(plan.missing_requirement_counts?.proposal_evidence, 2265);
    assert.equal(plan.requirements?.proposal_review_required_before_promotion, true);
    assert.equal(plan.requirements?.promotion_requires_plugins_write_scope, true);
    assert.equal(plan.requirements?.no_auto_promotion, true);
    assert.equal(plan.governance?.read_only, true);
    assert.equal(plan.governance?.does_not_write_promotion_receipts, true);
    assert.equal(plan.governance?.does_not_promote_capabilities, true);
    assert.equal(plan.governance?.does_not_enable_capabilities, true);
    assert.equal(plan.governance?.promotion_authority, false);
    assert.equal(plan.next_smallest_truthful_gap, "stage17_capability_library_promotion_readiness");
    assert.equal(plan.routes?.promotion_route, "/plugins/enable");
    assert.equal(plan.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(plan.packs[0]?.blocked_capability_count, 2);
    assert.equal(plan.packs[0]?.capabilities[0]?.capability, "generated.ops.run");
    assert.equal(plan.packs[0]?.capabilities[0]?.promotion_ready, false);
    assert.deepEqual(plan.packs[0]?.capabilities[0]?.missing_requirements, [
      "proposal_evidence",
      "proposal_review",
    ]);
    assert.equal(plan.packs[0]?.capabilities[0]?.promotion_route, "/plugins/enable");
    assert.equal(plan.packs[0]?.capabilities[0]?.promotion_would_write_receipt, true);
    assert.equal(plan.packs[0]?.capabilities[0]?.promotion_would_enable_capability, true);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists capability library proposal evidence plan", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.proposal_evidence_plan",
      stage: "Stage 17 / Capability Economy",
      status: "blocked",
      proposal_evidence_plan_ready: true,
      pack_total: 50,
      ready_pack_count: 50,
      blocked_pack_count: 0,
      candidate_pack_count: 47,
      candidate_capability_count: 2265,
      unique_proposal_count: 2265,
      proposal_evidence_missing_count: 2265,
      proposal_evidence_ready_count: 0,
      missing_proposal_evidence_count: 2265,
      evidence_ready_proposal_count: 0,
      proposal_id_missing_count: 0,
      proposal_review_missing_count: 2265,
      blocked_before_evidence_count: 0,
      missing_requirement_counts: {
        proposal_review: 2265,
        proposal_evidence: 2265,
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "0.0.0-migration",
          pack_name: "Ops Plugin",
          staged_capability_count: 2,
          proposal_evidence_missing_count: 2,
          proposal_evidence_ready_count: 0,
          blocked_before_evidence_count: 0,
          capabilities_truncated: false,
          capabilities: [
            {
              capability: "generated.ops.run",
              status: "staged",
              proposal_id: "plugin_proposal_generated_ops_run",
              proposal_review_status: "staged",
              proposal_evidence_ready: false,
              proposal_evidence_missing: true,
              proposal_evidence: [],
              linked_proposal_artifact_evidence: [],
              evidence_source: "missing_in_plugin_metadata_and_linked_proposal_artifact",
              missing_requirements: ["proposal_review", "proposal_evidence"],
              blockers_before_evidence: [],
            },
          ],
        },
      ],
      routes: {
        promotion_plan_route: "/plugins/capabilities/library/promotion/plan",
        proposal_review_plan_route: "/plugins/capabilities/library/proposal-review/plan",
      },
      requirements: {
        read_only_gap_projection: true,
        no_auto_reconstruction: true,
      },
      governance: {
        read_only: true,
        does_not_write_proposals: true,
        does_not_approve_proposals: true,
        promotion_authority: false,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_promotion_readiness",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const plan = await client.listCapabilityLibraryProposalEvidencePlan();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-evidence/plan"]);
    assert.equal(plan.status, "blocked");
    assert.equal(plan.proposal_evidence_plan_ready, true);
    assert.equal(plan.candidate_capability_count, 2265);
    assert.equal(plan.proposal_evidence_missing_count, 2265);
    assert.equal(plan.proposal_evidence_ready_count, 0);
    assert.equal(plan.missing_requirement_counts?.proposal_evidence, 2265);
    assert.equal(plan.requirements?.read_only_gap_projection, true);
    assert.equal(plan.requirements?.no_auto_reconstruction, true);
    assert.equal(plan.governance?.does_not_write_proposals, true);
    assert.equal(plan.governance?.does_not_approve_proposals, true);
    assert.equal(plan.governance?.promotion_authority, false);
    assert.equal(plan.next_smallest_truthful_gap, "stage17_capability_library_promotion_readiness");
    assert.equal(plan.routes?.promotion_plan_route, "/plugins/capabilities/library/promotion/plan");
    assert.equal(plan.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(plan.packs[0]?.proposal_evidence_missing_count, 2);
    assert.equal(plan.packs[0]?.capabilities[0]?.capability, "generated.ops.run");
    assert.equal(plan.packs[0]?.capabilities[0]?.proposal_evidence_missing, true);
    assert.equal(
      plan.packs[0]?.capabilities[0]?.evidence_source,
      "missing_in_plugin_metadata_and_linked_proposal_artifact",
    );
    assert.deepEqual(plan.packs[0]?.capabilities[0]?.missing_requirements, [
      "proposal_review",
      "proposal_evidence",
    ]);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists capability library proposal evidence remediation", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.proposal_evidence_remediation",
      stage: "Stage 17 / Capability Economy",
      status: "ready_for_proposal_evidence_backfill",
      proposal_evidence_remediation_ready: true,
      pack_total: 50,
      ready_pack_count: 50,
      blocked_pack_count: 0,
      candidate_pack_count: 1,
      candidate_capability_count: 2,
      existing_metadata_evidence_count: 10,
      proposal_id_missing_count: 0,
      plugin_record_missing_count: 0,
      source_proposal_evidence_plan: {
        status: "blocked",
        candidate_capability_count: 2265,
        proposal_evidence_missing_count: 2263,
        proposal_evidence_ready_count: 2,
        proposal_review_missing_count: 2265,
        next_smallest_truthful_gap: "stage17_capability_library_promotion_readiness",
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          staged_capability_count: 2,
          candidate_capability_count: 2,
          capabilities_truncated: false,
          capabilities: [
            {
              capability: "generated.ops.run",
              status: "staged",
              proposal_id: "plugin_proposal_generated_ops_run",
              metadata_proposal_evidence: [],
              linked_proposal_artifact_evidence: ["mission.generated.ops.run.repeat"],
              evidence_source: "linked_proposal_artifact",
              writes_registry_metadata: true,
              writes_proposals: false,
              approves_proposals: false,
              promotes_capability: false,
            },
          ],
        },
      ],
      routes: {
        proposal_evidence_plan_route: "/plugins/capabilities/library/proposal-evidence/plan",
        proposal_evidence_remediation_apply_route:
          "/plugins/capabilities/library/proposal-evidence/remediation/apply",
      },
      requirements: {
        only_existing_linked_proposal_artifact_evidence: true,
        no_synthetic_evidence: true,
      },
      governance: {
        read_only: true,
        apply_requires_plugins_write_scope: true,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_proposal_evidence_remediation_apply",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const remediation = await client.listCapabilityLibraryProposalEvidenceRemediation();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-evidence/remediation"]);
    assert.equal(remediation.status, "ready_for_proposal_evidence_backfill");
    assert.equal(remediation.proposal_evidence_remediation_ready, true);
    assert.equal(remediation.candidate_capability_count, 2);
    assert.equal(remediation.source_proposal_evidence_plan?.proposal_evidence_missing_count, 2263);
    assert.equal(remediation.requirements?.only_existing_linked_proposal_artifact_evidence, true);
    assert.equal(remediation.requirements?.no_synthetic_evidence, true);
    assert.equal(remediation.governance?.apply_requires_plugins_write_scope, true);
    assert.equal(remediation.governance?.does_not_approve_proposals, true);
    assert.equal(remediation.governance?.does_not_promote_capabilities, true);
    assert.equal(remediation.next_smallest_truthful_gap, "stage17_capability_library_proposal_evidence_remediation_apply");
    assert.equal(
      remediation.routes?.proposal_evidence_remediation_apply_route,
      "/plugins/capabilities/library/proposal-evidence/remediation/apply",
    );
    assert.equal(remediation.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(remediation.packs[0]?.candidate_capability_count, 2);
    assert.equal(remediation.packs[0]?.capabilities[0]?.capability, "generated.ops.run");
    assert.deepEqual(remediation.packs[0]?.capabilities[0]?.linked_proposal_artifact_evidence, [
      "mission.generated.ops.run.repeat",
    ]);
    assert.equal(remediation.packs[0]?.capabilities[0]?.writes_registry_metadata, true);
    assert.equal(remediation.packs[0]?.capabilities[0]?.writes_proposals, false);
    assert.equal(remediation.packs[0]?.capabilities[0]?.approves_proposals, false);
    assert.equal(remediation.packs[0]?.capabilities[0]?.promotes_capability, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists capability library proposal evidence source readiness", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.proposal_evidence_source_readiness",
      stage: "Stage 17 / Capability Economy",
      status: "operator_evidence_refs_required",
      proposal_evidence_source_readiness_ready: true,
      proposal_evidence_missing_count: 2268,
      proposal_evidence_ready_count: 0,
      proposal_review_missing_count: 2268,
      blocked_before_evidence_count: 0,
      automatic_source_candidate_pack_count: 0,
      automatic_source_candidate_capability_count: 0,
      automatic_sources_exhausted: true,
      operator_evidence_intake_candidate_pack_count: 47,
      operator_evidence_intake_candidate_capability_count: 2268,
      operator_evidence_ref_required_count: 2268,
      recorded_operator_evidence_pack_count: 0,
      recorded_operator_evidence_capability_count: 0,
      recorded_operator_evidence_ref_count: 0,
      next_operator_evidence_batch_ready: true,
      next_operator_evidence_batch_capability_count: 2,
      next_operator_evidence_batch: {
        status: "ready_for_operator_evidence_batch",
        ready: true,
        batch_source: "operator_evidence_intake_checklist_first_visible_pack",
        pack_id: "ops.market",
        pack_version: "1.0.0",
        pack_name: "Ops Market Pack",
        pack_candidate_capability_count: 2,
        pack_evidence_ref_required_count: 2,
        batch_capability_count: 2,
        batch_evidence_ref_required_count: 2,
        batch_capabilities_truncated: false,
        claim_scope: "operator_supplied_friction_evidence_reference_not_independent_verification",
        operator_must_supply_evidence_refs: true,
        operator_supplied_evidence_not_independently_verified: true,
        does_not_validate_evidence_truth: true,
        requires_future_proposal_review: true,
        dry_run_required_before_apply: true,
        no_synthetic_evidence: true,
        capabilities: [
          {
            capability: "generated.market",
            status: "staged",
            proposal_id: "plugin_proposal_market",
            proposal_review_status: "staged",
            proposal_review_receipt_id: "",
            missing_requirements: ["proposal_evidence", "proposal_review"],
            blockers_before_evidence: [],
            evidence_refs_required: true,
            operator_supplied_evidence_not_independently_verified: true,
            intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
          },
        ],
        apply_payload_hint: {
          pack_ids: ["ops.market"],
          capability_ids: ["generated.market"],
          evidence_refs: [],
          dry_run: true,
          max_pack_count: 1,
          max_total_capability_count: 1,
          max_capability_count_per_pack: 1,
        },
        routes: {
          operator_intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        },
      },
      proposal_review_apply_status: "blocked_on_operator_evidence_refs",
      source_proposal_evidence_plan: {
        status: "blocked",
        candidate_pack_count: 47,
        candidate_capability_count: 2268,
        proposal_evidence_missing_count: 2268,
        proposal_evidence_ready_count: 0,
        proposal_review_missing_count: 2268,
        blocked_before_evidence_count: 0,
        next_smallest_truthful_gap: "stage17_capability_library_promotion_readiness",
      },
      source_inventory: {
        existing_linked_proposal_artifact: {
          status: "no_existing_artifact_evidence_candidates",
          ready: false,
          candidate_capability_count: 0,
          writes_proposals: false,
        },
        existing_registry_friction_summary_ref: {
          status: "no_existing_friction_summary_ref_candidates",
          ready: false,
          candidate_capability_count: 0,
          records_reference_not_friction_summary_body: true,
        },
        operator_supplied_evidence_refs: {
          status: "ready_for_operator_evidence_refs",
          ready: true,
          candidate_capability_count: 2268,
          evidence_ref_required_count: 2268,
          does_not_validate_evidence_truth: true,
        },
        synthetic_evidence: {
          status: "disallowed",
          ready: false,
          candidate_capability_count: 0,
        },
      },
      routes: {
        proposal_evidence_source_readiness_route:
          "/plugins/capabilities/library/proposal-evidence/source-readiness",
        operator_intake_export_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/export",
      },
      requirements: {
        read_only_source_inventory: true,
        no_synthetic_evidence: true,
        does_not_validate_evidence_truth: true,
      },
      governance: {
        read_only: true,
        does_not_write_proposals: true,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const readiness = await client.listCapabilityLibraryProposalEvidenceSourceReadiness();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-evidence/source-readiness"]);
    assert.equal(readiness.status, "operator_evidence_refs_required");
    assert.equal(readiness.proposal_evidence_source_readiness_ready, true);
    assert.equal(readiness.proposal_evidence_missing_count, 2268);
    assert.equal(readiness.automatic_source_candidate_capability_count, 0);
    assert.equal(readiness.automatic_sources_exhausted, true);
    assert.equal(readiness.operator_evidence_intake_candidate_capability_count, 2268);
    assert.equal(readiness.operator_evidence_ref_required_count, 2268);
    assert.equal(readiness.next_operator_evidence_batch_ready, true);
    assert.equal(readiness.next_operator_evidence_batch_capability_count, 2);
    assert.equal(readiness.next_operator_evidence_batch?.status, "ready_for_operator_evidence_batch");
    assert.equal(readiness.next_operator_evidence_batch?.pack_id, "ops.market");
    assert.equal(readiness.next_operator_evidence_batch?.batch_capability_count, 2);
    assert.equal(readiness.next_operator_evidence_batch?.operator_must_supply_evidence_refs, true);
    assert.equal(readiness.next_operator_evidence_batch?.does_not_validate_evidence_truth, true);
    assert.equal(readiness.next_operator_evidence_batch?.dry_run_required_before_apply, true);
    assert.equal(readiness.next_operator_evidence_batch?.capabilities?.[0]?.capability, "generated.market");
    assert.deepEqual(readiness.next_operator_evidence_batch?.apply_payload_hint?.evidence_refs, []);
    assert.equal(readiness.source_proposal_evidence_plan?.candidate_pack_count, 47);
    assert.equal(readiness.source_inventory?.existing_linked_proposal_artifact?.candidate_capability_count, 0);
    assert.equal(
      readiness.source_inventory?.existing_registry_friction_summary_ref
        ?.records_reference_not_friction_summary_body,
      true,
    );
    assert.equal(readiness.source_inventory?.operator_supplied_evidence_refs?.ready, true);
    assert.equal(readiness.source_inventory?.operator_supplied_evidence_refs?.does_not_validate_evidence_truth, true);
    assert.equal(readiness.source_inventory?.synthetic_evidence?.status, "disallowed");
    assert.equal(readiness.requirements?.read_only_source_inventory, true);
    assert.equal(readiness.requirements?.no_synthetic_evidence, true);
    assert.equal(readiness.governance?.does_not_write_proposals, true);
    assert.equal(readiness.governance?.does_not_approve_proposals, true);
    assert.equal(readiness.governance?.does_not_promote_capabilities, true);
    assert.equal(
      readiness.routes?.operator_intake_export_route,
      "/plugins/capabilities/library/proposal-evidence/operator-intake/export",
    );
    assert.equal(
      readiness.next_smallest_truthful_gap,
      "stage17_capability_library_operator_proposal_evidence_refs",
    );
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists capability library proposal evidence friction summary refs", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.proposal_evidence_friction_summary_refs",
      stage: "Stage 17 / Capability Economy",
      status: "ready_for_proposal_evidence_friction_summary_ref_backfill",
      proposal_evidence_friction_summary_refs_ready: true,
      pack_total: 50,
      ready_pack_count: 50,
      blocked_pack_count: 0,
      candidate_pack_count: 1,
      candidate_capability_count: 2,
      existing_metadata_evidence_count: 10,
      friction_summary_missing_count: 3,
      proposal_id_missing_count: 0,
      plugin_record_missing_count: 0,
      source_proposal_evidence_plan: {
        status: "blocked",
        candidate_capability_count: 2265,
        proposal_evidence_missing_count: 2263,
        proposal_evidence_ready_count: 2,
        proposal_review_missing_count: 2265,
        next_smallest_truthful_gap: "stage17_capability_library_promotion_readiness",
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          staged_capability_count: 2,
          candidate_capability_count: 2,
          capabilities_truncated: false,
          capabilities: [
            {
              capability: "generated.ops.run",
              status: "staged",
              proposal_id: "plugin_proposal_generated_ops_run",
              metadata_proposal_evidence: [],
              friction_summary_field: "friction_summary",
              friction_summary_ref: "registry.plugins.generated.ops.run.meta.friction_summary",
              friction_summary_preview: "Repeated ops run review",
              evidence_source: "existing_registry_friction_summary_ref",
              writes_registry_metadata: true,
              writes_proposals: false,
              approves_proposals: false,
              promotes_capability: false,
              requires_future_review: true,
            },
          ],
        },
      ],
      routes: {
        proposal_evidence_plan_route: "/plugins/capabilities/library/proposal-evidence/plan",
        proposal_evidence_friction_summary_refs_apply_route:
          "/plugins/capabilities/library/proposal-evidence/friction-summary-refs/apply",
      },
      requirements: {
        only_existing_registry_friction_summary: true,
        records_reference_not_friction_summary_body: true,
        no_synthetic_evidence: true,
        not_independent_verification: true,
        requires_future_review: true,
      },
      governance: {
        read_only: true,
        apply_requires_plugins_write_scope: true,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_proposal_evidence_friction_summary_refs_apply",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const refs = await client.listCapabilityLibraryProposalEvidenceFrictionSummaryRefs();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-evidence/friction-summary-refs"]);
    assert.equal(refs.status, "ready_for_proposal_evidence_friction_summary_ref_backfill");
    assert.equal(refs.proposal_evidence_friction_summary_refs_ready, true);
    assert.equal(refs.candidate_capability_count, 2);
    assert.equal(refs.friction_summary_missing_count, 3);
    assert.equal(refs.source_proposal_evidence_plan?.proposal_evidence_missing_count, 2263);
    assert.equal(refs.requirements?.only_existing_registry_friction_summary, true);
    assert.equal(refs.requirements?.records_reference_not_friction_summary_body, true);
    assert.equal(refs.requirements?.not_independent_verification, true);
    assert.equal(refs.governance?.apply_requires_plugins_write_scope, true);
    assert.equal(refs.governance?.does_not_approve_proposals, true);
    assert.equal(refs.governance?.does_not_promote_capabilities, true);
    assert.equal(
      refs.routes?.proposal_evidence_friction_summary_refs_apply_route,
      "/plugins/capabilities/library/proposal-evidence/friction-summary-refs/apply",
    );
    assert.equal(refs.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(refs.packs[0]?.candidate_capability_count, 2);
    assert.equal(refs.packs[0]?.capabilities[0]?.capability, "generated.ops.run");
    assert.equal(
      refs.packs[0]?.capabilities[0]?.friction_summary_ref,
      "registry.plugins.generated.ops.run.meta.friction_summary",
    );
    assert.equal(refs.packs[0]?.capabilities[0]?.writes_registry_metadata, true);
    assert.equal(refs.packs[0]?.capabilities[0]?.writes_proposals, false);
    assert.equal(refs.packs[0]?.capabilities[0]?.approves_proposals, false);
    assert.equal(refs.packs[0]?.capabilities[0]?.promotes_capability, false);
    assert.equal(refs.packs[0]?.capabilities[0]?.requires_future_review, true);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient applies capability library proposal evidence friction summary refs", async () => {
  const captured: Record<string, unknown>[] = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/plugins/capabilities/library/proposal-evidence/friction-summary-refs/apply");
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    captured.push(body);
    if (body.dry_run === false) {
      return jsonResponse({
        ok: true,
        applied: true,
        kind: "plugin.capability_library.proposal_evidence_friction_summary_refs.apply",
        status: "recorded",
        dry_run: false,
        recorded_pack_count: 1,
        recorded_capability_count: 2,
        recorded: [
          {
            pack_id: "legacy.generated.opsplugin",
            pack_version: "1.0.0",
            pack_name: "Ops Plugin",
            capability_count: 2,
            changed_capability_count: 2,
            changed_capability_ids: ["generated.ops.run", "generated.ops.wait"],
            evidence_source: "existing_registry_friction_summary_ref",
            writes_registry_metadata: true,
            writes_proposals: false,
            approves_proposals: false,
            promotes_capabilities: false,
            enables_capabilities: false,
            requires_future_review: true,
            status: "recorded",
          },
        ],
        remaining_candidate_pack_count: 0,
        remaining_candidate_capability_count: 0,
        governance: {
          writes_registry_metadata: true,
          writes_receipts: false,
          writes_proposals: false,
          only_existing_registry_friction_summary: true,
          evidence_claim_scope: "existing_registry_friction_summary_reference_not_independent_verification",
          does_not_approve_proposals: true,
          does_not_promote_capabilities: true,
          memory_write: false,
        },
      });
    }
    return jsonResponse({
      ok: true,
      applied: false,
      kind: "plugin.capability_library.proposal_evidence_friction_summary_refs.apply",
      status: "dry_run",
      dry_run: true,
      planned_pack_count: 1,
      planned_capability_count: 2,
      planned: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          capability_count: 2,
          evidence_source: "existing_registry_friction_summary_ref",
          capabilities: [
            {
              capability: "generated.ops.run",
              proposal_id: "plugin_proposal_generated_ops_run",
              friction_summary_field: "friction_summary",
              friction_summary_ref: "registry.plugins.generated.ops.run.meta.friction_summary",
            },
          ],
          writes_registry_metadata: false,
          writes_proposals: false,
          approves_proposals: false,
          promotes_capabilities: false,
          enables_capabilities: false,
          requires_future_review: true,
        },
      ],
      governance: {
        writes_registry_metadata: false,
        writes_receipts: false,
        writes_proposals: false,
        only_existing_registry_friction_summary: true,
        evidence_claim_scope: "existing_registry_friction_summary_reference_not_independent_verification",
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_proposal_evidence_friction_summary_refs_apply",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const dryRun = await client.applyCapabilityLibraryProposalEvidenceFrictionSummaryRefs({
      pack_ids: ["legacy.generated.opsplugin"],
      max_pack_count: 1,
      max_total_capability_count: 2,
      max_capability_count_per_pack: 2,
      meta: { surface: "test" },
    });
    const applied = await client.applyCapabilityLibraryProposalEvidenceFrictionSummaryRefs({
      pack_ids: ["legacy.generated.opsplugin"],
      max_pack_count: 1,
      max_total_capability_count: 2,
      max_capability_count_per_pack: 2,
      dry_run: false,
      meta: { surface: "test" },
    });

    assert.equal(captured[0]?.actor, "chat_ui.plugins");
    assert.equal(captured[0]?.dry_run, true);
    assert.deepEqual(captured[0]?.pack_ids, ["legacy.generated.opsplugin"]);
    assert.equal(captured[0]?.max_pack_count, 1);
    assert.equal(captured[1]?.dry_run, false);
    assert.equal(dryRun.status, "dry_run");
    assert.equal(dryRun.applied, false);
    assert.equal(dryRun.planned_pack_count, 1);
    assert.equal(dryRun.planned_capability_count, 2);
    assert.equal(dryRun.planned?.[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(dryRun.planned?.[0]?.capabilities?.[0]?.capability, "generated.ops.run");
    assert.equal(
      dryRun.planned?.[0]?.capabilities?.[0]?.friction_summary_ref,
      "registry.plugins.generated.ops.run.meta.friction_summary",
    );
    assert.equal(dryRun.planned?.[0]?.writes_registry_metadata, false);
    assert.equal(dryRun.planned?.[0]?.writes_proposals, false);
    assert.equal(dryRun.planned?.[0]?.approves_proposals, false);
    assert.equal(dryRun.planned?.[0]?.promotes_capabilities, false);
    assert.equal(dryRun.planned?.[0]?.requires_future_review, true);
    assert.equal(dryRun.governance?.writes_registry_metadata, false);
    assert.equal(dryRun.governance?.only_existing_registry_friction_summary, true);
    assert.equal(
      dryRun.governance?.evidence_claim_scope,
      "existing_registry_friction_summary_reference_not_independent_verification",
    );
    assert.equal(dryRun.governance?.does_not_promote_capabilities, true);
    assert.equal(dryRun.governance?.memory_write, false);
    assert.equal(applied.applied, true);
    assert.equal(applied.recorded_pack_count, 1);
    assert.equal(applied.recorded_capability_count, 2);
    assert.deepEqual(applied.recorded?.[0]?.changed_capability_ids, ["generated.ops.run", "generated.ops.wait"]);
    assert.equal(applied.recorded?.[0]?.writes_registry_metadata, true);
    assert.equal(applied.recorded?.[0]?.writes_proposals, false);
    assert.equal(applied.recorded?.[0]?.approves_proposals, false);
    assert.equal(applied.recorded?.[0]?.promotes_capabilities, false);
    assert.equal(applied.remaining_candidate_capability_count, 0);
    assert.equal(applied.governance?.writes_registry_metadata, true);
    assert.equal(applied.governance?.does_not_approve_proposals, true);
    assert.equal(applied.governance?.memory_write, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists capability library proposal review plan", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.proposal_review_plan",
      stage: "Stage 17 / Capability Economy",
      status: "blocked",
      proposal_review_plan_ready: false,
      pack_total: 47,
      ready_pack_count: 47,
      blocked_pack_count: 0,
      candidate_pack_count: 47,
      candidate_capability_count: 2265,
      unique_proposal_count: 2265,
      proposal_review_missing_count: 2265,
      approved_proposal_review_count: 0,
      reviewable_capability_count: 0,
      reviewable_proposal_count: 0,
      blocked_before_review_capability_count: 2265,
      blocked_proposal_count: 2265,
      approved_proposal_count: 0,
      missing_requirement_counts: {
        proposal_evidence: 2265,
        proposal_review: 2265,
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          staged_capability_count: 2,
          reviewable_capability_count: 0,
          blocked_before_review_capability_count: 2,
          approved_proposal_review_count: 0,
          proposals_truncated: false,
          proposals: [
            {
              capability: "generated.ops.run",
              status: "staged",
              proposal_id: "plugin_proposal_generated_ops_run",
              proposal_review_status: "staged",
              proposal_review_receipt_id: "",
              proposal_review_missing: true,
              review_ready: false,
              approved_review: false,
              missing_requirements: ["proposal_evidence", "proposal_review"],
              blockers_before_review: ["proposal_evidence"],
              proposal_review_route: "/forge/proposals/decision",
              proposal_review_would_write_receipt: true,
              proposal_review_would_promote_capability: false,
              proposal_review_would_enable_capability: false,
            },
          ],
        },
      ],
      routes: {
        proposal_evidence_plan_route: "/plugins/capabilities/library/proposal-evidence/plan",
        proposal_review_route: "/forge/proposals/decision",
        promotion_plan_route: "/plugins/capabilities/library/promotion/plan",
      },
      requirements: {
        proposal_evidence_required_before_review: true,
        proposal_review_does_not_promote_or_enable_capabilities: true,
        no_auto_approval: true,
      },
      governance: {
        read_only: true,
        does_not_write_proposal_review_receipts: true,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        does_not_enable_capabilities: true,
        proposal_review_authority: false,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_promotion_readiness",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const plan = await client.listCapabilityLibraryProposalReviewPlan();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-review/plan"]);
    assert.equal(plan.status, "blocked");
    assert.equal(plan.proposal_review_plan_ready, false);
    assert.equal(plan.candidate_capability_count, 2265);
    assert.equal(plan.proposal_review_missing_count, 2265);
    assert.equal(plan.reviewable_capability_count, 0);
    assert.equal(plan.blocked_before_review_capability_count, 2265);
    assert.equal(plan.missing_requirement_counts?.proposal_evidence, 2265);
    assert.equal(plan.requirements?.proposal_evidence_required_before_review, true);
    assert.equal(plan.requirements?.no_auto_approval, true);
    assert.equal(plan.governance?.read_only, true);
    assert.equal(plan.governance?.does_not_write_proposal_review_receipts, true);
    assert.equal(plan.governance?.does_not_approve_proposals, true);
    assert.equal(plan.governance?.does_not_promote_capabilities, true);
    assert.equal(plan.governance?.proposal_review_authority, false);
    assert.equal(plan.next_smallest_truthful_gap, "stage17_capability_library_promotion_readiness");
    assert.equal(plan.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(plan.packs[0]?.blocked_before_review_capability_count, 2);
    assert.equal(plan.packs[0]?.proposals[0]?.capability, "generated.ops.run");
    assert.equal(plan.packs[0]?.proposals[0]?.review_ready, false);
    assert.deepEqual(plan.packs[0]?.proposals[0]?.blockers_before_review, ["proposal_evidence"]);
    assert.equal(plan.packs[0]?.proposals[0]?.proposal_review_would_write_receipt, true);
    assert.equal(plan.packs[0]?.proposals[0]?.proposal_review_would_promote_capability, false);
    assert.equal(plan.packs[0]?.proposals[0]?.proposal_review_would_enable_capability, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists proposal review apply readiness", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.proposal_review_apply_readiness",
      stage: "Stage 17 / Capability Economy",
      status: "blocked_on_operator_evidence_refs",
      proposal_review_apply_ready: false,
      reviewable_pack_count: 0,
      blocked_pack_count: 47,
      reviewable_capability_count: 0,
      proposal_review_missing_count: 2265,
      blocked_before_review_capability_count: 2265,
      approved_proposal_review_count: 0,
      source_proposal_evidence_plan: {
        status: "blocked",
        proposal_evidence_missing_count: 2265,
        proposal_evidence_ready_count: 0,
        proposal_review_missing_count: 2265,
        next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
      },
      source_operator_evidence_intake_audit: {
        status: "no_operator_evidence_refs_recorded",
        operator_evidence_intake_audit_ready: false,
        recorded_pack_count: 0,
        recorded_capability_count: 0,
        evidence_ref_count: 0,
        future_review_required_count: 0,
        next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
      },
      source_proposal_review_plan: {
        status: "blocked",
        proposal_review_plan_ready: false,
        candidate_capability_count: 2265,
        reviewable_capability_count: 0,
        blocked_before_review_capability_count: 2265,
        proposal_review_missing_count: 2265,
        approved_proposal_review_count: 0,
        next_smallest_truthful_gap: "stage17_capability_library_promotion_readiness",
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          staged_capability_count: 2,
          reviewable_capability_count: 0,
          blocked_before_review_capability_count: 2,
          approved_proposal_review_count: 0,
          proposals_truncated: false,
          proposals: [
            {
              capability: "generated.ops.run",
              proposal_id: "plugin_proposal_generated_ops_run",
              proposal_review_status: "staged",
              proposal_review_missing: true,
              review_ready: false,
              blockers_before_review: ["proposal_evidence"],
              proposal_review_route: "/forge/proposals/decision",
              proposal_review_would_write_receipt: true,
              proposal_review_would_promote_capability: false,
              proposal_review_would_enable_capability: false,
            },
          ],
        },
      ],
      routes: {
        proposal_review_apply_readiness_route: "/plugins/capabilities/library/proposal-review/apply-readiness",
        proposal_review_plan_route: "/plugins/capabilities/library/proposal-review/plan",
        proposal_review_route: "/forge/proposals/decision",
        operator_intake_audit_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/audit",
        operator_intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
      },
      requirements: {
        proposal_evidence_required_before_review: true,
        forge_decision_route_required: true,
        does_not_apply_reviews: true,
        no_auto_approval: true,
      },
      governance: {
        read_only: true,
        does_not_write_proposal_review_receipts: true,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        does_not_enable_capabilities: true,
        proposal_review_authority: false,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const readiness = await client.listCapabilityLibraryProposalReviewApplyReadiness();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-review/apply-readiness"]);
    assert.equal(readiness.status, "blocked_on_operator_evidence_refs");
    assert.equal(readiness.proposal_review_apply_ready, false);
    assert.equal(readiness.reviewable_capability_count, 0);
    assert.equal(readiness.blocked_before_review_capability_count, 2265);
    assert.equal(readiness.source_proposal_evidence_plan?.proposal_evidence_missing_count, 2265);
    assert.equal(readiness.source_operator_evidence_intake_audit?.recorded_capability_count, 0);
    assert.equal(readiness.source_proposal_review_plan?.proposal_review_plan_ready, false);
    assert.equal(readiness.requirements?.does_not_apply_reviews, true);
    assert.equal(readiness.requirements?.forge_decision_route_required, true);
    assert.equal(readiness.governance?.read_only, true);
    assert.equal(readiness.governance?.does_not_write_proposal_review_receipts, true);
    assert.equal(readiness.governance?.does_not_promote_capabilities, true);
    assert.equal(
      readiness.routes?.proposal_review_apply_readiness_route,
      "/plugins/capabilities/library/proposal-review/apply-readiness",
    );
    assert.equal(readiness.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(readiness.packs[0]?.blocked_before_review_capability_count, 2);
    assert.equal(readiness.packs[0]?.proposals[0]?.capability, "generated.ops.run");
    assert.deepEqual(readiness.packs[0]?.proposals[0]?.blockers_before_review, ["proposal_evidence"]);
    assert.equal(readiness.packs[0]?.proposals[0]?.proposal_review_would_write_receipt, true);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists operator proposal evidence intake checklist", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.operator_proposal_evidence_intake.checklist",
      stage: "Stage 17 / Capability Economy",
      status: "ready_for_operator_evidence_refs",
      operator_evidence_intake_checklist_ready: true,
      candidate_pack_count: 47,
      candidate_capability_count: 2265,
      evidence_ref_required_count: 2265,
      source_proposal_evidence_plan: {
        status: "blocked",
        candidate_capability_count: 2265,
        proposal_evidence_missing_count: 2265,
        proposal_evidence_ready_count: 0,
        proposal_review_missing_count: 2265,
        next_smallest_truthful_gap: "stage17_capability_library_promotion_readiness",
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          staged_capability_count: 2,
          candidate_capability_count: 2,
          evidence_ref_required_count: 2,
          claim_scope: "operator_supplied_friction_evidence_reference_not_independent_verification",
          capabilities_truncated: false,
          capabilities: [
            {
              capability: "generated.ops.run",
              status: "staged",
              proposal_id: "plugin_proposal_generated_ops_run",
              proposal_review_status: "staged",
              proposal_review_receipt_id: "",
              missing_requirements: ["proposal_evidence", "proposal_review"],
              blockers_before_evidence: [],
              evidence_refs_required: true,
              operator_supplied_evidence_not_independently_verified: true,
              intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
            },
          ],
        },
      ],
      routes: {
        proposal_evidence_plan_route: "/plugins/capabilities/library/proposal-evidence/plan",
        operator_intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
      },
      requirements: {
        operator_evidence_refs_required: true,
        dry_run_required_before_apply: true,
        no_synthetic_evidence: true,
      },
      governance: {
        read_only: true,
        apply_requires_plugins_write_scope: true,
        writes_registry_metadata: false,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const checklist = await client.listCapabilityLibraryOperatorProposalEvidenceIntakeChecklist();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-evidence/operator-intake/checklist"]);
    assert.equal(checklist.status, "ready_for_operator_evidence_refs");
    assert.equal(checklist.operator_evidence_intake_checklist_ready, true);
    assert.equal(checklist.candidate_capability_count, 2265);
    assert.equal(checklist.evidence_ref_required_count, 2265);
    assert.equal(checklist.source_proposal_evidence_plan?.proposal_evidence_missing_count, 2265);
    assert.equal(checklist.requirements?.operator_evidence_refs_required, true);
    assert.equal(checklist.requirements?.dry_run_required_before_apply, true);
    assert.equal(checklist.requirements?.no_synthetic_evidence, true);
    assert.equal(checklist.governance?.read_only, true);
    assert.equal(checklist.governance?.writes_registry_metadata, false);
    assert.equal(checklist.governance?.does_not_promote_capabilities, true);
    assert.equal(checklist.governance?.memory_write, false);
    assert.equal(
      checklist.routes?.operator_intake_apply_route,
      "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
    );
    assert.equal(checklist.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(checklist.packs[0]?.candidate_capability_count, 2);
    assert.equal(checklist.packs[0]?.evidence_ref_required_count, 2);
    assert.equal(
      checklist.packs[0]?.claim_scope,
      "operator_supplied_friction_evidence_reference_not_independent_verification",
    );
    assert.equal(checklist.packs[0]?.capabilities[0]?.capability, "generated.ops.run");
    assert.equal(checklist.packs[0]?.capabilities[0]?.evidence_refs_required, true);
    assert.equal(
      checklist.packs[0]?.capabilities[0]?.operator_supplied_evidence_not_independently_verified,
      true,
    );
    assert.equal(
      checklist.packs[0]?.capabilities[0]?.intake_apply_route,
      "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
    );
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists operator proposal evidence intake worksheet", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.operator_proposal_evidence_intake.worksheet",
      stage: "Stage 17 / Capability Economy",
      status: "ready_for_operator_evidence_collection",
      operator_evidence_intake_worksheet_ready: true,
      worksheet_pack_count: 47,
      worksheet_row_count: 2265,
      evidence_ref_required_count: 2265,
      source_proposal_evidence_plan: {
        status: "blocked",
        candidate_capability_count: 2265,
        proposal_evidence_missing_count: 2265,
        proposal_evidence_ready_count: 0,
        proposal_review_missing_count: 2265,
        next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          staged_capability_count: 2,
          worksheet_row_count: 2,
          evidence_ref_required_count: 2,
          claim_scope: "operator_supplied_friction_evidence_reference_not_independent_verification",
          rows_truncated: false,
          rows: [
            {
              capability: "generated.ops.run",
              status: "staged",
              proposal_id: "plugin_proposal_generated_ops_run",
              proposal_review_status: "staged",
              proposal_review_receipt_id: "",
              missing_requirements: ["proposal_evidence", "proposal_review"],
              blockers_before_evidence: [],
              operator_evidence_refs: [],
              operator_evidence_ref_count: 0,
              operator_evidence_refs_required: true,
              evidence_ref_collection_status: "pending_operator_input",
              claim_scope: "operator_supplied_friction_evidence_reference_not_independent_verification",
              apply_payload_hint: {
                pack_ids: ["legacy.generated.opsplugin"],
                capability_ids: ["generated.ops.run"],
                evidence_refs: [],
                dry_run: true,
              },
              operator_supplied_evidence_not_independently_verified: true,
              requires_future_proposal_review: true,
              intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
            },
          ],
        },
      ],
      routes: {
        operator_intake_worksheet_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/worksheet",
        operator_intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        proposal_review_apply_readiness_route: "/plugins/capabilities/library/proposal-review/apply-readiness",
      },
      requirements: {
        worksheet_contains_blank_evidence_slots: true,
        no_synthetic_evidence: true,
        pack_or_capability_scoped_apply_required: true,
      },
      governance: {
        read_only: true,
        writes_registry_metadata: false,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const worksheet = await client.listCapabilityLibraryOperatorProposalEvidenceIntakeWorksheet();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-evidence/operator-intake/worksheet"]);
    assert.equal(worksheet.status, "ready_for_operator_evidence_collection");
    assert.equal(worksheet.operator_evidence_intake_worksheet_ready, true);
    assert.equal(worksheet.worksheet_row_count, 2265);
    assert.equal(worksheet.evidence_ref_required_count, 2265);
    assert.equal(worksheet.source_proposal_evidence_plan?.proposal_evidence_missing_count, 2265);
    assert.equal(worksheet.requirements?.worksheet_contains_blank_evidence_slots, true);
    assert.equal(worksheet.requirements?.no_synthetic_evidence, true);
    assert.equal(worksheet.governance?.read_only, true);
    assert.equal(worksheet.governance?.writes_registry_metadata, false);
    assert.equal(
      worksheet.routes?.operator_intake_worksheet_route,
      "/plugins/capabilities/library/proposal-evidence/operator-intake/worksheet",
    );
    assert.equal(worksheet.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(worksheet.packs[0]?.worksheet_row_count, 2);
    assert.equal(worksheet.packs[0]?.rows[0]?.capability, "generated.ops.run");
    assert.deepEqual(worksheet.packs[0]?.rows[0]?.operator_evidence_refs, []);
    assert.equal(worksheet.packs[0]?.rows[0]?.evidence_ref_collection_status, "pending_operator_input");
    assert.equal(worksheet.packs[0]?.rows[0]?.operator_evidence_refs_required, true);
    assert.deepEqual(worksheet.packs[0]?.rows[0]?.apply_payload_hint?.capability_ids, ["generated.ops.run"]);
    assert.equal(
      worksheet.packs[0]?.rows[0]?.intake_apply_route,
      "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
    );
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists operator proposal evidence intake export", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.operator_proposal_evidence_intake.export",
      stage: "Stage 17 / Capability Economy",
      status: "ready_for_operator_evidence_export",
      operator_evidence_intake_export_ready: true,
      export_pack_count: 47,
      export_row_count: 2265,
      exported_row_count: 2265,
      evidence_ref_required_count: 2265,
      export_rows_truncated: false,
      row_limit: 5000,
      source_proposal_evidence_plan: {
        status: "blocked",
        candidate_capability_count: 2265,
        proposal_evidence_missing_count: 2265,
        proposal_evidence_ready_count: 0,
        proposal_review_missing_count: 2265,
        next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
      },
      export_schema: {
        format: "json",
        evidence_refs_input_format: "comma_separated_or_json_array",
        columns: ["pack_id", "pack_version", "capability", "proposal_id", "evidence_refs_input"],
        blank_evidence_refs_input_means_not_ready_for_apply: true,
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          staged_capability_count: 2,
          export_row_count: 2,
          exported_row_count: 2,
          evidence_ref_required_count: 2,
          claim_scope: "operator_supplied_friction_evidence_reference_not_independent_verification",
          rows_truncated: false,
          rows: [
            {
              pack_id: "legacy.generated.opsplugin",
              pack_version: "1.0.0",
              pack_name: "Ops Plugin",
              capability: "generated.ops.run",
              status: "staged",
              proposal_id: "plugin_proposal_generated_ops_run",
              proposal_review_status: "staged",
              proposal_review_receipt_id: "",
              missing_requirements: ["proposal_evidence", "proposal_review"],
              blockers_before_evidence: [],
              evidence_refs_input: "",
              evidence_refs_input_format: "comma_separated_or_json_array",
              operator_evidence_refs_required: true,
              evidence_ref_collection_status: "pending_operator_input",
              claim_scope: "operator_supplied_friction_evidence_reference_not_independent_verification",
              dry_run_required: true,
              apply_payload_hint: {
                pack_ids: ["legacy.generated.opsplugin"],
                capability_ids: ["generated.ops.run"],
                evidence_refs: [],
                dry_run: true,
              },
              operator_supplied_evidence_not_independently_verified: true,
              requires_future_proposal_review: true,
              intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
            },
          ],
        },
      ],
      routes: {
        operator_intake_export_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/export",
        operator_intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        proposal_review_apply_readiness_route: "/plugins/capabilities/library/proposal-review/apply-readiness",
      },
      requirements: {
        export_contains_blank_evidence_slots: true,
        no_synthetic_evidence: true,
        import_requires_governed_apply_route: true,
        does_not_validate_evidence_truth: true,
      },
      governance: {
        read_only: true,
        writes_registry_metadata: false,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const exported = await client.listCapabilityLibraryOperatorProposalEvidenceIntakeExport();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-evidence/operator-intake/export"]);
    assert.equal(exported.status, "ready_for_operator_evidence_export");
    assert.equal(exported.operator_evidence_intake_export_ready, true);
    assert.equal(exported.export_row_count, 2265);
    assert.equal(exported.exported_row_count, 2265);
    assert.equal(exported.export_rows_truncated, false);
    assert.equal(exported.source_proposal_evidence_plan?.proposal_evidence_missing_count, 2265);
    assert.equal(exported.requirements?.export_contains_blank_evidence_slots, true);
    assert.equal(exported.requirements?.import_requires_governed_apply_route, true);
    assert.equal(exported.requirements?.does_not_validate_evidence_truth, true);
    assert.equal(exported.governance?.read_only, true);
    assert.equal(exported.governance?.writes_registry_metadata, false);
    assert.equal(
      exported.routes?.operator_intake_export_route,
      "/plugins/capabilities/library/proposal-evidence/operator-intake/export",
    );
    assert.equal(exported.export_schema?.evidence_refs_input_format, "comma_separated_or_json_array");
    assert.equal(exported.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(exported.packs[0]?.exported_row_count, 2);
    assert.equal(exported.packs[0]?.rows[0]?.capability, "generated.ops.run");
    assert.equal(exported.packs[0]?.rows[0]?.evidence_refs_input, "");
    assert.equal(exported.packs[0]?.rows[0]?.evidence_refs_input_format, "comma_separated_or_json_array");
    assert.equal(exported.packs[0]?.rows[0]?.operator_evidence_refs_required, true);
    assert.equal(exported.packs[0]?.rows[0]?.dry_run_required, true);
    assert.deepEqual(exported.packs[0]?.rows[0]?.apply_payload_hint?.capability_ids, ["generated.ops.run"]);
    assert.equal(
      exported.packs[0]?.rows[0]?.intake_apply_route,
      "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
    );
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient previews filled operator proposal evidence export rows", async () => {
  let captured: Record<string, unknown> = {};
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/plugins/capabilities/library/proposal-evidence/operator-intake/import-preview");
    captured = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.operator_proposal_evidence_intake.import_preview",
      stage: "Stage 17 / Capability Economy",
      status: "ready_for_operator_evidence_import_preview",
      operator_evidence_intake_import_preview_ready: true,
      input_row_count: 3,
      processed_row_count: 3,
      ready_row_count: 1,
      pending_row_count: 1,
      invalid_row_count: 1,
      apply_group_count: 1,
      ready_rows: [
        {
          row_index: 0,
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          capability: "generated.ops.run",
          proposal_id: "plugin_proposal_generated_ops_run",
          status: "ready_for_preview",
          evidence_refs: ["operator.case.generated.ops.run"],
          evidence_ref_count: 1,
        },
      ],
      pending_rows: [
        {
          row_index: 1,
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          capability: "generated.ops.wait",
          status: "pending_operator_input",
          error: "evidence_refs_input_required",
        },
      ],
      invalid_rows: [
        {
          row_index: 2,
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          capability: "generated.ops.missing",
          status: "invalid",
          error: "row_not_current_operator_evidence_candidate",
        },
      ],
      apply_payload_groups: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          capability_count: 1,
          evidence_ref_count: 1,
          row_indexes: [0],
          preview_payload: {
            pack_ids: ["legacy.generated.opsplugin"],
            capability_ids: ["generated.ops.run"],
            evidence_refs: ["operator.case.generated.ops.run"],
            dry_run: true,
            max_pack_count: 1,
            max_total_capability_count: 1,
            max_capability_count_per_pack: 1,
          },
          apply_payload_hint: {
            pack_ids: ["legacy.generated.opsplugin"],
            capability_ids: ["generated.ops.run"],
            evidence_refs: ["operator.case.generated.ops.run"],
            dry_run: true,
            dry_run_fingerprint_required: true,
            max_pack_count: 1,
            max_total_capability_count: 1,
            max_capability_count_per_pack: 1,
          },
          preview_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/preview",
          apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
        },
      ],
      source_proposal_evidence_plan: {
        proposal_evidence_missing_count: 2265,
        proposal_evidence_ready_count: 0,
      },
      routes: {
        operator_intake_import_preview_route:
          "/plugins/capabilities/library/proposal-evidence/operator-intake/import-preview",
        operator_intake_preview_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/preview",
        operator_intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
      },
      requirements: {
        no_synthetic_evidence: true,
        does_not_validate_evidence_truth: true,
        dry_run_required_before_apply: true,
      },
      governance: {
        read_only: true,
        preview_only: true,
        write_authority: false,
        writes_registry_metadata: false,
        writes_operator_evidence_metadata: false,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_operator_proposal_evidence_refs",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const preview = await client.previewCapabilityLibraryOperatorProposalEvidenceIntakeImport({
      rows: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          capability: "generated.ops.run",
          evidence_refs_input: "operator.case.generated.ops.run",
        },
      ],
      max_row_count: 10,
      max_apply_group_count: 10,
    });

    assert.equal(captured.actor, "chat_ui.plugins");
    assert.equal((captured.rows as unknown[]).length, 1);
    assert.equal(preview.status, "ready_for_operator_evidence_import_preview");
    assert.equal(preview.operator_evidence_intake_import_preview_ready, true);
    assert.equal(preview.ready_row_count, 1);
    assert.equal(preview.pending_row_count, 1);
    assert.equal(preview.invalid_row_count, 1);
    assert.equal(preview.ready_rows?.[0]?.evidence_refs?.[0], "operator.case.generated.ops.run");
    assert.equal(preview.pending_rows?.[0]?.error, "evidence_refs_input_required");
    assert.equal(preview.invalid_rows?.[0]?.error, "row_not_current_operator_evidence_candidate");
    assert.deepEqual(preview.apply_payload_groups?.[0]?.preview_payload?.capability_ids, ["generated.ops.run"]);
    assert.equal(preview.apply_payload_groups?.[0]?.apply_payload_hint?.dry_run_fingerprint_required, true);
    assert.equal(preview.requirements?.does_not_validate_evidence_truth, true);
    assert.equal(preview.requirements?.no_synthetic_evidence, true);
    assert.equal(preview.governance?.read_only, true);
    assert.equal(preview.governance?.preview_only, true);
    assert.equal(preview.governance?.write_authority, false);
    assert.equal(preview.governance?.writes_operator_evidence_metadata, false);
    assert.equal(preview.governance?.memory_write, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists operator proposal evidence intake audit", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    return jsonResponse({
      ok: true,
      kind: "plugin.capability_library.operator_proposal_evidence_intake.audit",
      stage: "Stage 17 / Capability Economy",
      status: "operator_evidence_refs_recorded",
      operator_evidence_intake_audit_ready: true,
      recorded_pack_count: 1,
      recorded_capability_count: 1,
      evidence_ref_count: 1,
      future_review_required_count: 1,
      source_proposal_evidence_plan: {
        status: "proposal_evidence_complete",
        candidate_capability_count: 1,
        proposal_evidence_missing_count: 0,
        proposal_evidence_ready_count: 1,
        proposal_review_missing_count: 1,
        next_smallest_truthful_gap: "stage17_capability_library_proposal_review_apply",
      },
      packs: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          staged_capability_count: 1,
          recorded_capability_count: 1,
          evidence_ref_count: 1,
          claim_scope: "operator_supplied_friction_evidence_reference_not_independent_verification",
          capabilities_truncated: false,
          capabilities: [
            {
              capability: "generated.ops.run",
              status: "staged",
              proposal_id: "plugin_proposal_generated_ops_run",
              evidence_ref_count: 1,
              evidence_refs: ["operator.case.generated.ops.run"],
              evidence_refs_truncated: false,
              claim_scope: "operator_supplied_friction_evidence_reference_not_independent_verification",
              operator_intake_actor: "chat_ui.plugins",
              operator_intake_reason: "apply operator supplied proposal evidence",
              operator_intake_ts: 1_789_000_000,
              operator_intake_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
              operator_supplied_evidence_not_independently_verified: true,
              requires_future_proposal_review: true,
              writes_proposals: false,
              approval_claimed: false,
            },
          ],
        },
      ],
      routes: {
        operator_intake_checklist_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/checklist",
        operator_intake_audit_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/audit",
        operator_intake_apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
      },
      requirements: {
        audit_only: true,
        no_synthetic_evidence: true,
        does_not_validate_evidence_truth: true,
      },
      governance: {
        read_only: true,
        writes_registry_metadata: false,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
      next_smallest_truthful_gap: "stage17_capability_library_proposal_review_apply",
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const audit = await client.listCapabilityLibraryOperatorProposalEvidenceIntakeAudit();

    assert.deepEqual(requests, ["/plugins/capabilities/library/proposal-evidence/operator-intake/audit"]);
    assert.equal(audit.status, "operator_evidence_refs_recorded");
    assert.equal(audit.operator_evidence_intake_audit_ready, true);
    assert.equal(audit.recorded_pack_count, 1);
    assert.equal(audit.recorded_capability_count, 1);
    assert.equal(audit.evidence_ref_count, 1);
    assert.equal(audit.future_review_required_count, 1);
    assert.equal(audit.source_proposal_evidence_plan?.proposal_evidence_missing_count, 0);
    assert.equal(audit.source_proposal_evidence_plan?.proposal_evidence_ready_count, 1);
    assert.equal(audit.source_proposal_evidence_plan?.proposal_review_missing_count, 1);
    assert.equal(audit.requirements?.audit_only, true);
    assert.equal(audit.requirements?.no_synthetic_evidence, true);
    assert.equal(audit.requirements?.does_not_validate_evidence_truth, true);
    assert.equal(audit.governance?.read_only, true);
    assert.equal(audit.governance?.writes_registry_metadata, false);
    assert.equal(audit.governance?.does_not_promote_capabilities, true);
    assert.equal(
      audit.routes?.operator_intake_audit_route,
      "/plugins/capabilities/library/proposal-evidence/operator-intake/audit",
    );
    assert.equal(audit.packs[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(audit.packs[0]?.recorded_capability_count, 1);
    assert.equal(audit.packs[0]?.evidence_ref_count, 1);
    assert.equal(audit.packs[0]?.capabilities[0]?.capability, "generated.ops.run");
    assert.deepEqual(audit.packs[0]?.capabilities[0]?.evidence_refs, ["operator.case.generated.ops.run"]);
    assert.equal(
      audit.packs[0]?.capabilities[0]?.claim_scope,
      "operator_supplied_friction_evidence_reference_not_independent_verification",
    );
    assert.equal(audit.packs[0]?.capabilities[0]?.requires_future_proposal_review, true);
    assert.equal(audit.packs[0]?.capabilities[0]?.writes_proposals, false);
    assert.equal(audit.packs[0]?.capabilities[0]?.approval_claimed, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient previews operator proposal evidence intake without apply route", async () => {
  let captured: Record<string, unknown> = {};
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/plugins/capabilities/library/proposal-evidence/operator-intake/preview");
    captured = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({
      ok: true,
      applied: false,
      kind: "plugin.capability_library.operator_proposal_evidence_intake.preview",
      status: "preview",
      dry_run: true,
      planned_pack_count: 1,
      planned_capability_count: 1,
      evidence_ref_count: 1,
      dry_run_fingerprint: "preview123fingerprint",
      dry_run_confirmation: {
        required_for_apply: true,
        fingerprint: "preview123fingerprint",
        fingerprint_contract: "stage17_operator_proposal_evidence_intake_dry_run_v1",
        preview_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/preview",
        apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
      },
      planned: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          capability_count: 1,
          evidence_ref_count: 1,
          writes_registry_metadata: false,
          writes_proposals: false,
          capabilities: [
            {
              capability: "generated.ops.run",
              proposal_id: "plugin_proposal_generated_ops_run",
            },
          ],
        },
      ],
      governance: {
        read_only: true,
        preview_only: true,
        write_authority: false,
        writes_registry_metadata: false,
        writes_operator_evidence_metadata: false,
        apply_requires_plugins_write_scope: true,
        dry_run_fingerprint_does_not_authorize_without_plugins_write: true,
        memory_write: false,
      },
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const preview = await client.previewCapabilityLibraryOperatorProposalEvidenceIntake({
      pack_ids: ["legacy.generated.opsplugin"],
      capability_ids: ["generated.ops.run"],
      evidence_refs: ["operator.case.generated.ops.run.repeat"],
      dry_run: false,
      dry_run_fingerprint: "ignored-by-preview",
      max_pack_count: 1,
    });

    assert.equal(captured.actor, "chat_ui.plugins");
    assert.equal(captured.dry_run, true);
    assert.equal(captured.dry_run_fingerprint, undefined);
    assert.deepEqual(captured.pack_ids, ["legacy.generated.opsplugin"]);
    assert.deepEqual(captured.capability_ids, ["generated.ops.run"]);
    assert.deepEqual(captured.evidence_refs, ["operator.case.generated.ops.run.repeat"]);
    assert.equal(preview.status, "preview");
    assert.equal(preview.dry_run, true);
    assert.equal(preview.applied, false);
    assert.equal(preview.dry_run_fingerprint, "preview123fingerprint");
    assert.equal(preview.dry_run_confirmation?.required_for_apply, true);
    assert.equal(preview.planned?.[0]?.writes_registry_metadata, false);
    assert.equal(preview.planned?.[0]?.writes_proposals, false);
    assert.equal(preview.governance?.read_only, true);
    assert.equal(preview.governance?.preview_only, true);
    assert.equal(preview.governance?.write_authority, false);
    assert.equal(preview.governance?.writes_operator_evidence_metadata, false);
    assert.equal(preview.governance?.apply_requires_plugins_write_scope, true);
    assert.equal(preview.governance?.dry_run_fingerprint_does_not_authorize_without_plugins_write, true);
    assert.equal(preview.governance?.memory_write, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient dry-runs operator proposal evidence intake with selected pack scope", async () => {
  let captured: Record<string, unknown> = {};
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/plugins/capabilities/library/proposal-evidence/operator-intake/apply");
    captured = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({
      ok: true,
      applied: false,
      kind: "plugin.capability_library.operator_proposal_evidence_intake.apply",
      status: "dry_run",
      planned_pack_count: 1,
      planned_capability_count: 2,
      evidence_ref_count: 1,
      dry_run_fingerprint: "abc123dryrunfingerprint",
      dry_run_confirmation: {
        required_for_apply: true,
        fingerprint: "abc123dryrunfingerprint",
        fingerprint_contract: "stage17_operator_proposal_evidence_intake_dry_run_v1",
        planned_pack_count: 1,
        planned_capability_count: 2,
        evidence_ref_count: 1,
        apply_route: "/plugins/capabilities/library/proposal-evidence/operator-intake/apply",
      },
      planned: [
        {
          pack_id: "legacy.generated.opsplugin",
          pack_version: "1.0.0",
          pack_name: "Ops Plugin",
          capability_count: 2,
          evidence_ref_count: 1,
          claim_scope: "operator_supplied_friction_evidence_reference_not_independent_verification",
          capabilities: [
            {
              capability: "generated.ops.run",
              proposal_id: "plugin_proposal_generated_ops_run",
              missing_requirements: ["proposal_evidence"],
            },
          ],
          writes_registry_metadata: false,
          writes_proposals: false,
          approves_proposals: false,
          promotes_capabilities: false,
          enables_capabilities: false,
        },
      ],
      skipped: [],
      before: {
        proposal_evidence_missing_count: 2265,
        proposal_evidence_ready_count: 0,
      },
      governance: {
        writes_registry_metadata: false,
        writes_proposals: false,
        dry_run_required_before_apply: true,
        operator_supplied_evidence_not_independently_verified: true,
        does_not_approve_proposals: true,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const intake = await client.applyCapabilityLibraryOperatorProposalEvidenceIntake({
      pack_ids: ["legacy.generated.opsplugin"],
      capability_ids: ["generated.ops.run"],
      evidence_refs: ["operator.case.generated.ops.run.repeat"],
      max_pack_count: 1,
      max_total_capability_count: 2,
      max_capability_count_per_pack: 2,
    });

    assert.equal(captured.actor, "chat_ui.plugins");
    assert.equal(captured.dry_run, true);
    assert.deepEqual(captured.pack_ids, ["legacy.generated.opsplugin"]);
    assert.deepEqual(captured.capability_ids, ["generated.ops.run"]);
    assert.deepEqual(captured.evidence_refs, ["operator.case.generated.ops.run.repeat"]);
    assert.equal(captured.max_pack_count, 1);
    assert.equal(intake.status, "dry_run");
    assert.equal(intake.planned_pack_count, 1);
    assert.equal(intake.planned_capability_count, 2);
    assert.equal(intake.evidence_ref_count, 1);
    assert.equal(intake.dry_run_fingerprint, "abc123dryrunfingerprint");
    assert.equal(intake.dry_run_confirmation?.required_for_apply, true);
    assert.equal(intake.dry_run_confirmation?.fingerprint, "abc123dryrunfingerprint");
    assert.equal(intake.before?.proposal_evidence_missing_count, 2265);
    assert.equal(intake.planned?.[0]?.pack_id, "legacy.generated.opsplugin");
    assert.equal(intake.planned?.[0]?.capabilities?.[0]?.capability, "generated.ops.run");
    assert.equal(intake.planned?.[0]?.writes_registry_metadata, false);
    assert.equal(intake.planned?.[0]?.writes_proposals, false);
    assert.equal(intake.planned?.[0]?.approves_proposals, false);
    assert.equal(intake.planned?.[0]?.promotes_capabilities, false);
    assert.equal(intake.governance?.writes_registry_metadata, false);
    assert.equal(intake.governance?.dry_run_required_before_apply, true);
    assert.equal(intake.governance?.operator_supplied_evidence_not_independently_verified, true);
    assert.equal(intake.governance?.does_not_approve_proposals, true);
    assert.equal(intake.governance?.does_not_promote_capabilities, true);
    assert.equal(intake.governance?.memory_write, false);

    await client.applyCapabilityLibraryOperatorProposalEvidenceIntake({
      pack_ids: ["legacy.generated.opsplugin"],
      capability_ids: ["generated.ops.run"],
      evidence_refs: ["operator.case.generated.ops.run.repeat"],
      max_pack_count: 1,
      max_total_capability_count: 2,
      max_capability_count_per_pack: 2,
      dry_run: false,
      dry_run_fingerprint: "abc123dryrunfingerprint",
    });

    assert.equal(captured.dry_run, false);
    assert.equal(captured.dry_run_fingerprint, "abc123dryrunfingerprint");
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient writes capability pack operator review decision receipts", async () => {
  let captured: Record<string, unknown> = {};
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/plugins/capabilities/packs/operator/review/decisions");
    captured = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({
      ok: true,
      applied: true,
      status: "approved",
      pack_id: "ops.review",
      pack_version: "1.0.0",
      receipt_id: "capability_pack_operator_review_1710000000_ops_review",
      receipt_path: "data/artifacts/plugins/capability_packs/operator_review_decisions/receipt.json",
      receipt: {
        receipt_id: "capability_pack_operator_review_1710000000_ops_review",
        status: "approved",
        decision: "approve",
        pack_id: "ops.review",
        pack_version: "1.0.0",
        capability_ids: ["generated.review"],
        governance: {
          writes_receipt: true,
          does_not_promote_capabilities: true,
          promotion_authority: false,
          execution_authority: false,
        },
      },
      pack: {
        pack_id: "ops.review",
        pack_version: "1.0.0",
        status: "ready_for_operator_review",
        decision_required: true,
      },
      governance: {
        gate: "capability_pack_operator_review",
        promotion_authority: false,
        execution_authority: false,
      },
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const res = await client.decideCapabilityPackOperatorReview({
      pack_id: "ops.review",
      pack_version: "1.0.0",
      action: "approve",
      reason: "operator reviewed pack",
      notes: "bounded receipt only",
      capability_ids: ["generated.review"],
    });

    assert.equal(captured.pack_id, "ops.review");
    assert.equal(captured.pack_version, "1.0.0");
    assert.equal(captured.action, "approve");
    assert.equal(captured.actor, "chat_ui.plugins");
    assert.equal(captured.reason, "operator reviewed pack");
    assert.deepEqual(captured.capability_ids, ["generated.review"]);
    assert.equal(res.ok, true);
    assert.equal(res.applied, true);
    assert.equal(res.receipt_id, "capability_pack_operator_review_1710000000_ops_review");
    assert.equal(res.receipt?.status, "approved");
    assert.equal(res.receipt?.governance?.promotion_authority, false);
    assert.equal(res.pack?.decision_required, true);
    assert.equal(res.governance?.execution_authority, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient dry-runs and applies bulk capability pack operator review decisions", async () => {
  const requests: string[] = [];
  const captured: Record<string, unknown>[] = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push(parsed.pathname);
    assert.equal(parsed.pathname, "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface");
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    captured.push(body);
    if (body.dry_run === false) {
      return jsonResponse({
        ok: true,
        applied: true,
        kind: "plugin.capability_pack.operator_review.bulk_decision",
        status: "recorded",
        dry_run: false,
        batch_id: "capability_pack_operator_review_batch_1",
        planned_pack_count: 2,
        planned_capability_count: 4,
        recorded_pack_count: 2,
        recorded_capability_count: 4,
        recorded: [
          {
            pack_id: "ops.review.a",
            pack_version: "1.0.0",
            receipt_id: "receipt-a",
            receipt_path: "operator_review_decisions/receipt-a.json",
            capability_count: 2,
            status: "approved",
          },
        ],
        promotion_discipline: {
          ready_pack_count: 2,
          blocked_pack_count: 0,
        },
        governance: {
          writes_receipts: true,
          does_not_promote_capabilities: true,
          memory_write: false,
        },
      });
    }
    return jsonResponse({
      ok: true,
      applied: false,
      kind: "plugin.capability_pack.operator_review.bulk_decision",
      status: "dry_run",
      dry_run: true,
      planned_pack_count: 2,
      planned_capability_count: 4,
      planned: [
        {
          pack_id: "ops.review.a",
          pack_version: "1.0.0",
          pack_name: "Ops Review A",
          action: "approve",
          decision_status: "approved",
          capability_count: 2,
          staged_capability_count: 2,
          quality_evidence_ready: true,
          proposal_lineage_ready: true,
          validation_receipts_ready: true,
          operator_review_rule_declared: true,
          operator_review_governance_declared: true,
          writes_receipt: false,
        },
      ],
      before: {
        review_queue_count: 2,
        decision_recorded_pack_count: 0,
      },
      governance: {
        dry_run_default: true,
        writes_receipts: false,
        does_not_promote_capabilities: true,
        memory_write: false,
      },
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const dryRun = await client.decideCapabilityPackOperatorReviewBulkFromSurface({
      action: "approve",
      reason: "operator bulk review dry-run",
      pack_ids: ["ops.review.a", "ops.review.b"],
      max_pack_count: 2,
      max_total_capability_count: 4,
    });
    const applied = await client.decideCapabilityPackOperatorReviewBulkFromSurface({
      action: "approve",
      reason: "operator bulk review apply",
      pack_ids: ["ops.review.a", "ops.review.b"],
      max_pack_count: 2,
      max_total_capability_count: 4,
      dry_run: false,
    });

    assert.deepEqual(requests, [
      "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
      "/plugins/capabilities/packs/operator/review/decisions/bulk-from-surface",
    ]);
    assert.equal(captured[0]?.actor, "chat_ui.plugins");
    assert.equal(captured[0]?.dry_run, true);
    assert.deepEqual(captured[0]?.pack_ids, ["ops.review.a", "ops.review.b"]);
    assert.equal(captured[1]?.dry_run, false);
    assert.equal(dryRun.applied, false);
    assert.equal(dryRun.status, "dry_run");
    assert.equal(dryRun.planned_pack_count, 2);
    assert.equal(dryRun.planned?.[0]?.pack_id, "ops.review.a");
    assert.equal(dryRun.planned?.[0]?.writes_receipt, false);
    assert.equal(dryRun.governance?.writes_receipts, false);
    assert.equal(applied.applied, true);
    assert.equal(applied.recorded_pack_count, 2);
    assert.equal(applied.recorded?.[0]?.receipt_id, "receipt-a");
    assert.equal(applied.promotion_discipline?.blocked_pack_count, 0);
    assert.equal(applied.governance?.memory_write, false);
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient lists Forge capability catalog readback", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push(`${parsed.pathname}${parsed.search}`);
    return jsonResponse({
      ok: true,
      total: 1,
      offset: 0,
      limit: 5,
      filters: {
        status: "staged",
        risk_tier: "normal",
        source: "",
      },
      items: [
        {
          capability: "pl_stage",
          version: "0.1.0",
          status: "staged",
          risk_tier: "normal",
          source: "generated",
          proposal_id: "proposal_pl_stage_1",
          quality: {
            tests: ["tests/test_api_plugins.py::test_plugins_capability_catalog_readback"],
            docs: ["README.md"],
          },
          metadata: {
            plugin_name: "Stage Helper",
            validation_receipt_id: "plugin_validation_pl_stage_1",
            proposal_evidence: ["mission.forge.catalog"],
          },
        },
      ],
      summary: {
        total: 1,
        status_counts: {
          staged: 1,
        },
        risk_tier_counts: {
          normal: 1,
        },
        source_counts: {
          generated: 1,
        },
        tested_count: 1,
        documented_count: 1,
      },
      coherence: {
        total: 1,
        duplicate_capabilities: [],
        duplicate_proposals: [],
        lineage_gaps: [],
        validation_lineage_gaps: [],
        quality_gaps: [],
      },
      catalog: {
        total_plugins: 1,
        total_tools: 1,
        path: "D:/Francis/data/plugins/catalog.json",
      },
    });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    const res = await client.listCapabilityCatalog({ status: "staged", risk_tier: "normal", limit: 5 });

    assert.deepEqual(requests, ["/plugins/capabilities/catalog?limit=5&status=staged&risk_tier=normal"]);
    assert.equal(res.total, 1);
    assert.equal(res.limit, 5);
    assert.equal(res.items[0]?.capability, "pl_stage");
    assert.equal(res.items[0]?.status, "staged");
    assert.equal(res.items[0]?.source, "generated");
    assert.equal(res.items[0]?.proposal_id, "proposal_pl_stage_1");
    assert.deepEqual(res.items[0]?.quality?.docs, ["README.md"]);
    assert.equal(res.items[0]?.metadata?.plugin_name, "Stage Helper");
    assert.equal(res.items[0]?.metadata?.validation_receipt_id, "plugin_validation_pl_stage_1");
    assert.equal(res.summary?.tested_count, 1);
    assert.equal(res.summary?.status_counts?.staged, 1);
    assert.equal(res.coherence?.validation_lineage_gaps?.length, 0);
    assert.equal(res.catalog?.total_plugins, 1);
    assert.equal(res.filters?.status, "staged");
  } finally {
    restoreFetch();
  }
});
