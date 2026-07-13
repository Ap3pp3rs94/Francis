#include "SFrancisPresencePanel.h"

#include "FrancisPresenceBridge.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SWidgetSwitcher.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
const FLinearColor Background(0.008f, 0.009f, 0.012f, 0.58f);
const FLinearColor Surface(0.030f, 0.034f, 0.041f, 0.94f);
const FLinearColor SurfaceRaised(0.047f, 0.052f, 0.061f, 0.96f);
const FLinearColor Hairline(0.21f, 0.22f, 0.23f, 0.82f);
const FLinearColor Ink(0.95f, 0.93f, 0.88f, 1.0f);
const FLinearColor Muted(0.57f, 0.59f, 0.62f, 1.0f);
const FLinearColor Champagne(0.78f, 0.70f, 0.54f, 1.0f);
const FLinearColor Steel(0.49f, 0.59f, 0.69f, 1.0f);
const FLinearColor Live(0.35f, 0.72f, 0.58f, 1.0f);
const FLinearColor Warning(0.78f, 0.57f, 0.31f, 1.0f);
const FLinearColor Danger(0.72f, 0.31f, 0.26f, 1.0f);

const TCHAR* TruthWord(bool bValue)
{
    return bValue ? TEXT("yes") : TEXT("no");
}
}

void SFrancisPresencePanel::Construct(const FArguments& InArgs)
{
    Bridge = InArgs._Bridge;

    ChildSlot
    [
        SNew(SOverlay)
        + SOverlay::Slot()
        [
            SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
            .BorderBackgroundColor(Background)
        ]
        + SOverlay::Slot()
        .Padding(FMargin(34.0f, 24.0f, 34.0f, 28.0f))
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot()
            .AutoHeight()
            [
                BuildHeader()
            ]
            + SVerticalBox::Slot()
            .FillHeight(1.0f)
            .Padding(0.0f, 18.0f, 0.0f, 0.0f)
            [
                SAssignNew(PageSwitcher, SWidgetSwitcher)
                + SWidgetSwitcher::Slot()
                [
                    BuildFrontendPage()
                ]
                + SWidgetSwitcher::Slot()
                [
                    BuildBackendPage()
                ]
            ]
        ]
    ];
    PageSwitcher->SetActiveWidgetIndex(static_cast<int32>(ActivePage));
}

TSharedRef<SWidget> SFrancisPresencePanel::BuildHeader()
{
    const FSlateFontInfo BrandFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 20);
    const FSlateFontInfo MetaFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 10);
    const FSlateFontInfo NavFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 12);

    return SNew(SBorder)
        .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
        .BorderBackgroundColor(FLinearColor(0.020f, 0.022f, 0.027f, 0.97f))
        .Padding(FMargin(16.0f, 10.0f))
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot()
            .AutoWidth()
            .VAlign(VAlign_Center)
            [
                SNew(SBorder)
                .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                .BorderBackgroundColor_Lambda([this]() { return StateColor().GetSpecifiedColor(); })
                .Padding(FMargin(3.0f, 11.0f))
                [
                    SNew(SBox).WidthOverride(3.0f)
                ]
            ]
            + SHorizontalBox::Slot()
            .AutoWidth()
            .Padding(12.0f, 0.0f, 0.0f, 0.0f)
            .VAlign(VAlign_Center)
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight()
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("Francis")))
                    .Font(BrandFont)
                    .ColorAndOpacity(Ink)
                ]
                + SVerticalBox::Slot().AutoHeight()
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("LOCAL OPERATOR LAYER  /  UNREAL 5.8")))
                    .Font(MetaFont)
                    .ColorAndOpacity(Muted)
                ]
            ]
            + SHorizontalBox::Slot()
            .FillWidth(1.0f)
            [
                SNew(SSpacer)
            ]
            + SHorizontalBox::Slot()
            .AutoWidth()
            .VAlign(VAlign_Center)
            [
                SNew(SButton)
                .ContentPadding(FMargin(18.0f, 8.0f))
                .ButtonColorAndOpacity_Lambda([this]() { return PageButtonColor(EFrancisPresencePage::Frontend).GetSpecifiedColor(); })
                .OnClicked(this, &SFrancisPresencePanel::ShowFrontend)
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("Frontend")))
                    .Font(NavFont)
                    .ColorAndOpacity_Lambda([this]() { return PageButtonTextColor(EFrancisPresencePage::Frontend); })
                ]
            ]
            + SHorizontalBox::Slot()
            .AutoWidth()
            .Padding(4.0f, 0.0f, 0.0f, 0.0f)
            .VAlign(VAlign_Center)
            [
                SNew(SButton)
                .ContentPadding(FMargin(18.0f, 8.0f))
                .ButtonColorAndOpacity_Lambda([this]() { return PageButtonColor(EFrancisPresencePage::Backend).GetSpecifiedColor(); })
                .OnClicked(this, &SFrancisPresencePanel::ShowBackend)
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("Backend")))
                    .Font(NavFont)
                    .ColorAndOpacity_Lambda([this]() { return PageButtonTextColor(EFrancisPresencePage::Backend); })
                ]
            ]
            + SHorizontalBox::Slot()
            .FillWidth(1.0f)
            [
                SNew(SSpacer)
            ]
            + SHorizontalBox::Slot()
            .AutoWidth()
            .VAlign(VAlign_Center)
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right)
                [
                    SNew(STextBlock)
                    .Text(this, &SFrancisPresencePanel::LocalLinkText)
                    .Font(NavFont)
                    .ColorAndOpacity(this, &SFrancisPresencePanel::TransportColor)
                ]
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right)
                [
                    SNew(STextBlock)
                    .Text(this, &SFrancisPresencePanel::SequenceText)
                    .Font(MetaFont)
                    .ColorAndOpacity(Muted)
                ]
            ]
        ];
}

