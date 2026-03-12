from __future__ import annotations

from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import add_entry, list_entries
from francis_forge.library import build_capability_library, build_quality_standard, next_patch_version
from francis_forge.promotion import promote_stage


def _fs(root) -> WorkspaceFS:
    workspace = (root / "workspace").resolve()
    return WorkspaceFS(
        roots=[workspace],
        journal_path=(workspace / "journals" / "fs.jsonl").resolve(),
    )


def test_capability_library_groups_versions_and_assigns_next_patch(tmp_path) -> None:
    fs = _fs(tmp_path)
    add_entry(
        fs,
        {
            "id": "capability-stage-v1",
            "name": "Capability Stage",
            "slug": "capability-stage",
            "status": "active",
            "version": "0.1.0",
        },
    )
    add_entry(
        fs,
        {
            "id": "capability-stage-v2",
            "name": "Capability Stage",
            "slug": "capability-stage",
            "status": "staged",
            "version": "0.1.1",
        },
    )

    library = build_capability_library(list_entries(fs))

    assert next_patch_version(list_entries(fs), "capability-stage") == "0.1.2"
    assert library["pack_count"] == 1
    pack = library["packs"][0]
    assert pack["pack_id"] == "capability-stage"
    assert pack["version_count"] == 2
    assert pack["active_version"] == "0.1.0"
    assert pack["latest_version"] == "0.1.1"
    assert pack["focus_version"]["id"] == "capability-stage-v2"


def test_capability_quality_standard_requires_docs_tests_and_tool_pack() -> None:
    quality = build_quality_standard(
        {
            "validation": {"ok": True},
            "diff_summary": {
                "file_count": 2,
                "files": [
                    {"path": "forge/staging/capability-stage/README.md"},
                    {"path": "forge/staging/capability-stage/tests/test_capability_stage.py"},
                ],
            },
            "tool_pack": {"skill_name": "forge.pack.capability-stage"},
        }
    )

    assert quality["ok"] is True
    assert quality["score"] == "5/5"


def test_promote_stage_supersedes_prior_active_version(tmp_path) -> None:
    fs = _fs(tmp_path)
    add_entry(
        fs,
        {
            "id": "capability-stage-v1",
            "name": "Capability Stage",
            "slug": "capability-stage",
            "status": "active",
            "version": "0.1.0",
            "validation": {"ok": True},
            "diff_summary": {
                "file_count": 2,
                "files": [
                    {"path": "forge/staging/capability-stage-v1/README.md"},
                    {"path": "forge/staging/capability-stage-v1/tests/test_capability_stage.py"},
                ],
            },
            "tool_pack": {"skill_name": "forge.pack.capability-stage"},
        },
    )
    add_entry(
        fs,
        {
            "id": "capability-stage-v2",
            "name": "Capability Stage",
            "slug": "capability-stage",
            "status": "staged",
            "version": "0.1.1",
            "validation": {"ok": True},
            "diff_summary": {
                "file_count": 2,
                "files": [
                    {"path": "forge/staging/capability-stage-v2/README.md"},
                    {"path": "forge/staging/capability-stage-v2/tests/test_capability_stage.py"},
                ],
            },
            "tool_pack": {"skill_name": "forge.pack.capability-stage"},
        },
    )

    promoted = promote_stage(fs, "capability-stage-v2")
    assert promoted is not None
    assert promoted["status"] == "active"

    rows = {row["id"]: row for row in list_entries(fs)}
    assert rows["capability-stage-v1"]["status"] == "superseded"
    assert rows["capability-stage-v1"]["superseded_by"] == "capability-stage-v2"
    assert rows["capability-stage-v2"]["status"] == "active"
