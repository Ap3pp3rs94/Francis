from __future__ import annotations

import os


def collect() -> dict:
    cores = os.cpu_count() or 1
    load_avg_1 = None
    normalized_load_percent = None
    if hasattr(os, "getloadavg"):
        la1, _la5, _la15 = os.getloadavg()
        load_avg_1 = float(la1)
        normalized_load_percent = round((la1 / cores) * 100.0, 2)
    return {
        "logical_cores": int(cores),
        "load_avg_1": load_avg_1,
        "normalized_load_percent": normalized_load_percent,
    }
