### 4.4 Supervised-exec policy contract

- **Exit codes:** `0` for allowed commands, non-zero when denied.

- **Decision line:** supervised-exec writes one machine-parseable line per run to `stderr` in the exact form `DECISION: <ALLOW|DENY> reason="<reason>" artifact="<artifact id?>"` (uppercase verdict, sanitized reason text, optional artifact id); helpers must consume it once and avoid duplicates.

- **Log routing:** structured policy logs stay on `stderr`; stdout is reserved for pure JSON/decision data.

- **Validation:** the executed process must exactly match the provided `--cmd`; special operators only pass through when already in that string.

- **Audit:** include any related artifact/log identifier on the decision line instead of repeating gating text.

Wrappers that capture the CLI output may need to synthesize this line when the CLI's `stderr` stream is empty, but they must still emit exactly one `DECISION:` line (on `stderr`) so the JSON on `stdout` remains clean.

