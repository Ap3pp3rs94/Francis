from __future__ import annotations

import csv
import os
import subprocess
from collections import Counter


def _windows_tasklist() -> list[dict[str, str]]:
    proc = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    rows: list[dict[str, str]] = []
    if proc.returncode != 0:
        return rows
    reader = csv.reader(proc.stdout.splitlines())
    for row in reader:
        if len(row) < 5:
            continue
        rows.append(
            {
                "image_name": row[0],
                "pid": row[1],
                "session_name": row[2],
                "session_num": row[3],
                "mem_usage": row[4],
            }
        )
    return rows


def _posix_ps() -> list[dict[str, str]]:
    proc = subprocess.run(
        ["ps", "-eo", "pid,comm"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    rows: list[dict[str, str]] = []
    if proc.returncode != 0:
        return rows
    lines = proc.stdout.splitlines()[1:]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        pid, _, comm = line.partition(" ")
        rows.append({"pid": pid.strip(), "image_name": comm.strip()})
    return rows


def collect() -> dict:
    rows = _windows_tasklist() if os.name == "nt" else _posix_ps()
    counter = Counter(item.get("image_name", "unknown") for item in rows)
    top = [{"image_name": name, "count": count} for name, count in counter.most_common(5)]
    return {"total_processes": len(rows), "top_image_names": top}
