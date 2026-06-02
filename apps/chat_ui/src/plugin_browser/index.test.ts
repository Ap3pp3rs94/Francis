import assert from "node:assert/strict";
import test from "node:test";

import { PluginBrowserApiError, PluginBrowserClient } from "./index.ts";

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
