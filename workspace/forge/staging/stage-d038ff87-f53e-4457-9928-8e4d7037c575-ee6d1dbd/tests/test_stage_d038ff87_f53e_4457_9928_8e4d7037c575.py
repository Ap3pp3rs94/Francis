from __future__ import annotations

from stage_d038ff87_f53e_4457_9928_8e4d7037c575 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
