from __future__ import annotations

from pack_43362167_dae4_4a29_aafc_9adae7cc2d9e import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
