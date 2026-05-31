from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_trust_calibration_browser_readback_runner_contract_is_bounded() -> None:
    proc = subprocess.run(
        [
            "node",
            str(_repo_root() / "scripts" / "trust-calibration-browser-readback.mjs"),
            "--print-contract",
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert proc.returncode == 0, proc.stderr
    contract = json.loads(proc.stdout)
    assert contract["kind"] == "francis.stage13.trust_calibration.browser_readback_runner_contract"
    assert contract["target"] == "stage13_operator_browser_visual_readback"
    assert contract["actor"] == "chat_ui.trust_calibration"
    assert contract["required_scope"] == "trust_calibration.browser_visual_readback.write"
    assert contract["ui_surface_id"] == "francis-trust-calibration"
    assert contract["receipt_route"] == "/trust-calibration/operator-browser-visual-readback"
    assert contract["writes_receipt"] == "only_after_browser_visible_signals_are_observed_and_ui_action_succeeds"
    assert contract["closes_stage"] is False
    assert contract["writes_memory"] is False
    assert contract["grants_execution_authority"] is False
    assert contract["grants_mutation_authority"] is False
    assert "Stage 13 calibration" in contract["required_visible_signals"]
    assert "Record visual readback" in contract["required_visible_signals"]
    assert "stage13_operator_browser_visual_readback" in contract["required_visible_signals"]


def test_trust_calibration_browser_readback_runner_parses_as_javascript() -> None:
    proc = subprocess.run(
        ["node", "--check", str(_repo_root() / "scripts" / "trust-calibration-browser-readback.mjs")],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert proc.returncode == 0, proc.stderr
