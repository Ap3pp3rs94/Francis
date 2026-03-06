from __future__ import annotations

from stage_c4e665d2_902f_4fa7_8c7f_a87444dc783e import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
