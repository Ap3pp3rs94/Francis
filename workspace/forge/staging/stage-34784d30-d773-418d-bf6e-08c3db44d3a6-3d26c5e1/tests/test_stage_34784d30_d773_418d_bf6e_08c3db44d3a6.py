from __future__ import annotations

from stage_34784d30_d773_418d_bf6e_08c3db44d3a6 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
