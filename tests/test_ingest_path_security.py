from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.ingest import IngestService
from francis.ingest.core.lab_service import (
    _lab_provider_policy_manifest_metadata,
    _lab_provider_reference_metadata,
)
from francis.ingest.ingest.source import canonical_path, display_path, safe_local_path_text

_INGEST_LAB_SANDBOX_PROVIDER_SELECTION_ACTOR = "test.ingest.lab.sandbox.provider_selection"


def _outside_default_local_root(*parts: str) -> Path:
    return Path(Path.cwd().anchor).joinpath("__francis_disallowed_ingest_path__", *parts)


def test_canonical_path_accepts_operator_local_path(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()

    assert safe_local_path_text(source) == str(source)
    assert canonical_path(source) == source.resolve()


def test_canonical_path_rejects_control_characters() -> None:
    with pytest.raises(ValueError, match="path_text_contains_control_character"):
        canonical_path("bad\x00path")


def test_canonical_path_rejects_path_outside_allowed_local_roots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRANCIS_ALLOWED_LOCAL_PATH_ROOTS", raising=False)

    with pytest.raises(ValueError, match="path_outside_allowed_local_roots"):
        canonical_path(_outside_default_local_root("source"))


def test_canonical_path_allows_explicit_operator_local_root(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(Path.cwd().anchor) / "__francis_configured_ingest_root__"
    source = root / "source"
    monkeypatch.setenv("FRANCIS_ALLOWED_LOCAL_PATH_ROOTS", str(root))

    assert canonical_path(source) == source.resolve(strict=False)


def test_canonical_path_allows_multiple_explicit_operator_local_roots(monkeypatch: pytest.MonkeyPatch) -> None:
    first_root = Path(Path.cwd().anchor) / "__francis_configured_ingest_root_a__"
    second_root = Path(Path.cwd().anchor) / "__francis_configured_ingest_root_b__"
    source = second_root / "source"
    monkeypatch.setenv("FRANCIS_ALLOWED_LOCAL_PATH_ROOTS", os.pathsep.join([str(first_root), str(second_root)]))

    assert canonical_path(source) == source.resolve(strict=False)


def test_display_path_does_not_throw_on_invalid_path_text() -> None:
    assert display_path("bad\x00path") == "bad?path"


def test_add_source_records_invalid_path_text_as_failed_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "francis_data"))

    result = IngestService().add_source("bad\x00path", actor="test.ingest")

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["error"] == "source_path_invalid"
    assert Path(result["receipt_path"]).exists()
    assert result["receipt"]["operation"] == "source.add"
    assert "source_path_invalid" in result["receipt"]["errors"]
    assert "path_text_validation" in result["receipt"]["validation_performed"]


def test_sandbox_provider_selection_api_rejects_invalid_source_path_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-selection",
        json={
            "source_or_path": "bad\x00path",
            "candidate": "run_project_tests",
            "approval_id": "unused",
            "provider_kind": "local_process_sandbox",
            "provider_reference": "provider-service",
            "provider_policy_manifest": "",
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_SELECTION_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_selection"
    assert body["ok"] is False
    assert body["status"] == "failed"
    assert body["error"] == "source_path_invalid"
    assert body["execution"]["executed"] is False
    assert body["execution"]["execution_authority"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    selection_dir = data_root / "artifacts" / "ingest" / "lab_sandbox_provider_selections"
    assert not list(selection_dir.glob("*.json"))


def test_lab_provider_reference_metadata_rejects_invalid_path_text() -> None:
    metadata = _lab_provider_reference_metadata("C:\\runner\x00provider")

    assert metadata["reference_kind"] == "invalid_path_text"
    assert metadata["reference_present"] is False
    assert metadata["metadata_checked"] is True
    assert metadata["reference_verified"] is False
    assert metadata["contents_read"] is False
    assert metadata["executed"] is False
    assert metadata["error"] == "path_text_contains_control_character"


def test_lab_provider_reference_metadata_rejects_path_outside_allowed_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRANCIS_ALLOWED_LOCAL_PATH_ROOTS", raising=False)

    metadata = _lab_provider_reference_metadata(str(_outside_default_local_root("provider-bin")))

    assert metadata["reference_kind"] == "path"
    assert metadata["reference_present"] is False
    assert metadata["metadata_checked"] is True
    assert metadata["reference_verified"] is False
    assert metadata["contents_read"] is False
    assert metadata["executed"] is False
    assert metadata["error"] == "path_outside_allowed_local_roots"


def test_lab_provider_policy_manifest_metadata_rejects_invalid_path_text() -> None:
    metadata = _lab_provider_policy_manifest_metadata("C:\\runner\x00policy.json")

    assert metadata["present"] is False
    assert metadata["metadata_checked"] is True
    assert metadata["is_file"] is False
    assert metadata["bound"] is False
    assert metadata["contents_read"] is False
    assert metadata["error"] == "path_text_contains_control_character"


def test_lab_provider_policy_manifest_metadata_rejects_path_outside_allowed_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRANCIS_ALLOWED_LOCAL_PATH_ROOTS", raising=False)

    metadata = _lab_provider_policy_manifest_metadata(str(_outside_default_local_root("policy.json")))

    assert metadata["present"] is False
    assert metadata["metadata_checked"] is True
    assert metadata["is_file"] is False
    assert metadata["bound"] is False
    assert metadata["contents_read"] is False
    assert metadata["error"] == "path_outside_allowed_local_roots"
