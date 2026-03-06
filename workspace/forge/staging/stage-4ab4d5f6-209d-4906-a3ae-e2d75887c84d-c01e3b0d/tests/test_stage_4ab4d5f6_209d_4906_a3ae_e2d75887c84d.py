from __future__ import annotations

from stage_4ab4d5f6_209d_4906_a3ae_e2d75887c84d import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
