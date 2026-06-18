from __future__ import annotations

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from powershell_script_runner import run_powershell_script


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lens-command-palette-monitor.ps1"


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    assert exe is not None, "PowerShell is required for script tests"
    return exe


def _run_monitor(*args: str):
    return run_powershell_script(
        _powershell(),
        SCRIPT,
        list(args),
        cwd=ROOT,
        timeout_seconds=45,
    )


def _lens_status(*, command_total: int = 2) -> dict[str, object]:
    commands = [
        {"id": "voice_status", "label": "Voice status"},
        {"id": "open_lens", "label": "Open Lens"},
    ][:command_total]
    return {
        "ok": True,
        "kind": "lens.status",
        "command_palette": {
            "status": "readback_ready",
            "availability": "local_ui",
            "route": "/lens/status",
            "local_surface": "lens.status.command_palette",
            "url_entrypoint_ready": True,
            "url_entrypoint": {
                "kind": "lens.command_palette.url_entrypoint",
                "status": "ready",
                "route": "/?francis_lens=command_palette",
                "local_surface": "chat_ui.command_palette",
                "opens_palette_in_chat_ui": True,
                "requires_running_chat_ui": True,
                "os_level_command_palette": False,
                "summon_anywhere": False,
                "global_hotkey": False,
            },
            "commands": commands,
            "command_total": command_total,
            "summon_anywhere": False,
        },
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _json_stdout(stdout: str) -> dict[str, object]:
    return json.loads(stdout)


class _CommandPaletteHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = b'<!doctype html><html><body><div id="root"></div></body></html>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return None


class _LocalCommandPaletteServer:
    def __enter__(self) -> str:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _CommandPaletteHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        port = self._server.server_address[1]
        return f"http://127.0.0.1:{port}/?francis_lens=command_palette"

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._server.server_close()


def test_lens_command_palette_monitor_probe_records_healthy_status(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr
    payload = _json_stdout(proc.stdout)
    assert payload["ok"] is True
    assert payload["status"] == "healthy"
    assert payload["anomaly_count"] == 0
    assert payload["bridge"]["readback_ready"] is True
    assert payload["bridge"]["route"] == "/?francis_lens=command_palette"
    assert payload["bridge"]["local_surface"] == "chat_ui.command_palette"
    assert payload["bridge"]["command_total"] == 2
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False

    recorded_status = data_dir / "runtime" / "lens-command-palette-monitor" / "status.json"
    assert recorded_status.exists()
    assert json.loads(recorded_status.read_text(encoding="utf-8"))["status"] == "healthy"
    anomaly_log = data_dir / "runtime" / "lens-command-palette-monitor" / "anomalies.jsonl"
    assert not anomaly_log.exists()


def test_lens_command_palette_monitor_probe_writes_anomaly_receipt(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status(command_total=0))

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 1
    payload = _json_stdout(proc.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "anomaly"
    assert payload["anomaly_count"] >= 1
    assert "command_palette_commands" in {item["id"] for item in payload["anomalies"]}

    anomaly_log = data_dir / "runtime" / "lens-command-palette-monitor" / "anomalies.jsonl"
    assert anomaly_log.exists()
    logged = [json.loads(line) for line in anomaly_log.read_text(encoding="utf-8").splitlines()]
    assert logged[-1]["status"] == "anomaly"
