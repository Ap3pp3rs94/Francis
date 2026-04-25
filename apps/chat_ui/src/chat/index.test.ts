import assert from "node:assert/strict";
import test from "node:test";

import { parseChatEvent, parseChatSendResponse } from "./index.ts";

test("parseChatSendResponse preserves mission ingress metadata for the chat surface", () => {
  const result = parseChatSendResponse({
    ok: true,
    mode: "mission_ingress",
    status: "queued",
    reply: "Mission msn_chat declared. Next: link_operation.",
    mission_id: "msn_chat",
    mission: { id: "msn_chat", status: "queued" },
    queue_item: { recommended_action: "create_first_operation" },
    loop_state: {
      active_stage: "plan",
      handoff: { action: "link_operation", next_step: "Link an operation and advance the mission state." },
      interface: { status: "available" },
    },
    current_task: {
      source: "mission_handoff",
      handoff_action: "link_operation",
      next_step: "Link an operation and advance the mission state.",
    },
  });

  assert.equal(result.error, undefined);
  assert.equal(result.message?.role, "assistant");
  assert.equal(result.message?.content, "Mission msn_chat declared. Next: link_operation.");

  const meta = result.message?.meta as Record<string, unknown>;
  assert.equal(meta.mode, "mission_ingress");
  assert.equal(meta.status, "queued");
  assert.equal(meta.mission_id, "msn_chat");

  const loopState = meta.loop_state as Record<string, unknown>;
  assert.equal(loopState.active_stage, "plan");
  assert.deepEqual(loopState.interface, { status: "available" });

  const currentTask = meta.current_task as Record<string, unknown>;
  assert.equal(currentTask.source, "mission_handoff");
  assert.equal(currentTask.handoff_action, "link_operation");
});

test("parseChatEvent preserves websocket mission ingress metadata", () => {
  const event = parseChatEvent(
    JSON.stringify({
      type: "message",
      message: {
        role: "assistant",
        content: "Mission msn_ws declared. Next: link_operation.",
        meta: {
          ok: true,
          mode: "mission_ingress",
          status: "queued",
          mission_id: "msn_ws",
          loop_state: { active_stage: "plan", interface: { status: "available" } },
        },
      },
    }),
  );

  assert.equal(event.type, "message");
  assert.equal(event.message?.role, "assistant");
  assert.equal(event.message?.content, "Mission msn_ws declared. Next: link_operation.");
  assert.equal(event.message?.meta?.mode, "mission_ingress");
  assert.equal(event.message?.meta?.mission_id, "msn_ws");
});
