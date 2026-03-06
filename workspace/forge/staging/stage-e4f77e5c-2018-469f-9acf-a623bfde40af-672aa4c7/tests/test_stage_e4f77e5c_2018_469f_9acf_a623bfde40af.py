from __future__ import annotations

from stage_e4f77e5c_2018_469f_9acf_a623bfde40af import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
