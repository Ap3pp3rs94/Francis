from __future__ import annotations

from stage_047a7402_1bbd_4162_8ea7_07ecb893f947 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
