#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"

#include "FrancisPresencePlayerController.generated.h"

class UInputAction;
class UInputMappingContext;

UCLASS()
class FRANCISPRESENCE_API AFrancisPresencePlayerController final : public APlayerController
{
    GENERATED_BODY()

public:
    AFrancisPresencePlayerController();
    virtual void Tick(float DeltaSeconds) override;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void SetupInputComponent() override;

private:
    void EnsureInputObjects();
    void QueueContextRefresh();
    void QueueHandoff();
    void QueueApprovalReview();
    void QueuePanicStop();
    void QueueGovernedIntent(const TCHAR* IntentKind);

    UPROPERTY(Transient)
    TObjectPtr<UInputMappingContext> PresenceMappingContext;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> ContextRefreshAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> HandoffAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> ApprovalReviewAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> PanicStopAction;

    bool bMappingInstalled = false;
    bool bAutoIntentEnabled = false;
    bool bAutoIntentInjected = false;
};
