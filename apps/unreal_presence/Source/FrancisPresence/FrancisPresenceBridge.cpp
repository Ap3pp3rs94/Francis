#include "FrancisPresenceBridge.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "GenericPlatform/GenericPlatformMisc.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "HAL/RunnableThread.h"
#include "Misc/Base64.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#include "Windows/WindowsHWrapper.h"
#include <bcrypt.h>

namespace
{
constexpr int32 MaxRenderMessageBytes = 256 * 1024;
constexpr int32 MaxIntentMessageBytes = 64 * 1024;
constexpr double PipeReadTimeoutSeconds = 2.0;
constexpr int32 PollSleepMilliseconds = 10;

const TCHAR* RenderChannel = TEXT("francis.presence.render.v1");
const TCHAR* RenderAckChannel = TEXT("francis.presence.render.ack.v1");
const TCHAR* IntentChannel = TEXT("francis.presence.intent.v1");

bool HashSha256(const TArray<uint8>& Data, const TArray<uint8>* Key, TArray<uint8>& OutHash)
{
    BCRYPT_ALG_HANDLE Algorithm = nullptr;
    BCRYPT_HASH_HANDLE Hash = nullptr;
    const ULONG Flags = Key == nullptr ? 0 : BCRYPT_ALG_HANDLE_HMAC_FLAG;
    if (BCryptOpenAlgorithmProvider(&Algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, Flags) < 0)
    {
        return false;
    }

    DWORD ObjectLength = 0;
    DWORD HashLength = 0;
    DWORD ResultLength = 0;
    bool bSucceeded =
        BCryptGetProperty(
            Algorithm,
            BCRYPT_OBJECT_LENGTH,
            reinterpret_cast<PUCHAR>(&ObjectLength),
            sizeof(ObjectLength),
            &ResultLength,
            0
        ) >= 0 &&
        BCryptGetProperty(
            Algorithm,
            BCRYPT_HASH_LENGTH,
            reinterpret_cast<PUCHAR>(&HashLength),
            sizeof(HashLength),
            &ResultLength,
            0
        ) >= 0 &&
        HashLength == 32;

    TArray<uint8> HashObject;
    if (bSucceeded)
    {
        HashObject.SetNumUninitialized(static_cast<int32>(ObjectLength));
        PUCHAR SecretData = Key == nullptr || Key->IsEmpty() ? nullptr : const_cast<PUCHAR>(Key->GetData());
        const ULONG SecretLength = Key == nullptr ? 0 : static_cast<ULONG>(Key->Num());
        bSucceeded = BCryptCreateHash(
            Algorithm,
            &Hash,
            HashObject.GetData(),
            ObjectLength,
            SecretData,
            SecretLength,
            0
        ) >= 0;
    }
    if (bSucceeded && !Data.IsEmpty())
    {
        bSucceeded = BCryptHashData(Hash, const_cast<PUCHAR>(Data.GetData()), static_cast<ULONG>(Data.Num()), 0) >= 0;
    }
    if (bSucceeded)
    {
        OutHash.SetNumUninitialized(static_cast<int32>(HashLength));
        bSucceeded = BCryptFinishHash(Hash, OutHash.GetData(), HashLength, 0) >= 0;
    }

    if (Hash != nullptr)
    {
        BCryptDestroyHash(Hash);
    }
    BCryptCloseAlgorithmProvider(Algorithm, 0);
    if (!bSucceeded)
    {
        OutHash.Reset();
    }
    return bSucceeded;
}

int32 SkipJsonString(const TArray<uint8>& Json, int32 Index)
{
    if (!Json.IsValidIndex(Index) || Json[Index] != '"')
    {
        return INDEX_NONE;
    }
    ++Index;
    while (Json.IsValidIndex(Index))
    {
        if (Json[Index] == '\\')
        {
            Index += 2;
            continue;
        }
        if (Json[Index] == '"')
        {
            return Index + 1;
        }
        ++Index;
    }
    return INDEX_NONE;
}

int32 SkipJsonValue(const TArray<uint8>& Json, int32 Index)
{
    while (Json.IsValidIndex(Index) && FCharAnsi::IsWhitespace(static_cast<ANSICHAR>(Json[Index])))
    {
        ++Index;
    }
    if (!Json.IsValidIndex(Index))
    {
        return INDEX_NONE;
    }
    if (Json[Index] == '"')
    {
        return SkipJsonString(Json, Index);
    }
    if (Json[Index] == '{' || Json[Index] == '[')
    {
        const uint8 Opening = Json[Index];
        const uint8 Closing = Opening == '{' ? '}' : ']';
        int32 Depth = 0;
        while (Json.IsValidIndex(Index))
        {
            if (Json[Index] == '"')
            {
                Index = SkipJsonString(Json, Index);
                if (Index == INDEX_NONE)
                {
                    return INDEX_NONE;
                }
                continue;
            }
            if (Json[Index] == Opening)
            {
                ++Depth;
            }
            else if (Json[Index] == Closing)
            {
                --Depth;
                if (Depth == 0)
                {
                    return Index + 1;
                }
            }
            ++Index;
        }
        return INDEX_NONE;
    }
    while (Json.IsValidIndex(Index) && Json[Index] != ',' && Json[Index] != '}' && Json[Index] != ']')
    {
        ++Index;
    }
    return Index;
}

TSharedPtr<FJsonObject> MakeAuthority(bool bIncludeAdapterReadOnly = false)
{
    TSharedPtr<FJsonObject> Authority = MakeShared<FJsonObject>();
    Authority->SetBoolField(TEXT("francis_core_authoritative"), true);
    if (bIncludeAdapterReadOnly)
    {
        Authority->SetBoolField(TEXT("adapter_read_only"), true);
    }
    Authority->SetBoolField(TEXT("grants_execution_authority"), false);
    Authority->SetBoolField(TEXT("grants_desktop_authority"), false);
    Authority->SetBoolField(TEXT("grants_network_authority"), false);
    Authority->SetBoolField(TEXT("grants_memory_write_authority"), false);
    Authority->SetBoolField(TEXT("grants_approval_authority"), false);
    return Authority;
}

TSharedPtr<FJsonValue> JsonObjectValue(const TSharedPtr<FJsonObject>& Object)
{
    return MakeShared<FJsonValueObject>(Object);
}

TArray<TSharedPtr<FJsonValue>> StringArray(const TArray<FString>& Values)
{
    TArray<TSharedPtr<FJsonValue>> Result;
    Result.Reserve(Values.Num());
    for (const FString& Value : Values)
    {
        Result.Add(MakeShared<FJsonValueString>(Value));
    }
    return Result;
}
}

FFrancisPresenceBridge::FFrancisPresenceBridge() = default;

FFrancisPresenceBridge::~FFrancisPresenceBridge()
{
    Stop();
}

bool FFrancisPresenceBridge::Start()
{
    if (Thread)
    {
        return true;
    }
    const bool bConfigured = LoadConfiguration();
    WriteRuntimeStatus(bConfigured ? TEXT("waiting_for_core") : TEXT("configuration_required"), Readback.LastError);
    Thread.Reset(FRunnableThread::Create(this, TEXT("FrancisPresenceBridge"), 0, TPri_Normal));
    return Thread.IsValid();
}

void FFrancisPresenceBridge::Stop()
{
    bStopRequested = true;
    if (Thread)
    {
        Thread->WaitForCompletion();
        Thread.Reset();
    }
}

uint32 FFrancisPresenceBridge::Run()
{
    if (!Readback.bConfigured)
    {
        while (!bStopRequested)
        {
            FPlatformProcess::SleepNoStats(0.1f);
        }
        return 0;
    }

    WriteRuntimeStatus(TEXT("waiting_for_core"));
    while (!bStopRequested)
    {
        ProcessPendingIntent();

        void* HandleValue = nullptr;
        if (!ConnectRenderPipe(HandleValue))
        {
            FPlatformProcess::SleepNoStats(PollSleepMilliseconds / 1000.0f);
            continue;
        }

        HANDLE Handle = static_cast<HANDLE>(HandleValue);
        {
            FScopeLock Lock(&StateMutex);
            Readback.bPipeConnected = true;
            Readback.Status = TEXT("core_connected");
            Readback.LastError.Reset();
        }
        WriteRuntimeStatus(TEXT("core_connected"));

        TArray<uint8> RequestJson;
        FString Error;
        if (ReadFrame(Handle, RequestJson, Error))
        {
            TArray<uint8> AckJson;
            if (ProcessRenderMessage(RequestJson, AckJson, Error))
            {
                if (!WriteFrame(Handle, AckJson, Error))
                {
                    UE_LOG(LogTemp, Error, TEXT("FrancisPresence ACK write failed: %s"), *Error);
                }
                else
                {
                    FPlatformProcess::SleepNoStats(0.02f);
                }
            }
        }

        CloseHandle(Handle);
        {
            FScopeLock Lock(&StateMutex);
            Readback.bPipeConnected = false;
            if (!Error.IsEmpty())
            {
                Readback.LastError = Error;
            }
        }
        WriteRuntimeStatus(Error.IsEmpty() ? TEXT("waiting_for_core") : TEXT("transport_error"), Error);
    }

    WriteRuntimeStatus(TEXT("stopped"));
    return 0;
}

