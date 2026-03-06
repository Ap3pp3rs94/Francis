from __future__ import annotations

from pack_9b790795_49d5_4db7_9742_8ebf7bea66c6 import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
