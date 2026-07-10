from __future__ import annotations

import json
from pathlib import Path


def test_tail_reads_recent_entries_without_full_file_read(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    ledger_path = data_root / "conversations" / "ledger" / "ledger.jsonl"
    ledger_path.parent.mkdir(parents=True)
    with ledger_path.open("w", encoding="utf-8") as handle:
        for index in range(2_000):
            handle.write(
                json.dumps(
                    {
                        "ts": float(index),
                        "role": "system",
                        "content": f"entry-{index}",
                        "meta": {"padding": "x" * 512},
                    }
                )
                + "\n"
            )

    original_read_text = Path.read_text

    def fail_full_ledger_read(self: Path, *args: object, **kwargs: object) -> str:
        if self == ledger_path:
            raise AssertionError("tail() must not read the full continuity ledger")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_full_ledger_read)

    from francis.chat.continuity.ledger import tail

    entries = tail(limit=3)

    assert [entry["content"] for entry in entries] == ["entry-1997", "entry-1998", "entry-1999"]


def test_tail_reuses_cache_until_ledger_file_changes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    ledger_path = data_root / "conversations" / "ledger" / "ledger.jsonl"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text(
        "\n".join(
            json.dumps({"ts": float(index), "role": "system", "content": f"entry-{index}", "meta": {}})
            for index in range(5)
        )
        + "\n",
        encoding="utf-8",
    )

    from francis.chat.continuity import ledger as ledger_module

    ledger_module._TAIL_CACHE.clear()
    original_tail_lines = ledger_module._tail_lines
    calls = 0

    def counted_tail_lines(path: Path, *, limit: int) -> list[str]:
        nonlocal calls
        calls += 1
        return original_tail_lines(path, limit=limit)

    monkeypatch.setattr(ledger_module, "_tail_lines", counted_tail_lines)

    assert [entry["content"] for entry in ledger_module.tail(limit=2)] == ["entry-3", "entry-4"]
    assert [entry["content"] for entry in ledger_module.tail(limit=2)] == ["entry-3", "entry-4"]
    assert calls == 1

    ledger_module.append("system", "entry-5", {})

    assert [entry["content"] for entry in ledger_module.tail(limit=2)] == ["entry-4", "entry-5"]
    assert calls == 2
