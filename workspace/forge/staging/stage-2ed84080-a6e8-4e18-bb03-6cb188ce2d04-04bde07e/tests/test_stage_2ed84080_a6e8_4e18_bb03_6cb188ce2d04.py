from __future__ import annotations

from stage_2ed84080_a6e8_4e18_bb03_6cb188ce2d04 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
