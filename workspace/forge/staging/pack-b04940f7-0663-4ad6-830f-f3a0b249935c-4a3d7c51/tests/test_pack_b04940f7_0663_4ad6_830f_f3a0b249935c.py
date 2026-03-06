from __future__ import annotations

from pack_b04940f7_0663_4ad6_830f_f3a0b249935c import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