void FFrancisPresenceBridge::Exit()
{
}

FFrancisPresenceViewModel FFrancisPresenceBridge::GetViewModel() const
{
    FScopeLock Lock(&StateMutex);
    return ViewModel;
}

FFrancisPresenceBridgeReadback FFrancisPresenceBridge::GetReadback() const
{
    FScopeLock Lock(&StateMutex);
    return Readback;
}

void FFrancisPresenceBridge::MarkRendered(const FString& EnvelopeId, int64 Sequence)
{
    bool bUpdated = false;
    {
        FScopeLock Lock(&StateMutex);
        if (ViewModel.EnvelopeId == EnvelopeId && ViewModel.Sequence == Sequence)
        {
            ViewModel.bRendered = true;
            ViewModel.bRuntimeObserved = true;
            ViewModel.RenderedAt = UtcNowIso();
            Readback.Status = TEXT("render_applied");
            bUpdated = true;
        }
    }
    if (bUpdated)
    {
        WriteRuntimeStatus(TEXT("render_applied"));
    }
}

bool FFrancisPresenceBridge::QueueIntent(const FString& Kind, const FString& TargetKind, const FString& TargetId)
{
    static const TSet<FString> AllowedKinds = {
        TEXT("request_context_refresh"),
        TEXT("acknowledge_handback"),
        TEXT("request_review"),
        TEXT("request_panic_stop")
    };
    static const TSet<FString> AllowedTargets = {
        TEXT("none"), TEXT("mission"), TEXT("operation"), TEXT("receipt"), TEXT("surface")
    };
    if (!AllowedKinds.Contains(Kind) || !AllowedTargets.Contains(TargetKind))
    {
        return false;
    }
    if ((TargetKind == TEXT("none")) != TargetId.IsEmpty() || (!TargetId.IsEmpty() && !IsContractId(TargetId)))
    {
        return false;
    }
    FScopeLock Lock(&IntentMutex);
    if (PendingIntents.Num() >= 16)
    {
        return false;
    }
    PendingIntents.Add({Kind, TargetKind, TargetId});
    return true;
}

bool FFrancisPresenceBridge::LoadConfiguration()
{
    const auto Env = [](const TCHAR* Name) { return FPlatformMisc::GetEnvironmentVariable(Name).TrimStartAndEnd(); };
    Readback.AdapterId = Env(TEXT("FRANCIS_UNREAL_PRESENCE_ADAPTER_ID"));
    Readback.SessionId = Env(TEXT("FRANCIS_UNREAL_PRESENCE_SESSION_ID"));
    Readback.KeyId = Env(TEXT("FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID"));
    const FString EncodedSecret = Env(TEXT("FRANCIS_UNREAL_PRESENCE_IPC_KEY_B64"));
    Readback.AdapterId = Readback.AdapterId.IsEmpty() ? TEXT("unreal_presence_1") : Readback.AdapterId;
    Readback.SessionId = Readback.SessionId.IsEmpty() ? TEXT("francis_unreal_stage1_v1") : Readback.SessionId;
    Readback.EndpointId = FString::Printf(TEXT("francis.grounded_presence.%s"), *Readback.AdapterId);
    RenderPipePath = FString::Printf(TEXT("\\\\.\\pipe\\%s"), *Readback.EndpointId);
    IntentPipePath = FString::Printf(TEXT("\\\\.\\pipe\\francis.grounded_presence.intent.%s"), *Readback.AdapterId);

    Readback.StatusPath = Env(TEXT("FRANCIS_UNREAL_PRESENCE_STATUS_PATH"));
    if (Readback.StatusPath.IsEmpty())
    {
        Readback.StatusPath = FPaths::ConvertRelativePathToFull(
            FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("FrancisPresence"), TEXT("runtime_status.json"))
        );
    }
    Readback.DedupPath = Env(TEXT("FRANCIS_UNREAL_PRESENCE_DEDUP_PATH"));
    if (Readback.DedupPath.IsEmpty())
    {
        Readback.DedupPath = FPaths::ConvertRelativePathToFull(
            FPaths::Combine(
                FPaths::ProjectSavedDir(),
                TEXT("FrancisPresence"),
                TEXT("dedup"),
                Readback.SessionId + TEXT(".json")
            )
        );
    }
    if (!IsContractId(Readback.AdapterId) || !IsContractId(Readback.SessionId) || !IsContractId(Readback.KeyId))
    {
        Readback.Status = TEXT("configuration_required");
        Readback.LastError = TEXT("identity_or_key_id_invalid");
        return false;
    }
    if (!FBase64::Decode(EncodedSecret, Secret) || Secret.Num() < 32 || Secret.Num() > 128)
    {
        Secret.Reset();
        Readback.Status = TEXT("configuration_required");
        Readback.LastError = TEXT("ipc_secret_missing_or_invalid");
        return false;
    }
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Readback.StatusPath), true);
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Readback.DedupPath), true);
    if (!LoadDedup())
    {
        Readback.Status = TEXT("configuration_required");
        return false;
    }
    Readback.bConfigured = true;
    Readback.Status = TEXT("waiting_for_core");
    Readback.LastError.Reset();
    return true;
}

bool FFrancisPresenceBridge::ConnectRenderPipe(void*& OutHandle)
{
    OutHandle = nullptr;
    if (!WaitNamedPipeW(*RenderPipePath, 20))
    {
        return false;
    }
    HANDLE Handle = CreateFileW(
        *RenderPipePath,
        GENERIC_READ | GENERIC_WRITE,
        0,
        nullptr,
        OPEN_EXISTING,
        0,
        nullptr
    );
    if (Handle == INVALID_HANDLE_VALUE)
    {
        return false;
    }
    DWORD Mode = PIPE_READMODE_MESSAGE;
    if (!SetNamedPipeHandleState(Handle, &Mode, nullptr, nullptr))
    {
        CloseHandle(Handle);
        return false;
    }
    OutHandle = Handle;
    return true;
}

bool FFrancisPresenceBridge::ReadFrame(void* HandleValue, TArray<uint8>& OutJson, FString& OutError) const
{
    HANDLE Handle = static_cast<HANDLE>(HandleValue);
    const double Deadline = FPlatformTime::Seconds() + PipeReadTimeoutSeconds;
    DWORD Available = 0;
    while (!bStopRequested && FPlatformTime::Seconds() < Deadline)
    {
        if (PeekNamedPipe(Handle, nullptr, 0, nullptr, &Available, nullptr) && Available > 0)
        {
            break;
        }
        FPlatformProcess::SleepNoStats(PollSleepMilliseconds / 1000.0f);
    }
    if (Available < 5 || Available > static_cast<DWORD>(MaxRenderMessageBytes + 4))
    {
        OutError = Available == 0 ? TEXT("render_frame_timeout") : TEXT("render_frame_size_invalid");
        return false;
    }
    TArray<uint8> Frame;
    Frame.SetNumUninitialized(Available);
    DWORD BytesRead = 0;
    if (!ReadFile(Handle, Frame.GetData(), Available, &BytesRead, nullptr) || BytesRead != Available)
    {
        OutError = FString::Printf(TEXT("render_frame_read_failed_%lu"), GetLastError());
        return false;
    }
    const uint32 PayloadSize = static_cast<uint32>(Frame[0]) |
        (static_cast<uint32>(Frame[1]) << 8) |
        (static_cast<uint32>(Frame[2]) << 16) |
        (static_cast<uint32>(Frame[3]) << 24);
    if (PayloadSize != BytesRead - 4 || PayloadSize == 0 || PayloadSize > MaxRenderMessageBytes)
    {
        OutError = TEXT("render_frame_prefix_invalid");
        return false;
    }
    OutJson.Append(Frame.GetData() + 4, PayloadSize);
    return true;
}

