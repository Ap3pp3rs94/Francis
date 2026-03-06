from __future__ import annotations

from pack_777a9d13_420c_4715_a082_628f932c822d import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
