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
    orb_semantic_state: {
      ok: true,
      status: "blocked",
      semantic_state: "blocked",
      source: "francis.operator_mode.backlog_and_mission_continuity",
      truth_source: "mission_operation_readback",
      render_state: "handback",
      activity_intensity: { level: "handoff" },
      semantic_operator_state: {
        state: "blocked",
        counts: { blocked_missions: 1 },
        focus: { mission_id: "msn_blocked", operation_id: "tsk_blocked" },
      },
      operator_input: {
        feedback_state: "complete",
        virtual_pointer: {
          available: true,
          pointer_id: "francis.orb.primary_virtual_pointer",
          x: "101",
          y: 202,
          controls_user_os_cursor: false,
          user_mouse_taken: false,
        },
      },
      read_only: true,
      private_ui_state: false,
      visual_change: false,
      governance: { read_only: true, grants_execution_authority: false },
    },
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
    optional_readbacks: {
      "francis.policy.receipts": {
        authority: "policy_receipt_readback",
        data: {
          receipt_count: "2",
          returned_count: "1",
          items: [
            {
              receipt_id: "tool-call-policy-alpha",
              decision: "blocked",
              policy_id: "policy.shell.destructive_command.block",
              risk_class: "destructive_shell",
              tool_name: "francis.command.propose",
              requested_authority: "manual_approval_required",
              grants_execution_authority: false,
              grants_mutation_authority: false,
              remote_egress: false,
            },
          ],
        },
        error: "",
        label: "Tool policy receipts",
        ok: true,
        safe_readback: true,
        status: "ready",
        tool: "francis.policy.receipts",
      },
    },
  });

  assert.equal(status.ok, true);
  assert.equal(status.status, "ready");
  assert.equal(status.embodied_posture, "takeover_ready");
  assert.equal(status.resident, false);
  assert.equal(status.orb_semantic_state.semantic_state, "blocked");
  assert.equal(status.orb_semantic_state.source, "francis.operator_mode.backlog_and_mission_continuity");
  assert.equal(status.orb_semantic_state.truth_source, "mission_operation_readback");
  assert.equal(status.orb_semantic_state.render_state, "handback");
  assert.deepEqual(status.orb_semantic_state.activity_intensity, { level: "handoff" });
  assert.equal(status.orb_semantic_state.semantic_operator_state["state"], "blocked");
  assert.deepEqual(status.orb_semantic_state.semantic_operator_state["counts"], { blocked_missions: 1 });
  assert.equal(status.orb_semantic_state.operator_input["feedback_state"], "complete");
  assert.deepEqual(
    (status.orb_semantic_state.operator_input["virtual_pointer"] as Record<string, unknown>)["controls_user_os_cursor"],
    false,
  );
  assert.equal(status.orb_semantic_state.read_only, true);
  assert.equal(status.orb_semantic_state.private_ui_state, false);
  assert.equal(status.orb_semantic_state.visual_change, false);
  assert.equal(status.orb_semantic_state.governance["grants_execution_authority"], false);
  assert.equal(status.mcp.expected_tool_count, 18);
  assert.equal(status.mcp.tool_count, 18);
  assert.deepEqual(status.mcp.missing_tools, []);
  assert.deepEqual(status.mcp.missing_required_tools, []);
  assert.equal(status.routes.mcp_status, "/lens/mcp/status");
  assert.equal(status.components["francis.screen.status"]?.safe_readback, true);
  const policyReadback = status.optional_readbacks["francis.policy.receipts"];
  assert.equal(policyReadback?.status, "ready");
  assert.equal(policyReadback?.data["receipt_count"], "2");
  const items = policyReadback?.data["items"] as Array<Record<string, unknown>>;
  assert.equal(items[0]?.["decision"], "blocked");
  assert.equal(items[0]?.["grants_execution_authority"], false);
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

test("fetchLensMcpStatus aborts a slow Lens readback when timeout is configured", async () => {
  const restore = installFetch((_url, init) => {
    const signal = init?.signal;
    return new Promise<Response>((_resolve, reject) => {
      signal?.addEventListener(
        "abort",
        () => reject(new DOMException("The operation was aborted.", "AbortError")),
        { once: true },
      );
    });
  });

  try {
    await assert.rejects(
      () => fetchLensMcpStatus({ timeoutMs: 1 }),
      (err: unknown) => err instanceof DOMException && err.name === "AbortError",
    );
  } finally {
    restore();
  }
});