bool FFrancisPresenceBridge::WriteFrame(void* HandleValue, const TArray<uint8>& Json, FString& OutError) const
{
    if (Json.Num() <= 0 || Json.Num() > MaxRenderMessageBytes)
    {
        OutError = TEXT("ack_frame_size_invalid");
        return false;
    }
    TArray<uint8> Frame;
    Frame.Reserve(Json.Num() + 4);
    const uint32 Size = Json.Num();
    Frame.Add(static_cast<uint8>(Size & 0xff));
    Frame.Add(static_cast<uint8>((Size >> 8) & 0xff));
    Frame.Add(static_cast<uint8>((Size >> 16) & 0xff));
    Frame.Add(static_cast<uint8>((Size >> 24) & 0xff));
    Frame.Append(Json);
    DWORD BytesWritten = 0;
    HANDLE Handle = static_cast<HANDLE>(HandleValue);
    if (!WriteFile(Handle, Frame.GetData(), Frame.Num(), &BytesWritten, nullptr) || BytesWritten != Frame.Num())
    {
        OutError = FString::Printf(TEXT("pipe_write_failed_%lu"), GetLastError());
        return false;
    }
    if (!FlushFileBuffers(Handle))
    {
        OutError = FString::Printf(TEXT("pipe_flush_failed_%lu"), GetLastError());
        return false;
    }
    return true;
}

bool FFrancisPresenceBridge::ProcessRenderMessage(
    const TArray<uint8>& Json,
    TArray<uint8>& OutAckJson,
    FString& OutError
)
{
    TSharedPtr<FJsonObject> Message;
    if (!ParseJson(Json, Message))
    {
        OutError = TEXT("wire_json_invalid");
        FScopeLock Lock(&StateMutex);
        ++Readback.RejectedMessageCount;
        return false;
    }
    TArray<uint8> EnvelopeJson;
    if (!ValidateWireMessage(Json, Message, EnvelopeJson, OutError))
    {
        FScopeLock Lock(&StateMutex);
        ++Readback.RejectedMessageCount;
        return false;
    }
    TSharedPtr<FJsonObject> Envelope;
    if (!ParseJson(EnvelopeJson, Envelope))
    {
        OutError = TEXT("transport_envelope_json_invalid");
        FScopeLock Lock(&StateMutex);
        ++Readback.RejectedMessageCount;
        return false;
    }

    FFrancisPresenceViewModel Candidate;
    bool bDuplicate = false;
    if (!ValidateEnvelope(EnvelopeJson, Envelope, Candidate, bDuplicate, OutError))
    {
        FScopeLock Lock(&StateMutex);
        ++Readback.RejectedMessageCount;
        return false;
    }
    if (!BuildSignedAck(Message, Envelope, bDuplicate, OutAckJson, OutError))
    {
        FScopeLock Lock(&StateMutex);
        ++Readback.RejectedMessageCount;
        return false;
    }

    {
        FScopeLock Lock(&StateMutex);
        Candidate.Revision = ViewModel.Revision + 1;
        ViewModel = MoveTemp(Candidate);
        Readback.Status = bDuplicate ? TEXT("duplicate_acknowledged") : TEXT("snapshot_accepted");
        ++Readback.AcceptedMessageCount;
        if (bDuplicate)
        {
            ++Readback.DuplicateMessageCount;
        }
    }
    WriteRuntimeStatus(bDuplicate ? TEXT("duplicate_acknowledged") : TEXT("snapshot_accepted"));
    return true;
}

bool FFrancisPresenceBridge::ValidateWireMessage(
    const TArray<uint8>& Json,
    const TSharedPtr<FJsonObject>& Message,
    TArray<uint8>& OutEnvelopeJson,
    FString& OutError
) const
{
    if (StringField(Message, TEXT("kind")) != TEXT("francis.grounded_presence.ipc_message") ||
        StringField(Message, TEXT("schema_version")) != TEXT("francis.grounded_presence.ipc_message.v1") ||
        StringField(Message, TEXT("channel")) != RenderChannel ||
        StringField(Message, TEXT("direction")) != TEXT("francis_core_to_unreal"))
    {
        OutError = TEXT("wire_contract_invalid");
        return false;
    }
    const TSharedPtr<FJsonObject> Authentication = ObjectField(Message, TEXT("authentication"));
    const TSharedPtr<FJsonObject> Integrity = ObjectField(Message, TEXT("integrity"));
    if (StringField(Authentication, TEXT("algorithm")) != TEXT("hmac-sha256") ||
        StringField(Authentication, TEXT("key_id")) != Readback.KeyId ||
        StringField(Integrity, TEXT("algorithm")) != TEXT("sha256") ||
        StringField(Integrity, TEXT("canonicalization")) != TEXT("json_sort_keys_compact_utf8") ||
        !HasFalseAuthority(ObjectField(Message, TEXT("authority")), false))
    {
        OutError = TEXT("wire_security_contract_invalid");
        return false;
    }

    const FString Signature = StringField(Authentication, TEXT("signature")).ToLower();
    if (Signature.Len() != 64)
    {
        OutError = TEXT("wire_signature_invalid");
        return false;
    }
    FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(Json.GetData()), Json.Num());
    FString Canonical(Converter.Length(), Converter.Get());
    const FString SignatureToken = FString::Printf(TEXT("\"signature\":\"%s\""), *Signature);
    const int32 SignatureIndex = Canonical.Find(SignatureToken, ESearchCase::CaseSensitive);
    if (SignatureIndex == INDEX_NONE)
    {
        OutError = TEXT("wire_signature_token_missing");
        return false;
    }
    Canonical.RemoveAt(SignatureIndex + 13, Signature.Len());
    FTCHARToUTF8 CanonicalUtf8(*Canonical);
    TArray<uint8> CanonicalBytes;
    CanonicalBytes.Append(reinterpret_cast<const uint8*>(CanonicalUtf8.Get()), CanonicalUtf8.Length());
    if (!Signature.Equals(HmacSha256Hex(CanonicalBytes), ESearchCase::IgnoreCase))
    {
        OutError = TEXT("wire_signature_mismatch");
        return false;
    }
    if (!ExtractTopLevelValue(Json, "payload", OutEnvelopeJson))
    {
        OutError = TEXT("wire_payload_missing");
        return false;
    }
    if (!StringField(Integrity, TEXT("payload_digest")).Equals(Sha256Hex(OutEnvelopeJson), ESearchCase::IgnoreCase))
    {
        OutError = TEXT("wire_payload_digest_mismatch");
        return false;
    }
    FDateTime ExpiresAt;
    if (!FDateTime::ParseIso8601(*StringField(Message, TEXT("expires_at")), ExpiresAt) || FDateTime::UtcNow() >= ExpiresAt)
    {
        OutError = TEXT("wire_message_expired");
        return false;
    }
    return true;
}

