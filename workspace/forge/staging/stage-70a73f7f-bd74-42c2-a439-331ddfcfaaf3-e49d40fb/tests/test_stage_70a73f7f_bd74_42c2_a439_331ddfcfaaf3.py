from __future__ import annotations

from stage_70a73f7f_bd74_42c2_a439_331ddfcfaaf3 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
