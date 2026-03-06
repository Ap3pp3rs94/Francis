from __future__ import annotations

from stage_98344533_7585_494e_b8dd_eee959014673 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
