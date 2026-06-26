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
  latestToggleReceiptId: string;
  latestToggleProofStatus: string;
  currentToggleProof: CollaborationAgentCurrentToggleProof;
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
  operatorToggleProof: CollaborationAgentToggleProof;
  governance: Record<string, unknown>;
};

export type CollaborationAgentToggleProof = {
  proofStatus: string;
  actorRecorded: boolean;
  reasonRecorded: boolean;
  previousStateObserved: boolean;
  currentStateObserved: boolean;
  previousEnabled: boolean;
  currentEnabled: boolean;
  stateChanged: boolean;
  operatorConsoleActor: boolean;
  clientCanBeOperatorConsole: boolean;
  clientIsAutomaticExecutionAuthority: boolean;
  requiresOperatorReview: boolean;
  provesCapabilityAuthority: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsTrainingAuthority: boolean;
};

export type CollaborationAgentCurrentToggleProof = CollaborationAgentToggleProof & {
  kind: string;
  source: string;
  receiptId: string;
  createdAt: string;
  actor: string;
  reason: string;
  explicitOperatorToggleProof: boolean;
  legacyProjection: boolean;
  defaultStateProjection: boolean;
  requiresNewToggleForExplicitOperatorProof: boolean;
};

export type CollaborationAgentsStatus = {
  ok: boolean;
  mode: string;
  relay: string;
  agents: CollaborationAgent[];
  receipts: CollaborationAgentToggleReceipt[];
  definitions: {
    operatorToggleProof: string;
    currentToggleProof: string;
  };
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
    liveHealthEvidence: {
      observed: boolean;
      proofStatus: string;
      healthStatus: string;
      latestPromptId: string;
      latestReplyId: string;
      waitingState: string;
      waitingForOllama: boolean;
      turnGapRemainingSeconds: number;
      latestPromptWithinBudget: boolean;
      manualNudgeRequired: boolean | null;
      enabledParticipantCount: number;
      totalParticipantCount: number;
      allParticipantsEnabled: boolean;
      runningHelperCount: number;
      desiredHelperCount: number;
      effectiveWorkerCount: number;
      latestReviewArtifact: string;
      latestLearningArtifact: string;
      noActionAuthorityReceiptsObserved: boolean;
      evidenceFields: string[];
      storesFullTranscript: boolean;
      callsModel: boolean;
      grantsTrainingAuthority: boolean;
      grantsExecutionAuthority: boolean;
      grantsMutationAuthority: boolean;
      grantsApprovalAuthority: boolean;
      grantsMemoryWriteAuthority: boolean;
      grantsCapabilityAuthority: boolean;
    };
    latestLocalModelResponse: {
      observed: boolean;
      stateObserved: boolean;
      statePath: string;
      source: string;
      createdAt: string;
      ageSeconds: number | null;
      sourcePromptId: string;
      responsePromptId: string;
      status: string;
      outputGuardStatus: string;
      modelResponseObserved: boolean;
      isPassed: boolean;
      isGuardRewrite: boolean;
      storesFullTranscript: boolean;
      grantsTrainingAuthority: boolean;
      grantsExecutionAuthority: boolean;
      grantsMutationAuthority: boolean;
      grantsApprovalAuthority: boolean;
      grantsMemoryWriteAuthority: boolean;
      grantsCapabilityAuthority: boolean;
      adviceOnlyProof: CollaborationLocalModelAdviceOnlyProof;
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

export type CollaborationLocalModelAdviceOnlyProof = {
  proofStatus: string;
  modelResponseObserved: boolean;
  sourcePromptId: string;
  responsePromptId: string;
  outputGuardStatus: string;
  outputGuardPassed: boolean;
  outputGuardRewriteObserved: boolean;
  responseIsAdviceOnly: boolean;
  actionReadinessClaimAllowed: boolean;
  requiresCodexOrOperatorReviewBeforeActionReadiness: boolean;
  storesFullTranscript: boolean;
  grantsTrainingAuthority: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsCapabilityAuthority: boolean;
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
  display: CollaborationTranscriptDisplay;
  sourceChatEchoRequired: boolean;
  targetChatEchoRequired: boolean;
  governance: Record<string, unknown>;
};

export type CollaborationTranscriptDisplay = {
  category: string;
  priority: string;
  hideByDefault: boolean;
  reason: string;
  operatorLabel: string;
  rawTranscriptOpenedByDefault: boolean;
  storesFullTranscript: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsTrainingAuthority: boolean;
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

export type CollaborationTranscriptVisibilityOptions = {
  showAuditReceipts: boolean;
  showDriverPrompts: boolean;
  showGuardReceipts: boolean;
  showOtherHiddenReceipts?: boolean;
};

export const DEFAULT_SHOW_GUARD_RECEIPTS = false;

export type CollaborationTranscriptVisibility = {
  items: CollaborationTranscriptItem[];
  hiddenMechanicCount: number;
  hiddenAuditReceiptCount: number;
  hiddenDriverPromptCount: number;
  hiddenGuardReceiptCount: number;
  hiddenOtherReceiptCount: number;
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
  candidateLine: string;
  directAuthorityLine: string;
};

export type CollaborationImplementationReviewDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  artifact: string;
  surface: string;
  nextAction: string;
  detail: string[];
  conflictingSourceLines: string[];
  preflight: CollaborationImplementationPreflight;
};

export type CollaborationImplementationPreflight = {
  mustReadBeforeEditing: boolean;
  reviewItemId: string;
  insightId: string;
  reviewArtifact: string;
  reviewRoute: string;
  surfaceUnderReview: string;
  buildDirectionState: string;
  requiresTypedReviewArtifact: boolean;
  requiresCodexOrOperatorReview: boolean;
  requiresRepoTruthReview: boolean;
  validatedAgainstRepoTruth: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
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

export type CollaborationRuntimeLocalModelResponseDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  detail: string[];
};

export type CollaborationLearningGuardDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  failureType: string;
  latestTurn: number;
  reviewPriority: string;
  classification: string;
  promptPolicy: string;
  detail: string[];
};

export type CollaborationSubstrateChecklistDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  totalCount: number;
  passedCount: number;
  blockedCount: number;
  reviewCount: number;
  detail: string[];
};

export type FrancisBodySurface = {
  id: string;
  label: string;
  description: string;
  connectionState: string;
  accessMode: string;
  trustRequiredForNextMode: string;
  capabilityExposure: FrancisBodySurfaceCapabilityExposure;
  informationSafety: FrancisBodyInformationSafety;
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

export type FrancisBodySurfaceCapabilityExposure = {
  visibleToFrancis1: boolean;
  knownSurface: boolean;
  readbackConnected: boolean;
  connectedToLocalModel: boolean;
  capabilityGranted: boolean;
  grantState: string;
  grantableAfterTrust: boolean;
  grantRequires: string[];
  denyAfterGrantSupported: boolean;
  revocationState: string;
  canDenyAfterFactForTuning: boolean;
  safeForCapabilityUse: boolean;
  capabilityUseStatus: string;
  currentAccessMode: string;
  grantedAccessMode: string;
  nextTrustGate: string;
  requiresGovernedRequest: boolean;
  requiresCodexOrOperatorReviewBeforeCapabilityExposure: boolean;
  reason: string;
  grantsCapabilityAuthority: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsTrainingAuthority: boolean;
  detachedMemoryBin: FrancisDetachedMemoryBinPolicy;
};

export type FrancisDetachedMemoryBinPolicy = {
  applies: boolean;
  kind: string;
  status: string;
  retainsMemory: boolean;
  requiredForCurrentContext: boolean;
  usedByDefault: boolean;
  injectsIntoPromptContext: boolean;
  keepsStaleMemoryOutOfRequiredContext: boolean;
  promotionRequiresReview: boolean;
  canDenyAfterFactForTuning: boolean;
  storesFullTranscript: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsTrainingAuthority: boolean;
};

export type FrancisBodyExposureSummary = {
  kind: string;
  schemaVersion: string;
  surface: string;
  status: string;
  francis1CanSeeBody: boolean;
  francis1CanUseAllVisibleSurfaces: boolean;
  visibleSurfaceCount: number;
  readbackConnectedSurfaceCount: number;
  connectedToLocalModelCount: number;
  capabilityGrantedCount: number;
  safeForCapabilityUseCount: number;
  notExposedSurfaceCount: number;
  reviewRequiredSurfaceCount: number;
  grantRequiredBeforeUseCount: number;
  detachedMemorySurfaceCount: number;
  visibleSurfaceIds: string[];
  readbackConnectedSurfaceIds: string[];
  connectedToLocalModelSurfaceIds: string[];
  grantedSurfaceIds: string[];
  safeForCapabilityUseSurfaceIds: string[];
  notExposedSurfaceIds: string[];
  reviewRequiredSurfaceIds: string[];
  grantRequiredBeforeUseSurfaceIds: string[];
  detachedMemorySurfaceIds: string[];
  operatorReviewRequiredBeforeNewExposure: boolean;
  capabilityGrantReceiptRequiredBeforeUse: boolean;
  denyAfterGrantSupported: boolean;
  storesFullTranscript: boolean;
  grantsCapabilityAuthority: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsTrainingAuthority: boolean;
  nextReadbacks: string[];
};

export type FrancisBodyInformationSafety = {
  kind: string;
  schemaVersion: string;
  surface: string;
  surfaceId: string;
  status: string;
  validatedReadback: boolean;
  payloadScope: string;
  visibleSurfaceCount: number;
  sensitiveSurfaceCount: number;
  reviewRequiredSurfaceCount: number;
  evidencePathCount: number;
  relativeEvidencePathCount: number;
  absoluteEvidencePathCount: number;
  sensitiveSurfaceIds: string[];
  reviewRequiredSurfaceIds: string[];
  exposedPathFormat: string;
  evidencePathFormat: string;
  exposesLabel: boolean;
  exposesDescription: boolean;
  exposesCurrentBoundary: boolean;
  exposesEvidencePaths: boolean;
  sensitiveSurface: boolean;
  storesRawTranscript: boolean;
  storesFullTranscript: boolean;
  storesFileContents: boolean;
  storesSecretValues: boolean;
  exposesAbsoluteLocalPaths: boolean;
  exposesEnvironmentValues: boolean;
  embedsCapabilityReceipts: boolean;
  embedsMemoryRecords: boolean;
  embedsModelTrainingData: boolean;
  requiresCodexOrOperatorReviewBeforeExpandingDetail: boolean;
  detailExpansionAllowed: boolean;
  bodyMapVisibilityIsNotPromptInjectionAuthority: boolean;
  grantsCapabilityAuthority: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsTrainingAuthority: boolean;
  validationRule: string;
  nextReadbacks: string[];
};

export type FrancisBodySurfaceDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  boundary: string;
  evidenceLine: string;
  authorityLine: string;
  capabilityLine: string;
  detail: string[];
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
    visibleSurfaceCount: number;
    connectedToLocalModelCount: number;
    capabilityGrantedCount: number;
    notExposedSurfaceCount: number;
    reviewRequiredSurfaceCount: number;
    informationSafetyValidated: boolean;
    sensitiveSurfaceCount: number;
    absoluteEvidencePathCount: number;
    activeCapabilityGrantCount: number;
    deniedOrRevokedCapabilityCount: number;
    trustLadderEnforced: boolean;
    runtimeRestartObserved: boolean;
    coverageReviewed: boolean;
    canonicalPlaneCount: number;
    canonicalPlaneCoveredCount: number;
    coverageOpenGapCount: number;
  };
  exposureSummary: FrancisBodyExposureSummary;
  informationSafety: FrancisBodyInformationSafety;
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
  capabilityGrants: {
    surface: string;
    route: string;
    connected: boolean;
    activeGrantsPresent: boolean;
    grantedCount: number;
    deniedOrRevokedCount: number;
    denyAfterGrantSupported: boolean;
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

export type CollaborationSubstrateOpenOrbGap = {
  planeId: string;
  planeName: string;
  bodySurfaceId: string;
  currentPosture: string;
  riskLevel: string;
  riskStatement: string;
  remainingGaps: string[];
  nextReviewArtifact: string;
  recommendedNextAction: string;
  blocksMainBuildPrompt: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  grantsTrainingAuthority: boolean;
};

export type CollaborationRoadmapAlignment = {
  status: string;
  requiredSources: string[];
  sourceOrder: string[];
  ledgerFirst: boolean;
  ledgerObserved: boolean;
  manifestObserved: boolean;
  sourcesObserved: boolean;
  mainBuildPromptAllowed: boolean;
  mainBuildPromptGate: string;
  candidateOnlyUntilReview: boolean;
  blocksMainBuildPrompt: boolean;
  blockingItems: string[];
  openOrbGapCount: number;
  openOrbGapPlaneIds: string[];
  nextCheck: string;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
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
    openOrbGapPlaneIds: string[];
    trustLadderEnforced: boolean;
    runtimeHealthy: boolean;
    learningReceiptsBounded: boolean;
    noAuthorityGranted: boolean;
  };
  roadmapAlignment: CollaborationRoadmapAlignment;
  checklist: CollaborationSubstrateReadinessChecklistItem[];
  blockingItems: string[];
  openOrbGaps: CollaborationSubstrateOpenOrbGap[];
  nextAction: string;
  definitions: {
    collaborationSubstrateWired: string;
    mainBuildPromptAllowed: string;
    blockingItems: string;
    roadmapAlignment: string;
    openOrbGaps: string;
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
  latestReviewGate: CollaborationSessionReviewGate;
  transcriptDisclosure: CollaborationSessionTranscriptDisclosure;
};

export type CollaborationSessionTranscriptDisclosure = {
  summaryBeforeRawTranscript: boolean;
  safePreviewAvailable: boolean;
  rawTranscriptOpenedByDefault: boolean;
  rawReceiptDetailsOpenedByDefault: boolean;
  technicalReceiptsOpenedByDefault: boolean;
  storesFullTranscript: boolean;
  operatorReviewSurface: string;
  disclosureLabel: string;
};

export type CollaborationSessionReviewGate = {
  observed: boolean;
  reviewItemId: string;
  insightId: string;
  turn: number;
  topic: string;
  buildIssueCode: string;
  surface: string;
  requiredReviewArtifact: string;
  buildDirectionState: string;
  blocksBuildDirection: boolean;
  requiresCodexOrOperatorReview: boolean;
  requiresRepoTruthReview: boolean;
  nextCodexAction: string;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
  storesFullTranscript: boolean;
};

export type CollaborationSessionReviewGateDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  artifact: string;
  surface: string;
  nextAction: string;
  detail: string[];
};

