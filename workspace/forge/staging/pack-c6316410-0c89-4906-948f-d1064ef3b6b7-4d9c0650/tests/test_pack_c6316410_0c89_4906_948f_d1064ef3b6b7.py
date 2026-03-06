from __future__ import annotations

from pack_c6316410_0c89_4906_948f_d1064ef3b6b7 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
