import assert from "node:assert/strict";
import test from "node:test";

import { fetchLensMcpStatus, parseLensMcpStatus } from "./mcpStatus.ts";

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

test("parseLensMcpStatus preserves truthful Orb/Lens body state", () => {
  const status = parseLensMcpStatus({
    ok: true,
    kind: "francis.lens_orb.mcp_status_bridge",
    status: "ready",
    embodied_posture: "takeover_ready",
    resident: false,
    blockers: [],
    mcp: {
      expected_tool_count: 18,
      tool_count: "18",
      missing_tools: [],
      missing_required_tools: [],
    },
    routes: {
      mcp_status: "/lens/mcp/status",
      orb_mcp_status: "/lens/orb/mcp-status",
    },
    governance: {
      read_only: true,
      grants_execution_authority: false,
      grants_mutation_authority: false,
    },
    components: {
      "francis.screen.status": {
        authority: "screen_readback",
        data: { status: "ready" },
        error: "",
        label: "Screen readback",
        ok: true,
        safe_readback: true,
        status: "ready",
        tool: "francis.screen.status",
      },
    },
  });

  assert.equal(status.ok, true);
  assert.equal(status.status, "ready");
  assert.equal(status.embodied_posture, "takeover_ready");
  assert.equal(status.resident, false);
  assert.equal(status.mcp.expected_tool_count, 18);
  assert.equal(status.mcp.tool_count, 18);
  assert.deepEqual(status.mcp.missing_tools, []);
  assert.deepEqual(status.mcp.missing_required_tools, []);
  assert.equal(status.routes.mcp_status, "/lens/mcp/status");
  assert.equal(status.components["francis.screen.status"]?.safe_readback, true);
  assert.equal(status.governance["grants_execution_authority"], false);
});

test("parseLensMcpStatus aliases expected minimum tool count for UI compatibility", () => {
  const status = parseLensMcpStatus({
    mcp: {
      expected_min_tool_count: "18",
      tool_count: 18,
      missing_tools: [],
    },
  });

  assert.equal(status.mcp.expected_tool_count, 18);
});

test("parseLensMcpStatus aliases missing tool fields for UI compatibility", () => {
  const status = parseLensMcpStatus({
    mcp: {
      tool_count: 17,
      missing_required_tools: ["francis.input.status"],
    },
  });

  assert.deepEqual(status.mcp.missing_tools, ["francis.input.status"]);
  assert.deepEqual(status.mcp.missing_required_tools, ["francis.input.status"]);
});

test("fetchLensMcpStatus calls the existing Lens MCP status route read-only", async () => {
  const requests: Array<{ path: string; method: string; actor: string | null }> = [];
  const restore = installFetch((url, init) => {
    const parsed = new URL(url, "http://127.0.0.1:5173");
    requests.push({
      path: parsed.pathname,
      method: init?.method ?? "GET",
      actor: parsed.searchParams.get("actor"),
    });
    return jsonResponse({
      ok: true,
      status: "ready",
      embodied_posture: "takeover_ready",
      resident: false,
      blockers: [],
      mcp: { expected_min_tool_count: 18, tool_count: 18, missing_tools: [], missing_required_tools: [] },
      routes: { mcp_status: "/lens/mcp/status", orb_mcp_status: "/lens/orb/mcp-status" },
      governance: { read_only: true, grants_execution_authority: false },
      components: {},
    });
  });

  try {
    const status = await fetchLensMcpStatus({ actor: "operator.ui" });
    assert.equal(status.status, "ready");
    assert.equal(status.embodied_posture, "takeover_ready");
    assert.equal(status.mcp.expected_tool_count, 18);
    assert.deepEqual(requests, [{ path: "/lens/mcp/status", method: "GET", actor: "operator.ui" }]);
  } finally {
    restore();
  }
});
