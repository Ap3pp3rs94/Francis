from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_native_orb_cpp_renderer_is_visible_clickthrough_readonly_window() -> None:
    source = (_repo_root() / "native" / "orb" / "native_orb_renderer.cpp").read_text(encoding="utf-8")

    assert "CreateWindowExW" in source
    assert "WS_EX_LAYERED" in source
    assert "WS_EX_TOPMOST" in source
    assert "WS_EX_NOACTIVATE" in source
    assert "HTTRANSPARENT" in source
    assert "GetAsyncKeyState(VK_RBUTTON)" in source
    assert "return HTCLIENT;" in source
    assert "UpdateLayeredWindow" in source
    assert "GdiplusStartup" in source
    assert "draw_core_sphere" in source
    assert "ProjectedOrbitPoint" in source
    assert "project_orbit_point" in source
    assert "draw_projected_energy_orbit" in source
    assert "visual_lock_3d_ring_color" in source
    assert "visual_lock_2d_orbit_color" in source
    assert "animated_angle" in source
    assert "animation_seconds_for_ring" in source
    assert "kOrbitSampleCount = 128" in source
    assert "graphics.DrawLine" in source
    assert "constexpr bool kCoreFocusOnly = true;" in source
    assert "constexpr float kOrbVisualScale = 0.34f;" in source
    assert "constexpr int kCoreFluidTrailCount = 36;" in source
    assert "constexpr int kCoreFluidTrailSamples = 72;" in source
    assert "constexpr int kSingleFlowOrbitRingSamples = 112;" in source
    assert "constexpr int kFlowGapFadeSegments = 112;" in source
    assert "constexpr int kFlowGapElectricShimmerCount = 10;" in source
    assert "constexpr int kFlowStreamerRingInstanceCount = 8;" in source
    assert "constexpr int kFineFlowStreamerRingInstanceCount = 5;" in source
    assert "constexpr int kGlowSingleFlowRingCount = 20;" in source
    assert "constexpr int kMainFlowLightStreamerCount = 7;" in source
    assert "constexpr int kFineFlowDustTrailCount = 18;" in source
    assert "deterministic_unit" in source
    assert "deterministic_range" in source
    assert "PearlescentBlobGeometry const core_blob" in source
    assert "add_pearlescent_liquid_blob_path(core_path, core_blob)" in source
    assert "draw_flow_streamer_field(graphics, core_blob, phase, blocked, false)" in source
    assert "draw_fine_flow_streamer_field(graphics, core_blob, phase, blocked, false)" in source
    assert "draw_glow_single_ring_field(graphics, core_blob, phase, blocked, false)" in source
    assert "draw_pearlescent_liquid_blob(graphics, core_blob, phase, blocked)" in source
    assert "graphics.SetClip(&core_path, Gdiplus::CombineModeReplace)" in source
    assert "draw_flow_streamer_field(graphics, core_blob, phase, blocked, true)" in source
    assert "draw_fine_flow_streamer_field(graphics, core_blob, phase, blocked, true)" in source
    assert "draw_glow_single_ring_field(graphics, core_blob, phase, blocked, true)" in source
    assert "for (int trail = 0; trail < kCoreFluidTrailCount; ++trail)" in source
    assert "for (int sample = 0; sample <= kCoreFluidTrailSamples; ++sample)" in source
    assert "draw_pearlescent_liquid_blob" in source
    assert "struct FlowStreamerInstance" in source
    assert "flow_streamer_instance" in source
    assert "for (int stream = kFlowStreamerRingInstanceCount - 1; stream >= 0; --stream)" in source
    assert (
        "draw_flow_streamer_instance(graphics, blob, phase, blocked, front_pass, flow_streamer_instance(stream))"
        in source
    )
    assert "flow_fine_streamer_instance" in source
    assert "draw_fine_flow_streamer_field" in source
    assert "draw_flow_light_streamers" in source
    assert "flow_glow_single_ring_instance" in source
    assert "draw_glowing_single_flow_ring" in source
    assert "draw_glow_single_ring_field" in source
    assert "for (int stream = kFineFlowStreamerRingInstanceCount - 1; stream >= 0; --stream)" in source
    assert (
        "draw_flow_streamer_instance(graphics, blob, phase, blocked, front_pass, flow_fine_streamer_instance(stream))"
        in source
    )
    assert "for (int stream = kGlowSingleFlowRingCount - 1; stream >= 0; --stream)" in source
    assert "FlowStreamerInstance const streamer = flow_glow_single_ring_instance(stream);" in source
    assert "draw_glowing_single_flow_ring(graphics, blob, phase, blocked, front_pass, -1.0f, streamer)" in source
    assert "draw_glowing_single_flow_ring(graphics, blob, phase, blocked, front_pass, 1.0f, streamer)" in source
    assert "flow_orbit_ring_point" in source
    assert "flow_inverted_radius_scale" in source
    assert "float radius_scale" in source
    assert "float twist_direction = 1.0f" in source
    assert "FlowStreamerInstance streamer = {}" in source
    assert "streamer.phase_offset" in source
    assert "streamer.phase_speed" in source
    assert "streamer.rotation_offset" in source
    assert "streamer.alpha_scale" in source
    assert "streamer.size_scale" in source
    assert "streamer.length_scale" in source
    assert "streamer.width_scale" in source
    assert "streamer.inner_radius_scale" in source
    assert "streamer.outer_radius_scale" in source
    assert "streamer.dust_trail_enabled" in source
    assert "streamer.pulse_offset" in source
    assert "streamer.pulse_speed" in source
    assert "streamer.pulse_depth" in source
    assert "flow_streamer_pulse" in source
    assert "flow_single_ring_identity_pulse" in source
    assert "float const slow_breath" in source
    assert "float const counter_breath" in source
    assert "float const inner_flicker" in source
    assert "float const identity_breath" in source
    assert "streamer.rotation_speed" in source
    assert "streamer.rotation_wobble" in source
    assert "streamer.rotation_wobble_speed" in source
    assert "streamer.spin_x_offset" in source
    assert "streamer.spin_y_offset" in source
    assert "streamer.spin_z_offset" in source
    assert "streamer.spin_x_speed" in source
    assert "streamer.spin_y_speed" in source
    assert "streamer.spin_z_speed" in source
    assert "streamer.flare_offset" in source
    assert "streamer.flare_speed" in source
    assert "streamer.flare_depth" in source
    assert "streamer.flare_sharpness" in source
    assert "flow_streamer_flare_scale" in source
    assert "std::pow(wave(phase + streamer.flare_offset, streamer.flare_speed, local_offset)" in source
    assert "float const size_step" in source
    assert "float const rotation_direction" in source
    assert "float const main_inner_radius_scale = 1.0f;" in source
    assert "float const main_radius_gap = 0.12f;" in source
    assert "bool const longer_streamer = stream % 3 == 0;" in source
    assert "deterministic_range(stream, 113, 0.42f, 0.82f)" in source
    assert "deterministic_range(stream, 139, 1.08f, 1.20f)" in source
    assert "deterministic_range(stream, 139, 0.90f, 0.98f)" in source
    assert "deterministic_range(stream, 159, -0.46f, 0.46f)" in source
    assert "deterministic_range(stream, 161, -0.52f, 0.52f)" in source
    assert "deterministic_range(stream, 163, -0.74f, 0.74f)" in source
    assert "deterministic_range(stream, 165, 0.045f, 0.12f)" in source
    assert "deterministic_range(stream, 167, 0.050f, 0.14f)" in source
    assert "deterministic_range(stream, 169, 0.080f, 0.18f)" in source
    assert "deterministic_range(stream, 149, 0.62f, 1.46f)" in source
    assert "randomized_fraction" in source
    assert "spin_bias" in source
    assert "bool const longer_fine_streamer = stream % 3 == 1;" in source
    assert "deterministic_range(stream, 151, 0.0f, 5.8f)" in source
    assert "deterministic_range(stream, 167, 0.46f, 0.88f)" in source
    assert "deterministic_range(stream, 173, 1.08f, 1.22f)" in source
    assert "deterministic_range(stream, 173, 1.00f, 1.12f)" in source
    assert "deterministic_range(stream, 179, 0.20f, 0.36f)" in source
    assert "float const fine_inner_radius_scale = deterministic_range(stream, 183, 1.070f, 1.095f);" in source
    assert "float const fine_radius_gap = deterministic_range(stream, 191, 0.040f, 0.060f);" in source
    assert "fine_inner_radius_scale + fine_radius_gap" in source
    assert "deterministic_range(stream, 197, 0.16f, 0.40f)" in source
    assert "deterministic_range(stream, 199, 0.30f, 0.74f)" in source
    assert "deterministic_range(stream, 211, 0.20f, 0.55f)" in source
    assert "deterministic_range(stream, 221, -0.68f, 0.68f)" in source
    assert "deterministic_range(stream, 223, -0.58f, 0.58f)" in source
    assert "deterministic_range(stream, 227, -0.92f, 0.92f)" in source
    assert "deterministic_range(stream, 229, 0.070f, 0.18f)" in source
    assert "deterministic_range(stream, 231, 0.075f, 0.20f)" in source
    assert "deterministic_range(stream, 237, 0.12f, 0.26f)" in source
    assert "deterministic_range(stream, 127, 0.060f, 0.22f)" in source
    assert "deterministic_range(stream, 137, 0.13f, 0.38f)" in source
    assert "deterministic_range(stream, 151, 0.0f, 3.8f)" in source
    assert "deterministic_range(stream, 153, 0.24f, 0.54f)" in source
    assert "deterministic_range(stream, 157, 0.11f, 0.26f)" in source
    assert "deterministic_range(stream, 213, 0.0f, 4.6f)" in source
    assert "deterministic_range(stream, 217, 0.30f, 0.68f)" in source
    assert "deterministic_range(stream, 219, 0.13f, 0.32f)" in source
    assert "float const single_spin_bias = deterministic_range(stream, 235, -1.0f, 1.0f);" in source
    assert "float const rotation_direction = single_spin_bias < 0.0f ? -1.0f : 1.0f;" in source
    assert "float const glow_radius_scale = deterministic_range(stream, 239, 1.035f, 1.330f);" in source
    assert "float const single_alpha_scale = deterministic_range(stream, 245, 0.16f, 0.42f);" in source
    assert "bool const longer_single_streamer = stream % 3 == 2;" in source
    assert "bool const flare_single_streamer = stream % 3 == 0;" in source
    assert "deterministic_range(stream, 271, 1.16f, 1.36f)" in source
    assert "deterministic_range(stream, 271, 0.98f, 1.18f)" in source
    assert "float const single_width_scale = deterministic_range(stream, 277, 0.20f, 0.46f);" in source
    assert "deterministic_range(stream, 241, 0.0f, 6.2f)" in source
    assert "deterministic_range(stream, 251, 0.16f, 0.94f)" in source
    assert "deterministic_range(stream, 257, -0.76f, 0.76f)" in source
    assert "single_alpha_scale," in source
    assert "single_length_scale," in source
    assert "single_width_scale," in source
    assert "glow_radius_scale," in source
    assert "glow_radius_scale," in source
    assert "deterministic_range(stream, 283, 0.09f, 1.05f)" in source
    assert "deterministic_range(stream, 293, 0.20f, 0.62f)" in source
    assert "deterministic_range(stream, 311, 0.12f, 0.80f)" in source
    assert "deterministic_range(stream, 313, 0.10f, 0.82f)" in source
    assert "deterministic_range(stream, 317, -0.86f, 0.86f)" in source
    assert "deterministic_range(stream, 319, -0.74f, 0.74f)" in source
    assert "deterministic_range(stream, 331, -1.08f, 1.08f)" in source
    assert "deterministic_range(stream, 337, 0.050f, 0.15f)" in source
    assert "deterministic_range(stream, 347, 0.060f, 0.18f)" in source
    assert "deterministic_range(stream, 349, 0.11f, 0.24f)" in source
    assert "deterministic_range(stream, 353, 0.0f, 7.8f)" in source
    assert "deterministic_range(stream, 359, 0.070f, 0.16f)" in source
    assert "deterministic_range(stream, 367, 0.18f, 0.34f)" in source
    assert "deterministic_range(stream, 373, 3.0f, 6.0f)" in source
    assert "std::abs(streamer.rotation_speed) * 0.63f" in source
    assert "streamer_twist" in source
    assert "signed_streamer_twist" in source
    assert "fold_depth" in source
    assert "static_cast<float>(phase * 0.30 * twist_direction)" in source
    assert "static_cast<float>(local_phase * 0.34)" in source
    assert "static_cast<float>(local_phase * 0.22)" in source
    assert "static_cast<float>(local_phase * 0.26 * twist_direction)" in source
    assert "static_cast<float>(local_phase * 0.38)" in source
    assert "static_cast<float>(local_phase * 0.42 * twist_direction)" in source
    assert "float const local_z" in source
    assert (
        "streamer.spin_x_offset + static_cast<float>(local_phase * static_cast<double>(streamer.spin_x_speed))"
        in source
    )
    assert (
        "streamer.spin_y_offset + static_cast<float>(local_phase * static_cast<double>(streamer.spin_y_speed))"
        in source
    )
    assert (
        "streamer.spin_z_offset + static_cast<float>(local_phase * static_cast<double>(streamer.spin_z_speed))"
        in source
    )
    assert "float const x_spin_y = (rotated_y * spin_x_cos) - (rotated_z * spin_x_sin);" in source
    assert "float const y_spin_x = (x_spin_x * spin_y_cos) + (x_spin_z * spin_y_sin);" in source
    assert "float const xyz_spin_x = (y_spin_x * spin_z_cos) - (y_spin_y * spin_z_sin);" in source
    assert (
        "float const normalized_z = std::clamp(xyz_spin_z / std::max(1.0f, blob.radius * 0.72f), -1.0f, 1.0f);"
        in source
    )
    assert "(streamer.inner_radius_scale + streamer.outer_radius_scale) * 0.5f" in source
    assert "(streamer.outer_radius_scale - streamer.inner_radius_scale) * 0.5f" in source
    assert "(radius_scale - ring_midline) / ring_half_span" in source
    assert "float const flare_length_scale = flow_streamer_flare_scale(local_phase, streamer, t * 0.11f);" in source
    assert (
        "float const resolved_radius_scale = flow_inverted_radius_scale(radius_scale, t, local_phase, twist_direction, streamer)"
        in source
    )
    assert (
        "blob.radius * 1.00f * resolved_radius_scale * streamer.size_scale * streamer.length_scale * flare_length_scale * liquid_edge"
        in source
    )
    assert "blob.radius * 0.86f * resolved_radius_scale * streamer.size_scale * liquid_edge" in source
    assert (
        "float const radius_span = std::max(0.01f, streamer.outer_radius_scale - streamer.inner_radius_scale);"
        in source
    )
    assert (
        "float const outer_progress = std::clamp((radius_scale - streamer.inner_radius_scale) / radius_span" in source
    )
    assert "float const inner_to_outer_width = 1.10f - (0.52f * outer_progress);" in source
    assert "BYTE const wisp_alpha" in source
    assert (
        "float const wisp_width = (front_pass ? 1.18f : 0.72f) * streamer.width_scale * inner_to_outer_width;" in source
    )
    assert (
        "float const ring_width = (front_pass ? 0.56f : 0.34f) * streamer.width_scale * inner_to_outer_width;" in source
    )
    assert "Gdiplus::Pen wisp_pen" in source
    assert "graphics.DrawLine(&wisp_pen, previous.point, current.point)" in source
    assert (
        "float const ring_pulse = flow_streamer_pulse(phase, streamer, static_cast<float>(sample) * 0.017f);" in source
    )
    assert "streamer.alpha_scale * ring_pulse" in source
    assert "float const radius_scale = streamer.inner_radius_scale;" in source
    assert (
        "float const glow_pulse = flow_single_ring_identity_pulse(phase, streamer, static_cast<float>(sample) * 0.029f);"
        in source
    )
    assert "Gdiplus::Pen glow_pen" in source
    assert "Gdiplus::Pen core_pen" in source
    assert "graphics.DrawLine(&glow_pen, previous.point, current.point)" in source
    assert "graphics.DrawLine(&core_pen, previous.point, current.point)" in source
    assert "for (int segment = 0; segment < kFlowGapFadeSegments; ++segment)" in source
    assert (
        "float const band_pulse = flow_streamer_pulse(phase, streamer, static_cast<float>(segment) * 0.031f);" in source
    )
    assert "streamer.alpha_scale * band_pulse" in source
    assert "FlowOrbitRingPoint const inner_start" in source
    assert "streamer.inner_radius_scale, twist_direction, streamer" in source
    assert "FlowOrbitRingPoint const outer_start" in source
    assert "streamer.outer_radius_scale, twist_direction, streamer" in source
    assert "bool const is_front_segment = average_z >= 0.0f" in source
    assert "rolling_fade" in source
    assert "float const smoothed_fade = 0.42f + (0.58f * rolling_fade);" in source
    assert "BYTE const edge_alpha" in source
    assert "BYTE const center_alpha" in source
    assert "Gdiplus::GraphicsPath gap_fade_path" in source
    assert "gap_fade_path.AddPolygon(gap_points, 4)" in source
    assert "Gdiplus::PathGradientBrush gap_fade_paint(&gap_fade_path)" in source
    assert "gap_fade_paint.SetCenterColor" in source
    assert "gap_fade_paint.SetSurroundColors" in source
    assert "graphics.SetPixelOffsetMode(Gdiplus::PixelOffsetModeHighQuality)" in source
    assert "for (int shimmer = 0; shimmer < kFlowGapElectricShimmerCount; ++shimmer)" in source
    assert "streamer.inner_radius_scale + (radius_gap * 0.18f)" in source
    assert "streamer.outer_radius_scale - (radius_gap * 0.18f)" in source
    assert "flow_streamer_pulse(phase, streamer, static_cast<float>(shimmer) * 0.47f)" in source
    assert "Gdiplus::GraphicsPath electric_path" in source
    assert "electric_path.AddLines(electric_points, 4)" in source
    assert "Gdiplus::Pen electric_pen" in source
    assert "electric_pen.SetLineJoin(Gdiplus::LineJoinRound)" in source
    assert "streamer.dust_trail_enabled ? kFineFlowDustTrailCount : kMainFlowLightStreamerCount" in source
    assert "float const light_streamer_visibility = streamer.dust_trail_enabled ? 1.0f : 0.24f;" in source
    assert "float const light_streamer_width = streamer.dust_trail_enabled ? 1.0f : 0.55f;" in source
    assert "for (int trail = 0; trail < light_streamer_count; ++trail)" in source
    assert (
        "float const trail_pulse = flow_streamer_pulse(phase, streamer, static_cast<float>(trail) * 0.23f);" in source
    )
    assert "streamer.alpha_scale * light_streamer_visibility" in source
    assert "light_streamer_visibility * trail_pulse" in source
    assert "(front_pass ? 0.34f : 0.22f) * light_streamer_width" in source
    assert "Gdiplus::GraphicsPath trail_path" in source
    assert "trail_path.AddLines(trail_points, 3)" in source
    assert "std::array<Gdiplus::PointF, 28>" in source
    assert "AddClosedCurve" in source
    assert "pearl_brush" in source
    assert "pearl_path" in source
    assert "alpha_color(250, 255, 255, 255)" in source
    assert "alpha_color(92, 28, 46, 72)" in source
    assert "edge_depth_path" in source
    assert "edge_depth_brush" in source
    assert "edge_depth_brush.SetCenterColor(alpha_color(0, 255, 255, 255))" in source
    assert "alpha_color(78, 12, 24, 46)" in source
    assert "center_lumen_path" in source
    assert "center_lumen_brush" in source
    assert "center_lumen_alpha" in source
    assert "center_lumen_brush.SetCenterColor" in source
    assert "lower_depth_path" in source
    assert "lower_depth_brush" in source
    assert "alpha_color(64, 12, 22, 42)" in source
    assert "for (int glint = 0; glint < 4; ++glint)" in source
    assert "glint_path" in source
    assert "glint_brush" in source
    assert "for (int strand = 0; strand < 10; ++strand)" in source
    assert "AddBezier" in source
    assert "graphics.Clear(Gdiplus::Color(0, 0, 0, 0))" in source
    assert "float const visual_size = static_cast<float>(size) * kOrbVisualScale;" in source
    assert "float const base_radius = visual_size * 0.35f;" in source
    assert "float const core_radius = visual_size * (kCoreFocusOnly ? (60.0f / 220.0f) : (32.0f / 220.0f));" in source
    assert "constexpr int kThreeDRingCount = 38;" in source
    assert "constexpr int kFineOrbitCount = 56;" in source
    assert "constexpr int kBrightOrbitCount = 12;" in source
    assert "for (int ring = 0; ring < kThreeDRingCount; ++ring)" in source
    assert "for (int index = 0; index < kFineOrbitCount; ++index)" in source
    assert "for (int index = 0; index < kBrightOrbitCount; ++index)" in source
    assert "alpha_color(alpha, 226, 238, 252)" in source
    assert "alpha_color(alpha, 224, 236, 250)" in source
    assert "schemas\\\\native_orb_state_snapshot.fixture.json" in source
    assert "kMaxSnapshotBytes = 64 * 1024" in source
    assert "snapshot path must stay under schemas" in source
    assert "draw_star_dust_orbit" not in source
    assert "draw_flowing_hue_orbit" not in source
    assert "draw_angelic_smoke_wisp" not in source
    assert "draw_visual_lock_energy_ring" not in source
    assert "draw_visual_lock_orbit" not in source
    assert "flowing_hue" not in source
    assert "angelic_smoke" not in source
    assert "DrawArc" not in source
    assert "DrawEllipse(&rim" not in source
    assert "PathGradientBrush sphere_brush" not in source
    assert "glow_path" not in source
    assert "lower_shadow" not in source
    assert "sphere_path" not in source
    assert "for (int blob = 0; blob < 9; ++blob)" not in source
    assert "Gdiplus::GraphicsPath hot_path" not in source
    assert "hot_path.AddEllipse" not in source
    assert "hot_x" not in source
    assert "hot_y" not in source
    assert "draw_transparent_white_gap_dust" not in source
    assert "mote_" not in source
    assert "dust_count" not in source
    assert "dust_brush" not in source
    assert "dot_size" not in source