bool FFrancisPresenceBridge::ValidateEnvelope(
    const TArray<uint8>& EnvelopeJson,
    const TSharedPtr<FJsonObject>& Envelope,
    FFrancisPresenceViewModel& OutViewModel,
    bool& bOutDuplicate,
    FString& OutError
)
{
    const TSharedPtr<FJsonObject> Adapter = ObjectField(Envelope, TEXT("adapter"));
    const TSharedPtr<FJsonObject> Transport = ObjectField(Envelope, TEXT("transport"));
    const TSharedPtr<FJsonObject> Integrity = ObjectField(Envelope, TEXT("integrity"));
    const TSharedPtr<FJsonObject> Authority = ObjectField(Envelope, TEXT("authority"));
    if (StringField(Envelope, TEXT("kind")) != TEXT("francis.grounded_presence.transport_envelope") ||
        StringField(Envelope, TEXT("schema_version")) != TEXT("francis.grounded_presence.transport_envelope.v1") ||
        StringField(Envelope, TEXT("channel")) != RenderChannel ||
        StringField(Envelope, TEXT("direction")) != TEXT("francis_core_to_unreal") ||
        StringField(Adapter, TEXT("id")) != Readback.AdapterId ||
        StringField(Adapter, TEXT("session_id")) != Readback.SessionId ||
        StringField(Adapter, TEXT("kind")) != TEXT("unreal") ||
        StringField(Adapter, TEXT("role")) != TEXT("governed_renderer_adapter") ||
        StringField(Adapter, TEXT("engine_version")) != TEXT("5.8") ||
        StringField(Transport, TEXT("binding_status")) != TEXT("windows_named_pipe") ||
        StringField(Transport, TEXT("endpoint_id")) != Readback.EndpointId ||
        !BoolField(Transport, TEXT("local_only")) || BoolField(Transport, TEXT("network_allowed"), true) ||
        !HasFalseAuthority(Authority, true))
    {
        OutError = TEXT("transport_contract_invalid");
        return false;
    }

    const FString EnvelopeId = StringField(Envelope, TEXT("envelope_id"));
    const int64 Sequence = IntField(Envelope, TEXT("sequence"));
    const FString PayloadDigest = StringField(Integrity, TEXT("payload_digest")).ToLower();
    if (!EnvelopeId.StartsWith(TEXT("gpe_")) || Sequence <= 0 || PayloadDigest.Len() != 64)
    {
        OutError = TEXT("transport_identity_invalid");
        return false;
    }
    FDateTime ExpiresAt;
    if (!FDateTime::ParseIso8601(*StringField(Envelope, TEXT("expires_at")), ExpiresAt) || FDateTime::UtcNow() >= ExpiresAt)
    {
        OutError = TEXT("transport_envelope_expired");
        return false;
    }
    TArray<uint8> SnapshotJson;
    if (!ExtractTopLevelValue(EnvelopeJson, "payload", SnapshotJson) ||
        !PayloadDigest.Equals(Sha256Hex(SnapshotJson), ESearchCase::IgnoreCase))
    {
        OutError = TEXT("transport_payload_digest_mismatch");
        return false;
    }

    {
        FScopeLock Lock(&StateMutex);
        if (Sequence < Readback.LastAcceptedSequence)
        {
            OutError = TEXT("transport_sequence_replayed");
            return false;
        }
        if (Sequence == Readback.LastAcceptedSequence)
        {
            if (EnvelopeId != LastEnvelopeId || PayloadDigest != LastPayloadDigest)
            {
                OutError = TEXT("transport_sequence_collision");
                return false;
            }
            bOutDuplicate = true;
        }
    }

    const TSharedPtr<FJsonObject> Snapshot = ObjectField(Envelope, TEXT("payload"));
    if (StringField(Snapshot, TEXT("kind")) != TEXT("francis.grounded_presence.snapshot") ||
        StringField(Snapshot, TEXT("schema_version")) != TEXT("francis.grounded_presence.snapshot.v1") ||
        !HasFalseAuthority(ObjectField(Snapshot, TEXT("authority")), false))
    {
        OutError = TEXT("presence_snapshot_contract_invalid");
        return false;
    }
    const TSharedPtr<FJsonObject> Stage = ObjectField(Snapshot, TEXT("stage"));
    const TSharedPtr<FJsonObject> Presence = ObjectField(Snapshot, TEXT("presence"));
    const TSharedPtr<FJsonObject> Focus = ObjectField(Presence, TEXT("focus"));
    const TSharedPtr<FJsonObject> ReturnContext = ObjectField(Presence, TEXT("return_to_context"));
    const TSharedPtr<FJsonObject> Evidence = ObjectField(Snapshot, TEXT("evidence"));
    const TSharedPtr<FJsonObject> Freshness = ObjectField(Snapshot, TEXT("freshness"));
    const TSharedPtr<FJsonObject> Voice = ObjectField(Snapshot, TEXT("voice"));
    const TSharedPtr<FJsonObject> Visual = ObjectField(Snapshot, TEXT("visual_state"));
    const TSharedPtr<FJsonObject> Intent = ObjectField(Snapshot, TEXT("intent"));

    OutViewModel.EnvelopeId = EnvelopeId;
    OutViewModel.Sequence = Sequence;
    OutViewModel.ReceivedAt = UtcNowIso();
    OutViewModel.PresenceState = StringField(Presence, TEXT("state"), TEXT("unknown"));
    OutViewModel.Headline = StringField(Presence, TEXT("headline"), TEXT("No grounded briefing observed."));
    OutViewModel.FocusTitle = StringField(Focus, TEXT("title"));
    OutViewModel.FocusObjective = StringField(Focus, TEXT("objective"));
    OutViewModel.NextStep = StringField(ReturnContext, TEXT("next_step"));
    OutViewModel.StageStatus = StringField(Stage, TEXT("status"), TEXT("blocked"));
    OutViewModel.EvidenceStatus = StringField(Evidence, TEXT("status"), TEXT("missing_evidence"));
    OutViewModel.FreshnessStatus = StringField(Freshness, TEXT("status"), TEXT("missing_evidence"));
    OutViewModel.VoiceStatus = StringField(Voice, TEXT("status"), TEXT("unknown"));
    OutViewModel.VoiceProvider = StringField(Voice, TEXT("provider"));
    OutViewModel.SemanticState = StringField(Visual, TEXT("semantic_state"), TEXT("unknown"));
    OutViewModel.Activity = StringField(Visual, TEXT("activity"), TEXT("unknown"));
    OutViewModel.IncidentPressure = StringField(Visual, TEXT("incident_pressure"), TEXT("unknown"));
    OutViewModel.HandbackState = StringField(Visual, TEXT("handback_state"), TEXT("unknown"));
    OutViewModel.Mode = StringField(Visual, TEXT("mode"), TEXT("unknown"));
    OutViewModel.IntentAction = StringField(Intent, TEXT("action"));
    OutViewModel.IntentTargetKind = StringField(Intent, TEXT("target_kind"), TEXT("none"));
    OutViewModel.IntentTargetId = StringField(Intent, TEXT("target_id"));
    OutViewModel.bTruthful = BoolField(Presence, TEXT("truthful"));
    OutViewModel.bReceiptLinked = BoolField(Evidence, TEXT("receipt_linkage_ready"));
    OutViewModel.bApprovalRequired = BoolField(Visual, TEXT("approval_required"));
    OutViewModel.bAuthenticated = true;

    const TArray<TSharedPtr<FJsonValue>>* References = nullptr;
    if (Evidence.IsValid() && Evidence->TryGetArrayField(TEXT("references"), References) && References)
    {
        for (const TSharedPtr<FJsonValue>& Value : *References)
        {
            const TSharedPtr<FJsonObject> Reference = Value.IsValid() ? Value->AsObject() : nullptr;
            const FString Id = StringField(Reference, TEXT("id"));
            if (!Id.IsEmpty())
            {
                OutViewModel.EvidenceReferences.Add(Id);
            }
        }
    }
    const TArray<TSharedPtr<FJsonValue>>* Limitations = nullptr;
    if (Snapshot->TryGetArrayField(TEXT("limitations"), Limitations) && Limitations)
    {
        for (const TSharedPtr<FJsonValue>& Value : *Limitations)
        {
            FString Limitation;
            if (Value.IsValid() && Value->TryGetString(Limitation))
            {
                OutViewModel.Limitations.Add(Limitation);
            }
        }
    }

    if (!bOutDuplicate)
    {
        FString CommitError;
        if (!CommitDedup(EnvelopeId, PayloadDigest, Sequence, Readback.LastIntentSequence, CommitError))
        {
            OutError = CommitError;
            return false;
        }
    }
    return true;
}

