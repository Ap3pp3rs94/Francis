#include "third_party/nlohmann/json.hpp"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objidl.h>
#include <olectl.h>
#pragma warning(push)
#pragma warning(disable : 4458)
#include <gdiplus.h>
#pragma warning(pop)
#include <shellapi.h>

#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>

namespace fs = std::filesystem;
using Json = nlohmann::json;

namespace {

constexpr wchar_t kWindowClassName[] = L"FrancisNativeOrbRendererWindow";
constexpr wchar_t kDefaultSnapshotPath[] = L"schemas\\native_orb_state_snapshot.fixture.json";
constexpr std::uintmax_t kMaxSnapshotBytes = 64 * 1024;
constexpr int kDefaultOrbSize = 270;
constexpr int kMinOrbSize = 160;
constexpr int kMaxOrbSize = 360;
constexpr int kDefaultRunSeconds = 600;
constexpr int kMinRunSeconds = 0;
constexpr int kMaxRunSeconds = 3600;
constexpr UINT kMoveCenterMessage = WM_APP + 0x46;
constexpr double kPi = 3.14159265358979323846;
constexpr int kThreeDRingCount = 38;
constexpr int kFineOrbitCount = 56;
constexpr int kBrightOrbitCount = 12;
constexpr int kOrbitSampleCount = 128;
constexpr bool kCoreFocusOnly = true;
constexpr float kOrbVisualScale = 0.34f;
constexpr int kCoreFluidTrailCount = 36;
constexpr int kCoreFluidTrailSamples = 72;
constexpr int kSingleFlowOrbitRingSamples = 112;
constexpr int kFlowGapFadeSegments = 112;
constexpr int kFlowGapElectricShimmerCount = 10;
constexpr int kFlowStreamerRingInstanceCount = 15;
constexpr int kFineFlowStreamerRingInstanceCount = 5;
constexpr int kGlowSingleFlowRingCount = 20;
constexpr int kMainFlowLightStreamerCount = 7;
constexpr int kFineFlowDustTrailCount = 18;

struct OrbState {
    std::string feedback_state = "idle";
    std::string posture = "ambient_rest";
    bool pointer_available = false;
    int pointer_x = 0;
    int pointer_y = 0;
    bool unsafe_source_flags_denied = false;
};

struct RendererConfig {
    fs::path snapshot_path = fs::path(kDefaultSnapshotPath);
    int run_seconds = kDefaultRunSeconds;
    int size = kDefaultOrbSize;
    int x = -1;
    int y = -1;
};

[[noreturn]] void fail(std::string const& message) {
    throw std::runtime_error(message);
}

bool is_component(fs::path const& path, wchar_t const* expected) {
    return path.wstring() == expected;
}

int parse_int(std::wstring const& value, char const* name, int min_value, int max_value) {
    try {
        std::size_t consumed = 0;
        int parsed = std::stoi(value, &consumed);
        if (consumed != value.size()) {
            fail(std::string("invalid integer for ") + name);
        }
        return std::clamp(parsed, min_value, max_value);
    } catch (std::exception const&) {
        fail(std::string("invalid integer for ") + name);
    }
}

int message_coordinate_to_int(WPARAM value) {
    LONG_PTR const signed_value = static_cast<LONG_PTR>(value);
    return std::clamp(static_cast<int>(signed_value), -32767, 32767);
}

fs::path bounded_snapshot_path(fs::path const& candidate) {
    if (candidate.empty()) {
        fail("snapshot path is empty");
    }
    if (candidate.is_absolute()) {
        fail("snapshot path must be repo-relative");
    }

    fs::path normalized = candidate.lexically_normal();
    if (normalized.empty()) {
        fail("snapshot path is invalid");
    }

    bool saw_first_component = false;
    for (auto const& component : normalized) {
        if (component == L".." || component == L"." || component.empty()) {
            fail("snapshot path must not contain traversal components");
        }
        if (!saw_first_component) {
            if (!is_component(component, L"schemas")) {
                fail("snapshot path must stay under schemas");
            }
            saw_first_component = true;
        }
    }

    if (normalized.extension() != L".json") {
        fail("snapshot path must be a JSON file");
    }
    return normalized;
}

RendererConfig parse_args(int argc, wchar_t** argv) {
    RendererConfig config;
    for (int index = 1; index < argc; ++index) {
        std::wstring arg = argv[index];
        if (arg == L"--snapshot") {
            if (++index >= argc) {
                fail("--snapshot requires a value");
            }
            config.snapshot_path = bounded_snapshot_path(fs::path(argv[index]));
        } else if (arg == L"--run-seconds") {
            if (++index >= argc) {
                fail("--run-seconds requires a value");
            }
            config.run_seconds = parse_int(argv[index], "run-seconds", kMinRunSeconds, kMaxRunSeconds);
        } else if (arg == L"--size") {
            if (++index >= argc) {
                fail("--size requires a value");
            }
            config.size = parse_int(argv[index], "size", kMinOrbSize, kMaxOrbSize);
        } else if (arg == L"--x") {
            if (++index >= argc) {
                fail("--x requires a value");
            }
            config.x = parse_int(argv[index], "x", 0, 32767);
        } else if (arg == L"--y") {
            if (++index >= argc) {
                fail("--y requires a value");
            }
            config.y = parse_int(argv[index], "y", 0, 32767);
        } else if (arg == L"--help" || arg == L"-h") {
            fail("usage: native_orb_renderer.exe [--snapshot schemas/native_orb_state_snapshot.fixture.json] [--run-seconds 600] [--size 220] [--x 120] [--y 120]");
        } else {
            config.snapshot_path = bounded_snapshot_path(fs::path(arg));
        }
    }
    config.snapshot_path = bounded_snapshot_path(config.snapshot_path);
    return config;
}

std::string read_snapshot(fs::path const& snapshot_path) {
    std::error_code ec;
    std::uintmax_t const size = fs::file_size(snapshot_path, ec);
    if (ec) {
        fail("snapshot file could not be read");
    }
    if (size > kMaxSnapshotBytes) {
        fail("snapshot file exceeds bounded read limit");
    }

    std::ifstream input(snapshot_path, std::ios::binary);
    if (!input) {
        fail("snapshot file could not be opened");
    }

    std::string bytes;
    bytes.resize(static_cast<std::size_t>(size));
    input.read(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    if (!input && !input.eof()) {
        fail("snapshot file could not be fully read");
    }
    return bytes;
}

Json const& require_object(Json const& object, char const* key) {
    auto const item = object.find(key);
    if (item == object.end() || !item->is_object()) {
        fail("missing required object");
    }
    return *item;
}

std::string require_string(Json const& object, char const* key) {
    auto const item = object.find(key);
    if (item == object.end() || !item->is_string()) {
        fail("missing required string");
    }
    return item->get<std::string>();
}

bool require_bool(Json const& object, char const* key) {
    auto const item = object.find(key);
    if (item == object.end() || !item->is_boolean()) {
        fail("missing required boolean");
    }
    return item->get<bool>();
}

int optional_int(Json const& object, char const* key, int fallback) {
    auto const item = object.find(key);
    if (item == object.end() || item->is_null()) {
        return fallback;
    }
    if (!item->is_number_integer()) {
        return fallback;
    }
    return item->get<int>();
}

void expect_string(Json const& object, char const* key, char const* expected) {
    if (require_string(object, key) != expected) {
        fail(std::string("unexpected string for ") + key);
    }
}

void expect_bool(Json const& object, char const* key, bool expected) {
    if (require_bool(object, key) != expected) {
        fail(std::string("unexpected boolean for ") + key);
    }
}

OrbState load_orb_state(fs::path const& snapshot_path) {
    Json const root = Json::parse(read_snapshot(snapshot_path));
    expect_string(root, "kind", "francis.native_orb.state_snapshot");
    expect_string(root, "schema_version", "francis.native_orb.state_snapshot.v1");

    Json const& runtime = require_object(root, "runtime_contract");
    expect_string(runtime, "native_runtime", "cpp");
    expect_bool(runtime, "implemented", true);
    expect_bool(runtime, "active_renderer", true);
    expect_bool(runtime, "body_renderer_only", true);
    expect_bool(runtime, "francis_core_remains_authority", true);

    Json const& visual_lock = require_object(root, "visual_lock");
    expect_bool(visual_lock, "parity_required", true);
    expect_bool(visual_lock, "redesign_allowed", false);
    expect_string(visual_lock, "current_renderer", "native_cpp_orb_renderer");
    expect_bool(visual_lock, "native_renderer_active", true);

    Json const& pointer = require_object(root, "virtual_pointer");
    expect_bool(pointer, "controls_user_os_cursor", false);
    expect_bool(pointer, "user_mouse_taken", false);
    expect_bool(pointer, "physical_input_performed", false);
    expect_bool(pointer, "desktop_effect_performed", false);
    expect_bool(pointer, "presentation_only", true);

    Json const& authority = require_object(root, "authority");
    expect_bool(authority, "read_only", true);
    expect_bool(authority, "render_only", true);
    expect_bool(authority, "native_runtime_authority", false);
    expect_bool(authority, "grants_execution_authority", false);
    expect_bool(authority, "grants_input_authority", false);
    expect_bool(authority, "grants_desktop_bridge_authority", false);
    expect_bool(authority, "can_move_user_os_cursor", false);
    expect_bool(authority, "can_click", false);
    expect_bool(authority, "can_drag", false);
    expect_bool(authority, "can_type", false);
    expect_bool(authority, "can_enable_desktop_bridge", false);
    expect_bool(authority, "can_persist_memory", false);
    expect_bool(authority, "can_train_model", false);

    Json const& ipc = require_object(root, "ipc");
    expect_string(ipc, "event_channel", "not_implemented");
    expect_bool(ipc, "accepts_mutation_events", false);

    Json const& render_state = require_object(root, "render_state");
    OrbState state;
    state.feedback_state = require_string(render_state, "feedback_state");
    state.posture = require_string(render_state, "posture");
    state.pointer_available = require_bool(pointer, "available");
    state.pointer_x = optional_int(pointer, "x", 0);
    state.pointer_y = optional_int(pointer, "y", 0);
    state.unsafe_source_flags_denied = require_bool(authority, "unsafe_source_flags_denied");
    return state;
}

ULONG_PTR start_gdiplus() {
    Gdiplus::GdiplusStartupInput input;
    ULONG_PTR token = 0;
    if (Gdiplus::GdiplusStartup(&token, &input, nullptr) != Gdiplus::Ok) {
        fail("GDI+ startup failed");
    }
    return token;
}

Gdiplus::Color alpha_color(BYTE alpha, BYTE red, BYTE green, BYTE blue) {
    return Gdiplus::Color(alpha, red, green, blue);
}

float wave(double phase, double speed, double offset = 0.0) {
    return static_cast<float>((std::sin((phase * speed) + offset) + 1.0) * 0.5);
}

BYTE byte_clamp(float value) {
    return static_cast<BYTE>(std::clamp(value, 0.0f, 255.0f));
}

float deterministic_unit(int index, int salt) {
    std::uint32_t value = static_cast<std::uint32_t>(index + 1) * 747796405u;
    value ^= static_cast<std::uint32_t>(salt + 17) * 2891336453u;
    value = ((value >> ((value >> 28u) + 4u)) ^ value) * 277803737u;
    value = (value >> 22u) ^ value;
    return static_cast<float>(value & 0x00FFFFFFu) / static_cast<float>(0x00FFFFFFu);
}

float deterministic_range(int index, int salt, float min_value, float max_value) {
    return min_value + ((max_value - min_value) * deterministic_unit(index, salt));
}

float animation_seconds_for_ring(int index) {
    return static_cast<float>(12 + ((index * 5) % 27));
}

float animated_angle(double phase, int index, float base_angle, float seconds, bool reverse) {
    float const direction = reverse ? -1.0f : 1.0f;
    float const degrees = static_cast<float>(std::fmod((phase / seconds) * 360.0, 360.0));
    return base_angle + (direction * degrees) + static_cast<float>(std::sin((phase * 0.42) + index) * 2.8);
}

Gdiplus::Color visual_lock_3d_ring_color(BYTE alpha, bool blocked) {
    return blocked ? alpha_color(alpha, 255, 210, 150) : alpha_color(alpha, 226, 238, 252);
}

Gdiplus::Color visual_lock_2d_orbit_color(BYTE alpha, bool blocked) {
    return blocked ? alpha_color(alpha, 255, 226, 188) : alpha_color(alpha, 224, 236, 250);
}

struct ProjectedOrbitPoint {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

struct PearlescentBlobGeometry {
    float x = 0.0f;
    float y = 0.0f;
    float radius = 0.0f;
    std::array<Gdiplus::PointF, 28> points{};
};

struct FlowOrbitRingPoint {
    Gdiplus::PointF point{};
    float z = 0.0f;
};

struct FlowStreamerInstance {
    double phase_offset = 0.0;
    double phase_speed = 1.0;
    float rotation_offset = 0.0f;
    float alpha_scale = 1.0f;
    float size_scale = 1.0f;
    float length_scale = 1.0f;
    float width_scale = 1.0f;
    float inner_radius_scale = 1.0f;
    float outer_radius_scale = 1.12f;
    bool dust_trail_enabled = false;
    float pulse_offset = 0.0f;
    float pulse_speed = 0.42f;
    float pulse_depth = 0.20f;
    float rotation_speed = 0.18f;
    float rotation_wobble = 0.22f;
    float rotation_wobble_speed = 0.37f;
};

float flow_streamer_pulse(double phase, FlowStreamerInstance const& streamer, float local_offset = 0.0f) {
    return 1.0f - streamer.pulse_depth + (streamer.pulse_depth * wave(phase + streamer.pulse_offset, streamer.pulse_speed, local_offset));
}

float flow_single_ring_identity_pulse(double phase, FlowStreamerInstance const& streamer, float local_offset = 0.0f) {
    float const slow_breath = wave(phase + streamer.phase_offset, streamer.pulse_speed, streamer.pulse_offset + local_offset);
    float const counter_breath = wave(
        phase + streamer.phase_offset,
        streamer.rotation_wobble_speed + (std::abs(streamer.rotation_speed) * 0.63f),
        streamer.rotation_offset + (local_offset * 0.37f));
    float const inner_flicker =
        wave(phase + streamer.pulse_offset, streamer.phase_speed * 0.41, streamer.rotation_wobble + (local_offset * 0.19f));
    float const identity_breath = (slow_breath * 0.58f) + (counter_breath * 0.30f) + (inner_flicker * 0.12f);
    return 1.0f - streamer.pulse_depth + (streamer.pulse_depth * identity_breath);
}

float radians(float degrees) {
    return degrees * static_cast<float>(kPi / 180.0);
}

ProjectedOrbitPoint project_orbit_point(
    float center,
    float radius,
    float y_scale,
    float yaw_degrees,
    float pitch_degrees,
    float roll_degrees,
    float theta) {
    float const x0 = std::cos(theta) * radius;
    float const y0 = std::sin(theta) * radius * y_scale;
    float const z0 = 0.0f;

    float const pitch = radians(pitch_degrees);
    float const pitch_cos = std::cos(pitch);
    float const pitch_sin = std::sin(pitch);
    float const y1 = (y0 * pitch_cos) - (z0 * pitch_sin);
    float const z1 = (y0 * pitch_sin) + (z0 * pitch_cos);

    float const yaw = radians(yaw_degrees);
    float const yaw_cos = std::cos(yaw);
    float const yaw_sin = std::sin(yaw);
    float const x2 = (x0 * yaw_cos) + (z1 * yaw_sin);
    float const z2 = (-x0 * yaw_sin) + (z1 * yaw_cos);

    float const roll = radians(roll_degrees);
    float const roll_cos = std::cos(roll);
    float const roll_sin = std::sin(roll);
    float const x3 = (x2 * roll_cos) - (y1 * roll_sin);
    float const y3 = (x2 * roll_sin) + (y1 * roll_cos);

    float const camera_distance = center * 3.35f;
    float const perspective = camera_distance / std::max(1.0f, camera_distance - z2);
    return {
        center + (x3 * perspective),
        center + (y3 * perspective),
        z2,
    };
}

void draw_projected_energy_orbit(
    Gdiplus::Graphics& graphics,
    float center,
    float radius,
    float y_scale,
    float yaw_degrees,
    float pitch_degrees,
    float roll_degrees,
    double phase,
    int index,
    BYTE alpha,
    float stroke_width,
    bool blocked,
    bool front_pass,
    bool orbit_color) {
    float const seconds = animation_seconds_for_ring(index);
    float const animated_roll = animated_angle(phase, index, roll_degrees, seconds, index % 2 != 0);
    float const animated_yaw = yaw_degrees + static_cast<float>(std::sin((phase * 0.18) + index) * 4.8);
    float const animated_pitch = pitch_degrees + static_cast<float>(std::cos((phase * 0.16) + index) * 3.6);
    float const trace_phase = static_cast<float>(phase * (0.34 + (static_cast<double>(index % 7) * 0.013)));

    for (int sample = 0; sample < kOrbitSampleCount; ++sample) {
        float const theta0 = ((static_cast<float>(sample) / static_cast<float>(kOrbitSampleCount)) * 2.0f * static_cast<float>(kPi)) + trace_phase;
        float const theta1 =
            ((static_cast<float>(sample + 1) / static_cast<float>(kOrbitSampleCount)) * 2.0f * static_cast<float>(kPi)) +
            trace_phase;
        ProjectedOrbitPoint const a =
            project_orbit_point(center, radius, y_scale, animated_yaw, animated_pitch, animated_roll, theta0);
        ProjectedOrbitPoint const b =
            project_orbit_point(center, radius, y_scale, animated_yaw, animated_pitch, animated_roll, theta1);
        float const average_z = (a.z + b.z) * 0.5f;
        if (front_pass != (average_z >= 0.0f)) {
            continue;
        }

        float const depth = std::clamp((average_z / std::max(1.0f, radius) + 1.0f) * 0.5f, 0.0f, 1.0f);
        float const shimmer = wave(phase, 0.8 + (index * 0.01), theta0 + index);
        BYTE const segment_alpha =
            byte_clamp(static_cast<float>(alpha) * ((front_pass ? 0.52f : 0.18f) + (0.58f * depth)) * (0.74f + (0.26f * shimmer)));
        float const segment_width = stroke_width * ((front_pass ? 0.92f : 0.52f) + (0.62f * depth));
        Gdiplus::Pen trace_pen(
            orbit_color ? visual_lock_2d_orbit_color(segment_alpha, blocked) : visual_lock_3d_ring_color(segment_alpha, blocked),
            segment_width);
        trace_pen.SetStartCap(Gdiplus::LineCapRound);
        trace_pen.SetEndCap(Gdiplus::LineCapRound);
        graphics.DrawLine(&trace_pen, a.x, a.y, b.x, b.y);
    }
}

PearlescentBlobGeometry pearlescent_liquid_blob_geometry(
    float center,
    float core_radius,
    float pulse,
    double phase) {
    float const blob_x = center + static_cast<float>(std::sin(phase * 0.67 + 0.4) * core_radius * 0.18f) +
                         static_cast<float>(std::sin(phase * 1.13 + 2.1) * core_radius * 0.05f);
    float const blob_y = center + static_cast<float>(std::cos(phase * 0.59 + 1.6) * core_radius * 0.16f) +
                         static_cast<float>(std::sin(phase * 0.91 + 0.8) * core_radius * 0.04f);
    float const blob_radius = core_radius * (0.78f + (0.07f * pulse));

    PearlescentBlobGeometry blob{};
    blob.x = blob_x;
    blob.y = blob_y;
    blob.radius = blob_radius;
    for (int point = 0; point < static_cast<int>(blob.points.size()); ++point) {
        float const t = (static_cast<float>(point) / static_cast<float>(blob.points.size())) * 2.0f * static_cast<float>(kPi);
        float const liquid_edge =
            1.0f + (0.052f * std::sin((t * 3.0f) + static_cast<float>(phase * 0.74))) +
            (0.034f * std::cos((t * 5.0f) - static_cast<float>(phase * 0.51))) +
            (0.018f * std::sin((t * 7.0f) + static_cast<float>(phase * 0.37)));
        float const squash_x = 1.01f + (0.044f * std::sin(static_cast<float>(phase * 0.43)));
        float const squash_y = 0.97f + (0.046f * std::cos(static_cast<float>(phase * 0.49)));
        blob.points[static_cast<size_t>(point)] = Gdiplus::PointF(
            blob_x + (std::cos(t) * blob_radius * liquid_edge * squash_x),
            blob_y + (std::sin(t) * blob_radius * liquid_edge * squash_y));
    }
    return blob;
}

void add_pearlescent_liquid_blob_path(Gdiplus::GraphicsPath& pearl_path, PearlescentBlobGeometry const& blob) {
    pearl_path.AddClosedCurve(blob.points.data(), static_cast<INT>(blob.points.size()), 0.46f);
}

void draw_pearlescent_liquid_blob(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked) {
    Gdiplus::GraphicsPath pearl_path;
    add_pearlescent_liquid_blob_path(pearl_path, blob);
    Gdiplus::PathGradientBrush pearl_brush(&pearl_path);
    float const highlight_x = blob.x + static_cast<float>(std::sin(phase * 0.97 + 0.2) * blob.radius * 0.18f);
    float const highlight_y = blob.y + static_cast<float>(std::cos(phase * 0.89 + 1.4) * blob.radius * 0.16f);
    pearl_brush.SetCenterPoint(Gdiplus::PointF(highlight_x, highlight_y));
    pearl_brush.SetCenterColor(blocked ? alpha_color(236, 255, 246, 224) : alpha_color(250, 255, 255, 255));
    Gdiplus::Color pearl_surround[] = {
        blocked ? alpha_color(88, 98, 58, 40) : alpha_color(92, 28, 46, 72),
    };
    int pearl_surround_count = 1;
    pearl_brush.SetSurroundColors(pearl_surround, &pearl_surround_count);
    graphics.FillPath(&pearl_brush, &pearl_path);

    Gdiplus::GraphicsState pearl_clip = graphics.Save();
    graphics.SetClip(&pearl_path, Gdiplus::CombineModeReplace);

    Gdiplus::GraphicsPath edge_depth_path;
    add_pearlescent_liquid_blob_path(edge_depth_path, blob);
    Gdiplus::PathGradientBrush edge_depth_brush(&edge_depth_path);
    edge_depth_brush.SetCenterPoint(Gdiplus::PointF(highlight_x, highlight_y));
    edge_depth_brush.SetCenterColor(alpha_color(0, 255, 255, 255));
    Gdiplus::Color edge_depth_surround[] = {
        blocked ? alpha_color(70, 82, 42, 30) : alpha_color(78, 12, 24, 46),
    };
    int edge_depth_surround_count = 1;
    edge_depth_brush.SetSurroundColors(edge_depth_surround, &edge_depth_surround_count);
    graphics.FillPath(&edge_depth_brush, &edge_depth_path);

    Gdiplus::GraphicsPath center_lumen_path;
    float const center_lumen_radius_x = blob.radius * 0.46f;
    float const center_lumen_radius_y = blob.radius * 0.36f;
    center_lumen_path.AddEllipse(
        highlight_x - center_lumen_radius_x,
        highlight_y - center_lumen_radius_y,
        center_lumen_radius_x * 2.0f,
        center_lumen_radius_y * 2.0f);
    Gdiplus::PathGradientBrush center_lumen_brush(&center_lumen_path);
    center_lumen_brush.SetCenterPoint(Gdiplus::PointF(highlight_x, highlight_y));
    BYTE const center_lumen_alpha = byte_clamp(160.0f + (58.0f * wave(phase, 0.72, 0.18f)));
    center_lumen_brush.SetCenterColor(blocked ? alpha_color(center_lumen_alpha, 255, 244, 220) : alpha_color(center_lumen_alpha, 255, 255, 255));
    Gdiplus::Color center_lumen_surround[] = {alpha_color(0, 255, 255, 255)};
    int center_lumen_surround_count = 1;
    center_lumen_brush.SetSurroundColors(center_lumen_surround, &center_lumen_surround_count);
    graphics.FillPath(&center_lumen_brush, &center_lumen_path);

    Gdiplus::GraphicsPath lower_depth_path;
    float const depth_radius_x = blob.radius * 0.92f;
    float const depth_radius_y = blob.radius * 0.46f;
    lower_depth_path.AddEllipse(
        blob.x - depth_radius_x,
        blob.y + (blob.radius * 0.13f),
        depth_radius_x * 2.0f,
        depth_radius_y * 2.0f);
    Gdiplus::PathGradientBrush lower_depth_brush(&lower_depth_path);
    lower_depth_brush.SetCenterPoint(Gdiplus::PointF(blob.x, blob.y + (blob.radius * 0.40f)));
    lower_depth_brush.SetCenterColor(blocked ? alpha_color(62, 88, 48, 34) : alpha_color(64, 12, 22, 42));
    Gdiplus::Color depth_surround[] = {alpha_color(0, 12, 22, 42)};
    int depth_surround_count = 1;
    lower_depth_brush.SetSurroundColors(depth_surround, &depth_surround_count);
    graphics.FillPath(&lower_depth_brush, &lower_depth_path);

    for (int glint = 0; glint < 4; ++glint) {
        float const seed = static_cast<float>(glint);
        float const glint_x = blob.x + static_cast<float>(std::sin(phase * (0.61 + (glint * 0.07)) + seed) * blob.radius * 0.22f);
        float const glint_y =
            blob.y + static_cast<float>(std::cos(phase * (0.55 + (glint * 0.05)) + seed * 1.7f) * blob.radius * 0.18f);
        float const glint_radius = blob.radius * (0.075f + (0.045f * wave(phase, 0.67 + (glint * 0.04), seed)));
        Gdiplus::GraphicsPath glint_path;
        glint_path.AddEllipse(glint_x - glint_radius, glint_y - glint_radius, glint_radius * 2.0f, glint_radius * 2.0f);
        Gdiplus::PathGradientBrush glint_brush(&glint_path);
        glint_brush.SetCenterPoint(Gdiplus::PointF(glint_x, glint_y));
        BYTE const glint_alpha = byte_clamp(80.0f + (80.0f * wave(phase, 0.78 + (glint * 0.03), seed)));
        glint_brush.SetCenterColor(blocked ? alpha_color(glint_alpha, 255, 239, 214) : alpha_color(glint_alpha, 255, 255, 255));
        Gdiplus::Color glint_surround[] = {alpha_color(0, 255, 255, 255)};
        int glint_surround_count = 1;
        glint_brush.SetSurroundColors(glint_surround, &glint_surround_count);
        graphics.FillPath(&glint_brush, &glint_path);
    }

    for (int vein = 0; vein < 6; ++vein) {
        float const seed = static_cast<float>(vein);
        float const sweep = static_cast<float>(phase * (0.31 + (vein * 0.025)) + seed);
        float const x0 = blob.x + (std::sin(sweep) * blob.radius * 0.80f);
        float const y0 = blob.y + (std::cos(sweep * 0.72f + 0.5f) * blob.radius * 0.56f);
        float const x3 = blob.x + (std::cos(sweep * 0.88f + 1.3f) * blob.radius * 0.76f);
        float const y3 = blob.y + (std::sin(sweep * 0.83f + 0.9f) * blob.radius * 0.54f);
        float const x1 = blob.x + (std::sin(sweep * 1.23f + 0.6f) * blob.radius * 0.20f);
        float const y1 = blob.y + (std::cos(sweep * 1.17f + 1.0f) * blob.radius * 0.22f);
        float const x2 = blob.x + (std::cos(sweep * 1.19f + 2.1f) * blob.radius * 0.24f);
        float const y2 = blob.y + (std::sin(sweep * 1.11f + 1.8f) * blob.radius * 0.24f);
        Gdiplus::GraphicsPath vein_path;
        vein_path.AddBezier(x0, y0, x1, y1, x2, y2, x3, y3);
        BYTE const vein_alpha = byte_clamp(22.0f + (52.0f * wave(phase, 0.49 + (vein * 0.03), seed)));
        Gdiplus::Pen vein_pen(
            blocked ? alpha_color(vein_alpha, 255, 232, 204) : alpha_color(vein_alpha, 245, 250, 255),
            0.7f + (0.45f * wave(phase, 0.39, seed)));
        vein_pen.SetStartCap(Gdiplus::LineCapRound);
        vein_pen.SetEndCap(Gdiplus::LineCapRound);
        graphics.DrawPath(&vein_pen, &vein_path);
    }
    graphics.Restore(pearl_clip);
}

float flow_inverted_radius_scale(
    float radius_scale,
    float t,
    double phase,
    float twist_direction,
    FlowStreamerInstance const& streamer) {
    float const ring_midline = (streamer.inner_radius_scale + streamer.outer_radius_scale) * 0.5f;
    float const ring_half_span = std::max(0.01f, (streamer.outer_radius_scale - streamer.inner_radius_scale) * 0.5f);
    float const side = std::clamp((radius_scale - ring_midline) / ring_half_span, -1.0f, 1.0f);
    float const inversion = std::cos((t * 2.0f * twist_direction) + static_cast<float>(phase * 0.30 * twist_direction));
    return ring_midline + (ring_half_span * side * inversion);
}

FlowStreamerInstance flow_streamer_instance(int stream) {
    float const fraction = static_cast<float>(stream) / static_cast<float>(kFlowStreamerRingInstanceCount);
    float const size_step =
        static_cast<float>((stream * 7) % kFlowStreamerRingInstanceCount) / static_cast<float>(kFlowStreamerRingInstanceCount - 1);
    float const rotation_direction = stream % 2 == 0 ? 1.0f : -1.0f;
    float const main_inner_radius_scale = 1.0f;
    float const main_radius_gap = 0.12f;
    bool const longer_streamer = stream % 3 == 0;
    return {
        static_cast<double>(stream) * 0.43,
        static_cast<double>(deterministic_range(stream, 113, 0.42f, 0.82f)),
        (2.0f * static_cast<float>(kPi) * fraction) + deterministic_range(stream, 107, -0.18f, 0.18f),
        stream == 0 ? 0.88f : deterministic_range(stream, 109, 0.28f, 0.52f),
        0.78f + (0.42f * size_step) + deterministic_range(stream, 111, -0.014f, 0.014f),
        longer_streamer ? deterministic_range(stream, 139, 1.18f, 1.32f) : deterministic_range(stream, 139, 0.96f, 1.06f),
        deterministic_range(stream, 149, 0.62f, 1.46f),
        main_inner_radius_scale,
        main_inner_radius_scale + main_radius_gap,
        false,
        deterministic_range(stream, 151, 0.0f, 3.8f),
        deterministic_range(stream, 153, 0.24f, 0.54f),
        deterministic_range(stream, 157, 0.11f, 0.26f),
        rotation_direction * deterministic_range(stream, 127, 0.060f, 0.22f),
        deterministic_range(stream, 131, 0.10f, 0.36f),
        deterministic_range(stream, 137, 0.13f, 0.38f),
    };
}

FlowStreamerInstance flow_fine_streamer_instance(int stream) {
    float const randomized_fraction =
        std::fmod((static_cast<float>(stream) * 0.618034f) + deterministic_range(stream, 157, 0.0f, 0.44f), 1.0f);
    float const spin_bias = deterministic_range(stream, 193, -1.0f, 1.0f);
    float const rotation_direction = spin_bias < 0.0f ? -1.0f : 1.0f;
    float const fine_inner_radius_scale = deterministic_range(stream, 183, 1.070f, 1.095f);
    float const fine_radius_gap = deterministic_range(stream, 191, 0.040f, 0.060f);
    return {
        static_cast<double>(deterministic_range(stream, 151, 0.0f, 5.8f)),
        static_cast<double>(deterministic_range(stream, 167, 0.46f, 0.88f)),
        (2.0f * static_cast<float>(kPi) * randomized_fraction) + deterministic_range(stream, 171, -0.36f, 0.36f),
        deterministic_range(stream, 163, 0.24f, 0.40f),
        deterministic_range(stream, 181, 0.86f, 1.06f),
        deterministic_range(stream, 173, 1.38f, 1.56f),
        deterministic_range(stream, 179, 0.20f, 0.36f),
        fine_inner_radius_scale,
        fine_inner_radius_scale + fine_radius_gap,
        true,
        deterministic_range(stream, 213, 0.0f, 4.6f),
        deterministic_range(stream, 217, 0.30f, 0.68f),
        deterministic_range(stream, 219, 0.13f, 0.32f),
        rotation_direction * deterministic_range(stream, 197, 0.16f, 0.40f),
        deterministic_range(stream, 199, 0.30f, 0.74f),
        deterministic_range(stream, 211, 0.20f, 0.55f),
    };
}

FlowStreamerInstance flow_glow_single_ring_instance(int stream) {
    float const randomized_fraction =
        std::fmod((static_cast<float>(stream) * 0.381966f) + deterministic_range(stream, 233, 0.0f, 0.74f), 1.0f);
    float const single_spin_bias = deterministic_range(stream, 235, -1.0f, 1.0f);
    float const rotation_direction = single_spin_bias < 0.0f ? -1.0f : 1.0f;
    float const glow_radius_scale = deterministic_range(stream, 239, 1.035f, 1.330f);
    float const single_alpha_scale = deterministic_range(stream, 245, 0.16f, 0.42f);
    float const single_length_scale = deterministic_range(stream, 271, 1.32f, 1.94f);
    float const single_width_scale = deterministic_range(stream, 277, 0.18f, 0.52f);
    return {
        static_cast<double>(deterministic_range(stream, 241, 0.0f, 6.2f)),
        static_cast<double>(deterministic_range(stream, 251, 0.16f, 0.94f)),
        (2.0f * static_cast<float>(kPi) * randomized_fraction) + deterministic_range(stream, 257, -0.76f, 0.76f),
        single_alpha_scale,
        deterministic_range(stream, 269, 0.86f, 1.14f),
        single_length_scale,
        single_width_scale,
        glow_radius_scale,
        glow_radius_scale,
        false,
        deterministic_range(stream, 281, 0.0f, 5.6f),
        deterministic_range(stream, 283, 0.09f, 1.05f),
        deterministic_range(stream, 293, 0.20f, 0.62f),
        rotation_direction * deterministic_range(stream, 307, 0.07f, 0.32f),
        deterministic_range(stream, 311, 0.12f, 0.80f),
        deterministic_range(stream, 313, 0.10f, 0.82f),
    };
}

FlowOrbitRingPoint flow_orbit_ring_point(
    PearlescentBlobGeometry const& blob,
    double phase,
    int sample,
    float radius_scale,
    float twist_direction = 1.0f,
    FlowStreamerInstance streamer = {}) {
    double const local_phase = (phase * streamer.phase_speed) + streamer.phase_offset;
    float const t =
        (static_cast<float>(sample) / static_cast<float>(kSingleFlowOrbitRingSamples)) * 2.0f * static_cast<float>(kPi);
    float const streamer_twist =
        (0.30f * std::sin((t * 2.0f) + static_cast<float>(local_phase * 0.34))) +
        (0.14f * std::sin((t * 5.0f) - static_cast<float>(local_phase * 0.22)));
    float const signed_streamer_twist = streamer_twist * twist_direction;
    float const resolved_radius_scale = flow_inverted_radius_scale(radius_scale, t, local_phase, twist_direction, streamer);
    float const orbit =
        (t * twist_direction) + static_cast<float>(local_phase * 0.26 * twist_direction) +
        (signed_streamer_twist * (0.62f + (0.38f * resolved_radius_scale)));
    float const liquid_edge =
        1.0f + (0.040f * std::sin((t * 3.0f) + static_cast<float>(local_phase * 0.38))) +
        (0.026f * std::cos((t * 5.0f) - static_cast<float>(local_phase * 0.26))) +
        (0.014f * std::sin((t * 7.0f) + static_cast<float>(local_phase * 0.19)));
    float const ring_radius_x = blob.radius * 1.26f * resolved_radius_scale * streamer.size_scale * streamer.length_scale * liquid_edge;
    float const ring_radius_y = blob.radius * 0.52f * resolved_radius_scale * streamer.size_scale * liquid_edge;
    float const fold_depth =
        std::clamp(
            std::sin(orbit) +
                (0.38f * std::sin((t * 2.0f * twist_direction) + static_cast<float>(local_phase * 0.42 * twist_direction))),
            -1.0f,
            1.0f);
    float const perspective = 0.88f + (0.12f * ((fold_depth + 1.0f) * 0.5f));
    float const local_x =
        (std::cos(orbit) * ring_radius_x) + (std::sin((t * 2.0f) + static_cast<float>(local_phase * 0.22)) * blob.radius * 0.025f) +
        (fold_depth * blob.radius * 0.050f * streamer.size_scale * (resolved_radius_scale - 0.86f));
    float const local_y =
        (std::sin(orbit) * ring_radius_y) + (std::cos((t * 2.4f) - static_cast<float>(local_phase * 0.18)) * blob.radius * 0.018f) +
        (signed_streamer_twist * blob.radius * 0.038f * streamer.size_scale * resolved_radius_scale);
    float const rotation =
        static_cast<float>(local_phase * static_cast<double>(streamer.rotation_speed)) +
        (streamer.rotation_wobble * std::sin(static_cast<float>(local_phase * static_cast<double>(streamer.rotation_wobble_speed)))) +
        streamer.rotation_offset;
    float const rotation_cos = std::cos(rotation);
    float const rotation_sin = std::sin(rotation);

    return {
        Gdiplus::PointF(
            blob.x + (((local_x * rotation_cos) - (local_y * rotation_sin)) * perspective),
            blob.y + (((local_x * rotation_sin) + (local_y * rotation_cos)) * perspective)),
        fold_depth,
    };
}

void draw_single_flow_orbit_ring(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked,
    bool front_pass,
    float radius_scale,
    float twist_direction = 1.0f,
    FlowStreamerInstance streamer = {}) {
    FlowOrbitRingPoint previous = flow_orbit_ring_point(blob, phase, 0, radius_scale, twist_direction, streamer);
    for (int sample = 1; sample <= kSingleFlowOrbitRingSamples; ++sample) {
        FlowOrbitRingPoint const current = flow_orbit_ring_point(blob, phase, sample, radius_scale, twist_direction, streamer);
        float const average_z = (previous.z + current.z) * 0.5f;
        bool const is_front_segment = average_z >= 0.0f;
        if (is_front_segment == front_pass) {
            float const depth = std::clamp((average_z + 1.0f) * 0.5f, 0.0f, 1.0f);
            float const ring_pulse = flow_streamer_pulse(phase, streamer, static_cast<float>(sample) * 0.017f);
            BYTE const ring_alpha =
                byte_clamp((front_pass ? 126.0f : 58.0f) * (0.72f + (0.28f * depth)) * streamer.alpha_scale * ring_pulse);
            float const radius_span = std::max(0.01f, streamer.outer_radius_scale - streamer.inner_radius_scale);
            float const outer_progress = std::clamp((radius_scale - streamer.inner_radius_scale) / radius_span, 0.0f, 1.0f);
            float const inner_to_outer_width = 1.10f - (0.52f * outer_progress);
            BYTE const wisp_alpha =
                byte_clamp((front_pass ? 44.0f : 18.0f) * (0.62f + (0.38f * depth)) * streamer.alpha_scale * ring_pulse);
            float const wisp_width = (front_pass ? 1.18f : 0.72f) * streamer.width_scale * inner_to_outer_width;
            float const ring_width = (front_pass ? 0.56f : 0.34f) * streamer.width_scale * inner_to_outer_width;
            Gdiplus::Pen wisp_pen(
                blocked ? alpha_color(wisp_alpha, 255, 232, 204) : alpha_color(wisp_alpha, 218, 238, 255),
                wisp_width);
            Gdiplus::Pen ring_pen(
                blocked ? alpha_color(ring_alpha, 255, 230, 196) : alpha_color(ring_alpha, 230, 244, 255),
                ring_width);
            wisp_pen.SetStartCap(Gdiplus::LineCapRound);
            wisp_pen.SetEndCap(Gdiplus::LineCapRound);
            ring_pen.SetStartCap(Gdiplus::LineCapRound);
            ring_pen.SetEndCap(Gdiplus::LineCapRound);
            graphics.DrawLine(&wisp_pen, previous.point, current.point);
            graphics.DrawLine(&ring_pen, previous.point, current.point);
        }
        previous = current;
    }
}

void draw_wavy_transparent_gap_fade(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked,
    bool front_pass,
    float twist_direction = 1.0f,
    FlowStreamerInstance streamer = {}) {
    for (int segment = 0; segment < kFlowGapFadeSegments; ++segment) {
        FlowOrbitRingPoint const inner_start =
            flow_orbit_ring_point(blob, phase, segment, streamer.inner_radius_scale, twist_direction, streamer);
        FlowOrbitRingPoint const inner_end =
            flow_orbit_ring_point(blob, phase, segment + 1, streamer.inner_radius_scale, twist_direction, streamer);
        FlowOrbitRingPoint const outer_end =
            flow_orbit_ring_point(blob, phase, segment + 1, streamer.outer_radius_scale, twist_direction, streamer);
        FlowOrbitRingPoint const outer_start =
            flow_orbit_ring_point(blob, phase, segment, streamer.outer_radius_scale, twist_direction, streamer);
        float const average_z = (inner_start.z + inner_end.z + outer_end.z + outer_start.z) * 0.25f;
        bool const is_front_segment = average_z >= 0.0f;
        if (is_front_segment != front_pass) {
            continue;
        }
        float const depth = std::clamp((average_z + 1.0f) * 0.5f, 0.0f, 1.0f);
        float const band_pulse = flow_streamer_pulse(phase, streamer, static_cast<float>(segment) * 0.031f);
        float const rolling_fade =
            wave(phase + streamer.phase_offset, 0.34 * twist_direction, static_cast<float>(segment) * 0.11f) *
            wave(phase + streamer.phase_offset, 0.19 * twist_direction, static_cast<float>(segment) * 0.27f);
        BYTE const fade_alpha =
            byte_clamp(
                (front_pass ? 44.0f : 19.0f) * (0.20f + (0.80f * rolling_fade)) * (0.62f + (0.38f * depth)) *
                streamer.alpha_scale * band_pulse);

        Gdiplus::PointF gap_points[] = {
            inner_start.point,
            inner_end.point,
            outer_end.point,
            outer_start.point,
        };
        Gdiplus::GraphicsPath gap_fade_path;
        gap_fade_path.AddPolygon(gap_points, 4);
        Gdiplus::SolidBrush gap_fade_paint(
            blocked ? alpha_color(fade_alpha, 255, 236, 210) : alpha_color(fade_alpha, 255, 255, 255));
        graphics.FillPath(&gap_fade_paint, &gap_fade_path);
    }
}

void draw_gap_electric_shimmer(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked,
    bool front_pass,
    float twist_direction = 1.0f,
    FlowStreamerInstance streamer = {}) {
    for (int shimmer = 0; shimmer < kFlowGapElectricShimmerCount; ++shimmer) {
        int const start_sample =
            (shimmer * 11 + static_cast<int>(deterministic_range(shimmer, 89, 0.0f, 8.0f))) % kSingleFlowOrbitRingSamples;
        float const radius_gap = std::max(0.02f, streamer.outer_radius_scale - streamer.inner_radius_scale);
        float const shimmer_radius =
            deterministic_range(shimmer, 97, streamer.inner_radius_scale + (radius_gap * 0.18f), streamer.outer_radius_scale - (radius_gap * 0.18f));
        float const radius_spark = deterministic_range(shimmer, 101, radius_gap * 0.18f, radius_gap * 0.38f);
        FlowOrbitRingPoint const spark_a = flow_orbit_ring_point(blob, phase, start_sample, shimmer_radius, twist_direction, streamer);
        FlowOrbitRingPoint const spark_b =
            flow_orbit_ring_point(blob, phase, start_sample + 1, shimmer_radius + radius_spark, twist_direction, streamer);
        FlowOrbitRingPoint const spark_c =
            flow_orbit_ring_point(blob, phase, start_sample + 3, shimmer_radius - (radius_spark * 0.65f), twist_direction, streamer);
        FlowOrbitRingPoint const spark_d =
            flow_orbit_ring_point(blob, phase, start_sample + 4, shimmer_radius + (radius_spark * 0.35f), twist_direction, streamer);
        float const average_z = (spark_a.z + spark_b.z + spark_c.z + spark_d.z) * 0.25f;
        bool const is_front_segment = average_z >= 0.0f;
        if (is_front_segment != front_pass) {
            continue;
        }

        float const depth = std::clamp((average_z + 1.0f) * 0.5f, 0.0f, 1.0f);
        float const pulse =
            wave(phase + streamer.phase_offset, 1.18 * twist_direction, static_cast<float>(shimmer) * 1.31f) *
            flow_streamer_pulse(phase, streamer, static_cast<float>(shimmer) * 0.47f);
        BYTE const electric_alpha =
            byte_clamp(
                (front_pass ? 108.0f : 48.0f) * (0.30f + (0.70f * pulse)) * (0.62f + (0.38f * depth)) *
                streamer.alpha_scale);
        Gdiplus::PointF electric_points[] = {
            spark_a.point,
            spark_b.point,
            spark_c.point,
            spark_d.point,
        };
        Gdiplus::GraphicsPath electric_path;
        electric_path.AddLines(electric_points, 4);
        Gdiplus::Pen electric_pen(
            blocked ? alpha_color(electric_alpha, 255, 238, 210) : alpha_color(electric_alpha, 255, 255, 255),
            front_pass ? 0.72f : 0.46f);
        electric_pen.SetStartCap(Gdiplus::LineCapRound);
        electric_pen.SetEndCap(Gdiplus::LineCapRound);
        electric_pen.SetLineJoin(Gdiplus::LineJoinRound);
        graphics.DrawPath(&electric_pen, &electric_path);
    }
}

void draw_flow_light_streamers(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked,
    bool front_pass,
    float twist_direction = 1.0f,
    FlowStreamerInstance streamer = {}) {
    int const light_streamer_count = streamer.dust_trail_enabled ? kFineFlowDustTrailCount : kMainFlowLightStreamerCount;
    float const light_streamer_visibility = streamer.dust_trail_enabled ? 1.0f : 0.24f;
    float const light_streamer_width = streamer.dust_trail_enabled ? 1.0f : 0.55f;

    for (int trail = 0; trail < light_streamer_count; ++trail) {
        int const start_sample =
            (trail * 9 + static_cast<int>(deterministic_range(trail, 203, 0.0f, 11.0f))) % kSingleFlowOrbitRingSamples;
        int const mid_sample = start_sample - static_cast<int>(deterministic_range(trail, 207, 3.0f, 7.0f));
        int const tail_sample = start_sample - static_cast<int>(deterministic_range(trail, 211, 7.0f, 14.0f));
        float const radius_gap = std::max(0.02f, streamer.outer_radius_scale - streamer.inner_radius_scale);
        float const head_radius = deterministic_range(
            trail,
            223,
            streamer.inner_radius_scale + (radius_gap * 0.16f),
            streamer.outer_radius_scale - (radius_gap * 0.10f));
        float const mid_radius =
            head_radius + (radius_gap * deterministic_range(trail, 227, -0.20f, 0.18f));
        float const tail_radius =
            head_radius + (radius_gap * deterministic_range(trail, 229, -0.28f, 0.24f));

        FlowOrbitRingPoint const head =
            flow_orbit_ring_point(blob, phase, start_sample, head_radius, twist_direction, streamer);
        FlowOrbitRingPoint const mid = flow_orbit_ring_point(blob, phase, mid_sample, mid_radius, twist_direction, streamer);
        FlowOrbitRingPoint const tail =
            flow_orbit_ring_point(blob, phase, tail_sample, tail_radius, twist_direction, streamer);
        float const average_z = (head.z + mid.z + tail.z) / 3.0f;
        bool const is_front_segment = average_z >= 0.0f;
        if (is_front_segment != front_pass) {
            continue;
        }

        float const depth = std::clamp((average_z + 1.0f) * 0.5f, 0.0f, 1.0f);
        float const trail_pulse = flow_streamer_pulse(phase, streamer, static_cast<float>(trail) * 0.23f);
        float const streamer_wave =
            wave(phase + streamer.phase_offset, 0.27 * twist_direction, static_cast<float>(trail) * 0.37f) *
            wave(phase + streamer.phase_offset, 0.43 * twist_direction, static_cast<float>(trail) * 0.19f);
        BYTE const trail_alpha = byte_clamp(
            (front_pass ? 64.0f : 29.0f) * (0.18f + (0.82f * streamer_wave)) * (0.56f + (0.44f * depth)) *
            streamer.alpha_scale * light_streamer_visibility * trail_pulse);
        Gdiplus::PointF trail_points[] = {
            head.point,
            mid.point,
            tail.point,
        };
        Gdiplus::GraphicsPath trail_path;
        trail_path.AddLines(trail_points, 3);
        Gdiplus::Pen trail_pen(
            blocked ? alpha_color(trail_alpha, 255, 236, 210) : alpha_color(trail_alpha, 255, 255, 255),
            (front_pass ? 0.34f : 0.22f) * light_streamer_width);
        trail_pen.SetStartCap(Gdiplus::LineCapRound);
        trail_pen.SetEndCap(Gdiplus::LineCapRound);
        trail_pen.SetLineJoin(Gdiplus::LineJoinRound);
        graphics.DrawPath(&trail_pen, &trail_path);
    }
}

void draw_glowing_single_flow_ring(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked,
    bool front_pass,
    float twist_direction = 1.0f,
    FlowStreamerInstance streamer = {}) {
    float const radius_scale = streamer.inner_radius_scale;
    FlowOrbitRingPoint previous = flow_orbit_ring_point(blob, phase, 0, radius_scale, twist_direction, streamer);
    for (int sample = 1; sample <= kSingleFlowOrbitRingSamples; ++sample) {
        FlowOrbitRingPoint const current = flow_orbit_ring_point(blob, phase, sample, radius_scale, twist_direction, streamer);
        float const average_z = (previous.z + current.z) * 0.5f;
        bool const is_front_segment = average_z >= 0.0f;
        if (is_front_segment == front_pass) {
            float const depth = std::clamp((average_z + 1.0f) * 0.5f, 0.0f, 1.0f);
            float const glow_pulse = flow_single_ring_identity_pulse(phase, streamer, static_cast<float>(sample) * 0.029f);
            BYTE const glow_alpha =
                byte_clamp((front_pass ? 92.0f : 36.0f) * (0.56f + (0.44f * depth)) * streamer.alpha_scale * glow_pulse);
            BYTE const core_alpha =
                byte_clamp((front_pass ? 156.0f : 68.0f) * (0.62f + (0.38f * depth)) * streamer.alpha_scale * glow_pulse);
            Gdiplus::Pen glow_pen(
                blocked ? alpha_color(glow_alpha, 255, 234, 208) : alpha_color(glow_alpha, 226, 244, 255),
                (front_pass ? 1.35f : 0.82f) * streamer.width_scale);
            Gdiplus::Pen core_pen(
                blocked ? alpha_color(core_alpha, 255, 244, 224) : alpha_color(core_alpha, 255, 255, 255),
                (front_pass ? 0.54f : 0.34f) * streamer.width_scale);
            glow_pen.SetStartCap(Gdiplus::LineCapRound);
            glow_pen.SetEndCap(Gdiplus::LineCapRound);
            core_pen.SetStartCap(Gdiplus::LineCapRound);
            core_pen.SetEndCap(Gdiplus::LineCapRound);
            graphics.DrawLine(&glow_pen, previous.point, current.point);
            graphics.DrawLine(&core_pen, previous.point, current.point);
        }
        previous = current;
    }
}

void draw_flow_streamer_instance(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked,
    bool front_pass,
    FlowStreamerInstance streamer) {
    if (front_pass) {
        draw_wavy_transparent_gap_fade(graphics, blob, phase, blocked, true, -1.0f, streamer);
        draw_gap_electric_shimmer(graphics, blob, phase, blocked, true, -1.0f, streamer);
        draw_flow_light_streamers(graphics, blob, phase, blocked, true, -1.0f, streamer);
        draw_wavy_transparent_gap_fade(graphics, blob, phase, blocked, true, 1.0f, streamer);
        draw_gap_electric_shimmer(graphics, blob, phase, blocked, true, 1.0f, streamer);
        draw_flow_light_streamers(graphics, blob, phase, blocked, true, 1.0f, streamer);
        draw_single_flow_orbit_ring(graphics, blob, phase, blocked, true, streamer.inner_radius_scale, -1.0f, streamer);
        draw_single_flow_orbit_ring(graphics, blob, phase, blocked, true, streamer.outer_radius_scale, -1.0f, streamer);
        draw_single_flow_orbit_ring(graphics, blob, phase, blocked, true, streamer.inner_radius_scale, 1.0f, streamer);
        draw_single_flow_orbit_ring(graphics, blob, phase, blocked, true, streamer.outer_radius_scale, 1.0f, streamer);
        return;
    }

    draw_single_flow_orbit_ring(graphics, blob, phase, blocked, false, streamer.outer_radius_scale, -1.0f, streamer);
    draw_wavy_transparent_gap_fade(graphics, blob, phase, blocked, false, -1.0f, streamer);
    draw_gap_electric_shimmer(graphics, blob, phase, blocked, false, -1.0f, streamer);
    draw_flow_light_streamers(graphics, blob, phase, blocked, false, -1.0f, streamer);
    draw_single_flow_orbit_ring(graphics, blob, phase, blocked, false, streamer.inner_radius_scale, -1.0f, streamer);
    draw_single_flow_orbit_ring(graphics, blob, phase, blocked, false, streamer.outer_radius_scale, 1.0f, streamer);
    draw_wavy_transparent_gap_fade(graphics, blob, phase, blocked, false, 1.0f, streamer);
    draw_gap_electric_shimmer(graphics, blob, phase, blocked, false, 1.0f, streamer);
    draw_flow_light_streamers(graphics, blob, phase, blocked, false, 1.0f, streamer);
    draw_single_flow_orbit_ring(graphics, blob, phase, blocked, false, streamer.inner_radius_scale, 1.0f, streamer);
}

void draw_glow_single_ring_field(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked,
    bool front_pass) {
    for (int stream = kGlowSingleFlowRingCount - 1; stream >= 0; --stream) {
        FlowStreamerInstance const streamer = flow_glow_single_ring_instance(stream);
        draw_glowing_single_flow_ring(graphics, blob, phase, blocked, front_pass, -1.0f, streamer);
        draw_glowing_single_flow_ring(graphics, blob, phase, blocked, front_pass, 1.0f, streamer);
    }
}

void draw_flow_streamer_field(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked,
    bool front_pass) {
    for (int stream = kFlowStreamerRingInstanceCount - 1; stream >= 0; --stream) {
        draw_flow_streamer_instance(graphics, blob, phase, blocked, front_pass, flow_streamer_instance(stream));
    }
}

void draw_fine_flow_streamer_field(
    Gdiplus::Graphics& graphics,
    PearlescentBlobGeometry const& blob,
    double phase,
    bool blocked,
    bool front_pass) {
    for (int stream = kFineFlowStreamerRingInstanceCount - 1; stream >= 0; --stream) {
        draw_flow_streamer_instance(graphics, blob, phase, blocked, front_pass, flow_fine_streamer_instance(stream));
    }
}

void draw_core_sphere(Gdiplus::Graphics& graphics, float center, float core_radius, float pulse, double phase, bool blocked) {
    PearlescentBlobGeometry const core_blob = pearlescent_liquid_blob_geometry(center, core_radius, pulse, phase);
    Gdiplus::GraphicsPath core_path;
    add_pearlescent_liquid_blob_path(core_path, core_blob);
    draw_flow_streamer_field(graphics, core_blob, phase, blocked, false);
    draw_fine_flow_streamer_field(graphics, core_blob, phase, blocked, false);
    draw_glow_single_ring_field(graphics, core_blob, phase, blocked, false);
    draw_pearlescent_liquid_blob(graphics, core_blob, phase, blocked);

    Gdiplus::GraphicsState clipped = graphics.Save();
    graphics.SetClip(&core_path, Gdiplus::CombineModeReplace);

    for (int trail = 0; trail < kCoreFluidTrailCount; ++trail) {
        bool const inner = trail < (kCoreFluidTrailCount / 3);
        bool const highlight_trail = deterministic_unit(trail, 41) > 0.78f;
        float const orbit_base =
            core_radius * (inner ? deterministic_range(trail, 3, 0.12f, 0.43f) : deterministic_range(trail, 5, 0.30f, 0.82f));
        float const rx = orbit_base * deterministic_range(trail, 7, 0.74f, 1.20f);
        float const ry = orbit_base * deterministic_range(trail, 11, 0.50f, 1.03f);
        float const z_strength = deterministic_range(trail, 13, 0.12f, 0.46f);
        float const phase_a = deterministic_range(trail, 17, 0.0f, 2.0f * static_cast<float>(kPi));
        float const phase_b = deterministic_range(trail, 19, 0.0f, 2.0f * static_cast<float>(kPi));
        float const phase_c = deterministic_range(trail, 23, 0.0f, 2.0f * static_cast<float>(kPi));
        float const rotation = deterministic_range(trail, 29, -static_cast<float>(kPi), static_cast<float>(kPi)) +
                               static_cast<float>(phase * deterministic_range(trail, 31, -0.16f, 0.16f));
        float const rotation_cos = std::cos(rotation);
        float const rotation_sin = std::sin(rotation);
        float const trail_alpha = deterministic_range(trail, 37, inner ? 0.060f : 0.026f, inner ? 0.150f : 0.080f) *
                                  (highlight_trail ? 1.55f : 1.0f);
        float const glow_alpha = deterministic_range(trail, 43, inner ? 0.018f : 0.006f, inner ? 0.044f : 0.022f);

        Gdiplus::PointF previous{};
        bool has_previous = false;
        for (int sample = 0; sample <= kCoreFluidTrailSamples; ++sample) {
            float const t = (static_cast<float>(sample) / static_cast<float>(kCoreFluidTrailSamples)) *
                            2.0f * static_cast<float>(kPi);
            float const breathing = 1.0f + (0.085f * std::sin((t * deterministic_range(trail, 47, 2.0f, 5.0f)) + phase_b)) +
                                    (0.045f * std::sin((t * deterministic_range(trail, 53, 6.0f, 11.0f)) + phase_c));
            float const angle_x = t + (0.075f * std::sin((t * 3.0f) + phase_a + static_cast<float>(phase * 0.24)));
            float const angle_y = t + (0.055f * std::sin((t * 4.0f) + phase_c - static_cast<float>(phase * 0.19)));
            float const z = std::sin((t * deterministic_range(trail, 59, 1.0f, 4.0f)) + phase_c + static_cast<float>(phase * 0.21)) *
                            z_strength;
            float const local_x =
                (rx * breathing * std::cos(angle_x)) + (core_radius * 0.035f * std::sin((5.0f * t) + phase_c));
            float const local_y =
                (ry * breathing * std::sin(angle_y)) + (core_radius * 0.030f * std::cos((4.0f * t) + phase_a));
            float const depth_scale = 0.78f + (0.22f * ((z + 1.0f) * 0.5f));
            Gdiplus::PointF current(
                center + (((local_x * rotation_cos) - (local_y * rotation_sin)) * depth_scale),
                center + (((local_x * rotation_sin) + (local_y * rotation_cos)) * depth_scale));

            if (has_previous) {
                float const depth_alpha = std::clamp(0.72f + (0.28f * z), 0.35f, 1.05f);
                BYTE const line_alpha = byte_clamp(255.0f * trail_alpha * depth_alpha);
                Gdiplus::Pen trail_pen(
                    blocked ? alpha_color(line_alpha, 255, 228, 194) : alpha_color(line_alpha, 205, 230, 245),
                    highlight_trail ? 1.05f : 0.62f);
                trail_pen.SetStartCap(Gdiplus::LineCapRound);
                trail_pen.SetEndCap(Gdiplus::LineCapRound);
                graphics.DrawLine(&trail_pen, previous, current);
            }

            if (sample % (inner ? 5 : 10) == 0) {
                BYTE const glow_alpha_byte = byte_clamp(255.0f * glow_alpha * (0.65f + (0.35f * ((z + 1.0f) * 0.5f))));
                float const glow_size = core_radius * deterministic_range(trail, 61, inner ? 0.025f : 0.018f, inner ? 0.060f : 0.050f);
                Gdiplus::SolidBrush glow_brush(
                    blocked ? alpha_color(glow_alpha_byte, 255, 234, 204) : alpha_color(glow_alpha_byte, 170, 215, 255));
                graphics.FillEllipse(&glow_brush, current.X - glow_size, current.Y - glow_size, glow_size * 2.0f, glow_size * 2.0f);
            }

            previous = current;
            has_previous = true;
        }
    }

    for (int strand = 0; strand < 10; ++strand) {
        float const seed = static_cast<float>(strand);
        float const sweep = static_cast<float>(phase * (0.18 + (strand * 0.015)) + seed);
        float const x0 = center + (std::sin(sweep) * core_radius * 0.68f);
        float const y0 = center + (std::cos(sweep * 0.74f + 0.6f) * core_radius * 0.58f);
        float const x3 = center + (std::cos(sweep * 0.92f + 1.4f) * core_radius * 0.62f);
        float const y3 = center + (std::sin(sweep * 0.81f + 0.9f) * core_radius * 0.56f);
        float const x1 = center + (std::sin(sweep * 1.31f + 0.3f) * core_radius * 0.28f);
        float const y1 = center + (std::cos(sweep * 1.18f + 1.1f) * core_radius * 0.30f);
        float const x2 = center + (std::cos(sweep * 1.27f + 2.2f) * core_radius * 0.34f);
        float const y2 = center + (std::sin(sweep * 1.09f + 1.7f) * core_radius * 0.32f);

        Gdiplus::GraphicsPath strand_path;
        strand_path.AddBezier(x0, y0, x1, y1, x2, y2, x3, y3);
        BYTE const strand_alpha = byte_clamp(28.0f + (76.0f * wave(phase, 0.57 + (strand * 0.022), seed)));
        Gdiplus::Pen strand_pen(
            blocked ? alpha_color(strand_alpha, 255, 230, 196) : alpha_color(strand_alpha, 226, 238, 252),
            0.75f + (0.65f * wave(phase, 0.49, seed)));
        strand_pen.SetStartCap(Gdiplus::LineCapRound);
        strand_pen.SetEndCap(Gdiplus::LineCapRound);
        strand_pen.SetLineJoin(Gdiplus::LineJoinRound);
        graphics.DrawPath(&strand_pen, &strand_path);
    }

    graphics.Restore(clipped);
    draw_flow_streamer_field(graphics, core_blob, phase, blocked, true);
    draw_fine_flow_streamer_field(graphics, core_blob, phase, blocked, true);
    draw_glow_single_ring_field(graphics, core_blob, phase, blocked, true);
}

void draw_orb(Gdiplus::Graphics& graphics, int size, OrbState const& state, double phase) {
    graphics.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
    graphics.SetCompositingQuality(Gdiplus::CompositingQualityHighQuality);
    graphics.SetCompositingMode(Gdiplus::CompositingModeSourceOver);
    graphics.Clear(Gdiplus::Color(0, 0, 0, 0));

    float const center = static_cast<float>(size) * 0.5f;
    float const visual_size = static_cast<float>(size) * kOrbVisualScale;
    float const base_radius = visual_size * 0.35f;
    float const core_radius = visual_size * (kCoreFocusOnly ? (60.0f / 220.0f) : (32.0f / 220.0f));
    bool const active = state.posture == "active_feedback";
    bool const blocked = state.posture == "blocked" || state.unsafe_source_flags_denied;
    float const pulse = wave(phase, active ? 4.8 : 2.2);

    if constexpr (!kCoreFocusOnly) {
        for (int ring = 0; ring < kThreeDRingCount; ++ring) {
        float const major_radius = 0.34f + (static_cast<float>((ring * 17) % 22) / 100.0f);
        float const scale_x = 0.72f + (static_cast<float>((ring * 19) % 30) / 100.0f);
        float const scale_y = 0.26f + (static_cast<float>((ring * 13) % 38) / 100.0f);
        float const radius = base_radius * (0.72f + major_radius) * scale_x;
        float const yaw = static_cast<float>(((ring * 17) % 84) - 42);
        float const pitch = static_cast<float>(((ring * 13) % 76) - 38);
        float const roll = static_cast<float>((ring * 37) % 360);
        BYTE const alpha = byte_clamp(static_cast<float>(58 + ((ring * 23) % 132)) * 0.42f);
        float const stroke = 0.36f + (static_cast<float>((ring * 11) % 8) / 120.0f);
        draw_projected_energy_orbit(graphics, center, radius, scale_y, yaw, pitch, roll, phase, ring, alpha, stroke, blocked, false, false);
        }

        for (int index = 0; index < kFineOrbitCount; ++index) {
        float const width = static_cast<float>(42 + ((index * 29) % 76));
        float const height = static_cast<float>(14 + ((index * 17) % 50));
        float const radius = width * 0.5f;
        float const y_scale = std::clamp(height / std::max(1.0f, width), 0.12f, 0.72f);
        float const yaw = static_cast<float>(((index * 31) % 82) - 41);
        float const pitch = static_cast<float>(((index * 17) % 74) - 37);
        float const roll = static_cast<float>(std::fmod(index * 137.507, 360.0));
        BYTE const alpha = byte_clamp((52.0f + static_cast<float>((index * 11) % 95)) * 0.55f);
        draw_projected_energy_orbit(graphics, center, radius, y_scale, yaw, pitch, roll, phase, index, alpha, 0.55f, blocked, false, true);
        }
    }

    draw_core_sphere(graphics, center, core_radius * (0.94f + (0.08f * pulse)), pulse, phase, blocked);

    if constexpr (!kCoreFocusOnly) {
        for (int ring = 0; ring < kThreeDRingCount; ++ring) {
        float const major_radius = 0.34f + (static_cast<float>((ring * 17) % 22) / 100.0f);
        float const scale_x = 0.72f + (static_cast<float>((ring * 19) % 30) / 100.0f);
        float const scale_y = 0.26f + (static_cast<float>((ring * 13) % 38) / 100.0f);
        float const radius = base_radius * (0.72f + major_radius) * scale_x;
        float const yaw = static_cast<float>(((ring * 17) % 84) - 42);
        float const pitch = static_cast<float>(((ring * 13) % 76) - 38);
        float const roll = static_cast<float>((ring * 37) % 360);
        BYTE const alpha = byte_clamp(static_cast<float>(58 + ((ring * 23) % 132)) * 0.82f);
        float const stroke = 0.48f + (static_cast<float>((ring * 11) % 8) / 95.0f);
        draw_projected_energy_orbit(graphics, center, radius, scale_y, yaw, pitch, roll, phase, ring, alpha, stroke, blocked, true, false);
        }

        for (int index = 0; index < kBrightOrbitCount; ++index) {
        float const width = static_cast<float>(58 + ((index * 17) % 58));
        float const height = static_cast<float>(18 + ((index * 11) % 38));
        float const radius = width * 0.5f;
        float const y_scale = std::clamp(height / std::max(1.0f, width), 0.14f, 0.70f);
        float const yaw = static_cast<float>(((index * 29) % 76) - 38);
        float const pitch = static_cast<float>(((index * 23) % 68) - 34);
        float const roll = static_cast<float>((index * 41) % 360);
        draw_projected_energy_orbit(graphics, center, radius, y_scale, yaw, pitch, roll, phase, index, 142, 0.85f, blocked, true, true);
        }
    }

    if constexpr (!kCoreFocusOnly) {
        if (state.pointer_available) {
            float const pointer_angle = static_cast<float>(std::fmod((state.pointer_x * 0.021) + (phase * 0.65), kPi * 2.0));
            float const pointer_radius = base_radius * 1.16f;
            float const px = center + (std::cos(pointer_angle) * pointer_radius);
            float const py = center + (std::sin(pointer_angle) * pointer_radius * 0.64f);
            Gdiplus::SolidBrush pointer_glow(alpha_color(180, 255, 255, 255));
            graphics.FillEllipse(&pointer_glow, px - 5.0f, py - 5.0f, 10.0f, 10.0f);
        }
    }
}

class NativeOrbWindow {
public:
    NativeOrbWindow(RendererConfig config, OrbState state)
        : config_(config), state_(std::move(state)), start_(std::chrono::steady_clock::now()) {}

    int run(HINSTANCE instance) {
        WNDCLASSEXW wc{};
        wc.cbSize = sizeof(wc);
        wc.lpfnWndProc = &NativeOrbWindow::window_proc;
        wc.hInstance = instance;
        wc.lpszClassName = kWindowClassName;
        wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
        if (RegisterClassExW(&wc) == 0 && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
            fail("native Orb window class registration failed");
        }

        int const screen_width = GetSystemMetrics(SM_CXSCREEN);
        int const screen_height = GetSystemMetrics(SM_CYSCREEN);
        if (config_.x < 0) {
            config_.x = std::max(12, screen_width - config_.size - 72);
        }
        if (config_.y < 0) {
            config_.y = std::max(12, screen_height - config_.size - 96);
        }

        hwnd_ = CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
            kWindowClassName,
            L"Francis Native Orb",
            WS_POPUP,
            config_.x,
            config_.y,
            config_.size,
            config_.size,
            nullptr,
            nullptr,
            instance,
            this);
        if (hwnd_ == nullptr) {
            fail("native Orb window creation failed");
        }

        ShowWindow(hwnd_, SW_SHOWNOACTIVATE);
        SetTimer(hwnd_, 1, 16, nullptr);

        MSG message{};
        while (GetMessageW(&message, nullptr, 0, 0) > 0) {
            TranslateMessage(&message);
            DispatchMessageW(&message);
        }
        return static_cast<int>(message.wParam);
    }

private:
    static LRESULT CALLBACK window_proc(HWND hwnd, UINT message, WPARAM wparam, LPARAM lparam) {
        NativeOrbWindow* self = reinterpret_cast<NativeOrbWindow*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
        if (message == WM_NCCREATE) {
            CREATESTRUCTW const* create = reinterpret_cast<CREATESTRUCTW const*>(lparam);
            self = reinterpret_cast<NativeOrbWindow*>(create->lpCreateParams);
            SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(self));
            return TRUE;
        }
        if (self == nullptr) {
            return DefWindowProcW(hwnd, message, wparam, lparam);
        }
        switch (message) {
        case kMoveCenterMessage:
            self->move_center_to(message_coordinate_to_int(wparam), message_coordinate_to_int(static_cast<WPARAM>(lparam)));
            return 0;
        case WM_TIMER:
            self->on_timer();
            return 0;
        case WM_DESTROY:
            KillTimer(hwnd, 1);
            PostQuitMessage(0);
            return 0;
        case WM_NCHITTEST:
            return HTTRANSPARENT;
        default:
            return DefWindowProcW(hwnd, message, wparam, lparam);
        }
    }

    void move_center_to(int center_x, int center_y) {
        config_.x = center_x - (config_.size / 2);
        config_.y = center_y - (config_.size / 2);
    }

    void on_timer() {
        auto const now = std::chrono::steady_clock::now();
        double const elapsed = std::chrono::duration<double>(now - start_).count();
        if (config_.run_seconds > 0 && elapsed >= config_.run_seconds) {
            DestroyWindow(hwnd_);
            return;
        }
        if (elapsed - last_reload_seconds_ > 1.0) {
            last_reload_seconds_ = elapsed;
            try {
                state_ = load_orb_state(config_.snapshot_path);
            } catch (std::exception const&) {
                state_.posture = "blocked";
                state_.feedback_state = "blocked";
                state_.unsafe_source_flags_denied = true;
            }
        }
        render(elapsed);
    }

    void render(double elapsed) {
        int const size = config_.size;
        HDC screen_dc = GetDC(nullptr);
        HDC memory_dc = CreateCompatibleDC(screen_dc);
        if (screen_dc == nullptr || memory_dc == nullptr) {
            if (memory_dc != nullptr) {
                DeleteDC(memory_dc);
            }
            if (screen_dc != nullptr) {
                ReleaseDC(nullptr, screen_dc);
            }
            return;
        }

        BITMAPINFO bitmap_info{};
        bitmap_info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        bitmap_info.bmiHeader.biWidth = size;
        bitmap_info.bmiHeader.biHeight = -size;
        bitmap_info.bmiHeader.biPlanes = 1;
        bitmap_info.bmiHeader.biBitCount = 32;
        bitmap_info.bmiHeader.biCompression = BI_RGB;

        void* pixels = nullptr;
        HBITMAP bitmap = CreateDIBSection(screen_dc, &bitmap_info, DIB_RGB_COLORS, &pixels, nullptr, 0);
        if (bitmap == nullptr) {
            DeleteDC(memory_dc);
            ReleaseDC(nullptr, screen_dc);
            return;
        }

        HGDIOBJ old_bitmap = SelectObject(memory_dc, bitmap);
        {
            Gdiplus::Graphics graphics(memory_dc);
            draw_orb(graphics, size, state_, elapsed);
        }

        POINT destination{config_.x, config_.y};
        SIZE window_size{size, size};
        POINT source{0, 0};
        BLENDFUNCTION blend{};
        blend.BlendOp = AC_SRC_OVER;
        blend.SourceConstantAlpha = 255;
        blend.AlphaFormat = AC_SRC_ALPHA;
        UpdateLayeredWindow(hwnd_, screen_dc, &destination, &window_size, memory_dc, &source, 0, &blend, ULW_ALPHA);

        SelectObject(memory_dc, old_bitmap);
        DeleteObject(bitmap);
        DeleteDC(memory_dc);
        ReleaseDC(nullptr, screen_dc);
    }

    RendererConfig config_;
    OrbState state_;
    HWND hwnd_ = nullptr;
    std::chrono::steady_clock::time_point start_;
    double last_reload_seconds_ = -10.0;
};

}  // namespace

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int) {
    try {
        int argc = 0;
        wchar_t** argv = CommandLineToArgvW(GetCommandLineW(), &argc);
        if (argv == nullptr) {
            fail("command line parse failed");
        }
        RendererConfig config = parse_args(argc, argv);
        LocalFree(argv);

        ULONG_PTR gdiplus_token = start_gdiplus();
        OrbState state = load_orb_state(config.snapshot_path);
        NativeOrbWindow window(config, state);
        int const result = window.run(instance);
        Gdiplus::GdiplusShutdown(gdiplus_token);
        return result;
    } catch (std::exception const& error) {
        MessageBoxA(nullptr, error.what(), "Francis Native Orb denied", MB_OK | MB_ICONERROR);
        return 2;
    }
}
