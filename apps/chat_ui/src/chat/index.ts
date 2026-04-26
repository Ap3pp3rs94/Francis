/**
 * Chat module (UI).
 *
 * Framework-agnostic chat transport + protocol layer.
 *
 * Responsibilities:
 *  - Define chat message/event types
 *  - Normalize inbound/outbound WebSocket payloads
 *  - Provide a defensive ChatClient abstraction
 *
 * Non-goals:
 *  - No React imports
 *  - No DOM manipulation
 *  - No UI state
 */

export type ChatRole = "user" | "assistant" | "system" | "tool" | string;

export type ChatMessage = {
  role: ChatRole;
  content: string;
  ts?: number; // unix seconds (preferred) or ms (accepted)
  meta?: Record<string, unknown>;
};

export type ChatEventType =
  | "message"
  | "error"
  | "status"
  | "tool_call"
  | "tool_result"
  | string;

export type ChatEvent = {
  type: ChatEventType;
  message?: ChatMessage;
  error?: string;
  status?: string;
  meta?: Record<string, unknown>;
};

export type ChatSendResult = {
  message?: ChatMessage;
  error?: string;
  meta?: Record<string, unknown>;
};

export class ChatProtocolError extends Error {
  readonly raw?: unknown;

  constructor(message: string, raw?: unknown) {
    super(message);
    this.name = "ChatProtocolError";
    this.raw = raw;
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function normalizeTimestamp(ts?: unknown): number | undefined {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return undefined;
  // Heuristic: seconds vs ms
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : ts;
}

const CHAT_SEND_META_KEYS = [
  "ok",
  "mode",
  "status",
  "error",
  "mission_id",
  "mission",
  "operation_id",
  "operation",
  "advance",
  "queue_item",
  "loop_state",
  "current_task",
  "receipt_summary",
] as const;

function chatResponseMeta(raw: Record<string, unknown>): Record<string, unknown> | undefined {
  const meta: Record<string, unknown> = {};
  for (const key of CHAT_SEND_META_KEYS) {
    if (raw[key] !== undefined) meta[key] = raw[key];
  }
  return Object.keys(meta).length > 0 ? meta : undefined;
}

/**
 * Parse the HTTP /chat/send response into the same message shape used by
 * WebSocket chat events, preserving only backend-returned metadata.
 */
export function parseChatSendResponse(raw: unknown): ChatSendResult {
  if (!isRecord(raw)) {
    return { error: "Invalid chat response" };
  }

  const result: ChatSendResult = {};
  const reply = safeString(raw.reply).trim();
  const error = safeString(raw.error).trim();
  const meta = chatResponseMeta(raw);
  if (error) result.error = error;
  if (meta) result.meta = meta;

  if (reply) {
    const message: ChatMessage = { role: "assistant", content: reply };
    if (meta) message.meta = meta;
    result.message = message;
  }

  return result;
}

/**
 * Parse an inbound WebSocket payload into a ChatEvent.
 *
 * Accepts:
 *  - Plain text → assistant message
 *  - JSON string → structured ChatEvent
 *  - Object → structured ChatEvent
 */
export function parseChatEvent(raw: unknown): ChatEvent {
  // Plain text payload (most basic WS servers)
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return parseChatEvent(parsed);
    } catch {
      return {
        type: "message",
        message: { role: "assistant", content: raw },
      };
    }
  }

  if (!isRecord(raw)) {
    throw new ChatProtocolError("Invalid chat payload (not object)", raw);
  }

  const type = safeString(raw.type, "message");

  if (type === "message") {
    const msgRaw = raw.message ?? raw;
    if (!isRecord(msgRaw)) {
      throw new ChatProtocolError("Invalid chat message payload", raw);
    }

    return {
      type: "message",
      message: {
        role: safeString(msgRaw.role, "assistant"),
        content: safeString(msgRaw.content),
        ts: normalizeTimestamp(msgRaw.ts),
        meta: isRecord(msgRaw.meta) ? msgRaw.meta : undefined,
      },
    };
  }

  if (type === "error") {
    return {
      type: "error",
      error: safeString(raw.error, "Unknown chat error"),
      meta: isRecord(raw.meta) ? raw.meta : undefined,
    };
  }

  if (type === "status") {
    return {
      type: "status",
      status: safeString(raw.status),
      meta: isRecord(raw.meta) ? raw.meta : undefined,
    };
  }

  // Forward-compatible: unknown structured event
  return {
    type,
    meta: isRecord(raw.meta) ? raw.meta : (raw as Record<string, unknown>),
  };
}

/**
 * Serialize a user chat message for outbound WebSocket send.
 *
 * Keeps format minimal and forward-compatible.
 */
export function serializeUserMessage(content: string): string {
  const trimmed = content.trim();
  return JSON.stringify({
    type: "message",
    message: {
      role: "user",
      content: trimmed,
      ts: Math.floor(Date.now() / 1000),
    },
  });
}

/**
 * Minimal ChatClient wrapper for WebSocket usage.
 *
 * This does NOT manage reconnection, buffering, or UI state.
 * Those concerns live one layer up (React hooks/components).
 */
export class ChatClient {
  readonly ws: WebSocket;

  constructor(ws: WebSocket) {
    this.ws = ws;
  }

  sendUserMessage(text: string): void {
    const trimmed = text.trim();
    if (!trimmed) return;
    this.ws.send(serializeUserMessage(trimmed));
  }

  /**
   * Send a raw payload. Use sparingly—prefer typed helpers.
   */
  sendRaw(data: string | ArrayBufferLike | Blob | ArrayBufferView): void {
    this.ws.send(data);
  }

  close(code?: number, reason?: string): void {
    try {
      this.ws.close(code, reason);
    } catch {
      // ignore
    }
  }

  /**
   * Attach a message handler that receives normalized ChatEvent objects.
   * Returns an unsubscribe function.
   *
   * This is a convenience; higher layers may prefer to bind ws.onmessage directly.
   */
  onEvent(handler: (ev: ChatEvent) => void): () => void {
    const prev = this.ws.onmessage;
    this.ws.onmessage = (msgEv) => {
      try {
        handler(parseChatEvent(msgEv.data));
      } catch (err) {
        const e = err instanceof Error ? err.message : "Chat protocol error";
        handler({ type: "error", error: e, meta: { raw: msgEv.data } });
      }

      // Preserve any previous handler chain (defensive / composable)
      if (typeof prev === "function") {
        try {
          prev.call(this.ws, msgEv);
        } catch {
          // ignore
        }
      }
    };

    return () => {
      // Restore prior handler if no one else overwrote ours.
      if (this.ws.onmessage !== prev) {
        this.ws.onmessage = prev ?? null;
      }
    };
  }
}
