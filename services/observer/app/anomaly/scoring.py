from __future__ import annotations

from typing import Any

SEVERITY_WEIGHTS = {
    "info": 1,
    "warning": 3,
    "critical": 8,
}


def score(anomalies: list[dict[str, Any]]) -> dict[str, Any]:
    if not anomalies:
        return {
            "level": "healthy",
            "total_score": 0,
            "critical_count": 0,
            "warning_count": 0,
            "headline": "No anomalies detected.",
        }

    total = 0
    critical_count = 0
    warning_count = 0
    for item in anomalies:
        sev = str(item.get("severity", "info"))
        total += SEVERITY_WEIGHTS.get(sev, 1)
        if sev == "critical":
            critical_count += 1
        elif sev == "warning":
            warning_count += 1

    level = "critical" if critical_count > 0 else "warning"
    headline = (
        f"{critical_count} critical anomaly(s) detected."
        if critical_count > 0
        else f"{warning_count} warning anomaly(s) detected."
    )
    return {
        "level": level,
        "total_score": total,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "headline": headline,
    }
