from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from francis.unreal_presence_selection import (
    UNREAL_PRESENCE_SELECTION_PATH_ENV,
    build_unreal_presence_selection,
    unreal_presence_selection_readback,
    validate_unreal_presence_selection,
)


def _selection_inputs(tmp_path: Path) -> tuple[Path, Path, list[dict[str, str]]]:
    engine_root = tmp_path / "UE_5.8"
    build_path = engine_root / "Engine" / "Build" / "Build.version"
    editor_path = engine_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
    build_path.parent.mkdir(parents=True)
    editor_path.parent.mkdir(parents=True)
    build_path.write_text(
        json.dumps({"MajorVersion": 5, "MinorVersion": 8, "PatchVersion": 0, "Changelist": 55116800}),
        encoding="utf-8",
    )
    editor_path.write_bytes(b"MZ")

    project_path = tmp_path / "FrancisPresence" / "FrancisPresence.uproject"
    project_path.parent.mkdir(parents=True)
    project_path.write_text(
        json.dumps(
            {
                "FileVersion": 3,
                "EngineAssociation": "5.8",
                "Category": "",
                "Description": "Francis governed presence renderer",
            }
        ),
        encoding="utf-8",
    )
    technologies = [
        {"id": "cpp_runtime_module", "role": "governed_transport_adapter"},
        {"id": "niagara", "role": "presence_visualization"},
    ]
    return engine_root, project_path, technologies


def _schema() -> dict[str, object]:
    path = Path(__file__).parents[2] / "schemas" / "grounded_presence_unreal_selection.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_builder_produces_deterministic_schema_valid_operator_selection(tmp_path: Path) -> None:
    engine_root, project_path, technologies = _selection_inputs(tmp_path)
    first = build_unreal_presence_selection(
        engine_root=engine_root,
        project_path=project_path,
        technology_stack=technologies,
        confirmed_at="2026-07-10T12:00:00Z",
    )
    second = build_unreal_presence_selection(
        engine_root=engine_root,
        project_path=project_path,
        technology_stack=technologies,
        confirmed_at="2026-07-10T12:00:00Z",
    )

    Draft202012Validator(_schema(), format_checker=FormatChecker()).validate(first)
    assert first == second
    assert first["selection_id"].startswith("gpu_")
    assert validate_unreal_presence_selection(first) == ()
    assert "secret" not in json.dumps(first).lower()
    assert first["authority"]["grants_execution_authority"] is False


def test_readback_is_pending_without_explicit_manifest_path() -> None:
    readback = unreal_presence_selection_readback(environ={})

    assert readback["status"] == "operator_confirmation_required"
    assert readback["configured"] is False
    assert readback["valid"] is False
    assert readback["selection_id"] == ""
    assert readback["runtime_configured"] is False
    assert readback["runtime_observed"] is False
    assert readback["launches_unreal"] is False
    assert readback["validation"]["reasons"] == ["selection_path_not_configured"]


def test_readback_accepts_only_explicit_digest_pinned_selection(tmp_path: Path) -> None:
    engine_root, project_path, technologies = _selection_inputs(tmp_path)
    selection = build_unreal_presence_selection(
        engine_root=engine_root,
        project_path=project_path,
        technology_stack=technologies,
        confirmed_at="2026-07-10T12:00:00Z",
    )
    manifest_path = tmp_path / "selection.json"
    manifest_path.write_text(json.dumps(selection), encoding="utf-8")

    readback = unreal_presence_selection_readback(environ={UNREAL_PRESENCE_SELECTION_PATH_ENV: str(manifest_path)})

    assert readback["status"] == "operator_selection_confirmed"
    assert readback["configured"] is True
    assert readback["valid"] is True
    assert readback["selection_id"] == selection["selection_id"]
    assert readback["project_selection_status"] == "operator_confirmed"
    assert readback["technology_selection_status"] == "operator_confirmed"
    assert readback["technology_stack"] == technologies
    assert readback["runtime_configured"] is False
    assert readback["authority"]["grants_desktop_authority"] is False


def test_readback_fails_closed_when_confirmed_project_drifts(tmp_path: Path) -> None:
    engine_root, project_path, technologies = _selection_inputs(tmp_path)
    selection = build_unreal_presence_selection(
        engine_root=engine_root,
        project_path=project_path,
        technology_stack=technologies,
        confirmed_at="2026-07-10T12:00:00Z",
    )
    manifest_path = tmp_path / "selection.json"
    manifest_path.write_text(json.dumps(selection), encoding="utf-8")
    project_path.write_text(
        json.dumps({"FileVersion": 3, "EngineAssociation": "5.8", "Description": "drifted"}),
        encoding="utf-8",
    )

    readback = unreal_presence_selection_readback(selection_path=manifest_path)

    assert readback["status"] == "selection_stale"
    assert readback["valid"] is False
    assert readback["project"] == {}
    assert readback["technology_stack"] == []
    assert "selection_project_descriptor_drift" in readback["validation"]["reasons"]


def test_selection_rejects_authority_expansion_and_unknown_fields(tmp_path: Path) -> None:
    engine_root, project_path, technologies = _selection_inputs(tmp_path)
    selection = build_unreal_presence_selection(
        engine_root=engine_root,
        project_path=project_path,
        technology_stack=technologies,
        confirmed_at="2026-07-10T12:00:00Z",
    )
    expanded = deepcopy(selection)
    expanded["authority"]["grants_network_authority"] = True
    expanded["launch_command"] = "UnrealEditor.exe"

    reasons = validate_unreal_presence_selection(expanded)

    assert "selection_fields_invalid" in reasons
    assert "selection_authority_invalid" in reasons
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema(), format_checker=FormatChecker()).validate(expanded)


def test_builder_rejects_non_5_8_project_and_duplicate_technology(tmp_path: Path) -> None:
    engine_root, project_path, technologies = _selection_inputs(tmp_path)
    project_path.write_text(json.dumps({"FileVersion": 3, "EngineAssociation": "5.7"}), encoding="utf-8")

    with pytest.raises(ValueError, match="selection_project_engine_association_not_5_8"):
        build_unreal_presence_selection(
            engine_root=engine_root,
            project_path=project_path,
            technology_stack=technologies,
        )

    project_path.write_text(json.dumps({"FileVersion": 3, "EngineAssociation": "5.8"}), encoding="utf-8")
    with pytest.raises(ValueError, match="selection_technology_duplicate"):
        build_unreal_presence_selection(
            engine_root=engine_root,
            project_path=project_path,
            technology_stack=[technologies[0], technologies[0]],
        )
