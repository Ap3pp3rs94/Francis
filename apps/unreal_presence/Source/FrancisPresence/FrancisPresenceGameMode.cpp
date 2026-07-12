#include "FrancisPresenceGameMode.h"

#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "FrancisPresence.h"
#include "FrancisPresenceBridge.h"
#include "FrancisPresencePlayerController.h"
#include "FrancisPresenceStageActor.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformMisc.h"
#include "HighResScreenshot.h"
#include "Misc/Paths.h"
#include "SFrancisPresencePanel.h"
#include "TimerManager.h"

AFrancisPresenceGameMode::AFrancisPresenceGameMode()
{
    DefaultPawnClass = nullptr;
    PlayerControllerClass = AFrancisPresencePlayerController::StaticClass();
}

void AFrancisPresenceGameMode::StartPlay()
{
    Super::StartPlay();
    StageActor = GetWorld()->SpawnActor<AFrancisPresenceStageActor>();
    if (APlayerController* Controller = GetWorld()->GetFirstPlayerController())
    {
        Controller->bShowMouseCursor = true;
        FInputModeGameAndUI InputMode;
        InputMode.SetHideCursorDuringCapture(false);
        InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        Controller->SetInputMode(InputMode);
    }
    if (GEngine && GEngine->GameViewport && FFrancisPresenceModule::IsAvailable())
    {
        PresencePanel = SNew(SFrancisPresencePanel).Bridge(FFrancisPresenceModule::Get().GetBridge());
        GEngine->GameViewport->AddViewportWidgetContent(PresencePanel.ToSharedRef(), 100);
    }

    ScreenshotPath = FPlatformMisc::GetEnvironmentVariable(TEXT("FRANCIS_UNREAL_PRESENCE_SCREENSHOT_PATH"));
    if (!ScreenshotPath.IsEmpty())
    {
        ScreenshotPath = FPaths::ConvertRelativePathToFull(ScreenshotPath);
        GetWorldTimerManager().SetTimerForNextTick([this]()
        {
            FTimerHandle CaptureTimer;
            GetWorldTimerManager().SetTimer(CaptureTimer, this, &AFrancisPresenceGameMode::CaptureRequestedScreenshot, 5.0f, false);
        });
    }
    const FString ExitSecondsValue = FPlatformMisc::GetEnvironmentVariable(TEXT("FRANCIS_UNREAL_PRESENCE_EXIT_AFTER_SECONDS"));
    const float ExitSeconds = FCString::Atof(*ExitSecondsValue);
    if (ExitSeconds > 0.0f)
    {
        FTimerHandle ExitTimer;
        GetWorldTimerManager().SetTimer(ExitTimer, this, &AFrancisPresenceGameMode::ExitRequestedRuntime, ExitSeconds, false);
    }
}

void AFrancisPresenceGameMode::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (PresencePanel.IsValid() && GEngine && GEngine->GameViewport)
    {
        GEngine->GameViewport->RemoveViewportWidgetContent(PresencePanel.ToSharedRef());
        PresencePanel.Reset();
    }
    Super::EndPlay(EndPlayReason);
}

void AFrancisPresenceGameMode::CaptureRequestedScreenshot()
{
    if (!ScreenshotPath.IsEmpty())
    {
        FScreenshotRequest::RequestScreenshot(ScreenshotPath, false, false);
    }
}

void AFrancisPresenceGameMode::ExitRequestedRuntime()
{
    FPlatformMisc::RequestExit(false);
}
