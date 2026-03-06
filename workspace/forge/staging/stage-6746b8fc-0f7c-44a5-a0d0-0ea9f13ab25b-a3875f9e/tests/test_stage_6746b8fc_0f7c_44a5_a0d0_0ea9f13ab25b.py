from __future__ import annotations

from stage_6746b8fc_0f7c_44a5_a0d0_0ea9f13ab25b import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