def test_native_orb_cpp_renderer_fails_closed_on_authority_flags() -> None:
    source = (_repo_root() / "native" / "orb" / "native_orb_renderer.cpp").read_text(encoding="utf-8")

    required_denials = [
        'expect_bool(runtime, "implemented", true)',
        'expect_bool(runtime, "active_renderer", true)',
        'expect_string(visual_lock, "current_renderer", "native_cpp_orb_renderer")',
        'expect_bool(visual_lock, "native_renderer_active", true)',
        'expect_bool(pointer, "controls_user_os_cursor", false)',
        'expect_bool(pointer, "user_mouse_taken", false)',
        'expect_bool(pointer, "physical_input_performed", false)',
        'expect_bool(pointer, "desktop_effect_performed", false)',
        'expect_bool(authority, "native_runtime_authority", false)',
        'expect_bool(authority, "grants_execution_authority", false)',
        'expect_bool(authority, "grants_input_authority", false)',
        'expect_bool(authority, "grants_desktop_bridge_authority", false)',
        'expect_bool(authority, "can_move_user_os_cursor", false)',
        'expect_bool(authority, "can_click", false)',
        'expect_bool(authority, "can_drag", false)',
        'expect_bool(authority, "can_type", false)',
        'expect_bool(ipc, "accepts_mutation_events", false)',
    ]
    for denial in required_denials:
        assert denial in source


