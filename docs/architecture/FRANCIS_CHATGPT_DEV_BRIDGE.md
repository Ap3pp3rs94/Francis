# Francis ChatGPT Developer Bridge

## Status

`v0.1` is a read-only verification surface. It is not an autonomy upgrade and it is not a write-capable operator bridge.

## Roadmap fit

This slice supports the current substrate priority of making Francis's governed runtime loop more visible and checkable:

- `P1_INTERFACE`: gives ChatGPT Developer Mode / MCP a small, explicit interface surface.
- `P3_GOVERNANCE`: keeps bridge behavior bounded, read-only, and deny-by-default for sensitive paths.
- `P7_EXECUTION`: exposes supervised-exec receipts as evidence, not as authority.
- `P9_OBSERVABILITY`: makes repo status, ledger state, and diff summaries inspectable.

## Contract

The bridge may read only bounded repo truth and bounded supervised-exec display artifacts. It must not mutate repository state, shell state, external services, credentials, or operator data.

Allowed v0.1 operations:

- read current repo status
- read a non-sensitive UTF-8 repo file by repo-relative path
- search non-sensitive UTF-8 repo files
- read Git status and diff summaries without patch text
- read the completion ledger
- read allowlisted supervised-exec receipt files by run id

Denied v0.1 operations:

- arbitrary shell
- patch application
- file writes
- commits
- pushes
- outside-repo file reads
- `.env`, `.npmrc`, `.pypirc`, key/certificate material, and `.ssh` paths
- path traversal
- external account actions

## HTTP API

Mounted under `/developer-bridge`:

- `GET /developer-bridge/status`
- `GET /developer-bridge/read-file?path=README.md`
- `GET /developer-bridge/search?query=needle`
- `GET /developer-bridge/git-diff-summary`
- `GET /developer-bridge/completion-ledger`
- `GET /developer-bridge/supervised-exec-receipt?run_id=<run_id>&filename=result.json`

## Optional MCP wrapper

`src/francis/developer_bridge/mcp_server.py` exposes the same read-only tools behind an optional MCP server.

Install with the bridge extra once the dependency is accepted into the local environment:

```powershell
pip install -e ".[bridge,web,dev]"
```

Default transport:

```powershell
$env:FRANCIS_DEV_BRIDGE_TRANSPORT = "streamable-http"
python -m francis.developer_bridge.mcp_server
```

## Operating rule

Receipts are claims until checked against repo status, diff summaries, and validation logs. ChatGPT may use this bridge to audit evidence, but it must not infer write authority from read access.

## Validation

Narrow validation for this slice:

```powershell
python -m compileall src/francis/developer_bridge src/francis/api/routes/developer_bridge.py
python -m pytest tests/test_developer_bridge.py
python -m ruff check src/francis/developer_bridge src/francis/api/routes/developer_bridge.py tests/test_developer_bridge.py
python -m mypy src/francis/developer_bridge src/francis/api/routes/developer_bridge.py
```

Full repo validation before merge when practical:

```powershell
.\scripts\check.ps1
```
