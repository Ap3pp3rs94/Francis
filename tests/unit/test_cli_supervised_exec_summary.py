from __future__ import annotations

from francis.__main__ import _print_supervised_exec_summary


def test_supervised_exec_summary_preserves_gate_and_trace_handles(capsys) -> None:
    _print_supervised_exec_summary(
        {
            "task_id": "tsk_cli_summary",
            "status": "complete",
            "status_reason": "",
            "result": {
                "ok": True,
                "data": {
                    "approval_id": "apr_cli_summary",
                    "trace_id": "trace_cli_summary",
                    "run_id": "run_cli_summary",
                    "artifact_dir": "D:/Francis/.data/artifacts/supervised_exec/run_cli_summary",
                },
            },
        }
    )

    summary = capsys.readouterr().err

    assert "SUMMARY: task_id=tsk_cli_summary status=complete ok=True" in summary
    assert "SUMMARY: approval_id=apr_cli_summary" in summary
    assert "SUMMARY: trace_id=trace_cli_summary" in summary
    assert "SUMMARY: run_id=run_cli_summary" in summary
    assert "SUMMARY: artifact_dir=D:/Francis/.data/artifacts/supervised_exec/run_cli_summary" in summary