export type CollaborationSessionTranscriptDisclosureDisplay = {
  badge: string;
  tone: CollaborationReviewTone;
  detail: string[];
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
    latestReviewGate: string;
    transcriptDisclosure: string;
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
  actionCandidateBoundary: {
    applies: boolean;
    surface: string;
    proofStatus: string;
    proofSource: string;
    chatSendActionCandidateReadback: boolean;
    chatWsActionCandidateReadback: boolean;
    missionCurrentTaskReadback: boolean;
    missionRecordReceipt: string;
    taskRecordReceipt: string;
    sourceModesObservedByTests: string[];
    sourceModeProofReadback: boolean;
    inputActorReadback: boolean;
    sourceModeDerivationReadback: boolean;
    voiceTurnCorrelationReadOnly: boolean;
    voiceTurnCorrelationGrantsExecutionAuthority: boolean;
    voiceTurnCorrelationGrantsMutationAuthority: boolean;
    operationCandidateRequired: boolean;
    missionRecordRequired: boolean;
    firstOperationCandidateRequired: boolean;
    directExecution: boolean;
    requiresPolicy: boolean;
    requiresApproval: boolean;
    requiresTraceableReceipt: boolean;
    storesFullTranscript: boolean;
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
    grantsTrainingAuthority: boolean;
    grantsCapabilityAuthority: boolean;
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
  sourceDisagreementBoundary: {
    applies: boolean;
    surface: string;
    proofStatus: string;
    reviewArtifactObserved: boolean;
    requiredReviewArtifact: string;
    surfaceUnderReview: string;
    conflictingSourceCount: number;
    conflictingSources: {
      source: string;
      receiptId: string;
      role: string;
      providerLane: string;
    }[];
    blocksBuildDirection: boolean;
    conversationCanChooseWinner: boolean;
    conversationCanExecuteResolution: boolean;
    requiresTypedReviewArtifact: boolean;
    requiresCodexOrOperatorReview: boolean;
    requiresRepoTruthReview: boolean;
    proofSource: string;
    storesFullTranscript: boolean;
    grantsBuildDirectionAuthority: boolean;
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
    grantsTrainingAuthority: boolean;
    grantsCapabilityAuthority: boolean;
  };
  roadmapAlignmentProof: {
    latestLedgerEntry: string;
    currentPhase: string;
    currentPhasePosture: string;
    currentPriorityOrPlaneLine: string;
    ledgerObserved: boolean;
    manifestObserved: boolean;
    sourcesObserved: boolean;
    sourceOrder: string[];
    coverageOpenGapCount: number;
    remainingBlockers: string[];
    mainBuildPromptAllowed: boolean;
    mainBuildPromptGate: string;
    mainBuildPromptCandidateOnly: boolean;
    conversationCanOverrideRoadmap: boolean;
    proofSource: string;
    storesFullTranscript: boolean;
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
    grantsTrainingAuthority: boolean;
  };
  participantToggleBoundary: {
    applies: boolean;
    surface: string;
    disabledParticipantBlocksNewRelaySubmissions: boolean;
    requiresOperatorToggleProof: boolean;
    visibilityIsCapabilityGrant: boolean;
    participantEnablementIsExecutionAuthority: boolean;
    receiptKind: string;
    knownAgents: string[];
    receiptCount: number;
    proofReceiptCount: number;
    legacyReceiptCount: number;
    latestReceiptId: string;
    latestAgent: string;
    agentCurrentToggleProofCount: number;
    agentExplicitOperatorToggleProofCount: number;
    agentLegacyProjectionCount: number;
    agentDefaultStateProjectionCount: number;
    agentsWithExplicitOperatorToggleProof: string[];
    agentsMissingExplicitOperatorToggleProof: string[];
    allAgentsHaveCurrentToggleReadback: boolean;
    allAgentsHaveExplicitOperatorToggleProof: boolean;
    operatorConsoleActor: string;
    clientCanBeOperatorConsole: boolean;
    clientIsAutomaticExecutionAuthority: boolean;
    proofSource: string;
    agentProofs: {
      agent: string;
      enabled: boolean;
      proofStatus: string;
      source: string;
      receiptId: string;
      explicitOperatorToggleProof: boolean;
      legacyProjection: boolean;
      defaultStateProjection: boolean;
      requiresNewToggleForExplicitOperatorProof: boolean;
      actorRecorded: boolean;
      reasonRecorded: boolean;
      currentStateObserved: boolean;
      grantsExecutionAuthority: boolean;
      grantsCapabilityAuthority: boolean;
    }[];
    storesFullTranscript: boolean;
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
    grantsTrainingAuthority: boolean;
    grantsCapabilityAuthority: boolean;
  };
  modelAdviceGovernanceBoundary: {
    applies: boolean;
    surface: string;
    actionReadinessClaimAllowed: boolean;
    modelAdviceCanCreateActionCandidate: boolean;
    modelAdviceCanExecuteAction: boolean;
    modelAdviceCanApproveAction: boolean;
    requiresActionBoundaryReadback: boolean;
    requiresLatestLocalModelAdviceOnlyProof: boolean;
    requiresPolicy: boolean;
    requiresApproval: boolean;
    requiresTraceableReceipt: boolean;
    requiresActionCandidateBoundary: boolean;
    proofStatus: string;
    runtimeStatus: string;
    modelResponseObserved: boolean;
    latestResponseStatus: string;
    sourcePromptId: string;
    responsePromptId: string;
    outputGuardStatus: string;
    outputGuardPassed: boolean;
    outputGuardRewriteObserved: boolean;
    responseIsAdviceOnly: boolean;
    requiredGates: string[];
    proofSource: string;
    storesFullTranscript: boolean;
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
    grantsTrainingAuthority: boolean;
    grantsCapabilityAuthority: boolean;
  };
  implementationPreflight: CollaborationImplementationPreflight;
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
    implementationPreflight: string;
    sourceDisagreementBoundary: string;
    participantToggleBoundary: string;
    modelAdviceGovernanceBoundary: string;
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
  signalReview: CollaborationLearningSignalReview;
  memoryPromotionGate: CollaborationLearningMemoryPromotionGate;
  writerGovernance: Record<string, unknown>;
};

export type CollaborationLearningSignalReview = {
  applies: boolean;
  classification: string;
  reviewPriority: string;
  impact: string;
  failureType: string;
  currentSignalRecentTurnCount: number;
  recentTurnCount: number;
  repeatedTermCount: number;
  requiredReviewArtifact: string;
  recommendedNextAction: string;
  memoryPromotionAllowed: boolean;
  longTermMemoryPromotionAllowed: boolean;
  modelTuningAllowed: boolean;
  requiresCodexOrOperatorReview: boolean;
  requiresRepoTruthReview: boolean;
  storesFullTranscript: boolean;
  grantsTrainingAuthority: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
};

export type CollaborationLearningMemoryPromotionGate = {
  applies: boolean;
  sourceEventId: string;
  failureIsLearningEvidence: boolean;
  memoryPromotionAllowed: boolean;
  longTermMemoryPromotionAllowed: boolean;
  modelTuningAllowed: boolean;
  requiresCodexOrOperatorReview: boolean;
  requiresRepoTruthReview: boolean;
  requiresMemoryPromotionReview: boolean;
  requiredReviewArtifact: string;
  nextCodexAction: string;
  storesFullTranscript: boolean;
  grantsTrainingAuthority: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  grantsApprovalAuthority: boolean;
  grantsMemoryWriteAuthority: boolean;
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

function safeNullableBoolean(v: unknown): boolean | null {
  return typeof v === "boolean" ? v : null;
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

function inferTranscriptDisplay(
  sourceAgent: string,
  targetAgent: string,
  objective: string,
  context: string,
  prompt: string,
): CollaborationTranscriptDisplay {
  const receiptKind = classifyTranscriptReceipt(objective, context, prompt);
  const driverPrompt =
    sourceAgent === "codex" &&
    targetAgent === "ollama" &&
    objective.toLowerCase().startsWith("francis1 collaboration driver turn") &&
    (prompt.startsWith("Francis1 collab turn ") || prompt.startsWith("Francis1 turn "));
  const guardReceipt = prompt.startsWith("Francis1 output guard fallback:");
  if (receiptKind === "audit_ack") {
    return {
      category: "audit_ack",
      priority: "mechanic",
      hideByDefault: true,
      reason: "relay_acknowledgement",
      operatorLabel: "Auto-ack receipt",
      rawTranscriptOpenedByDefault: false,
      storesFullTranscript: false,
      grantsExecutionAuthority: false,
      grantsMutationAuthority: false,
      grantsApprovalAuthority: false,
      grantsMemoryWriteAuthority: false,
      grantsTrainingAuthority: false,
    };
  }
  if (driverPrompt) {
    return {
      category: "driver_prompt",
      priority: "mechanic",
      hideByDefault: true,
      reason: "codex_driver_prompt",
      operatorLabel: "Codex driver prompt",
      rawTranscriptOpenedByDefault: false,
      storesFullTranscript: false,
      grantsExecutionAuthority: false,
      grantsMutationAuthority: false,
      grantsApprovalAuthority: false,
      grantsMemoryWriteAuthority: false,
      grantsTrainingAuthority: false,
    };
  }
  if (guardReceipt) {
    return {
      category: "guard_receipt",
      priority: "supporting",
      hideByDefault: true,
      reason: "local_model_output_guard",
      operatorLabel: "Guarded Francis1 response",
      rawTranscriptOpenedByDefault: false,
      storesFullTranscript: false,
      grantsExecutionAuthority: false,
      grantsMutationAuthority: false,
      grantsApprovalAuthority: false,
      grantsMemoryWriteAuthority: false,
      grantsTrainingAuthority: false,
    };
  }
  return {
    category: "conversation",
    priority: "primary",
    hideByDefault: false,
    reason: "agent_message",
    operatorLabel: "Conversation message",
    rawTranscriptOpenedByDefault: false,
    storesFullTranscript: false,
    grantsExecutionAuthority: false,
    grantsMutationAuthority: false,
    grantsApprovalAuthority: false,
    grantsMemoryWriteAuthority: false,
    grantsTrainingAuthority: false,
  };
}

function parseTranscriptDisplay(
  raw: unknown,
  sourceAgent: string,
  targetAgent: string,
  objective: string,
  context: string,
  prompt: string,
): CollaborationTranscriptDisplay {
  const fallback = inferTranscriptDisplay(sourceAgent, targetAgent, objective, context, prompt);
  const item = isRecord(raw) ? raw : {};
  return {
    category: safeString(item.category, fallback.category),
    priority: safeString(item.priority, fallback.priority),
    hideByDefault: safeBoolean(item.hide_by_default, fallback.hideByDefault),
    reason: safeString(item.reason, fallback.reason),
    operatorLabel: safeString(item.operator_label, fallback.operatorLabel),
    rawTranscriptOpenedByDefault: safeBoolean(
      item.raw_transcript_opened_by_default,
      fallback.rawTranscriptOpenedByDefault,
    ),
    storesFullTranscript: safeBoolean(item.stores_full_transcript, fallback.storesFullTranscript),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority, fallback.grantsExecutionAuthority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority, fallback.grantsMutationAuthority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority, fallback.grantsApprovalAuthority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority, fallback.grantsMemoryWriteAuthority),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority, fallback.grantsTrainingAuthority),
  };
}

export function isCollaborationAuditReceipt(item: CollaborationTranscriptItem): boolean {
  return item.display.category === "audit_ack" || item.receiptKind === "audit_ack";
}

export function isCollaborationDriverPrompt(item: CollaborationTranscriptItem): boolean {
  const raw = receiptText(item);
  return (
    item.display.category === "driver_prompt" ||
    (item.sourceAgent === "codex" &&
      item.targetAgent === "ollama" &&
      item.objective.toLowerCase().startsWith("francis1 collaboration driver turn") &&
      (raw.startsWith("Francis1 collab turn ") || raw.startsWith("Francis1 turn ")))
  );
}

export function isCollaborationGuardReceipt(item: CollaborationTranscriptItem): boolean {
  return item.display.category === "guard_receipt" || receiptText(item).startsWith("Francis1 output guard fallback:");
}

export function collaborationTranscriptAuditSummary(items: CollaborationTranscriptItem[]): {
  conversationItems: CollaborationTranscriptItem[];
  operatorConversationItems: CollaborationTranscriptItem[];
  auditReceipts: CollaborationTranscriptItem[];
  driverPrompts: CollaborationTranscriptItem[];
  guardReceipts: CollaborationTranscriptItem[];
  auditReceiptCount: number;
  driverPromptCount: number;
  guardReceiptCount: number;
  relayMechanicCount: number;
  substantiveTurnCount: number;
  totalCount: number;
} {
  const conversationItems: CollaborationTranscriptItem[] = [];
  const operatorConversationItems: CollaborationTranscriptItem[] = [];
  const auditReceipts: CollaborationTranscriptItem[] = [];
  const driverPrompts: CollaborationTranscriptItem[] = [];
  const guardReceipts: CollaborationTranscriptItem[] = [];
  let driverPromptCount = 0;
  for (const item of items) {
    const driverPrompt = isCollaborationDriverPrompt(item);
    const guardReceipt = isCollaborationGuardReceipt(item);
    if (isCollaborationAuditReceipt(item)) {
      auditReceipts.push(item);
    } else {
      conversationItems.push(item);
      if (!driverPrompt && !guardReceipt) operatorConversationItems.push(item);
    }
    if (driverPrompt) {
      driverPrompts.push(item);
      driverPromptCount += 1;
    }
    if (guardReceipt) guardReceipts.push(item);
  }
  const relayMechanicCount = auditReceipts.length + driverPromptCount + guardReceipts.length;
  return {
    conversationItems,
    operatorConversationItems,
    auditReceipts,
    driverPrompts,
    guardReceipts,
    auditReceiptCount: auditReceipts.length,
    driverPromptCount,
    guardReceiptCount: guardReceipts.length,
    relayMechanicCount,
    substantiveTurnCount: Math.max(0, items.length - relayMechanicCount),
    totalCount: items.length,
  };
}

export function filterCollaborationTranscriptItems(
  items: CollaborationTranscriptItem[],
  options: CollaborationTranscriptVisibilityOptions,
): CollaborationTranscriptVisibility {
  const visibleItems: CollaborationTranscriptItem[] = [];
  const hiddenGuardReceipts: CollaborationTranscriptItem[] = [];
  let hiddenAuditReceiptCount = 0;
  let hiddenDriverPromptCount = 0;
  let hiddenGuardReceiptCount = 0;
  let hiddenOtherReceiptCount = 0;
  for (const item of items) {
    const auditReceipt = isCollaborationAuditReceipt(item);
    const driverPrompt = isCollaborationDriverPrompt(item);
    const guardReceipt = isCollaborationGuardReceipt(item);
    if (auditReceipt && !options.showAuditReceipts) {
      hiddenAuditReceiptCount += 1;
      continue;
    }
    if (driverPrompt && !options.showDriverPrompts) {
      hiddenDriverPromptCount += 1;
      continue;
    }
    if (guardReceipt && !options.showGuardReceipts) {
      hiddenGuardReceipts.push(item);
      hiddenGuardReceiptCount += 1;
      continue;
    }
    if (item.display.hideByDefault && !auditReceipt && !driverPrompt && !guardReceipt && !options.showOtherHiddenReceipts) {
      hiddenOtherReceiptCount += 1;
      continue;
    }
    visibleItems.push(item);
  }
  if (!visibleItems.length && hiddenGuardReceipts.length) {
    visibleItems.push(...hiddenGuardReceipts);
    hiddenGuardReceiptCount = 0;
  }
  return {
    items: visibleItems,
    hiddenMechanicCount: hiddenAuditReceiptCount + hiddenDriverPromptCount + hiddenGuardReceiptCount + hiddenOtherReceiptCount,
    hiddenAuditReceiptCount,
    hiddenDriverPromptCount,
    hiddenGuardReceiptCount,
    hiddenOtherReceiptCount,
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

  const isDriverPrompt = isCollaborationDriverPrompt(item);
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
  const bodyMap = textBetween(raw, "Body map:", [
    " Roadmap:",
    ". Roadmap:",
    " Trust:",
    ". Trust:",
    " Current artifact:",
    ". Current artifact:",
  ]);
  const roadmap = textBetween(raw, "Roadmap:", [" Trust:", ". Trust:", " Current artifact:", ". Current artifact:"]);
  const trust = textBetween(raw, "Trust:", [
    " Claude=",
    ". Claude=",
    " Current artifact:",
    ". Current artifact:",
    " Prior check:",
    ". Prior check:",
  ]);
  const sourceAlignment = raw.includes("Claude guidance acknowledged; Francis subject; Codex validates repo truth.")
    ? "Claude guidance acknowledged; Francis subject; Codex validates repo truth"
    : raw.includes("Claude acknowledged as guidance; Francis stays subject; Codex validates repo truth.")
    ? "Claude acknowledged as guidance; Francis stays subject; Codex validates repo truth"
    : raw.includes("Claude=guidance; Francis=subject; validate claims.")
    ? "Claude=guidance; Francis=subject; validate claims"
    : textBetween(raw, "Claude acknowledged as guidance;", [" Current artifact:", ". Current artifact:"]);
  const artifact = textBetween(raw, "Current artifact:", [". Prior check:", " Prior check:", ". Codex response:", " Codex response:"]);
  const priorCheck = textBetween(raw, "Prior check:", [
    ". Codex response:",
    " Codex response:",
    ". Codex:",
    " Codex:",
    ". Guard note:",
    " Guard note:",
    ". Guard:",
    " Guard:",
    ". Body map:",
    " Body map:",
  ]);
  const codexResponse = firstTextBetween(raw, ["Codex response:", "Codex:"], [
    ". Guard note:",
    " Guard note:",
    ". Guard:",
    " Guard:",
    ". Body map:",
    " Body map:",
    ". Trust:",
    " Trust:",
  ]);
  const guardNote = firstTextBetween(raw, ["Guard note:", "Guard:"], []);
  const lines = [
    turn ? `Turn ${turn}` : item.objective,
    topic ? `Topic: ${topic}` : "",
    artifact ? `Artifact: ${artifact}` : "",
  ].filter(Boolean);
  const conversationLines = [topic ? `Topic: ${topic}` : "", codexResponse ? `Codex response: ${codexResponse}` : ""].filter(Boolean);
  const technicalLines = [
    turn ? `Turn ${turn}` : item.objective,
    bodyMap ? `Body map: ${bodyMap}` : "",
    roadmap ? `Roadmap: ${roadmap}` : "",
    trust ? `Trust: ${trust}` : "",
    sourceAlignment ? `Source alignment: ${sourceAlignment}` : "",
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

function collaborationConflictingSourceLine(source: CollaborationReviewItem["buildDirectionGate"]["conflictingSources"][number]): string {
  const sourceName = source.source || "unknown source";
  const receipt = source.receiptId || "missing receipt";
  const role = source.role || "unspecified role";
  const provider = source.providerLane ? ` / provider ${source.providerLane}` : "";
  return `${sourceName}: ${receipt} / ${role}${provider}`;
}

export function collaborationImplementationReviewSummary(item: CollaborationReviewItem): CollaborationImplementationReviewDisplay {
  const preflight = item.implementationPreflight;
  const unsafeAuthority =
    item.actionBoundary.conversationCanExecuteAction ||
    item.actionBoundary.conversationCanApproveAction ||
    preflight.grantsExecutionAuthority ||
    preflight.grantsMutationAuthority ||
    preflight.grantsApprovalAuthority ||
    preflight.grantsMemoryWriteAuthority ||
    item.buildDirectionGate.grantsExecutionAuthority ||
    item.buildDirectionGate.grantsMutationAuthority ||
    item.buildDirectionGate.grantsApprovalAuthority ||
    item.buildDirectionGate.grantsMemoryWriteAuthority;
  const artifact = preflight.reviewArtifact || item.buildDirectionGate.requiredReviewArtifact || item.reviewArtifact || "unknown";
  const surface = preflight.surfaceUnderReview || item.buildDirectionGate.surfaceUnderReview || item.concreteRepoSurface || "unknown";
  const conflictingSourceLines = item.buildDirectionGate.conflictingSources.length
    ? item.buildDirectionGate.conflictingSources.map(collaborationConflictingSourceLine)
    : [];
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
      `review item ${preflight.reviewItemId || item.id || "unknown"}`,
      `route ${preflight.reviewRoute || "/developer-bridge/collaboration-review?limit=1"}`,
      `turn ${item.turn || "unknown"}`,
      `must read ${actionBoundaryBool(preflight.mustReadBeforeEditing || item.buildDirectionGate.requiresTypedReviewArtifact)}`,
      `gate ${preflight.buildDirectionState || item.buildDirectionGate.state || "advisory_review_required"}`,
      `typed artifact ${actionBoundaryBool(preflight.requiresTypedReviewArtifact || item.buildDirectionGate.requiresTypedReviewArtifact)}`,
      `codex review ${actionBoundaryBool(preflight.requiresCodexOrOperatorReview || item.buildDirectionGate.requiresCodexOrOperatorReview)}`,
      `repo review ${actionBoundaryBool(preflight.requiresRepoTruthReview || item.buildDirectionGate.requiresRepoTruthReview)}`,
      `repo checked ${actionBoundaryBool(preflight.validatedAgainstRepoTruth || item.reviewRecommendation.validatedAgainstRepoTruth)}`,
      `execute ${actionBoundaryBool(item.actionBoundary.conversationCanExecuteAction || preflight.grantsExecutionAuthority || item.buildDirectionGate.grantsExecutionAuthority)}`,
      `mutation ${actionBoundaryBool(preflight.grantsMutationAuthority || item.buildDirectionGate.grantsMutationAuthority)}`,
      `approve ${actionBoundaryBool(item.actionBoundary.conversationCanApproveAction || preflight.grantsApprovalAuthority || item.buildDirectionGate.grantsApprovalAuthority)}`,
      `memory write ${actionBoundaryBool(preflight.grantsMemoryWriteAuthority || item.buildDirectionGate.grantsMemoryWriteAuthority)}`,
    ],
    conflictingSourceLines,
    preflight,
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
    ? gate.conflictingSources.map(collaborationConflictingSourceLine)
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
      `mutation ${actionBoundaryBool(gate.grantsMutationAuthority)}`,
      `approve ${actionBoundaryBool(item.actionBoundary.conversationCanApproveAction || gate.grantsApprovalAuthority)}`,
      `memory write ${actionBoundaryBool(gate.grantsMemoryWriteAuthority)}`,
    ],
    conflictingSourceLines,
  };
}

function actionBoundaryBool(value: boolean): string {
  return value ? "true" : "false";
}

function governanceFlag(governance: Record<string, unknown>, key: string): boolean {
  return safeBoolean(governance[key]);
}

export function collaborationSessionReviewGateSummary(gate: CollaborationSessionReviewGate): CollaborationSessionReviewGateDisplay {
  const unsafeAuthority =
    gate.grantsExecutionAuthority ||
    gate.grantsMutationAuthority ||
    gate.grantsApprovalAuthority ||
    gate.grantsMemoryWriteAuthority;
  return {
    badge: unsafeAuthority ? "authority drift" : gate.blocksBuildDirection ? "build blocked" : "advisory gate",
    tone: unsafeAuthority || gate.blocksBuildDirection ? "blocked" : "ready",
    artifact: gate.requiredReviewArtifact || gate.reviewItemId || "unknown",
    surface: gate.surface || "unknown",
    nextAction: gate.nextCodexAction || "Inspect the session review gate before expanding transcript visibility.",
    detail: [
      `gate ${gate.buildDirectionState || "advisory_review_required"}`,
      `codex review ${actionBoundaryBool(gate.requiresCodexOrOperatorReview)}`,
      `repo review ${actionBoundaryBool(gate.requiresRepoTruthReview)}`,
      `execute ${actionBoundaryBool(gate.grantsExecutionAuthority)}`,
      `mutation ${actionBoundaryBool(gate.grantsMutationAuthority)}`,
      `approve ${actionBoundaryBool(gate.grantsApprovalAuthority)}`,
      `memory write ${actionBoundaryBool(gate.grantsMemoryWriteAuthority)}`,
      `full transcript ${actionBoundaryBool(gate.storesFullTranscript)}`,
    ],
  };
}

export function collaborationSessionTranscriptDisclosureSummary(
  disclosure: CollaborationSessionTranscriptDisclosure,
): CollaborationSessionTranscriptDisclosureDisplay {
  const rawOpen =
    disclosure.rawTranscriptOpenedByDefault ||
    disclosure.rawReceiptDetailsOpenedByDefault ||
    disclosure.technicalReceiptsOpenedByDefault;
  const unsafeDisclosure = rawOpen || disclosure.storesFullTranscript || !disclosure.summaryBeforeRawTranscript;
  return {
    badge: unsafeDisclosure ? "raw disclosure drift" : "summary-first",
    tone: unsafeDisclosure ? "blocked" : "ready",
    detail: [
      disclosure.disclosureLabel || "summary first; raw receipt detail remains opt-in",
      `safe preview ${actionBoundaryBool(disclosure.safePreviewAvailable)}`,
      `raw transcript open ${actionBoundaryBool(disclosure.rawTranscriptOpenedByDefault)}`,
      `receipt detail open ${actionBoundaryBool(disclosure.rawReceiptDetailsOpenedByDefault)}`,
      `technical receipts open ${actionBoundaryBool(disclosure.technicalReceiptsOpenedByDefault)}`,
      `full transcript store ${actionBoundaryBool(disclosure.storesFullTranscript)}`,
      `surface ${disclosure.operatorReviewSurface || "developer_bridge.collaboration_sessions"}`,
    ],
  };
}

export function francisBodySurfaceExposureSummary(surface: FrancisBodySurface): FrancisBodySurfaceDisplay {
  const unsafeAuthority =
    surface.grantsExecutionAuthority ||
    surface.grantsMutationAuthority ||
    surface.grantsApprovalAuthority ||
    surface.grantsMemoryWriteAuthority ||
    surface.grantsTrainingAuthority ||
    surface.capabilityExposure.grantsExecutionAuthority ||
    surface.capabilityExposure.grantsMutationAuthority ||
    surface.capabilityExposure.grantsApprovalAuthority ||
    surface.capabilityExposure.grantsMemoryWriteAuthority ||
    surface.capabilityExposure.grantsTrainingAuthority ||
    surface.capabilityExposure.grantsCapabilityAuthority ||
    surface.capabilityExposure.connectedToLocalModel ||
    surface.capabilityExposure.capabilityGranted ||
    surface.capabilityExposure.detachedMemoryBin.injectsIntoPromptContext ||
    surface.capabilityExposure.detachedMemoryBin.requiredForCurrentContext ||
    surface.capabilityExposure.detachedMemoryBin.grantsMemoryWriteAuthority ||
    surface.capabilityExposure.detachedMemoryBin.grantsTrainingAuthority ||
    surface.capabilityExposure.safeForCapabilityUse;
  const evidenceItems = surface.evidence
    .filter((item) => item.path)
    .map((item) => `${item.path} ${item.observed ? "observed" : "missing"}`);
  const evidenceLine = evidenceItems.length ? evidenceItems.slice(0, 3).join(" / ") : "no evidence paths reported";
  const boundary =
    surface.capabilityExposure.reason ||
    surface.currentBoundary ||
    "capability exposure requires trust-gated review";
  return {
    badge: unsafeAuthority
      ? "authority visible"
      : surface.capabilityExposure.visibleToFrancis1
        ? `${surface.capabilityExposure.capabilityUseStatus || "not_exposed"}`
        : `${surface.accessMode || "observe"} only`,
    tone: unsafeAuthority ? "blocked" : "ready",
    boundary,
    evidenceLine: evidenceItems.length > 3 ? `${evidenceLine} / +${evidenceItems.length - 3} more` : evidenceLine,
    authorityLine: `execute ${actionBoundaryBool(surface.grantsExecutionAuthority)} / mutation ${actionBoundaryBool(
      surface.grantsMutationAuthority,
    )} / approve ${actionBoundaryBool(surface.grantsApprovalAuthority)} / memory write ${actionBoundaryBool(
      surface.grantsMemoryWriteAuthority,
    )} / training ${actionBoundaryBool(surface.grantsTrainingAuthority)}`,
    capabilityLine: `visible ${actionBoundaryBool(surface.capabilityExposure.visibleToFrancis1)} / connected ${actionBoundaryBool(
      surface.capabilityExposure.connectedToLocalModel,
    )} / granted ${actionBoundaryBool(surface.capabilityExposure.capabilityGranted)} / safe use ${actionBoundaryBool(
      surface.capabilityExposure.safeForCapabilityUse,
    )} / request ${actionBoundaryBool(surface.capabilityExposure.requiresGovernedRequest)} / codex review ${actionBoundaryBool(
      surface.capabilityExposure.requiresCodexOrOperatorReviewBeforeCapabilityExposure,
    )}`,
    detail: [
      `state ${surface.connectionState || "unknown"}`,
      `access ${surface.capabilityExposure.currentAccessMode || surface.accessMode || "observe"}`,
      `next trust ${surface.capabilityExposure.nextTrustGate || surface.trustRequiredForNextMode || "review"}`,
      `capability ${surface.capabilityExposure.capabilityUseStatus || "not_exposed"}`,
      `grant ${surface.capabilityExposure.grantState || "not_granted"}`,
      `grantable after trust ${actionBoundaryBool(surface.capabilityExposure.grantableAfterTrust)}`,
      `deny after grant ${actionBoundaryBool(surface.capabilityExposure.denyAfterGrantSupported)}`,
      `revocation ${surface.capabilityExposure.revocationState || "revocable_for_tuning"}`,
      `granted access ${surface.capabilityExposure.grantedAccessMode || "observe"}`,
      `grant can deny for tuning ${actionBoundaryBool(surface.capabilityExposure.canDenyAfterFactForTuning)}`,
      surface.capabilityExposure.detachedMemoryBin.applies
        ? `detached memory ${surface.capabilityExposure.detachedMemoryBin.status || "detach_if_stale"}`
        : "",
      surface.capabilityExposure.detachedMemoryBin.applies
        ? `memory required ${actionBoundaryBool(surface.capabilityExposure.detachedMemoryBin.requiredForCurrentContext)}`
        : "",
      `visible ${actionBoundaryBool(surface.capabilityExposure.visibleToFrancis1)}`,
      `connected ${actionBoundaryBool(surface.capabilityExposure.connectedToLocalModel)}`,
      `granted ${actionBoundaryBool(surface.capabilityExposure.capabilityGranted)}`,
      `safe use ${actionBoundaryBool(surface.capabilityExposure.safeForCapabilityUse)}`,
      `capability authority ${actionBoundaryBool(surface.capabilityExposure.grantsCapabilityAuthority)}`,
      `execute ${actionBoundaryBool(surface.grantsExecutionAuthority)}`,
      `mutation ${actionBoundaryBool(surface.grantsMutationAuthority)}`,
      `approve ${actionBoundaryBool(surface.grantsApprovalAuthority)}`,
      `memory write ${actionBoundaryBool(surface.grantsMemoryWriteAuthority)}`,
      `training ${actionBoundaryBool(surface.grantsTrainingAuthority)}`,
    ].filter(Boolean),
  };
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
      candidateLine: "",
      directAuthorityLine: "",
    };
  }
  const boundary = item.actionBoundary;
  const gate = item.buildDirectionGate;
  const canCreateCandidate = boundary.conversationCanCreateActionCandidate;
  const canExecute = boundary.conversationCanExecuteAction || gate.grantsExecutionAuthority;
  const canApprove = boundary.conversationCanApproveAction || gate.grantsApprovalAuthority;
  const canMutate = gate.grantsMutationAuthority;
  const canWriteMemory = gate.grantsMemoryWriteAuthority;
  const unsafeAuthority =
    canExecute ||
    canApprove ||
    canMutate ||
    canWriteMemory;
  return {
    applies: true,
    badge: unsafeAuthority ? "action authority visible" : "action candidate only",
    tone: unsafeAuthority ? "blocked" : "ready",
    candidateLine: `candidate ${actionBoundaryBool(canCreateCandidate)} / codex review ${actionBoundaryBool(
      boundary.requiresCodexOrOperatorReviewBeforeImplementation || gate.requiresCodexOrOperatorReview,
    )} / repo review ${actionBoundaryBool(boundary.requiresRepoTruthReview)}`,
    directAuthorityLine: `execute ${actionBoundaryBool(canExecute)} / mutation ${actionBoundaryBool(
      canMutate,
    )} / approve ${actionBoundaryBool(canApprove)} / memory write ${actionBoundaryBool(canWriteMemory)}`,
    detail: [
      `surface ${surface || "unknown"}`,
      `candidate ${actionBoundaryBool(canCreateCandidate)}`,
      `codex review ${actionBoundaryBool(boundary.requiresCodexOrOperatorReviewBeforeImplementation || gate.requiresCodexOrOperatorReview)}`,
      `repo review ${actionBoundaryBool(boundary.requiresRepoTruthReview)}`,
      `execute ${actionBoundaryBool(canExecute)}`,
      `mutation ${actionBoundaryBool(canMutate)}`,
      `approve ${actionBoundaryBool(canApprove)}`,
      `memory write ${actionBoundaryBool(canWriteMemory)}`,
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
        "codex prompt unknown",
        "ollama reply unknown",
        "note unknown",
        "insight unknown",
        "learning receipt unknown",
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
  const liveEvidence = health.collaborationLoop.liveHealthEvidence;
  const liveEvidenceReady = !liveEvidence.observed || liveEvidence.proofStatus === "recurring_cleanly";
  const noActionReceipts = liveEvidence.observed ? liveEvidence.noActionAuthorityReceiptsObserved : authorityNone;
  const recurringCleanly =
    health.status === "healthy" &&
    helpersReady &&
    loopFresh &&
    supervisorFresh &&
    loopActive &&
    authorityNone &&
    liveEvidenceReady &&
    noActionReceipts;

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
      `codex prompt ${health.collaborationLoop.latestTurn.codexPromptId || health.collaborationLoop.lastCodexPromptId || "unknown"}`,
      `ollama reply ${health.collaborationLoop.latestTurn.ollamaPromptId || health.collaborationLoop.lastOllamaPromptId || "unknown"}`,
      `note ${health.collaborationLoop.latestTurn.noteId || health.collaborationLoop.lastNoteId || "unknown"}`,
      `insight ${health.collaborationLoop.latestTurn.insightId || health.collaborationLoop.lastInsightId || "unknown"}`,
      `learning receipt ${health.collaborationLoop.lastLearningEventId || "unknown"}`,
      `waiting for ollama ${actionBoundaryBool(health.collaborationLoop.waitingForOllama)}`,
      `turn gap ${Math.max(0, Math.round(health.collaborationLoop.turnGapRemainingSeconds || 0))}s`,
      `live proof ${liveEvidence.proofStatus || "unknown"}`,
      `participants enabled ${liveEvidence.enabledParticipantCount || health.participants.enabledCount}/${
        liveEvidence.totalParticipantCount || health.participants.totalCount
      }`,
      `no-action receipts ${actionBoundaryBool(noActionReceipts)}`,
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
        "mutation false",
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
      `mutation ${actionBoundaryBool(receipt.grantsMutationAuthority)}`,
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

export function collaborationRuntimeLocalModelResponseSummary(
  health: CollaborationRuntimeHealth | null | undefined,
): CollaborationRuntimeLocalModelResponseDisplay {
  const response = health?.collaborationLoop.latestLocalModelResponse;
  if (!response?.observed) {
    return {
      badge: "model response unknown",
      tone: "neutral",
      detail: [
        "status unobserved",
        "guard unknown",
        "model observed false",
        "source prompt unknown",
        "reply unknown",
        "training false",
        "memory write false",
      ],
    };
  }
  const proof = response.adviceOnlyProof;
  const unsafeAuthority =
    response.storesFullTranscript ||
    response.grantsTrainingAuthority ||
    response.grantsExecutionAuthority ||
    response.grantsMutationAuthority ||
    response.grantsApprovalAuthority ||
    response.grantsMemoryWriteAuthority ||
    response.grantsCapabilityAuthority ||
    proof.storesFullTranscript ||
    proof.grantsTrainingAuthority ||
    proof.grantsExecutionAuthority ||
    proof.grantsMutationAuthority ||
    proof.grantsApprovalAuthority ||
    proof.grantsMemoryWriteAuthority ||
    proof.grantsCapabilityAuthority ||
    proof.actionReadinessClaimAllowed ||
    !proof.responseIsAdviceOnly;
  const tone = unsafeAuthority ? "blocked" : proof.outputGuardPassed ? "ready" : proof.outputGuardRewriteObserved ? "neutral" : "neutral";
  const badge = unsafeAuthority
    ? "model authority drift"
    : proof.outputGuardPassed
      ? "advice-only proof"
      : proof.outputGuardRewriteObserved
        ? "model reply guarded"
        : "model advice observed";
  return {
    badge,
    tone,
    detail: [
      `proof ${proof.proofStatus || "unknown"}`,
      `status ${response.status || "unknown"}`,
      `guard ${response.outputGuardStatus || "unknown"}`,
      `advice only ${actionBoundaryBool(proof.responseIsAdviceOnly)}`,
      `action readiness ${actionBoundaryBool(proof.actionReadinessClaimAllowed)}`,
      `review before action ${actionBoundaryBool(proof.requiresCodexOrOperatorReviewBeforeActionReadiness)}`,
      `model observed ${actionBoundaryBool(proof.modelResponseObserved || response.modelResponseObserved)}`,
      `source ${response.sourcePromptId || "unknown"}`,
      `reply ${response.responsePromptId || "unknown"}`,
      `age ${ageText(response.ageSeconds)}`,
      `training ${actionBoundaryBool(response.grantsTrainingAuthority)}`,
      `capability ${actionBoundaryBool(response.grantsCapabilityAuthority || proof.grantsCapabilityAuthority)}`,
      `memory write ${actionBoundaryBool(response.grantsMemoryWriteAuthority)}`,
    ],
  };
}

export function collaborationLearningGuardSummary(
  learning: CollaborationLearning | null | undefined,
  health: CollaborationRuntimeHealth | null | undefined,
): CollaborationLearningGuardDisplay {
  const signal = health?.collaborationLoop.currentLearningSignal;
  const latestLearning = learning?.items.find((item) => item.currentSignalObserved) ?? learning?.items[0];
  const signalObserved = Boolean(signal?.observed || latestLearning?.currentSignalObserved);
  const failureType = signal?.failureType || latestLearning?.failureType || "none";
  const latestTurn = signal?.latestTurn || latestLearning?.latestTurn || latestLearning?.turn || 0;
  const promptPolicy =
    latestLearning?.learning.nextPromptPolicy ||
    "No prompt policy recorded; keep the next exchange bounded to a concrete Francis surface.";
  const signalReview = latestLearning?.signalReview;
  const reviewPriority = signalReview?.reviewPriority || "unknown";
  const classification = signalReview?.classification || failureType || "unknown_learning_signal";
  const storesFullTranscript =
    Boolean(signal?.storesFullTranscript) ||
    Boolean(signalReview?.storesFullTranscript) ||
    Boolean(latestLearning?.memoryPromotionGate.storesFullTranscript) ||
    governanceFlag(latestLearning?.writerGovernance ?? {}, "stores_full_transcript");
  const grantsTraining =
    Boolean(signal?.grantsTrainingAuthority) ||
    Boolean(signalReview?.grantsTrainingAuthority) ||
    Boolean(latestLearning?.memoryPromotionGate.grantsTrainingAuthority) ||
    governanceFlag(latestLearning?.writerGovernance ?? {}, "grants_training_authority");
  const grantsExecution =
    Boolean(signal?.grantsExecutionAuthority) ||
    Boolean(signalReview?.grantsExecutionAuthority) ||
    Boolean(latestLearning?.memoryPromotionGate.grantsExecutionAuthority) ||
    governanceFlag(latestLearning?.writerGovernance ?? {}, "grants_execution_authority");
  const grantsMutation =
    Boolean(signal?.grantsMutationAuthority) ||
    Boolean(signalReview?.grantsMutationAuthority) ||
    Boolean(latestLearning?.memoryPromotionGate.grantsMutationAuthority) ||
    governanceFlag(latestLearning?.writerGovernance ?? {}, "grants_mutation_authority");
  const grantsApproval =
    Boolean(signal?.grantsApprovalAuthority) ||
    Boolean(signalReview?.grantsApprovalAuthority) ||
    Boolean(latestLearning?.memoryPromotionGate.grantsApprovalAuthority) ||
    governanceFlag(latestLearning?.writerGovernance ?? {}, "grants_approval_authority");
  const grantsMemoryWrite =
    Boolean(signal?.grantsMemoryWriteAuthority) ||
    Boolean(signalReview?.grantsMemoryWriteAuthority) ||
    Boolean(latestLearning?.memoryPromotionGate.grantsMemoryWriteAuthority) ||
    governanceFlag(latestLearning?.writerGovernance ?? {}, "grants_memory_write_authority");
  const promotionGate = latestLearning?.memoryPromotionGate;
  const memoryPromotionAllowed = Boolean(promotionGate?.memoryPromotionAllowed || signalReview?.memoryPromotionAllowed);
  const modelTuningAllowed = Boolean(promotionGate?.modelTuningAllowed || signalReview?.modelTuningAllowed);
  const unsafeAuthority =
    storesFullTranscript ||
    grantsTraining ||
    grantsExecution ||
    grantsMutation ||
    grantsApproval ||
    grantsMemoryWrite ||
    memoryPromotionAllowed ||
    modelTuningAllowed;
  const recentTurnCount = signal?.recentTurnCount || latestLearning?.recentTurnCount || 0;
  return {
    badge: unsafeAuthority ? "learning authority drift" : signalObserved ? "prompt guard active" : "learning guard quiet",
    tone: unsafeAuthority ? "blocked" : signalObserved ? "ready" : "neutral",
    failureType,
    latestTurn,
    reviewPriority,
    classification,
    promptPolicy,
    detail: [
      `failure ${failureType}`,
      `classification ${classification}`,
      `priority ${reviewPriority}`,
      `latest turn ${latestTurn}`,
      `recent turns ${recentTurnCount}`,
      `learning receipt ${signal?.learningEventId || latestLearning?.id || "unknown"}`,
      `review artifact ${signalReview?.requiredReviewArtifact || promotionGate?.requiredReviewArtifact || "unknown"}`,
      `memory promotion ${actionBoundaryBool(memoryPromotionAllowed)}`,
      `tuning ${actionBoundaryBool(modelTuningAllowed)}`,
      `promotion review ${actionBoundaryBool(promotionGate?.requiresMemoryPromotionReview ?? true)}`,
      `codex review ${actionBoundaryBool(signalReview?.requiresCodexOrOperatorReview ?? true)}`,
      `full transcript ${actionBoundaryBool(storesFullTranscript)}`,
      `training ${actionBoundaryBool(grantsTraining)}`,
      `execute ${actionBoundaryBool(grantsExecution)}`,
      `mutation ${actionBoundaryBool(grantsMutation)}`,
      `approve ${actionBoundaryBool(grantsApproval)}`,
      `memory write ${actionBoundaryBool(grantsMemoryWrite)}`,
    ],
  };
}

export function collaborationSubstrateChecklistSummary(
  readiness: CollaborationSubstrateReadiness | null | undefined,
): CollaborationSubstrateChecklistDisplay {
  const items = readiness?.checklist ?? [];
  const totalCount = items.length;
  const passedCount = items.filter((item) => item.status === "passed").length;
  const blockedCount = items.filter((item) => item.status !== "passed" && item.blocksMainBuildPrompt).length;
  const reviewCount = items.filter((item) => item.status !== "passed" && !item.blocksMainBuildPrompt).length;
  if (!totalCount) {
    return {
      badge: "checklist unknown",
      tone: "neutral",
      totalCount: 0,
      passedCount: 0,
      blockedCount: 0,
      reviewCount: 0,
      detail: ["passed 0/0", "blocking 0", "review 0", "gate unknown", "authority none false"],
    };
  }
  const authorityNone = Boolean(readiness?.summary.noAuthorityGranted);
  const tone = blockedCount > 0 ? "blocked" : reviewCount > 0 ? "neutral" : "ready";
  const badge =
    blockedCount > 0
      ? `checklist blocked ${blockedCount}`
      : reviewCount > 0
        ? `checklist review ${reviewCount}`
        : "checklist passed";
  return {
    badge,
    tone,
    totalCount,
    passedCount,
    blockedCount,
    reviewCount,
    detail: [
      `passed ${passedCount}/${totalCount}`,
      `blocking ${blockedCount}`,
      `review ${reviewCount}`,
      `gate ${readiness?.summary.mainBuildPromptGate || "unknown"}`,
      `wire ${readiness?.summary.boundedWiringPercentComplete ?? 0}%`,
      `authority none ${actionBoundaryBool(authorityNone)}`,
    ],
  };
}

function parseAgent(raw: unknown): CollaborationAgent {
  const item = isRecord(raw) ? raw : {};
  const enabled = safeBoolean(item.enabled);
  const updatedBy = safeString(item.updated_by);
  const reason = safeString(item.reason);
  return {
    agent: safeString(item.agent, "unknown"),
    label: safeString(item.label, safeString(item.agent, "unknown")),
    enabled,
    participantKind: safeString(item.participant_kind),
    localRunner: safeString(item.local_runner),
    authority: safeString(item.authority),
    updatedAt: safeString(item.updated_at),
    updatedBy,
    reason,
    latestToggleReceiptId: safeString(item.latest_toggle_receipt_id),
    latestToggleProofStatus: safeString(item.latest_toggle_proof_status),
    currentToggleProof: parseAgentCurrentToggleProof(item.current_toggle_proof, {
      actor: updatedBy,
      enabled,
      reason,
    }),
    writesRelayReceipts: safeBoolean(item.writes_relay_receipts),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
  };
}

function parseAgentToggleReceipt(raw: unknown): CollaborationAgentToggleReceipt {
  const item = isRecord(raw) ? raw : {};
  const enabled = safeBoolean(item.enabled);
  const previousEnabled = safeBoolean(item.previous_enabled);
  const actor = safeString(item.actor);
  const reason = safeString(item.reason);
  return {
    kind: safeString(item.kind, "developer_bridge.collaboration_agent_toggle_receipt"),
    receiptId: safeString(item.receipt_id),
    createdAt: safeString(item.created_at),
    agent: safeString(item.agent, "unknown"),
    enabled,
    previousEnabled,
    actor,
    reason,
    operatorToggleProof: parseAgentToggleProofVerdict(item.operator_toggle_proof, {
      actor,
      enabled,
      previousEnabled,
      reason,
      governance: isRecord(item.governance) ? item.governance : {},
    }),
    governance: isRecord(item.governance) ? item.governance : {},
  };
}

function parseAgentToggleProofVerdict(
  raw: unknown,
  fallback: { actor: string; enabled: boolean; previousEnabled: boolean; reason: string; governance: Record<string, unknown> },
): CollaborationAgentToggleProof {
  const item = isRecord(raw) ? raw : {};
  const governance = fallback.governance;
  return {
    proofStatus: safeString(item.proof_status, isRecord(raw) ? "unknown" : "legacy_receipt_inferred"),
    actorRecorded: safeBoolean(item.actor_recorded, Boolean(fallback.actor)),
    reasonRecorded: safeBoolean(item.reason_recorded, Boolean(fallback.reason)),
    previousStateObserved: safeBoolean(item.previous_state_observed, true),
    currentStateObserved: safeBoolean(item.current_state_observed, true),
    previousEnabled: safeBoolean(item.previous_enabled, fallback.previousEnabled),
    currentEnabled: safeBoolean(item.current_enabled, fallback.enabled),
    stateChanged: safeBoolean(item.state_changed, fallback.previousEnabled !== fallback.enabled),
    operatorConsoleActor: safeBoolean(item.operator_console_actor),
    clientCanBeOperatorConsole: safeBoolean(
      item.client_can_be_operator_console,
      safeBoolean(governance.client_can_be_operator_console),
    ),
    clientIsAutomaticExecutionAuthority: safeBoolean(
      item.client_is_automatic_execution_authority,
      safeBoolean(governance.client_is_automatic_execution_authority),
    ),
    requiresOperatorReview: safeBoolean(item.requires_operator_review, safeBoolean(governance.requires_operator_review, true)),
    provesCapabilityAuthority: safeBoolean(item.proves_capability_authority),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority, safeBoolean(governance.grants_execution_authority)),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority, safeBoolean(governance.grants_mutation_authority)),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority, safeBoolean(governance.grants_approval_authority)),
    grantsMemoryWriteAuthority: safeBoolean(
      item.grants_memory_write_authority,
      safeBoolean(governance.grants_memory_write_authority),
    ),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority, safeBoolean(governance.grants_training_authority)),
  };
}

