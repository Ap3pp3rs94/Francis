#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

class FFrancisPresenceBridge;
class SWidgetSwitcher;

enum class EFrancisPresencePage : uint8
{
    Frontend,
    Backend,
};

class SFrancisPresencePanel final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SFrancisPresencePanel) {}
        SLATE_ARGUMENT(FFrancisPresenceBridge*, Bridge)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

private:
    TSharedRef<SWidget> BuildHeader();
    TSharedRef<SWidget> BuildFrontendPage();
    TSharedRef<SWidget> BuildBackendPage();
    void SetActivePage(EFrancisPresencePage Page);

    FText HeadlineText() const;
    FText FocusText() const;
    FText NextStepText() const;
    FText PresenceStatusText() const;
    FText StageStatusText() const;
    FText EvidenceStatusText() const;
    FText FreshnessStatusText() const;
    FText TransportStatusText() const;
    FText VoiceStatusText() const;
    FText RuntimeStatusText() const;
    FText ModeStatusText() const;
    FText AdapterText() const;
    FText SessionText() const;
    FText EndpointText() const;
    FText TransportCountsText() const;
    FText IntentCountsText() const;
    FText EvidenceSummaryText() const;
    FText LimitationsText() const;
    FText AuthorityBoundaryText() const;
    FText SequenceText() const;
    FText LocalLinkText() const;
    FSlateColor StateColor() const;
    FSlateColor TransportColor() const;
    FSlateColor PageButtonColor(EFrancisPresencePage Page) const;
    FSlateColor PageButtonTextColor(EFrancisPresencePage Page) const;
    FReply ShowFrontend();
    FReply ShowBackend();
    FReply RequestContextRefresh();
    FReply RequestReview();
    FReply AcknowledgeHandback();
    FReply RequestPanicStop();

    FFrancisPresenceBridge* Bridge = nullptr;
    TSharedPtr<SWidgetSwitcher> PageSwitcher;
    EFrancisPresencePage ActivePage = EFrancisPresencePage::Frontend;
};
