from __future__ import annotations

from pack_33536910_8258_4e35_a31c_b9d6e1539f1a import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
