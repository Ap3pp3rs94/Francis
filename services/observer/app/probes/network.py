from __future__ import annotations

import socket
from contextlib import closing


def _tcp_reachable(host: str, port: int, timeout: float = 0.25) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def collect() -> dict:
    hostname = socket.gethostname()
    try:
        primary_ip = socket.gethostbyname(hostname)
    except OSError:
        primary_ip = None
    return {
        "hostname": hostname,
        "primary_ip": primary_ip,
        "loopback_8000_reachable": _tcp_reachable("127.0.0.1", 8000),
    }
