import assert from "node:assert/strict";
import test from "node:test";

import { parseChatEvent, parseChatSendResponse } from "./index.ts";

test("parseChatSendResponse preserves mission ingress metadata for the chat surface", () => {
  const result = parseChatSendResponse({
    ok: true,
    mode: "mission_ingress",
    status: "queued",
    reply: "Mission msn_chat declared. First operation tsk_chat queued. Next: run_linked_operation.",
    mission_id: "msn_chat",
    operation_id: "tsk_chat",
    operation: { id: "tsk_chat", name: "plan.create", status: "queued" },
    advance: { ok: true, applied: true, action: "create_first_operation", operation_id: "tsk_chat" },
    mission: { id: "msn_chat", status: "queued", linked_task_ids: ["tsk_chat"] },
    queue_item: { recommended_action: "run_linked_operation", action_target_id: "tsk_chat" },
    loop_state: {
      active_stage: "execute",
      handoff: { action: "run_linked_operation", operation_id: "tsk_chat", next_step: "Run linked operation." },
      interface: { status: "available", operation_id: "tsk_chat" },
    },
    current_task: {
      source: "mission_meta",
      operation_id: "tsk_chat",
      handoff_action: "run_linked_operation",
      next_step: "Run linked operation.",
    },
  });

  assert.equal(result.error, undefined);
  assert.equal(result.message?.role, "assistant");
  assert.equal(result.message?.content, "Mission msn_chat declared. First operation tsk_chat queued. Next: run_linked_operation.");

  const meta = result.message?.meta as Record<string, unknown>;
  assert.equal(meta.mode, "mission_ingress");
  assert.equal(meta.status, "queued");
  assert.equal(meta.mission_id, "msn_chat");
  assert.equal(meta.operation_id, "tsk_chat");

  const advance = meta.advance as Record<string, unknown>;
  assert.equal(advance.action, "create_first_operation");
  assert.equal(advance.operation_id, "tsk_chat");

  const loopState = meta.loop_state as Record<string, unknown>;
  assert.equal(loopState.active_stage, "execute");
  assert.deepEqual(loopState.interface, { status: "available", operation_id: "tsk_chat" });

  const currentTask = meta.current_task as Record<string, unknown>;
  assert.equal(currentTask.source, "mission_meta");
  assert.equal(currentTask.operation_id, "tsk_chat");
  assert.equal(currentTask.handoff_action, "run_linked_operation");
});

test("parseChatEvent preserves websocket mission ingress metadata", () => {
  const event = parseChatEvent(
    JSON.stringify({
      type: "message",
      message: {
        role: "assistant",
        content: "Mission msn_ws declared. First operation tsk_ws queued. Next: run_linked_operation.",
        meta: {
          ok: true,
          mode: "mission_ingress",
          status: "queued",
          mission_id: "msn_ws",
          operation_id: "tsk_ws",
          advance: { action: "create_first_operation", operation_id: "tsk_ws" },
          loop_state: { active_stage: "execute", interface: { status: "available", operation_id: "tsk_ws" } },
        },
      },
    }),
  );

  assert.equal(event.type, "message");
  assert.equal(event.message?.role, "assistant");
  assert.equal(event.message?.content, "Mission msn_ws declared. First operation tsk_ws queued. Next: run_linked_operation.");
  assert.equal(event.message?.meta?.mode, "mission_ingress");
  assert.equal(event.message?.meta?.mission_id, "msn_ws");
  assert.equal(event.message?.meta?.operation_id, "tsk_ws");
});