TSharedRef<SWidget> SFrancisPresencePanel::BuildFrontendPage()
{
    const FSlateFontInfo EyebrowFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 11);
    const FSlateFontInfo DisplayFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 44);
    const FSlateFontInfo HeadingFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 25);
    const FSlateFontInfo BodyFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 14);
    const FSlateFontInfo SmallFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 10);
    const FSlateFontInfo ButtonFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 11);

    return SNew(SVerticalBox)
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1.0f)
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight()
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("FRONTEND  /  GROUNDED PRESENCE")))
                    .Font(EyebrowFont)
                    .ColorAndOpacity(Champagne)
                ]
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 4.0f, 0.0f, 0.0f)
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("Francis")))
                    .Font(DisplayFont)
                    .ColorAndOpacity(Ink)
                ]
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 6.0f, 0.0f, 0.0f)
                [
                    SNew(STextBlock)
                    .Text(this, &SFrancisPresencePanel::HeadlineText)
                    .Font(BodyFont)
                    .ColorAndOpacity(Muted)
                    .AutoWrapText(true)
                    .WrapTextAt(720.0f)
                ]
            ]
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom)
            [
                SNew(STextBlock)
                .Text(this, &SFrancisPresencePanel::PresenceStatusText)
                .Font(BodyFont)
                .ColorAndOpacity(this, &SFrancisPresencePanel::StateColor)
            ]
        ]
        + SVerticalBox::Slot()
        .FillHeight(1.0f)
        [
            SNew(SSpacer)
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(0.66f).Padding(0.0f, 0.0f, 9.0f, 0.0f)
            [
                SNew(SBorder)
                .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                .BorderBackgroundColor(Surface)
                .Padding(FMargin(22.0f, 18.0f))
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(STextBlock)
                        .Text(FText::FromString(TEXT("CURRENT BRIEFING")))
                        .Font(SmallFont)
                        .ColorAndOpacity(Steel)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 8.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock)
                        .Text(this, &SFrancisPresencePanel::HeadlineText)
                        .Font(HeadingFont)
                        .ColorAndOpacity(Ink)
                        .AutoWrapText(true)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 12.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock)
                        .Text(this, &SFrancisPresencePanel::FocusText)
                        .Font(BodyFont)
                        .ColorAndOpacity(FLinearColor(0.72f, 0.75f, 0.76f, 1.0f))
                        .AutoWrapText(true)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 9.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock)
                        .Text(this, &SFrancisPresencePanel::NextStepText)
                        .Font(BodyFont)
                        .ColorAndOpacity(Ink)
                        .AutoWrapText(true)
                    ]
                ]
            ]
            + SHorizontalBox::Slot().FillWidth(0.34f).Padding(9.0f, 0.0f, 0.0f, 0.0f)
            [
                SNew(SBorder)
                .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                .BorderBackgroundColor(Surface)
                .Padding(FMargin(20.0f, 18.0f))
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(STextBlock).Text(FText::FromString(TEXT("LIVE TRUTH"))).Font(SmallFont).ColorAndOpacity(Steel)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 12.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock).Text(this, &SFrancisPresencePanel::VoiceStatusText).Font(BodyFont).ColorAndOpacity(Ink)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 8.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock).Text(this, &SFrancisPresencePanel::EvidenceStatusText).Font(BodyFont).ColorAndOpacity(Ink)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 8.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock).Text(this, &SFrancisPresencePanel::FreshnessStatusText).Font(BodyFont).ColorAndOpacity(Ink)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 8.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock).Text(this, &SFrancisPresencePanel::ModeStatusText).Font(BodyFont).ColorAndOpacity(Muted).AutoWrapText(true)
                    ]
                    + SVerticalBox::Slot().FillHeight(1.0f)
                    [
                        SNew(SSpacer)
                    ]
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(STextBlock)
                        .Text(FText::FromString(TEXT("CORE AUTHORITY  /  REQUEST ONLY")))
                        .Font(SmallFont)
                        .ColorAndOpacity(Live)
                    ]
                ]
            ]
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        .Padding(0.0f, 14.0f, 0.0f, 0.0f)
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 8.0f, 0.0f)
            [
                SNew(SButton).ContentPadding(FMargin(14.0f, 7.0f)).ButtonColorAndOpacity(SurfaceRaised)
                .OnClicked(this, &SFrancisPresencePanel::RequestContextRefresh)
                [SNew(STextBlock).Text(FText::FromString(TEXT("Refresh"))).Font(ButtonFont).ColorAndOpacity(Ink)]
            ]
            + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 8.0f, 0.0f)
            [
                SNew(SButton).ContentPadding(FMargin(14.0f, 7.0f)).ButtonColorAndOpacity(SurfaceRaised)
                .OnClicked(this, &SFrancisPresencePanel::RequestReview)
                [SNew(STextBlock).Text(FText::FromString(TEXT("Request review"))).Font(ButtonFont).ColorAndOpacity(Ink)]
            ]
            + SHorizontalBox::Slot().AutoWidth()
            [
                SNew(SButton).ContentPadding(FMargin(14.0f, 7.0f)).ButtonColorAndOpacity(SurfaceRaised)
                .OnClicked(this, &SFrancisPresencePanel::AcknowledgeHandback)
                [SNew(STextBlock).Text(FText::FromString(TEXT("Handback"))).Font(ButtonFont).ColorAndOpacity(Ink)]
            ]
            + SHorizontalBox::Slot().FillWidth(1.0f)
            [
                SNew(SSpacer)
            ]
            + SHorizontalBox::Slot().AutoWidth()
            [
                SNew(SButton).ContentPadding(FMargin(14.0f, 7.0f)).ButtonColorAndOpacity(FLinearColor(0.22f, 0.08f, 0.07f, 1.0f))
                .OnClicked(this, &SFrancisPresencePanel::RequestPanicStop)
                [SNew(STextBlock).Text(FText::FromString(TEXT("Request panic stop"))).Font(ButtonFont).ColorAndOpacity(FLinearColor(0.95f, 0.70f, 0.65f, 1.0f))]
            ]
        ];
}

