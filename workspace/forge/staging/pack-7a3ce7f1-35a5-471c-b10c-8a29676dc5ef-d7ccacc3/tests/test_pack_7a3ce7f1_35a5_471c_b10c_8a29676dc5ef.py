from __future__ import annotations

from pack_7a3ce7f1_35a5_471c_b10c_8a29676dc5ef import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