bool FFrancisPresenceBridge::BuildSignedAck(
    const TSharedPtr<FJsonObject>& RequestMessage,
    const TSharedPtr<FJsonObject>& Envelope,
    bool bDuplicate,
    TArray<uint8>& OutJson,
    FString& OutError
) const
{
    const TSharedPtr<FJsonObject> Adapter = ObjectField(Envelope, TEXT("adapter"));
    const TSharedPtr<FJsonObject> Integrity = ObjectField(Envelope, TEXT("integrity"));
    const FString ConsumerStatus = bDuplicate ? TEXT("duplicate_already_accepted") : TEXT("accepted_for_render");
    const FString MessageId = StringField(RequestMessage, TEXT("message_id"));
    const FString EnvelopeId = StringField(Envelope, TEXT("envelope_id"));
    const FString AckSeed = FString::Join(
        TArray<FString>{MessageId, EnvelopeId, Readback.EndpointId, ConsumerStatus},
        TEXT("|")
    );

    TSharedPtr<FJsonObject> AckRequest = MakeShared<FJsonObject>();
    AckRequest->SetStringField(TEXT("message_id"), MessageId);
    AckRequest->SetStringField(TEXT("envelope_id"), EnvelopeId);
    AckRequest->SetStringField(TEXT("adapter_id"), StringField(Adapter, TEXT("id")));
    AckRequest->SetStringField(TEXT("session_id"), StringField(Adapter, TEXT("session_id")));
    AckRequest->SetNumberField(TEXT("sequence"), IntField(Envelope, TEXT("sequence")));
    AckRequest->SetStringField(TEXT("endpoint_id"), Readback.EndpointId);
    AckRequest->SetStringField(TEXT("payload_digest"), StringField(Integrity, TEXT("payload_digest")));

    TSharedPtr<FJsonObject> Consumer = MakeShared<FJsonObject>();
    Consumer->SetStringField(TEXT("status"), ConsumerStatus);
    Consumer->SetBoolField(TEXT("durable_deduplication"), true);
    Consumer->SetBoolField(TEXT("sequence_committed"), true);
    Consumer->SetStringField(TEXT("render_application_status"), TEXT("queued_not_proven"));
    Consumer->SetBoolField(TEXT("payload_persisted"), false);

    TSharedPtr<FJsonObject> Ack = MakeShared<FJsonObject>();
    Ack->SetStringField(TEXT("kind"), TEXT("francis.grounded_presence.delivery_ack"));
    Ack->SetStringField(TEXT("schema_version"), TEXT("francis.grounded_presence.delivery_ack.v1"));
    Ack->SetStringField(TEXT("schema_path"), TEXT("schemas/grounded_presence_delivery_ack.schema.json"));
    Ack->SetStringField(TEXT("ack_id"), IdFromSeed(TEXT("gpa_"), AckSeed));
    Ack->SetStringField(TEXT("acknowledged_at"), UtcNowIso());
    Ack->SetObjectField(TEXT("request"), AckRequest);
    Ack->SetObjectField(TEXT("consumer"), Consumer);
    Ack->SetObjectField(TEXT("authority"), MakeAuthority());

    const FString IssuedAt = UtcNowIso();
    FDateTime IssuedDate;
    if (!FDateTime::ParseIso8601(*IssuedAt, IssuedDate))
    {
        OutError = TEXT("ack_timestamp_generation_failed");
        return false;
    }
    const FString ExpiresAt = UtcIso(IssuedDate + FTimespan::FromSeconds(1));
    const FString Nonce = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
    const FString AckCanonical = CanonicalObject(Ack);
    FTCHARToUTF8 AckUtf8(*AckCanonical);
    TArray<uint8> AckBytes;
    AckBytes.Append(reinterpret_cast<const uint8*>(AckUtf8.Get()), AckUtf8.Length());
    const FString PayloadDigest = Sha256Hex(AckBytes);
    const FString MessageSeed = FString::Join(
        TArray<FString>{
            Readback.KeyId,
            RenderAckChannel,
            TEXT("unreal_to_francis_core"),
            Nonce,
            IssuedAt,
            PayloadDigest
        },
        TEXT("|")
    );

    TSharedPtr<FJsonObject> WireIntegrity = MakeShared<FJsonObject>();
    WireIntegrity->SetStringField(TEXT("algorithm"), TEXT("sha256"));
    WireIntegrity->SetStringField(TEXT("canonicalization"), TEXT("json_sort_keys_compact_utf8"));
    WireIntegrity->SetStringField(TEXT("payload_digest"), PayloadDigest);
    TSharedPtr<FJsonObject> Authentication = MakeShared<FJsonObject>();
    Authentication->SetStringField(TEXT("algorithm"), TEXT("hmac-sha256"));
    Authentication->SetStringField(TEXT("key_id"), Readback.KeyId);
    Authentication->SetStringField(TEXT("signature"), TEXT(""));

    TSharedPtr<FJsonObject> Wire = MakeShared<FJsonObject>();
    Wire->SetStringField(TEXT("kind"), TEXT("francis.grounded_presence.ipc_message"));
    Wire->SetStringField(TEXT("schema_version"), TEXT("francis.grounded_presence.ipc_message.v1"));
    Wire->SetStringField(TEXT("schema_path"), TEXT("schemas/grounded_presence_ipc_message.schema.json"));
    Wire->SetStringField(TEXT("message_id"), IdFromSeed(TEXT("gpm_"), MessageSeed));
    Wire->SetStringField(TEXT("channel"), RenderAckChannel);
    Wire->SetStringField(TEXT("direction"), TEXT("unreal_to_francis_core"));
    Wire->SetStringField(TEXT("issued_at"), IssuedAt);
    Wire->SetStringField(TEXT("expires_at"), ExpiresAt);
    Wire->SetNumberField(TEXT("ttl_ms"), 1000);
    Wire->SetStringField(TEXT("nonce"), Nonce);
    Wire->SetObjectField(TEXT("integrity"), WireIntegrity);
    Wire->SetObjectField(TEXT("authentication"), Authentication);
    Wire->SetObjectField(TEXT("payload"), Ack);
    Wire->SetObjectField(TEXT("authority"), MakeAuthority());

    const FString UnsignedCanonical = CanonicalObject(Wire);
    FTCHARToUTF8 UnsignedUtf8(*UnsignedCanonical);
    TArray<uint8> UnsignedBytes;
    UnsignedBytes.Append(reinterpret_cast<const uint8*>(UnsignedUtf8.Get()), UnsignedUtf8.Length());
    Authentication->SetStringField(TEXT("signature"), HmacSha256Hex(UnsignedBytes));
    const FString SignedCanonical = CanonicalObject(Wire);
    FTCHARToUTF8 SignedUtf8(*SignedCanonical);
    OutJson.Append(reinterpret_cast<const uint8*>(SignedUtf8.Get()), SignedUtf8.Length());
    return true;
}

bool FFrancisPresenceBridge::ProcessPendingIntent()
{
    FFrancisPresenceIntentRequest Request;
    {
        FScopeLock Lock(&IntentMutex);
        if (PendingIntents.IsEmpty())
        {
            return false;
        }
        Request = PendingIntents[0];
    }
    void* HandleValue = nullptr;
    if (!ConnectIntentPipe(HandleValue))
    {
        return false;
    }
    TArray<uint8> Json;
    FString EventId;
    FString Error;
    const bool bBuilt = BuildSignedIntent(Request, Json, EventId);
    const bool bWritten = bBuilt && WriteFrame(HandleValue, Json, Error);
    CloseHandle(static_cast<HANDLE>(HandleValue));
    {
        FScopeLock Lock(&IntentMutex);
        if (!PendingIntents.IsEmpty())
        {
            PendingIntents.RemoveAt(0);
        }
    }
    {
        FScopeLock Lock(&StateMutex);
        Readback.LastIntentKind = Request.Kind;
        Readback.LastIntentId = EventId;
        Readback.bLastIntentWriteSucceeded = bWritten;
        Readback.LastError = Error;
        if (bWritten)
        {
            ++Readback.IntentSentCount;
        }
    }
    WriteRuntimeStatus(bWritten ? TEXT("intent_sent") : TEXT("intent_send_failed"), Error);
    return bWritten;
}