TSharedRef<SWidget> SFrancisPresencePanel::BuildBackendPage()
{
    const FSlateFontInfo EyebrowFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 11);
    const FSlateFontInfo DisplayFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 42);
    const FSlateFontInfo MetricLabelFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 9);
    const FSlateFontInfo MetricFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 13);
    const FSlateFontInfo BodyFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 13);

    return SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight()
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1.0f)
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight()
                [SNew(STextBlock).Text(FText::FromString(TEXT("BACKEND  /  SYSTEMS"))).Font(EyebrowFont).ColorAndOpacity(Champagne)]
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 4.0f, 0.0f, 0.0f)
                [SNew(STextBlock).Text(FText::FromString(TEXT("Systems"))).Font(DisplayFont).ColorAndOpacity(Ink)]
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 6.0f, 0.0f, 0.0f)
                [SNew(STextBlock).Text(FText::FromString(TEXT("Authenticated transport, evidence posture, runtime state, and governed intent receipts."))).Font(BodyFont).ColorAndOpacity(Muted)]
            ]
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom)
            [
                SNew(STextBlock)
                .Text(this, &SFrancisPresencePanel::AuthorityBoundaryText)
                .Font(EyebrowFont)
                .ColorAndOpacity(Live)
            ]
        ]
        + SVerticalBox::Slot().FillHeight(1.0f)
        [SNew(SSpacer)]
        + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 8.0f)
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1.0f).Padding(0.0f, 0.0f, 6.0f, 0.0f)
            [
                SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(Surface).Padding(FMargin(14.0f, 12.0f))
                [SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("TRANSPORT"))).Font(MetricLabelFont).ColorAndOpacity(Steel)]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 7.0f, 0.0f, 0.0f)[SNew(STextBlock).Text(this, &SFrancisPresencePanel::TransportStatusText).Font(MetricFont).ColorAndOpacity(this, &SFrancisPresencePanel::TransportColor).AutoWrapText(true)]]
            ]
            + SHorizontalBox::Slot().FillWidth(1.0f).Padding(6.0f, 0.0f)
            [
                SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(Surface).Padding(FMargin(14.0f, 12.0f))
                [SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("RUNTIME"))).Font(MetricLabelFont).ColorAndOpacity(Steel)]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 7.0f, 0.0f, 0.0f)[SNew(STextBlock).Text(this, &SFrancisPresencePanel::RuntimeStatusText).Font(MetricFont).ColorAndOpacity(Ink).AutoWrapText(true)]]
            ]
            + SHorizontalBox::Slot().FillWidth(1.0f).Padding(6.0f, 0.0f)
            [
                SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(Surface).Padding(FMargin(14.0f, 12.0f))
                [SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("STAGE GATE"))).Font(MetricLabelFont).ColorAndOpacity(Steel)]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 7.0f, 0.0f, 0.0f)[SNew(STextBlock).Text(this, &SFrancisPresencePanel::StageStatusText).Font(MetricFont).ColorAndOpacity(this, &SFrancisPresencePanel::StateColor).AutoWrapText(true)]]
            ]
            + SHorizontalBox::Slot().FillWidth(1.0f).Padding(6.0f, 0.0f, 0.0f, 0.0f)
            [
                SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(Surface).Padding(FMargin(14.0f, 12.0f))
                [SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("EVIDENCE"))).Font(MetricLabelFont).ColorAndOpacity(Steel)]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 7.0f, 0.0f, 0.0f)[SNew(STextBlock).Text(this, &SFrancisPresencePanel::EvidenceSummaryText).Font(MetricFont).ColorAndOpacity(Ink).AutoWrapText(true)]]
            ]
        ]
        + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 8.0f, 0.0f, 0.0f)
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1.0f).Padding(0.0f, 0.0f, 6.0f, 0.0f)
            [
                SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(Surface).Padding(FMargin(14.0f, 12.0f))
                [SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("ADAPTER"))).Font(MetricLabelFont).ColorAndOpacity(Steel)]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 7.0f, 0.0f, 0.0f)[SNew(STextBlock).Text(this, &SFrancisPresencePanel::AdapterText).Font(MetricFont).ColorAndOpacity(Ink).AutoWrapText(true)]]
            ]
            + SHorizontalBox::Slot().FillWidth(1.0f).Padding(6.0f, 0.0f)
            [
                SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(Surface).Padding(FMargin(14.0f, 12.0f))
                [SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("SESSION"))).Font(MetricLabelFont).ColorAndOpacity(Steel)]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 7.0f, 0.0f, 0.0f)[SNew(STextBlock).Text(this, &SFrancisPresencePanel::SessionText).Font(MetricFont).ColorAndOpacity(Ink).AutoWrapText(true)]]
            ]
            + SHorizontalBox::Slot().FillWidth(1.0f).Padding(6.0f, 0.0f)
            [
                SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(Surface).Padding(FMargin(14.0f, 12.0f))
                [SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("MESSAGES"))).Font(MetricLabelFont).ColorAndOpacity(Steel)]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 7.0f, 0.0f, 0.0f)[SNew(STextBlock).Text(this, &SFrancisPresencePanel::TransportCountsText).Font(MetricFont).ColorAndOpacity(Ink).AutoWrapText(true)]]
            ]
            + SHorizontalBox::Slot().FillWidth(1.0f).Padding(6.0f, 0.0f, 0.0f, 0.0f)
            [
                SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(Surface).Padding(FMargin(14.0f, 12.0f))
                [SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("INTENT RECEIPTS"))).Font(MetricLabelFont).ColorAndOpacity(Steel)]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 7.0f, 0.0f, 0.0f)[SNew(STextBlock).Text(this, &SFrancisPresencePanel::IntentCountsText).Font(MetricFont).ColorAndOpacity(Ink).AutoWrapText(true)]]
            ]
        ]
        + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 14.0f, 0.0f, 0.0f)
        [
            SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
            .BorderBackgroundColor(SurfaceRaised)
            .Padding(FMargin(14.0f, 10.0f))
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight()
                [SNew(STextBlock).Text(this, &SFrancisPresencePanel::EndpointText).Font(BodyFont).ColorAndOpacity(Muted).AutoWrapText(true)]
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 5.0f, 0.0f, 0.0f)
                [SNew(STextBlock).Text(this, &SFrancisPresencePanel::LimitationsText).Font(BodyFont).ColorAndOpacity(Ink).AutoWrapText(true)]
            ]
        ];
}

