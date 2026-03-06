from __future__ import annotations

from pack_236ec887_ece6_41da_a1dc_c3cd71d57526 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
