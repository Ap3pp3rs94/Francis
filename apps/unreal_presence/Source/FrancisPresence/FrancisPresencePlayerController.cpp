#include "FrancisPresencePlayerController.h"

#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "FrancisPresence.h"
#include "FrancisPresenceBridge.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputCoreTypes.h"
#include "InputMappingContext.h"
#include "HAL/PlatformMisc.h"

AFrancisPresencePlayerController::AFrancisPresencePlayerController()
{
    PrimaryActorTick.bCanEverTick = true;
    bShowMouseCursor = true;
}

void AFrancisPresencePlayerController::BeginPlay()
{
    Super::BeginPlay();
    EnsureInputObjects();
    bAutoIntentEnabled = FPlatformMisc::GetEnvironmentVariable(TEXT("FRANCIS_UNREAL_PRESENCE_AUTO_INTENT")) ==
        TEXT("1");
    if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
            ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
    {
        Subsystem->AddMappingContext(PresenceMappingContext, 0);
        bMappingInstalled = true;
        UE_LOG(LogFrancisPresence, Display, TEXT("Enhanced Input governed intent mapping installed."));
    }
    else
    {
        UE_LOG(LogFrancisPresence, Error, TEXT("Enhanced Input local-player subsystem is unavailable."));
    }
}

void AFrancisPresencePlayerController::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bAutoIntentEnabled || bAutoIntentInjected || !FFrancisPresenceModule::IsAvailable())
    {
        return;
    }
    FFrancisPresenceBridge* Bridge = FFrancisPresenceModule::Get().GetBridge();
    if (!Bridge || Bridge->GetViewModel().EnvelopeId.IsEmpty())
    {
        return;
    }
    if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
            ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
    {
        const TArray<UInputModifier*> NoModifiers;
        const TArray<UInputTrigger*> NoTriggers;
        Subsystem->InjectInputForAction(ContextRefreshAction, FInputActionValue(true), NoModifiers, NoTriggers);
        bAutoIntentInjected = true;
        UE_LOG(LogFrancisPresence, Display, TEXT("Enhanced Input acceptance action injected."));
    }
}

void AFrancisPresencePlayerController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (bMappingInstalled)
    {
        if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
                ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
        {
            Subsystem->RemoveMappingContext(PresenceMappingContext);
        }
        bMappingInstalled = false;
    }
    Super::EndPlay(EndPlayReason);
}

void AFrancisPresencePlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    EnsureInputObjects();
    UEnhancedInputComponent* EnhancedInput = Cast<UEnhancedInputComponent>(InputComponent);
    if (!EnhancedInput)
    {
        UE_LOG(LogFrancisPresence, Error, TEXT("Enhanced Input component is unavailable."));
        return;
    }
    EnhancedInput->BindAction(ContextRefreshAction, ETriggerEvent::Started, this, &ThisClass::QueueContextRefresh);
    EnhancedInput->BindAction(HandoffAction, ETriggerEvent::Started, this, &ThisClass::QueueHandoff);
    EnhancedInput->BindAction(ApprovalReviewAction, ETriggerEvent::Started, this, &ThisClass::QueueApprovalReview);
    EnhancedInput->BindAction(PanicStopAction, ETriggerEvent::Started, this, &ThisClass::QueuePanicStop);
}

void AFrancisPresencePlayerController::EnsureInputObjects()
{
    if (PresenceMappingContext)
    {
        return;
    }
    PresenceMappingContext = NewObject<UInputMappingContext>(this, TEXT("IMC_FrancisPresenceGovernedIntents"));
    ContextRefreshAction = NewObject<UInputAction>(this, TEXT("IA_FrancisRequestContextRefresh"));
    HandoffAction = NewObject<UInputAction>(this, TEXT("IA_FrancisRequestHandoff"));
    ApprovalReviewAction = NewObject<UInputAction>(this, TEXT("IA_FrancisRequestApprovalReview"));
    PanicStopAction = NewObject<UInputAction>(this, TEXT("IA_FrancisRequestPanicStop"));

    ContextRefreshAction->ValueType = EInputActionValueType::Boolean;
    HandoffAction->ValueType = EInputActionValueType::Boolean;
    ApprovalReviewAction->ValueType = EInputActionValueType::Boolean;
    PanicStopAction->ValueType = EInputActionValueType::Boolean;

    PresenceMappingContext->MapKey(ContextRefreshAction, EKeys::F5);
    PresenceMappingContext->MapKey(HandoffAction, EKeys::F6);
    PresenceMappingContext->MapKey(ApprovalReviewAction, EKeys::F7);
    PresenceMappingContext->MapKey(PanicStopAction, EKeys::F12);
}

void AFrancisPresencePlayerController::QueueContextRefresh()
{
    QueueGovernedIntent(TEXT("request_context_refresh"));
}

void AFrancisPresencePlayerController::QueueHandoff()
{
    QueueGovernedIntent(TEXT("acknowledge_handback"));
}

void AFrancisPresencePlayerController::QueueApprovalReview()
{
    QueueGovernedIntent(TEXT("request_review"));
}

void AFrancisPresencePlayerController::QueuePanicStop()
{
    QueueGovernedIntent(TEXT("request_panic_stop"));
}

void AFrancisPresencePlayerController::QueueGovernedIntent(const TCHAR* IntentKind)
{
    if (FFrancisPresenceModule::IsAvailable())
    {
        if (FFrancisPresenceBridge* Bridge = FFrancisPresenceModule::Get().GetBridge())
        {
            const bool bQueued = Bridge->QueueIntent(IntentKind);
            if (bQueued)
            {
                UE_LOG(LogFrancisPresence, Display, TEXT("Enhanced Input governed intent %s: queued"), IntentKind);
            }
            else
            {
                UE_LOG(LogFrancisPresence, Warning, TEXT("Enhanced Input governed intent %s: not_queued"), IntentKind);
            }
        }
    }
}
