from __future__ import annotations

from typing import Any


def summarize_files(files: dict[str, str]) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    total_lines = 0
    total_chars = 0
    for path, content in files.items():
        lines = len(content.splitlines())
        chars = len(content)
        total_lines += lines
        total_chars += chars
        details.append({"path": path, "lines": lines, "chars": chars})
    return {
        "file_count": len(files),
        "total_lines": total_lines,
        "total_chars": total_chars,
        "files": details,
    }
