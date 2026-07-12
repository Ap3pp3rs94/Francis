#pragma once

#include "CoreMinimal.h"

struct FFrancisPresenceViewModel
{
    int64 Revision = 0;
    FString EnvelopeId;
    int64 Sequence = 0;
    FString ReceivedAt;
    FString RenderedAt;
    FString PresenceState = TEXT("unknown");
    FString Headline = TEXT("Waiting for a grounded Francis briefing.");
    FString FocusTitle;
    FString FocusObjective;
    FString NextStep;
    FString StageStatus = TEXT("blocked");
    FString EvidenceStatus = TEXT("missing_evidence");
    FString FreshnessStatus = TEXT("missing_evidence");
    FString VoiceStatus = TEXT("unknown");
    FString VoiceProvider;
    FString SemanticState = TEXT("unknown");
    FString Activity = TEXT("unknown");
    FString IncidentPressure = TEXT("unknown");
    FString HandbackState = TEXT("unknown");
    FString Mode = TEXT("unknown");
    FString IntentAction;
    FString IntentTargetKind = TEXT("none");
    FString IntentTargetId;
    TArray<FString> EvidenceReferences;
    TArray<FString> Limitations;
    bool bTruthful = false;
    bool bReceiptLinked = false;
    bool bApprovalRequired = false;
    bool bRuntimeObserved = false;
    bool bAuthenticated = false;
    bool bRendered = false;
};

struct FFrancisPresenceIntentRequest
{
    FString Kind;
    FString TargetKind = TEXT("none");
    FString TargetId;
};

struct FFrancisPresenceBridgeReadback
{
    FString Status = TEXT("starting");
    FString LastError;
    FString AdapterId;
    FString SessionId;
    FString EndpointId;
    FString KeyId;
    FString StatusPath;
    FString DedupPath;
    FString LastIntentKind;
    FString LastIntentId;
    int64 LastAcceptedSequence = 0;
    int64 LastIntentSequence = 0;
    int64 AcceptedMessageCount = 0;
    int64 RejectedMessageCount = 0;
    int64 DuplicateMessageCount = 0;
    int64 IntentSentCount = 0;
    bool bConfigured = false;
    bool bPipeConnected = false;
    bool bLastIntentWriteSucceeded = false;
};
