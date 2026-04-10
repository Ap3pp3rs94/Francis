import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChatMessage } from "./chat";

import type { ApprovalItem } from "./index";
import { ApprovalsApiError, ApprovalsClient } from "./index";
import type { PluginRef, PluginToolRef, PluginToolRunRequest } from "./plugin_browser";
import { PluginBrowserApiError, PluginBrowserClient } from "./plugin_browser";

const DEFAULT_API = "http://127.0.0.1:8000";

type TabKey = "approvals" | "plugins" | "system" | "operations" | "settings";
type SensingMode = "text_only" | "input_only" | "camera_mic";

type UiSettings = {
  proactive: boolean;
  sensingMode: SensingMode;
  voiceEnabled: boolean;
  voiceAutoFemale: boolean;
  voiceUri: string;
  voiceRate: number;
  voicePitch: number;
};

type ChatSession = {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedTs: number;
};

const DEFAULT_SETTINGS: UiSettings = {
  proactive: true,
  sensingMode: "text_only",
  voiceEnabled: false,
  voiceAutoFemale: true,
  voiceUri: "",
  voiceRate: 1.0,
  voicePitch: 1.0,
};

const THEME = {
  bg: "#0a0a0a",
  panel: "#141414",
  panelBorder: "#242424",
  rail: "#0f0f0f",
  railBorder: "#1f1f1f",
  inputBg: "#1b1b1b",
  inputBorder: "#2e2e2e",
  text: "#f5f5f5",
  muted: "#bdbdbd",
  buttonBg: "#1f1f1f",
  buttonBorder: "#333333",
  buttonActive: "#2a2a2a",
  errorBg: "#2a0f0f",
  errorBorder: "#5a1a1a",
  userBubble: "#1f1f1f",
  assistantBubble: "#121212",
};

const panelStyle: React.CSSProperties = {
  border: `1px solid ${THEME.panelBorder}`,
  padding: 16,
  borderRadius: 14,
  background: THEME.panel,
};

const inputStyle: React.CSSProperties = {
  padding: 12,
  borderRadius: 12,
  border: `1px solid ${THEME.inputBorder}`,
  background: THEME.inputBg,
  color: THEME.text,
};

const buttonStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: 12,
  border: `1px solid ${THEME.buttonBorder}`,
  background: THEME.buttonBg,
  color: THEME.text,
};

