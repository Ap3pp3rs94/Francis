from __future__ import annotations

from stage_5fba01c1_9c4d_48f6_b641_efa38f9df521 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