def test_native_orb_cpp_renderer_has_no_desktop_input_or_process_authority() -> None:
    source = (_repo_root() / "native" / "orb" / "native_orb_renderer.cpp").read_text(encoding="utf-8")

    forbidden_runtime_authority = [
        "SendInput",
        "mouse_event",
        "keybd_event",
        "SetCursorPos",
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
        "raylib.h",
        "InitWindow",
        "WindowShouldClose",
        "IsKeyPressed",
        "ExportImage",
        "LoadImageFromScreen",
        "ClearBackground(BLACK)",
    ]
    for forbidden in forbidden_runtime_authority:
        assert forbidden not in source
    assert "SetWindowPos(\n            local_ui_panel_hwnd_," in source
    assert "SetWindowPos(\n            hwnd_," not in source


def test_native_orb_cpp_renderer_accepts_bounded_move_and_contact_messages_only() -> None:
    source = (_repo_root() / "native" / "orb" / "native_orb_renderer.cpp").read_text(encoding="utf-8")

    assert "constexpr UINT kMoveCenterMessage = WM_APP + 0x46;" in source
    assert "constexpr UINT kContactPulseMessage = WM_APP + 0x47;" in source
    assert "constexpr UINT kShowLocalUiMessage = WM_APP + 0x48;" in source
    assert 'constexpr wchar_t kLocalUiWindowClassName[] = L"FrancisNativeOrbLocalUiWindow";' in source
    assert 'constexpr wchar_t kNativeRightClickRequestFile[] = L"right-click-request.json";' in source
    assert "constexpr int kLocalUiPanelWidth = 320;" in source
    assert "constexpr int kLocalUiPanelHeight = 146;" in source
    assert "case kMoveCenterMessage:" in source
    assert "case kContactPulseMessage:" in source
    assert "case kShowLocalUiMessage:" in source
    assert "case WM_RBUTTONDOWN:" in source
    assert "case WM_NCRBUTTONDOWN:" in source
    assert "case WM_CONTEXTMENU:" in source
    assert "move_center_to(message_coordinate_to_int(wparam)" in source
    assert "trigger_contact_pulse();" in source
    assert "show_local_ui_panel();" in source
    assert "request_local_ui_panel_from_right_click();" in source
    assert "void request_local_ui_panel_from_right_click()" in source
    assert "static LRESULT CALLBACK local_ui_window_proc" in source
    assert "void ensure_local_ui_panel()" in source
    assert "void show_local_ui_panel()" in source
    assert "void minimize_local_ui_panel()" in source
    assert "void paint_local_ui_panel(HWND hwnd)" in source
    assert "CreateWindowExW(" in source
    assert "kLocalUiWindowClassName" in source
    assert "kLocalUiMinimizeButtonId" in source
    assert 'DrawTextW(dc, L"Francis Local UI"' in source
    assert 'DrawTextW(\n            dc,\n            L"Native C++ panel.' in source
    assert '"francis.native_orb_renderer.right_click_request"' in source
    assert '"open_native_local_ui_panel"' in source
    assert '"minimize_native_local_ui_panel"' in source
    assert '"native_cpp_local_ui_minimize"' in source
    assert '"runtime_overlay_panel_only"' in source
    assert '"native_local_ui_panel"' in source
    assert '"native_local_ui_panel_visible"' in source
    assert '"native_local_ui_panel_minimized"' in source
    assert "MoveFileExW(temp_path.c_str(), request_path.c_str()" in source
    assert "ShellExecute" not in source
    assert "contact_pulse_started_seconds_" in source
    assert "draw_contact_press_ring" in source
    assert "target_center_x_ = static_cast<double>(center_x);" in source
    assert "target_center_y_ = static_cast<double>(center_y);" in source
    assert "SetTimer(hwnd_, 1, 8, nullptr);" in source
    assert "void update_motion(double elapsed)" in source
    assert "1.0 - std::exp(-9.0 * delta_seconds)" in source
    assert "delta_seconds * 4.0" in source
    assert "delta_seconds * 5.0" in source
    assert "0.060f" in source
    assert "target_heading_degrees_ = normalize_degrees" in source
    assert "shortest_angle_delta_degrees(heading_degrees_, target_heading_degrees_)" in source
    assert "spin_degrees_ = normalize_degrees" in source
    assert "OrbMotionKinetics{" in source
    assert "float const travel_phase_degrees" in source
    assert "kinetics.heading_degrees * travel_strength * 0.18f" in source
    assert "kinetics.spin_degrees * 0.16f" in source
    assert "graphics.RotateTransform(travel_spin)" not in source
    assert "HTTRANSPARENT" in source


