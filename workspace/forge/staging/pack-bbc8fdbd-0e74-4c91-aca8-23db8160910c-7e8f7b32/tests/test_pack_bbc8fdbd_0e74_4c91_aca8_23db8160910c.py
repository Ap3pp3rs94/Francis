from __future__ import annotations

from pack_bbc8fdbd_0e74_4c91_aca8_23db8160910c import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
