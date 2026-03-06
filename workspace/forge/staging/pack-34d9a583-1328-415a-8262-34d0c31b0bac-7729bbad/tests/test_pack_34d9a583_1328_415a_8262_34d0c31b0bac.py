from __future__ import annotations

from pack_34d9a583_1328_415a_8262_34d0c31b0bac import run

def test_run_returns_ok() -> None:
    out = run({"sample": True})
    assert out["status"] == "ok"