void SFrancisPresencePanel::SetActivePage(EFrancisPresencePage Page)
{
    ActivePage = Page;
    if (PageSwitcher.IsValid())
    {
        PageSwitcher->SetActiveWidgetIndex(static_cast<int32>(Page));
    }
}

FReply SFrancisPresencePanel::ShowFrontend()
{
    SetActivePage(EFrancisPresencePage::Frontend);
    return FReply::Handled();
}

FReply SFrancisPresencePanel::ShowBackend()
{
    SetActivePage(EFrancisPresencePage::Backend);
    return FReply::Handled();
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
    return FText::FromString(Focus.IsEmpty() ? TEXT("Focus  /  No active focus has been observed.") : FString(TEXT("Focus  /  ")) + Focus);
}

FText SFrancisPresencePanel::NextStepText() const
{
    if (!Bridge) return FText::GetEmpty();
    const FString Next = Bridge->GetViewModel().NextStep;
    return FText::FromString(Next.IsEmpty() ? TEXT("Next  /  No grounded next step is available.") : FString(TEXT("Next  /  ")) + Next);
}

FText SFrancisPresencePanel::PresenceStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(FString::Printf(TEXT("Presence  /  %s"), *State.PresenceState));
}

FText SFrancisPresencePanel::StageStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(FString::Printf(TEXT("%s / approval required %s"), *State.StageStatus, TruthWord(State.bApprovalRequired)));
}

