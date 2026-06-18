export const FRANCIS_BROWSER_VOICE_ACTOR = "chat_ui.voice";
export const FRANCIS_BROWSER_VOICE_SOURCE = "chat_ui.voice";
export const FRANCIS_BROWSER_VOICE_CLIENT_ORIGIN = "francis_chat_ui_browser_voice";

export type FrancisVoiceTurnKind = "wake" | "passive" | "noise";

export type FrancisVoiceTranscriptClassification = {
  kind: FrancisVoiceTurnKind;
  transcript: string;
  wake_phrase_detected: boolean;
  forward_to_chat: boolean;
  use_llm: boolean;
  awareness_state: string;
};

export type FrancisVoiceSoundClassification = {
  kind: FrancisVoiceTurnKind;
  sound_observed: boolean;
  speech_observed: boolean;
  transcript_observed: boolean;
  awareness_state: string;
  forward_to_chat: boolean;
};

export type FrancisVoiceIngressRequest = {
  transcript: string;
  actor?: string;
  source?: string;
  client_origin?: string;
  conversation_id?: string;
  turn_id?: string;
  locale?: string;
  forward_to_chat?: boolean;
  use_llm?: boolean;
};

export type FrancisVoiceIngressResponse = {
  ok: boolean;
  status: string;
  reply: string;
  error: string;
  voice_response?: Record<string, unknown>;
  chat_forward?: Record<string, unknown>;
  receipt?: Record<string, unknown>;
  orb_voice_bridge?: Record<string, unknown>;
};

export class FrancisVoiceClientError extends Error {
  readonly status?: number;
  readonly url?: string;

  constructor(message: string, opts?: { status?: number; url?: string; cause?: unknown }) {
    super(message);
    this.name = "FrancisVoiceClientError";
    this.status = opts?.status;
    this.url = opts?.url;
    if (opts?.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = opts.cause;
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function normalizeBaseUrl(value: string | undefined): string {
  return (value ?? "").trim().replace(/\/+$/, "");
}

export function normalizeVoiceTranscript(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function wakePhrasePattern(phrase: string): RegExp | null {
  const normalized = phrase.trim().toLowerCase();
  if (!normalized) return null;
  const escaped = normalized.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
  return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`, "i");
}

export function classifyVoiceTranscript(
  transcript: string,
  opts?: { wakePhrases?: string[]; useLlmForWake?: boolean },
): FrancisVoiceTranscriptClassification {
  const cleanTranscript = normalizeVoiceTranscript(transcript);
  const wakePhrases = opts?.wakePhrases?.length ? opts.wakePhrases : ["francis", "hey francis", "okay francis"];
  const wakePhraseDetected = wakePhrases
    .map(wakePhrasePattern)
    .some((pattern) => pattern !== null && pattern.test(cleanTranscript));
  const kind: FrancisVoiceTurnKind = wakePhraseDetected ? "wake" : "passive";
  return {
    kind,
    transcript: cleanTranscript,
    wake_phrase_detected: wakePhraseDetected,
    forward_to_chat: wakePhraseDetected,
    use_llm: wakePhraseDetected ? opts?.useLlmForWake ?? true : false,
    awareness_state: wakePhraseDetected ? "wake_phrase_detected" : "passive_transcript_recorded",
  };
}

export function classifyVoiceSound(opts: {
  soundObserved: boolean;
  speechObserved: boolean;
  transcript: string;
}): FrancisVoiceSoundClassification {
  const transcriptObserved = Boolean(normalizeVoiceTranscript(opts.transcript));
  if (opts.soundObserved && !opts.speechObserved && !transcriptObserved) {
    return {
      kind: "noise",
      sound_observed: true,
      speech_observed: false,
      transcript_observed: false,
      awareness_state: "ambient_noise_observed",
      forward_to_chat: false,
    };
  }
  return {
    kind: transcriptObserved ? classifyVoiceTranscript(opts.transcript).kind : "passive",
    sound_observed: opts.soundObserved,
    speech_observed: opts.speechObserved,
    transcript_observed: transcriptObserved,
    awareness_state: transcriptObserved ? "speech_transcript_observed" : "listening",
    forward_to_chat: transcriptObserved ? classifyVoiceTranscript(opts.transcript).forward_to_chat : false,
  };
}

export function createVoiceTurnId(prefix = "chat_ui_voice"): string {
  const random = Math.random().toString(16).slice(2, 10);
  return `${prefix}_${Date.now().toString(36)}_${random}`;
}

export function buildVoiceIngressPayload(req: FrancisVoiceIngressRequest): Record<string, unknown> {
  return {
    actor: req.actor?.trim() || FRANCIS_BROWSER_VOICE_ACTOR,
    source: req.source?.trim() || FRANCIS_BROWSER_VOICE_SOURCE,
    client_origin: req.client_origin?.trim() || FRANCIS_BROWSER_VOICE_CLIENT_ORIGIN,
    transcript: normalizeVoiceTranscript(req.transcript),
    conversation_id: req.conversation_id?.trim() || "chat_ui_voice",
    turn_id: req.turn_id?.trim() || createVoiceTurnId(),
    locale: req.locale?.trim() || "",
    forward_to_chat: Boolean(req.forward_to_chat),
    use_llm: Boolean(req.use_llm),
  };
}

export function parseVoiceIngressResponse(value: unknown): FrancisVoiceIngressResponse {
  const raw = isRecord(value) ? value : {};
  return {
    ok: Boolean(raw.ok),
    status: safeString(raw.status),
    reply: safeString(raw.reply),
    error: safeString(raw.error),
    voice_response: isRecord(raw.voice_response) ? raw.voice_response : undefined,
    chat_forward: isRecord(raw.chat_forward) ? raw.chat_forward : undefined,
    receipt: isRecord(raw.receipt) ? raw.receipt : undefined,
    orb_voice_bridge: isRecord(raw.orb_voice_bridge) ? raw.orb_voice_bridge : undefined,
  };
}

export class FrancisVoiceClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
  }

  async recordTranscript(req: FrancisVoiceIngressRequest, opts?: { signal?: AbortSignal }): Promise<FrancisVoiceIngressResponse> {
    const url = `${this.baseUrl}/chatgpt-voice/ingress`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildVoiceIngressPayload(req)),
      signal: opts?.signal,
    });
    const text = await res.text();
    let json: unknown = {};
    if (text.trim()) {
      try {
        json = JSON.parse(text);
      } catch (err) {
        throw new FrancisVoiceClientError("Voice ingress response was not valid JSON.", {
          status: res.status,
          url,
          cause: err,
        });
      }
    }
    if (!res.ok) {
      throw new FrancisVoiceClientError(`Voice ingress request failed with HTTP ${res.status}.`, {
        status: res.status,
        url,
      });
    }
    return parseVoiceIngressResponse(json);
  }
}
