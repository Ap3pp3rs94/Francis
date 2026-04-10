from __future__ import annotations

from pathlib import Path

import pytest

from tools.replace_doc_block import replace_doc_block


def test_replace_doc_block_replaces_inclusive_start_exclusive_end(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("a\nSTART\nold1\nold2\nEND\nb\n", encoding="utf-8")

    template = tmp_path / "tmpl.md"
    template.write_text("START\nnew1\nnew2\n", encoding="utf-8")

    replace_doc_block(file=doc, start="START", end="END", template_file=template)

    assert doc.read_text(encoding="utf-8") == "a\nSTART\nnew1\nnew2\nEND\nb\n"


def test_replace_doc_block_missing_start_raises(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("a\nnope\nEND\nb\n", encoding="utf-8")

    template = tmp_path / "tmpl.md"
    template.write_text("START\nnew\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Start marker not found"):
        replace_doc_block(file=doc, start="START", end="END", template_file=template)


def test_replace_doc_block_missing_end_raises(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("a\nSTART\nold\nb\n", encoding="utf-8")

    template = tmp_path / "tmpl.md"
    template.write_text("START\nnew\n", encoding="utf-8")

    with pytest.raises(ValueError, match="End marker not found"):
        replace_doc_block(file=doc, start="START", end="END", template_file=template)
