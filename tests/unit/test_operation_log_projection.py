from __future__ import annotations


def test_operation_log_projection_promotes_approval_receipt_handle() -> None:
    from francis.api.routes.operations import _event_to_operation

    projected = _event_to_operation(
        "tsk_audit_projection",
        0,
        {
            "ts": "2026-04-26T12:00:00+00:00",
            "event": "status_updated",
            "details": {
                "to": "complete",
                "approval_id": "apr_audit_projection",
                "trace_id": "trace_audit_projection",
                "run_id": "run_audit_projection",
                "artifact_dir": "D:/Francis/.data/artifacts/audit_projection",
            },
        },
    )

    assert projected["approval_id"] == "apr_audit_projection"
    assert projected["trace_id"] == "trace_audit_projection"
    assert projected["run_id"] == "run_audit_projection"
    assert projected["artifact_dir"] == "D:/Francis/.data/artifacts/audit_projection"
    assert projected["meta"]["approval_id"] == "apr_audit_projection"
    assert projected["output"]["approval_id"] == "apr_audit_projection"
