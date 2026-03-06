from __future__ import annotations

from stage_a44c902a_660a_4f65_8954_c9dbbb5e750a import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
