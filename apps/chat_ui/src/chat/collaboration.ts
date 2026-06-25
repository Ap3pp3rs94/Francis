export type CollaborationAgentId = "codex" | "claude" | "ollama" | string;

export type CollaborationAgent = {
  agent: CollaborationAgentId;
  label: string;
  enabled: boolean;
  participantKind: string;
  localRunner: string;
  authority: string;
  updatedAt: string;
  updatedBy: string;
  reason: string;
  writesRelayReceipts: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
};

export type CollaborationAgentToggleReceipt = {
  kind: string;
  receiptId: string;
  createdAt: string;
  agent: CollaborationAgentId;
  enabled: boolean;
  previousEnabled: boolean;
  actor: string;
  reason: string;
  governance: Record<string, unknown>;
};

export type CollaborationAgentsStatus = {
  ok: boolean;
  mode: string;
  relay: string;
  agents: CollaborationAgent[];
  receipts: CollaborationAgentToggleReceipt[];
  operatorConsole: {
    surface: string;
    actor: string;
    clientCanBeOperatorConsole: boolean;
    clientIsAutomaticExecutionAuthority: boolean;
  };
  governance: Record<string, unknown>;
};

export type CollaborationRuntimeHelper = {
  name: string;
  status: string;
  running: boolean;
  pids: number[];
  processCount: number;
  processModel: string;
  effectiveWorkerCount: number;
  effectivePids: number[];
  wrapperProcessCount: number;
  wrapperPids: number[];
  processes: {
    pid: number;
    parentPid: number;
    role: string;
  }[];
  logPath: string;
  startsArbitraryCommands: boolean;
};

export type CollaborationRuntimeHealth = {
  ok: boolean;
  mode: string;
  surface: string;
  status: string;
  desiredCount: number;
  helperCount: number;
  helpers: CollaborationRuntimeHelper[];
  supervisor: {
    stateObserved: boolean;
    statePath: string;
    generatedAt: string;
    ageSeconds: number | null;
  };
  collaborationLoop: {
    stateObserved: boolean;
    turnCount: number;
    recurrenceState: string;
    waitingForOllama: boolean;
    lastCodexPromptId: string;
    lastOllamaPromptId: string;
    lastNoteId: string;
    lastInsightId: string;
    lastLearningEventId: string;
    nextPromptAfter: string;
    turnGapRemainingSeconds: number;
    updatedAt: string;
    ageSeconds: number | null;
    latestTurn: {
      turn: number;
      turnLabel: string;
      topic: string;
      codexPromptId: string;
      ollamaPromptId: string;
      noteId: string;
      insightId: string;
      createdAt: string;
    };
    latestReviewReceipt: {
      observed: boolean;
      insightId: string;
      reviewItemId: string;
      reviewArtifact: string;
      reviewRoute: string;
      source: string;
      requiresCodexOrOperatorReviewBeforeImplementation: boolean;
      grantsExecutionAuthority: boolean;
      grantsMutationAuthority: boolean;
      grantsApprovalAuthority: boolean;
      grantsMemoryWriteAuthority: boolean;
    };
    latestLearningReceipt: {
      observed: boolean;
      learningEventId: string;
      learningArtifact: string;
      learningRoute: string;
      source: string;
      recordsModelDriftAsLearning: boolean;
      requiresCodexOrOperatorReviewBeforeTuning: boolean;
      storesFullTranscript: boolean;
      grantsTrainingAuthority: boolean;
      grantsExecutionAuthority: boolean;
      grantsMutationAuthority: boolean;
      grantsApprovalAuthority: boolean;
      grantsMemoryWriteAuthority: boolean;
    };
    currentLearningSignal: {
      observed: boolean;
      failureType: string;
      repeatedTerms: string[];
      recentTurnCount: number;
      latestTurn: number;
      learningEventId: string;
      learningArtifact: string;
      source: string;
      updatedAt: string;
      ageSeconds: number | null;
      recordsModelDriftAsLearning: boolean;
      requiresCodexOrOperatorReviewBeforeTuning: boolean;
      storesFullTranscript: boolean;
      grantsTrainingAuthority: boolean;
      grantsExecutionAuthority: boolean;
      grantsMutationAuthority: boolean;
      grantsApprovalAuthority: boolean;
      grantsMemoryWriteAuthority: boolean;
    };
  };
  participants: {
    enabledCount: number;
    totalCount: number;
    items: {
      agent: string;
      label: string;
      enabled: boolean;
      authority: string;
    }[];
  };
  readbackCache: CollaborationReadbackCache;
  governance: Record<string, unknown>;
};

export type CollaborationTranscriptItem = {
  id: string;
  createdAt: string;
  updatedAt: string;
  status: string;
  sourceAgent: string;
  targetAgent: string;
  direction: string;
  objective: string;
  prompt: string;
  context: string;
  chatText: string;
  receiptKind: "conversation" | "audit_ack";
  sourceChatEchoRequired: boolean;
  targetChatEchoRequired: boolean;
  governance: Record<string, unknown>;
};

export type CollaborationTranscript = {
  ok: boolean;
  mode: string;
  relayRoot: string;
  items: CollaborationTranscriptItem[];
  count: number;
  truncated: boolean;
  filters: Record<string, unknown>;
  readbackCache: CollaborationReadbackCache;
  governance: Record<string, unknown>;
};

export type CollaborationRelayDisplay = {
  summary: string;
  conversationText: string;
  technicalText: string;
  tone: "conversation" | "driver" | "guard" | "audit" | "technical";
  raw: string;
  compacted: boolean;
  receiptFields: string[];
};

export type CollaborationActionBoundaryDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  detail: string[];
};

export type CollaborationActionIntakeDisplay = {
  applies: boolean;
  badge: string;
  tone: CollaborationReviewTone;
  detail: string[];
};

export type CollaborationImplementationReviewDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  artifact: string;
  surface: string;
  nextAction: string;
  detail: string[];
};

export type CollaborationBuildDirectionGateDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  artifact: string;
  surface: string;
  reason: string;
  detail: string[];
  conflictingSourceLines: string[];
};

export type CollaborationRuntimeRecurrenceDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  detail: string[];
};

export type CollaborationRuntimeReviewReceiptDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  detail: string[];
};

export type CollaborationRuntimeLearningReceiptDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  detail: string[];
};

export type CollaborationRuntimeLearningSignalDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  detail: string[];
};

export type FrancisBodySurface = {
  id: string;
  label: string;
  description: string;
  connectionState: string;
  accessMode: string;
  trustRequiredForNextMode: string;
  evidence: {
    path: string;
    observed: boolean;
  }[];
  currentBoundary: string;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsTrainingAuthority: boolean;
};

export type FrancisBodyCoverageItem = {
  planeId: string;
  planeName: string;
  bodySurfaceId: string;
  currentPosture: string;
  connectionState: string;
  accessMode: string;
  riskLevel: string;
  riskStatement: string;
  nextReviewArtifact: string;
  recommendedNextAction: string;
  validationHint: string;
  evidence: {
    path: string;
    observed: boolean;
  }[];
  remainingGaps: string[];
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsTrainingAuthority: boolean;
};

export type FrancisBodyMap = {
  ok: boolean;
  mode: string;
  surface: string;
  generatedAt: string;
  identity: {
    localIdentity: string;
    providerLane: string;
    providerNameIsIdentity: boolean;
    codexRole: string;
    claudeRole: string;
    francisRole: string;
  };
  phase: {
    current: string;
    source: string;
    posture: string;
    priority: string;
  };
  accessLadder: string[];
  surfaces: FrancisBodySurface[];
  summary: {
    surfaceCount: number;
    connectedOrPartialCount: number;
    candidateCount: number;
    blockedCount: number;
    unknownCount: number;
    defaultAccessMode: string;
    fullBodyVisible: boolean;
    fullBodyAuthorityGranted: boolean;
    trustLadderEnforced: boolean;
    runtimeRestartObserved: boolean;
    coverageReviewed: boolean;
    canonicalPlaneCount: number;
    canonicalPlaneCoveredCount: number;
    coverageOpenGapCount: number;
  };
  quest: {
    id: string;
    title: string;
    estimatedTimeline: string;
    singleTimeline: {
      order: number;
      label: string;
      targetDuration: string;
      expectedStatusAfterThisSlice: string;
    }[];
    steps: {
      id: string;
      label: string;
      status: string;
      evidence: string;
    }[];
    completedSteps: number;
    totalSteps: number;
    percentComplete: number;
    percentBaseline: string;
    remaining: string[];
  };
  evidence: {
    manifestObserved: boolean;
    ledgerObserved: boolean;
    trustLadderObserved: boolean;
    runtimeRestartObserved: boolean;
    bodyCoverageReviewObserved: boolean;
    canonicalPlaneCount: number;
    canonicalPlaneCoveredCount: number;
    missingCanonicalPlaneIds: string[];
    coverageOpenGapCount: number;
    latestRuntimePromptId: string;
    latestRuntimeResponseId: string;
    latestLedgerEntry: string;
  };
  coverageReview: {
    kind: string;
    schemaVersion: string;
    surface: string;
    observed: boolean;
    status: string;
    coverageComplete: boolean;
    capabilityComplete: boolean;
    canonicalSource: string;
    canonicalSourcesObserved: boolean;
    planeCount: number;
    coveredPlaneCount: number;
    missingPlaneIds: string[];
    openGapCount: number;
    items: FrancisBodyCoverageItem[];
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
    grantsTrainingAuthority: boolean;
  };
  runtimeObservation: {
    observed: boolean;
    promptObserved: boolean;
    responseObserved: boolean;
    promptId: string;
    responseId: string;
    outputGuardRewriteObserved: boolean;
    storesFullTranscript: boolean;
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
    grantsTrainingAuthority: boolean;
  };
  trustLadder: {
    surface: string;
    route: string;
    mcpTool: string;
    connected: boolean;
    decisionContract: string[];
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
    grantsTrainingAuthority: boolean;
  };
  readbackCache: CollaborationReadbackCache;
  governance: Record<string, unknown>;
};

export type FrancisTrustLadderItem = {
  id: string;
  sourceReviewItemId: string;
  insightId: string;
  createdAt: string;
  sessionId: string;
  turn: number;
  topic: string;
  needStatement: string;
  requestedSurface: string;
  sourceArtifact: string;
  decision: string;
  decisionReason: string;
  currentAccessMode: string;
  requestedAccessMode: string;
  nextTrustGate: string;
  recommendedNextAction: string;
  classificationPath: string[];
  surfaceVerification: {
    status: string;
    existingSurfaceFound: boolean;
    requiresBuildOrWiringReview: boolean;
    surfaceKind: string;
  };
  actionBoundary: {
    conversationCanCreateActionCandidate: boolean;
    conversationCanExecuteAction: boolean;
    conversationCanApproveAction: boolean;
    requiresCodexOrOperatorReviewBeforeImplementation: boolean;
    requiresRepoTruthReview: boolean;
  };
  governance: Record<string, unknown>;
};

