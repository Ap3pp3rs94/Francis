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
                    .Text(FText::FromString(TEXT("YOUR LOCAL WORKSPACE")))
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
                    .Text(FText::FromString(TEXT("Home")))
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
                    .Text(FText::FromString(TEXT("Systems")))
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
    const FSlateFontInfo DisplayFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 36);
    const FSlateFontInfo HeadingFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 23);
    const FSlateFontInfo FocusFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 17);
    const FSlateFontInfo BodyFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 14);
    const FSlateFontInfo FocusBodyFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 12);
    const FSlateFontInfo SmallFont = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 10);
    const FSlateFontInfo ButtonFont = FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 11);
    const FLinearColor PrimaryButtonFill(0.18f, 0.15f, 0.09f, 1.0f);

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
                    .Text(FText::FromString(TEXT("YOUR FRANCIS")))
                    .Font(EyebrowFont)
                    .ColorAndOpacity(Champagne)
                ]
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 4.0f, 0.0f, 0.0f)
                [
                    SNew(STextBlock)
                    .Text(this, &SFrancisPresencePanel::UserStatusTitleText)
                    .Font(DisplayFont)
                    .ColorAndOpacity(Ink)
                    .AutoWrapText(true)
                    .WrapTextAt(780.0f)
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
            + SHorizontalBox::Slot().AutoWidth().Padding(24.0f, 0.0f, 0.0f, 0.0f).VAlign(VAlign_Bottom)
            [
                SNew(SBorder)
                .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                .BorderBackgroundColor(SurfaceRaised)
                .Padding(FMargin(14.0f, 9.0f))
                [
                    SNew(STextBlock)
                    .Text(this, &SFrancisPresencePanel::UserStatusLabelText)
                    .Font(EyebrowFont)
                    .ColorAndOpacity(this, &SFrancisPresencePanel::StateColor)
                ]
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
            + SHorizontalBox::Slot().FillWidth(0.64f).Padding(0.0f, 0.0f, 9.0f, 0.0f)
            [
                SNew(SBorder)
                .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                .BorderBackgroundColor(Surface)
                .Padding(FMargin(24.0f, 20.0f))
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(STextBlock)
                        .Text(FText::FromString(TEXT("RECOMMENDED NEXT STEP")))
                        .Font(SmallFont)
                        .ColorAndOpacity(Steel)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 8.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock)
                        .Text(this, &SFrancisPresencePanel::RecommendedActionTitleText)
                        .Font(HeadingFont)
                        .ColorAndOpacity(Ink)
                        .AutoWrapText(true)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 10.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock)
                        .Text(this, &SFrancisPresencePanel::NextStepText)
                        .Font(BodyFont)
                        .ColorAndOpacity(FLinearColor(0.72f, 0.75f, 0.76f, 1.0f))
                        .AutoWrapText(true)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 16.0f, 0.0f, 0.0f)
                    [
                        SNew(SHorizontalBox)
                        + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 8.0f, 0.0f)
                        [
                            SNew(SButton)
                            .ContentPadding(FMargin(18.0f, 9.0f))
                            .ButtonColorAndOpacity(PrimaryButtonFill)
                            .OnClicked(this, &SFrancisPresencePanel::RequestReview)
                            [
                                SNew(STextBlock)
                                .Text(FText::FromString(TEXT("Review with Francis")))
                                .Font(ButtonFont)
                                .ColorAndOpacity(Ink)
                            ]
                        ]
                        + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 8.0f, 0.0f)
                        [
                            SNew(SButton)
                            .ContentPadding(FMargin(14.0f, 9.0f))
                            .ButtonColorAndOpacity(SurfaceRaised)
                            .OnClicked(this, &SFrancisPresencePanel::RequestContextRefresh)
                            [SNew(STextBlock).Text(FText::FromString(TEXT("Refresh briefing"))).Font(ButtonFont).ColorAndOpacity(Ink)]
                        ]
                        + SHorizontalBox::Slot().AutoWidth()
                        [
                            SNew(SButton)
                            .ContentPadding(FMargin(14.0f, 9.0f))
                            .ButtonColorAndOpacity(SurfaceRaised)
                            .OnClicked(this, &SFrancisPresencePanel::AcknowledgeHandback)
                            [SNew(STextBlock).Text(FText::FromString(TEXT("Hand back"))).Font(ButtonFont).ColorAndOpacity(Ink)]
                        ]
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 14.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock)
                        .Text(this, &SFrancisPresencePanel::UserTrustLineText)
                        .Font(SmallFont)
                        .ColorAndOpacity(Muted)
                    ]
                ]
            ]
            + SHorizontalBox::Slot().FillWidth(0.36f).Padding(9.0f, 0.0f, 0.0f, 0.0f)
            [
                SNew(SBorder)
                .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                .BorderBackgroundColor(Surface)
                .Padding(FMargin(22.0f, 20.0f))
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(STextBlock).Text(FText::FromString(TEXT("CURRENT FOCUS"))).Font(SmallFont).ColorAndOpacity(Steel)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 9.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock)
                        .Text(this, &SFrancisPresencePanel::FocusTitleText)
                        .Font(FocusFont)
                        .ColorAndOpacity(Ink)
                        .AutoWrapText(true)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 9.0f, 0.0f, 0.0f)
                    [
                        SNew(STextBlock)
                        .Text(this, &SFrancisPresencePanel::FocusText)
                        .Font(FocusBodyFont)
                        .ColorAndOpacity(Muted)
                        .AutoWrapText(true)
                    ]
                    + SVerticalBox::Slot().FillHeight(1.0f)
                    [
                        SNew(SSpacer)
                    ]
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(STextBlock)
                        .Text(this, &SFrancisPresencePanel::ContextConfidenceText)
                        .Font(SmallFont)
                        .ColorAndOpacity(this, &SFrancisPresencePanel::StateColor)
                        .AutoWrapText(true)
                    ]
                ]
            ]
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        .Padding(0.0f, 14.0f, 0.0f, 0.0f)
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
            [
                SNew(STextBlock)
                .Text(FText::FromString(TEXT("Actions are governed requests. Francis Core remains in control.")))
                .Font(SmallFont)
                .ColorAndOpacity(Muted)
            ]
            + SHorizontalBox::Slot().FillWidth(1.0f)
            [
                SNew(SSpacer)
            ]
            + SHorizontalBox::Slot().AutoWidth()
            [
                SNew(SButton).ContentPadding(FMargin(14.0f, 7.0f)).ButtonColorAndOpacity(FLinearColor(0.22f, 0.08f, 0.07f, 1.0f))
                .OnClicked(this, &SFrancisPresencePanel::RequestPanicStop)
                [SNew(STextBlock).Text(FText::FromString(TEXT("Request emergency stop"))).Font(ButtonFont).ColorAndOpacity(FLinearColor(0.95f, 0.70f, 0.65f, 1.0f))]
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

FText SFrancisPresencePanel::UserStatusTitleText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    const FString Combined =
        (State.PresenceState + TEXT(" ") + State.SemanticState + TEXT(" ") + State.HandbackState).ToLower();
    if (!State.bAuthenticated) return FText::FromString(TEXT("Francis is getting ready"));
    if (Combined.Contains(TEXT("fault")) || Combined.Contains(TEXT("error")) || Combined.Contains(TEXT("panic")))
        return FText::FromString(TEXT("Francis needs your attention"));
    if (State.bApprovalRequired || Combined.Contains(TEXT("blocked")) || Combined.Contains(TEXT("attention")))
        return FText::FromString(TEXT("A decision is waiting for you"));
    if (Combined.Contains(TEXT("handback")) || Combined.Contains(TEXT("handoff")))
        return FText::FromString(TEXT("Francis is ready to hand back"));
    if (Combined.Contains(TEXT("review"))) return FText::FromString(TEXT("A review is ready for you"));
    if (Combined.Contains(TEXT("idle")) || Combined.Contains(TEXT("ready")))
        return FText::FromString(TEXT("Everything is steady"));
    return FText::FromString(TEXT("Here is what matters now"));
}

