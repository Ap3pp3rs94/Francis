from __future__ import annotations

from pack_b7503e1c_9cd4_45c8_b683_423858667776 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
