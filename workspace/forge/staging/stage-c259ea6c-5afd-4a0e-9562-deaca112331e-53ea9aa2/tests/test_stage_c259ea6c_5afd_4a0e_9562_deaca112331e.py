from __future__ import annotations

from stage_c259ea6c_5afd_4a0e_9562_deaca112331e import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