function clamp01(n: number): number {
  return Math.min(2, Math.max(0.5, n));
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function loadSettings(): UiSettings {
  try {
    const raw = localStorage.getItem("francis_ui_settings");
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<UiSettings>;
    return { ...DEFAULT_SETTINGS, ...parsed };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function saveSettings(settings: UiSettings): void {
  try {
    localStorage.setItem("francis_ui_settings", JSON.stringify(settings));
  } catch {
    // ignore
  }
}

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem("francis_ui_sessions");
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatSession[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions: ChatSession[]): void {
  try {
    localStorage.setItem("francis_ui_sessions", JSON.stringify(sessions));
  } catch {
    // ignore
  }
}

function createSession(): ChatSession {
  const id = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Date.now());
  return { id, title: "New chat", messages: [], updatedTs: Date.now() };
}

function summarizeTitle(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "New chat";
  const short = trimmed.length > 48 ? `${trimmed.slice(0, 48)}.` : trimmed;
  return short.replace(/\s+/g, " ");
}

function pickAutoFemaleVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  if (!voices.length) return undefined;
  const preferred = voices.find((v) => /female|zira|susan|samantha|karen|victoria/i.test(v.name));
  return preferred ?? voices[0];
}

function useWindowWidth(): number {
  const [width, setWidth] = useState(() => window.innerWidth);
  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return width;
}
function ChatPanel(props: {
  baseUrl: string;
  messages: ChatMessage[];
  busy: boolean;
  error: string | null;
  onSend: (text: string) => void;
  onSpeak: (text: string) => void;
}) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const lastSpokenIdx = useRef(-1);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [props.messages]);

  useEffect(() => {
    const lastIdx = props.messages.length - 1;
    if (lastIdx <= lastSpokenIdx.current) return;
    const msg = props.messages[lastIdx];
    if (msg.role !== "assistant") return;
    lastSpokenIdx.current = lastIdx;
    props.onSpeak(msg.content);
  }, [props.messages, props.onSpeak]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, height: "100%" }}>
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflow: "auto",
          padding: "8px 4px 8px 0",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {props.messages.length === 0 ? (
          <div style={{ color: THEME.muted, marginTop: 24 }}>
            Start a conversation. Francis will respond in the main window.
          </div>
        ) : null}
        {props.messages.map((m, idx) => {
          const isUser = m.role === "user";
          return (
            <div
              key={`${m.role}-${idx}`}
              style={{
                alignSelf: isUser ? "flex-end" : "flex-start",
                maxWidth: "78%",
                background: isUser ? THEME.userBubble : THEME.assistantBubble,
                border: `1px solid ${THEME.panelBorder}`,
                borderRadius: 16,
                padding: "12px 14px",
                lineHeight: 1.45,
              }}
            >
              <div style={{ fontSize: 12, color: THEME.muted, marginBottom: 6 }}>
                {isUser ? "You" : "Francis"}
              </div>
              <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
            </div>
          );
        })}
      </div>

      {props.error ? (
        <div
          style={{
            border: `1px solid ${THEME.errorBorder}`,
            background: THEME.errorBg,
            padding: 10,
            borderRadius: 10,
            color: "#ffaaaa",
            fontSize: 12,
          }}
        >
          <b>Error:</b> {props.error}
        </div>
      ) : null}

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              props.onSend(input);
              setInput("");
            }
          }}
          placeholder="Message Francis"
          style={{ ...inputStyle, flex: 1 }}
        />
        <button
          onClick={() => {
            props.onSend(input);
            setInput("");
          }}
          disabled={props.busy}
          style={buttonStyle}
        >
          {props.busy ? "Working." : "Send"}
        </button>
      </div>
      <div style={{ fontSize: 11, color: THEME.muted }}>
        API: <code>{props.baseUrl}</code>
      </div>
    </div>
  );
}

