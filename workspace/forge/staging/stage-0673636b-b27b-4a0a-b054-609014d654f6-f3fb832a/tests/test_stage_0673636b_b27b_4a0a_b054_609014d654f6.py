from __future__ import annotations

from stage_0673636b_b27b_4a0a_b054_609014d654f6 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
