from __future__ import annotations

from stage_54360577_4a1a_48bf_92a2_c82a769232f3 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
