#pragma once

#include "CoreMinimal.h"
#include "FrancisPresenceTypes.h"
#include "HAL/Runnable.h"

class FRunnableThread;
class FJsonObject;
class FJsonValue;

class FFrancisPresenceBridge final : public FRunnable
{
public:
    FFrancisPresenceBridge();
    virtual ~FFrancisPresenceBridge() override;

    bool Start();
    void Stop();

    virtual uint32 Run() override;
    virtual void Exit() override;

    FFrancisPresenceViewModel GetViewModel() const;
    FFrancisPresenceBridgeReadback GetReadback() const;
    void MarkRendered(const FString& EnvelopeId, int64 Sequence);
    bool QueueIntent(const FString& Kind, const FString& TargetKind = TEXT("none"), const FString& TargetId = TEXT(""));

private:
    bool LoadConfiguration();
    bool ConnectRenderPipe(void*& OutHandle);
    bool ReadFrame(void* Handle, TArray<uint8>& OutJson, FString& OutError) const;
    bool WriteFrame(void* Handle, const TArray<uint8>& Json, FString& OutError) const;
    bool ProcessRenderMessage(const TArray<uint8>& Json, TArray<uint8>& OutAckJson, FString& OutError);
    bool ValidateWireMessage(
        const TArray<uint8>& Json,
        const TSharedPtr<FJsonObject>& Message,
        TArray<uint8>& OutEnvelopeJson,
        FString& OutError
    ) const;
    bool ValidateEnvelope(
        const TArray<uint8>& EnvelopeJson,
        const TSharedPtr<FJsonObject>& Envelope,
        FFrancisPresenceViewModel& OutViewModel,
        bool& bOutDuplicate,
        FString& OutError
    );
    bool BuildSignedAck(
        const TSharedPtr<FJsonObject>& RequestMessage,
        const TSharedPtr<FJsonObject>& Envelope,
        bool bDuplicate,
        TArray<uint8>& OutJson,
        FString& OutError
    ) const;
    bool ProcessPendingIntent();
    bool BuildSignedIntent(const FFrancisPresenceIntentRequest& Request, TArray<uint8>& OutJson, FString& OutEventId);
    bool ConnectIntentPipe(void*& OutHandle) const;
    bool CommitDedup(
        const FString& EnvelopeId,
        const FString& PayloadDigest,
        int64 Sequence,
        int64 IntentSequence,
        FString& OutError
    );
    bool LoadDedup();
    void WriteRuntimeStatus(const FString& Status, const FString& Error = TEXT(""));

    static FString CanonicalJson(const TSharedPtr<FJsonValue>& Value);
    static FString CanonicalObject(const TSharedPtr<FJsonObject>& Object);
    static FString EscapeJsonString(const FString& Value);
    static bool ParseJson(const TArray<uint8>& Json, TSharedPtr<FJsonObject>& OutObject);
    static bool ExtractTopLevelValue(const TArray<uint8>& Json, const ANSICHAR* Key, TArray<uint8>& OutValue);
    static FString Sha256Hex(const TArray<uint8>& Data);
    FString HmacSha256Hex(const TArray<uint8>& Data) const;
    static FString IdFromSeed(const FString& Prefix, const FString& Seed);
    static FString UtcIso(const FDateTime& Value);
    static FString UtcNowIso();
    static bool IsContractId(const FString& Value);
    static bool HasFalseAuthority(const TSharedPtr<FJsonObject>& Authority, bool bRequireAdapterReadOnly);
    static FString StringField(const TSharedPtr<FJsonObject>& Object, const FString& Field, const FString& Fallback = TEXT(""));
    static bool BoolField(const TSharedPtr<FJsonObject>& Object, const FString& Field, bool Fallback = false);
    static int64 IntField(const TSharedPtr<FJsonObject>& Object, const FString& Field, int64 Fallback = 0);
    static TSharedPtr<FJsonObject> ObjectField(const TSharedPtr<FJsonObject>& Object, const FString& Field);

    mutable FCriticalSection StateMutex;
    mutable FCriticalSection IntentMutex;
    TUniquePtr<FRunnableThread> Thread;
    FThreadSafeBool bStopRequested = false;
    FFrancisPresenceViewModel ViewModel;
    FFrancisPresenceBridgeReadback Readback;
    TArray<FFrancisPresenceIntentRequest> PendingIntents;
    TArray<uint8> Secret;
    FString RenderPipePath;
    FString IntentPipePath;
    FString LastEnvelopeId;
    FString LastPayloadDigest;
};
