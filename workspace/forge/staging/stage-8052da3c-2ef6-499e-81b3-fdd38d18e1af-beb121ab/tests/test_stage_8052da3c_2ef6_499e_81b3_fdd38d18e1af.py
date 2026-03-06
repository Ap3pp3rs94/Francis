from __future__ import annotations

from stage_8052da3c_2ef6_499e_81b3_fdd38d18e1af import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
