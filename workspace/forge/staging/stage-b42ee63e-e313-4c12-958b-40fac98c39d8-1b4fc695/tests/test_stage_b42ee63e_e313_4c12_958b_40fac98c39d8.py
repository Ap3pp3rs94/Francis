from __future__ import annotations

from stage_b42ee63e_e313_4c12_958b_40fac98c39d8 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
