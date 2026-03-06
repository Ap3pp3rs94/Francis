from __future__ import annotations

from stage_92787836_b4d1_4a22_89c7_f43168a510b2 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
