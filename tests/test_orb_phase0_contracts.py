from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_orb_visual_lock_manifest_records_current_locked_surface() -> None:
    manifest = _read("docs/operations/ORB_VISUAL_LOCK.md")

    assert "Status: locked" in manifest
    assert "`apps/chat_ui/src/lens/orbGlyph.ts`" in manifest
    assert "`apps/chat_ui/src/App.tsx`" in manifest
    assert "`scripts/lens-overlay-window.ps1`" in manifest
    assert "core color: `#0b1220`" in manifest
    assert "ring color: `#dbe4f0`" in manifest
    assert "visual contract: `chat_ui.orbGlyph.energy_reference`" in manifest
    assert "renderer: `wpf_3d_animated_energy_orb`" in manifest
    assert "Do not change the Orb:" in manifest


def test_chat_ui_orb_glyph_visual_tokens_remain_locked() -> None:
    glyph = _read("apps/chat_ui/src/lens/orbGlyph.ts")

    assert 'const CORE_COLOR = "#0b1220";' in glyph
    assert 'const RING_COLOR = "#dbe4f0";' in glyph
    assert 'idle: { glow: "#cbd5e1", intensity: 0.55 }' in glyph
    assert 'ready: { glow: "#eaf2ff", intensity: 0.85 }' in glyph
    assert 'attention: { glow: "#fbe9cf", intensity: 0.8 }' in glyph
    assert 'active: { glow: "#ffffff", intensity: 1 }' in glyph
    assert "fetch(" not in glyph
    assert "grantsExecutionAuthority" in glyph
    assert "grantsMutationAuthority" in glyph


def test_overlay_orb_renderer_visual_constants_remain_locked() -> None:
    script = _read("scripts/lens-overlay-window.ps1")

    assert "visual_contract = 'chat_ui.orbGlyph.energy_reference'" in script
    assert "renderer = 'wpf_3d_animated_energy_orb'" in script
    assert "transparent_background = $true" in script
    assert "route = '/?francis_lens=orb_overlay'" in script
    assert "function New-OrbEnergySurface" in script
    assert "param([double]$Size = 220)" in script
    assert "$OrbSize = 220" in script
    assert "$Form.WindowStyle = [System.Windows.WindowStyle]::None" in script
    assert "$Form.AllowsTransparency = $true" in script
    assert "$Form.Background = [System.Windows.Media.Brushes]::Transparent" in script
    assert "$Form.ShowInTaskbar = $true" in script
    assert "$Form.TopMost = $true" in script
    assert "$Viewport = New-Object System.Windows.Controls.Viewport3D" in script
    assert "$Camera.Position = New-Object System.Windows.Media.Media3D.Point3D -ArgumentList 0, 0, 3.2" in script
    assert "$Camera.FieldOfView = 56" in script
    assert "for ($Index = 0; $Index -lt 38; $Index += 1)" in script
    assert "for ($Index = 0; $Index -lt 56; $Index += 1)" in script
    assert "for ($Index = 0; $Index -lt 12; $Index += 1)" in script
    assert "$OuterGlow.Width = 148" in script
    assert "$OuterGlow.Height = 148" in script
    assert "$OuterGlow.Opacity = 0.38" in script
    assert "$OuterGlow.Effect = New-Object System.Windows.Media.Effects.BlurEffect -Property @{ Radius = 16 }" in script
    assert "$Core.Width = 64" in script
    assert "$Core.Height = 64" in script
    assert "$HotCenter.Width = 34" in script
    assert "$HotCenter.Height = 34" in script


def test_orb_continuum_state_preserves_one_path_wiring_rules() -> None:
    state = _read("docs/operations/ORB_CONTINUUM_STATE.md")

    assert "## Lens-To-Overlay Wiring Rule" in state
    assert "The transparent overlay is the desktop-space host." in state
    assert "The lens is the substrate-backed observation interface" in state
    assert "Do not create a second overlay application." in state
    assert "Do not create a separate lens app." in state
    assert "## Voice-To-Orb Wiring Rule" in state
    assert "Voice enters Francis. Francis creates governed substrate state." in state
    assert "Voice must not connect ElevenLabs directly to Orb animations or desktop controls." in state
    assert "A first overlay-bound Lens observation contract exists" in state
    assert "A bounded sandbox canvas operator adapter now exists" in state
    assert "Mona Lisa mission advancement now deterministically queues the sandbox canvas" in state
    assert "A read-only Mona Lisa sandbox replay/evaluation readback now exists" in state
    assert "GET /operations/sandbox-canvas/mona-lisa/evaluation" in state
    assert "A guarded Mona Lisa sandbox evaluation recording path now exists" in state
    assert "POST /operations/sandbox-canvas/mona-lisa/evaluation/record" in state
    assert "GET /operations/sandbox-canvas/mona-lisa/evaluation-queue" in state
    assert "GET /operations/sandbox-canvas/mona-lisa/improvement-proposals" in state
    assert "Orb semantic operator state is now mapped from existing Francis substrate" in state
    assert "Acceptance criteria for the completed Orb semantic-state sub-slice" in state
    assert "Structured observation receipts now carry the Mona Lisa mission/operator" in state
    assert "Acceptance criteria for the completed structured observation receipt sub-slice" in state
    assert "Mona Lisa sandbox recognizability scoring now includes a repo-local offline" in state
    assert "Acceptance criteria for the completed offline recognizability fixture sub-slice" in state
    assert "Add replay/evaluation review scoring that can classify repeated failures" in state