FText SFrancisPresencePanel::UserStatusLabelText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    const FString Combined =
        (State.PresenceState + TEXT(" ") + State.SemanticState + TEXT(" ") + State.HandbackState).ToLower();
    if (!State.bAuthenticated) return FText::FromString(TEXT("CONNECTING"));
    if (Combined.Contains(TEXT("fault")) || Combined.Contains(TEXT("error")) || Combined.Contains(TEXT("panic")))
        return FText::FromString(TEXT("ACTION REQUIRED"));
    if (State.bApprovalRequired || Combined.Contains(TEXT("blocked")) || Combined.Contains(TEXT("attention")))
        return FText::FromString(TEXT("WAITING FOR YOU"));
    if (Combined.Contains(TEXT("handback")) || Combined.Contains(TEXT("handoff")))
        return FText::FromString(TEXT("HANDOFF READY"));
    if (Combined.Contains(TEXT("idle")) || Combined.Contains(TEXT("ready")))
        return FText::FromString(TEXT("ALL CLEAR"));
    return FText::FromString(TEXT("ACTIVE"));
}

FText SFrancisPresencePanel::FocusText() const
{
    if (!Bridge) return FText::GetEmpty();
    const FFrancisPresenceViewModel State = Bridge->GetViewModel();
    if (State.FocusObjective.IsEmpty() || State.FocusObjective.Equals(State.FocusTitle))
    {
        return FText::GetEmpty();
    }
    return FText::FromString(State.FocusObjective);
}

