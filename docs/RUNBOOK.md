==============================================================================

FRANCIS — RUNBOOK.md

Operational runbooks, incident playbooks, and repeatable execution patterns

==============================================================================



Purpose

-------

This document defines how FRANCIS represents, generates, executes, and audits

runbooks and playbooks.



Runbooks are the bridge between:

   - policy (what is allowed),

   - permissions/trust/approvals (who can do it and when),

   - and operations (how we do it safely and repeatably).



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/POLICIES.md

   - docs/GOVERNANCE.md

   - docs/API_PERMISSIONS.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/CONCURRENCY.md

   - docs/WEB_ACCESS.md

   - docs/ATTACHMENTS.md

   - config/policies/action_readiness.yaml

   - config/policies/approvals.yaml

   - config/policies/filesystem.yaml

   - config/policies/networks.yaml

   - config/policies/sandbox.yaml

   - src/francis/agent/playbooks/*

   - src/francis/governance/*

   - src/francis/telemetry/*

   - schemas/*playbook* (if present) and action schemas in schemas/



Design stance

------------

   - A runbook is an executable specification with explicit constraints.

   - Runbooks must be safe-by-default: least privilege, explicit approvals,

     bounded blast radius, and postcondition verification.

   - Every runbook run is auditable and reproducible (or clearly marked when not).



==============================================================================





## 1. Definitions



### 1.1 Runbook

A **runbook** is a structured, repeatable procedure for achieving an outcome.

It may be:

- **human-executed** (steps for operators),

- **machine-executed** (FRANCIS executes tool calls),

- or **hybrid** (FRANCIS executes low-risk steps, operator approves high-risk steps).



### 1.2 Playbook

A **playbook** is a runbook optimized for dynamic, high-uncertainty contexts

(e.g., incident response) where branching, hypotheses, and evidence tracking

are first-class.



### 1.3 Step

A **step** is the smallest auditable unit in a runbook:

- inputs

- actions (tool operations)

- constraints

- expected outputs

- preconditions and postconditions



### 1.4 Preconditions and postconditions

- **Precondition**: must be true before executing a step.

- **Postcondition**: must be verified after executing a step.

If postconditions fail, the runbook must:

- stop,

- or branch into a recovery path,

- and record the failure.



### 1.5 Idempotence

A step is **idempotent** if it can be run multiple times without causing

unintended side effects. Idempotence is preferred for automation.



### 1.6 Blast radius

**Blast radius** is the maximum scope of damage a runbook can cause if wrong.

Runbooks must explicitly constrain blast radius:

- target resources

- permitted operations

- rate limits

- rollback plans

- timeouts





## 2. Where runbooks live



Runbooks may be stored in multiple places depending on purpose:



- **Templates / curated runbooks**:

  - `data/artifacts/runbooks/` (exports)

  - `specializations/*/_shared/playbooks/` (if you add them)

  - `src/francis/agent/playbooks/` (code-based builtins)



- **Generated runbooks (per task/session)**:

  - `data/artifacts/runbooks/` (persisted exports)

  - `data/conversations/*` (referenced in ledger with hashes)



- **Runbook execution traces**:

  - `data/logs/operations/*`

  - `data/logs/audit/*`

  - `data/artifacts/reports/*` (post-run reports)



A runbook should always be linkable from the conversation ledger entry that

triggered it.





## 3. Runbook lifecycle



1) **Intake**

   - capture goal + constraints

   - classify sensitivity and risk



2) **Draft generation**

   - propose steps

   - identify required tools and data

   - determine approvals required



3) **Policy \& permission compilation**

   - map steps → tool operations

   - verify policy eligibility

   - bind to delegation/scope requirements



4) **Review**

   - safety review (especially for write/destructive steps)

   - optional human review



5) **Execution**

   - run steps with governance gates at each step

   - log each tool call + decision + redactions



6) **Verification**

   - validate postconditions

   - record outcomes and evidence



7) **Closeout**

   - produce final report

   - update trust metrics (success/failure)

   - optionally export as a reusable template





## 4. Runbook format (recommended schema)



Runbooks should be machine-checkable and exportable (YAML or JSON).



Recommended top-level fields:



- `runbook_id` (stable id; include namespace)

- `title`

- `version`

- `created_at`

- `created_by` (identity/role)

- `description`

- `tags` (incident_response, maintenance, onboarding, etc.)

- `environment_constraints` (allowed environments)

- `risk_profile`

  - `max_risk_level`

  - `requires_approval_for` (write/delete/network changes/etc.)

- `required_tools` (by tool name)

- `required_scopes` (scope ids)

- `inputs` (parameters required)

- `steps` (ordered)

- `rollback` (optional global plan)

- `verification` (global postconditions)

- `artifacts` (expected outputs)

- `audit`

  - `audit_level`

  - `redaction_profile`

  - `evidence_requirements`



### 4.1 Step schema (recommended)

Each step should include:



- `step_id`

- `title`

- `intent`

- `inputs`

- `actions`:

  - `tool`

  - `operation`

  - `params` (templated)

- `constraints`

  - rate limits

  - max results

  - allowlists (domains, repos, channels, db tables)

  - filesystem paths

- `preconditions`

- `postconditions`

- `on_failure`

  - `halt`

  - `branch_to`

  - `rollback_step`

- `notes_for_human` (if hybrid)



### 4.2 Example runbook snippet (illustrative)



```yaml

runbook_id: ops.backup.verify_latest

title: Verify latest backup exists and is restorable

version: 1.0.0

environment_constraints:

  allowed: ["dev", "production"]

risk_profile:

  max_risk_level: "medium"

required_tools: ["filesystem", "process", "db"]

steps:

  - step_id: s1

    title: Locate latest backup artifact

    intent: Find the newest backup file in the backups directory.

    actions:

      - tool: filesystem

        operation: list_dir

        params:

          path: "{{backup_dir}}"

    constraints:

      filesystem_allowlist:

        - "{{backup_dir}}"

      max_results: 2000

    postconditions:

      - type: assert_nonempty

        field: "result.files"

    on_failure:

      halt: true



  - step_id: s2

    title: Restore to staging and run smoke checks

    intent: Validate backup integrity without touching production.

    actions:

      - tool: db

        operation: restore_backup

        params:

          backup_file: "{{s1.latest_file}}"

          target_env: "staging"

    constraints:

      requires_approval: true

      approval_type: "ops.restore"

    postconditions:

      - type: smoke_test

        command: "python -m tests.smoke"



