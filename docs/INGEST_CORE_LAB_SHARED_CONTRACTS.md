# Ingest Subsystem Layer Contracts (INGEST → CORE → LAB → SHARED)

This document is the explicit architectural contract for the `src/francis/ingest/`
subsystem after the structure-alignment pass. It states what each layer **may**
and **may not** do, and records the **current compliance level** measured against
that contract. Compliance is rounded down where uncertain and is evidence-based,
not aspirational.

Layers map to packages:

- INGEST → `src/francis/ingest/ingest/`
- CORE → `src/francis/ingest/core/`
- LAB → `src/francis/ingest/lab/`
- SHARED → `src/francis/ingest/shared/`

Compliance tiers: **Compliant** · **Substantially compliant** (minor, documented
cross-cut) · **Partial** (a contract clause is materially crossed) ·
**Non-compliant**.

---

## INGEST — observation layer

**Contract**
- Observation only: source ingestion, parsing, fingerprinting, repo-map
  inspection, and capability-candidate generation as **data only**.
- MUST NOT execute repository code.
- MUST NOT promote capabilities or mutate lifecycle state.

**Members:** `source.py`, `repo_adapter.py`, `capabilities.py`

**Current compliance: Substantially compliant.**
- No execution and no promotion logic present. ✓
- Candidate generation produces records only (`CapabilityCandidateExtractor`). ✓
- Cross-cut: `repo_adapter.py` imports `francis.governance.redaction` (a
  repo-wide governance utility) for safe display. This is a cross-cutting
  concern, not an execution or lifecycle dependency, but it is a dependency on
  governance code from the observation layer. Documented, not yet removed.

---

## CORE — governance layer

**Contract**
- Governance, source/capability registries, receipts, and lifecycle decisions.
- MUST NOT execute repository code.

**Members:** `registry.py`, `service.py` (the `IngestService` orchestrator)

**Current compliance: Partial.**
- Registries, receipts, and lifecycle bookkeeping live here. ✓
- `IngestService` **orchestrates** execution: `run_lab_capability` gates and
  invokes the LAB executor (`detect_docker`, `SandboxExecutor`) and decides
  real-vs-simulated. The execution *mechanism* is in LAB, but the execution
  *control flow and authority gate* live in CORE. This is the deliberate
  consequence of keeping the 18.8k-line `IngestService` monolith whole rather
  than splitting it (a split would be a behavior-risk refactor). Recorded as a
  known, bounded crossing — CORE depends on LAB and INGEST.

---

## LAB — execution layer

**Contract**
- Sandboxed execution only, plus validation and rebuild/runtime operations.

**Members:** `lab.py` (boundary), `lab_runtime.py`

**Current compliance: Partial.**
- Sandboxed execution (`SandboxExecutor`), rebuild planning
  (`CapabilityRebuilder`), and deterministic validation (`validate_run`) are
  here. ✓ Imports only SHARED. ✓
- Cross-cut: `lab_runtime.py` also hosts `decide_promotion` (a **lifecycle
  decision**, contractually CORE) and `candidate_lab_safety` (a **governance
  policy**, contractually CORE). These were co-located with the runtime for
  cohesion but belong to CORE by this contract. Documented, not yet moved.

---

## SHARED — types layer

**Contract**
- Shared dataclasses, schemas, and utilities only. No behavior, no execution,
  no governance decisions.

**Members:** `models.py`

**Current compliance: Substantially compliant.**
- `models.py` is pure dataclasses with `to_dict`/`from_dict`. ✓
- Minor: several shared-shaped dataclasses (`CommandResult`, `RunOutcome`,
  `LabExecutionRunReceipt`) currently live in `lab/lab_runtime.py` rather than
  SHARED. They are LAB-local types today; promote to SHARED only if another
  layer needs them.

---

## Dependency direction (observed)

```
SHARED   ← (no intra-subsystem imports)
LAB      → SHARED
INGEST   → SHARED, (governance.redaction cross-cut)
CORE     → SHARED, INGEST, LAB, governance, kernel
```

Intended direction is `INGEST → CORE → LAB` with all layers consuming SHARED.
The observed reality inverts CORE→LAB (CORE orchestrates LAB) and CORE→INGEST,
because the orchestrator monolith lives in CORE. No reverse leakage exists in the
other direction: LAB does not import CORE, and INGEST imports neither CORE nor
LAB.

---

## Summary

| Layer  | Contract                          | Compliance              |
|--------|-----------------------------------|-------------------------|
| INGEST | observe only, no exec, no promote | Substantially compliant |
| CORE   | govern/registry/receipts, no exec | Partial (orchestrates exec) |
| LAB    | sandbox exec / validate / rebuild | Partial (hosts CORE-class lifecycle + safety logic) |
| SHARED | types/schemas/utils               | Substantially compliant |

These crossings are **documented architectural realities, not regressions**. No
code is changed by this audit; remediation (e.g. moving `decide_promotion` and
`candidate_lab_safety` to CORE, extracting an execution orchestrator out of the
monolith) is recorded as follow-up, not performed here.
