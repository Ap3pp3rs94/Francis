from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReplaceResult:
    file: Path
    start_line: int  # 1-based
    end_line: int  # 1-based (line containing the end marker)
    replaced_lines: int


def _find_line_index(lines: list[str], marker: str, *, start_at: int = 0) -> int:
    for i in range(start_at, len(lines)):
        if marker in lines[i]:
            return i
    return -1


def replace_doc_block(*, file: Path, start: str, end: str, template_file: Path) -> ReplaceResult:
    """Replace a block of text in `file` between `start` and `end` markers.

    Markers are treated as literal substrings searched line-by-line.

    Replacement behavior:
    - The line containing `start` is replaced (template typically includes it).
    - The line containing `end` is preserved and acts as the end delimiter.
    """
    text = file.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)

    start_i = _find_line_index(lines, start)
    if start_i < 0:
        raise ValueError(f"Start marker not found: {start!r}")

    end_i = _find_line_index(lines, end, start_at=start_i + 1)
    if end_i < 0:
        raise ValueError(f"End marker not found after start: {end!r}")

    template_text = template_file.read_text(encoding="utf-8", errors="replace")
    template_lines = template_text.splitlines(keepends=True)
    if template_lines and not template_lines[-1].endswith(("\n", "\r")):
        template_lines[-1] += "\n"

    new_lines = [*lines[:start_i], *template_lines, *lines[end_i:]]
    # Avoid newline translation on Windows; keep the file's existing newline style.
    file.write_text("".join(new_lines), encoding="utf-8", newline="\n")

    return ReplaceResult(
        file=file,
        start_line=start_i + 1,
        end_line=end_i + 1,
        replaced_lines=(end_i - start_i),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Replace a marked block in a text/Markdown file.")
    p.add_argument("--file", required=True, help="Target file to edit in place.")
    p.add_argument("--start", required=True, help="Start marker (literal substring searched line-by-line).")
    p.add_argument("--end", required=True, help="End marker (literal substring searched line-by-line).")
    p.add_argument("--template-file", required=True, help="Template file whose contents replace the marked block.")
    args = p.parse_args(argv)

    try:
        result = replace_doc_block(
            file=Path(args.file),
            start=str(args.start),
            end=str(args.end),
            template_file=Path(args.template_file),
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        f"OK: updated {result.file} (replaced {result.replaced_lines} lines; "
        f"start={result.start_line} end={result.end_line})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
