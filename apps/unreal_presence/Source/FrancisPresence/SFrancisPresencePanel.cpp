#include "SFrancisPresencePanel.h"

#include "FrancisPresenceBridge.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

void SFrancisPresencePanel::Construct(const FArguments& InArgs)
{
    Bridge = InArgs._Bridge;
    const FSlateFontInfo BrandFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 18);
    const FSlateFontInfo HeadingFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 30);
    const FSlateFontInfo BodyFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 15);
    const FSlateFontInfo SmallFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 11);
    const FLinearColor Ink(0.92f, 0.95f, 0.97f, 1.0f);
    const FLinearColor Muted(0.52f, 0.60f, 0.65f, 1.0f);
    const FLinearColor Panel(0.018f, 0.025f, 0.032f, 0.88f);
    const FLinearColor Border(0.15f, 0.21f, 0.24f, 0.9f);

    ChildSlot
    [
        SNew(SOverlay)
        + SOverlay::Slot()
        [
            SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
            .BorderBackgroundColor(FLinearColor(0.006f, 0.009f, 0.012f, 0.26f))
        ]
        + SOverlay::Slot()
        .Padding(FMargin(42.0f, 32.0f, 42.0f, 34.0f))
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot()
            .AutoHeight()
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot()
                .AutoWidth()
                .VAlign(VAlign_Center)
                [
                    SNew(SBorder)
                    .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                    .BorderBackgroundColor_Lambda([this]() { return StateColor().GetSpecifiedColor(); })
                    .Padding(FMargin(4.0f, 10.0f))
                    [
                        SNew(SBox).WidthOverride(4.0f)
                    ]
                ]
                + SHorizontalBox::Slot()
                .AutoWidth()
                .Padding(14.0f, 0.0f, 0.0f, 0.0f)
                .VAlign(VAlign_Center)
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("FRANCIS  /  GROUNDED PRESENCE")))
                    .Font(BrandFont)
                    .ColorAndOpacity(Ink)
                ]
                + SHorizontalBox::Slot()
                .FillWidth(1.0f)
                [SNew(SSpacer)]
                + SHorizontalBox::Slot()
                .AutoWidth()
                .VAlign(VAlign_Center)
                [
                    SNew(STextBlock)
                    .Text(this, &SFrancisPresencePanel::SequenceText)
                    .Font(SmallFont)
                    .ColorAndOpacity(Muted)
                ]
            ]
            + SVerticalBox::Slot()
            .FillHeight(1.0f)
            [SNew(SSpacer)]
            + SVerticalBox::Slot()
            .AutoHeight()
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot()
                .FillWidth(0.66f)
                .Padding(0.0f, 0.0f, 18.0f, 0.0f)
                [
                    SNew(SBorder)
                    .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                    .BorderBackgroundColor(Panel)
                    .Padding(FMargin(24.0f, 20.0f))
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot()
                        .AutoHeight()
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT("CURRENT BRIEFING")))
                            .Font(SmallFont)
                            .ColorAndOpacity(Muted)
                        ]
                        + SVerticalBox::Slot()
                        .AutoHeight()
                        .Padding(0.0f, 8.0f, 0.0f, 0.0f)
                        [
                            SNew(STextBlock)
                            .Text(this, &SFrancisPresencePanel::HeadlineText)
                            .Font(HeadingFont)
                            .ColorAndOpacity(Ink)
                            .AutoWrapText(true)
                        ]
                        + SVerticalBox::Slot()
                        .AutoHeight()
                        .Padding(0.0f, 12.0f, 0.0f, 0.0f)
                        [
                            SNew(STextBlock)
                            .Text(this, &SFrancisPresencePanel::FocusText)
                            .Font(BodyFont)
                            .ColorAndOpacity(FLinearColor(0.65f, 0.72f, 0.76f, 1.0f))
                            .AutoWrapText(true)
                        ]
                        + SVerticalBox::Slot()
                        .AutoHeight()
                        .Padding(0.0f, 10.0f, 0.0f, 0.0f)
                        [
                            SNew(STextBlock)
                            .Text(this, &SFrancisPresencePanel::NextStepText)
                            .Font(BodyFont)
                            .ColorAndOpacity(FLinearColor(0.76f, 0.81f, 0.84f, 1.0f))
                            .AutoWrapText(true)
                        ]
                    ]
                ]
                + SHorizontalBox::Slot()
                .FillWidth(0.34f)
                [
                    SNew(SBorder)
                    .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                    .BorderBackgroundColor(Panel)
                    .Padding(FMargin(20.0f))
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight()
                        [SNew(STextBlock).Text(FText::FromString(TEXT("TRUTH SURFACES"))).Font(SmallFont).ColorAndOpacity(Muted)]
                        + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 14.0f, 0.0f, 0.0f)
                        [SNew(STextBlock).Text(this, &SFrancisPresencePanel::PresenceStatusText).Font(BodyFont).ColorAndOpacity(this, &SFrancisPresencePanel::StateColor)]
                        + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 9.0f, 0.0f, 0.0f)
                        [SNew(STextBlock).Text(this, &SFrancisPresencePanel::EvidenceStatusText).Font(BodyFont).ColorAndOpacity(Ink)]
                        + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 9.0f, 0.0f, 0.0f)
                        [SNew(STextBlock).Text(this, &SFrancisPresencePanel::TransportStatusText).Font(BodyFont).ColorAndOpacity(this, &SFrancisPresencePanel::TransportColor)]
                        + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 9.0f, 0.0f, 0.0f)
                        [SNew(STextBlock).Text(this, &SFrancisPresencePanel::VoiceStatusText).Font(BodyFont).ColorAndOpacity(Ink)]
                        + SVerticalBox::Slot().FillHeight(1.0f)
                        [SNew(SSpacer)]
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT("CORE AUTHORITY  /  RENDER ONLY")))
                            .Font(SmallFont)
                            .ColorAndOpacity(FLinearColor(0.28f, 0.78f, 0.66f, 1.0f))
                        ]
                    ]
                ]
            ]
            + SVerticalBox::Slot()
            .AutoHeight()
            .Padding(0.0f, 16.0f, 0.0f, 0.0f)
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 10.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("Refresh context"))).OnClicked(this, &SFrancisPresencePanel::RequestContextRefresh)]
                + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 10.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("Request review"))).OnClicked(this, &SFrancisPresencePanel::RequestReview)]
                + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 10.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("Acknowledge handback"))).OnClicked(this, &SFrancisPresencePanel::AcknowledgeHandback)]
                + SHorizontalBox::Slot().FillWidth(1.0f)
                [SNew(SSpacer)]
                + SHorizontalBox::Slot().AutoWidth()
                [SNew(SButton).Text(FText::FromString(TEXT("Request panic stop"))).OnClicked(this, &SFrancisPresencePanel::RequestPanicStop)]
            ]
        ]
    ];
}

