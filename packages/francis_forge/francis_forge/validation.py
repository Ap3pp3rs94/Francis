from __future__ import annotations

from typing import Any

from francis_core.workspace_fs import WorkspaceFS


def validate_stage(fs: WorkspaceFS, rel_paths: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    validated: list[str] = []

    for rel_path in rel_paths:
        try:
            content = fs.read_text(rel_path)
        except Exception as exc:
            errors.append(f"missing:{rel_path}:{exc}")
            continue

        if rel_path.endswith(".py"):
            try:
                compile(content, rel_path, "exec")
            except Exception as exc:
                errors.append(f"syntax:{rel_path}:{exc}")
                continue

        validated.append(rel_path)

    return {
        "ok": len(errors) == 0,
        "validated_count": len(validated),
        "errors": errors,
    }