bool FFrancisPresenceBridge::BuildSignedIntent(
    const FFrancisPresenceIntentRequest& Request,
    TArray<uint8>& OutJson,
    FString& OutEventId
)
{
    static const TMap<FString, FString> IntentClasses = {
        {TEXT("request_context_refresh"), TEXT("read_request")},
        {TEXT("acknowledge_handback"), TEXT("acknowledgement_request")},
        {TEXT("request_review"), TEXT("governed_action_request")},
        {TEXT("request_panic_stop"), TEXT("safety_request")}
    };
    static const TMap<FString, FString> IntentRoutes = {
        {TEXT("request_context_refresh"), TEXT("/continuity/presence")},
        {TEXT("acknowledge_handback"), TEXT("operator_review_required")},
        {TEXT("request_review"), TEXT("operator_review_required")},
        {TEXT("request_panic_stop"), TEXT("/takeover/panic-stop")}
    };
    FFrancisPresenceViewModel Snapshot;
    FFrancisPresenceBridgeReadback CurrentReadback;
    {
        FScopeLock Lock(&StateMutex);
        Snapshot = ViewModel;
        CurrentReadback = Readback;
    }
    if (Snapshot.EnvelopeId.IsEmpty() || Snapshot.Sequence <= 0)
    {
        return false;
    }
    const int64 EventSequence = CurrentReadback.LastIntentSequence + 1;
    const FString IssuedAt = UtcNowIso();
    FDateTime IssuedDate;
    if (!FDateTime::ParseIso8601(*IssuedAt, IssuedDate))
    {
        return false;
    }
    const FString ExpiresAt = UtcIso(IssuedDate + FTimespan::FromSeconds(1));
    const FString EventSeed = FString::Join(
        TArray<FString>{
            CurrentReadback.AdapterId,
            CurrentReadback.SessionId,
            FString::Printf(TEXT("%lld"), EventSequence),
            Snapshot.EnvelopeId,
            Request.Kind,
            IssuedAt
        },
        TEXT("|")
    );
    OutEventId = IdFromSeed(TEXT("gpi_"), EventSeed);

    TSharedPtr<FJsonObject> Adapter = MakeShared<FJsonObject>();
    Adapter->SetStringField(TEXT("id"), CurrentReadback.AdapterId);
    Adapter->SetStringField(TEXT("kind"), TEXT("unreal"));
    Adapter->SetStringField(TEXT("role"), TEXT("governed_renderer_adapter"));
    Adapter->SetStringField(TEXT("engine_version"), TEXT("5.8"));
    Adapter->SetStringField(TEXT("session_id"), CurrentReadback.SessionId);
    Adapter->SetStringField(TEXT("authentication_status"), TEXT("ipc_hmac_wrapper_required"));
    TSharedPtr<FJsonObject> Source = MakeShared<FJsonObject>();
    Source->SetStringField(TEXT("envelope_id"), Snapshot.EnvelopeId);
    Source->SetNumberField(TEXT("sequence"), Snapshot.Sequence);
    Source->SetStringField(TEXT("channel"), RenderChannel);
    TSharedPtr<FJsonObject> Target = MakeShared<FJsonObject>();
    Target->SetStringField(TEXT("kind"), Request.TargetKind);
    Target->SetStringField(TEXT("id"), Request.TargetId);
    TSharedPtr<FJsonObject> Intent = MakeShared<FJsonObject>();
    Intent->SetStringField(TEXT("kind"), Request.Kind);
    Intent->SetStringField(TEXT("class"), IntentClasses[Request.Kind]);
    Intent->SetObjectField(TEXT("target"), Target);
    Intent->SetBoolField(TEXT("request_only"), true);
    TSharedPtr<FJsonObject> Routing = MakeShared<FJsonObject>();
    Routing->SetStringField(TEXT("required_core_route"), IntentRoutes[Request.Kind]);
    Routing->SetStringField(TEXT("status"), TEXT("not_dispatched"));
    Routing->SetBoolField(TEXT("dispatch_allowed"), false);
    Routing->SetBoolField(TEXT("mutation_allowed"), false);
    Routing->SetBoolField(TEXT("receipt_required_before_dispatch"), true);

    TSharedPtr<FJsonObject> Event = MakeShared<FJsonObject>();
    Event->SetStringField(TEXT("kind"), TEXT("francis.grounded_presence.intent_event"));
    Event->SetStringField(TEXT("schema_version"), TEXT("francis.grounded_presence.intent_event.v1"));
    Event->SetStringField(TEXT("schema_path"), TEXT("schemas/grounded_presence_intent_event.schema.json"));
    Event->SetStringField(TEXT("event_id"), OutEventId);
    Event->SetObjectField(TEXT("adapter"), Adapter);
    Event->SetNumberField(TEXT("event_sequence"), EventSequence);
    Event->SetObjectField(TEXT("source"), Source);
    Event->SetStringField(TEXT("issued_at"), IssuedAt);
    Event->SetStringField(TEXT("expires_at"), ExpiresAt);
    Event->SetNumberField(TEXT("ttl_ms"), 1000);
    Event->SetObjectField(TEXT("intent"), Intent);
    Event->SetObjectField(TEXT("routing"), Routing);
    Event->SetObjectField(TEXT("authority"), MakeAuthority());
    Event->SetArrayField(
        TEXT("limitations"),
        StringArray({
            TEXT("application_authentication_applied_at_ipc_wrapper"),
            TEXT("intent_is_not_a_dispatched_action"),
            TEXT("core_policy_route_required")
        })
    );
    const FString EventClaims = CanonicalObject(Event);
    FTCHARToUTF8 EventClaimsUtf8(*EventClaims);
    TArray<uint8> EventClaimBytes;
    EventClaimBytes.Append(reinterpret_cast<const uint8*>(EventClaimsUtf8.Get()), EventClaimsUtf8.Length());
    TSharedPtr<FJsonObject> EventIntegrity = MakeShared<FJsonObject>();
    EventIntegrity->SetStringField(TEXT("algorithm"), TEXT("sha256"));
    EventIntegrity->SetStringField(TEXT("canonicalization"), TEXT("json_sort_keys_compact_utf8_without_integrity"));
    EventIntegrity->SetStringField(TEXT("event_digest"), Sha256Hex(EventClaimBytes));
    Event->SetObjectField(TEXT("integrity"), EventIntegrity);

    const FString EventCanonical = CanonicalObject(Event);
    FTCHARToUTF8 EventUtf8(*EventCanonical);
    TArray<uint8> EventBytes;
    EventBytes.Append(reinterpret_cast<const uint8*>(EventUtf8.Get()), EventUtf8.Length());
    const FString PayloadDigest = Sha256Hex(EventBytes);
    const FString Nonce = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
    const FString MessageSeed = FString::Join(
        TArray<FString>{
            CurrentReadback.KeyId,
            IntentChannel,
            TEXT("unreal_to_francis_core"),
            Nonce,
            IssuedAt,
            PayloadDigest
        },
        TEXT("|")
    );
    TSharedPtr<FJsonObject> WireIntegrity = MakeShared<FJsonObject>();
    WireIntegrity->SetStringField(TEXT("algorithm"), TEXT("sha256"));
    WireIntegrity->SetStringField(TEXT("canonicalization"), TEXT("json_sort_keys_compact_utf8"));
    WireIntegrity->SetStringField(TEXT("payload_digest"), PayloadDigest);
    TSharedPtr<FJsonObject> Authentication = MakeShared<FJsonObject>();
    Authentication->SetStringField(TEXT("algorithm"), TEXT("hmac-sha256"));
    Authentication->SetStringField(TEXT("key_id"), CurrentReadback.KeyId);
    Authentication->SetStringField(TEXT("signature"), TEXT(""));
    TSharedPtr<FJsonObject> Wire = MakeShared<FJsonObject>();
    Wire->SetStringField(TEXT("kind"), TEXT("francis.grounded_presence.ipc_message"));
    Wire->SetStringField(TEXT("schema_version"), TEXT("francis.grounded_presence.ipc_message.v1"));
    Wire->SetStringField(TEXT("schema_path"), TEXT("schemas/grounded_presence_ipc_message.schema.json"));
    Wire->SetStringField(TEXT("message_id"), IdFromSeed(TEXT("gpm_"), MessageSeed));
    Wire->SetStringField(TEXT("channel"), IntentChannel);
    Wire->SetStringField(TEXT("direction"), TEXT("unreal_to_francis_core"));
    Wire->SetStringField(TEXT("issued_at"), IssuedAt);
    Wire->SetStringField(TEXT("expires_at"), ExpiresAt);
    Wire->SetNumberField(TEXT("ttl_ms"), 1000);
    Wire->SetStringField(TEXT("nonce"), Nonce);
    Wire->SetObjectField(TEXT("integrity"), WireIntegrity);
    Wire->SetObjectField(TEXT("authentication"), Authentication);
    Wire->SetObjectField(TEXT("payload"), Event);
    Wire->SetObjectField(TEXT("authority"), MakeAuthority());
    const FString UnsignedCanonical = CanonicalObject(Wire);
    FTCHARToUTF8 UnsignedUtf8(*UnsignedCanonical);
    TArray<uint8> UnsignedBytes;
    UnsignedBytes.Append(reinterpret_cast<const uint8*>(UnsignedUtf8.Get()), UnsignedUtf8.Length());
    Authentication->SetStringField(TEXT("signature"), HmacSha256Hex(UnsignedBytes));
    const FString SignedCanonical = CanonicalObject(Wire);
    FTCHARToUTF8 SignedUtf8(*SignedCanonical);
    OutJson.Append(reinterpret_cast<const uint8*>(SignedUtf8.Get()), SignedUtf8.Length());

    FString CommitError;
    if (!CommitDedup(LastEnvelopeId, LastPayloadDigest, CurrentReadback.LastAcceptedSequence, EventSequence, CommitError))
    {
        return false;
    }
    return true;
}

