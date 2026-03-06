from __future__ import annotations

from stage_ef93cbc8_d14d_4bb0_8337_0681c4609c63 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
