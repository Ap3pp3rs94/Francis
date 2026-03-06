from __future__ import annotations

from pack_2f05b481_3664_4934_b10c_c923244a1704 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
