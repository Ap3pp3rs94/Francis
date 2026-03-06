from __future__ import annotations

from stage_e9c0c629_8f49_49a7_bea7_f3ecc43c61a2 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
