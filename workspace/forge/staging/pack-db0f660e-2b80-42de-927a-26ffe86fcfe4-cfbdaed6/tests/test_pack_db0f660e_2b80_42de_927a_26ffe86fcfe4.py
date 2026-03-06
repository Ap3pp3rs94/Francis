from __future__ import annotations

from pack_db0f660e_2b80_42de_927a_26ffe86fcfe4 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
