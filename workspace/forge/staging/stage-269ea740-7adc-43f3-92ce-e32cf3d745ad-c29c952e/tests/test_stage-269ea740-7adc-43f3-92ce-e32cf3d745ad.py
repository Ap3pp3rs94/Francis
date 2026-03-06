from __future__ import annotations

from stage-269ea740-7adc-43f3-92ce-e32cf3d745ad import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
