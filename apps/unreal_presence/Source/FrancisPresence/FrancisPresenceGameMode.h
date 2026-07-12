#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"

#include "FrancisPresenceGameMode.generated.h"

class AFrancisPresenceStageActor;
class SFrancisPresencePanel;

UCLASS()
class FRANCISPRESENCE_API AFrancisPresenceGameMode final : public AGameModeBase
{
    GENERATED_BODY()

public:
    AFrancisPresenceGameMode();
    virtual void StartPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    void CaptureRequestedScreenshot();
    void ExitRequestedRuntime();

    UPROPERTY()
    TObjectPtr<AFrancisPresenceStageActor> StageActor;

    TSharedPtr<SFrancisPresencePanel> PresencePanel;
    FString ScreenshotPath;
};
