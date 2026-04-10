from __future__ import annotations


def run_daemon() -> None:
    from francis.daemon.runner import run_daemon as _run

    _run()
