from __future__ import annotations

from pack_fefa2a53_a1ed_4039_872e_efd1e0781a8f import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
