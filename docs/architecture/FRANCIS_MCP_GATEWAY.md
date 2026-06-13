# Francis MCP Gateway v0

Francis MCP Gateway is a governed local ingress surface for MCP-capable AI clients.

It is not raw shell access and not raw PC control.

The intended path is:

```text
AI client
  -> MCP gateway
  -> Francis tool contract
  -> policy/readback/approval boundary
  -> bounded local action
  -> receipt/readback
```

## v0 tools

- `francis.health`
- `francis.repo.status`
- `francis.git.diff`
- `francis.tests.run_targeted`
- `francis.command.propose`
- `francis.command.execute_approved`
- `francis.receipts.readback`

## Security posture

The gateway refuses arbitrary shell strings. Bounded execution is assembled from allowlisted command kinds and typed arguments.

Manual approval is represented by the phrase:

```text
APPROVE <proposal_id>
```

That is intentionally explicit for v0. It is not a replacement for full Francis approval UI; it is a temporary local-human approval gate for Codex-outage operation.

## Running the dependency-free contract tests

```powershell
python -m pytest tests/unit/test_mcp_gateway.py
python -m ruff check src/francis/mcp_gateway tests/unit/test_mcp_gateway.py
python -m ruff format --check src/francis/mcp_gateway tests/unit/test_mcp_gateway.py
python -m mypy src/francis/mcp_gateway
```

## Running as an MCP stdio server

Install an MCP SDK package that exposes `mcp.server.fastmcp.FastMCP`, then run:

```powershell
python -m francis.mcp_gateway.server
```

If the optional MCP package is missing, the adapter fails truthfully instead of pretending to run.
