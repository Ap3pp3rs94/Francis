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
    await client.reload();

    assert.equal(captured["/plugins/enable"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/disable"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/install"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/uninstall"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/reload"]?.actor, "chat_ui.plugins");
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
    assert.equal(reviews.items[0]?.receipt_id, "review_1");
    assert.equal(reviews.items[0]?.decision, "approve");
    assert.equal(reviews.items[0]?.previous_status, "staged");
  } finally {
    restoreFetch();
  }
});
