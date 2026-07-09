from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_native_orb_cpp_probe_remains_read_only_state_consumer() -> None:
    source = (_repo_root() / "native" / "orb" / "native_orb_state_probe.cpp").read_text(encoding="utf-8")

    assert "third_party/nlohmann/json.hpp" in source
    assert "validate_native_orb_state_snapshot" in source
    assert "schemas\\\\native_orb_state_snapshot.fixture.json" in source
    assert "kMaxSnapshotBytes = 64 * 1024" in source
    assert "snapshot path must stay under schemas" in source
    assert "std::ifstream" in source

    forbidden_runtime_authority = [
        "SendInput",
        "mouse_event",
        "keybd_event",
        "SetCursorPos",
        "SetWindowPos",
        "MoveWindow",
        "ShellExecute",
        "CreateProcess",
        "WinExec",
        "std::system",
        "URLDownloadToFile",
        "InternetOpen",
        "WinHttp",
        "socket(",
        "std::thread",
        "CreateThread",
    ]
    for forbidden in forbidden_runtime_authority:
        assert forbidden not in source


def test_native_orb_cpp_probe_fails_closed_on_authority_flags() -> None:
    source = (_repo_root() / "native" / "orb" / "native_orb_state_probe.cpp").read_text(encoding="utf-8")

    required_denials = [
        'expect_bool(runtime, "implemented", false)',
        'expect_bool(runtime, "active_renderer", false)',
        'expect_bool(pointer, "controls_user_os_cursor", false)',
        'expect_bool(pointer, "user_mouse_taken", false)',
        'expect_bool(authority, "native_runtime_authority", false)',
        'expect_bool(authority, "grants_execution_authority", false)',
        'expect_bool(authority, "grants_input_authority", false)',
        'expect_bool(authority, "grants_desktop_bridge_authority", false)',
        'expect_bool(authority, "can_move_user_os_cursor", false)',
        'expect_bool(authority, "can_click", false)',
        'expect_bool(authority, "can_drag", false)',
        'expect_bool(authority, "can_type", false)',
        'expect_bool(ipc, "accepts_mutation_events", false)',
        'expect_bool(events, "emits_intent_events", false)',
    ]
    for denial in required_denials:
        assert denial in source


def test_native_orb_cpp_probe_build_script_is_bounded_to_local_msvc_build() -> None:
    script = (_repo_root() / "native" / "orb" / "build-native-orb-state-probe.ps1").read_text(encoding="utf-8")

    assert "vswhere.exe" in script
    assert "VsDevCmd.bat" in script
    assert "cl.exe /nologo /std:c++17 /EHsc /W4 /permissive-" in script
    assert "native_orb_state_probe.cpp" in script
    assert "schemas\\native_orb_state_snapshot.fixture.json" in script
    assert ' /I`"$PSScriptRoot`" ' in script

    forbidden_network_or_install = [
        "Invoke-WebRequest",
        "curl",
        "wget",
        "Start-BitsTransfer",
        "Install-Module",
        "winget",
        "choco",
    ]
    for forbidden in forbidden_network_or_install:
        assert forbidden not in script


def test_native_orb_cpp_probe_vendors_pinned_json_header_with_license() -> None:
    third_party_root = _repo_root() / "native" / "orb" / "third_party" / "nlohmann"

    assert (third_party_root / "json.hpp").is_file()
    license_text = (third_party_root / "LICENSE.MIT").read_text(encoding="utf-8")

    assert "MIT License" in license_text
    assert "Niels Lohmann" in license_text
