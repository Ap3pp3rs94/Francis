#include "third_party/nlohmann/json.hpp"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using Json = nlohmann::json;

namespace {

constexpr wchar_t kDefaultSnapshotPath[] = L"schemas\\native_orb_state_snapshot.fixture.json";
constexpr std::uintmax_t kMaxSnapshotBytes = 64 * 1024;

[[noreturn]] void fail(std::string const& message) {
    throw std::runtime_error(message);
}

bool is_component(fs::path const& path, wchar_t const* expected) {
    return path.wstring() == expected;
}

fs::path bounded_snapshot_path(int argc, wchar_t** argv) {
    if (argc > 2) {
        fail("usage: native_orb_state_probe.exe [schemas/native_orb_state_snapshot.fixture.json]");
    }

    fs::path candidate = argc == 2 ? fs::path(argv[1]) : fs::path(kDefaultSnapshotPath);
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

Json const& require_array(Json const& object, char const* key) {
    auto const item = object.find(key);
    if (item == object.end() || !item->is_array()) {
        fail("missing required array");
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

void expect_string(Json const& object, char const* key, char const* expected) {
    std::string const actual = require_string(object, key);
    if (actual != expected) {
        fail(std::string("unexpected string for ") + key);
    }
}

void expect_bool(Json const& object, char const* key, bool expected) {
    bool const actual = require_bool(object, key);
    if (actual != expected) {
        fail(std::string("unexpected boolean for ") + key);
    }
}

bool array_contains(Json const& values, char const* expected) {
    for (auto const& value : values) {
        if (value.is_string() && value.get<std::string>() == expected) {
            return true;
        }
    }
    return false;
}

void validate_native_orb_state_snapshot(Json const& root) {
    expect_string(root, "kind", "francis.native_orb.state_snapshot");
    expect_string(root, "schema_version", "francis.native_orb.state_snapshot.v1");
    expect_string(root, "schema_path", "schemas/native_orb_state_snapshot.schema.json");

    Json const& runtime = require_object(root, "runtime_contract");
    expect_string(runtime, "native_runtime", "cpp");
    expect_string(runtime, "status", "contract_ready");
    expect_bool(runtime, "implemented", true);
    expect_bool(runtime, "active_renderer", true);
    expect_bool(runtime, "body_renderer_only", true);
    expect_string(runtime, "authority_layer", "francis_core");
    expect_bool(runtime, "francis_core_remains_authority", true);

    Json const& visual_lock = require_object(root, "visual_lock");
    expect_string(visual_lock, "source", "docs/operations/ORB_VISUAL_LOCK.md");
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
    expect_bool(authority, "francis_core_authority", true);
    expect_bool(authority, "native_runtime_authority", false);
    expect_bool(authority, "grants_execution_authority", false);
    expect_bool(authority, "grants_capability_authority", false);
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
    expect_string(ipc, "state_channel", "read_only_snapshot");
    expect_string(ipc, "event_channel", "not_implemented");
    expect_bool(ipc, "local_only", true);
    expect_bool(ipc, "network_transport_required", false);
    expect_bool(ipc, "accepts_mutation_events", false);

    Json const& events = require_object(root, "event_contract");
    expect_bool(events, "emits_intent_events", false);
    expect_bool(events, "mutation_events_default_denied", true);
    expect_bool(events, "desktop_action_events_require_governed_path", true);

    Json const& limitations = require_array(root, "limitations");
    if (!array_contains(limitations, "no_native_event_channel_implemented")) {
        fail("snapshot must keep native event channel unimplemented");
    }
    if (!array_contains(limitations, "no_desktop_mutation_authority")) {
        fail("snapshot must deny desktop mutation authority");
    }
    if (!array_contains(limitations, "no_user_os_cursor_control")) {
        fail("snapshot must deny user OS cursor control");
    }
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    try {
        fs::path const snapshot_path = bounded_snapshot_path(argc, argv);
        std::string const snapshot_bytes = read_snapshot(snapshot_path);
        Json const root = Json::parse(snapshot_bytes);
        validate_native_orb_state_snapshot(root);

        Json const& render_state = require_object(root, "render_state");
        Json const& pointer = require_object(root, "virtual_pointer");

        std::cout << "francis_native_orb_state_probe=accepted_read_only_snapshot\n";
        std::cout << "schema_version=" << require_string(root, "schema_version") << "\n";
        std::cout << "runtime=cpp\n";
        std::cout << "renderer_implemented=true\n";
        std::cout << "native_renderer_active=true\n";
        std::cout << "render_only=true\n";
        std::cout << "feedback_state=" << require_string(render_state, "feedback_state") << "\n";
        std::cout << "virtual_pointer_available=" << (require_bool(pointer, "available") ? "true" : "false")
                  << "\n";
        std::cout << "desktop_mutation_authority=false\n";
        std::cout << "user_os_cursor_control=false\n";
        std::cout << "event_channel=not_implemented\n";
        return 0;
    } catch (std::exception const& error) {
        std::cerr << "francis_native_orb_state_probe=denied\n";
        std::cerr << "reason=" << error.what() << "\n";
        return 2;
    }
}
