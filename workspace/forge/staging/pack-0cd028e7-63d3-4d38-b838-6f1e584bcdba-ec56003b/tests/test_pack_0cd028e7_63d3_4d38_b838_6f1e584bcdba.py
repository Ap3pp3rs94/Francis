from __future__ import annotations

from pack_0cd028e7_63d3_4d38_b838_6f1e584bcdba import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