FText SFrancisPresencePanel::FocusTitleText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    return FText::FromString(State.FocusTitle.IsEmpty() ? TEXT("Current priority") : State.FocusTitle);
}

FText SFrancisPresencePanel::NextStepText() const
{
    if (!Bridge) return FText::GetEmpty();
    const FString Next = Bridge->GetViewModel().NextStep;
    return FText::FromString(Next.IsEmpty() ? TEXT("No grounded next step is available yet.") : Next);
}

FText SFrancisPresencePanel::RecommendedActionTitleText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    const FString Handback = State.HandbackState.ToLower();
    const FString Evidence = State.EvidenceStatus.ToLower();
    const FString Stage = State.StageStatus.ToLower();
    if (!State.bAuthenticated) return FText::FromString(TEXT("Wait for Francis to finish connecting"));
    if (State.bApprovalRequired) return FText::FromString(TEXT("Review before Francis continues"));
    if (Handback.Contains(TEXT("operator_action_required")) || Handback.Contains(TEXT("handback")))
        return FText::FromString(TEXT("Take the handback"));
    if (Evidence.Contains(TEXT("blocked")) || Evidence.Contains(TEXT("missing")))
        return FText::FromString(TEXT("Review the missing context"));
    if (Stage.Contains(TEXT("blocked"))) return FText::FromString(TEXT("Resolve the current blocker"));
    if (!State.NextStep.IsEmpty()) return FText::FromString(TEXT("Continue with the next step"));
    return FText::FromString(TEXT("Refresh your briefing"));
}

FText SFrancisPresencePanel::ContextConfidenceText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    const FString Evidence = State.EvidenceStatus.ToLower();
    const FString Freshness = State.FreshnessStatus.ToLower();
    if (!State.bAuthenticated) return FText::FromString(TEXT("CONTEXT  /  CONNECTING"));
    if (Freshness.Contains(TEXT("stale"))) return FText::FromString(TEXT("CONTEXT  /  MAY BE OUT OF DATE"));
    if (Evidence.Contains(TEXT("blocked")) || Evidence.Contains(TEXT("missing")))
        return FText::FromString(TEXT("CONTEXT  /  NEEDS REVIEW"));
    if (State.bTruthful && State.bReceiptLinked)
        return FText::FromString(TEXT("CONTEXT  /  GROUNDED AND RECEIPT LINKED"));
    if (State.bTruthful) return FText::FromString(TEXT("CONTEXT  /  GROUNDED"));
    return FText::FromString(TEXT("CONTEXT  /  OBSERVED LOCALLY"));
}

FText SFrancisPresencePanel::UserTrustLineText() const
{
    const FFrancisPresenceViewModel State = Bridge ? Bridge->GetViewModel() : FFrancisPresenceViewModel();
    const FFrancisPresenceBridgeReadback Runtime = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    if (State.bAuthenticated && State.bRuntimeObserved)
        return FText::FromString(TEXT("Authenticated local state  /  Updated from Francis Core"));
    if (State.bAuthenticated)
        return FText::FromString(TEXT("Authenticated local state  /  Runtime observation pending"));
    if (Runtime.bConfigured)
        return FText::FromString(TEXT("Local connection configured  /  Waiting for authenticated state"));
    return FText::FromString(TEXT("Local connection is not configured"));
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
        ? FString::Printf(TEXT("AUTHENTICATED  /  UPDATE %lld"), State.Sequence)
        : TEXT("WAITING FOR AUTHENTICATED STATE"));
}

FText SFrancisPresencePanel::LocalLinkText() const
{
    const FFrancisPresenceBridgeReadback State = Bridge ? Bridge->GetReadback() : FFrancisPresenceBridgeReadback();
    if (State.bPipeConnected) return FText::FromString(TEXT("LOCAL CONNECTION ACTIVE"));
    if (State.bConfigured && State.AcceptedMessageCount > 0)
        return FText::FromString(TEXT("LOCAL CONNECTION READY"));
    if (State.bConfigured) return FText::FromString(TEXT("LOCAL CONNECTION STARTING"));
    return FText::FromString(TEXT("LOCAL CONNECTION UNCONFIGURED"));
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
    return ActivePage == Page ? FLinearColor(0.18f, 0.15f, 0.09f, 1.0f) : SurfaceRaised;
}

FSlateColor SFrancisPresencePanel::PageButtonTextColor(EFrancisPresencePage Page) const
{
    return ActivePage == Page ? Champagne : Ink;
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