FText SFrancisPresencePanel::EvidenceStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(FString::Printf(TEXT("Evidence  /  %s"), *State.EvidenceStatus));
}

FText SFrancisPresencePanel::FreshnessStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(FString::Printf(TEXT("Freshness  /  %s"), *State.FreshnessStatus));
}

FText SFrancisPresencePanel::TransportStatusText() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    const FString Error = State.LastError.Left(120);
    return FText::FromString(Error.IsEmpty() ? State.Status : FString::Printf(TEXT("%s / %s"), *State.Status, *Error));
}

FText SFrancisPresencePanel::VoiceStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    const FString Provider = State.VoiceProvider.IsEmpty() ? TEXT("unassigned") : State.VoiceProvider;
    return FText::FromString(FString::Printf(TEXT("Voice  /  %s / %s"), *State.VoiceStatus, *Provider));
}

FText SFrancisPresencePanel::RuntimeStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(FString::Printf(
        TEXT("authenticated %s / rendered %s / observed %s"),
        TruthWord(State.bAuthenticated),
        TruthWord(State.bRendered),
        TruthWord(State.bRuntimeObserved)));
}

FText SFrancisPresencePanel::ModeStatusText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(FString::Printf(TEXT("Mode  /  %s / %s / %s"), *State.Mode, *State.SemanticState, *State.Activity));
}

