# Francis Substrate Operating Contract

`D:\Francis` is the active project substrate and the primary source of truth for
work performed in this workspace.

## Startup procedure

At the beginning of every substantial task:

1. Inspect the relevant top-level folders and current repository state.
2. Read this file and any nested `CLAUDE.md` files that apply to the target.
3. Locate relevant roadmaps, ledgers, architecture notes, schemas, reports,
   decision records, tests, and handoff artifacts.
4. Identify the actual entry points, dependencies, services, storage layers, and
   downstream consumers involved.
5. Trace the current implementation before proposing or making changes.
6. Record uncertainty instead of inventing missing details.

## Working rule

Use the substrate directly to determine what the task needs. Reuse existing
modules, services, types, schemas, scripts, automation, test harnesses, browser
sessions, local services, conventions, and integrations when they provide the
correct path.

Do not create a parallel implementation merely because it is easier to start
from scratch. Do not assume an existing implementation is correct merely because
it exists. Repair or extend the narrowest proven root cause while accounting for
all consumers of shared contracts.

## End-to-end responsibility

For relevant changes, check the full applicable path:

UI and navigation
→ route and component
→ handler and state
→ client service and API contract
→ authentication and authorization
→ validation and business logic
→ repository and database
→ jobs, integrations, or downstream modules
→ response, cache, and visible behavior
→ tests and regression coverage

Do not declare success from a single passing layer.

## Autonomy

Perform safe discovery, implementation, and verification without repeatedly
asking for permission. Use available tools and evidence to resolve ordinary
ambiguity.

Escalate only actions that are destructive, irreversible, production-changing,
externally public, financially consequential, credential-related, or dependent
on a nontechnical business decision.

## Task modes

Task-specific instructions control mutation authority:

- `audit only` or `read-only`: inspect and validate without changing protected
  source or data.
- `implement`, `repair`, or equivalent: make the required changes and validate
  them end to end.
- When mutation authority is unclear, prefer reversible work and preserve a
  checkpoint.

## Security and integrity

Never expose secrets or private data. Do not bypass established authentication,
authorization, validation, transaction, tenant-isolation, audit, or logging
controls. Do not run state-changing operations against production unless the
task explicitly authorizes the exact action.

## Completion standard

A task is complete only when the requested outcome is implemented or fully
audited, relevant validation has been performed, connected systems have been
checked for regressions, and remaining blockers or uncertainty are stated
plainly.
