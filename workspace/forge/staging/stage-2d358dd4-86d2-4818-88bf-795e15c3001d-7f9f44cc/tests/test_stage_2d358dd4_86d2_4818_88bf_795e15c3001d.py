from __future__ import annotations

from stage_2d358dd4_86d2_4818_88bf_795e15c3001d import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
