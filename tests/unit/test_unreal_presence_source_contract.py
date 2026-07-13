from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UNREAL_SOURCE = ROOT / "apps" / "unreal_presence" / "Source" / "FrancisPresence"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_enhanced_input_uses_only_bridge_supported_governed_intents() -> None:
    controller = _read(UNREAL_SOURCE / "FrancisPresencePlayerController.cpp")
    bridge = _read(UNREAL_SOURCE / "FrancisPresenceBridge.cpp")
    controller_intents = set(re.findall(r'QueueGovernedIntent\(TEXT\("([^"]+)"\)\)', controller))

    assert controller_intents == {
        "request_context_refresh",
        "acknowledge_handback",
        "request_review",
        "request_panic_stop",
    }
    for intent in controller_intents:
        assert f'TEXT("{intent}")' in bridge
    assert "request_handoff" not in controller
    assert "request_approval_review" not in controller


def test_launcher_bounds_deletion_and_restores_process_environment() -> None:
    launcher = _read(ROOT / "scripts" / "start-unreal-presence.ps1")

    assert "function Resolve-BoundedScreenshotPath" in launcher
    assert "ScreenshotPath must name a file directly under" in launcher
    assert "Remove-Item -LiteralPath $resolvedScreenshotPath" in launcher
    assert "Remove-Item -LiteralPath ([System.IO.Path]::GetFullPath($ScreenshotPath))" not in launcher
    assert "function Get-ProcessEnvironmentSnapshot" in launcher
    assert "function Restore-ProcessEnvironment" in launcher
    assert "Restore-ProcessEnvironment -Snapshot $environmentSnapshot" in launcher
    assert '"FRANCIS_UNREAL_PRESENCE_IPC_KEY_B64"' in launcher


def test_launcher_is_transactional_and_prefers_the_repo_virtual_environment() -> None:
    launcher = _read(ROOT / "scripts" / "start-unreal-presence.ps1")

    assert '$temporaryReceipt = "$launchReceiptPath.$PID.tmp"' in launcher
    assert "$launchCommitted = $false" in launcher
    assert "Stop-OwnedProcess -Process $unrealProcess" in launcher
    assert "Stop-OwnedProcess -Process $hostProcess" in launcher
    assert "Remove-Item -LiteralPath $temporaryReceipt" in launcher
    assert 'Join-Path $repoRoot ".venv\\Scripts\\python.exe"' in launcher


def test_standard_api_wrapper_supplies_only_the_pinned_explicit_selection_path() -> None:
    wrapper = _read(ROOT / "scripts" / "francis.ps1")

    assert "$Args[0] -eq 'api'" in wrapper
    assert "apps\\unreal_presence\\Config\\francis_presence_selection.json" in wrapper
    assert "[Environment]::SetEnvironmentVariable($unrealSelectionEnv, $repoUnrealSelectionPath, 'Process')" in wrapper
    assert 'Remove-Item -LiteralPath "Env:$unrealSelectionEnv"' in wrapper


def test_operator_ui_uses_a_bounded_presence_specific_timeout() -> None:
    app = _read(ROOT / "apps" / "chat_ui" / "src" / "App.tsx")

    assert "const GROUNDED_PRESENCE_TIMEOUT_MS = 15000;" in app
    assert ".getGroundedPresence(" in app
    assert "timeoutMs: GROUNDED_PRESENCE_TIMEOUT_MS" in app


def test_native_operator_ui_has_local_frontend_backend_pages_without_new_authority() -> None:
    header = _read(UNREAL_SOURCE / "SFrancisPresencePanel.h")
    panel = _read(UNREAL_SOURCE / "SFrancisPresencePanel.cpp")
    game_mode = _read(UNREAL_SOURCE / "FrancisPresenceGameMode.cpp")

    assert "enum class EFrancisPresencePage" in header
    assert "Frontend" in header
    assert "Backend" in header
    assert "SWidgetSwitcher" in panel
    assert 'TEXT("YOUR FRANCIS")' in panel
    assert 'TEXT("BACKEND  /  SYSTEMS")' in panel
    assert 'TEXT("CORE AUTHORITATIVE  /  ADAPTER READ ONLY")' in panel
    assert "FInputModeGameAndUI" in game_mode
    assert "SetHideCursorDuringCapture(false)" in game_mode
    assert "SetWidgetToFocus(PresencePanel)" not in game_mode

    frontend_body = panel.split("FReply SFrancisPresencePanel::ShowFrontend()", 1)[1].split(
        "FReply SFrancisPresencePanel::ShowBackend()", 1
    )[0]
    backend_body = panel.split("FReply SFrancisPresencePanel::ShowBackend()", 1)[1].split(
        "FText SFrancisPresencePanel::HeadlineText()", 1
    )[0]
    assert "QueueIntent" not in frontend_body
    assert "QueueIntent" not in backend_body


def test_native_frontend_prioritizes_the_operator_decision_over_system_telemetry() -> None:
    panel = _read(UNREAL_SOURCE / "SFrancisPresencePanel.cpp")
    frontend_layout = panel.split("TSharedRef<SWidget> SFrancisPresencePanel::BuildFrontendPage()", 1)[1].split(
        "TSharedRef<SWidget> SFrancisPresencePanel::BuildBackendPage()", 1
    )[0]

    assert 'TEXT("Home")' in panel
    assert 'TEXT("Systems")' in panel
    assert 'TEXT("RECOMMENDED NEXT STEP")' in frontend_layout
    assert 'TEXT("CURRENT FOCUS")' in frontend_layout
    assert 'TEXT("Review with Francis")' in frontend_layout
    assert 'TEXT("Actions are governed requests. Francis Core remains in control.")' in frontend_layout
    assert "UserStatusTitleText" in frontend_layout
    assert "RecommendedActionTitleText" in frontend_layout
    assert "ContextConfidenceText" in frontend_layout
    assert "VoiceStatusText" not in frontend_layout
    assert "TransportStatusText" not in frontend_layout
    assert "RuntimeStatusText" not in frontend_layout
    assert "ModeStatusText" not in frontend_layout


def test_native_operator_ui_preserves_governed_intents_and_click_navigation() -> None:
    panel = _read(UNREAL_SOURCE / "SFrancisPresencePanel.cpp")

    assert ".OnClicked(this, &SFrancisPresencePanel::ShowFrontend)" in panel
    assert ".OnClicked(this, &SFrancisPresencePanel::ShowBackend)" in panel
    assert "PageSwitcher->SetActiveWidgetIndex(static_cast<int32>(ActivePage))" in panel
    assert "EKeys::F1" not in panel
    assert "EKeys::F2" not in panel
    assert 'QueueIntent(TEXT("request_context_refresh"))' in panel
    assert 'QueueIntent(TEXT("request_review"))' in panel
    assert 'QueueIntent(TEXT("acknowledge_handback"))' in panel
    assert 'QueueIntent(TEXT("request_panic_stop"))' in panel
