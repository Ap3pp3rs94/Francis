from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

import pytest

from francis.windows_named_mutex import WindowsNamedMutex


@pytest.mark.skipif(os.name != "nt", reason="Windows named mutex proof requires Windows")
def test_windows_named_mutex_serializes_child_process() -> None:
    scope = f"test|{uuid.uuid4().hex}"
    parent = WindowsNamedMutex(scope=scope, timeout_ms=1_000)
    acquired = parent.acquire()
    assert acquired.acquired is True

    blocked = _run_child(scope=scope, timeout_ms=100)
    assert blocked["acquired"] is False
    assert blocked["status"] == "timeout"
    assert parent.release() == ""

    after_release = _run_child(scope=scope, timeout_ms=1_000)
    assert after_release["acquired"] is True
    assert after_release["release_error"] == ""


def _run_child(*, scope: str, timeout_ms: int) -> dict[str, object]:
    code = (
        "import json; "
        "from francis.windows_named_mutex import WindowsNamedMutex; "
        f"mutex=WindowsNamedMutex(scope={scope!r}, timeout_ms={timeout_ms}); "
        "result=mutex.acquire(); "
        "payload=result.to_dict(); "
        "payload['release_error']=mutex.release() if result.acquired else ''; "
        "print(json.dumps(payload))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict)
    return payload
