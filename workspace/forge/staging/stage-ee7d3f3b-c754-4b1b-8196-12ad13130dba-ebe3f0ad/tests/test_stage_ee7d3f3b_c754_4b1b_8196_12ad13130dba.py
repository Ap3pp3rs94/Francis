from __future__ import annotations

from stage_ee7d3f3b_c754_4b1b_8196_12ad13130dba import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
