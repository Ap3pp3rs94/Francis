from __future__ import annotations

import json
from pathlib import Path

from francis_core.dependency_library import (
    build_dependency_library,
    build_dependency_provenance,
    list_dependency_entries,
    quarantine_dependency,
    revoke_dependency,
)
from francis_core.workspace_fs import WorkspaceFS


def _fs(root: Path) -> WorkspaceFS:
    workspace = (root / "workspace").resolve()
    return WorkspaceFS(
        roots=[workspace],
        journal_path=(workspace / "journals" / "fs.jsonl").resolve(),
    )


def _write_registry(fs: WorkspaceFS, rows: list[dict[str, object]]) -> None:
    fs.write_text(
        "dependencies/registry.json",
        json.dumps({"dependencies": rows}, ensure_ascii=False, indent=2),
    )


def _seed_repo(root: Path) -> None:
    root.joinpath("pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "francis"',
                'version = "0.2.0"',
                'requires-python = ">=3.10"',
                'dependencies = ["fastapi>=0.110,<1", "uvicorn>=0.29,<1"]',
                "[project.optional-dependencies]",
                'dev = ["pytest>=8,<9"]',
            ]
        ),
        encoding="utf-8",
    )
    root.joinpath("package.json").write_text(
        json.dumps(
            {
                "name": "francis-overlay-shell",
                "devDependencies": {
                    "electron": "40.8.0",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    root.joinpath("package-lock.json").write_text(
        json.dumps(
            {
                "name": "francis-overlay-shell",
                "lockfileVersion": 3,
                "packages": {
                    "": {"devDependencies": {"electron": "40.8.0"}},
                    "node_modules/electron": {"version": "40.8.0"},
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_dependency_library_counts_review_required_and_unpinned_rows(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    fs = _fs(tmp_path)

    entries = list_dependency_entries(fs)
    library = build_dependency_library(entries)
    fastapi = next(row for row in entries if row["id"] == "python:francis:fastapi")
    provenance = build_dependency_provenance(fastapi)

    assert library["dependency_count"] == 4
    assert library["runtime_count"] == 2
    assert library["unpinned_count"] >= 1
    assert provenance["kind"] == "third_party"
    assert provenance["review_required"] is True
    assert provenance["pinned"] is False
    assert "pinning" in provenance["promotion_rule_detail"].lower()


def test_dependency_provenance_accepts_pinned_vendor_review(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    fs = _fs(tmp_path)
    _write_registry(
        fs,
        [
            {
                "id": "node:francis-overlay-shell:electron",
                "provenance": {
                    "source_kind": "vendor",
                    "review_state": "approved",
                },
            }
        ],
    )

    entries = list_dependency_entries(fs)
    electron = next(row for row in entries if row["id"] == "node:francis-overlay-shell:electron")
    provenance = build_dependency_provenance(electron)

    assert provenance["kind"] == "vendor"
    assert provenance["label"] == "Vendor Provided"
    assert provenance["pinned"] is True
    assert provenance["review_required"] is False
    assert provenance["review_state"] == "approved"
    assert provenance["locked_version"] == "40.8.0"


def test_quarantine_and_revoke_dependency_preserve_audit(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    fs = _fs(tmp_path)

    quarantined = quarantine_dependency(
        fs,
        "python:francis:fastapi",
        reason="Dependency is unpinned on the governed runtime path.",
        actor="dependencies:architect",
    )
    assert quarantined is not None
    assert quarantined["status"] == "quarantined"
    assert quarantined["previous_status"] == "declared"
    assert quarantined["quarantine_reason"] == "Dependency is unpinned on the governed runtime path."
    assert quarantined["provenance"]["review_state"] == "quarantined"

    revoked = revoke_dependency(
        fs,
        "python:francis:fastapi",
        reason="Dependency is no longer trusted for governed use.",
        actor="dependencies:architect",
    )
    assert revoked is not None
    assert revoked["status"] == "revoked"
    assert revoked["previous_status"] == "quarantined"
    assert revoked["quarantined_at"]
    assert revoked["revoked_at"]
    assert revoked["revocation_reason"] == "Dependency is no longer trusted for governed use."
    assert revoked["provenance"]["review_state"] == "revoked"
