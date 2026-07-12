#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

class FFrancisPresenceBridge;

class SFrancisPresencePanel final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SFrancisPresencePanel) {}
        SLATE_ARGUMENT(FFrancisPresenceBridge*, Bridge)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

private:
    FText HeadlineText() const;
    FText FocusText() const;
    FText NextStepText() const;
    FText PresenceStatusText() const;
    FText EvidenceStatusText() const;
    FText TransportStatusText() const;
    FText VoiceStatusText() const;
    FText SequenceText() const;
    FSlateColor StateColor() const;
    FSlateColor TransportColor() const;
    FReply RequestContextRefresh();
    FReply RequestReview();
    FReply AcknowledgeHandback();
    FReply RequestPanicStop();

    FFrancisPresenceBridge* Bridge = nullptr;
};