FText SFrancisPresencePanel::AdapterText() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    const FString Adapter = State.AdapterId.IsEmpty() ? TEXT("unconfigured") : State.AdapterId;
    const FString Key = State.KeyId.IsEmpty() ? TEXT("no key id") : State.KeyId;
    return FText::FromString(FString::Printf(TEXT("%s / %s"), *Adapter, *Key));
}

FText SFrancisPresencePanel::SessionText() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    return FText::FromString(State.SessionId.IsEmpty() ? TEXT("No local session") : State.SessionId);
}

FText SFrancisPresencePanel::EndpointText() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    const FString Endpoint = State.EndpointId.IsEmpty() ? TEXT("unavailable") : State.EndpointId;
    return FText::FromString(FString::Printf(TEXT("Local endpoint  /  %s"), *Endpoint));
}

FText SFrancisPresencePanel::TransportCountsText() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    return FText::FromString(FString::Printf(
        TEXT("accepted %lld / duplicate %lld / rejected %lld"),
        State.AcceptedMessageCount,
        State.DuplicateMessageCount,
        State.RejectedMessageCount));
}

FText SFrancisPresencePanel::IntentCountsText() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    const FString Last = State.LastIntentKind.IsEmpty() ? TEXT("none") : State.LastIntentKind;
    return FText::FromString(FString::Printf(
        TEXT("sent %lld / last %s / write %s"),
        State.IntentSentCount,
        *Last,
        TruthWord(State.bLastIntentWriteSucceeded)));
}

FText SFrancisPresencePanel::EvidenceSummaryText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(FString::Printf(
        TEXT("%s / references %d / linked %s"),
        *State.EvidenceStatus,
        State.EvidenceReferences.Num(),
        TruthWord(State.bReceiptLinked)));
}

FText SFrancisPresencePanel::LimitationsText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    if (State.Limitations.IsEmpty())
    {
        return FText::FromString(TEXT("Limitations  /  none supplied by Core"));
    }
    TArray<FString> Visible = State.Limitations;
    Visible.SetNum(FMath::Min(Visible.Num(), 3));
    return FText::FromString(FString::Printf(TEXT("Limitations  /  %s"), *FString::Join(Visible, TEXT(" / "))));
}

FText SFrancisPresencePanel::AuthorityBoundaryText() const
{
    return FText::FromString(TEXT("CORE AUTHORITATIVE  /  ADAPTER READ ONLY"));
}

FText SFrancisPresencePanel::SequenceText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(State.Sequence > 0
        ? FString::Printf(TEXT("ENVELOPE %lld  /  AUTHENTICATED"), State.Sequence)
        : TEXT("WAITING FOR AUTHENTICATED CORE STATE"));
}

FText SFrancisPresencePanel::LocalLinkText() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    if (State.bPipeConnected) return FText::FromString(TEXT("LOCAL LINK LIVE"));
    if (State.bConfigured) return FText::FromString(TEXT("LOCAL LINK WAITING"));
    return FText::FromString(TEXT("LOCAL LINK UNCONFIGURED"));
}

FSlateColor SFrancisPresencePanel::StateColor() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    const FString Combined = (State.PresenceState + TEXT(" ") + State.SemanticState + TEXT(" ") + State.IncidentPressure).ToLower();
    if (Combined.Contains(TEXT("fault")) || Combined.Contains(TEXT("error")) || Combined.Contains(TEXT("panic")))
        return Danger;
    if (Combined.Contains(TEXT("attention")) || Combined.Contains(TEXT("blocked")) || Combined.Contains(TEXT("warning")))
        return Warning;
    if (Combined.Contains(TEXT("handoff")) || Combined.Contains(TEXT("review")))
        return Steel;
    return Live;
}

FSlateColor SFrancisPresencePanel::TransportColor() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    if (State.Status.Contains(TEXT("error")) || State.Status.Contains(TEXT("required"))) return Danger;
    return State.bPipeConnected ? Live : Warning;
}

FSlateColor SFrancisPresencePanel::PageButtonColor(EFrancisPresencePage Page) const
{
    return ActivePage == Page ? Champagne : SurfaceRaised;
}

FSlateColor SFrancisPresencePanel::PageButtonTextColor(EFrancisPresencePage Page) const
{
    return ActivePage == Page ? FLinearColor(0.08f, 0.075f, 0.06f, 1.0f) : Ink;
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