FText SFrancisPresencePanel::HeadlineText() const
{
    return FText::FromString(Bridge ? Bridge->GetViewModel().Headline : TEXT("Bridge unavailable."));
}

FText SFrancisPresencePanel::FocusText() const
{
    if (!Bridge) return FText::GetEmpty();
    const FFrancisPresenceViewModel State = Bridge->GetViewModel();
    const FString Focus = !State.FocusObjective.IsEmpty() ? State.FocusObjective : State.FocusTitle;
    return FText::FromString(Focus.IsEmpty() ? TEXT("No active focus has been observed.") : Focus);
}

FText SFrancisPresencePanel::NextStepText() const
{
    if (!Bridge) return FText::GetEmpty();
    const FString Next = Bridge->GetViewModel().NextStep;
    return FText::FromString(Next.IsEmpty() ? TEXT("No grounded next step is available.") : FString(TEXT("Next  /  ")) + Next);
}

FText SFrancisPresencePanel::PresenceStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(FString::Printf(TEXT("Presence     %s"), *State.PresenceState));
}

FText SFrancisPresencePanel::EvidenceStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(FString::Printf(TEXT("Evidence     %s"), *State.EvidenceStatus));
}

FText SFrancisPresencePanel::TransportStatusText() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    return FText::FromString(FString::Printf(TEXT("Transport    %s"), *State.Status));
}

FText SFrancisPresencePanel::VoiceStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    const FString Provider = State.VoiceProvider.IsEmpty() ? TEXT("unassigned") : State.VoiceProvider;
    return FText::FromString(FString::Printf(TEXT("Voice        %s / %s"), *State.VoiceStatus, *Provider));
}

FText SFrancisPresencePanel::SequenceText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(State.Sequence > 0
        ? FString::Printf(TEXT("ENVELOPE %lld  /  AUTHENTICATED"), State.Sequence)
        : TEXT("WAITING FOR AUTHENTICATED CORE STATE"));
}

FSlateColor SFrancisPresencePanel::StateColor() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    const FString Combined = (State.PresenceState + TEXT(" ") + State.SemanticState + TEXT(" ") + State.IncidentPressure).ToLower();
    if (Combined.Contains(TEXT("fault")) || Combined.Contains(TEXT("error")) || Combined.Contains(TEXT("panic")))
        return FLinearColor(0.95f, 0.24f, 0.16f, 1.0f);
    if (Combined.Contains(TEXT("attention")) || Combined.Contains(TEXT("blocked")) || Combined.Contains(TEXT("warning")))
        return FLinearColor(0.96f, 0.58f, 0.12f, 1.0f);
    if (Combined.Contains(TEXT("handoff")) || Combined.Contains(TEXT("review")))
        return FLinearColor(0.32f, 0.52f, 1.0f, 1.0f);
    return FLinearColor(0.16f, 0.78f, 0.70f, 1.0f);
}

FSlateColor SFrancisPresencePanel::TransportColor() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    return State.Status.Contains(TEXT("error")) || State.Status.Contains(TEXT("required"))
        ? FLinearColor(0.96f, 0.54f, 0.12f, 1.0f)
        : FLinearColor(0.42f, 0.76f, 0.70f, 1.0f);
}

FReply SFrancisPresencePanel::RequestContextRefresh()
{
    if (Bridge) Bridge->QueueIntent(TEXT("request_context_refresh"));
    return FReply::Handled();
}
FReply SFrancisPresencePanel::RequestReview()
{
    if (Bridge) Bridge->QueueIntent(TEXT("request_review"));
    return FReply::Handled();
}

FReply SFrancisPresencePanel::AcknowledgeHandback()
{
    if (Bridge) Bridge->QueueIntent(TEXT("acknowledge_handback"));
    return FReply::Handled();
}

FReply SFrancisPresencePanel::RequestPanicStop()
{
    if (Bridge) Bridge->QueueIntent(TEXT("request_panic_stop"));
    return FReply::Handled();
}
