from __future__ import annotations

from stage_a4da15be_2ca7_4183_9bd7_522411c8557e import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
