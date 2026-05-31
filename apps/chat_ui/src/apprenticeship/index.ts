export type ApprenticeshipDeliverable = {
  id: string;
  label?: string;
  ready: boolean;
  evidence?: string;
};

export type ApprenticeshipStatusSnapshot = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  ready_count: number;
  required_count: number;
  teaching_session_ready: boolean;
  replay_generalization_ready: boolean;
  skillization_ready: boolean;
  forge_handoff_ready: boolean;
  live_teaching_session_ux_ready: boolean;
  deliverables: ApprenticeshipDeliverable[];
  routes: Record<string, string>;
  writes_receipts: boolean;
  writes_memory: boolean;
  captures_screen: boolean;
  captures_audio: boolean;
  captures_keystrokes: boolean;
  passive_learning_enabled: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  next_smallest_truthful_gap?: string;
};

export type ApprenticeshipVisibleSection = {
  id: string;
  label?: string;
  source_route?: string;
  visible: boolean;
  status?: string;
};

export type ApprenticeshipOperatorAction = {
  id: string;
  label?: string;
  enabled: boolean;
  status?: string;
};

export type ApprenticeshipLiveTeachingSessionUx = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  surface?: string;
  route?: string;
  live_teaching_session_ux_ready: boolean;
  visible_sections: ApprenticeshipVisibleSection[];
  visible_section_count: number;
  operator_actions: ApprenticeshipOperatorAction[];
  operator_action_count: number;
  denied_modes: string[];
  writes_receipts: boolean;
  writes_memory: boolean;
  writes_skill_artifact: boolean;
  writes_forge_proposal: boolean;
  starts_teaching_session: boolean;
  captures_screen: boolean;
  captures_audio: boolean;
  captures_keystrokes: boolean;
  passive_learning_enabled: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  next_smallest_truthful_gap?: string;
};

export type ApprenticeshipPanelModel = {
  status: string;
  stage: string;
  readyCount: number;
  requiredCount: number;
  nextGap: string;
  readyDeliverables: string[];
  blockedDeliverables: string[];
  visibleSections: string[];
  disabledActions: string[];
  guardLines: string[];
};

export class ApprenticeshipApiError extends Error {
  readonly status?: number;
  readonly url?: string;

  constructor(message: string, opts?: { status?: number; url?: string }) {
    super(message);
    this.name = "ApprenticeshipApiError";
    this.status = opts?.status;
    this.url = opts?.url;
  }
}

export function trimTrailingSlashes(value: string): string {
  let end = value.length;
  while (end > 0 && value.charCodeAt(end - 1) === 47) {
    end -= 1;
  }
  return value.slice(0, end);
}

function safeString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function safeNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function safeBoolean(value: unknown): boolean {
  return typeof value === "boolean" ? value : false;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => safeString(item).trim()).filter(Boolean);
}

function parseDeliverable(raw: unknown): ApprenticeshipDeliverable | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id).trim();
  if (!id) return null;
  return {
    id,
    label: safeString(raw.label).trim() || undefined,
    ready: safeBoolean(raw.ready),
    evidence: safeString(raw.evidence).trim() || undefined,
  };
}

function parseVisibleSection(raw: unknown): ApprenticeshipVisibleSection | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id).trim();
  if (!id) return null;
  return {
    id,
    label: safeString(raw.label).trim() || undefined,
    source_route: safeString(raw.source_route).trim() || undefined,
    visible: safeBoolean(raw.visible),
    status: safeString(raw.status).trim() || undefined,
  };
}

function parseOperatorAction(raw: unknown): ApprenticeshipOperatorAction | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id).trim();
  if (!id) return null;
  return {
    id,
    label: safeString(raw.label).trim() || undefined,
    enabled: safeBoolean(raw.enabled),
    status: safeString(raw.status).trim() || undefined,
  };
}

function parseRoutes(raw: unknown): Record<string, string> {
  if (!isRecord(raw)) return {};
  const routes: Record<string, string> = {};
  for (const [key, value] of Object.entries(raw)) {
    const text = safeString(value).trim();
    if (text) routes[key] = text;
  }
  return routes;
}

export function parseApprenticeshipStatusSnapshot(raw: unknown): ApprenticeshipStatusSnapshot {
  if (!isRecord(raw)) {
    return {
      ok: false,
      ready_count: 0,
      required_count: 0,
      teaching_session_ready: false,
      replay_generalization_ready: false,
      skillization_ready: false,
      forge_handoff_ready: false,
      live_teaching_session_ux_ready: false,
      deliverables: [],
      routes: {},
      writes_receipts: false,
      writes_memory: false,
      captures_screen: false,
      captures_audio: false,
      captures_keystrokes: false,
      passive_learning_enabled: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
    };
  }

  const deliverables = Array.isArray(raw.deliverables)
    ? raw.deliverables.map(parseDeliverable).filter((item): item is ApprenticeshipDeliverable => item !== null)
    : [];
  return {
    ok: Boolean(raw.ok),
    kind: safeString(raw.kind).trim() || undefined,
    stage: safeString(raw.stage).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    ready_count: safeNumber(raw.ready_count, deliverables.filter((item) => item.ready).length),
    required_count: safeNumber(raw.required_count, deliverables.length),
    teaching_session_ready: safeBoolean(raw.teaching_session_ready),
    replay_generalization_ready: safeBoolean(raw.replay_generalization_ready),
    skillization_ready: safeBoolean(raw.skillization_ready),
    forge_handoff_ready: safeBoolean(raw.forge_handoff_ready),
    live_teaching_session_ux_ready: safeBoolean(raw.live_teaching_session_ux_ready),
    deliverables,
    routes: parseRoutes(raw.routes),
    writes_receipts: safeBoolean(raw.writes_receipts),
    writes_memory: safeBoolean(raw.writes_memory),
    captures_screen: safeBoolean(raw.captures_screen),
    captures_audio: safeBoolean(raw.captures_audio),
    captures_keystrokes: safeBoolean(raw.captures_keystrokes),
    passive_learning_enabled: safeBoolean(raw.passive_learning_enabled),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap).trim() || undefined,
  };
}

