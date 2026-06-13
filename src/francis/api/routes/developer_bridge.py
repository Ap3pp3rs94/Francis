from __future__ import annotations

from fastapi import APIRouter, Query

from francis.developer_bridge.repo_tools import (
    DeveloperBridgeError,
    git_diff_summary,
    read_completion_ledger,
    read_repo_file,
    read_supervised_exec_receipt,
    repo_status,
    search_repo,
)

router = APIRouter()


def _call_read_only(func, *args, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
    try:
        return func(*args, **kwargs)
    except DeveloperBridgeError as exc:
        return exc.to_dict()


@router.get("/status")
def status() -> dict[str, object]:
    return _call_read_only(repo_status)


@router.get("/read-file")
def read_file(
    path: str = Query(..., min_length=1),
    max_bytes: int = Query(256_000, ge=1, le=256_000),
) -> dict[str, object]:
    return _call_read_only(read_repo_file, path, max_bytes=max_bytes)


@router.get("/search")
def search(
    query: str = Query(..., min_length=1),
    max_results: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    return _call_read_only(search_repo, query, max_results=max_results)


@router.get("/git-diff-summary")
def diff_summary() -> dict[str, object]:
    return _call_read_only(git_diff_summary)


@router.get("/completion-ledger")
def completion_ledger(max_bytes: int = Query(256_000, ge=1, le=256_000)) -> dict[str, object]:
    return _call_read_only(read_completion_ledger, max_bytes=max_bytes)


@router.get("/supervised-exec-receipt")
def supervised_exec_receipt(
    run_id: str = Query(..., min_length=1),
    filename: str = Query("result.json", min_length=1),
    max_bytes: int = Query(256_000, ge=1, le=256_000),
) -> dict[str, object]:
    return _call_read_only(read_supervised_exec_receipt, run_id, filename=filename, max_bytes=max_bytes)
