from __future__ import annotations

from stage_19caf1a9_f8e7_4c39_9ca3_e6f054684a48 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
