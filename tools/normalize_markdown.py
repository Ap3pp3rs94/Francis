from __future__ import annotations

import argparse
import re
from pathlib import Path


# Markdown characters that are commonly escaped in the current repo docs.
_MD_UNESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!>|])")


def _looks_machine_escaped(text: str) -> bool:
    # Heuristic: lots of "\#" or "\##" is a strong signal.
    if re.search(r"(?m)^\\#{1,6}\s", text):
        return True
    if "\\*" in text and "\\#" in text:
        return True
    return False


def _looks_banner_commented(text: str) -> bool:
    lines = text.splitlines()
    first_non_empty = next((ln for ln in lines if ln.strip() != ""), "")
    return first_non_empty.startswith("# ") and "=" in first_non_empty


def _strip_hash_prefix_lines(text: str) -> str:
    """Strip a leading '# ' from every line when the whole file is hash-prefixed.

    This is used for docs/canonical/BUILD_MANIFEST.md, which currently has every line prefixed
    with '# ' (as if it were copied from a comment block).
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return text

    non_empty = [ln for ln in lines if ln.strip() != ""]
    if not non_empty:
        return text

    prefixed = sum(1 for ln in non_empty if ln.startswith("#") and (len(ln) == 1 or ln[1] == " "))
    # Only strip if it's basically the entire non-empty file (avoid false positives).
    if prefixed / max(1, len(non_empty)) < 0.95:
        return text
    out: list[str] = []
    for ln in lines:
        if ln.startswith("# "):
            out.append(ln[2:])
        elif ln.startswith("#\n") or ln == "#":
            out.append("\n" if ln.endswith("\n") else "")
        else:
            out.append(ln)
    return "".join(out)


def _decomment_initial_block(text: str) -> str:
    """Decomment an initial '# ' comment block into normal markdown text.

    Many docs start with a banner/preamble where every non-empty line begins with '# '.
    In markdown, that turns into headings, which is not intended. This strips only the
    initial contiguous block (stops at the first non-comment non-blank line).
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return text

    # Heuristic: banner file starts with "# ==="
    first_non_empty = next((ln for ln in lines if ln.strip() != ""), "")
    if not first_non_empty.startswith("# ") or "=" not in first_non_empty:
        return text

    out: list[str] = []
    i = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "":
            out.append(ln)
            continue

        if ln.startswith("# "):
            rem = ln[2:]
        elif ln.startswith("#\n") or ln == "#":
            rem = "\n" if ln.endswith("\n") else ""
        else:
            # End of the initial comment block.
            out.extend(lines[i:])
            break

        # Remove a single leading space introduced by "#  ..." while preserving indentation.
        if rem.startswith(" ") and not rem.startswith("  "):
            rem = rem[1:]
        out.append(rem)
    else:
        # Whole file was comment-prefixed
        return "".join(out)

    return "".join(out)


def normalize_markdown(text: str, *, strip_hash_prefix: bool = False) -> str:
    if strip_hash_prefix:
        text = _strip_hash_prefix_lines(text)

    # Replace HTML non-breaking spaces with normal spaces so markdown renders naturally.
    text = text.replace("&nbsp;", " ")

    # Collapse double backslashes that were introduced by string escaping.
    text = text.replace("\\\\", "\\")

    # Unescape markdown punctuation.
    text = _MD_UNESCAPE_RE.sub(r"\1", text)

    # Convert initial banner comment blocks into normal markdown text.
    text = _decomment_initial_block(text)
    return text


def iter_markdown_files(root: Path) -> list[Path]:
    return sorted([p for p in root.rglob("*.md") if p.is_file()])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Normalize machine-escaped markdown in-place.")
    p.add_argument("--root", default=".", help="Root directory to scan (default: .).")
    p.add_argument("--dry-run", action="store_true", help="Do not write files; report changes only.")
    args = p.parse_args(argv)

    root = Path(args.root).resolve()
    changed: list[Path] = []

    for path in iter_markdown_files(root):
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        strip_hash_prefix = path.name.upper() == "BUILD_MANIFEST.MD"
        needs = (
            strip_hash_prefix
            or _looks_machine_escaped(raw)
            or _looks_banner_commented(raw)
            or "&nbsp;" in raw
            or "\\\\" in raw
        )
        if not needs:
            continue

        new = normalize_markdown(raw, strip_hash_prefix=strip_hash_prefix)
        if new == raw:
            continue

        changed.append(path)
        if not args.dry_run:
            path.write_text(new, encoding="utf-8", newline="\n")

    if args.dry_run:
        for pth in changed:
            print(pth.as_posix())
    print(f"normalized={len(changed)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