function SettingsPanel(props: { settings: UiSettings; onChange: (next: UiSettings) => void }) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    const load = () => setVoices(window.speechSynthesis.getVoices());
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, []);

  const hasVoices = voices.length > 0;

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>Settings</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>Behavior, sensing, and voice.</div>

      <div style={{ display: "grid", gap: 12, marginTop: 16 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={props.settings.proactive}
            onChange={(e) => props.onChange({ ...props.settings, proactive: e.target.checked })}
          />
          Proactive mode (speak only when it adds value)
        </label>

        <div>
          <div style={{ fontSize: 12, marginBottom: 6, color: THEME.muted }}>Sensing mode</div>
          <select
            value={props.settings.sensingMode}
            onChange={(e) => props.onChange({ ...props.settings, sensingMode: e.target.value as SensingMode })}
            style={{
              padding: "6px 8px",
              borderRadius: 6,
              border: `1px solid ${THEME.inputBorder}`,
              background: THEME.inputBg,
              color: THEME.text,
            }}
          >
            <option value="text_only">Text only</option>
            <option value="input_only">Input only (keyboard/mouse)</option>
            <option value="camera_mic">Camera + mic</option>
          </select>
        </div>

        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={props.settings.voiceEnabled}
            onChange={(e) => props.onChange({ ...props.settings, voiceEnabled: e.target.checked })}
          />
          Voice enabled (assistant replies)
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={props.settings.voiceAutoFemale}
            onChange={(e) => props.onChange({ ...props.settings, voiceAutoFemale: e.target.checked })}
            disabled={!props.settings.voiceEnabled}
          />
          Auto-pick a soft female voice
        </label>

        <div>
          <div style={{ fontSize: 12, marginBottom: 6, color: THEME.muted }}>Voice</div>
          <select
            value={props.settings.voiceUri}
            onChange={(e) => props.onChange({ ...props.settings, voiceUri: e.target.value, voiceAutoFemale: false })}
            disabled={!props.settings.voiceEnabled || !hasVoices}
            style={{
              padding: "6px 8px",
              borderRadius: 6,
              border: `1px solid ${THEME.inputBorder}`,
              minWidth: 260,
              background: THEME.inputBg,
              color: THEME.text,
            }}
          >
            <option value="">Auto</option>
            {voices.map((v) => (
              <option key={v.voiceURI} value={v.voiceURI}>
                {v.name} ({v.lang})
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            Rate
            <input
              type="number"
              step="0.1"
              min="0.5"
              max="2"
              value={props.settings.voiceRate}
              onChange={(e) =>
                props.onChange({ ...props.settings, voiceRate: clamp01(parseFloat(e.target.value) || 1.0) })
              }
              style={{
                width: 80,
                padding: "4px 6px",
                borderRadius: 6,
                border: `1px solid ${THEME.inputBorder}`,
                background: THEME.inputBg,
                color: THEME.text,
              }}
              disabled={!props.settings.voiceEnabled}
            />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}
          >
            Pitch
            <input
              type="number"
              step="0.1"
              min="0.5"
              max="2"
              value={props.settings.voicePitch}
              onChange={(e) =>
                props.onChange({ ...props.settings, voicePitch: clamp01(parseFloat(e.target.value) || 1.0) })
              }
              style={{
                width: 80,
                padding: "4px 6px",
                borderRadius: 6,
                border: `1px solid ${THEME.inputBorder}`,
                background: THEME.inputBg,
                color: THEME.text,
              }}
              disabled={!props.settings.voiceEnabled}
            />
          </label>
        </div>
      </div>
    </section>
  );
}
export default function App() {
  const [settings, setSettings] = useState<UiSettings>(() => loadSettings());
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions());
  const [activeId, setActiveId] = useState<string>(() => (loadSessions()[0]?.id ?? createSession().id));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<TabKey>("approvals");
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [baseUrl, setBaseUrl] = useState(() => {
    const env = safeString(import.meta.env.VITE_FRANCIS_API_BASE_URL, DEFAULT_API);
    return normalizeBaseUrl(env);
  });
  const width = useWindowWidth();

  useEffect(() => {
    if (sessions.length === 0) {
      const s = createSession();
      setSessions([s]);
      setActiveId(s.id);
    }
  }, [sessions.length]);

  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  useEffect(() => {
    const load = () => setVoices(window.speechSynthesis.getVoices());
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (!settings.voiceEnabled) return;
      if (!text.trim()) return;
      const utterance = new SpeechSynthesisUtterance(text);
      const voice =
        settings.voiceAutoFemale && voices.length
          ? pickAutoFemaleVoice(voices)
          : voices.find((v) => v.voiceURI === settings.voiceUri);
      if (voice) utterance.voice = voice;
      utterance.rate = settings.voiceRate;
      utterance.pitch = settings.voicePitch;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    },
    [settings, voices],
  );

  const activeSession = sessions.find((s) => s.id === activeId) ?? sessions[0];

  const updateSession = useCallback(
    (id: string, updater: (s: ChatSession) => ChatSession) => {
      setSessions((prev) => prev.map((s) => (s.id === id ? updater(s) : s)));
    },
    [],
  );

  const onSend = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !activeSession || busy) return;
      setError(null);
      setBusy(true);

      updateSession(activeSession.id, (s) => {
        const next = { ...s };
        const title = s.title === "New chat" ? summarizeTitle(trimmed) : s.title;
        next.title = title;
        next.messages = [
          ...s.messages,
          { role: "user", content: trimmed, ts: Math.floor(Date.now() / 1000) },
        ];
        next.updatedTs = Date.now();
        return next;
      });

      try {
        const res = await fetch(`${baseUrl}/chat/send`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed, use_llm: true }),
        });
        if (!res.ok) {
          setError(`HTTP ${res.status}`);
          return;
        }
        const json = (await res.json()) as { reply?: string };
        const reply = (json.reply ?? "").trim();
        if (reply) {
          updateSession(activeSession.id, (s) => ({
            ...s,
            messages: [
              ...s.messages,
              { role: "assistant", content: reply, ts: Math.floor(Date.now() / 1000) },
            ],
            updatedTs: Date.now(),
          }));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Chat request failed.");
      } finally {
        setBusy(false);
      }
    },
    [activeSession, baseUrl, busy, updateSession],
  );

  const createNewChat = useCallback(() => {
    const s = createSession();
    setSessions((prev) => [s, ...prev]);
    setActiveId(s.id);
  }, []);

  const isNarrow = width < 1100;

  return (
    <div
      style={{
        minHeight: "100vh",
        color: THEME.text,
        background: "radial-gradient(1200px 600px at 15% -10%, #1d1d1d 0%, #0a0a0a 55%, #070707 100%)",
        fontFamily: '"Space Grotesk", "Manrope", "Segoe UI", sans-serif',
      }}
    >
      <div style={{ display: "flex", minHeight: "100vh" }}>
        <aside
          style={{
            width: 280,
            background: THEME.rail,
            borderRight: `1px solid ${THEME.railBorder}`,
            padding: 18,
            display: isNarrow ? "none" : "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>Francis</div>
            <div style={{ fontSize: 12, color: THEME.muted }}>Operator console</div>
          </div>

          <button onClick={createNewChat} style={{ ...buttonStyle, width: "100%" }}>
            New chat
          </button>

          <div style={{ fontSize: 12, color: THEME.muted }}>History</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveId(s.id)}
                style={{
                  ...buttonStyle,
                  textAlign: "left",
                  border: s.id === activeId ? `1px solid ${THEME.text}` : `1px solid ${THEME.buttonBorder}`,
                  background: s.id === activeId ? THEME.buttonActive : THEME.buttonBg,
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 600 }}>{s.title}</div>
                <div style={{ fontSize: 11, color: THEME.muted }}>
                  {new Date(s.updatedTs).toLocaleDateString()}
                </div>
              </button>
            ))}
          </div>

          <div style={{ marginTop: "auto", fontSize: 11, color: THEME.muted }}>
            Connected to <code>{baseUrl}</code>
          </div>
        </aside>

        <main style={{ flex: 1, display: "flex", flexDirection: "column", padding: 24, gap: 18 }}>
          <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>Francis Console</div>
              <div style={{ fontSize: 12, color: THEME.muted }}>
                Chat, approvals, plugins, system checks, and operations.
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 12, color: THEME.muted }}>API</span>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(normalizeBaseUrl(e.target.value))}
                style={{ ...inputStyle, padding: "8px 10px", minWidth: 220 }}
              />
            </div>
          </header>

          <div style={{ display: "flex", gap: 18, flex: 1, minHeight: 0 }}>
            <section style={{ ...panelStyle, flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
              {activeSession ? (
                <ChatPanel
                  baseUrl={baseUrl}
                  messages={activeSession.messages}
                  busy={busy}
                  error={error}
                  onSend={onSend}
                  onSpeak={speak}
                />
              ) : (
                <div style={{ color: THEME.muted }}>No active chat.</div>
              )}
            </section>

            {isNarrow ? null : (
              <aside style={{ width: 360, display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {(
                    [
                      ["approvals", "Approvals"],
                      ["plugins", "Plugins"],
                      ["system", "System"],
                      ["operations", "Operations"],
                      ["settings", "Settings"],
                    ] as Array<[TabKey, string]>
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      onClick={() => setPanel(key)}
                      style={{
                        ...buttonStyle,
                        border: panel === key ? `1px solid ${THEME.text}` : `1px solid ${THEME.buttonBorder}`,
                        background: panel === key ? THEME.buttonActive : THEME.buttonBg,
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {panel === "approvals" ? <ApprovalsPanel baseUrl={baseUrl} /> : null}
                {panel === "plugins" ? <PluginsPanel baseUrl={baseUrl} /> : null}
                {panel === "system" ? <SystemPanel baseUrl={baseUrl} /> : null}
                {panel === "operations" ? <OperationsPanel baseUrl={baseUrl} /> : null}
                {panel === "settings" ? <SettingsPanel settings={settings} onChange={setSettings} /> : null}
              </aside>
            )}
          </div>

          {isNarrow ? (
            <section style={{ ...panelStyle, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {(
                  [
                    ["approvals", "Approvals"],
                    ["plugins", "Plugins"],
                    ["system", "System"],
                    ["operations", "Operations"],
                    ["settings", "Settings"],
                  ] as Array<[TabKey, string]>
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setPanel(key)}
                    style={{
                      ...buttonStyle,
                      border: panel === key ? `1px solid ${THEME.text}` : `1px solid ${THEME.buttonBorder}`,
                      background: panel === key ? THEME.buttonActive : THEME.buttonBg,
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {panel === "approvals" ? <ApprovalsPanel baseUrl={baseUrl} /> : null}
              {panel === "plugins" ? <PluginsPanel baseUrl={baseUrl} /> : null}
              {panel === "system" ? <SystemPanel baseUrl={baseUrl} /> : null}
              {panel === "operations" ? <OperationsPanel baseUrl={baseUrl} /> : null}
              {panel === "settings" ? <SettingsPanel settings={settings} onChange={setSettings} /> : null}
            </section>
          ) : null}
        </main>
      </div>
    </div>
  );
}
function ApprovalsPanel(props: { baseUrl: string }) {
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const client = useMemo(() => new ApprovalsClient(resolvedBaseUrl), [resolvedBaseUrl]);

  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [decisionBusy, setDecisionBusy] = useState<Record<string, boolean>>({});
  const [decisionError, setDecisionError] = useState<Record<string, string | null>>({});

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await client.list({ status: "pending", limit: 50 });
      setItems(res.items ?? []);
    } catch (err) {
      if (err instanceof ApprovalsApiError) {
        const detail = err.status ? `HTTP ${err.status}` : "request failed";
        setLoadError(`${detail}${err.url ? ` (${err.url})` : ""}`);
      } else if (err instanceof Error) {
        setLoadError(err.message);
      } else {
        setLoadError("Failed to load approvals.");
      }
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function performDecision(id: string, action: string) {
    setDecisionError((prev) => ({ ...prev, [id]: null }));
    setDecisionBusy((prev) => ({ ...prev, [id]: true }));
    try {
      await client.decide({ id, action });
      await refresh();
    } catch (err) {
      const msg =
        err instanceof ApprovalsApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
          : err instanceof Error
            ? err.message
            : "Decision failed.";
      setDecisionError((prev) => ({ ...prev, [id]: msg }));
    } finally {
      setDecisionBusy((prev) => ({ ...prev, [id]: false }));
    }
  }

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>Approvals</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>
        status=pending / api=<code>{resolvedBaseUrl}</code>
      </div>

      {loadError ? (
        <div
          style={{
            marginTop: 12,
            padding: 10,
            borderRadius: 10,
            border: `1px solid ${THEME.errorBorder}`,
            background: THEME.errorBg,
            color: "#ffaaaa",
            fontSize: 12,
          }}
        >
          <b>Load error:</b> {loadError}
        </div>
      ) : null}

      <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10, maxHeight: 300, overflow: "auto" }}>
        {loading && items.length === 0 ? <i>Loading approvals.</i> : null}
        {!loading && items.length === 0 ? <i>No approvals found.</i> : null}
        {items.map((a) => {
          const busy = Boolean(decisionBusy[a.id]);
          const err = decisionError[a.id];
          return (
            <div key={a.id} style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 12, padding: 10 }}>
              <div style={{ fontWeight: 600 }}>{a.action || "(unknown action)"}</div>
              <div style={{ fontSize: 12, color: THEME.muted, marginTop: 4 }}>{a.reason || "No reason provided."}</div>
              {err ? (
                <div style={{ marginTop: 6, fontSize: 12, color: "#ffaaaa" }}>
                  <b>Decision error:</b> {err}
                </div>
              ) : null}
              <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                <button style={buttonStyle} disabled={busy} onClick={() => void performDecision(a.id, "approve")}>
                  Approve
                </button>
                <button style={buttonStyle} disabled={busy} onClick={() => void performDecision(a.id, "reject")}>
                  Reject
                </button>
                <button style={buttonStyle} disabled={busy} onClick={() => void performDecision(a.id, "emergency")}>
                  Emergency
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SystemPanel(props: { baseUrl: string }) {
  const [data, setData] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${props.baseUrl}/system/health`);
      if (!res.ok) {
        setError(`HTTP ${res.status}`);
        return;
      }
      const json = await res.json();
      setData(JSON.stringify(json, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>System</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>Health and runtime status.</div>

      <button onClick={() => void load()} disabled={busy} style={{ ...buttonStyle, marginTop: 10 }}>
        {busy ? "Loading." : "Run health check"}
      </button>

      {error ? (
        <div style={{ marginTop: 10, fontSize: 12, color: "#ffaaaa" }}>
          <b>Error:</b> {error}
        </div>
      ) : null}

      {data ? (
        <pre style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>{data}</pre>
      ) : (
        <div style={{ marginTop: 10, color: THEME.muted }}>No data loaded.</div>
      )}
    </section>
  );
}

function PluginsPanel(props: { baseUrl: string }) {
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const client = useMemo(() => new PluginBrowserClient(resolvedBaseUrl), [resolvedBaseUrl]);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [plugins, setPlugins] = useState<PluginRef[]>([]);
  const [tools, setTools] = useState<PluginToolRef[]>([]);
  const [selectedPluginId, setSelectedPluginId] = useState("");
  const [selectedToolId, setSelectedToolId] = useState("");
  const [toolDetail, setToolDetail] = useState<PluginToolRef | null>(null);
  const [runInput, setRunInput] = useState("{\"input\": \"hello\"}");
  const [runReason, setRunReason] = useState("requested");
  const [approvalId, setApprovalId] = useState("");
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPlugin = useMemo(
    () => plugins.find((item) => item.id === selectedPluginId) ?? null,
    [plugins, selectedPluginId],
  );
  const selectedTool = useMemo(
    () => tools.find((item) => item.id === selectedToolId) ?? null,
    [tools, selectedToolId],
  );

  function pluginErrorMessage(err: unknown): string {
    if (err instanceof PluginBrowserApiError) {
      const status = err.status ? `HTTP ${err.status}` : "request failed";
      return `${status}${err.url ? ` (${err.url})` : ""}`;
    }
    if (err instanceof Error) return err.message;
    return "Plugin request failed.";
  }

  const refreshPlugins = useCallback(async () => {
    setLoading(true);
    try {
      const res = await client.list({ limit: 200 });
      const items = res.items ?? [];
      setPlugins(items);
      setSelectedPluginId((prev) => {
        if (prev && items.some((item) => item.id === prev)) return prev;
        return items[0]?.id ?? "";
      });
    } finally {
      setLoading(false);
    }
  }, [client]);

  const refreshTools = useCallback(
    async (pluginId: string) => {
      const resolvedPluginId = pluginId.trim();
      if (!resolvedPluginId) {
        setTools([]);
        setSelectedToolId("");
        setToolDetail(null);
        return;
      }
      const res = await client.listTools({ plugin_id: resolvedPluginId, limit: 500 });
      const items = res.items ?? [];
      setTools(items);
      setSelectedToolId((prev) => {
        if (prev && items.some((item) => item.id === prev)) return prev;
        return items[0]?.id ?? "";
      });
    },
    [client],
  );

  const loadToolDetail = useCallback(
    async (toolId: string) => {
      const resolvedToolId = toolId.trim();
      if (!resolvedToolId) {
        setToolDetail(null);
        return;
      }
      const detail = await client.getTool(resolvedToolId);
      setToolDetail(detail.item);
    },
    [client],
  );

  useEffect(() => {
    void (async () => {
      setError(null);
      try {
        await refreshPlugins();
      } catch (err) {
        setError(pluginErrorMessage(err));
      }
    })();
  }, [refreshPlugins]);

  useEffect(() => {
    void (async () => {
      setError(null);
      try {
        await refreshTools(selectedPluginId);
      } catch (err) {
        setError(pluginErrorMessage(err));
      }
    })();
  }, [selectedPluginId, refreshTools]);

  useEffect(() => {
    void (async () => {
      setError(null);
      try {
        await loadToolDetail(selectedToolId);
      } catch (err) {
        setError(pluginErrorMessage(err));
      }
    })();
  }, [selectedToolId, loadToolDetail]);

  function parseRunInput(text: string): unknown {
    const trimmed = text.trim();
    if (!trimmed) return "";
    try {
      return JSON.parse(trimmed) as unknown;
    } catch {
      return trimmed;
    }
  }

  async function build() {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult("");

    try {
      const res = await fetch(`${resolvedBaseUrl}/plugins/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed, description: description.trim() }),
      });
      if (!res.ok) {
        setError(`HTTP ${res.status}`);
        return;
      }
      const json = (await res.json()) as unknown;
      setResult(JSON.stringify(json, null, 2));
      await refreshPlugins();
    } catch (err) {
      setError(pluginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function reloadRegistry() {
    setBusy(true);
    setError(null);
    try {
      const res = await client.reload();
      setResult(JSON.stringify(res, null, 2));
      await refreshPlugins();
      await refreshTools(selectedPluginId);
    } catch (err) {
      setError(pluginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function exportToolsCsv() {
    setBusy(true);
    setError(null);
    try {
      const exportParams: { plugin_id?: string } = {};
      if (selectedPluginId) exportParams.plugin_id = selectedPluginId;
      const blob = await client.exportTools("csv", exportParams);
      const toolScope = selectedPluginId || "all";
      const fileName = `francis-plugin-tools-${toolScope}.csv`;
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(href);
      const preview = await blob.text();
      setResult(preview.slice(0, 4000));
    } catch (err) {
      setError(pluginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function runSelectedTool() {
    if (!selectedPluginId) {
      setError("Select a plugin.");
      return;
    }
    const tool = toolDetail ?? selectedTool;
    if (!tool) {
      setError("Select a tool action.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const req: PluginToolRunRequest = {
        id: tool.id,
        input: parseRunInput(runInput),
      };
      const reason = runReason.trim();
      if (reason) req.reason = reason;
      const approval = approvalId.trim();
      if (approval) req.approval_id = approval;

      const res = await client.runTool(req);
      if (res.approval_id) setApprovalId(res.approval_id);
      setResult(JSON.stringify(res, null, 2));
      await refreshPlugins();
      await refreshTools(selectedPluginId);
      if (selectedToolId) await loadToolDetail(selectedToolId);
    } catch (err) {
      setError(pluginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>Plugins</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>
        Build plugins, inspect tool actions, and run/export tool catalog.
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        <button onClick={() => void refreshPlugins()} disabled={busy || loading} style={buttonStyle}>
          {loading ? "Loading." : "Refresh"}
        </button>
        <button onClick={() => void reloadRegistry()} disabled={busy} style={buttonStyle}>
          {busy ? "Working." : "Reload registry"}
        </button>
        <button onClick={() => void exportToolsCsv()} disabled={busy} style={buttonStyle}>
          {busy ? "Working." : "Export tools CSV"}
        </button>
      </div>

      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Plugin name" style={inputStyle} />
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          rows={3}
          style={inputStyle}
        />
        <button onClick={() => void build()} disabled={busy} style={buttonStyle}>
          {busy ? "Building." : "Build plugin"}
        </button>
      </div>

      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <select
          value={selectedPluginId}
          onChange={(e) => setSelectedPluginId(e.target.value)}
          style={{ ...inputStyle, padding: "8px 10px" }}
        >
          <option value="">Select plugin</option>
          {plugins.map((plugin) => (
            <option key={plugin.id} value={plugin.id}>
              {plugin.name} ({plugin.id})
            </option>
          ))}
        </select>

        <select
          value={selectedToolId}
          onChange={(e) => setSelectedToolId(e.target.value)}
          style={{ ...inputStyle, padding: "8px 10px" }}
          disabled={!selectedPluginId}
        >
          <option value="">Select tool action</option>
          {tools.map((tool) => (
            <option key={tool.id} value={tool.id}>
              {tool.action} [{tool.risk_tier || "normal"}]
            </option>
          ))}
        </select>
      </div>

      {selectedPlugin ? (
        <div style={{ marginTop: 10, fontSize: 12, color: THEME.muted }}>
          Plugin: <code>{selectedPlugin.id}</code> / status={selectedPlugin.status ?? "unknown"} / enabled=
          {String(selectedPlugin.enabled ?? false)}
        </div>
      ) : null}

      {toolDetail ? (
        <div style={{ marginTop: 8, fontSize: 12, color: THEME.muted }}>
          Tool: <code>{toolDetail.id}</code> / action=<code>{toolDetail.action}</code> / risk=
          {toolDetail.risk_tier ?? "normal"} / required_trust=
          {String(toolDetail.required_trust ?? 0)} / approvals_required=
          {String(toolDetail.approvals_required ?? false)}
        </div>
      ) : null}

      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <textarea
          value={runInput}
          onChange={(e) => setRunInput(e.target.value)}
          placeholder="Tool input JSON or plain text"
          rows={3}
          style={inputStyle}
        />
        <input
          value={runReason}
          onChange={(e) => setRunReason(e.target.value)}
          placeholder="Run reason (audit)"
          style={inputStyle}
        />
        <input
          value={approvalId}
          onChange={(e) => setApprovalId(e.target.value)}
          placeholder="Approval id (optional, for gated actions)"
          style={inputStyle}
        />
        <button onClick={() => void runSelectedTool()} disabled={busy || !selectedPluginId || !selectedToolId} style={buttonStyle}>
          {busy ? "Running." : "Run selected action"}
        </button>
      </div>

      {error ? (
        <div style={{ marginTop: 10, fontSize: 12, color: "#ffaaaa" }}>
          <b>Error:</b> {error}
        </div>
      ) : null}

      {result ? <pre style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>{result}</pre> : null}
    </section>
  );
}

function OperationsPanel(props: { baseUrl: string }) {
  const [data, setData] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${props.baseUrl}/operations/status`);
      if (!res.ok) {
        setError(`HTTP ${res.status}`);
        return;
      }
      const json = await res.json();
      setData(JSON.stringify(json, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>Operations</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>Ops status and telemetry.</div>

      <button onClick={() => void load()} disabled={busy} style={{ ...buttonStyle, marginTop: 10 }}>
        {busy ? "Loading." : "Load status"}
      </button>

      {error ? (
        <div style={{ marginTop: 10, fontSize: 12, color: "#ffaaaa" }}>
          <b>Error:</b> {error}
        </div>
      ) : null}

      {data ? (
        <pre style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>{data}</pre>
      ) : (
        <div style={{ marginTop: 10, color: THEME.muted }}>No data loaded.</div>
      )}
    </section>
  );
}
