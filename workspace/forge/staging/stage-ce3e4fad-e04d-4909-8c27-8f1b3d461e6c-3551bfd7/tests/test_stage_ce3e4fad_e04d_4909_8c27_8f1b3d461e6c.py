from __future__ import annotations

from stage_ce3e4fad_e04d_4909_8c27_8f1b3d461e6c import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
