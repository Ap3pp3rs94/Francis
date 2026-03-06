from __future__ import annotations

from pack_57a9ab73_9f7d_45ac_a09b_f1b05dfd19c0 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
