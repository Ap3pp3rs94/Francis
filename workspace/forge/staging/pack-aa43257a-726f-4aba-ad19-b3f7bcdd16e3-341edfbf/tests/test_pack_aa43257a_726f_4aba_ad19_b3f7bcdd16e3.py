from __future__ import annotations

from pack_aa43257a_726f_4aba_ad19_b3f7bcdd16e3 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
