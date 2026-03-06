from __future__ import annotations

from stage_3d021bde_af5f_4afe_a289_db9dc6638732 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
