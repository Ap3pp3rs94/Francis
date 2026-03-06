from __future__ import annotations

from stage_a5c3d2ba_d0dc_4f84_a9a5_c7102d9d8e89 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
