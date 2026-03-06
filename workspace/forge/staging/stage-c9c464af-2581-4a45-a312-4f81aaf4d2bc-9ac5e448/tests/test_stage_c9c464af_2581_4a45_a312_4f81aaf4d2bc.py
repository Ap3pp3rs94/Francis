from __future__ import annotations

from stage_c9c464af_2581_4a45_a312_4f81aaf4d2bc import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
