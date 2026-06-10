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
