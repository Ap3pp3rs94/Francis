from __future__ import annotations

from stage_219f8549_e3dc_4fb4_96dd_a460193328b7 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