export type FrancisTrustLadder = {
  ok: boolean;
  mode: string;
  surface: string;
  items: FrancisTrustLadderItem[];
  count: number;
  summary: {
    allowedDecisions: string[];
    decisionCounts: Record<string, number>;
    requestCount: number;
    requestsWithExistingSurface: number;
    requestsRequiringBuildOrWiringReview: number;
    requestsRequiringPromptGuard: number;
    requestsRejectedAsDrift: number;
    grantsAnyAuthority: boolean;
  };
  filters: Record<string, unknown>;
  definitions: {
    wireExisting: string;
    buildMissing: string;
    tunePromptGuard: string;
    rejectAsDrift: string;
  };
  readbackCache: CollaborationReadbackCache;
  governance: Record<string, unknown>;
};

export type CollaborationSubstrateReadinessChecklistItem = {
  id: string;
  label: string;
  status: string;
  evidence: string;
  detail: string;
  blocksMainBuildPrompt: boolean;
};

export type CollaborationSubstrateReadiness = {
  ok: boolean;
  mode: string;
  surface: string;
  generatedAt: string;
  status: string;
  requiredAlignmentSources: string[];
  summary: {
    collaborationSubstrateWired: boolean;
    boundedWiringPercentComplete: number;
    mainBuildPromptAllowed: boolean;
    mainBuildPromptGate: string;
    coverageOpenGapCount: number;
    trustLadderEnforced: boolean;
    runtimeHealthy: boolean;
    learningReceiptsBounded: boolean;
    noAuthorityGranted: boolean;
  };
  checklist: CollaborationSubstrateReadinessChecklistItem[];
  blockingItems: string[];
  nextAction: string;
  definitions: {
    collaborationSubstrateWired: string;
    mainBuildPromptAllowed: string;
    blockingItems: string;
  };
  sourceReadbacks: Record<string, string>;
  readbackCache: CollaborationReadbackCache;
  governance: Record<string, unknown>;
};

export type CollaborationReadbackCache = {
  status: string;
  ageMs: number | null;
  ttlMs: number | null;
  servesFullTranscriptStore: boolean;
};

type CollaborationReadbackWithItems = {
  count: number;
  items: unknown[];
  readbackCache: CollaborationReadbackCache;
};

export type CollaborationSessionSummary = {
  id: string;
  startedAt: string;
  endedAt: string;
  messageCount: number;
  participants: string[];
  directionCounts: Record<string, number>;
  latestItemId: string;
  latestDirection: string;
  latestObjective: string;
  latestPreview: string;
};

export type CollaborationSessions = {
  ok: boolean;
  mode: string;
  relayRoot: string;
  items: CollaborationSessionSummary[];
  count: number;
  truncated: boolean;
  filters: Record<string, unknown>;
  definitions: {
    session: string;
    latestPreview: string;
  };
  readbackCache: CollaborationReadbackCache;
  governance: Record<string, unknown>;
};

export type CollaborationReviewItem = {
  id: string;
  insightId: string;
  createdAt: string;
  sessionId: string;
  turn: number;
  topic: string;
  finding: string;
  concreteRepoSurface: string;
  reviewArtifact: string;
  surfaceVerification: {
    status: string;
    existingSurfaceFound: boolean;
    requiresBuildOrWiringReview: boolean;
    projectionApplied: boolean;
    surfaceKind: string;
    evidence: string;
    nextCodexAction: string;
  };
  qualityFlags: {
    genericSurface: boolean;
    inventedArtifactHint: boolean;
    loopLanguagePresent: boolean;
    needsRepoTruthReview: boolean;
    safeToImplementWithoutReview: boolean;
  };
  reviewRecommendation: {
    decision: string;
    nextCodexAction: string;
    operatorActionRequired: boolean;
    validatedAgainstRepoTruth: boolean;
    authority: string;
  };
  actionBoundary: {
    conversationCanCreateActionCandidate: boolean;
    conversationCanExecuteAction: boolean;
    conversationCanApproveAction: boolean;
    requiresCodexOrOperatorReviewBeforeImplementation: boolean;
    requiresRepoTruthReview: boolean;
  };
  buildDirectionGate: {
    state: string;
    blocksBuildDirection: boolean;
    requiresTypedReviewArtifact: boolean;
    requiresConflictingSources: boolean;
    requiresCodexOrOperatorReview: boolean;
    requiresRepoTruthReview: boolean;
    conflictingSources: {
      source: string;
      receiptId: string;
      role: string;
      providerLane: string;
    }[];
    surfaceUnderReview: string;
    requiredReviewArtifact: string;
    reason: string;
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
  };
  governance: Record<string, unknown>;
};

export type CollaborationReview = {
  ok: boolean;
  mode: string;
  surface: string;
  items: CollaborationReviewItem[];
  count: number;
  filters: Record<string, unknown>;
  definitions: {
    concreteRepoSurface: string;
    reviewArtifact: string;
    surfaceVerification: string;
    buildDirectionGate: string;
  };
  readbackCache: CollaborationReadbackCache;
  governance: Record<string, unknown>;
};

export type CollaborationLearningRecentTurn = {
  turn: number;
  noteId: string;
  ollamaPromptId: string;
  matchedTerms: string[];
};

export type CollaborationLearningEvent = {
  id: string;
  createdAt: string;
  sessionId: string;
  turn: number;
  latestTurn: number;
  latestObservedAt: string;
  currentSignalObserved: boolean;
  currentSignalRecentTurnCount: number;
  failureType: string;
  observation: string;
  repeatedTerms: string[];
  recentTurnCount: number;
  recentTurns: CollaborationLearningRecentTurn[];
  learning: {
    memoryValue: string;
    operatorIntent: string;
    nextPromptPolicy: string;
  };
  writerGovernance: Record<string, unknown>;
};

export type CollaborationLearning = {
  ok: boolean;
  mode: string;
  surface: string;
  items: CollaborationLearningEvent[];
  count: number;
  truncated: boolean;
  filters: Record<string, unknown>;
  definitions: {
    learningEvent: string;
    failureType: string;
    repeatedTerms: string;
    recentTurns: string;
    latestTurn: string;
  };
  readbackCache: CollaborationReadbackCache;
  governance: Record<string, unknown>;
};

