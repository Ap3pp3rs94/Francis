from __future__ import annotations

from pack_fe55688c_ff4c_4c32_af7d_bdacffc6c7bc import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