function parseAgentCurrentToggleProof(
  raw: unknown,
  fallback: { actor: string; enabled: boolean; reason: string },
): CollaborationAgentCurrentToggleProof {
  const item = isRecord(raw) ? raw : {};
  const currentEnabled = safeBoolean(item.current_enabled, fallback.enabled);
  const previousEnabled = safeBoolean(item.previous_enabled, currentEnabled);
  const actor = safeString(item.actor, fallback.actor);
  const reason = safeString(item.reason, fallback.reason);
  const proof = parseAgentToggleProofVerdict(item, {
    actor,
    enabled: currentEnabled,
    previousEnabled,
    reason,
    governance: item,
  });
  return {
    ...proof,
    kind: safeString(item.kind, "developer_bridge.collaboration_agent_current_toggle_proof"),
    source: safeString(item.source, isRecord(raw) ? "unknown" : "missing_current_toggle_proof"),
    receiptId: safeString(item.receipt_id),
    createdAt: safeString(item.created_at),
    actor,
    reason,
    explicitOperatorToggleProof: safeBoolean(item.explicit_operator_toggle_proof),
    legacyProjection: safeBoolean(item.legacy_projection),
    defaultStateProjection: safeBoolean(item.default_state_projection, !isRecord(raw)),
    requiresNewToggleForExplicitOperatorProof: safeBoolean(item.requires_new_toggle_for_explicit_operator_proof),
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
  const sourceAgent = safeString(item.source_agent);
  const targetAgent = safeString(item.target_agent);
  return {
    id: safeString(item.id),
    createdAt: safeString(item.created_at),
    updatedAt: safeString(item.updated_at),
    status: safeString(item.status),
    sourceAgent,
    targetAgent,
    direction: safeString(item.direction),
    objective,
    prompt,
    context,
    chatText: safeString(handoff.chat_text),
    receiptKind: classifyTranscriptReceipt(objective, context, prompt),
    display: parseTranscriptDisplay(item.display, sourceAgent, targetAgent, objective, context, prompt),
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
  const actionCandidateBoundary = isRecord(item.action_candidate_boundary) ? item.action_candidate_boundary : {};
  const actionCandidateProof = isRecord(actionCandidateBoundary.current_proof)
    ? actionCandidateBoundary.current_proof
    : {};
  const buildGate = isRecord(item.build_direction_gate) ? item.build_direction_gate : {};
  const sourceDisagreementBoundary = isRecord(item.source_disagreement_boundary)
    ? item.source_disagreement_boundary
    : {};
  const sourceDisagreementProof = isRecord(sourceDisagreementBoundary.current_proof)
    ? sourceDisagreementBoundary.current_proof
    : {};
  const roadmapBoundary = isRecord(item.roadmap_alignment_boundary) ? item.roadmap_alignment_boundary : {};
  const roadmapProof = isRecord(roadmapBoundary.current_proof) ? roadmapBoundary.current_proof : {};
  const toggleBoundary = isRecord(item.participant_toggle_boundary) ? item.participant_toggle_boundary : {};
  const toggleProof = isRecord(toggleBoundary.current_proof) ? toggleBoundary.current_proof : {};
  const modelAdviceBoundary = isRecord(item.model_advice_governance_boundary)
    ? item.model_advice_governance_boundary
    : {};
  const modelAdviceProof = isRecord(modelAdviceBoundary.current_proof) ? modelAdviceBoundary.current_proof : {};
  const implementationPreflight = isRecord(item.implementation_preflight) ? item.implementation_preflight : {};
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
    actionCandidateBoundary: {
      applies: safeBoolean(actionCandidateBoundary.applies),
      surface: safeString(actionCandidateBoundary.surface),
      proofStatus: safeString(actionCandidateProof.proof_status),
      proofSource: safeString(actionCandidateProof.proof_source),
      chatSendActionCandidateReadback: safeBoolean(actionCandidateProof.chat_send_action_candidate_readback),
      chatWsActionCandidateReadback: safeBoolean(actionCandidateProof.chat_ws_action_candidate_readback),
      missionCurrentTaskReadback: safeBoolean(actionCandidateProof.mission_current_task_readback),
      missionRecordReceipt: safeString(actionCandidateProof.mission_record_receipt),
      taskRecordReceipt: safeString(actionCandidateProof.task_record_receipt),
      sourceModesObservedByTests: Array.isArray(actionCandidateProof.source_modes_observed_by_tests)
        ? actionCandidateProof.source_modes_observed_by_tests.map((entry) => safeString(entry)).filter(Boolean)
        : [],
      sourceModeProofReadback: safeBoolean(actionCandidateProof.source_mode_proof_readback),
      inputActorReadback: safeBoolean(actionCandidateProof.input_actor_readback),
      sourceModeDerivationReadback: safeBoolean(actionCandidateProof.source_mode_derivation_readback),
      voiceTurnCorrelationReadOnly: safeBoolean(actionCandidateProof.voice_turn_correlation_read_only),
      voiceTurnCorrelationGrantsExecutionAuthority: safeBoolean(
        actionCandidateProof.voice_turn_correlation_grants_execution_authority,
      ),
      voiceTurnCorrelationGrantsMutationAuthority: safeBoolean(
        actionCandidateProof.voice_turn_correlation_grants_mutation_authority,
      ),
      operationCandidateRequired: safeBoolean(actionCandidateProof.operation_candidate_required),
      missionRecordRequired: safeBoolean(actionCandidateProof.mission_record_required),
      firstOperationCandidateRequired: safeBoolean(actionCandidateProof.first_operation_candidate_required),
      directExecution: safeBoolean(actionCandidateProof.direct_execution),
      requiresPolicy: safeBoolean(actionCandidateProof.requires_policy),
      requiresApproval: safeBoolean(actionCandidateProof.requires_approval),
      requiresTraceableReceipt: safeBoolean(actionCandidateProof.requires_traceable_receipt),
      storesFullTranscript: safeBoolean(actionCandidateProof.stores_full_transcript),
      grantsExecutionAuthority: safeBoolean(actionCandidateProof.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(actionCandidateProof.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(actionCandidateProof.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(actionCandidateProof.grants_memory_write_authority),
      grantsTrainingAuthority: safeBoolean(actionCandidateProof.grants_training_authority),
      grantsCapabilityAuthority: safeBoolean(actionCandidateProof.grants_capability_authority),
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
    sourceDisagreementBoundary: {
      applies: safeBoolean(sourceDisagreementBoundary.applies),
      surface: safeString(sourceDisagreementBoundary.surface),
      proofStatus: safeString(sourceDisagreementProof.proof_status),
      reviewArtifactObserved: safeBoolean(sourceDisagreementProof.review_artifact_observed),
      requiredReviewArtifact: safeString(sourceDisagreementProof.required_review_artifact),
      surfaceUnderReview: safeString(sourceDisagreementProof.surface_under_review),
      conflictingSourceCount: safeNumber(sourceDisagreementProof.conflicting_source_count),
      conflictingSources: Array.isArray(sourceDisagreementProof.conflicting_sources)
        ? sourceDisagreementProof.conflicting_sources.map((source) => {
            const sourceRecord = isRecord(source) ? source : {};
            return {
              source: safeString(sourceRecord.source),
              receiptId: safeString(sourceRecord.receipt_id),
              role: safeString(sourceRecord.role),
              providerLane: safeString(sourceRecord.provider_lane),
            };
          })
        : [],
      blocksBuildDirection: safeBoolean(sourceDisagreementProof.blocks_build_direction),
      conversationCanChooseWinner: safeBoolean(sourceDisagreementProof.conversation_can_choose_winner),
      conversationCanExecuteResolution: safeBoolean(sourceDisagreementProof.conversation_can_execute_resolution),
      requiresTypedReviewArtifact: safeBoolean(sourceDisagreementProof.requires_typed_review_artifact),
      requiresCodexOrOperatorReview: safeBoolean(sourceDisagreementProof.requires_codex_or_operator_review),
      requiresRepoTruthReview: safeBoolean(sourceDisagreementProof.requires_repo_truth_review),
      proofSource: safeString(sourceDisagreementProof.proof_source),
      storesFullTranscript: safeBoolean(sourceDisagreementProof.stores_full_transcript),
      grantsBuildDirectionAuthority: safeBoolean(sourceDisagreementProof.grants_build_direction_authority),
      grantsExecutionAuthority: safeBoolean(sourceDisagreementProof.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(sourceDisagreementProof.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(sourceDisagreementProof.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(sourceDisagreementProof.grants_memory_write_authority),
      grantsTrainingAuthority: safeBoolean(sourceDisagreementProof.grants_training_authority),
      grantsCapabilityAuthority: safeBoolean(sourceDisagreementProof.grants_capability_authority),
    },
    roadmapAlignmentProof: {
      latestLedgerEntry: safeString(roadmapProof.latest_ledger_entry),
      currentPhase: safeString(roadmapProof.current_phase),
      currentPhasePosture: safeString(roadmapProof.current_phase_posture),
      currentPriorityOrPlaneLine: safeString(roadmapProof.current_priority_or_plane_line),
      ledgerObserved: safeBoolean(roadmapProof.ledger_observed),
      manifestObserved: safeBoolean(roadmapProof.manifest_observed),
      sourcesObserved: safeBoolean(roadmapProof.sources_observed),
      sourceOrder: Array.isArray(roadmapProof.source_order) ? roadmapProof.source_order.map((entry) => safeString(entry)).filter(Boolean) : [],
      coverageOpenGapCount: safeNumber(roadmapProof.coverage_open_gap_count),
      remainingBlockers: Array.isArray(roadmapProof.remaining_blockers)
        ? roadmapProof.remaining_blockers.map((entry) => safeString(entry)).filter(Boolean)
        : [],
      mainBuildPromptAllowed: safeBoolean(roadmapProof.main_build_prompt_allowed),
      mainBuildPromptGate: safeString(roadmapProof.main_build_prompt_gate),
      mainBuildPromptCandidateOnly: safeBoolean(roadmapProof.main_build_prompt_candidate_only),
      conversationCanOverrideRoadmap: safeBoolean(roadmapProof.conversation_can_override_roadmap),
      proofSource: safeString(roadmapProof.proof_source),
      storesFullTranscript: safeBoolean(roadmapProof.stores_full_transcript),
      grantsExecutionAuthority: safeBoolean(roadmapProof.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(roadmapProof.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(roadmapProof.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(roadmapProof.grants_memory_write_authority),
      grantsTrainingAuthority: safeBoolean(roadmapProof.grants_training_authority),
    },
    participantToggleBoundary: {
      applies: safeBoolean(toggleBoundary.applies),
      surface: safeString(toggleBoundary.surface),
      disabledParticipantBlocksNewRelaySubmissions: safeBoolean(
        toggleBoundary.disabled_participant_blocks_new_relay_submissions,
      ),
      requiresOperatorToggleProof: safeBoolean(toggleBoundary.requires_operator_toggle_proof),
      visibilityIsCapabilityGrant: safeBoolean(toggleBoundary.visibility_is_capability_grant),
      participantEnablementIsExecutionAuthority: safeBoolean(
        toggleBoundary.participant_enablement_is_execution_authority,
      ),
      receiptKind: safeString(toggleProof.receipt_kind),
      knownAgents: Array.isArray(toggleProof.known_agents) ? toggleProof.known_agents.map((entry) => safeString(entry)).filter(Boolean) : [],
      receiptCount: safeNumber(toggleProof.receipt_count),
      proofReceiptCount: safeNumber(toggleProof.proof_receipt_count),
      legacyReceiptCount: safeNumber(toggleProof.legacy_receipt_count),
      latestReceiptId: safeString(toggleProof.latest_receipt_id),
      latestAgent: safeString(toggleProof.latest_agent),
      agentCurrentToggleProofCount: safeNumber(toggleProof.agent_current_toggle_proof_count),
      agentExplicitOperatorToggleProofCount: safeNumber(toggleProof.agent_explicit_operator_toggle_proof_count),
      agentLegacyProjectionCount: safeNumber(toggleProof.agent_legacy_projection_count),
      agentDefaultStateProjectionCount: safeNumber(toggleProof.agent_default_state_projection_count),
      agentsWithExplicitOperatorToggleProof: Array.isArray(toggleProof.agents_with_explicit_operator_toggle_proof)
        ? toggleProof.agents_with_explicit_operator_toggle_proof.map((entry) => safeString(entry)).filter(Boolean)
        : [],
      agentsMissingExplicitOperatorToggleProof: Array.isArray(toggleProof.agents_missing_explicit_operator_toggle_proof)
        ? toggleProof.agents_missing_explicit_operator_toggle_proof.map((entry) => safeString(entry)).filter(Boolean)
        : [],
      allAgentsHaveCurrentToggleReadback: safeBoolean(toggleProof.all_agents_have_current_toggle_readback),
      allAgentsHaveExplicitOperatorToggleProof: safeBoolean(toggleProof.all_agents_have_explicit_operator_toggle_proof),
      operatorConsoleActor: safeString(toggleProof.operator_console_actor),
      clientCanBeOperatorConsole: safeBoolean(toggleProof.client_can_be_operator_console),
      clientIsAutomaticExecutionAuthority: safeBoolean(toggleProof.client_is_automatic_execution_authority),
      proofSource: safeString(toggleProof.proof_source),
      agentProofs: Array.isArray(toggleProof.agent_proofs)
        ? toggleProof.agent_proofs.map((entry) => {
            const proof = isRecord(entry) ? entry : {};
            return {
              agent: safeString(proof.agent),
              enabled: safeBoolean(proof.enabled),
              proofStatus: safeString(proof.proof_status),
              source: safeString(proof.source),
              receiptId: safeString(proof.receipt_id),
              explicitOperatorToggleProof: safeBoolean(proof.explicit_operator_toggle_proof),
              legacyProjection: safeBoolean(proof.legacy_projection),
              defaultStateProjection: safeBoolean(proof.default_state_projection),
              requiresNewToggleForExplicitOperatorProof: safeBoolean(
                proof.requires_new_toggle_for_explicit_operator_proof,
              ),
              actorRecorded: safeBoolean(proof.actor_recorded),
              reasonRecorded: safeBoolean(proof.reason_recorded),
              currentStateObserved: safeBoolean(proof.current_state_observed),
              grantsExecutionAuthority: safeBoolean(proof.grants_execution_authority),
              grantsCapabilityAuthority: safeBoolean(proof.grants_capability_authority),
            };
          })
        : [],
      storesFullTranscript: safeBoolean(toggleProof.stores_full_transcript),
      grantsExecutionAuthority: safeBoolean(toggleProof.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(toggleProof.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(toggleProof.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(toggleProof.grants_memory_write_authority),
      grantsTrainingAuthority: safeBoolean(toggleProof.grants_training_authority),
      grantsCapabilityAuthority: safeBoolean(toggleProof.grants_capability_authority),
    },
    modelAdviceGovernanceBoundary: {
      applies: safeBoolean(modelAdviceBoundary.applies),
      surface: safeString(modelAdviceBoundary.surface),
      actionReadinessClaimAllowed: safeBoolean(modelAdviceBoundary.action_readiness_claim_allowed),
      modelAdviceCanCreateActionCandidate: safeBoolean(modelAdviceBoundary.model_advice_can_create_action_candidate),
      modelAdviceCanExecuteAction: safeBoolean(modelAdviceBoundary.model_advice_can_execute_action),
      modelAdviceCanApproveAction: safeBoolean(modelAdviceBoundary.model_advice_can_approve_action),
      requiresActionBoundaryReadback: safeBoolean(modelAdviceBoundary.requires_action_boundary_readback),
      requiresLatestLocalModelAdviceOnlyProof: safeBoolean(
        modelAdviceBoundary.requires_latest_local_model_advice_only_proof,
      ),
      requiresPolicy: safeBoolean(modelAdviceBoundary.requires_policy),
      requiresApproval: safeBoolean(modelAdviceBoundary.requires_approval),
      requiresTraceableReceipt: safeBoolean(modelAdviceBoundary.requires_traceable_receipt),
      requiresActionCandidateBoundary: safeBoolean(modelAdviceBoundary.requires_action_candidate_boundary),
      proofStatus: safeString(modelAdviceProof.proof_status),
      runtimeStatus: safeString(modelAdviceProof.runtime_status),
      modelResponseObserved: safeBoolean(modelAdviceProof.model_response_observed),
      latestResponseStatus: safeString(modelAdviceProof.latest_response_status),
      sourcePromptId: safeString(modelAdviceProof.source_prompt_id),
      responsePromptId: safeString(modelAdviceProof.response_prompt_id),
      outputGuardStatus: safeString(modelAdviceProof.output_guard_status),
      outputGuardPassed: safeBoolean(modelAdviceProof.output_guard_passed),
      outputGuardRewriteObserved: safeBoolean(modelAdviceProof.output_guard_rewrite_observed),
      responseIsAdviceOnly: safeBoolean(modelAdviceProof.response_is_advice_only),
      requiredGates: Array.isArray(modelAdviceProof.required_gates)
        ? modelAdviceProof.required_gates.map((entry) => safeString(entry)).filter(Boolean)
        : [],
      proofSource: safeString(modelAdviceProof.proof_source),
      storesFullTranscript: safeBoolean(modelAdviceProof.stores_full_transcript),
      grantsExecutionAuthority: safeBoolean(modelAdviceProof.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(modelAdviceProof.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(modelAdviceProof.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(modelAdviceProof.grants_memory_write_authority),
      grantsTrainingAuthority: safeBoolean(modelAdviceProof.grants_training_authority),
      grantsCapabilityAuthority: safeBoolean(modelAdviceProof.grants_capability_authority),
    },
    implementationPreflight: parseImplementationPreflight(implementationPreflight),
    governance: isRecord(item.governance) ? item.governance : {},
  };
}

function parseImplementationPreflight(raw: unknown): CollaborationImplementationPreflight {
  const item = isRecord(raw) ? raw : {};
  return {
    mustReadBeforeEditing: safeBoolean(item.must_read_before_editing),
    reviewItemId: safeString(item.review_item_id),
    insightId: safeString(item.insight_id),
    reviewArtifact: safeString(item.review_artifact),
    reviewRoute: safeString(item.review_route),
    surfaceUnderReview: safeString(item.surface_under_review),
    buildDirectionState: safeString(item.build_direction_state, "advisory_review_required"),
    requiresTypedReviewArtifact: safeBoolean(item.requires_typed_review_artifact),
    requiresCodexOrOperatorReview: safeBoolean(item.requires_codex_or_operator_review),
    requiresRepoTruthReview: safeBoolean(item.requires_repo_truth_review),
    validatedAgainstRepoTruth: safeBoolean(item.validated_against_repo_truth),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
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

function parseLearningSignalReview(raw: unknown, fallbackEventId: string): CollaborationLearningSignalReview {
  const item = isRecord(raw) ? raw : {};
  return {
    applies: safeBoolean(item.applies, true),
    classification: safeString(item.classification, "unknown_learning_signal"),
    reviewPriority: safeString(item.review_priority, "low"),
    impact: safeString(item.impact),
    failureType: safeString(item.failure_type),
    currentSignalRecentTurnCount: safeNumber(item.current_signal_recent_turn_count),
    recentTurnCount: safeNumber(item.recent_turn_count),
    repeatedTermCount: safeNumber(item.repeated_term_count),
    requiredReviewArtifact: safeString(
      item.required_review_artifact,
      fallbackEventId ? `developer_bridge.collaboration_driver.learning_events:${fallbackEventId}` : "",
    ),
    recommendedNextAction: safeString(
      item.recommended_next_action,
      "Review the bounded learning receipt before tuning or memory promotion.",
    ),
    memoryPromotionAllowed: safeBoolean(item.memory_promotion_allowed),
    longTermMemoryPromotionAllowed: safeBoolean(item.long_term_memory_promotion_allowed),
    modelTuningAllowed: safeBoolean(item.model_tuning_allowed),
    requiresCodexOrOperatorReview: safeBoolean(item.requires_codex_or_operator_review, true),
    requiresRepoTruthReview: safeBoolean(item.requires_repo_truth_review, true),
    storesFullTranscript: safeBoolean(item.stores_full_transcript),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
  };
}

function parseLearningMemoryPromotionGate(raw: unknown, fallbackEventId: string): CollaborationLearningMemoryPromotionGate {
  const item = isRecord(raw) ? raw : {};
  return {
    applies: safeBoolean(item.applies, true),
    sourceEventId: safeString(item.source_event_id, fallbackEventId),
    failureIsLearningEvidence: safeBoolean(item.failure_is_learning_evidence, true),
    memoryPromotionAllowed: safeBoolean(item.memory_promotion_allowed),
    longTermMemoryPromotionAllowed: safeBoolean(item.long_term_memory_promotion_allowed),
    modelTuningAllowed: safeBoolean(item.model_tuning_allowed),
    requiresCodexOrOperatorReview: safeBoolean(item.requires_codex_or_operator_review, true),
    requiresRepoTruthReview: safeBoolean(item.requires_repo_truth_review, true),
    requiresMemoryPromotionReview: safeBoolean(item.requires_memory_promotion_review, true),
    requiredReviewArtifact: safeString(
      item.required_review_artifact,
      fallbackEventId ? `developer_bridge.collaboration_driver.learning_events:${fallbackEventId}` : "",
    ),
    nextCodexAction: safeString(item.next_codex_action, "Review the bounded learning receipt before tuning or memory promotion."),
    storesFullTranscript: safeBoolean(item.stores_full_transcript),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
  };
}

function parseLearningEvent(raw: unknown): CollaborationLearningEvent {
  const item = isRecord(raw) ? raw : {};
  const learning = isRecord(item.learning) ? item.learning : {};
  const id = safeString(item.id);
  return {
    id,
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
    signalReview: parseLearningSignalReview(item.signal_review, id),
    memoryPromotionGate: parseLearningMemoryPromotionGate(item.memory_promotion_gate, id),
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
    latestReviewGate: parseSessionReviewGate(item.latest_review_gate),
    transcriptDisclosure: parseSessionTranscriptDisclosure(item.transcript_disclosure),
  };
}

function parseSessionTranscriptDisclosure(raw: unknown): CollaborationSessionTranscriptDisclosure {
  const item = isRecord(raw) ? raw : {};
  return {
    summaryBeforeRawTranscript: safeBoolean(item.summary_before_raw_transcript),
    safePreviewAvailable: safeBoolean(item.safe_preview_available),
    rawTranscriptOpenedByDefault: safeBoolean(item.raw_transcript_opened_by_default),
    rawReceiptDetailsOpenedByDefault: safeBoolean(item.raw_receipt_details_opened_by_default),
    technicalReceiptsOpenedByDefault: safeBoolean(item.technical_receipts_opened_by_default),
    storesFullTranscript: safeBoolean(item.stores_full_transcript),
    operatorReviewSurface: safeString(item.operator_review_surface),
    disclosureLabel: safeString(item.disclosure_label),
  };
}

function parseSessionReviewGate(raw: unknown): CollaborationSessionReviewGate {
  const item = isRecord(raw) ? raw : {};
  return {
    observed: safeBoolean(item.observed),
    reviewItemId: safeString(item.review_item_id),
    insightId: safeString(item.insight_id),
    turn: safeNumber(item.turn),
    topic: safeString(item.topic),
    buildIssueCode: safeString(item.build_issue_code),
    surface: safeString(item.surface),
    requiredReviewArtifact: safeString(item.required_review_artifact),
    buildDirectionState: safeString(item.build_direction_state, "advisory_review_required"),
    blocksBuildDirection: safeBoolean(item.blocks_build_direction),
    requiresCodexOrOperatorReview: safeBoolean(item.requires_codex_or_operator_review),
    requiresRepoTruthReview: safeBoolean(item.requires_repo_truth_review),
    nextCodexAction: safeString(item.next_codex_action),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
    storesFullTranscript: safeBoolean(item.stores_full_transcript),
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
    capabilityExposure: parseFrancisBodySurfaceCapabilityExposure(item.capability_exposure),
    informationSafety: parseFrancisBodyInformationSafety(item.information_safety),
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

function parseFrancisBodySurfaceCapabilityExposure(raw: unknown): FrancisBodySurfaceCapabilityExposure {
  const item = isRecord(raw) ? raw : {};
  return {
    visibleToFrancis1: safeBoolean(item.visible_to_francis1),
    knownSurface: safeBoolean(item.known_surface, safeBoolean(item.visible_to_francis1)),
    readbackConnected: safeBoolean(item.readback_connected),
    connectedToLocalModel: safeBoolean(item.connected_to_local_model),
    capabilityGranted: safeBoolean(item.capability_granted),
    grantState: safeString(item.grant_state, "not_granted"),
    grantableAfterTrust: safeBoolean(item.grantable_after_trust),
    grantRequires: Array.isArray(item.grant_requires) ? item.grant_requires.map((entry) => safeString(entry)).filter(Boolean) : [],
    denyAfterGrantSupported: safeBoolean(item.deny_after_grant_supported, true),
    revocationState: safeString(item.revocation_state, "revocable_for_tuning"),
    canDenyAfterFactForTuning: safeBoolean(item.can_deny_after_fact_for_tuning, true),
    safeForCapabilityUse: safeBoolean(item.safe_for_capability_use),
    capabilityUseStatus: safeString(item.capability_use_status, "not_exposed"),
    currentAccessMode: safeString(item.current_access_mode),
    grantedAccessMode: safeString(item.granted_access_mode, "observe"),
    nextTrustGate: safeString(item.next_trust_gate),
    requiresGovernedRequest: safeBoolean(item.requires_governed_request, true),
    requiresCodexOrOperatorReviewBeforeCapabilityExposure: safeBoolean(
      item.requires_codex_or_operator_review_before_capability_exposure,
      true,
    ),
    reason: safeString(item.reason),
    grantsCapabilityAuthority: safeBoolean(item.grants_capability_authority),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority),
    detachedMemoryBin: parseDetachedMemoryBinPolicy(item.detached_memory_bin),
  };
}

function parseDetachedMemoryBinPolicy(raw: unknown): FrancisDetachedMemoryBinPolicy {
  const item = isRecord(raw) ? raw : {};
  return {
    applies: safeBoolean(item.applies),
    kind: safeString(item.kind, "developer_bridge.detached_memory_bin_policy"),
    status: safeString(item.status, "not_applicable"),
    retainsMemory: safeBoolean(item.retains_memory),
    requiredForCurrentContext: safeBoolean(item.required_for_current_context),
    usedByDefault: safeBoolean(item.used_by_default),
    injectsIntoPromptContext: safeBoolean(item.injects_into_prompt_context),
    keepsStaleMemoryOutOfRequiredContext: safeBoolean(item.keeps_stale_memory_out_of_required_context, true),
    promotionRequiresReview: safeBoolean(item.promotion_requires_review, true),
    canDenyAfterFactForTuning: safeBoolean(item.can_deny_after_fact_for_tuning, true),
    storesFullTranscript: safeBoolean(item.stores_full_transcript),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority),
  };
}

function parseStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => safeString(item)).filter(Boolean) : [];
}

function parseFrancisBodyExposureSummary(raw: unknown): FrancisBodyExposureSummary {
  const item = isRecord(raw) ? raw : {};
  return {
    kind: safeString(item.kind, "developer_bridge.francis_body_exposure_summary"),
    schemaVersion: safeString(item.schema_version, "developer_bridge_francis_body_exposure_summary_v1"),
    surface: safeString(item.surface, "developer_bridge.francis_body_map.exposure_summary"),
    status: safeString(item.status, "unknown"),
    francis1CanSeeBody: safeBoolean(item.francis1_can_see_body),
    francis1CanUseAllVisibleSurfaces: safeBoolean(item.francis1_can_use_all_visible_surfaces),
    visibleSurfaceCount: safeNumber(item.visible_surface_count),
    readbackConnectedSurfaceCount: safeNumber(item.readback_connected_surface_count),
    connectedToLocalModelCount: safeNumber(item.connected_to_local_model_count),
    capabilityGrantedCount: safeNumber(item.capability_granted_count),
    safeForCapabilityUseCount: safeNumber(item.safe_for_capability_use_count),
    notExposedSurfaceCount: safeNumber(item.not_exposed_surface_count),
    reviewRequiredSurfaceCount: safeNumber(item.review_required_surface_count),
    grantRequiredBeforeUseCount: safeNumber(item.grant_required_before_use_count),
    detachedMemorySurfaceCount: safeNumber(item.detached_memory_surface_count),
    visibleSurfaceIds: parseStringList(item.visible_surface_ids),
    readbackConnectedSurfaceIds: parseStringList(item.readback_connected_surface_ids),
    connectedToLocalModelSurfaceIds: parseStringList(item.connected_to_local_model_surface_ids),
    grantedSurfaceIds: parseStringList(item.granted_surface_ids),
    safeForCapabilityUseSurfaceIds: parseStringList(item.safe_for_capability_use_surface_ids),
    notExposedSurfaceIds: parseStringList(item.not_exposed_surface_ids),
    reviewRequiredSurfaceIds: parseStringList(item.review_required_surface_ids),
    grantRequiredBeforeUseSurfaceIds: parseStringList(item.grant_required_before_use_surface_ids),
    detachedMemorySurfaceIds: parseStringList(item.detached_memory_surface_ids),
    operatorReviewRequiredBeforeNewExposure: safeBoolean(item.operator_review_required_before_new_exposure, true),
    capabilityGrantReceiptRequiredBeforeUse: safeBoolean(item.capability_grant_receipt_required_before_use, true),
    denyAfterGrantSupported: safeBoolean(item.deny_after_grant_supported, true),
    storesFullTranscript: safeBoolean(item.stores_full_transcript),
    grantsCapabilityAuthority: safeBoolean(item.grants_capability_authority),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority),
    nextReadbacks: parseStringList(item.next_readbacks),
  };
}

function parseFrancisBodyInformationSafety(raw: unknown): FrancisBodyInformationSafety {
  const item = isRecord(raw) ? raw : {};
  return {
    kind: safeString(item.kind, "developer_bridge.francis_body_information_safety"),
    schemaVersion: safeString(item.schema_version, "developer_bridge_francis_body_information_safety_v1"),
    surface: safeString(item.surface, "developer_bridge.francis_body_map.information_safety"),
    surfaceId: safeString(item.surface_id),
    status: safeString(item.status, "unknown"),
    validatedReadback: safeBoolean(item.validated_readback),
    payloadScope: safeString(item.payload_scope, "metadata_only"),
    visibleSurfaceCount: safeNumber(item.visible_surface_count),
    sensitiveSurfaceCount: safeNumber(item.sensitive_surface_count),
    reviewRequiredSurfaceCount: safeNumber(item.review_required_surface_count),
    evidencePathCount: safeNumber(item.evidence_path_count),
    relativeEvidencePathCount: safeNumber(item.relative_evidence_path_count),
    absoluteEvidencePathCount: safeNumber(item.absolute_evidence_path_count),
    sensitiveSurfaceIds: parseStringList(item.sensitive_surface_ids),
    reviewRequiredSurfaceIds: parseStringList(item.review_required_surface_ids),
    exposedPathFormat: safeString(item.exposed_path_format, "repo_relative_only"),
    evidencePathFormat: safeString(item.evidence_path_format, "repo_relative"),
    exposesLabel: safeBoolean(item.exposes_label),
    exposesDescription: safeBoolean(item.exposes_description),
    exposesCurrentBoundary: safeBoolean(item.exposes_current_boundary),
    exposesEvidencePaths: safeBoolean(item.exposes_evidence_paths),
    sensitiveSurface: safeBoolean(item.sensitive_surface),
    storesRawTranscript: safeBoolean(item.stores_raw_transcript),
    storesFullTranscript: safeBoolean(item.stores_full_transcript),
    storesFileContents: safeBoolean(item.stores_file_contents),
    storesSecretValues: safeBoolean(item.stores_secret_values),
    exposesAbsoluteLocalPaths: safeBoolean(item.exposes_absolute_local_paths),
    exposesEnvironmentValues: safeBoolean(item.exposes_environment_values),
    embedsCapabilityReceipts: safeBoolean(item.embeds_capability_receipts),
    embedsMemoryRecords: safeBoolean(item.embeds_memory_records),
    embedsModelTrainingData: safeBoolean(item.embeds_model_training_data),
    requiresCodexOrOperatorReviewBeforeExpandingDetail: safeBoolean(
      item.requires_codex_or_operator_review_before_expanding_detail,
      true,
    ),
    detailExpansionAllowed: safeBoolean(item.detail_expansion_allowed),
    bodyMapVisibilityIsNotPromptInjectionAuthority: safeBoolean(
      item.body_map_visibility_is_not_prompt_injection_authority,
      true,
    ),
    grantsCapabilityAuthority: safeBoolean(item.grants_capability_authority),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority),
    validationRule: safeString(item.validation_rule),
    nextReadbacks: parseStringList(item.next_readbacks),
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

function parseLocalModelAdviceOnlyProof(
  raw: unknown,
  fallback: {
    modelResponseObserved: boolean;
    sourcePromptId: string;
    responsePromptId: string;
    outputGuardStatus: string;
    storesFullTranscript: boolean;
    grantsTrainingAuthority: boolean;
    grantsExecutionAuthority: boolean;
    grantsMutationAuthority: boolean;
    grantsApprovalAuthority: boolean;
    grantsMemoryWriteAuthority: boolean;
    grantsCapabilityAuthority: boolean;
  },
): CollaborationLocalModelAdviceOnlyProof {
  const item = isRecord(raw) ? raw : {};
  const guardStatus = safeString(item.output_guard_status, fallback.outputGuardStatus || "unknown");
  const guardRewrite =
    guardStatus.endsWith("_rewritten") ||
    guardStatus === "empty_reply" ||
    guardStatus === "disabled" ||
    safeBoolean(item.output_guard_rewrite_observed);
  return {
    proofStatus: safeString(item.proof_status, isRecord(raw) ? "unknown" : "legacy_response_inferred"),
    modelResponseObserved: safeBoolean(item.model_response_observed, fallback.modelResponseObserved),
    sourcePromptId: safeString(item.source_prompt_id, fallback.sourcePromptId),
    responsePromptId: safeString(item.response_prompt_id, fallback.responsePromptId),
    outputGuardStatus: guardStatus,
    outputGuardPassed: safeBoolean(item.output_guard_passed, guardStatus === "passed"),
    outputGuardRewriteObserved: guardRewrite,
    responseIsAdviceOnly: safeBoolean(item.response_is_advice_only, true),
    actionReadinessClaimAllowed: safeBoolean(item.action_readiness_claim_allowed),
    requiresCodexOrOperatorReviewBeforeActionReadiness: safeBoolean(
      item.requires_codex_or_operator_review_before_action_readiness,
      true,
    ),
    storesFullTranscript: safeBoolean(item.stores_full_transcript, fallback.storesFullTranscript),
    grantsTrainingAuthority: safeBoolean(item.grants_training_authority, fallback.grantsTrainingAuthority),
    grantsExecutionAuthority: safeBoolean(item.grants_execution_authority, fallback.grantsExecutionAuthority),
    grantsMutationAuthority: safeBoolean(item.grants_mutation_authority, fallback.grantsMutationAuthority),
    grantsApprovalAuthority: safeBoolean(item.grants_approval_authority, fallback.grantsApprovalAuthority),
    grantsMemoryWriteAuthority: safeBoolean(item.grants_memory_write_authority, fallback.grantsMemoryWriteAuthority),
    grantsCapabilityAuthority: safeBoolean(item.grants_capability_authority, fallback.grantsCapabilityAuthority),
  };
}

export function parseCollaborationAgentsStatus(raw: unknown): CollaborationAgentsStatus {
  const value = isRecord(raw) ? raw : {};
  const operatorConsole = isRecord(value.operator_console) ? value.operator_console : {};
  const definitions = isRecord(value.definitions) ? value.definitions : {};
  return {
    ok: safeBoolean(value.ok),
    mode: safeString(value.mode, "unknown"),
    relay: safeString(value.relay),
    agents: Array.isArray(value.agents) ? value.agents.map(parseAgent) : [],
    receipts: Array.isArray(value.receipts) ? value.receipts.map(parseAgentToggleReceipt) : [],
    definitions: {
      operatorToggleProof: safeString(definitions.operator_toggle_proof),
      currentToggleProof: safeString(definitions.current_toggle_proof),
    },
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
  const capabilityGrants = isRecord(value.capability_grants) ? value.capability_grants : {};
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
      visibleSurfaceCount: safeNumber(summary.visible_surface_count),
      connectedToLocalModelCount: safeNumber(summary.connected_to_local_model_count),
      capabilityGrantedCount: safeNumber(summary.capability_granted_count),
      notExposedSurfaceCount: safeNumber(summary.not_exposed_surface_count),
      reviewRequiredSurfaceCount: safeNumber(summary.review_required_surface_count),
      informationSafetyValidated: safeBoolean(summary.information_safety_validated),
      sensitiveSurfaceCount: safeNumber(summary.sensitive_surface_count),
      absoluteEvidencePathCount: safeNumber(summary.absolute_evidence_path_count),
      activeCapabilityGrantCount: safeNumber(summary.active_capability_grant_count),
      deniedOrRevokedCapabilityCount: safeNumber(summary.denied_or_revoked_capability_count),
      trustLadderEnforced: safeBoolean(summary.trust_ladder_enforced),
      runtimeRestartObserved: safeBoolean(summary.runtime_restart_observed),
      coverageReviewed: safeBoolean(summary.coverage_reviewed),
      canonicalPlaneCount: safeNumber(summary.canonical_plane_count),
      canonicalPlaneCoveredCount: safeNumber(summary.canonical_plane_covered_count),
      coverageOpenGapCount: safeNumber(summary.coverage_open_gap_count),
    },
    exposureSummary: parseFrancisBodyExposureSummary(value.exposure_summary),
    informationSafety: parseFrancisBodyInformationSafety(value.information_safety),
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
      missingCanonicalPlaneIds: parseStringList(evidence.missing_canonical_plane_ids),
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
      missingPlaneIds: parseStringList(coverageReview.missing_plane_ids),
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
    capabilityGrants: {
      surface: safeString(capabilityGrants.surface),
      route: safeString(capabilityGrants.route),
      connected: safeBoolean(capabilityGrants.connected),
      activeGrantsPresent: safeBoolean(capabilityGrants.active_grants_present),
      grantedCount: safeNumber(capabilityGrants.granted_count),
      deniedOrRevokedCount: safeNumber(capabilityGrants.denied_or_revoked_count),
      denyAfterGrantSupported: safeBoolean(capabilityGrants.deny_after_grant_supported, true),
      grantsExecutionAuthority: safeBoolean(capabilityGrants.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(capabilityGrants.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(capabilityGrants.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(capabilityGrants.grants_memory_write_authority),
      grantsTrainingAuthority: safeBoolean(capabilityGrants.grants_training_authority),
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
  const roadmapAlignment = isRecord(value.roadmap_alignment) ? value.roadmap_alignment : {};
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
      openOrbGapPlaneIds: Array.isArray(summary.open_orb_gap_plane_ids)
        ? summary.open_orb_gap_plane_ids.map((item) => safeString(item)).filter(Boolean)
        : [],
      trustLadderEnforced: safeBoolean(summary.trust_ladder_enforced),
      runtimeHealthy: safeBoolean(summary.runtime_healthy),
      learningReceiptsBounded: safeBoolean(summary.learning_receipts_bounded),
      noAuthorityGranted: safeBoolean(summary.no_authority_granted),
    },
    roadmapAlignment: {
      status: safeString(roadmapAlignment.status, "unknown"),
      requiredSources: Array.isArray(roadmapAlignment.required_sources)
        ? roadmapAlignment.required_sources.map((item) => safeString(item)).filter(Boolean)
        : [],
      sourceOrder: Array.isArray(roadmapAlignment.source_order)
        ? roadmapAlignment.source_order.map((item) => safeString(item)).filter(Boolean)
        : [],
      ledgerFirst: safeBoolean(roadmapAlignment.ledger_first),
      ledgerObserved: safeBoolean(roadmapAlignment.ledger_observed),
      manifestObserved: safeBoolean(roadmapAlignment.manifest_observed),
      sourcesObserved: safeBoolean(roadmapAlignment.sources_observed),
      mainBuildPromptAllowed: safeBoolean(roadmapAlignment.main_build_prompt_allowed),
      mainBuildPromptGate: safeString(roadmapAlignment.main_build_prompt_gate, "requires_alignment_review"),
      candidateOnlyUntilReview: safeBoolean(roadmapAlignment.candidate_only_until_review),
      blocksMainBuildPrompt: safeBoolean(roadmapAlignment.blocks_main_build_prompt),
      blockingItems: Array.isArray(roadmapAlignment.blocking_items)
        ? roadmapAlignment.blocking_items.map((item) => safeString(item)).filter(Boolean)
        : [],
      openOrbGapCount: safeNumber(roadmapAlignment.open_orb_gap_count),
      openOrbGapPlaneIds: Array.isArray(roadmapAlignment.open_orb_gap_plane_ids)
        ? roadmapAlignment.open_orb_gap_plane_ids.map((item) => safeString(item)).filter(Boolean)
        : [],
      nextCheck: safeString(roadmapAlignment.next_check),
      grantsExecutionAuthority: safeBoolean(roadmapAlignment.grants_execution_authority),
      grantsMutationAuthority: safeBoolean(roadmapAlignment.grants_mutation_authority),
      grantsApprovalAuthority: safeBoolean(roadmapAlignment.grants_approval_authority),
      grantsMemoryWriteAuthority: safeBoolean(roadmapAlignment.grants_memory_write_authority),
    },
    checklist: Array.isArray(value.checklist) ? value.checklist.map(parseCollaborationSubstrateChecklistItem) : [],
    blockingItems: Array.isArray(value.blocking_items) ? value.blocking_items.map((item) => safeString(item)).filter(Boolean) : [],
    openOrbGaps: Array.isArray(value.open_orb_gaps) ? value.open_orb_gaps.map(parseCollaborationSubstrateOpenOrbGap) : [],
    nextAction: safeString(value.next_action),
    definitions: {
      collaborationSubstrateWired: safeString(definitions.collaboration_substrate_wired),
      mainBuildPromptAllowed: safeString(definitions.main_build_prompt_allowed),
      blockingItems: safeString(definitions.blocking_items),
      roadmapAlignment: safeString(definitions.roadmap_alignment),
      openOrbGaps: safeString(definitions.open_orb_gaps),
    },
    sourceReadbacks: Object.fromEntries(Object.entries(sourceReadbacks).map(([key, item]) => [key, safeString(item)])),
    readbackCache: parseReadbackCache(value.readback_cache),
    governance: isRecord(value.governance) ? value.governance : {},
  };
}

function parseCollaborationSubstrateOpenOrbGap(raw: unknown): CollaborationSubstrateOpenOrbGap {
  const value = isRecord(raw) ? raw : {};
  return {
    planeId: safeString(value.plane_id),
    planeName: safeString(value.plane_name),
    bodySurfaceId: safeString(value.body_surface_id),
    currentPosture: safeString(value.current_posture),
    riskLevel: safeString(value.risk_level),
    riskStatement: safeString(value.risk_statement),
    remainingGaps: Array.isArray(value.remaining_gaps) ? value.remaining_gaps.map((item) => safeString(item)).filter(Boolean) : [],
    nextReviewArtifact: safeString(value.next_review_artifact),
    recommendedNextAction: safeString(value.recommended_next_action),
    blocksMainBuildPrompt: safeBoolean(value.blocks_main_build_prompt),
    grantsExecutionAuthority: safeBoolean(value.grants_execution_authority),
    grantsMutationAuthority: safeBoolean(value.grants_mutation_authority),
    grantsApprovalAuthority: safeBoolean(value.grants_approval_authority),
    grantsMemoryWriteAuthority: safeBoolean(value.grants_memory_write_authority),
    grantsTrainingAuthority: safeBoolean(value.grants_training_authority),
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
  const liveHealthEvidence = isRecord(loop.live_health_evidence) ? loop.live_health_evidence : {};
  const latestLocalModelResponse = isRecord(loop.latest_local_model_response) ? loop.latest_local_model_response : {};
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
      liveHealthEvidence: {
        observed: safeBoolean(liveHealthEvidence.observed),
        proofStatus: safeString(liveHealthEvidence.proof_status, "unknown"),
        healthStatus: safeString(liveHealthEvidence.health_status, "unknown"),
        latestPromptId: safeString(liveHealthEvidence.latest_prompt_id),
        latestReplyId: safeString(liveHealthEvidence.latest_reply_id),
        waitingState: safeString(liveHealthEvidence.waiting_state, "unknown"),
        waitingForOllama: safeBoolean(liveHealthEvidence.waiting_for_ollama),
        turnGapRemainingSeconds: safeNumber(liveHealthEvidence.turn_gap_remaining_seconds),
        latestPromptWithinBudget: safeBoolean(liveHealthEvidence.latest_prompt_within_budget),
        manualNudgeRequired: safeNullableBoolean(liveHealthEvidence.manual_nudge_required),
        enabledParticipantCount: safeNumber(liveHealthEvidence.enabled_participant_count),
        totalParticipantCount: safeNumber(liveHealthEvidence.total_participant_count),
        allParticipantsEnabled: safeBoolean(liveHealthEvidence.all_participants_enabled),
        runningHelperCount: safeNumber(liveHealthEvidence.running_helper_count),
        desiredHelperCount: safeNumber(liveHealthEvidence.desired_helper_count),
        effectiveWorkerCount: safeNumber(liveHealthEvidence.effective_worker_count),
        latestReviewArtifact: safeString(liveHealthEvidence.latest_review_artifact),
        latestLearningArtifact: safeString(liveHealthEvidence.latest_learning_artifact),
        noActionAuthorityReceiptsObserved: safeBoolean(liveHealthEvidence.no_action_authority_receipts_observed),
        evidenceFields: Array.isArray(liveHealthEvidence.evidence_fields)
          ? liveHealthEvidence.evidence_fields.map((field) => safeString(field)).filter(Boolean)
          : [],
        storesFullTranscript: safeBoolean(liveHealthEvidence.stores_full_transcript),
        callsModel: safeBoolean(liveHealthEvidence.calls_model),
        grantsTrainingAuthority: safeBoolean(liveHealthEvidence.grants_training_authority),
        grantsExecutionAuthority: safeBoolean(liveHealthEvidence.grants_execution_authority),
        grantsMutationAuthority: safeBoolean(liveHealthEvidence.grants_mutation_authority),
        grantsApprovalAuthority: safeBoolean(liveHealthEvidence.grants_approval_authority),
        grantsMemoryWriteAuthority: safeBoolean(liveHealthEvidence.grants_memory_write_authority),
        grantsCapabilityAuthority: safeBoolean(liveHealthEvidence.grants_capability_authority),
      },
      latestLocalModelResponse: {
        observed: safeBoolean(latestLocalModelResponse.observed),
        stateObserved: safeBoolean(latestLocalModelResponse.state_observed),
        statePath: safeString(latestLocalModelResponse.state_path),
        source: safeString(latestLocalModelResponse.source),
        createdAt: safeString(latestLocalModelResponse.created_at),
        ageSeconds: safeNullableNumber(latestLocalModelResponse.age_seconds),
        sourcePromptId: safeString(latestLocalModelResponse.source_prompt_id),
        responsePromptId: safeString(latestLocalModelResponse.response_prompt_id),
        status: safeString(latestLocalModelResponse.status, "unknown"),
        outputGuardStatus: safeString(latestLocalModelResponse.output_guard_status, "unknown"),
        modelResponseObserved: safeBoolean(latestLocalModelResponse.model_response_observed),
        isPassed: safeBoolean(latestLocalModelResponse.is_passed),
        isGuardRewrite: safeBoolean(latestLocalModelResponse.is_guard_rewrite),
        storesFullTranscript: safeBoolean(latestLocalModelResponse.stores_full_transcript),
        grantsTrainingAuthority: safeBoolean(latestLocalModelResponse.grants_training_authority),
        grantsExecutionAuthority: safeBoolean(latestLocalModelResponse.grants_execution_authority),
        grantsMutationAuthority: safeBoolean(latestLocalModelResponse.grants_mutation_authority),
        grantsApprovalAuthority: safeBoolean(latestLocalModelResponse.grants_approval_authority),
        grantsMemoryWriteAuthority: safeBoolean(latestLocalModelResponse.grants_memory_write_authority),
        grantsCapabilityAuthority: safeBoolean(latestLocalModelResponse.grants_capability_authority),
        adviceOnlyProof: parseLocalModelAdviceOnlyProof(latestLocalModelResponse.advice_only_proof, {
          modelResponseObserved: safeBoolean(latestLocalModelResponse.model_response_observed),
          sourcePromptId: safeString(latestLocalModelResponse.source_prompt_id),
          responsePromptId: safeString(latestLocalModelResponse.response_prompt_id),
          outputGuardStatus: safeString(latestLocalModelResponse.output_guard_status, "unknown"),
          storesFullTranscript: safeBoolean(latestLocalModelResponse.stores_full_transcript),
          grantsTrainingAuthority: safeBoolean(latestLocalModelResponse.grants_training_authority),
          grantsExecutionAuthority: safeBoolean(latestLocalModelResponse.grants_execution_authority),
          grantsMutationAuthority: safeBoolean(latestLocalModelResponse.grants_mutation_authority),
          grantsApprovalAuthority: safeBoolean(latestLocalModelResponse.grants_approval_authority),
          grantsMemoryWriteAuthority: safeBoolean(latestLocalModelResponse.grants_memory_write_authority),
          grantsCapabilityAuthority: safeBoolean(latestLocalModelResponse.grants_capability_authority),
        }),
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
      latestReviewGate: safeString(definitions.latest_review_gate),
      transcriptDisclosure: safeString(definitions.transcript_disclosure),
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
      implementationPreflight: safeString(definitions.implementation_preflight),
      sourceDisagreementBoundary: safeString(definitions.source_disagreement_boundary),
      participantToggleBoundary: safeString(definitions.participant_toggle_boundary),
      modelAdviceGovernanceBoundary: safeString(definitions.model_advice_governance_boundary),
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
