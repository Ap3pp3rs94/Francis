from __future__ import annotations

from typing import Any


def detect(snapshot: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []

    disk = snapshot.get("disk", {})
    disk_free = disk.get("free_percent")
    if isinstance(disk_free, (int, float)) and disk_free < float(baseline["disk_free_percent_min"]):
        severity = "critical" if disk_free < 5.0 else "warning"
        anomalies.append(
            {
                "kind": "disk.low_free_space",
                "severity": severity,
                "message": f"Disk free space is low ({disk_free:.2f}%).",
                "evidence": {"free_percent": disk_free},
            }
        )

    memory = snapshot.get("memory", {})
    mem_available = memory.get("available_percent")
    if isinstance(mem_available, (int, float)) and mem_available < float(baseline["memory_available_percent_min"]):
        severity = "critical" if mem_available < 5.0 else "warning"
        anomalies.append(
            {
                "kind": "memory.low_available",
                "severity": severity,
                "message": f"Available memory is low ({mem_available:.2f}%).",
                "evidence": {"available_percent": mem_available},
            }
        )

    repo = snapshot.get("repo", {})
    dirty_files = repo.get("dirty_files")
    if isinstance(dirty_files, int) and dirty_files > int(baseline["repo_dirty_files_warn"]):
        anomalies.append(
            {
                "kind": "repo.high_drift",
                "severity": "warning",
                "message": f"Repository has high local drift ({dirty_files} dirty files).",
                "evidence": {"dirty_files": dirty_files},
            }
        )

    cpu = snapshot.get("cpu", {})
    normalized_load = cpu.get("normalized_load_percent")
    if isinstance(normalized_load, (int, float)) and normalized_load > float(baseline["cpu_normalized_load_warn"]):
        anomalies.append(
            {
                "kind": "cpu.high_load",
                "severity": "warning",
                "message": f"CPU normalized load is high ({normalized_load:.2f}%).",
                "evidence": {"normalized_load_percent": normalized_load},
            }
        )

    return anomalies