def test_native_orb_cpp_renderer_build_script_is_local_only() -> None:
    script = (_repo_root() / "native" / "orb" / "build-native-orb-renderer.ps1").read_text(encoding="utf-8")

    assert "vswhere.exe" in script
    assert "VsDevCmd.bat" in script
    assert "native_orb_renderer.cpp" in script
    assert "cl.exe /nologo /std:c++17 /EHsc /W4 /permissive-" in script
    assert "gdiplus.lib user32.lib gdi32.lib shell32.lib" in script
    assert "/SUBSYSTEM:WINDOWS" in script
    assert "Start-Process" in script
    assert "schemas\\native_orb_state_snapshot.fixture.json" in script
    assert "[int]$Size = 270" in script
    assert "[int]$X = -1" in script
    assert "[int]$Y = -1" in script
    assert '[string]$RuntimeDir = ""' in script
    assert '"--x", [string]$X' in script
    assert '"--y", [string]$Y' in script
    assert '"--runtime-dir", $runtimeDir' in script
    assert "data\\runtime\\native-orb-renderer" in script
    assert "native-orb-renderer.pid" in script
    assert "right-click-request.json" in script
    assert "native_right_click_request_supported = $true" in script
    assert "can_open_backend_surface_directly = $false" in script
    assert "right_click_opens_local_ui_panel = $true" in script
    assert "native_local_ui_panel_supported = $true" in script
    assert 'native_local_ui_panel_open_mode = "native_cpp_panel"' in script
    assert "francis.native_orb_renderer.runtime_status" in script
    assert "native_cpp_orb_renderer" in script
    assert "active_renderer = $true" in script
    assert "authority_granted = $false" in script
    assert "accepts_mutation_events = $false" in script
    assert "controls_user_os_cursor = $false" in script
    assert "can_click = $false" in script
    assert "can_drag = $false" in script
    assert "can_type = $false" in script
    assert 'liveness_truth = "launcher_pid_observation_only"' in script
    assert "runtime_status_path = $statusPath" in script
    assert "pid_path = $pidPath" in script

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
