# Francis Lab v0 sandbox image

`Dockerfile` builds `francis-lab-base:pinned`, the minimal, Francis-owned base
image used by the Lab v0 sandbox runner
(`src/francis/ingest/lab/lab_runtime.py`). It contains **no** application code,
credentials, or external dependencies beyond the pinned public base
(`alpine:3.20`, pinned by digest). Isolation is enforced by the runtime at run
time (`build_run_argv`), not by this image.

## Build

```bash
docker build -t francis-lab-base:pinned infra/lab
```

The tag matches the Lab runtime default `FRANCIS_LAB_IMAGE`. Override with the
`FRANCIS_LAB_IMAGE` environment variable if a different local image is desired.

## Python toolchain variant (`francis-lab-python:pinned`)

The bare base above carries no language toolchain, so a capability whose detected
validation command is `python -m pytest` cannot reach `VALID` in it (the command
exits 127, `python: not found`). `Dockerfile.python` builds a **second** image —
the bare base stays the minimal default; this variant is selected per-run via
`FRANCIS_LAB_IMAGE` when a Python capability needs an interpreter + test runner.

```bash
docker build -f infra/lab/Dockerfile.python -t francis-lab-python:pinned infra/lab
```

It pins `python:3.12-alpine` by digest, bakes a pinned `pytest`, and sets
`TMPDIR=/work` so pytest's temp files land on the writable tmpfs scratch instead
of the read-only root. It contains **no** application code or credentials and
**does not relax any isolation flag** — `--network none`, `--read-only`,
`--cap-drop ALL`, etc. are still enforced by the runtime exactly as for the base.

### Growth-rung closure verification (2026-06-14)

The full promotion ladder was driven on a **live daemon (server 29.5.3)** against
a throwaway `FRANCIS_DATA_DIR`, with `FRANCIS_LAB_IMAGE=francis-lab-python:pinned`
and a real Python capability tree (pyproject + a discoverable test that exercises
the function). Each rung is an independent real `docker run` of `python -m pytest`
through the production path (`run_lab_capability` → `SandboxExecutor.run_real` →
`validate_run` → `decide_promotion`):

- standalone smoke under the exact `build_run_argv` flags: `1 passed`, exit `0`,
  read-only root + `--network none` + tmpfs `/work` all held.
- `run 1: real / VALID / discovered -> drafted`
- `run 2: real / VALID / drafted -> runnable`
- `run 3: real / VALID / runnable -> validated` (ladder cap)
- per run: `executed=True`, `repo_code_executed=True`, `network_accessed=False`
  (structural — identical isolation flags to the digest-pinned base),
  `wrote_to_repo=False`, a `lab.execution.run` receipt written.

What was **real**: docker execution, pytest collection+pass, validation, and
promotion. What was **seeded** (documented test seam, as in
`tests/unit/test_lab_run_service.py::test_real_run_valid_promotes_one_rung`): only
the upstream approval *consumption*. `run_lab_capability` still enforced
source/candidate identity, the safety gate, `opt_in`, and a live daemon. The live
multi-gate operator approval chain remains exercised by its own unit tests.

## Real substrate verification (2026-06-10)

The real Docker execution substrate was verified against a **live daemon**
(server 29.2.0). This documents what was run; it does not change runtime
behavior.

1. Locked-down container smoke (network isolation), using the exact run flags
   `build_run_argv` emits:

   ```bash
   docker run --rm --network none --read-only --cap-drop ALL \
     --security-opt no-new-privileges --pids-limit 256 --memory 512m \
     --tmpfs /work:rw,exec,size=64m,nodev,nosuid -w /work --env HOME=/work \
     francis-lab-base:pinned /bin/sh -lc 'echo ok; wget -T2 -qO- http://1.1.1.1 || echo NET_BLOCKED'
   # -> "NET_BLOCKED", exit 0
   ```

2. Real run through the **production** execution components
   (`CapabilityRebuilder` -> `SandboxExecutor.run_real` -> `validate_run` ->
   `decide_promotion`) against a harmless Francis fixture repo, with a throwaway
   `FRANCIS_DATA_DIR` and `FRANCIS_LAB_IMAGE=francis-lab-base:pinned`. Observed:

   - `execution_mode = real`, `exit_code = 0`
   - network blocked inside the container (`NET_BLOCKED`)
   - source copied into tmpfs `/work` only; read-only `/src` mount
   - host fixture repo byte-identical after the run (no host mutation)
   - `validate_run = VALID`; `decide_promotion = drafted -> runnable` (one rung)

### Not yet verified live

The full `IngestService.run_lab_capability` wrapper was **not** invoked, so **no
`lab.execution.run` receipt was written** by the verification run. Driving the
wrapper end-to-end requires a legitimately consumed `sandboxed_rebuild_run_test`
approval from the governed approval chain; that live verification remains
pending. The wrapper, its receipt write, and the approval gate are covered by
unit tests (`tests/unit/test_lab_run_service.py`).