export type CollaborationReviewTone = "ready" | "blocked" | "neutral";

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeBoolean(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function safeNullableNumber(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function parseReadbackCache(raw: unknown): CollaborationReadbackCache {
  const item = isRecord(raw) ? raw : {};
  return {
    status: safeString(item.status, "not_reported"),
    ageMs: safeNullableNumber(item.age_ms),
    ttlMs: safeNullableNumber(item.ttl_ms),
    servesFullTranscriptStore: safeBoolean(item.serves_full_transcript_store),
  };
}

function receiptText(item: CollaborationTranscriptItem): string {
  return item.prompt || item.chatText || "No relay text.";
}

function classifyTranscriptReceipt(objective: string, context: string, prompt: string): CollaborationTranscriptItem["receiptKind"] {
  const normalizedObjective = objective.toLowerCase();
  const normalizedContext = context.toLowerCase();
  const normalizedPrompt = prompt.toLowerCase();
  if (
    normalizedObjective.startsWith("auto-ack ") ||
    normalizedContext.includes("no_response_requested=true") ||
    normalizedPrompt.startsWith("auto-ack ")
  ) {
    return "audit_ack";
  }
  return "conversation";
}

export function isCollaborationAuditReceipt(item: CollaborationTranscriptItem): boolean {
  return item.receiptKind === "audit_ack";
}

export function collaborationTranscriptAuditSummary(items: CollaborationTranscriptItem[]): {
  conversationItems: CollaborationTranscriptItem[];
  auditReceipts: CollaborationTranscriptItem[];
  auditReceiptCount: number;
  totalCount: number;
} {
  const conversationItems: CollaborationTranscriptItem[] = [];
  const auditReceipts: CollaborationTranscriptItem[] = [];
  for (const item of items) {
    if (isCollaborationAuditReceipt(item)) {
      auditReceipts.push(item);
    } else {
      conversationItems.push(item);
    }
  }
  return {
    conversationItems,
    auditReceipts,
    auditReceiptCount: auditReceipts.length,
    totalCount: items.length,
  };
}

function textBetween(value: string, start: string, endMarkers: string[]): string {
  const startIndex = value.indexOf(start);
  if (startIndex < 0) return "";
  const afterStart = startIndex + start.length;
  let endIndex = value.length;
  for (const marker of endMarkers) {
    const markerIndex = value.indexOf(marker, afterStart);
    if (markerIndex >= 0 && markerIndex < endIndex) endIndex = markerIndex;
  }
  return value.slice(afterStart, endIndex).replace(/\s+/g, " ").trim();
}

function firstTextBetween(value: string, starts: string[], endMarkers: string[]): string {
  for (const start of starts) {
    const text = textBetween(value, start, endMarkers);
    if (text) return text;
  }
  return "";
}

function compactGuardFallbackReceipt(raw: string, item: CollaborationTranscriptItem): CollaborationRelayDisplay | null {
  if (!raw.startsWith("Francis1 output guard fallback:")) return null;
  const drift = textBetween(raw, "Drift terms:", [". Topic:", ". Review artifact:", ". Issue/gap/risk:"]);
  const topic = textBetween(raw, "Topic:", [". Review artifact:", ". Issue/gap/risk:"]);
  const artifact = textBetween(raw, "Review artifact:", [". Issue/gap/risk:", ". No execution"]);
  const issue = textBetween(raw, "Issue/gap/risk:", [". No execution", " No execution"]);
  const technicalLines = [
    drift ? `Guard: ${drift}` : "Guard fallback",
    topic ? `Topic: ${topic}` : "",
    artifact ? `Artifact: ${artifact}` : "",
    raw.includes("No execution") ? "Boundary: no execution, mutation, approval, training, or memory-promotion authority" : "",
  ].filter(Boolean);
  const conversationText = issue ? `Issue/gap/risk: ${issue}` : "Model reply was rewritten by the output guard.";
  const technicalText = technicalLines.join("\n");
  return {
    summary: [conversationText, technicalText].filter(Boolean).join("\n"),
    conversationText,
    technicalText,
    tone: "guard",
    raw,
    compacted: true,
    receiptFields: item.context ? ["prompt", "context"] : ["prompt"],
  };
}

export function formatCollaborationRelayMessage(item: CollaborationTranscriptItem): CollaborationRelayDisplay {
  const raw = receiptText(item);
  const guardFallback = compactGuardFallbackReceipt(raw, item);
  if (guardFallback) return guardFallback;

  const isDriverPrompt =
    item.sourceAgent === "codex" &&
    item.targetAgent === "ollama" &&
    item.objective.toLowerCase().startsWith("francis1 collaboration driver turn") &&
    (raw.startsWith("Francis1 collab turn ") || raw.startsWith("Francis1 turn "));
  if (!isDriverPrompt) {
    const technicalText = [item.objective ? `Objective: ${item.objective}` : "", item.context ? `Context: ${item.context}` : ""]
      .filter(Boolean)
      .join("\n");
    return {
      summary: raw,
      conversationText: raw,
      technicalText,
      tone: isCollaborationAuditReceipt(item) ? "audit" : "conversation",
      raw,
      compacted: false,
      receiptFields: raw === item.prompt ? ["prompt"] : ["chat_handoff.chat_text"],
    };
  }

  const turn = firstTextBetween(raw, ["Francis1 collab turn ", "Francis1 turn "], [
    ". Contract",
    ". contract",
    ". francis1-collaboration",
    ". Topic",
  ]);
  const topic = textBetween(raw, "Topic:", [" Reply:", ". Reply:", " Current artifact:", ". Current artifact:"]);
  const bodyMap = textBetween(raw, "Body map:", [" Trust:", ". Trust:", " Current artifact:", ". Current artifact:"]);
  const trust = textBetween(raw, "Trust:", [" Current artifact:", ". Current artifact:", " Prior check:", ". Prior check:"]);
  const artifact = textBetween(raw, "Current artifact:", [". Prior check:", " Prior check:", ". Codex response:", " Codex response:"]);
  const priorCheck = textBetween(raw, "Prior check:", [". Codex response:", " Codex response:", ". Body map:", " Body map:"]);
  const codexResponse = textBetween(raw, "Codex response:", [
    ". Guard note:",
    " Guard note:",
    ". Body map:",
    " Body map:",
    ". Trust:",
    " Trust:",
  ]);
  const guardNote = textBetween(raw, "Guard note:", []);
  const lines = [
    turn ? `Turn ${turn}` : item.objective,
    topic ? `Topic: ${topic}` : "",
    artifact ? `Artifact: ${artifact}` : "",
  ].filter(Boolean);
  const conversationLines = [topic ? `Topic: ${topic}` : "", codexResponse ? `Codex response: ${codexResponse}` : ""].filter(Boolean);
  const technicalLines = [
    turn ? `Turn ${turn}` : item.objective,
    bodyMap ? `Body map: ${bodyMap}` : "",
    trust ? `Trust: ${trust}` : "",
    artifact ? `Artifact: ${artifact}` : "",
    priorCheck ? `Prior check: ${priorCheck}` : "",
    guardNote ? `Guard note: ${guardNote}` : "",
    item.context ? `Context: ${item.context}` : "",
  ].filter(Boolean);

  return {
    summary: lines.length ? lines.join("\n") : raw,
    conversationText: conversationLines.length ? conversationLines.join("\n") : raw,
    technicalText: technicalLines.join("\n"),
    tone: "driver",
    raw,
    compacted: lines.length > 0,
    receiptFields: ["objective", "prompt", "context"],
  };
}

export function preserveCollaborationReadbackDuringWarming<T extends CollaborationReadbackWithItems>(
  previous: T | null,
  next: T,
): T {
  if (!previous || next.readbackCache.status !== "warming") return next;
  if (next.items.length > 0 || next.count > 0) return next;
  if (previous.items.length === 0 && previous.count === 0) return next;
  return {
    ...previous,
    readbackCache: next.readbackCache,
  };
}

export function collaborationReviewTone(item: CollaborationReviewItem): CollaborationReviewTone {
  if (
    item.actionBoundary.conversationCanExecuteAction ||
    item.qualityFlags.safeToImplementWithoutReview ||
    item.qualityFlags.loopLanguagePresent ||
    item.reviewRecommendation.decision === "model_drift_needs_review"
  ) {
    return "blocked";
  }
  if (item.reviewRecommendation.decision === "candidate_for_codex_review") return "ready";
  return "neutral";
}

export function collaborationReviewBadge(item: CollaborationReviewItem): string {
  if (item.qualityFlags.loopLanguagePresent || item.reviewRecommendation.decision === "model_drift_needs_review") {
    return "model drift";
  }
  if (item.reviewRecommendation.validatedAgainstRepoTruth) return "repo checked";
  if (item.reviewRecommendation.decision === "candidate_for_codex_review") return "candidate";
  return "triage";
}

export function collaborationReviewNextAction(item: CollaborationReviewItem): string {
  return (
    item.reviewRecommendation.nextCodexAction ||
    item.surfaceVerification.nextCodexAction ||
    "Inspect the cited review artifact against repo truth before implementation."
  );
}

export function collaborationImplementationReviewSummary(item: CollaborationReviewItem): CollaborationImplementationReviewDisplay {
  const unsafeAuthority =
    item.actionBoundary.conversationCanExecuteAction ||
    item.actionBoundary.conversationCanApproveAction ||
    item.buildDirectionGate.grantsExecutionAuthority ||
    item.buildDirectionGate.grantsMutationAuthority ||
    item.buildDirectionGate.grantsApprovalAuthority ||
    item.buildDirectionGate.grantsMemoryWriteAuthority;
  const artifact = item.buildDirectionGate.requiredReviewArtifact || item.reviewArtifact || "unknown";
  const surface = item.buildDirectionGate.surfaceUnderReview || item.concreteRepoSurface || "unknown";
  return {
    badge: unsafeAuthority
      ? "authority drift"
      : item.buildDirectionGate.blocksBuildDirection
        ? "build blocked"
        : "read before editing",
    tone: unsafeAuthority || item.buildDirectionGate.blocksBuildDirection ? "blocked" : "ready",
    artifact,
    surface,
    nextAction: collaborationReviewNextAction(item),
    detail: [
      `turn ${item.turn || "unknown"}`,
      `gate ${item.buildDirectionGate.state || "advisory_review_required"}`,
      `typed artifact ${actionBoundaryBool(item.buildDirectionGate.requiresTypedReviewArtifact)}`,
      `codex review ${actionBoundaryBool(item.buildDirectionGate.requiresCodexOrOperatorReview)}`,
      `repo review ${actionBoundaryBool(item.buildDirectionGate.requiresRepoTruthReview)}`,
      `execute ${actionBoundaryBool(item.actionBoundary.conversationCanExecuteAction || item.buildDirectionGate.grantsExecutionAuthority)}`,
      `approve ${actionBoundaryBool(item.actionBoundary.conversationCanApproveAction || item.buildDirectionGate.grantsApprovalAuthority)}`,
      `memory write ${actionBoundaryBool(item.buildDirectionGate.grantsMemoryWriteAuthority)}`,
    ],
  };
}

export function collaborationBuildDirectionGateSummary(item: CollaborationReviewItem): CollaborationBuildDirectionGateDisplay {
  const gate = item.buildDirectionGate;
  const unsafeAuthority =
    gate.grantsExecutionAuthority ||
    gate.grantsMutationAuthority ||
    gate.grantsApprovalAuthority ||
    gate.grantsMemoryWriteAuthority ||
    item.actionBoundary.conversationCanExecuteAction ||
    item.actionBoundary.conversationCanApproveAction;
  const artifact = gate.requiredReviewArtifact || item.reviewArtifact || "unknown";
  const surface = gate.surfaceUnderReview || item.concreteRepoSurface || "unknown";
  const reason =
    gate.reason ||
    (gate.blocksBuildDirection
      ? "Typed review is required before this can become build direction."
      : "Collaboration output remains advisory until reviewed against repo truth.");
  const conflictingSourceLines = gate.conflictingSources.length
    ? gate.conflictingSources.map((source) => {
        const sourceName = source.source || "unknown source";
        const receipt = source.receiptId || "missing receipt";
        const role = source.role || "unspecified role";
        const provider = source.providerLane ? ` / provider ${source.providerLane}` : "";
        return `${sourceName}: ${receipt} / ${role}${provider}`;
      })
    : ["No conflicting source receipts recorded."];
  return {
    badge: unsafeAuthority ? "authority drift" : gate.blocksBuildDirection ? "source disagreement blocked" : "advisory gate",
    tone: unsafeAuthority || gate.blocksBuildDirection ? "blocked" : "ready",
    artifact,
    surface,
    reason,
    detail: [
      `gate ${gate.state || "advisory_review_required"}`,
      `typed artifact ${actionBoundaryBool(gate.requiresTypedReviewArtifact)}`,
      `conflicting sources ${actionBoundaryBool(gate.requiresConflictingSources)}`,
      `source receipts ${gate.conflictingSources.length}`,
      `codex review ${actionBoundaryBool(gate.requiresCodexOrOperatorReview)}`,
      `repo review ${actionBoundaryBool(gate.requiresRepoTruthReview)}`,
      `execute ${actionBoundaryBool(item.actionBoundary.conversationCanExecuteAction || gate.grantsExecutionAuthority)}`,
      `approve ${actionBoundaryBool(item.actionBoundary.conversationCanApproveAction || gate.grantsApprovalAuthority)}`,
      `memory write ${actionBoundaryBool(gate.grantsMemoryWriteAuthority)}`,
    ],
    conflictingSourceLines,
  };
}

function actionBoundaryBool(value: boolean): string {
  return value ? "true" : "false";
}

export function collaborationActionBoundarySummary(item: CollaborationReviewItem): CollaborationActionBoundaryDisplay {
  const boundary = item.actionBoundary;
  const unsafeAuthority = boundary.conversationCanExecuteAction || boundary.conversationCanApproveAction;
  return {
    badge: unsafeAuthority ? "action authority visible" : "advice only",
    tone: unsafeAuthority ? "blocked" : "ready",
    detail: [
      `candidate ${actionBoundaryBool(boundary.conversationCanCreateActionCandidate)}`,
      `execute ${actionBoundaryBool(boundary.conversationCanExecuteAction)}`,
      `approve ${actionBoundaryBool(boundary.conversationCanApproveAction)}`,
      `codex review ${actionBoundaryBool(boundary.requiresCodexOrOperatorReviewBeforeImplementation)}`,
      `repo review ${actionBoundaryBool(boundary.requiresRepoTruthReview)}`,
    ],
  };
}

export function collaborationActionIntakeSummary(item: CollaborationReviewItem): CollaborationActionIntakeDisplay {
  const surface = item.concreteRepoSurface || item.buildDirectionGate.surfaceUnderReview || "";
  const surfaceKind = item.surfaceVerification.surfaceKind || "";
  const applies =
    surfaceKind === "mission_ingress_action_boundary" ||
    surface.includes("mission_ingress") ||
    surface.includes("api.routes.chat");
  if (!applies) {
    return {
      applies: false,
      badge: "",
      tone: "neutral",
      detail: [],
    };
  }
  const boundary = item.actionBoundary;
  const unsafeAuthority = boundary.conversationCanExecuteAction || boundary.conversationCanApproveAction;
  return {
    applies: true,
    badge: unsafeAuthority ? "action authority visible" : "action candidate only",
    tone: unsafeAuthority ? "blocked" : "ready",
    detail: [
      `surface ${surface || "unknown"}`,
      `candidate ${actionBoundaryBool(boundary.conversationCanCreateActionCandidate)}`,
      `execute ${actionBoundaryBool(boundary.conversationCanExecuteAction)}`,
      `approve ${actionBoundaryBool(boundary.conversationCanApproveAction)}`,
      `repo review ${actionBoundaryBool(boundary.requiresRepoTruthReview)}`,
      `gate ${item.buildDirectionGate.state || "advisory_review_required"}`,
    ],
  };
}

function ageText(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "unknown";
  return `${Math.max(0, Math.round(value))}s`;
}

export function collaborationRuntimeRecurrenceSummary(
  health: CollaborationRuntimeHealth | null | undefined,
): CollaborationRuntimeRecurrenceDisplay {
  if (!health) {
    return {
      badge: "runtime unknown",
      tone: "neutral",
      detail: [
        "status unknown",
        "helpers 0/0",
        "workers 0/0",
        "process model unknown",
        "loop observed false",
        "turn 0",
        "state unknown",
        "waiting for ollama false",
        "driver age unknown",
        "supervisor age unknown",
        "authority none false",
      ],
    };
  }

  const runningHelpers = health.helpers.filter((helper) => helper.running).length;
  const expectedHelpers = health.desiredCount || health.helperCount || health.helpers.length;
  const effectiveWorkers = health.helpers.reduce((sum, helper) => sum + Math.max(0, helper.effectiveWorkerCount), 0);
  const helpersReady =
    expectedHelpers > 0 &&
    runningHelpers >= expectedHelpers &&
    effectiveWorkers >= expectedHelpers &&
    health.helpers.every((helper) => !helper.running || helper.effectiveWorkerCount > 0);
  const processModels = [...new Set(health.helpers.map((helper) => helper.processModel).filter(Boolean))];
  const processModelLabel = processModels.length === 1 ? processModels[0] : processModels.length > 1 ? processModels.join(",") : "unknown";
  const loopFresh = typeof health.collaborationLoop.ageSeconds === "number" && health.collaborationLoop.ageSeconds <= 90;
  const supervisorFresh = typeof health.supervisor.ageSeconds === "number" && health.supervisor.ageSeconds <= 120;
  const loopActive =
    health.collaborationLoop.stateObserved &&
    health.collaborationLoop.turnCount > 0 &&
    Boolean(
      health.collaborationLoop.recurrenceState ||
        health.collaborationLoop.lastCodexPromptId ||
        health.collaborationLoop.lastOllamaPromptId,
    );
  const authorityNone =
    !safeBoolean(health.governance.starts_arbitrary_commands) &&
    !safeBoolean(health.governance.grants_model_execution_authority) &&
    !safeBoolean(health.governance.grants_repo_mutation_authority) &&
    !safeBoolean(health.governance.grants_approval_authority) &&
    !safeBoolean(health.governance.grants_memory_write_authority);
  const recurringCleanly = health.status === "healthy" && helpersReady && loopFresh && supervisorFresh && loopActive && authorityNone;

  return {
    badge: recurringCleanly ? "recurring cleanly" : "recurrence needs review",
    tone: recurringCleanly ? "ready" : health.status === "healthy" && authorityNone ? "neutral" : "blocked",
    detail: [
      `status ${health.status || "unknown"}`,
      `helpers ${runningHelpers}/${expectedHelpers}`,
      `workers ${effectiveWorkers}/${expectedHelpers}`,
      `process model ${processModelLabel}`,
      `loop observed ${actionBoundaryBool(health.collaborationLoop.stateObserved)}`,
      `turn ${health.collaborationLoop.turnCount}`,
      `state ${health.collaborationLoop.recurrenceState || "unknown"}`,
      `waiting for ollama ${actionBoundaryBool(health.collaborationLoop.waitingForOllama)}`,
      `turn gap ${Math.max(0, Math.round(health.collaborationLoop.turnGapRemainingSeconds || 0))}s`,
      `driver age ${ageText(health.collaborationLoop.ageSeconds)}`,
      `supervisor age ${ageText(health.supervisor.ageSeconds)}`,
      `authority none ${actionBoundaryBool(authorityNone)}`,
    ],
  };
}

export function collaborationRuntimeReviewReceiptSummary(
  health: CollaborationRuntimeHealth | null | undefined,
): CollaborationRuntimeReviewReceiptDisplay {
  const receipt = health?.collaborationLoop.latestReviewReceipt;
  if (!receipt?.observed) {
    return {
      badge: "review receipt unknown",
      tone: "neutral",
      detail: [
        "insight unknown",
        "review item unknown",
        "artifact unknown",
        "route /developer-bridge/collaboration-review",
        "codex review true",
        "execute false",
        "approve false",
        "memory write false",
      ],
    };
  }
  const unsafeAuthority =
    receipt.grantsExecutionAuthority ||
    receipt.grantsMutationAuthority ||
    receipt.grantsApprovalAuthority ||
    receipt.grantsMemoryWriteAuthority;
  return {
    badge: unsafeAuthority ? "review authority drift" : "read before editing",
    tone: unsafeAuthority ? "blocked" : "ready",
    detail: [
      `insight ${receipt.insightId}`,
      `review item ${receipt.reviewItemId}`,
      `artifact ${receipt.reviewArtifact}`,
      `route ${receipt.reviewRoute}`,
      `codex review ${actionBoundaryBool(receipt.requiresCodexOrOperatorReviewBeforeImplementation)}`,
      `execute ${actionBoundaryBool(receipt.grantsExecutionAuthority)}`,
      `approve ${actionBoundaryBool(receipt.grantsApprovalAuthority)}`,
      `memory write ${actionBoundaryBool(receipt.grantsMemoryWriteAuthority)}`,
    ],
  };
}

export function collaborationRuntimeLearningReceiptSummary(
  health: CollaborationRuntimeHealth | null | undefined,
): CollaborationRuntimeLearningReceiptDisplay {
  const receipt = health?.collaborationLoop.latestLearningReceipt;
  if (!receipt?.observed) {
    return {
      badge: "learning receipt unknown",
      tone: "neutral",
      detail: [
        "learning event unknown",
        "artifact unknown",
        "route /developer-bridge/collaboration-learning",
        "drift learning true",
        "tuning review true",
        "training false",
        "memory write false",
      ],
    };
  }
  const unsafeAuthority =
    receipt.storesFullTranscript ||
    receipt.grantsTrainingAuthority ||
    receipt.grantsExecutionAuthority ||
    receipt.grantsMutationAuthority ||
    receipt.grantsApprovalAuthority ||
    receipt.grantsMemoryWriteAuthority;
  return {
    badge: unsafeAuthority ? "learning authority drift" : "tuning evidence",
    tone: unsafeAuthority ? "blocked" : "ready",
    detail: [
      `learning event ${receipt.learningEventId}`,
      `artifact ${receipt.learningArtifact}`,
      `route ${receipt.learningRoute}`,
      `drift learning ${actionBoundaryBool(receipt.recordsModelDriftAsLearning)}`,
      `tuning review ${actionBoundaryBool(receipt.requiresCodexOrOperatorReviewBeforeTuning)}`,
      `training ${actionBoundaryBool(receipt.grantsTrainingAuthority)}`,
      `memory write ${actionBoundaryBool(receipt.grantsMemoryWriteAuthority)}`,
    ],
  };
}

export function collaborationRuntimeLearningSignalSummary(
  health: CollaborationRuntimeHealth | null | undefined,
): CollaborationRuntimeLearningSignalDisplay {
  const signal = health?.collaborationLoop.currentLearningSignal;
  if (!signal?.observed) {
    return {
      badge: "learning signal quiet",
      tone: "neutral",
      detail: [
        "failure none",
        "latest turn 0",
        "recent turns 0",
        "terms none",
        "receipt unknown",
        "training false",
        "memory write false",
      ],
    };
  }
  const unsafeAuthority =
    signal.storesFullTranscript ||
    signal.grantsTrainingAuthority ||
    signal.grantsExecutionAuthority ||
    signal.grantsMutationAuthority ||
    signal.grantsApprovalAuthority ||
    signal.grantsMemoryWriteAuthority;
  return {
    badge: unsafeAuthority ? "learning signal authority drift" : "current drift signal",
    tone: unsafeAuthority ? "blocked" : "ready",
    detail: [
      `failure ${signal.failureType || "unknown"}`,
      `latest turn ${signal.latestTurn}`,
      `recent turns ${signal.recentTurnCount}`,
      `terms ${signal.repeatedTerms.length ? signal.repeatedTerms.join(",") : "none"}`,
      `receipt ${signal.learningEventId || "unknown"}`,
      `training ${actionBoundaryBool(signal.grantsTrainingAuthority)}`,
      `memory write ${actionBoundaryBool(signal.grantsMemoryWriteAuthority)}`,
    ],
  };
}

function parseAgent(raw: unknown): CollaborationAgent {
  const item = isRecord(raw) ? raw : {};
  return {
    agent: safeString(item.agent, "unknown"),
    label: safeString(item.label, safeString(item.agent, "unknown")),
    enabled: safeBoolean(item.enabled),
    participantKind: safeString(item.participant_kind),
    localRunner: safeString(item.local_runner),
    authority: safeString(item.authority),
    updatedAt: safeString(item.updated_at),
    updatedBy: safeString(item.updated_by),
    reason: safeString(item.reason),
    writesRelayReceipts: safeBoolean(item.writes_relay_receipts),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
  };
}

function parseAgentToggleReceipt(raw: unknown): CollaborationAgentToggleReceipt {
  const item = isRecord(raw) ? raw : {};
  return {
    kind: safeString(item.kind, "developer_bridge.collaboration_agent_toggle_receipt"),
    receiptId: safeString(item.receipt_id),
    createdAt: safeString(item.created_at),
    agent: safeString(item.agent, "unknown"),
    enabled: safeBoolean(item.enabled),
    previousEnabled: safeBoolean(item.previous_enabled),
    actor: safeString(item.actor),
    reason: safeString(item.reason),
    governance: isRecord(item.governance) ? item.governance : {},
  };
}

function parseRuntimeHelper(raw: unknown): CollaborationRuntimeHelper {
  const item = isRecord(raw) ? raw : {};
  const pids = Array.isArray(item.pids) ? item.pids.map((pid) => safeNumber(pid)).filter((pid) => pid > 0) : [];
  const effectivePids = Array.isArray(item.effective_pids)
    ? item.effective_pids.map((pid) => safeNumber(pid)).filter((pid) => pid > 0)
    : pids.length === 1
      ? pids
      : [];
  const wrapperPids = Array.isArray(item.wrapper_pids)
    ? item.wrapper_pids.map((pid) => safeNumber(pid)).filter((pid) => pid > 0)
    : [];
  return {
    name: safeString(item.name),
    status: safeString(item.status, "unknown"),
    running: safeBoolean(item.running),
    pids,
    processCount: safeNumber(item.process_count, pids.length),
    processModel: safeString(item.process_model, pids.length ? "legacy_unclassified" : "unmatched"),
    effectiveWorkerCount: safeNumber(item.effective_worker_count, effectivePids.length),
    effectivePids,
    wrapperProcessCount: safeNumber(item.wrapper_process_count, wrapperPids.length),
    wrapperPids,
    processes: Array.isArray(item.processes)
      ? item.processes.map((process) => {
          const processItem = isRecord(process) ? process : {};
          return {
            pid: safeNumber(processItem.pid),
            parentPid: safeNumber(processItem.parent_pid),
            role: safeString(processItem.role, "unknown"),
          };
        })
      : [],
    logPath: safeString(item.log_path),
    startsArbitraryCommands: safeBoolean(item.starts_arbitrary_commands),
  };
}

function parseTranscriptItem(raw: unknown): CollaborationTranscriptItem {
  const item = isRecord(raw) ? raw : {};
  const handoff = isRecord(item.chat_handoff) ? item.chat_handoff : {};
  const objective = safeString(item.objective);
  const prompt = safeString(item.prompt);
  const context = safeString(item.context);
  return {
    id: safeString(item.id),
    createdAt: safeString(item.created_at),
    updatedAt: safeString(item.updated_at),
    status: safeString(item.status),
    sourceAgent: safeString(item.source_agent),
    targetAgent: safeString(item.target_agent),
    direction: safeString(item.direction),
    objective,
    prompt,
    context,
    chatText: safeString(handoff.chat_text),
    receiptKind: classifyTranscriptReceipt(objective, context, prompt),
    sourceChatEchoRequired: safeBoolean(handoff.source_chat_echo_required),
    targetChatEchoRequired: safeBoolean(handoff.target_chat_echo_required),
    governance: isRecord(item.governance) ? item.governance : {},
  };
}

function parseReviewItem(raw: unknown): CollaborationReviewItem {
  const item = isRecord(raw) ? raw : {};
  const quality = isRecord(item.quality_flags) ? item.quality_flags : {};
  const verification = isRecord(item.surface_verification) ? item.surface_verification : {};
  const recommendation = isRecord(item.review_recommendation) ? item.review_recommendation : {};
  const boundary = isRecord(item.action_boundary) ? item.action_boundary : {};
  const buildGate = isRecord(item.build_direction_gate) ? item.build_direction_gate : {};
  return {
    id: safeString(item.id),
    insightId: safeString(item.insight_id),
    createdAt: safeString(item.created_at),
    sessionId: safeString(item.session_id),
    turn: safeNumber(item.turn),
    topic: safeString(item.topic),
    finding: safeString(item.finding),
    concreteRepoSurface: safeString(item.concrete_repo_surface),
    reviewArtifact: safeString(item.review_artifact),
    surfaceVerification: {
      status: safeString(verification.status, "unknown"),
      existingSurfaceFound: safeBoolean(verification.existing_surface_found),
      requiresBuildOrWiringReview: safeBoolean(verification.requires_build_or_wiring_review),
      projectionApplied: safeBoolean(verification.projection_applied),
      surfaceKind: safeString(verification.surface_kind),
      evidence: safeString(verification.evidence),
      nextCodexAction: safeString(verification.next_codex_action),
    },
    qualityFlags: {
      genericSurface: safeBoolean(quality.generic_surface),
      inventedArtifactHint: safeBoolean(quality.invented_artifact_hint),
      loopLanguagePresent: safeBoolean(quality.loop_language_present),
      needsRepoTruthReview: safeBoolean(quality.needs_repo_truth_review),
      safeToImplementWithoutReview: safeBoolean(quality.safe_to_implement_without_review),
    },
    reviewRecommendation: {
      decision: safeString(recommendation.decision, "unknown"),
      nextCodexAction: safeString(recommendation.next_codex_action),
      operatorActionRequired: safeBoolean(recommendation.operator_action_required),
      validatedAgainstRepoTruth: safeBoolean(recommendation.validated_against_repo_truth),
      authority: safeString(recommendation.authority),
    },
    actionBoundary: {
      conversationCanCreateActionCandidate: safeBoolean(boundary.conversation_can_create_action_candidate),
      conversationCanExecuteAction: safeBoolean(boundary.conversation_can_execute_action),
      conversationCanApproveAction: safeBoolean(boundary.conversation_can_approve_action),
      requiresCodexOrOperatorReviewBeforeImplementation: safeBoolean(
        boundary.requires_codex_or_operator_review_before_implementation,
      ),
      requiresRepoTruthReview: safeBoolean(boundary.requires_repo_truth_review),
    },
    buildDirectionGate: {
      state: safeString(buildGate.state, "advisory_review_required"),
      blocksBuildDirection: safeBoolean(buildGate.blocks_build_direction),
      requiresTypedReviewArtifact: safeBoolean(buildGate.requires_typed_review_artifact),
      requiresConflictingSources: safeBoolean(buildGate.requires_conflicting_sources),
      requiresCodexOrOperatorReview: safeBoolean(buildGate.requires_codex_or_operator_review),
      requiresRepoTruthReview: safeBoolean(buildGate.requires_repo_truth_review),
      conflictingSources: Array.isArray(buildGate.conflicting_sources)
        ? buildGate.conflicting_sources.map((source) => {
            const sourceRecord = isRecord(source) ? source : {};
            return {
              source: safeString(sourceRecord.source),
              receiptId: safeString(sourceRecord.receipt_id),
              role: safeString(sourceRecord.role),
              providerLane: safeString(sourceRecord.provider_lane),
            };
          })
        : [],
      surfaceUnderReview: safeString(buildGate.surface_under_review),
      requiredReviewArtifact: safeString(buildGate.required_review_artifact),
      reason: safeString(buildGate.reason),
      grantsExecutionAuthority: safeBoolean(buildGate.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(buildGate.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(buildGate.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(buildGate.grants_memory_write_authority),
    },
    governance: isRecord(item.governance) ? item.governance : {},
  };
}

function parseLearningRecentTurn(raw: unknown): CollaborationLearningRecentTurn {
  const item = isRecord(raw) ? raw : {};
  return {
    turn: safeNumber(item.turn),
    noteId: safeString(item.note_id),
    ollamaPromptId: safeString(item.ollama_prompt_id),
    matchedTerms: Array.isArray(item.matched_terms) ? item.matched_terms.map((term) => safeString(term)).filter(Boolean) : [],
  };
}

function parseLearningEvent(raw: unknown): CollaborationLearningEvent {
  const item = isRecord(raw) ? raw : {};
  const learning = isRecord(item.learning) ? item.learning : {};
  return {
    id: safeString(item.id),
    createdAt: safeString(item.created_at),
    sessionId: safeString(item.session_id),
    turn: safeNumber(item.turn),
    latestTurn: safeNumber(item.latest_turn),
    latestObservedAt: safeString(item.latest_observed_at),
    currentSignalObserved: safeBoolean(item.current_signal_observed),
    currentSignalRecentTurnCount: safeNumber(item.current_signal_recent_turn_count),
    failureType: safeString(item.failure_type),
    observation: safeString(item.observation),
    repeatedTerms: Array.isArray(item.repeated_terms)
      ? item.repeated_terms.map((term) => safeString(term)).filter(Boolean)
      : [],
    recentTurnCount: safeNumber(item.recent_turn_count),
    recentTurns: Array.isArray(item.recent_turns) ? item.recent_turns.map(parseLearningRecentTurn) : [],
    learning: {
      memoryValue: safeString(learning.memory_value),
      operatorIntent: safeString(learning.operator_intent),
      nextPromptPolicy: safeString(learning.next_prompt_policy),
    },
    writerGovernance: isRecord(item.writer_governance) ? item.writer_governance : {},
  };
}

function parseSessionSummary(raw: unknown): CollaborationSessionSummary {
  const item = isRecord(raw) ? raw : {};
  const directionCounts = isRecord(item.direction_counts) ? item.direction_counts : {};
  const parsedDirectionCounts: Record<string, number> = {};
  for (const [direction, count] of Object.entries(directionCounts)) {
    parsedDirectionCounts[direction] = safeNumber(count);
  }
  return {
    id: safeString(item.id),
    startedAt: safeString(item.started_at),
    endedAt: safeString(item.ended_at),
    messageCount: safeNumber(item.message_count),
    participants: Array.isArray(item.participants) ? item.participants.map((participant) => safeString(participant)) : [],
    directionCounts: parsedDirectionCounts,
    latestItemId: safeString(item.latest_item_id),
    latestDirection: safeString(item.latest_direction),
    latestObjective: safeString(item.latest_objective),
    latestPreview: safeString(item.latest_preview),
  };
}

function parseFrancisBodySurface(raw: unknown): FrancisBodySurface {
  const item = isRecord(raw) ? raw : {};
  return {
    id: safeString(item.id),
    label: safeString(item.label),
    description: safeString(item.description),
    connectionState: safeString(item.connection_state, "unknown"),
    accessMode: safeString(item.access_mode, "observe"),
    trustRequiredForNextMode: safeString(item.trust_required_for_next_mode),
    evidence: Array.isArray(item.evidence)
      ? item.evidence.map((entry) => {
          const evidence = isRecord(entry) ? entry : {};
          return {
            path: safeString(evidence.path),
            observed: safeBoolean(evidence.observed),
          };
        })
      : [],
    currentBoundary: safeString(item.current_boundary),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority),
  };
}

function parseFrancisBodyCoverageItem(raw: unknown): FrancisBodyCoverageItem {
  const item = isRecord(raw) ? raw : {};
  return {
    planeId: safeString(item.plane_id),
    planeName: safeString(item.plane_name),
    bodySurfaceId: safeString(item.body_surface_id),
    currentPosture: safeString(item.current_posture),
    connectionState: safeString(item.connection_state, "unknown"),
    accessMode: safeString(item.access_mode, "observe"),
    riskLevel: safeString(item.risk_level, "unknown"),
    riskStatement: safeString(item.risk_statement),
    nextReviewArtifact: safeString(item.next_review_artifact),
    recommendedNextAction: safeString(item.recommended_next_action),
    validationHint: safeString(item.validation_hint),
    evidence: Array.isArray(item.evidence)
      ? item.evidence.map((entry) => {
          const evidence = isRecord(entry) ? entry : {};
          return {
            path: safeString(evidence.path),
            observed: safeBoolean(evidence.observed),
          };
        })
      : [],
    remainingGaps: Array.isArray(item.remaining_gaps) ? item.remaining_gaps.map((gap) => safeString(gap)).filter(Boolean) : [],
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority),
  };
}

export function parseCollaborationAgentsStatus(raw: unknown): CollaborationAgentsStatus {
  const value = isRecord(raw) ? raw : {};
  const operatorConsole = isRecord(value.operator_console) ? value.operator_console : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    relay: safeString(value.relay),
    agents: Array.isArray(value.agents) ? value.agents.map(parseAgent) : [],
    receipts: Array.isArray(value.receipts) ? value.receipts.map(parseAgentToggleReceipt) : [],
    operatorConsole: {
      surface: safeString(operatorConsole.surface),
      actor: safeString(operatorConsole.actor),
      clientCanBeOperatorConsole: safeBoolean(operatorConsole.client_can_be_operator_console),
      clientIsAutomaticExecutionAuthority: safeBoolean(operatorConsole.client_is_automatic_execution_authority),
    },
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

export function parseFrancisBodyMap(raw: unknown): FrancisBodyMap {
  const value = isRecord(raw) ? raw : {};
  const identity = isRecord(value.identity) ? value.identity : {};
  const phase = isRecord(value.phase) ? value.phase : {};
  const summary = isRecord(value.summary) ? value.summary : {};
  const quest = isRecord(value.quest) ? value.quest : {};
  const evidence = isRecord(value.evidence) ? value.evidence : {};
  const coverageReview = isRecord(value.coverage_review) ? value.coverage_review : {};
  const runtimeObservation = isRecord(value.runtime_observation) ? value.runtime_observation : {};
  const trustLadder = isRecord(value.trust_ladder) ? value.trust_ladder : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    surface: safeString(value.surface),
    generatedAt: safeString(value.generated_at),
    identity: {
      localIdentity: safeString(identity.local_identity),
      providerLane: safeString(identity.provider_lane),
      providerNameIsIdentity: safeBoolean(identity.provider_name_is_identity),
      codexRole: safeString(identity.codex_role),
      claudeRole: safeString(identity.claude_role),
      francisRole: safeString(identity.francis_role),
    },
    phase: {
      current: safeString(phase.current),
      source: safeString(phase.source),
      posture: safeString(phase.posture),
      priority: safeString(phase.priority),
    },
    accessLadder: Array.isArray(value.access_ladder) ? value.access_ladder.map((item) => safeString(item)).filter(Boolean) : [],
    surfaces: Array.isArray(value.surfaces) ? value.surfaces.map(parseFrancisBodySurface) : [],
    summary: {
      surfaceCount: safeNumber(summary.surface_count),
      connectedOrPartialCount: safeNumber(summary.connected_or_partial_count),
      candidateCount: safeNumber(summary.candidate_count),
      blockedCount: safeNumber(summary.blocked_count),
      unknownCount: safeNumber(summary.unknown_count),
      defaultAccessMode: safeString(summary.default_access_mode, "observe"),
      fullBodyVisible: safeBoolean(summary.full_body_visible),
      fullBodyAuthorityGranted: safeBoolean(summary.full_body_authority_granted),
      trustLadderEnforced: safeBoolean(summary.trust_ladder_enforced),
      runtimeRestartObserved: safeBoolean(summary.runtime_restart_observed),
      coverageReviewed: safeBoolean(summary.coverage_reviewed),
      canonicalPlaneCount: safeNumber(summary.canonical_plane_count),
      canonicalPlaneCoveredCount: safeNumber(summary.canonical_plane_covered_count),
      coverageOpenGapCount: safeNumber(summary.coverage_open_gap_count),
    },
    quest: {
      id: safeString(quest.id),
      title: safeString(quest.title),
      estimatedTimeline: safeString(quest.estimated_timeline),
      singleTimeline: Array.isArray(quest.single_timeline)
        ? quest.single_timeline.map((entry) => {
            const item = isRecord(entry) ? entry : {};
            return {
              order: safeNumber(item.order),
              label: safeString(item.label),
              targetDuration: safeString(item.target_duration),
              expectedStatusAfterThisSlice: safeString(item.expected_status_after_this_slice),
            };
          })
        : [],
      steps: Array.isArray(quest.steps)
        ? quest.steps.map((entry) => {
            const item = isRecord(entry) ? entry : {};
            return {
              id: safeString(item.id),
              label: safeString(item.label),
              status: safeString(item.status),
              evidence: safeString(item.evidence),
            };
          })
        : [],
      completedSteps: safeNumber(quest.completed_steps),
      totalSteps: safeNumber(quest.total_steps),
      percentComplete: safeNumber(quest.percent_complete),
      percentBaseline: safeString(quest.percent_baseline),
      remaining: Array.isArray(quest.remaining) ? quest.remaining.map((item) => safeString(item)).filter(Boolean) : [],
    },
    evidence: {
      manifestObserved: safeBoolean(evidence.manifest_observed),
      ledgerObserved: safeBoolean(evidence.ledger_observed),
      trustLadderObserved: safeBoolean(evidence.trust_ladder_observed),
      runtimeRestartObserved: safeBoolean(evidence.runtime_restart_observed),
      bodyCoverageReviewObserved: safeBoolean(evidence.body_coverage_review_observed),
      canonicalPlaneCount: safeNumber(evidence.canonical_plane_count),
      canonicalPlaneCoveredCount: safeNumber(evidence.canonical_plane_covered_count),
      missingCanonicalPlaneIds: Array.isArray(evidence.missing_canonical_plane_ids)
        ? evidence.missing_canonical_plane_ids.map((item) => safeString(item)).filter(Boolean)
        : [],
      coverageOpenGapCount: safeNumber(evidence.coverage_open_gap_count),
      latestRuntimePromptId: safeString(evidence.latest_runtime_prompt_id),
      latestRuntimeResponseId: safeString(evidence.latest_runtime_response_id),
      latestLedgerEntry: safeString(evidence.latest_ledger_entry),
    },
    coverageReview: {
      kind: safeString(coverageReview.kind),
      schemaVersion: safeString(coverageReview.schema_version),
      surface: safeString(coverageReview.surface),
      observed: safeBoolean(coverageReview.observed),
      status: safeString(coverageReview.status, "unknown"),
      coverageComplete: safeBoolean(coverageReview.coverage_complete),
      capabilityComplete: safeBoolean(coverageReview.capability_complete),
      canonicalSource: safeString(coverageReview.canonical_source),
      canonicalSourcesObserved: safeBoolean(coverageReview.canonical_sources_observed),
      planeCount: safeNumber(coverageReview.plane_count),
      coveredPlaneCount: safeNumber(coverageReview.covered_plane_count),
      missingPlaneIds: Array.isArray(coverageReview.missing_plane_ids)
        ? coverageReview.missing_plane_ids.map((item) => safeString(item)).filter(Boolean)
        : [],
      openGapCount: safeNumber(coverageReview.open_gap_count),
      items: Array.isArray(coverageReview.items) ? coverageReview.items.map(parseFrancisBodyCoverageItem) : [],
      grantsExecutionAuthority: safeBoolean(coverageReview.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(coverageReview.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(coverageReview.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(coverageReview.grants_memory_write_authority),
      grantsTrainingAuthority: safeBoolean(coverageReview.grants_training_authority),
    },
    runtimeObservation: {
      observed: safeBoolean(runtimeObservation.observed),
      promptObserved: safeBoolean(runtimeObservation.prompt_observed),
      responseObserved: safeBoolean(runtimeObservation.response_observed),
      promptId: safeString(runtimeObservation.prompt_id),
      responseId: safeString(runtimeObservation.response_id),
      outputGuardRewriteObserved: safeBoolean(runtimeObservation.output_guard_rewrite_observed),
      storesFullTranscript: safeBoolean(runtimeObservation.stores_full_transcript),
      grantsExecutionAuthority: safeBoolean(runtimeObservation.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(runtimeObservation.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(runtimeObservation.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(runtimeObservation.grants_memory_write_authority),
      grantsTrainingAuthority: safeBoolean(runtimeObservation.grants_training_authority),
    },
    trustLadder: {
      surface: safeString(trustLadder.surface),
      route: safeString(trustLadder.route),
      mcpTool: safeString(trustLadder.mcp_tool),
      connected: safeBoolean(trustLadder.connected),
      decisionContract: Array.isArray(trustLadder.decision_contract)
        ? trustLadder.decision_contract.map((item) => safeString(item)).filter(Boolean)
        : [],
      grantsExecutionAuthority: safeBoolean(trustLadder.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(trustLadder.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(trustLadder.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(trustLadder.grants_memory_write_authority),
      grantsTrainingAuthority: safeBoolean(trustLadder.grants_training_authority),
    },
    readbackCache: parseReadbackCache(value.readback_cache),
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

export function parseFrancisTrustLadder(raw: unknown): FrancisTrustLadder {
  const value = isRecord(raw) ? raw : {};
  const summary = isRecord(value.summary) ? value.summary : {};
  const definitions = isRecord(value.definitions) ? value.definitions : {};
  const decisionCounts = isRecord(summary.decision_counts) ? summary.decision_counts : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    surface: safeString(value.surface),
    items: Array.isArray(value.items) ? value.items.map(parseFrancisTrustLadderItem) : [],
    count: safeNumber(value.count),
    summary: {
      allowedDecisions: Array.isArray(summary.allowed_decisions)
        ? summary.allowed_decisions.map((item) => safeString(item)).filter(Boolean)
        : [],
      decisionCounts: Object.fromEntries(
        Object.entries(decisionCounts).map(([key, count]) => [key, safeNumber(count)]),
      ),
      requestCount: safeNumber(summary.request_count),
      requestsWithExistingSurface: safeNumber(summary.requests_with_existing_surface),
      requestsRequiringBuildOrWiringReview: safeNumber(summary.requests_requiring_build_or_wiring_review),
      requestsRequiringPromptGuard: safeNumber(summary.requests_requiring_prompt_guard),
      requestsRejectedAsDrift: safeNumber(summary.requests_rejected_as_drift),
      grantsAnyAuthority: safeBoolean(summary.grants_any_authority),
    },
    filters: isRecord(value.filters) ? value.filters : {},
    definitions: {
      wireExisting: safeString(definitions.wire_existing),
      buildMissing: safeString(definitions.build_missing),
      tunePromptGuard: safeString(definitions.tune_prompt_guard),
      rejectAsDrift: safeString(definitions.reject_as_drift),
    },
    readbackCache: parseReadbackCache(value.readback_cache),
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

export function parseCollaborationSubstrateReadiness(raw: unknown): CollaborationSubstrateReadiness {
  const value = isRecord(raw) ? raw : {};
  const summary = isRecord(value.summary) ? value.summary : {};
  const definitions = isRecord(value.definitions) ? value.definitions : {};
  const sourceReadbacks = isRecord(value.source_readbacks) ? value.source_readbacks : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    surface: safeString(value.surface),
    generatedAt: safeString(value.generated_at),
    status: safeString(value.status, "unknown"),
    requiredAlignmentSources: Array.isArray(value.required_alignment_sources)
      ? value.required_alignment_sources.map((item) => safeString(item)).filter(Boolean)
      : [],
    summary: {
      collaborationSubstrateWired: safeBoolean(summary.collaboration_substrate_wired),
      boundedWiringPercentComplete: safeNumber(summary.bounded_wiring_percent_complete),
      mainBuildPromptAllowed: safeBoolean(summary.main_build_prompt_allowed),
      mainBuildPromptGate: safeString(summary.main_build_prompt_gate, "requires_alignment_review"),
      coverageOpenGapCount: safeNumber(summary.coverage_open_gap_count),
      trustLadderEnforced: safeBoolean(summary.trust_ladder_enforced),
      runtimeHealthy: safeBoolean(summary.runtime_healthy),
      learningReceiptsBounded: safeBoolean(summary.learning_receipts_bounded),
      noAuthorityGranted: safeBoolean(summary.no_authority_granted),
    },
    checklist: Array.isArray(value.checklist) ? value.checklist.map(parseCollaborationSubstrateChecklistItem) : [],
    blockingItems: Array.isArray(value.blocking_items) ? value.blocking_items.map((item) => safeString(item)).filter(Boolean) : [],
    nextAction: safeString(value.next_action),
    definitions: {
      collaborationSubstrateWired: safeString(definitions.collaboration_substrate_wired),
      mainBuildPromptAllowed: safeString(definitions.main_build_prompt_allowed),
      blockingItems: safeString(definitions.blocking_items),
    },
    sourceReadbacks: Object.fromEntries(Object.entries(sourceReadbacks).map(([key, item]) => [key, safeString(item)])),
    readbackCache: parseReadbackCache(value.readback_cache),
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

function parseCollaborationSubstrateChecklistItem(raw: unknown): CollaborationSubstrateReadinessChecklistItem {
  const value = isRecord(raw) ? raw : {};
  return {
    id: safeString(value.id),
    label: safeString(value.label),
    status: safeString(value.status, "unknown"),
    evidence: safeString(value.evidence),
    detail: safeString(value.detail),
    blocksMainBuildPrompt: safeBoolean(value.blocks_main_build_prompt),
  };
}

function parseFrancisTrustLadderItem(raw: unknown): FrancisTrustLadderItem {
  const value = isRecord(raw) ? raw : {};
  const surfaceVerification = isRecord(value.surface_verification) ? value.surface_verification : {};
  const actionBoundary = isRecord(value.action_boundary) ? value.action_boundary : {};
  return {
    id: safeString(value.id),
    sourceReviewItemId: safeString(value.source_review_item_id),
    insightId: safeString(value.insight_id),
    createdAt: safeString(value.created_at),
    sessionId: safeString(value.session_id),
    turn: safeNumber(value.turn),
    topic: safeString(value.topic),
    needStatement: safeString(value.need_statement),
    requestedSurface: safeString(value.requested_surface),
    sourceArtifact: safeString(value.source_artifact),
    decision: safeString(value.decision),
    decisionReason: safeString(value.decision_reason),
    currentAccessMode: safeString(value.current_access_mode),
    requestedAccessMode: safeString(value.requested_access_mode),
    nextTrustGate: safeString(value.next_trust_gate),
    recommendedNextAction: safeString(value.recommended_next_action),
    classificationPath: Array.isArray(value.classification_path)
      ? value.classification_path.map((item) => safeString(item)).filter(Boolean)
      : [],
    surfaceVerification: {
      status: safeString(surfaceVerification.status),
      existingSurfaceFound: safeBoolean(surfaceVerification.existing_surface_found),
      requiresBuildOrWiringReview: safeBoolean(surfaceVerification.requires_build_or_wiring_review),
      surfaceKind: safeString(surfaceVerification.surface_kind),
    },
    actionBoundary: {
      conversationCanCreateActionCandidate: safeBoolean(actionBoundary.conversation_can_create_action_candidate),
      conversationCanExecuteAction: safeBoolean(actionBoundary.conversation_can_execute_action),
      conversationCanApproveAction: safeBoolean(actionBoundary.conversation_can_approve_action),
      requiresCodexOrOperatorReviewBeforeImplementation: safeBoolean(
        actionBoundary.requires_codex_or_operator_review_before_implementation,
      ),
      requiresRepoTruthReview: safeBoolean(actionBoundary.requires_repo_truth_review),
    },
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

export function parseCollaborationRuntimeHealth(raw: unknown): CollaborationRuntimeHealth {
  const value = isRecord(raw) ? raw : {};
  const supervisor = isRecord(value.supervisor) ? value.supervisor : {};
  const loop = isRecord(value.collaboration_loop) ? value.collaboration_loop : {};
  const latestTurn = isRecord(loop.latest_turn) ? loop.latest_turn : {};
  const latestReviewReceipt = isRecord(loop.latest_review_receipt) ? loop.latest_review_receipt : {};
  const latestLearningReceipt = isRecord(loop.latest_learning_receipt) ? loop.latest_learning_receipt : {};
  const currentLearningSignal = isRecord(loop.current_learning_signal) ? loop.current_learning_signal : {};
  const participants = isRecord(value.participants) ? value.participants : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    surface: safeString(value.surface),
    status: safeString(value.status, "unknown"),
    desiredCount: safeNumber(value.desired_count),
    helperCount: safeNumber(value.helper_count),
    helpers: Array.isArray(value.helpers) ? value.helpers.map(parseRuntimeHelper) : [],
    supervisor: {
      stateObserved: safeBoolean(supervisor.state_observed),
      statePath: safeString(supervisor.state_path),
      generatedAt: safeString(supervisor.generated_at),
      ageSeconds: safeNullableNumber(supervisor.age_seconds),
    },
    collaborationLoop: {
      stateObserved: safeBoolean(loop.state_observed),
      turnCount: safeNumber(loop.turn_count),
      recurrenceState: safeString(loop.recurrence_state, "unknown"),
      waitingForOllama: safeBoolean(loop.waiting_for_ollama),
      lastCodexPromptId: safeString(loop.last_codex_prompt_id),
      lastOllamaPromptId: safeString(loop.last_ollama_prompt_id),
      lastNoteId: safeString(loop.last_note_id),
      lastInsightId: safeString(loop.last_insight_id),
      lastLearningEventId: safeString(loop.last_learning_event_id),
      nextPromptAfter: safeString(loop.next_prompt_after),
      turnGapRemainingSeconds: safeNumber(loop.turn_gap_remaining_seconds),
      updatedAt: safeString(loop.updated_at),
      ageSeconds: safeNullableNumber(loop.age_seconds),
      latestTurn: {
        turn: safeNumber(latestTurn.turn),
        turnLabel: safeString(latestTurn.turn_label),
        topic: safeString(latestTurn.topic),
        codexPromptId: safeString(latestTurn.codex_prompt_id),
        ollamaPromptId: safeString(latestTurn.ollama_prompt_id),
        noteId: safeString(latestTurn.note_id),
        insightId: safeString(latestTurn.insight_id),
        createdAt: safeString(latestTurn.created_at),
      },
      latestReviewReceipt: {
        observed: safeBoolean(latestReviewReceipt.observed),
        insightId: safeString(latestReviewReceipt.insight_id),
        reviewItemId: safeString(latestReviewReceipt.review_item_id),
        reviewArtifact: safeString(latestReviewReceipt.review_artifact),
        reviewRoute: safeString(latestReviewReceipt.review_route),
        source: safeString(latestReviewReceipt.source),
        requiresCodexOrOperatorReviewBeforeImplementation: safeBoolean(
          latestReviewReceipt.requires_codex_or_operator_review_before_implementation,
        ),
        grantsExecutionAuthority: safeBoolean(latestReviewReceipt.grants_execution_authority),
        grantsMutationAuthority: safeBoolean(latestReviewReceipt.grants_mutation_authority),
        grantsApprovalAuthority: safeBoolean(latestReviewReceipt.grants_approval_authority),
        grantsMemoryWriteAuthority: safeBoolean(latestReviewReceipt.grants_memory_write_authority),
      },
      latestLearningReceipt: {
        observed: safeBoolean(latestLearningReceipt.observed),
        learningEventId: safeString(latestLearningReceipt.learning_event_id),
        learningArtifact: safeString(latestLearningReceipt.learning_artifact),
        learningRoute: safeString(latestLearningReceipt.learning_route),
        source: safeString(latestLearningReceipt.source),
        recordsModelDriftAsLearning: safeBoolean(latestLearningReceipt.records_model_drift_as_learning),
        requiresCodexOrOperatorReviewBeforeTuning: safeBoolean(
          latestLearningReceipt.requires_codex_or_operator_review_before_tuning,
        ),
        storesFullTranscript: safeBoolean(latestLearningReceipt.stores_full_transcript),
        grantsTrainingAuthority: safeBoolean(latestLearningReceipt.grants_training_authority),
        grantsExecutionAuthority: safeBoolean(latestLearningReceipt.grants_execution_authority),
        grantsMutationAuthority: safeBoolean(latestLearningReceipt.grants_mutation_authority),
        grantsApprovalAuthority: safeBoolean(latestLearningReceipt.grants_approval_authority),
        grantsMemoryWriteAuthority: safeBoolean(latestLearningReceipt.grants_memory_write_authority),
      },
      currentLearningSignal: {
        observed: safeBoolean(currentLearningSignal.observed),
        failureType: safeString(currentLearningSignal.failure_type),
        repeatedTerms: Array.isArray(currentLearningSignal.repeated_terms)
          ? currentLearningSignal.repeated_terms.map((term) => safeString(term)).filter(Boolean)
          : [],
        recentTurnCount: safeNumber(currentLearningSignal.recent_turn_count),
        latestTurn: safeNumber(currentLearningSignal.latest_turn),
        learningEventId: safeString(currentLearningSignal.learning_event_id),
        learningArtifact: safeString(currentLearningSignal.learning_artifact),
        source: safeString(currentLearningSignal.source),
        updatedAt: safeString(currentLearningSignal.updated_at),
        ageSeconds: safeNullableNumber(currentLearningSignal.age_seconds),
        recordsModelDriftAsLearning: safeBoolean(currentLearningSignal.records_model_drift_as_learning),
        requiresCodexOrOperatorReviewBeforeTuning: safeBoolean(
          currentLearningSignal.requires_codex_or_operator_review_before_tuning,
        ),
        storesFullTranscript: safeBoolean(currentLearningSignal.stores_full_transcript),
        grantsTrainingAuthority: safeBoolean(currentLearningSignal.grants_training_authority),
        grantsExecutionAuthority: safeBoolean(currentLearningSignal.grants_execution_authority),
        grantsMutationAuthority: safeBoolean(currentLearningSignal.grants_mutation_authority),
        grantsApprovalAuthority: safeBoolean(currentLearningSignal.grants_approval_authority),
        grantsMemoryWriteAuthority: safeBoolean(currentLearningSignal.grants_memory_write_authority),
      },
    },
    participants: {
      enabledCount: safeNumber(participants.enabled_count),
      totalCount: safeNumber(participants.total_count),
      items: Array.isArray(participants.items)
        ? participants.items.map((participant) => {
            const item = isRecord(participant) ? participant : {};
            return {
              agent: safeString(item.agent),
              label: safeString(item.label),
              enabled: safeBoolean(item.enabled),
              authority: safeString(item.authority),
            };
          })
        : [],
    },
    readbackCache: parseReadbackCache(value.readback_cache),
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

export function parseCollaborationTranscript(raw: unknown): CollaborationTranscript {
  const value = isRecord(raw) ? raw : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    relayRoot: safeString(value.relay_root),
    items: Array.isArray(value.items) ? value.items.map(parseTranscriptItem) : [],
    count: safeNumber(value.count),
    truncated: safeBoolean(value.truncated),
    filters: isRecord(value.filters) ? value.filters : {},
    readbackCache: parseReadbackCache(value.readback_cache),
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

export function parseCollaborationSessions(raw: unknown): CollaborationSessions {
  const value = isRecord(raw) ? raw : {};
  const definitions = isRecord(value.definitions) ? value.definitions : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    relayRoot: safeString(value.relay_root),
    items: Array.isArray(value.items) ? value.items.map(parseSessionSummary) : [],
    count: safeNumber(value.count),
    truncated: safeBoolean(value.truncated),
    filters: isRecord(value.filters) ? value.filters : {},
    definitions: {
      session: safeString(definitions.session),
      latestPreview: safeString(definitions.latest_preview),
    },
    readbackCache: parseReadbackCache(value.readback_cache),
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

export function parseCollaborationReview(raw: unknown): CollaborationReview {
  const value = isRecord(raw) ? raw : {};
  const definitions = isRecord(value.definitions) ? value.definitions : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    surface: safeString(value.surface),
    items: Array.isArray(value.items) ? value.items.map(parseReviewItem) : [],
    count: safeNumber(value.count),
    filters: isRecord(value.filters) ? value.filters : {},
    definitions: {
      concreteRepoSurface: safeString(definitions.concrete_repo_surface),
      reviewArtifact: safeString(definitions.review_artifact),
      surfaceVerification: safeString(definitions.surface_verification),
      buildDirectionGate: safeString(definitions.build_direction_gate),
    },
    readbackCache: parseReadbackCache(value.readback_cache),
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

export function parseCollaborationLearning(raw: unknown): CollaborationLearning {
  const value = isRecord(raw) ? raw : {};
  const definitions = isRecord(value.definitions) ? value.definitions : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    surface: safeString(value.surface),
    items: Array.isArray(value.items) ? value.items.map(parseLearningEvent) : [],
    count: safeNumber(value.count),
    truncated: safeBoolean(value.truncated),
    filters: isRecord(value.filters) ? value.filters : {},
    definitions: {
      learningEvent: safeString(definitions.learning_event),
      failureType: safeString(definitions.failure_type),
      repeatedTerms: safeString(definitions.repeated_terms),
      recentTurns: safeString(definitions.recent_turns),
      latestTurn: safeString(definitions.latest_turn),
    },
    readbackCache: parseReadbackCache(value.readback_cache),
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

export async function fetchFrancisBodyMap(opts: {
  baseUrl: string;
  signal?: AbortSignal;
}): Promise<FrancisBodyMap> {
  const url = `${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/francis-body-map`;
  const response = await fetch(url, { method: "GET", signal: opts.signal });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Francis body map request failed with HTTP ${response.status}.`);
  }
  return parseFrancisBodyMap(json);
}

export async function fetchFrancisTrustLadder(opts: {
  baseUrl: string;
  limit?: number;
  signal?: AbortSignal;
}): Promise<FrancisTrustLadder> {
  const url = new URL(`${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/francis-trust-ladder`);
  url.searchParams.set("limit", String(Math.min(Math.max(opts.limit ?? 8, 1), 50)));
  const response = await fetch(url, { method: "GET", signal: opts.signal });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Francis trust ladder request failed with HTTP ${response.status}.`);
  }
  return parseFrancisTrustLadder(json);
}

export async function fetchCollaborationSubstrateReadiness(opts: {
  baseUrl: string;
  signal?: AbortSignal;
}): Promise<CollaborationSubstrateReadiness> {
  const url = `${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/collaboration-substrate-readiness`;
  const response = await fetch(url, { method: "GET", signal: opts.signal });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Collaboration substrate readiness request failed with HTTP ${response.status}.`);
  }
  return parseCollaborationSubstrateReadiness(json);
}

export async function fetchCollaborationAgentsStatus(opts: {
  baseUrl: string;
  signal?: AbortSignal;
}): Promise<CollaborationAgentsStatus> {
  const url = `${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/collaboration-agents`;
  const response = await fetch(url, { method: "GET", signal: opts.signal });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Collaboration agents request failed with HTTP ${response.status}.`);
  }
  return parseCollaborationAgentsStatus(json);
}

export async function fetchCollaborationRuntimeHealth(opts: {
  baseUrl: string;
  signal?: AbortSignal;
}): Promise<CollaborationRuntimeHealth> {
  const url = `${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/collaboration-runtime-health`;
  const response = await fetch(url, { method: "GET", signal: opts.signal });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Collaboration runtime health request failed with HTTP ${response.status}.`);
  }
  return parseCollaborationRuntimeHealth(json);
}

export async function setCollaborationAgentEnabled(opts: {
  baseUrl: string;
  agent: CollaborationAgentId;
  enabled: boolean;
  actor?: string;
  reason?: string;
  signal?: AbortSignal;
}): Promise<CollaborationAgentsStatus> {
  const url = `${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/collaboration-agents/toggle`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    signal: opts.signal,
    body: JSON.stringify({
      agent: opts.agent,
      enabled: opts.enabled,
      actor: opts.actor || "chat_ui.system",
      reason: opts.reason || "operator collaboration toggle",
    }),
  });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Collaboration agent toggle failed with HTTP ${response.status}.`);
  }
  const status = isRecord(json) && isRecord(json.status) ? json.status : json;
  return parseCollaborationAgentsStatus(status);
}

export async function fetchCollaborationTranscript(opts: {
  baseUrl: string;
  agent?: CollaborationAgentId;
  limit?: number;
  signal?: AbortSignal;
}): Promise<CollaborationTranscript> {
  const url = new URL(`${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/collaboration-transcript`);
  if (opts.agent) url.searchParams.set("agent", opts.agent);
  url.searchParams.set("limit", String(Math.min(Math.max(opts.limit ?? 8, 1), 50)));
  const response = await fetch(url, { method: "GET", signal: opts.signal });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Collaboration transcript request failed with HTTP ${response.status}.`);
  }
  return parseCollaborationTranscript(json);
}

export async function fetchCollaborationSessions(opts: {
  baseUrl: string;
  agent?: CollaborationAgentId;
  limit?: number;
  itemLimit?: number;
  signal?: AbortSignal;
}): Promise<CollaborationSessions> {
  const url = new URL(`${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/collaboration-sessions`);
  if (opts.agent) url.searchParams.set("agent", opts.agent);
  url.searchParams.set("limit", String(Math.min(Math.max(opts.limit ?? 5, 1), 20)));
  url.searchParams.set("item_limit", String(Math.min(Math.max(opts.itemLimit ?? 50, 1), 50)));
  const response = await fetch(url, { method: "GET", signal: opts.signal });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Collaboration sessions request failed with HTTP ${response.status}.`);
  }
  return parseCollaborationSessions(json);
}

export async function fetchCollaborationReview(opts: {
  baseUrl: string;
  limit?: number;
  signal?: AbortSignal;
}): Promise<CollaborationReview> {
  const url = new URL(`${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/collaboration-review`);
  url.searchParams.set("limit", String(Math.min(Math.max(opts.limit ?? 5, 1), 50)));
  const response = await fetch(url, { method: "GET", signal: opts.signal });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Collaboration review request failed with HTTP ${response.status}.`);
  }
  return parseCollaborationReview(json);
}

export async function fetchCollaborationLearning(opts: {
  baseUrl: string;
  limit?: number;
  signal?: AbortSignal;
}): Promise<CollaborationLearning> {
  const url = new URL(`${opts.baseUrl.replace(/\/$/, "")}/developer-bridge/collaboration-learning`);
  url.searchParams.set("limit", String(Math.min(Math.max(opts.limit ?? 4, 1), 50)));
  const response = await fetch(url, { method: "GET", signal: opts.signal });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Collaboration learning request failed with HTTP ${response.status}.`);
  }
  return parseCollaborationLearning(json);
}