bool FFrancisPresenceBridge::ConnectIntentPipe(void*& OutHandle) const
{
    OutHandle = nullptr;
    if (!WaitNamedPipeW(*IntentPipePath, 20))
    {
        return false;
    }
    HANDLE Handle = CreateFileW(*IntentPipePath, GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
    if (Handle == INVALID_HANDLE_VALUE)
    {
        return false;
    }
    OutHandle = Handle;
    return true;
}

bool FFrancisPresenceBridge::CommitDedup(
    const FString& EnvelopeId,
    const FString& PayloadDigest,
    int64 Sequence,
    int64 IntentSequence,
    FString& OutError
)
{
    TSharedPtr<FJsonObject> State = MakeShared<FJsonObject>();
    State->SetStringField(TEXT("kind"), TEXT("francis.grounded_presence.unreal_dedup_state"));
    State->SetStringField(TEXT("schema_version"), TEXT("francis.grounded_presence.unreal_dedup_state.v1"));
    State->SetStringField(TEXT("adapter_id"), Readback.AdapterId);
    State->SetStringField(TEXT("session_id"), Readback.SessionId);
    State->SetStringField(TEXT("envelope_id"), EnvelopeId);
    State->SetStringField(TEXT("payload_digest"), PayloadDigest);
    State->SetNumberField(TEXT("last_accepted_sequence"), Sequence);
    State->SetNumberField(TEXT("last_intent_sequence"), IntentSequence);
    State->SetStringField(TEXT("committed_at"), UtcNowIso());
    State->SetObjectField(TEXT("authority"), MakeAuthority());
    const FString Serialized = CanonicalObject(State);
    const FString TempPath = Readback.DedupPath + TEXT(".tmp");
    if (!FFileHelper::SaveStringToFile(Serialized, *TempPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        OutError = TEXT("dedup_temp_write_failed");
        return false;
    }
    if (!IFileManager::Get().Move(*Readback.DedupPath, *TempPath, true, true, false, true))
    {
        IFileManager::Get().Delete(*TempPath, false, true);
        OutError = TEXT("dedup_atomic_replace_failed");
        return false;
    }
    {
        FScopeLock Lock(&StateMutex);
        Readback.LastAcceptedSequence = Sequence;
        Readback.LastIntentSequence = IntentSequence;
        LastEnvelopeId = EnvelopeId;
        LastPayloadDigest = PayloadDigest;
    }
    return true;
}

bool FFrancisPresenceBridge::LoadDedup()
{
    if (!IFileManager::Get().FileExists(*Readback.DedupPath))
    {
        return true;
    }
    FString Serialized;
    if (!FFileHelper::LoadFileToString(Serialized, *Readback.DedupPath))
    {
        Readback.LastError = TEXT("dedup_read_failed");
        return false;
    }
    TSharedPtr<FJsonObject> State;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Serialized);
    if (!FJsonSerializer::Deserialize(Reader, State) || !State.IsValid() ||
        StringField(State, TEXT("kind")) != TEXT("francis.grounded_presence.unreal_dedup_state") ||
        StringField(State, TEXT("adapter_id")) != Readback.AdapterId ||
        StringField(State, TEXT("session_id")) != Readback.SessionId ||
        !HasFalseAuthority(ObjectField(State, TEXT("authority")), false))
    {
        Readback.LastError = TEXT("dedup_state_invalid");
        return false;
    }
    Readback.LastAcceptedSequence = IntField(State, TEXT("last_accepted_sequence"));
    Readback.LastIntentSequence = IntField(State, TEXT("last_intent_sequence"));
    LastEnvelopeId = StringField(State, TEXT("envelope_id"));
    LastPayloadDigest = StringField(State, TEXT("payload_digest"));
    if (Readback.LastAcceptedSequence < 0 || Readback.LastIntentSequence < 0 ||
        (Readback.LastAcceptedSequence > 0 && (LastEnvelopeId.IsEmpty() || LastPayloadDigest.Len() != 64)))
    {
        Readback.LastError = TEXT("dedup_state_values_invalid");
        return false;
    }
    return true;
}

void FFrancisPresenceBridge::WriteRuntimeStatus(const FString& Status, const FString& Error)
{
    FFrancisPresenceViewModel Snapshot;
    FFrancisPresenceBridgeReadback Runtime;
    {
        FScopeLock Lock(&StateMutex);
        Snapshot = ViewModel;
        Runtime = Readback;
    }
    TSharedPtr<FJsonObject> Transport = MakeShared<FJsonObject>();
    Transport->SetStringField(TEXT("status"), Status);
    Transport->SetBoolField(TEXT("configured"), Runtime.bConfigured);
    Transport->SetBoolField(TEXT("pipe_connected"), Runtime.bPipeConnected);
    Transport->SetNumberField(TEXT("accepted_message_count"), Runtime.AcceptedMessageCount);
    Transport->SetNumberField(TEXT("rejected_message_count"), Runtime.RejectedMessageCount);
    Transport->SetNumberField(TEXT("duplicate_message_count"), Runtime.DuplicateMessageCount);
    Transport->SetStringField(TEXT("last_error"), Error.IsEmpty() ? Runtime.LastError : Error);
    TSharedPtr<FJsonObject> Render = MakeShared<FJsonObject>();
    Render->SetStringField(TEXT("status"), Snapshot.bRendered ? TEXT("applied") : Snapshot.bAuthenticated ? TEXT("queued") : TEXT("waiting"));
    Render->SetStringField(TEXT("envelope_id"), Snapshot.EnvelopeId);
    Render->SetNumberField(TEXT("sequence"), Snapshot.Sequence);
    Render->SetStringField(TEXT("received_at"), Snapshot.ReceivedAt);
    Render->SetStringField(TEXT("rendered_at"), Snapshot.RenderedAt);
    Render->SetStringField(TEXT("presence_state"), Snapshot.PresenceState);
    Render->SetStringField(TEXT("headline"), Snapshot.Headline.Left(512));
    Render->SetBoolField(TEXT("authenticated"), Snapshot.bAuthenticated);
    Render->SetBoolField(TEXT("runtime_observed"), Snapshot.bRuntimeObserved);
    TSharedPtr<FJsonObject> Intent = MakeShared<FJsonObject>();
    Intent->SetNumberField(TEXT("last_sequence"), Runtime.LastIntentSequence);
    Intent->SetStringField(TEXT("last_kind"), Runtime.LastIntentKind);
    Intent->SetStringField(TEXT("last_event_id"), Runtime.LastIntentId);
    Intent->SetNumberField(TEXT("sent_count"), Runtime.IntentSentCount);
    Intent->SetBoolField(TEXT("last_write_succeeded"), Runtime.bLastIntentWriteSucceeded);
    TSharedPtr<FJsonObject> Technology = MakeShared<FJsonObject>();
    Technology->SetStringField(TEXT("engine"), TEXT("Unreal Engine"));
    Technology->SetStringField(TEXT("engine_version"), TEXT("5.8"));
    Technology->SetArrayField(
        TEXT("active_stack"),
        StringArray({
            TEXT("cpp_runtime_module"),
            TEXT("slate_operator_surface"),
            TEXT("lumen_dynamic_gi"),
            TEXT("substrate_materials"),
            TEXT("niagara_fx"),
            TEXT("enhanced_input"),
            TEXT("procedural_presence_stage")
        })
    );
    TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("kind"), TEXT("francis.grounded_presence.unreal_runtime_status"));
    Root->SetStringField(TEXT("schema_version"), TEXT("francis.grounded_presence.unreal_runtime_status.v1"));
    Root->SetStringField(TEXT("schema_path"), TEXT("schemas/grounded_presence_unreal_runtime_status.schema.json"));
    Root->SetStringField(TEXT("observed_at"), UtcNowIso());
    Root->SetNumberField(TEXT("process_id"), FPlatformProcess::GetCurrentProcessId());
    Root->SetStringField(TEXT("adapter_id"), Runtime.AdapterId);
    Root->SetStringField(TEXT("session_id"), Runtime.SessionId);
    Root->SetStringField(TEXT("endpoint_id"), Runtime.EndpointId);
    Root->SetStringField(TEXT("authentication_key_id"), Runtime.KeyId);
    Root->SetObjectField(TEXT("transport"), Transport);
    Root->SetObjectField(TEXT("render"), Render);
    Root->SetObjectField(TEXT("intent"), Intent);
    Root->SetObjectField(TEXT("technology"), Technology);
    Root->SetObjectField(TEXT("authority"), MakeAuthority());
    Root->SetBoolField(TEXT("stores_presence_payload"), false);
    const FString Serialized = CanonicalObject(Root);
    const FString TempPath = Runtime.StatusPath + TEXT(".tmp");
    if (FFileHelper::SaveStringToFile(Serialized, *TempPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        IFileManager::Get().Move(*Runtime.StatusPath, *TempPath, true, true, false, true);
    }
}

FString FFrancisPresenceBridge::CanonicalJson(const TSharedPtr<FJsonValue>& Value)
{
    if (!Value.IsValid())
    {
        return TEXT("null");
    }
    switch (Value->Type)
    {
    case EJson::Null:
        return TEXT("null");
    case EJson::String:
        return EscapeJsonString(Value->AsString());
    case EJson::Number:
    {
        const double Number = Value->AsNumber();
        if (!FMath::IsFinite(Number))
        {
            return TEXT("null");
        }
        if (FMath::Abs(Number) <= 9007199254740991.0 && FMath::FloorToDouble(Number) == Number)
        {
            return FString::Printf(TEXT("%.0f"), Number);
        }
        return FString::SanitizeFloat(Number, 0);
    }
    case EJson::Boolean:
        return Value->AsBool() ? TEXT("true") : TEXT("false");
    case EJson::Array:
    {
        TArray<FString> Items;
        for (const TSharedPtr<FJsonValue>& Item : Value->AsArray())
        {
            Items.Add(CanonicalJson(Item));
        }
        return FString::Printf(TEXT("[%s]"), *FString::Join(Items, TEXT(",")));
    }
    case EJson::Object:
        return CanonicalObject(Value->AsObject());
    default:
        return TEXT("null");
    }
}

FString FFrancisPresenceBridge::CanonicalObject(const TSharedPtr<FJsonObject>& Object)
{
    if (!Object.IsValid())
    {
        return TEXT("{}");
    }
    TArray<TPair<FString, TSharedPtr<FJsonValue>>> Entries;
    Entries.Reserve(Object->Values.Num());
    for (const auto& Pair : Object->Values)
    {
        Entries.Emplace(FString(Pair.Key.Len(), *Pair.Key), Pair.Value);
    }
    Entries.Sort([](const auto& Left, const auto& Right)
    {
        return Left.Key.Compare(Right.Key, ESearchCase::CaseSensitive) < 0;
    });
    TArray<FString> Fields;
    Fields.Reserve(Entries.Num());
    for (const auto& Entry : Entries)
    {
        Fields.Add(EscapeJsonString(Entry.Key) + TEXT(":") + CanonicalJson(Entry.Value));
    }
    return FString::Printf(TEXT("{%s}"), *FString::Join(Fields, TEXT(",")));
}

FString FFrancisPresenceBridge::EscapeJsonString(const FString& Value)
{
    FString Result = TEXT("\"");
    for (int32 Index = 0; Index < Value.Len(); ++Index)
    {
        const TCHAR Character = Value[Index];
        switch (Character)
        {
        case '"': Result += TEXT("\\\""); break;
        case '\\': Result += TEXT("\\\\"); break;
        case '\b': Result += TEXT("\\b"); break;
        case '\f': Result += TEXT("\\f"); break;
        case '\n': Result += TEXT("\\n"); break;
        case '\r': Result += TEXT("\\r"); break;
        case '\t': Result += TEXT("\\t"); break;
        default:
            if (Character < 0x20 || Character > 0x7f)
            {
                Result += FString::Printf(TEXT("\\u%04x"), static_cast<uint16>(Character));
            }
            else
            {
                Result.AppendChar(Character);
            }
            break;
        }
    }
    Result += TEXT("\"");
    return Result;
}

bool FFrancisPresenceBridge::ParseJson(const TArray<uint8>& Json, TSharedPtr<FJsonObject>& OutObject)
{
    if (Json.IsEmpty())
    {
        return false;
    }
    FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(Json.GetData()), Json.Num());
    const FString Text(Converter.Length(), Converter.Get());
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    return FJsonSerializer::Deserialize(Reader, OutObject) && OutObject.IsValid();
}