export function parseApprenticeshipLiveTeachingSessionUx(raw: unknown): ApprenticeshipLiveTeachingSessionUx {
  if (!isRecord(raw)) {
    return {
      ok: false,
      live_teaching_session_ux_ready: false,
      visible_sections: [],
      visible_section_count: 0,
      operator_actions: [],
      operator_action_count: 0,
      denied_modes: [],
      writes_receipts: false,
      writes_memory: false,
      writes_skill_artifact: false,
      writes_forge_proposal: false,
      starts_teaching_session: false,
      captures_screen: false,
      captures_audio: false,
      captures_keystrokes: false,
      passive_learning_enabled: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
    };
  }

  const visibleSections = Array.isArray(raw.visible_sections)
    ? raw.visible_sections.map(parseVisibleSection).filter((item): item is ApprenticeshipVisibleSection => item !== null)
    : [];
  const operatorActions = Array.isArray(raw.operator_actions)
    ? raw.operator_actions.map(parseOperatorAction).filter((item): item is ApprenticeshipOperatorAction => item !== null)
    : [];
  return {
    ok: Boolean(raw.ok),
    kind: safeString(raw.kind).trim() || undefined,
    stage: safeString(raw.stage).trim() || undefined,
    status: safeString(raw.status).trim() || undefined,
    surface: safeString(raw.surface).trim() || undefined,
    route: safeString(raw.route).trim() || undefined,
    live_teaching_session_ux_ready: safeBoolean(raw.live_teaching_session_ux_ready),
    visible_sections: visibleSections,
    visible_section_count: safeNumber(raw.visible_section_count, visibleSections.length),
    operator_actions: operatorActions,
    operator_action_count: safeNumber(raw.operator_action_count, operatorActions.length),
    denied_modes: safeStringList(raw.denied_modes),
    writes_receipts: safeBoolean(raw.writes_receipts),
    writes_memory: safeBoolean(raw.writes_memory),
    writes_skill_artifact: safeBoolean(raw.writes_skill_artifact),
    writes_forge_proposal: safeBoolean(raw.writes_forge_proposal),
    starts_teaching_session: safeBoolean(raw.starts_teaching_session),
    captures_screen: safeBoolean(raw.captures_screen),
    captures_audio: safeBoolean(raw.captures_audio),
    captures_keystrokes: safeBoolean(raw.captures_keystrokes),
    passive_learning_enabled: safeBoolean(raw.passive_learning_enabled),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap).trim() || undefined,
  };
}

export function presentApprenticeshipPanel(
  status: ApprenticeshipStatusSnapshot | null | undefined,
  ux: ApprenticeshipLiveTeachingSessionUx | null | undefined,
): ApprenticeshipPanelModel {
  const readyDeliverables = (status?.deliverables ?? [])
    .filter((item) => item.ready)
    .map((item) => item.label || item.id);
  const blockedDeliverables = (status?.deliverables ?? [])
    .filter((item) => !item.ready)
    .map((item) => item.label || item.id);
  const visibleSections = (ux?.visible_sections ?? [])
    .filter((item) => item.visible)
    .map((item) => item.label || item.id);
  const disabledActions = (ux?.operator_actions ?? [])
    .filter((item) => !item.enabled)
    .map((item) => item.label || item.id);
  const guardLines = [
    status?.writes_memory ? "memory writes enabled" : "memory writes blocked",
    status?.captures_screen || status?.captures_audio || status?.captures_keystrokes
      ? "ambient capture enabled"
      : "ambient capture blocked",
    ux?.starts_teaching_session ? "teaching session start enabled" : "teaching actions disabled pending receipts",
    ux?.writes_forge_proposal ? "Forge proposal writes enabled" : "Forge proposal writes blocked",
    status?.grants_execution_authority || ux?.grants_execution_authority ? "execution authority granted" : "execution authority blocked",
  ];
  return {
    status: status?.status || "unknown",
    stage: status?.stage || ux?.stage || "Stage 11 / Apprenticeship",
    readyCount: status?.ready_count ?? 0,
    requiredCount: status?.required_count ?? 0,
    nextGap: status?.next_smallest_truthful_gap || ux?.next_smallest_truthful_gap || "unknown",
    readyDeliverables,
    blockedDeliverables,
    visibleSections,
    disabledActions,
    guardLines,
  };
}

export class ApprenticeshipClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = trimTrailingSlashes(baseUrl || "");
  }

  async getStatus(opts?: { signal?: AbortSignal }): Promise<ApprenticeshipStatusSnapshot> {
    const url = `${this.baseUrl}/apprenticeship/status`;
    const res = await fetch(url, { method: "GET", signal: opts?.signal });
    if (!res.ok) {
      throw new ApprenticeshipApiError("Failed to load Apprenticeship status.", { status: res.status, url });
    }
    return parseApprenticeshipStatusSnapshot(await res.json());
  }

  async getLiveTeachingSessionUx(opts?: { signal?: AbortSignal }): Promise<ApprenticeshipLiveTeachingSessionUx> {
    const url = `${this.baseUrl}/apprenticeship/live-teaching-session-ux`;
    const res = await fetch(url, { method: "GET", signal: opts?.signal });
    if (!res.ok) {
      throw new ApprenticeshipApiError("Failed to load Apprenticeship teaching surface.", { status: res.status, url });
    }
    return parseApprenticeshipLiveTeachingSessionUx(await res.json());
  }
}