bool FFrancisPresenceBridge::ExtractTopLevelValue(
    const TArray<uint8>& Json,
    const ANSICHAR* Key,
    TArray<uint8>& OutValue
)
{
    if (Json.Num() < 2 || Json[0] != '{')
    {
        return false;
    }
    int32 Index = 1;
    while (Json.IsValidIndex(Index))
    {
        while (Json.IsValidIndex(Index) && (FCharAnsi::IsWhitespace(static_cast<ANSICHAR>(Json[Index])) || Json[Index] == ','))
        {
            ++Index;
        }
        if (!Json.IsValidIndex(Index) || Json[Index] == '}')
        {
            break;
        }
        const int32 KeyStart = Index;
        const int32 KeyEnd = SkipJsonString(Json, KeyStart);
        if (KeyEnd == INDEX_NONE)
        {
            return false;
        }
        FString ParsedKey;
        if (KeyEnd - KeyStart >= 2)
        {
            const int32 Length = KeyEnd - KeyStart - 2;
            FUTF8ToTCHAR KeyConverter(reinterpret_cast<const ANSICHAR*>(Json.GetData() + KeyStart + 1), Length);
            ParsedKey = FString(KeyConverter.Length(), KeyConverter.Get());
        }
        Index = KeyEnd;
        while (Json.IsValidIndex(Index) && FCharAnsi::IsWhitespace(static_cast<ANSICHAR>(Json[Index])))
        {
            ++Index;
        }
        if (!Json.IsValidIndex(Index) || Json[Index] != ':')
        {
            return false;
        }
        ++Index;
        while (Json.IsValidIndex(Index) && FCharAnsi::IsWhitespace(static_cast<ANSICHAR>(Json[Index])))
        {
            ++Index;
        }
        const int32 ValueStart = Index;
        const int32 ValueEnd = SkipJsonValue(Json, ValueStart);
        if (ValueEnd == INDEX_NONE)
        {
            return false;
        }
        if (ParsedKey.Equals(UTF8_TO_TCHAR(Key), ESearchCase::CaseSensitive))
        {
            OutValue.Append(Json.GetData() + ValueStart, ValueEnd - ValueStart);
            return true;
        }
        Index = ValueEnd;
    }
    return false;
}

FString FFrancisPresenceBridge::Sha256Hex(const TArray<uint8>& Data)
{
    TArray<uint8> Hash;
    if (!HashSha256(Data, nullptr, Hash))
    {
        return FString();
    }
    return BytesToHex(Hash.GetData(), Hash.Num()).ToLower();
}

FString FFrancisPresenceBridge::HmacSha256Hex(const TArray<uint8>& Data) const
{
    TArray<uint8> Hash;
    if (!HashSha256(Data, &Secret, Hash))
    {
        return FString();
    }
    return BytesToHex(Hash.GetData(), Hash.Num()).ToLower();
}

FString FFrancisPresenceBridge::IdFromSeed(const FString& Prefix, const FString& Seed)
{
    FTCHARToUTF8 Utf8(*Seed);
    TArray<uint8> Bytes;
    Bytes.Append(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
    return Prefix + Sha256Hex(Bytes).Left(32);
}

FString FFrancisPresenceBridge::UtcIso(const FDateTime& Value)
{
    return FString::Printf(
        TEXT("%04d-%02d-%02dT%02d:%02d:%02d.%06d+00:00"),
        Value.GetYear(),
        Value.GetMonth(),
        Value.GetDay(),
        Value.GetHour(),
        Value.GetMinute(),
        Value.GetSecond(),
        Value.GetMillisecond() * 1000
    );
}

FString FFrancisPresenceBridge::UtcNowIso()
{
    return UtcIso(FDateTime::UtcNow());
}

bool FFrancisPresenceBridge::IsContractId(const FString& Value)
{
    if (Value.IsEmpty() || Value.Len() > 160)
    {
        return false;
    }
    for (const TCHAR Character : Value)
    {
        if (!FChar::IsAlnum(Character) && Character != '-' && Character != '_' && Character != '.')
        {
            return false;
        }
    }
    return true;
}

bool FFrancisPresenceBridge::HasFalseAuthority(
    const TSharedPtr<FJsonObject>& Authority,
    bool bRequireAdapterReadOnly
)
{
    if (!Authority.IsValid() || !BoolField(Authority, TEXT("francis_core_authoritative")))
    {
        return false;
    }
    if (bRequireAdapterReadOnly && !BoolField(Authority, TEXT("adapter_read_only")))
    {
        return false;
    }
    return !BoolField(Authority, TEXT("grants_execution_authority"), true) &&
        !BoolField(Authority, TEXT("grants_desktop_authority"), true) &&
        !BoolField(Authority, TEXT("grants_network_authority"), true) &&
        !BoolField(Authority, TEXT("grants_memory_write_authority"), true) &&
        !BoolField(Authority, TEXT("grants_approval_authority"), true);
}

FString FFrancisPresenceBridge::StringField(
    const TSharedPtr<FJsonObject>& Object,
    const FString& Field,
    const FString& Fallback
)
{
    FString Value;
    return Object.IsValid() && Object->TryGetStringField(Field, Value) ? Value : Fallback;
}

bool FFrancisPresenceBridge::BoolField(const TSharedPtr<FJsonObject>& Object, const FString& Field, bool Fallback)
{
    bool Value = Fallback;
    return Object.IsValid() && Object->TryGetBoolField(Field, Value) ? Value : Fallback;
}

int64 FFrancisPresenceBridge::IntField(const TSharedPtr<FJsonObject>& Object, const FString& Field, int64 Fallback)
{
    double Value = static_cast<double>(Fallback);
    if (!Object.IsValid() || !Object->TryGetNumberField(Field, Value) || !FMath::IsFinite(Value) || Value != FMath::FloorToDouble(Value))
    {
        return Fallback;
    }
    return static_cast<int64>(Value);
}

TSharedPtr<FJsonObject> FFrancisPresenceBridge::ObjectField(
    const TSharedPtr<FJsonObject>& Object,
    const FString& Field
)
{
    const TSharedPtr<FJsonObject>* Value = nullptr;
    return Object.IsValid() && Object->TryGetObjectField(Field, Value) && Value ? *Value : nullptr;
}
