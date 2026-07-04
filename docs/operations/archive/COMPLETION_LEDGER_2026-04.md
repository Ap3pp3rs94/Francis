# FRANCIS - COMPLETION_LEDGER archive (2026-04)

Entries moved verbatim from docs/operations/COMPLETION_LEDGER.md.
Archived on 2026-07-02 by scripts/archive-completion-ledger.ps1.

### 2026-04-28 - Stage 6/Lens HUD runtime readiness readback

Stage 6/Lens now makes the HUD runtime boundary explicit instead of relying on
operator inference. `GET /lens/status` and its `/lens/hud` alias expose a
read-only `hud.runtime` object that says the current HUD surface is
`chat_ui.system_orb`, with `resident_overlay`, `always_on_top`,
`global_hotkey`, `tray_presence`, and `os_level` all false. The readiness
criteria now include `hud_layer_runtime` as `readback_only` with explicit
blockers for the missing resident overlay runtime, global hotkey binding, tray
host, and always-on-top window. The chat UI Lens parser preserves that runtime
readback, and the existing console HUD fallback copy no longer claims a
resident operator HUD is active.

This is a truth/readback slice only. It does not create execution authority,
approval-decision authority, memory-write authority, overlay-control authority,
summon authority, capture authority, new sensing authority, promotion
authority, or a resident OS HUD runtime.

Latest targeted validation for the `2026-04-28` Stage 6/Lens HUD runtime
readiness readback:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `node --test --experimental-strip-types src/lens/index.test.ts`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens tests\test_api_lens.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `cd apps\chat_ui; npm run test`
  Result: `passed`
- `cd apps\chat_ui; npm run build`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens resident host readiness contract

Stage 6/Lens now has a dedicated read-only resident-host readiness contract.
`GET /lens/host` returns `kind: lens.resident_host`, and `GET /lens/status`
embeds the same `resident_host` readback. The contract names the missing
components required before Francis can truthfully claim a resident Lens host:
resident host process, tray or equivalent presence, global summon hotkey,
always-on-top overlay window, native command-palette bridge, and summon binding.
Stage 6 readiness now includes `resident_host_runtime` as `not_implemented`, and
the existing `summon_anywhere` blocker list is tied to `/lens/host` evidence
instead of an empty claim.

This is a backend readback/contract slice only. It does not create a host
process, launch a local process, register a tray icon, install a hotkey, create
an overlay window, bind OS-level summon, change UI behavior, write memory,
decide approvals, execute actions, or grant overlay-control, summon, capture,
sensing, telemetry, promotion, policy, or local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens resident host
readiness contract:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens host launch manifest contract

Stage 6/Lens now has a dedicated read-only launch-manifest contract for the
future resident host. `GET /lens/host/manifest` returns
`kind: lens.host.launch_manifest`, and `/lens/host` embeds the same manifest.
The manifest declares the intended future entrypoint as `scripts/lens-host.ps1`,
marks that entrypoint as missing and non-executable, declares the candidate
foreground `pwsh` command as disabled, and names the future service config path
`data/config/services/lens-host.json` as absent. It also records the required
bindings that a real host must satisfy before Stage 6 can claim resident host
behavior: `/lens/status`, `/lens/host`, tray presence, global hotkey, and overlay
window.

This is a backend readback/contract slice only. It does not create
`scripts/lens-host.ps1`, create a service config, launch a process, install or
start a service, register a hotkey, open an overlay, change UI behavior, write
memory, decide approvals, execute actions, or grant overlay-control, summon,
capture, sensing, telemetry, promotion, policy, service-install, or
local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens host launch
manifest contract:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens host status runner

Stage 6/Lens now has the first safe host entrypoint for the future resident
Lens process. `scripts/lens-host.ps1` exists as a status-only PowerShell runner
that emits `kind: lens.host.status_runner`, reports the Lens host runtime as
not implemented, and preserves explicit false values for launch support,
foreground support, resident process supervision, tray presence, global hotkey,
always-on-top overlay, overlay window, command-palette binding, and
summon-anywhere behavior. If invoked with foreground/launch intent, it returns a
refusal payload and exits non-zero instead of starting a process.

`GET /lens/host/manifest` now reflects the entrypoint as present and exposes a
separate executable status command while keeping the foreground candidate
command disabled. `/lens/host` embeds the same manifest and marks
`status_runner_present: true`, but its resident-host runtime status remains
`not_implemented` with blockers for the missing runtime process, service config,
tray host, global hotkey binding, overlay window, and summon binding.

This is a status/readback and launch-boundary slice only. It does not create a
resident process, install or start a service, register a hotkey, open an
overlay, change UI behavior, write memory, decide approvals, execute actions,
or grant overlay-control, summon, capture, sensing, telemetry, promotion,
policy, service-install, or local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens host status
runner:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host.ps1 -Mode Status`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -Command '$output = & .\scripts\lens-host.ps1 -Mode Foreground; if ($LASTEXITCODE -ne 2) { Write-Error "expected exit 2, got $LASTEXITCODE"; exit 1 }; $output | Out-String'`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens host service config baseline

Stage 6/Lens now has a tracked disabled service-readiness baseline for the
future Lens resident host. `config/runtime/services/lens-host.json` declares
`kind: lens.host.service_config`, service name `Francis-LensHost`, the current
`scripts/lens-host.ps1` entrypoint, status/foreground modes, manual startup
intent, and explicit false values for `enabled`, `auto_start`,
`start_after_install`, `installable`, `install_authority`, and
`service_install_authority`.

The launch manifest now points to this tracked config path instead of ignored
runtime state, reports `config_exists: true` with `config_status:
present_disabled`, and no longer lists `lens_host_service_config_missing` when
the config is present. `/lens/host` now exposes `service_config_present: true`
and a `host_service_config` component marked `present_disabled`. The service
config is readiness/readback only; the foreground command remains disabled, the
runner still refuses foreground launch, and the resident host runtime remains
`not_implemented`.

This is a config/readback slice only. It does not install or start a service,
create a resident process, register a hotkey, open an overlay, change UI
behavior, write memory, decide approvals, execute actions, or grant
overlay-control, summon, capture, sensing, telemetry, promotion, policy,
service-install, or local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens host service
config baseline:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host.ps1 -Mode Status`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -Command '$output = & .\scripts\lens-host.ps1 -Mode Foreground; if ($LASTEXITCODE -ne 2) { Write-Error "expected exit 2, got $LASTEXITCODE"; exit 1 }; $output | Out-String'`
  Result: `passed`
- `python -m json.tool config\runtime\services\lens-host.json`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens host process readback boundary

Stage 6/Lens now has a non-starting process-state readback boundary for the
future resident Lens host. The disabled service config declares the future
runtime state path `data/runtime/lens-host/status.json` and PID path
`data/runtime/lens-host/lens-host.pid`, with `process_supervision_enabled:
false` and `process_supervision_readback: true`.

`scripts/lens-host.ps1 -Mode Status` now reports a `process_readback` object
that checks only the declared local state/PID files and, if a PID file exists,
uses a read-only process lookup to report whether that PID is alive. The API
readback exposes the same contract through `/lens/host/manifest` and
`/lens/host`, marks `process_readback_ready: true`, and keeps the resident host
process itself missing. In the current validated repo posture, process readback
reports `status: missing`, `process_alive: false`, `supervision_enabled: false`,
and no start/stop/restart support.

This is a process-readback slice only. It does not create a resident process,
write PID/state files, install or start a service, register a hotkey, open an
overlay, change UI behavior, write memory, decide approvals, execute actions,
or grant overlay-control, summon, capture, sensing, telemetry, promotion,
policy, service-install, supervision, restart, stop, or local-process-launch
authority. `resident_host_process_missing` remains a blocker.

Latest targeted validation for the `2026-04-28` Stage 6/Lens host process
readback boundary:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host.ps1 -Mode Status`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -Command '$output = & .\scripts\lens-host.ps1 -Mode Foreground; if ($LASTEXITCODE -ne 2) { Write-Error "expected exit 2, got $LASTEXITCODE"; exit 1 }; $output | Out-String'`
  Result: `passed`
- `python -m json.tool config\runtime\services\lens-host.json`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`

As of `2026-04-28`, Stage 6/Lens host readiness also has read-only Windows
service status readback. The disabled service config now declares
`service_status_readback: true` and `service_control_authority: false` for the
future `Francis-LensHost` service. `scripts/lens-host.ps1 -Mode Status` reads
the configured service name, checks only the local Windows Service Control
Manager/CIM status when available, and reports `service_readback` with
installed/status/start-type/path/account/error fields plus explicit denials for
install, start, stop, restart, service-install, and service-control authority.
The API does not query host services directly; `/lens/host/manifest` and
`/lens/host` expose a deterministic `runner_only` service-readback contract and
mark `host_service_readback` as ready so the operator can distinguish a declared
service from an installed/running resident host.

This is service-status readback only. It does not install, start, stop, restart,
or supervise a Windows service; create a resident host process; write PID/state
files; register a hotkey; open an overlay; change UI behavior; write memory;
decide approvals; execute actions; or grant overlay-control, summon, capture,
sensing, telemetry, promotion, policy, service-install, service-control,
supervision, restart, stop, or local-process-launch authority.
`resident_host_process_missing` and service installation/startup remain blockers.

Latest targeted validation for the `2026-04-28` Stage 6/Lens host service status
readback boundary:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host.ps1 -Mode Status`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -Command '$output = & .\scripts\lens-host.ps1 -Mode Foreground; if ($LASTEXITCODE -ne 2) { Write-Error "expected exit 2, got $LASTEXITCODE"; exit 1 }; $output | Out-String'`
  Result: `passed`
- `python -m json.tool config\runtime\services\lens-host.json`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`

As of `2026-04-28`, Stage 6/Lens has a separate read-only host lifecycle
preflight.
`scripts/lens-host-preflight.ps1` returns `kind:
lens.host.lifecycle_preflight` and checks the declared service config,
entrypoint, service-status-readback declaration, Windows service installation
state when available, install/start policy, process-supervision state, runtime
state/PID presence, tray presence, global hotkey binding, overlay window, and
summon binding. `-Mode Status` exits `0` with a blocked readiness payload, while
`-Mode Install`, `-Mode Start`, and `-Mode Launch` refuse with exit `2` and a
durable JSON reason. This makes the lifecycle gate inspectable before any
service install/start work exists.

This is diagnostic/preflight-only. It does not install, start, stop, restart, or
supervise a Windows service; create a resident host process; write PID/state
files; register a hotkey; open an overlay; change UI behavior; write memory;
decide approvals; execute actions; or grant overlay-control, summon, capture,
sensing, telemetry, promotion, policy, service-install, service-control,
supervision, restart, stop, or local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens host lifecycle
preflight:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-preflight.ps1 -Mode Status`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -Command '$output = & .\scripts\lens-host-preflight.ps1 -Mode Start; if ($LASTEXITCODE -ne 2) { Write-Error "expected exit 2, got $LASTEXITCODE"; exit 1 }; $output | Out-String'`
  Result: `passed`
- `python -m pytest tests\test_lens_host_preflight_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_preflight_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check tests\test_lens_host_preflight_script.py`
  Result: `passed`
- `python -m ruff format --check tests\test_lens_host_preflight_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens summon hotkey preflight baseline

Stage 6/Lens now has a disabled summon hotkey preflight baseline for the future
resident Lens summon path.
`config/runtime/lens/summon.json` declares the intended Lens summon name,
`Ctrl+Alt+Space` global hotkey intent, palette route, host preflight dependency,
host status runner dependency, and the explicit disabled/no-authority flags that
must remain false until the resident host, tray/presence, overlay window, global
hotkey binding, and summon binding are real.
`scripts/lens-summon-preflight.ps1` returns `kind: lens.summon.preflight` in
status mode with a blocked readiness payload and refuses `Bind` or `Launch`
intent with exit `2`.

This is diagnostic/preflight-only. It does not register a global hotkey; bind a
summon shortcut; launch Lens; open an overlay; create tray presence; start,
install, or supervise a resident host; write memory; decide approvals; execute
actions; or grant overlay-control, summon, capture, sensing, telemetry,
promotion, policy, hotkey-registration, or local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens summon hotkey
preflight baseline:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-summon-preflight.ps1 -Mode Status`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -Command '$output = & .\scripts\lens-summon-preflight.ps1 -Mode Bind; if ($LASTEXITCODE -ne 2) { Write-Error "expected exit 2, got $LASTEXITCODE"; exit 1 }; $output | Out-String'`
  Result: `passed`
- `python -m pytest tests\test_lens_summon_preflight_script.py tests\test_lens_host_preflight_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check tests\test_lens_summon_preflight_script.py`
  Result: `passed`
- `python -m ruff format --check tests\test_lens_summon_preflight_script.py`
  Result: `passed`
- `python -m json.tool config\runtime\lens\summon.json`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens tray presence preflight baseline

Stage 6/Lens now has a disabled tray/presence preflight baseline for the future
resident Lens presence surface.
`config/runtime/lens/tray.json` declares the intended tray presence name,
user-session tray scope, host/summon preflight dependencies, status routes, and
the explicit disabled/no-authority flags that must remain false until a
resident host process, tray icon, user-session presence, global hotkey binding,
overlay window, and summon binding are real.
`scripts/lens-tray-preflight.ps1` returns `kind: lens.tray.preflight` in status
mode with a blocked readiness payload and refuses `Register` or `Show` intent
with exit `2`.

This is diagnostic/preflight-only. It does not register a tray icon; create
tray presence; send notifications; launch Lens; start, install, or supervise a
resident host; register a global hotkey; open an overlay; write memory; decide
approvals; execute actions; or grant overlay-control, summon, capture, sensing,
telemetry, promotion, policy, service-control, tray-registration,
tray-icon, notification, or local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens tray presence
preflight baseline:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-tray-preflight.ps1 -Mode Status`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -Command '$output = & .\scripts\lens-tray-preflight.ps1 -Mode Register; if ($LASTEXITCODE -ne 2) { Write-Error "expected exit 2, got $LASTEXITCODE"; exit 1 }; $output | Out-String'`
  Result: `passed`
- `python -m pytest tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_host_preflight_script.py -q`
  Result: `passed`
- `python -m ruff check tests\test_lens_tray_preflight_script.py`
  Result: `passed`
- `python -m ruff format --check tests\test_lens_tray_preflight_script.py`
  Result: `passed`
- `python -m json.tool config\runtime\lens\tray.json`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens overlay window preflight baseline

Stage 6/Lens now has a disabled overlay/window preflight baseline for the future
resident Lens HUD surface.
`config/runtime/lens/overlay.json` declares the intended overlay name,
user-session scope, host/summon/tray preflight dependencies, status routes, and
the explicit disabled/no-authority flags that must remain false until a
resident host process, tray presence, overlay window, always-on-top policy,
global hotkey binding, and summon binding are real.
`scripts/lens-overlay-preflight.ps1` returns `kind: lens.overlay.preflight` in
status mode with a blocked readiness payload and refuses `Open` or `Focus`
intent with exit `2`.

This is diagnostic/preflight-only. It does not create an overlay window; make a
window always-on-top; focus, dock, or manage windows; capture screen content;
launch Lens; start, install, or supervise a resident host; register a global
hotkey; create tray presence; write memory; decide approvals; execute actions;
or grant overlay-control, window-management, summon, capture, sensing,
telemetry, promotion, policy, tray-registration, or local-process-launch
authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens overlay window
preflight baseline:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-overlay-preflight.ps1 -Mode Status`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -Command '$output = & .\scripts\lens-overlay-preflight.ps1 -Mode Open; if ($LASTEXITCODE -ne 2) { Write-Error "expected exit 2, got $LASTEXITCODE"; exit 1 }; $output | Out-String'`
  Result: `passed`
- `python -m pytest tests\test_lens_overlay_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_host_preflight_script.py -q`
  Result: `passed`
- `python -m ruff check tests\test_lens_overlay_preflight_script.py`
  Result: `passed`
- `python -m ruff format --check tests\test_lens_overlay_preflight_script.py`
  Result: `passed`
- `python -m json.tool config\runtime\lens\overlay.json`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens bounded foreground host session

Stage 6/Lens now has the first bounded foreground Lens host session instead of
only a refusing status runner. `scripts/lens-host.ps1 -Mode Foreground
-RunSeconds N` now writes a local runtime-state file and PID file under the
configured `FRANCIS_DATA_DIR` or the repo `data/runtime/lens-host` path, bounds
the session to `0..30` seconds, records a stopped runtime-state receipt when the
foreground session completes, and exits successfully without launching any child
process. `GET /lens/host/manifest` now exposes the foreground candidate command
as executable only as a manual bounded foreground status session; the route
still grants no API launch authority.

This is a bounded local runtime-state slice only. It does not install or start a
service; create a resident supervised process; register a tray icon; bind a
global hotkey; open or focus an overlay window; capture screen content; write
memory; decide approvals; execute operator actions; or grant overlay-control,
window-management, summon, capture, sensing, telemetry, promotion, policy,
service-install, service-control, tray-registration, hotkey-registration, or
API local-process-launch authority. `resident_host_process_missing`,
`tray_host_missing`, `global_hotkey_binding_missing`, `overlay_window_missing`,
and `summon_binding_missing` remain blockers after the foreground session exits.

Latest targeted validation for the `2026-04-28` Stage 6/Lens bounded foreground
host session:

- `powershell -NoProfile -ExecutionPolicy Bypass -Command '$tmp = Join-Path $env:TEMP ("francis-lens-host-" + [guid]::NewGuid().ToString("N")); $env:FRANCIS_DATA_DIR = $tmp; $output = & .\scripts\lens-host.ps1 -Mode Foreground -RunSeconds 0; if ($LASTEXITCODE -ne 0) { Write-Error "expected exit 0, got $LASTEXITCODE"; exit 1 }; $output | Out-String'`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py tests\test_lens_host_foreground_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py tests\test_lens_host_foreground_script.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `python -m json.tool config\runtime\services\lens-host.json`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens live foreground host readback proof

Stage 6/Lens now has a validated live-readback proof for the bounded foreground
host session. While `scripts/lens-host.ps1 -Mode Foreground -RunSeconds N` is
still running, a separate `scripts/lens-host.ps1 -Mode Status` invocation reads
the same runtime state/PID files, verifies the process is alive, reports
`process_readback.status: process_observed`, reports
`foreground_session: true`, and removes the stale
`resident_host_process_missing` blocker for that live foreground interval. The
script now uses `resident_host_not_supervised` as the live process readback
blocked reason so the status payload no longer claims the foreground process is
missing when it is actually observed.

This is still a bounded foreground status-session proof only. It does not create
a resident supervised host; install, start, stop, or restart a Windows service;
register tray presence; bind a global hotkey; open or focus an overlay window;
summon Francis anywhere; capture screen content; write memory; decide approvals;
execute operator actions; or grant overlay-control, window-management, summon,
capture, sensing, telemetry, promotion, policy, service-control,
tray-registration, hotkey-registration, or API local-process-launch authority.
After the foreground session exits, `resident_host_process_missing` remains a
truthful blocker.

Latest targeted validation for the `2026-04-28` Stage 6/Lens live foreground
host readback proof:

- `python -m pytest tests\test_lens_host_foreground_script.py -q`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens API live process readback

Stage 6/Lens now carries live foreground host process readback through the API
contract, not only through the PowerShell status runner. `/lens/status`,
`/lens/host`, and `/lens/host/manifest` read the Lens host runtime state and PID
files, perform a platform-aware process liveness check, report
`process_readback.status: process_observed` while the foreground process is
alive, expose `process_alive: true`, and use
`resident_host_not_supervised` instead of claiming the resident host process is
missing during that live foreground interval. The resident host component
reports `foreground_observed` while preserving `resident: false` and
`process_supervision: false`.

This is readback-only. It does not create a supervised resident process; install,
start, stop, or restart a Windows service; register tray presence; bind a global
hotkey; open or focus an overlay window; summon Francis anywhere; capture screen
content; write memory; decide approvals; execute operator actions; or grant
overlay-control, window-management, summon, capture, sensing, telemetry,
promotion, policy, service-control, tray-registration, hotkey-registration, or
API local-process-launch authority. After the foreground process is gone, the
API continues to report `resident_host_process_missing`.

Latest targeted validation for the `2026-04-28` Stage 6/Lens API live process
readback:

- `python -m pytest tests\test_api_lens.py tests\test_lens_host_foreground_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py tests\test_lens_host_foreground_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py tests\test_lens_host_foreground_script.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens resident supervision readiness gate

Stage 6/Lens now exposes an explicit resident supervision readiness gate instead
of leaving the next host step implicit. `config/runtime/services/lens-host.json`
declares the disabled supervision gate and Windows-service supervision mode.
`/lens/status`, `/lens/host`, and `/lens/host/manifest` now include
`supervision_readiness`, with prerequisite readback for the host entrypoint,
service manager script, disabled service config, foreground process readback,
process-supervision enablement, service-install authority, and service-control
authority. The gate remains `blocked`; `process_supervision_enabled`,
`service_install_authority`, and `service_control_authority` are the active
blockers in the validated baseline.

This is readback-only. It does not install, start, stop, update, restart, or
supervise a Windows service; create a resident host process; register tray
presence; bind a global hotkey; open or focus an overlay window; summon Francis
anywhere; capture screen content; write memory; decide approvals; execute
operator actions; or grant overlay-control, window-management, summon, capture,
sensing, telemetry, promotion, policy, service-control, tray-registration,
hotkey-registration, service-install, or API local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens resident
supervision readiness gate:

- `python -m pytest tests\test_api_lens.py tests\test_lens_host_foreground_script.py -q`
  Result: `passed`
- `python -m json.tool config\runtime\services\lens-host.json`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens service manager dry-run plan

Stage 6/Lens now has a non-mutating service-manager plan proof for the future
resident Lens host. `scripts/service-install.ps1` supports `-Mode Plan`, accepts
the single-object Lens service config shape, normalizes snake_case service
fields, resolves the planned PowerShell foreground host command, computes the
planned wrapper/binary path, and writes the existing service-install JSON report
with a `service_install.plan` record. The tracked Lens host service config now
declares the intended foreground command for future service supervision while
remaining disabled and non-installable.

The validated baseline plan is still `blocked`: `installable`,
`install_authority`, `service_install_authority`, and
`service_control_authority` remain false, and the plan reports
`would_install: false`, `would_start: false`, `wrapper.would_write: false`, and
`mutation_authority_granted: false`.

This is dry-run/readback-only. It does not install, update, start, stop, restart,
delete, supervise, or write a Windows service wrapper; create a resident host
process; register tray presence; bind a global hotkey; open or focus an overlay
window; summon Francis anywhere; capture screen content; write memory; decide
approvals; execute operator actions; or grant overlay-control, window-management,
summon, capture, sensing, telemetry, promotion, policy, service-install,
service-control, wrapper-write, or API local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens service manager
dry-run plan:

- `python -m pytest tests\test_service_install_plan_script.py -q`
  Result: `passed`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\service-install.ps1 -Mode Plan -Root D:\Francis -ConfigPath config\runtime\services\lens-host.json`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_host_preflight_script.py tests\test_service_install_plan_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m json.tool config\runtime\services\lens-host.json`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_service_install_plan_script.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_service_install_plan_script.py tests\test_api_lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens service plan preflight readback

Stage 6/Lens now surfaces the future resident host service plan through the
read-only lifecycle preflight. `scripts/lens-host-preflight.ps1 -Mode Status`
projects a `service_plan` object from `config/runtime/services/lens-host.json`,
including the service manager path, plan mode, intended foreground command,
wrapper intent, start policy, blocker list, and governance flags. The preflight
also includes `service_manager` and `service_plan` checks so an operator can see
that the service-manager dry-run plan is present but still blocked.

The validated preflight projection remains blocked and non-mutating:
`would_install: false`, `would_start: false`, `wrapper_would_write: false`,
`service_install_authority: false`, `service_control_authority: false`, and
`mutation_authority_granted: false`. It does not invoke the service manager or
write service-install reports during ordinary preflight status.

This is readback-only. It does not install, update, start, stop, restart, delete,
supervise, or write a Windows service wrapper; create a resident host process;
register tray presence; bind a global hotkey; open or focus an overlay window;
summon Francis anywhere; capture screen content; write memory; decide approvals;
execute operator actions; or grant overlay-control, window-management, summon,
capture, sensing, telemetry, promotion, policy, service-install,
service-control, wrapper-write, or API local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens service plan
preflight readback:

- `python -m pytest tests\test_lens_host_preflight_script.py -q`
  Result: `passed`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-preflight.ps1 -Mode Status`
  Result: `passed`
- `python -m pytest tests\test_lens_host_preflight_script.py tests\test_service_install_plan_script.py tests\test_lens_host_foreground_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\service-install.ps1 -Mode Plan -Root D:\Francis -ConfigPath config\runtime\services\lens-host.json`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens API service plan readback

Stage 6/Lens now surfaces the future resident host service plan through the
read-only API surfaces as well as the preflight script. `/lens/host/manifest`
projects a `service_plan` object from `config/runtime/services/lens-host.json`,
including the service manager path, plan mode, intended foreground command,
wrapper intent, start policy, blocker list, and governance flags. `/lens/status`
threads the same projection into `resident_host.service_plan` and marks
`service_plan_ready: false`, so operator surfaces can read the service plan
truthfully without invoking the service manager or implying resident runtime
readiness.

The validated API projection remains blocked and non-mutating:
`would_install: false`, `would_start: false`, `wrapper_would_write: false`,
`service_install_authority: false`, `service_control_authority: false`,
`wrapper_write_authority: false`, and `mutation_authority_granted: false`.

This is readback-only. It does not install, update, start, stop, restart, delete,
supervise, or write a Windows service wrapper; create a resident host process;
register tray presence; bind a global hotkey; open or focus an overlay window;
summon Francis anywhere; capture screen content; write memory; decide approvals;
execute operator actions; or grant overlay-control, window-management, summon,
capture, sensing, telemetry, promotion, policy, service-install,
service-control, wrapper-write, or API local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens API service plan
readback:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m json.tool config\runtime\services\lens-host.json`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens API primitive preflight readback

Stage 6/Lens now exposes read-only API preflight for the Lens host, summon,
tray, and overlay primitives. `GET /lens/preflight` reads the existing disabled
Lens runtime configs and host launch manifest, then projects blocked readiness
for the resident host, global hotkey summon, tray presence, and overlay window
without invoking the PowerShell preflight scripts. `GET /lens/status` embeds the
same preflight object and adds Stage 6 readiness criteria for summon, tray, and
overlay preflight status.

The API projection keeps all lifecycle surfaces blocked: host remains blocked,
summon remains blocked, tray remains blocked, and overlay remains blocked. It
reports the declared `Ctrl+Alt+Space` hotkey intent, disabled tray and overlay
settings, missing resident host state, and no-authority blockers while preserving
`execution_authority: false`, `local_process_launch_authority: false`,
`service_control_authority: false`, `hotkey_registration_authority: false`,
`tray_registration_authority: false`, `overlay_control_authority: false`, and
`mutation_authority_granted: false`.

This is readback-only. It does not bind a hotkey, register tray presence, open
or focus an overlay, install/start/control a service, launch a resident process,
summon Francis anywhere, capture screen content, write memory, decide approvals,
execute operator actions, or grant overlay-control, window-management, summon,
capture, sensing, telemetry, promotion, policy, service-install,
service-control, tray, hotkey, wrapper-write, or API local-process-launch
authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens API primitive
preflight readback:

- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m json.tool config\runtime\lens\summon.json; python -m json.tool config\runtime\lens\tray.json; python -m json.tool config\runtime\lens\overlay.json; python -m json.tool config\runtime\services\lens-host.json`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens host activation approval-request boundary

Stage 6/Lens now has a governed request boundary for future foreground Lens host
activation. `POST /lens/host/activation/request` requires the existing
`system.write` API actor scope, records a pending
`lens.host.foreground_activation` approval request, and returns the exact
activation intent, preflight blockers, host manifest command projection, and
non-execution governance flags. `/lens/status` and `/lens/host` expose the
activation-request contract, and the Lens command palette readback includes the
request command as a confirmation-requiring control with no launch authority.

This is an approval-request write, not runtime activation. It does not launch a
Lens host process; install, start, stop, restart, supervise, or control a
Windows service; register tray presence; bind a global hotkey; open or focus an
overlay window; summon Francis anywhere; capture screen content; write memory;
decide approvals; execute operator actions; or grant overlay-control,
window-management, summon, capture, sensing, telemetry, promotion, policy,
service-install, service-control, wrapper-write, or API local-process-launch
authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens host activation
approval-request boundary:

- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-28 - Stage 6/Lens host activation approval-state readback

Stage 6/Lens now has read-only approval-state readback for the future Lens host
activation path. `GET /lens/host/activation` filters approval records for
`lens.host.foreground_activation` across pending, approved, rejected, and
emergency queues, returns counts, latest records, and by-status records, and
states the next operator step without starting anything. `/lens/status` and
`/lens/host` embed the same readback as `activation_state`, and Stage 6
readiness now includes a `host_activation_approval_readback` criterion.

The readback preserves the approval boundary after decisions: a pending request
shows `pending_review`, an approved request shows `approved_no_execution`, and
execution remains blocked behind a future separate implementation slice. This
turns approval decisions into operator-visible evidence without treating
approval as launch authority.

This is readback-only. It does not launch a Lens host process; install, start,
stop, restart, supervise, or control a Windows service; register tray presence;
bind a global hotkey; open or focus an overlay window; summon Francis anywhere;
capture screen content; write memory; decide approvals; execute operator
actions; or grant overlay-control, window-management, summon, capture, sensing,
telemetry, promotion, policy, service-install, service-control, wrapper-write,
or API local-process-launch authority.

Latest targeted validation for the `2026-04-28` Stage 6/Lens host activation
approval-state readback:

- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py tests\test_api_approvals.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py tests\test_api_approvals.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens host activation execution preflight gate

Stage 6/Lens now has a read-only execution-preflight gate for the future Lens
host activation path. `GET /lens/host/activation/preflight` requires an exact
approval id, reads the matching `lens.host.foreground_activation` approval
record, checks whether the caller has `system.write`, reads operator posture,
and projects the host command, foreground-session, process, service-plan, and
Lens primitive preflight blockers before any future execution slice can run.
`/lens/status` and `/lens/host` embed the same contract as
`activation_execution_preflight`, and Stage 6 readiness now includes a
`host_activation_execution_preflight` criterion.

The gate deliberately remains non-executing. A pending approval stays blocked
on `activation_approval_not_approved`; an approved activation request can clear
the approval and actor-scope blockers while still reporting the remaining host
preflight blockers and `local_process_launch_authority_not_granted`. Observe
mode adds `operator_posture_not_ready`, so approval alone is never treated as
launch permission.

This is readback-only and gate-only. It does not launch a Lens host process;
install, start, stop, restart, supervise, or control a Windows service; register
tray presence; bind a global hotkey; open or focus an overlay window; summon
Francis anywhere; capture screen content; write memory; decide approvals;
execute operator actions; or grant overlay-control, window-management, summon,
capture, sensing, telemetry, promotion, policy, service-install,
service-control, wrapper-write, or API local-process-launch authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens host activation
execution preflight gate:

- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py tests\test_api_approvals.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens host activation execution-plan readback

Stage 6/Lens now has a read-only execution-plan readback for the future Lens
host activation path. `GET /lens/host/activation/plan` consumes the exact
activation preflight contract, keeps the selected approval, actor scope,
operator posture, host command, process readback, service plan, and primitive
preflight evidence together, and projects the bounded steps that a future
activation execution slice would need to satisfy before launching anything.
`/lens/status` and `/lens/host` embed the same contract as
`activation_execution_plan`, and Stage 6 readiness now includes a
`host_activation_execution_plan` criterion.

The plan is deliberately non-executing. It can show that an approved activation
request cleared approval and actor-scope blockers while still blocking launch
on remaining host preflight blockers and
`local_process_launch_authority_not_granted`. The launch and receipt steps are
reported as future-slice steps with authority granted set to false.

This is readback-only and plan-only. It does not launch a Lens host process;
install, start, stop, restart, supervise, or control a Windows service; register
tray presence; bind a global hotkey; open or focus an overlay window; summon
Francis anywhere; capture screen content; write memory; write activation
receipts; decide approvals; execute operator actions; or grant overlay-control,
window-management, summon, capture, sensing, telemetry, promotion, policy,
service-install, service-control, wrapper-write, receipt-write, or API
local-process-launch authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens host activation
execution-plan readback:

- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py tests\test_api_approvals.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens host activation execution-denial boundary

Stage 6/Lens now has a governed, non-launching execution-denial boundary for
the future Lens host activation path. `POST /lens/host/activation/execute`
accepts an exact activation approval id and actor, consumes the existing
activation preflight and execution-plan contracts, rechecks `system.write` on
the execute route, and returns a typed
`lens.host.activation.execution_denial` response instead of starting anything.
`/lens/status` and `/lens/host` embed the same boundary as
`activation_execution_denial`, and Stage 6 readiness now includes a
`host_activation_execution_denial_boundary` criterion.

The boundary preserves approval specificity without turning approval into
power. An approved activation request can clear approval, actor-scope, and
operator-posture blockers while the execute route still returns
`denied_no_execution_authority` because `local_process_launch_authority` and
receipt-write authority are not granted. No runtime state or pid file is
created by the denial path.

This is a denial boundary only. It does not launch a Lens host process; install,
start, stop, restart, supervise, or control a Windows service; register tray
presence; bind a global hotkey; open or focus an overlay window; summon Francis
anywhere; capture screen content; write memory; write activation receipts;
decide approvals; execute operator actions; or grant overlay-control,
window-management, summon, capture, sensing, telemetry, promotion, policy,
service-install, service-control, wrapper-write, receipt-write, or API
local-process-launch authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens host activation
execution-denial boundary:

- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py tests\test_api_approvals.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens host activation denial receipt readback

Stage 6/Lens host activation denials now produce durable local receipt evidence
when a scoped execute attempt reaches the existing non-launching denial boundary.
`POST /lens/host/activation/execute` still refuses local process launch, service,
hotkey, overlay, approval-decision, and memory-write authority, but scoped
attempts now persist a typed `lens.host.activation.denial.receipt` under the
local data directory and return the receipt handle in the denial response.

The denial receipts are readable through `GET /lens/host/activation/denials`
with bounded limit, approval-id, and status filters. `/lens/status` and
`/lens/host` embed the same readback as `activation_denial_receipts`, and Stage 6
readiness now includes `host_activation_denial_receipt_readback`. Readback routes
remain read-only; unscoped execute attempts do not get denial-receipt write
authority.

This is receipt/readback work only. It does not launch a Lens host process;
install, start, stop, restart, supervise, or control a Windows service; register
tray presence; bind a global hotkey; open or focus an overlay window; summon
Francis anywhere; capture screen content; write memory; decide approvals; execute
operator actions; or grant overlay-control, window-management, summon, capture,
sensing, telemetry, promotion, policy, service-install, service-control,
wrapper-write, activation-receipt-write, or API local-process-launch authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens host activation
denial receipt readback:

- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_service_install_plan_script.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py tests\test_api_approvals.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\activation.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\activation.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py tests\test_api_contract_chat_ui.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens activation denial receipt UI readback

The chat UI Lens readback surface now preserves and renders Lens host activation
denial receipt evidence from the existing `/lens/status` response. The typed
Lens client parses `resident_host.activation_denial_receipts`, the
`/lens/host/activation/denials` route handle, latest receipt id, receipt total,
receipt blockers, execution no-launch flags, and no-authority governance fields.
The System/ORB Lens Readback panel now includes a compact host-activation-denials
card with the denial receipt count, readback status, latest receipt id, and
readback route.

This is UI/readback-only. It does not call execute routes, create approval
requests, decide approvals, launch a Lens host process, install/start/control
services, bind hotkeys, open overlays, write memory, add backend routes, add
promotion or execution authority, or infer readiness client-side.

Latest targeted validation for the `2026-04-29` Stage 6/Lens activation denial
receipt UI readback:

- `node --test --experimental-strip-types src\lens\index.test.ts`
  Result: `passed`
- `npm run test`
  Result: `passed`
- `npm run build`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens preflight prerequisite readback

Stage 6/Lens preflight now surfaces the explicit prerequisite lists that were
already declared in the disabled summon, tray, and overlay configs. The
PowerShell preflight scripts and the `/lens/preflight` API projection expose
`required_before_enable` for the future global summon binding, tray/presence,
and overlay/window primitives, so checkpoint audits can distinguish declared
prerequisites from current blockers without rereading raw config files.

This is readback-only prerequisite traceability. It does not enable summon,
register a global hotkey, create tray presence, open or focus an overlay, launch
a Lens host process, install/start/control services, write memory, decide
approvals, execute operator actions, or grant overlay-control, window-management,
summon, tray-registration, hotkey-registration, service-control,
local-process-launch, capture, sensing, telemetry, or policy authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens preflight
prerequisite readback:

- `python -m pytest tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\preflight.py tests\test_api_lens.py tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_overlay_preflight_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\preflight.py tests\test_api_lens.py tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_overlay_preflight_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-summon-preflight.ps1 -Mode Status | ConvertFrom-Json | Select-Object -ExpandProperty required_before_enable`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-tray-preflight.ps1 -Mode Status | ConvertFrom-Json | Select-Object -ExpandProperty required_before_enable`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-overlay-preflight.ps1 -Mode Status | ConvertFrom-Json | Select-Object -ExpandProperty required_before_enable`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens completion checkpoint diagnostic

Stage 6/Lens now has a status-only completion checkpoint diagnostic.
`scripts/lens-stage6-checkpoint.ps1 -Mode Status` imports the existing
`/lens/status` readiness contract without needing a running API server and maps
the roadmap's Stage 6 done criteria into a compact checkpoint payload:
summon-anywhere, helpful/not-noisy, mode visibility, Pilot visibility
groundwork, and system-resident presence. The current repo truth is
`status: blocked`, `ready_to_close: false`, with two criteria ready
(`mode_visibility` and `pilot_visibility_groundwork`) and three criteria still
blocked (`summon_anywhere`, `helpful_not_noisy`, and
`system_resident_presence`).

The checkpoint names the next smallest truthful gap as
`resident_host_process_or_supervised_foreground_readiness_proof` and preserves
the current blockers for missing resident host process, global hotkey binding,
summon binding, tray host, overlay window, resident overlay runtime, and live
operator proof. This turns Stage 6 checkpoint audits into repeatable repo truth
instead of a prose-only judgment.

This is diagnostic/readback-only. It does not enable summon, register a global
hotkey, create tray presence, open or focus an overlay, launch a Lens host
process, install/start/control services, write memory, decide approvals, execute
operator actions, or grant overlay-control, window-management, summon,
tray-registration, hotkey-registration, service-control, local-process-launch,
capture, sensing, telemetry, or policy authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens completion
checkpoint diagnostic:

- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens foreground host proof diagnostic

Stage 6/Lens now has a repeatable foreground host readiness proof diagnostic.
`scripts/lens-host-foreground-proof.ps1 -Mode Status` starts the existing
bounded foreground `scripts/lens-host.ps1` status session against a temporary
data root, waits for live runtime state, verifies that `scripts/lens-host.ps1
-Mode Status` observes the same foreground process and PID, then verifies the
bounded session stops and leaves `foreground_stopped` state. The proof returns
`kind: lens.host.foreground_readiness_proof`, `status: proof_passed`, and keeps
`ready_for_resident_claim: false`.

The Stage 6 checkpoint now names this proof as evidence for the blocked
`system_resident_presence` criterion and advances the next smallest truthful
gap to `resident_host_supervision_or_resident_surface_proof`. This removes the
foreground-observation proof gap without claiming a resident host, service
supervision, tray presence, global hotkey binding, overlay window, command
palette binding, summon-anywhere behavior, or live operator experience proof.

This is diagnostic/proof-only. It does not install, start, stop, restart, or
control a Windows service; create resident supervision; register tray presence;
bind a global hotkey; open or focus an overlay; summon Francis anywhere; expose
new UI controls; call API execute routes; write memory; decide approvals; or
grant execution, approval-decision, memory-write, overlay-control,
window-management, summon, capture, sensing, telemetry, policy,
service-install, service-control, hotkey-registration, tray-registration, API
local-process-launch, or product local-process-launch authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens foreground host
proof diagnostic:

- `python -m pytest tests\test_lens_host_foreground_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_foreground_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_foreground_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-foreground-proof.ps1 -Mode Status -RunSeconds 3`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens supervision readiness proof diagnostic

Stage 6/Lens now has a composed resident-host supervision readiness proof
diagnostic. `scripts/lens-host-supervision-proof.ps1 -Mode Status` verifies the
existing host lifecycle preflight is readable and blocked, composes the bounded
foreground host proof, confirms the service plan remains non-installing and
non-starting, confirms the Lens host service is not installed, and confirms
process supervision, service control, service install, and product local-process
launch authority remain denied.

The proof returns `kind: lens.host.supervision_readiness_proof` with
`status: proof_passed`, `supervision_ready: false`,
`ready_for_resident_claim: false`, and `resident_claim_allowed: false`. The
Stage 6 checkpoint now names this supervision proof as evidence for the blocked
`system_resident_presence` criterion and advances the next smallest truthful gap
to `resident_surface_or_tray_presence_readiness_proof`.

This is diagnostic/proof-only. It does not install, start, stop, restart, or
control a Windows service; enable process supervision; create a resident host
process; register tray presence; bind a global hotkey; open or focus an overlay;
summon Francis anywhere; expose new UI controls; call API execute routes; write
memory; decide approvals; or grant execution, approval-decision, memory-write,
overlay-control, window-management, summon, capture, sensing, telemetry, policy,
service-install, service-control, hotkey-registration, tray-registration, API
local-process-launch, or product local-process-launch authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens supervision
readiness proof diagnostic:

- `python -m pytest tests\test_lens_host_supervision_proof_script.py tests\test_lens_stage6_checkpoint_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervision_proof_script.py tests\test_lens_host_foreground_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_overlay_preflight_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_supervision_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_supervision_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-supervision-proof.ps1 -Mode Status -ForegroundRunSeconds 2`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident surface readiness proof diagnostic

Stage 6/Lens now has a composed resident-surface readiness proof diagnostic.
`scripts/lens-resident-surface-proof.ps1 -Mode Status` verifies the existing
host lifecycle boundary, confirms the separate host supervision proof remains
available as foreground-process evidence, and composes the disabled tray
presence preflight, disabled overlay window preflight, and disabled
summon/hotkey preflight together. The proof returns
`kind: lens.resident_surface.readiness_proof` with `status: proof_passed`,
`resident_surface_ready: false`, `ready_for_lens_resident_claim: false`, and
`resident_claim_allowed: false`.

The Stage 6 checkpoint now names this proof as evidence for the blocked
`system_resident_presence` criterion and advances the next smallest truthful
gap to `resident_surface_activation_boundary_or_live_operator_experience_proof`.
This removes the resident-surface proof gap without claiming tray presence,
global hotkey binding, overlay window behavior, summon-anywhere behavior, live
operator experience proof, or resident Lens readiness.

This is diagnostic/proof-only. It does not install, start, stop, restart, or
control a Windows service; enable process supervision; create a resident host
process; register tray presence; bind a global hotkey; open, focus, or control
an overlay; summon Francis anywhere; expose new UI controls; call API execute
routes; spawn a foreground host; write runtime state; write memory; decide
approvals; or grant execution, approval-decision, memory-write,
overlay-control, window-management, summon, capture, sensing, telemetry,
policy, service-install, service-control, hotkey-registration,
tray-registration, tray-icon, notification, API local-process-launch, or
product local-process-launch authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident surface
readiness proof diagnostic:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-resident-surface-proof.ps1 -Mode Status`
  Result: `passed`
- `python -m pytest tests\test_lens_resident_surface_proof_script.py tests\test_lens_stage6_checkpoint_script.py -q`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident surface activation boundary readback

Stage 6/Lens now has a backend readback contract for the resident-surface
activation boundary. `GET /lens/resident-surface/activation` composes the
existing Lens host activation approval/readback path, execution preflight,
execution plan, execution denial, and the host/summon/tray/overlay preflight
surfaces into a single `kind: lens.resident_surface.activation_boundary`
payload. The payload reports `status: blocked`, `boundary_ready: true`,
`activation_ready: false`, `resident_surface_ready: false`,
`ready_for_lens_resident_claim: false`, and `resident_claim_allowed: false`.

`/lens/status` now embeds the same boundary as
`resident_surface_activation`, and Stage 6 readiness includes a
`resident_surface_activation_boundary` criterion with
`status: blocked_readback_ready`. The Stage 6 checkpoint now lists
`/lens/resident-surface/activation` as evidence under
`system_resident_presence` and advances the next smallest truthful gap to
`live_operator_experience_proof`.

This is readback-only and boundary-only. It does not launch a Lens host
process; install, start, stop, restart, supervise, or control a Windows
service; register tray presence; bind a global hotkey; open, focus, or
control an overlay; summon Francis anywhere; create live operator experience
proof; write runtime state; write memory; decide approvals; or grant
execution, approval-decision, memory-write, overlay-control,
window-management, summon, capture, sensing, telemetry, policy,
service-install, service-control, hotkey-registration, tray-registration,
tray-icon, notification, API local-process-launch, or product
local-process-launch authority.

Follow-up CI stabilization kept the proof diagnostic bounded while making the
foreground child process observation less timing-sensitive on Windows runners:
`scripts/lens-host-supervision-proof.ps1` now preserves the requested foreground
run duration in the payload and uses a minimum 5-second observation window for
the nested foreground proof. This remains diagnostic-only and does not add
process-launch authority beyond the existing explicit foreground proof harness.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident surface
activation boundary readback:

- `python -m pytest tests\test_api_lens.py tests\test_api_contract_chat_ui.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_host_foreground_proof_script.py tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_overlay_preflight_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_supervision_proof_script.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_supervision_proof_script.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py`
  Result: `passed`
- `python -m mypy src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-supervision-proof.ps1 -Mode Status -ForegroundRunSeconds 2`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`
- `git diff --check`
  Result: `passed` with the expected PowerShell line-ending warning for
  `scripts/lens-host-supervision-proof.ps1`

### 2026-04-29 - Stage 6/Lens live operator experience readback proof

Stage 6/Lens now has a status-only live operator experience proof diagnostic.
`scripts/lens-live-operator-proof.ps1 -Mode Status` starts a temporary local
Francis API process on loopback with an isolated temporary data directory,
reads `/lens/status?limit=5` over HTTP, and verifies that the operator-facing
Lens payload carries HUD readback, command palette readback, mode/Pilot
visibility, approvals/incidents/missions/receipts lanes, resident-surface
activation boundary state, and governance denial flags through the same route
the operator UI consumes.

The Stage 6 checkpoint now consumes this proof. The `helpful_not_noisy`
criterion advances from `needs_live_operator_proof` to
`operator_readback_proof_ready`, and `operator_experience_proof_missing` is no
longer a checkpoint blocker. Stage 6 remains active and blocked: the proof
reports `live_operator_experience_ready: false`, `ready_for_stage6_closure:
false`, `resident_surface_ready: false`, and `resident_claim_allowed: false`.
The checkpoint's next smallest truthful gap is now
`resident_host_or_resident_overlay_runtime`.

This is diagnostic/readback work only. It creates a temporary API process and
temporary proof logs under an isolated data directory, but it does not create a
resident Lens host; install, start, stop, restart, supervise, or control a
Windows service; register tray presence; bind a global hotkey; open, focus, or
control an overlay; summon Francis anywhere; grant telemetry, sensing, capture,
execution, approval-decision, memory-write, overlay-control,
window-management, service-control, service-install, hotkey-registration, or
tray-registration authority; or claim Stage 6 closure.

Latest targeted validation for the `2026-04-29` Stage 6/Lens live operator
experience readback proof:

- `python -m pytest tests\test_lens_live_operator_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_api_lens.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_host_foreground_proof_script.py tests\test_lens_host_foreground_script.py tests\test_lens_host_preflight_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_overlay_preflight_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_live_operator_proof_script.py tests\test_lens_stage6_checkpoint_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_live_operator_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_live_operator_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-live-operator-proof.ps1 -Mode Status -StartupTimeoutSeconds 20`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`
- `git diff --check`
  Result: `passed` with the expected PowerShell line-ending warning for
  `scripts/lens-stage6-checkpoint.ps1`

### 2026-04-29 - Stage 6/Lens bounded host launch diagnostic

Stage 6/Lens now has an explicit bounded local host launch diagnostic.
`scripts/lens-host.ps1 -Mode Launch -RunSeconds <n>` starts one child
PowerShell process running the existing bounded `Foreground` host mode,
observes the runtime state and PID through `data/runtime/lens-host/status.json`
and `lens-host.pid`, returns `status: launch_started` when the foreground
process is observed, and lets that foreground host self-stop after the requested
run window. The launch response now distinguishes diagnostic launch authority
from product launch authority: `diagnostic_launch_authority: true`,
`launch_authority: false`, `product_execution_authority: false`, and
`api_local_process_launch_authority: false`.

This removes the previous `Launch` mode refusal for the local diagnostic runner
only. It does not create a resident Lens host, install/start/stop/restart a
service, supervise the process after the bounded window, register tray presence,
bind a global hotkey, open or control an overlay, summon Francis anywhere, add
API launch authority, grant execution authority, approve anything, write memory,
or claim Stage 6 closure. The remaining truthful Stage 6 blocker is still
resident host or overlay runtime that is supervised and operator-visible beyond
this bounded diagnostic process.

Latest targeted validation for the `2026-04-29` Stage 6/Lens bounded host launch
diagnostic:

- `python -m pytest tests\test_lens_host_foreground_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_foreground_script.py tests\test_lens_host_foreground_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_live_operator_proof_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_foreground_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_foreground_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host.ps1 -Mode Launch -RunSeconds 3`
  Result: `passed` against an isolated temporary `FRANCIS_DATA_DIR`

### 2026-04-29 - Stage 6/Lens host launch proof checkpoint

Stage 6/Lens now consumes the bounded host launch diagnostic through a repeatable
proof and checkpoint readback. `scripts/lens-host-launch-proof.ps1 -Mode Status`
invokes the existing `scripts/lens-host.ps1 -Mode Launch -RunSeconds <n>` path
against an isolated temporary data directory, verifies that the bounded
foreground host process is observed, verifies that the host self-stops and leaves
only stopped runtime readback, and verifies that the launch remains diagnostic:
`launch_authority: false`, `product_execution_authority: false`, and
`api_local_process_launch_authority: false`.

The Stage 6 checkpoint now consumes this launch proof. The
`system_resident_presence` criterion advances from the raw backend
`not_implemented` status to `bounded_host_launch_observed`, but it remains
blocked and `ready_to_close: false` because the observed process is not a
supervised resident host and there is still no tray presence, global hotkey,
overlay runtime, summon-anywhere behavior, or live Pilot takeover. The
checkpoint's next smallest truthful gap is now
`resident_host_supervision_or_resident_overlay_runtime`.

This is proof/checkpoint work only. It does not rework the host runner, add API
launch authority, install/start/control a service, register tray presence, bind a
global hotkey, open or control an overlay, grant product execution authority,
approve anything, write memory, or claim Stage 6 closure.

Latest targeted validation for the `2026-04-29` Stage 6/Lens host launch proof
checkpoint:

- `python -m pytest tests\test_lens_host_launch_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_launch_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_host_foreground_script.py tests\test_lens_host_foreground_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_live_operator_proof_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_launch_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_launch_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-launch-proof.ps1 -Mode Status -RunSeconds 3`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status -HostLaunchRunSeconds 3`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens supervision proof consumes bounded launch

Stage 6/Lens resident supervision proof now consumes the bounded host launch
proof instead of stopping at foreground-readback evidence. Running
`scripts/lens-host-supervision-proof.ps1 -Mode Status` now verifies the lifecycle
preflight, the foreground readiness proof, and
`scripts/lens-host-launch-proof.ps1 -Mode Status`, then reports
`bounded_host_launch_observed: true` while keeping `supervision_ready: false`,
`ready_for_resident_claim: false`, `resident_host_process: false`, and
`supervised: false`.

This makes the supervision layer's current truth sharper: Francis can prove one
bounded diagnostic host launch was observed and self-stopped, but it still cannot
claim a resident/supervised host. The proof also stops carrying the stale
`operator_experience_proof_missing` blocker because the live operator readback
proof already exists and is consumed elsewhere in Stage 6. The next smallest
truthful gap remains `resident_host_supervision_or_resident_overlay_runtime`.

This is proof/readback composition only. It grants no product execution
authority, no API launch authority, no service install/control authority, no
approval-decision authority, no memory-write authority, no tray registration, no
hotkey registration, no overlay control, and no summon-anywhere claim. The proof
does perform bounded diagnostic local process launch through the existing launch
proof, and records that distinction explicitly as
`local_process_launch_authority: true` with
`api_local_process_launch_authority: false` and
`product_execution_authority: false`.

Latest targeted validation for the `2026-04-29` Stage 6/Lens supervision proof
composition:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-supervision-proof.ps1 -Mode Status -ForegroundRunSeconds 2 -HostLaunchRunSeconds 3`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervision_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_launch_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_host_foreground_proof_script.py tests\test_lens_host_foreground_script.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_live_operator_proof_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_supervision_proof_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_supervision_proof_script.py`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens bounded supervisor observation proof

Stage 6/Lens now has a bounded supervisor-observation proof for the future Lens
resident host. `scripts/lens-host-supervisor-observation-proof.ps1 -Mode Status`
uses the existing `scripts/lens-host.ps1 -Mode Launch -RunSeconds <n>` path
against an isolated temporary data directory, observes the launch runner's
foreground-running process readback, waits for the same process to self-stop,
then verifies post-stop status readback as `state_present_process_not_running`.

The Stage 6 checkpoint now consumes this proof. The `system_resident_presence`
criterion advances from `bounded_host_launch_observed` to
`bounded_supervisor_observed`, but remains blocked and `ready_to_close: false`.
This is intentionally not a resident/supervised host claim: the proof reports
`resident_host_process: false`, `supervised: false`,
`process_restart_authority: false`, `process_supervision_authority: false`, and
`service_control_authority: false`. The next smallest truthful gap is now
`resident_host_process_supervision_or_resident_overlay_runtime`.

This is diagnostic proof/checkpoint work only. It grants no product execution
authority, no API launch authority, no process-restart authority, no process
supervision authority, no service install/control authority, no approval-decision
authority, no memory-write authority, no tray registration, no hotkey
registration, no overlay control, and no summon-anywhere claim. It does perform
bounded diagnostic local process launch through the existing launch runner and
records that distinction explicitly.

Latest targeted validation for the `2026-04-29` Stage 6/Lens bounded supervisor
observation proof:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-supervisor-observation-proof.ps1 -Mode Status -RunSeconds 4`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status -HostLaunchRunSeconds 3 -SupervisorRunSeconds 4`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_stage6_checkpoint_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_host_launch_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_host_foreground_proof_script.py tests\test_lens_host_foreground_script.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_live_operator_proof_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident overlay runtime boundary proof

Stage 6/Lens now has a composed resident overlay runtime boundary proof for the
future resident Lens surface.
`scripts/lens-resident-overlay-runtime-proof.ps1 -Mode Status` runs the existing
resident-surface readiness proof and the bounded supervisor-observation proof,
then verifies that the repo can observe both sides of the boundary at once: one
bounded diagnostic Lens host lifecycle can be seen through running/stopped
states, while overlay, tray, global hotkey, and summon-anywhere preflights remain
readable, disabled, and blocked.

The proof reports `kind: lens.resident_overlay_runtime.proof`,
`status: proof_passed`, `bounded_supervisor_observed: true`, and
`temporary_host_process_observed: true`, while keeping
`resident_overlay_runtime_ready: false`, `resident_overlay_runtime: false`,
`resident_host_process: false`, `supervised: false`, `overlay_window: false`,
`tray_presence: false`, `global_hotkey_bound: false`, and
`summon_anywhere: false`. The next smallest truthful gap reported by the proof is
`resident_overlay_activation_or_process_supervision_authority_boundary`.

This is diagnostic proof composition only. It does not change the Lens API,
Stage 6 checkpoint, chat UI, service configuration, host runner, approval paths,
or memory paths. It grants no product execution authority, no API launch
authority, no process-restart authority, no process-supervision authority, no
service install/control authority, no approval-decision authority, no
memory-write authority, no tray registration, no hotkey registration, no overlay
control, and no summon-anywhere claim. It does perform bounded diagnostic local
process launch through the existing supervisor-observation proof and records that
distinction explicitly.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident overlay
runtime boundary proof:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-resident-overlay-runtime-proof.ps1 -Mode Status -SupervisorRunSeconds 4`
  Result: `passed`
- `python -m pytest tests\test_lens_resident_overlay_runtime_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_resident_overlay_runtime_proof_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_resident_overlay_runtime_proof_script.py`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens checkpoint consumes resident overlay boundary

Stage 6/Lens completion checkpoint now consumes the resident overlay runtime
boundary proof. `scripts/lens-stage6-checkpoint.ps1 -Mode Status` invokes
`scripts/lens-resident-overlay-runtime-proof.ps1`, projects it into the
`system_resident_presence` criterion, and advances that criterion's checkpoint
status from `bounded_supervisor_observed` to
`resident_overlay_boundary_observed`.

The checkpoint now exposes a dedicated `resident_overlay_runtime_proof` block
with `status: proof_passed`, `bounded_supervisor_observed: true`,
`resident_overlay_runtime_ready: false`, `resident_overlay_runtime: false`,
`overlay_window: false`, `tray_presence: false`, `global_hotkey_bound: false`,
`summon_anywhere: false`, and `ready_for_lens_resident_claim: false`. The
checkpoint remains `status: blocked`, `stage_state: active`, and
`ready_to_close: false`, and its next smallest truthful gap is now
`resident_overlay_activation_or_process_supervision_authority_boundary`.

This is checkpoint/readback composition only. It does not change Lens API
routes, UI surfaces, service configuration, host runner behavior, approval
decisions, memory writes, process supervision, service control, tray
registration, hotkey registration, overlay control, or summon-anywhere behavior.
The checkpoint still performs bounded diagnostic local process launch through the
existing proof chain and reports that distinction explicitly.

Latest targeted validation for the `2026-04-29` Stage 6/Lens checkpoint
resident overlay boundary consumption:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status -HostLaunchRunSeconds 3 -SupervisorRunSeconds 4`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py -q`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident overlay activation boundary proof

Stage 6/Lens now has a composed resident overlay activation-boundary proof.
`scripts/lens-resident-overlay-activation-boundary-proof.ps1 -Mode Status`
runs the live operator readback proof, the resident overlay runtime boundary
proof, and the read-only resident-surface activation boundary. It verifies that
Francis can observe live Lens readback and a bounded resident-overlay runtime
boundary while the actual resident overlay activation path remains blocked.

The proof reports `kind: lens.resident_overlay_activation_boundary.proof`,
`status: proof_passed`, `live_operator_experience_proof: true`,
`resident_overlay_boundary_observed: true`, and
`activation_boundary_observed: true`, while keeping
`resident_overlay_activation_ready: false`, `activation_ready: false`,
`resident_surface_ready: false`, `resident_overlay_runtime_ready: false`,
`ready_for_lens_resident_claim: false`, `resident_claim_allowed: false`,
`execution_ready: false`, `executed: false`, and `applied: false`. The proof
also verifies that the activation plan would not launch a process, install or
start a service, register a hotkey, open an overlay, write memory, or decide an
approval.

This is diagnostic proof composition only. It does not change Lens API routes,
UI surfaces, service configuration, host runner behavior, approval decisions,
memory writes, process supervision, service control, tray registration, hotkey
registration, overlay control, or summon-anywhere behavior. It composes existing
bounded diagnostics that may start a temporary API process and a temporary
foreground host process, but it grants no resident activation authority and
writes no denial receipts or memory receipts.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident overlay
activation boundary proof:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-resident-overlay-activation-boundary-proof.ps1 -Mode Status -StartupTimeoutSeconds 20 -SupervisorRunSeconds 4`
  Result: `passed`
- `python -m pytest tests\test_lens_resident_overlay_activation_boundary_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_live_operator_proof_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_resident_overlay_activation_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_resident_overlay_activation_boundary_proof_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens checkpoint consumes overlay activation boundary

Stage 6/Lens completion checkpoint now consumes the resident overlay activation
boundary proof. `scripts/lens-stage6-checkpoint.ps1 -Mode Status` invokes
`scripts/lens-resident-overlay-activation-boundary-proof.ps1`, exposes a
dedicated `resident_overlay_activation_boundary_proof` block, and advances the
`system_resident_presence` checkpoint status from
`resident_overlay_boundary_observed` to
`resident_overlay_activation_boundary_observed`.

The checkpoint now reports the activation-boundary proof as `status:
proof_passed`, `live_operator_experience_proof: true`,
`resident_overlay_boundary_observed: true`, and
`activation_boundary_observed: true`, while keeping
`resident_overlay_activation_ready: false`, `activation_ready: false`,
`execution_ready: false`, `executed: false`, and `applied: false`. It also
projects the proof's non-authority fields: no process launch, service install,
service start, hotkey registration, overlay open, memory write, or approval
decision. The checkpoint remains `status: blocked`, `stage_state: active`, and
`ready_to_close: false`; its next smallest truthful gap is now
`process_supervision_authority_boundary_or_service_activation_plan`.

This is checkpoint/readback composition only. It does not change Lens API
routes, UI surfaces, service configuration, host runner behavior, approval
decisions, memory writes, resident process supervision, service control, tray
registration, hotkey registration, overlay control, or summon-anywhere behavior.
The checkpoint still performs bounded diagnostic local process launch through
the existing proof chain and reports that distinction explicitly.

Latest targeted validation for the `2026-04-29` Stage 6/Lens checkpoint overlay
activation boundary consumption:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status -HostLaunchRunSeconds 3 -SupervisorRunSeconds 4`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_live_operator_proof_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens process supervision authority boundary proof

Stage 6/Lens now has a composed process-supervision/service-activation
authority boundary proof. `scripts/lens-process-supervision-authority-boundary-proof.ps1`
composes the current Stage 6 checkpoint with the resident-host supervision proof
and verifies that the latest resident overlay activation boundary remains
checkpointed while future resident process supervision and service activation
are still blocked.

The proof reports `status: proof_passed` with `stage6_checkpoint_observed:
true`, `host_supervision_boundary_observed: true`,
`process_supervision_boundary_observed: true`, and
`service_activation_plan_observed: true`. It also reports
`supervision_ready: false`, `ready_for_resident_claim: false`,
`resident_claim_allowed: false`, `process_supervision_ready: false`, and
`service_activation_ready: false`. The proof keeps resident host supervision,
process restart, service install/start/control, tray presence, hotkey binding,
overlay window, summon-anywhere, execution, approval decisions, and memory writes
disabled.

This is a diagnostic/readback composition only. It does not change Lens API
routes, UI surfaces, service configuration, host runner behavior, approval
decisions, memory writes, resident process supervision, process restart
authority, service installation, service control, tray registration, hotkey
registration, overlay control, or summon-anywhere behavior. The proof still
observes bounded diagnostic local process launch from the existing host
supervision proof and reports that distinction explicitly.

Latest targeted validation for the `2026-04-29` Stage 6/Lens process supervision
authority boundary proof:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-process-supervision-authority-boundary-proof.ps1 -Mode Status -StartupTimeoutSeconds 20 -ForegroundRunSeconds 2 -HostLaunchRunSeconds 3 -SupervisorRunSeconds 4`
  Result: `passed`
- `python -m pytest tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident supervision enablement gate readback

Stage 6/Lens now has a direct read-only resident supervision enablement gate at
`/lens/host/supervision`. The route projects the existing Lens host launch
manifest, process readback, service readback, service install plan, required
bindings, and supervision readiness prerequisites into one operator-facing gate
for the future resident host supervision path.

The gate reports `kind: lens.host.supervision_enablement_gate`, `status:
blocked`, `ready: false`, `supervision_ready: false`,
`resident_claim_allowed: false`, `resident_host_supervised: false`,
`service_managed: false`, `would_install_service: false`,
`would_start_service: false`, `would_supervise_process: false`, and
`would_restart_process: false`. Its blockers include disabled process
supervision, missing service install/control authority, the disabled service
plan, and the remaining Lens runtime blockers. The Lens status payload now embeds
this gate under `resident_host.supervision_gate` and exposes a Stage 6 readiness
criterion named `resident_supervision_enablement_gate`.

This is backend/API readback only. It does not start, supervise, restart, install,
or control a resident Lens host process or Windows service. It does not grant
execution authority, approval-decision authority, memory-write behavior,
local-process-launch authority, process-supervision authority, process-restart
authority, service-install authority, service-control authority, resident-claim
authority, UI controls, tray registration, hotkey registration, overlay control,
or summon-anywhere behavior.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident supervision
enablement gate readback:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\host_manifest.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\host_manifest.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed after formatting`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens summon enablement gate readback

Stage 6/Lens now has a direct read-only summon enablement gate at `/lens/summon`.
The route projects the existing Lens primitive preflight state for summon,
resident host, tray, and overlay into one operator-facing gate for the future
summon-anywhere path.

The gate reports `kind: lens.summon.enablement_gate`, `status: blocked`,
`ready: false`, `summon_anywhere: false`, `summon_binding_ready: false`,
`resident_host_ready: false`, `tray_ready: false`, and `overlay_ready: false`.
It preserves the declared `Ctrl+Alt+Space` hotkey intent and reports blockers
including disabled global hotkey binding, missing resident host process, missing
tray/overlay surfaces, missing summon binding, and missing summon/hotkey/overlay
authority. The Lens status payload now embeds this gate under
`summon_enablement_gate` and exposes a Stage 6 readiness criterion named
`summon_enablement_gate` while keeping `summon_anywhere` itself
`not_implemented`.

This is backend/API readback only. It does not register a global hotkey, launch a
resident host, open an overlay, create tray presence, grant summon authority, or
claim OS-wide summon behavior. It does not grant execution authority,
approval-decision authority, memory-write behavior, local-process-launch
authority, hotkey-registration authority, tray-registration authority, overlay
control authority, or any new UI control.

Latest targeted validation for the `2026-04-29` Stage 6/Lens summon enablement
gate readback:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_summon_preflight_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\preflight.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\preflight.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens tray enablement gate readback

Stage 6/Lens now has a direct read-only tray/presence enablement gate at
`/lens/tray`. The route projects the existing Lens primitive preflight state for
tray, resident host, summon, and overlay into one operator-facing gate for the
future user-session tray or equivalent presence path.

The gate reports `kind: lens.tray.enablement_gate`, `status: blocked`, `ready:
false`, `tray_presence: false`, `tray_preflight_ready: false`,
`resident_host_ready: false`, `summon_binding_ready: false`, `overlay_ready:
false`, `tray_host_enabled: false`, `tray_icon_enabled: false`, and
`notification_supported: false`. Its blockers include disabled tray host/icon,
missing resident host process, missing summon/overlay prerequisites, and missing
tray-registration, tray-icon, notification, service-control, local-process-launch,
overlay-control, and summon authority. The Lens status payload now embeds this
gate under `tray_enablement_gate` and exposes a Stage 6 readiness criterion named
`tray_enablement_gate` while keeping tray presence itself blocked.

This is backend/API readback only. It does not register a tray icon, create
user-session presence, launch a resident host, register a hotkey, open an
overlay, send a notification, or claim resident Lens presence. It does not grant
execution authority, approval-decision authority, memory-write behavior,
local-process-launch authority, service-control authority, tray-registration
authority, tray-icon authority, notification authority, overlay-control
authority, summon authority, or any new UI control.

Latest targeted validation for the `2026-04-29` Stage 6/Lens tray enablement
gate readback:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\preflight.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\preflight.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens overlay enablement gate readback

Stage 6/Lens now has a direct read-only overlay/window enablement gate at
`/lens/overlay`. The route projects the existing Lens primitive preflight state
for overlay, resident host, summon, and tray into one operator-facing gate for
the future resident HUD/window path.

The gate reports `kind: lens.overlay.enablement_gate`, `status: blocked`,
`ready: false`, `overlay_window: false`, `overlay_preflight_ready: false`,
`resident_host_ready: false`, `summon_binding_ready: false`,
`tray_presence_ready: false`, `overlay_enabled: false`,
`window_enabled: false`, `always_on_top: false`, `dock_supported: false`,
`focus_supported: false`, `click_through_supported: false`, and
`capture_supported: false`. Its blockers include disabled overlay window and
always-on-top behavior, missing resident host process, missing summon/tray
prerequisites, and missing overlay-control, window-management, capture,
local-process-launch, tray-registration, and summon authority. The Lens status
payload now embeds this gate under `overlay_enablement_gate` and exposes a Stage
6 readiness criterion named `overlay_enablement_gate` while keeping resident
overlay/window behavior itself blocked.

This is backend/API readback only. It does not open, focus, dock, control, or
capture through an overlay window; launch a resident host; register tray
presence; register a hotkey; summon Francis anywhere; or claim resident Lens
runtime. It does not grant execution authority, approval-decision authority,
memory-write behavior, local-process-launch authority, service-control
authority, window-management authority, overlay-control authority, capture
authority, hotkey-registration authority, tray-registration authority, summon
authority, or any new UI control.

Latest targeted validation for the `2026-04-29` Stage 6/Lens overlay enablement
gate readback:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_summon_preflight_script.py tests\test_lens_tray_preflight_script.py tests\test_lens_overlay_preflight_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\preflight.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\preflight.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens UI enablement gate readback

The chat UI System/ORB Lens Readback panel now preserves and renders the Stage 6
resident enablement gate criteria from `/lens/status`. The Lens client parser
keeps typed readback fields for `resident_supervision_enablement_gate`,
`summon_enablement_gate`, `tray_enablement_gate`, and `overlay_enablement_gate`,
including readiness booleans, resident claim state, summon hotkey, tray presence
name, overlay window name, blockers, evidence routes, and authority-denial flags.

The operator surface now shows a compact read-only Resident enablement gates
block for host, summon, tray, and overlay. Each row is driven by the backend
criterion status and shows whether the gate is ready, the first evidence route,
and the leading blocker when one exists. This makes the recent backend gate work
operator-visible without adding activation controls or claiming resident runtime.

This is UI readback/parser work only. It does not create approvals, decide
approvals, launch a Lens host, install/start/control a service, register tray
presence, register a hotkey, open or control an overlay, capture screen content,
write memory, execute actions, or grant execution, approval-decision,
local-process-launch, service-control, tray-registration, tray-icon,
notification, hotkey-registration, overlay-control, window-management, capture,
summon, telemetry, sensing, or promotion authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens UI enablement gate
readback:

- `node --test --experimental-strip-types src/lens/index.test.ts`
  Result: `passed`
- `npm run test`
  Result: `passed`
- `npm run build`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens checkpoint enablement gate audit

The Stage 6/Lens checkpoint now exposes the direct host/summon/tray/overlay
enablement gates that were added after the earlier process-supervision boundary
proof. `scripts/lens-stage6-checkpoint.ps1 -Mode Status` reports
`enablement_gates` for `resident_supervision_enablement_gate`,
`summon_enablement_gate`, `tray_enablement_gate`, and
`overlay_enablement_gate`, plus summary counts for total, ready, and blocked
enablement gates.

The checkpoint remains `status: blocked`, `stage_state: active`, and
`ready_to_close: false`. It still reports two ready done criteria
(`mode_visibility` and `pilot_visibility_groundwork`) and three blocked done
criteria (`summon_anywhere`, `helpful_not_noisy`, and
`system_resident_presence`). The checkpoint's next smallest truthful gap now
points at `supervised_resident_host_tray_hotkey_overlay_runtime_plan` instead
of the already-ledgered process-supervision boundary proof.

This is checkpoint/readback audit work only. It does not launch a resident Lens
host, supervise or restart a process, install/start/control a service, register
tray presence, register a hotkey, open or control an overlay, capture screen
content, write memory, execute actions, decide approvals, or grant execution,
approval-decision, local-process-launch, process-supervision, process-restart,
service-install, service-control, tray-registration, tray-icon, notification,
hotkey-registration, overlay-control, window-management, capture, summon,
telemetry, sensing, or promotion authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens checkpoint
enablement gate audit:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-process-supervision-authority-boundary-proof.ps1 -Mode Status -StartupTimeoutSeconds 20 -ForegroundRunSeconds 2 -HostLaunchRunSeconds 3 -SupervisorRunSeconds 4`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed after correcting the new expected blocker assertion`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_api_lens.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens supervised resident runtime plan readback

Lens now exposes a read-only `/lens/resident-runtime/plan` route that composes
the existing host activation execution plan, resident supervision enablement
gate, summon gate, tray gate, and overlay gate into one supervised resident
runtime activation plan. The plan keeps runtime activation blocked and explicitly
projects that it would not launch a process, supervise or restart a process,
install/start/control a service, register tray presence, bind a hotkey, open an
overlay, capture screen content, write memory, write a runtime receipt, decide
an approval, or claim resident status.

`/lens/status` now embeds this runtime plan and adds a
`resident_runtime_activation_plan` Stage 6 readiness criterion with evidence
routes through `/lens/resident-runtime/plan`, `/lens/host/supervision`,
`/lens/summon`, `/lens/tray`, `/lens/overlay`, and `/lens/status`.
`/lens/resident-surface/activation` now includes the same runtime plan and uses
it to make the next smallest truthful gap
`implement_supervised_resident_runtime_authority`. The Stage 6 checkpoint script
now reports the runtime plan as observed and moves its next smallest truthful gap
from the now-shipped runtime-plan readback to
`supervised_resident_host_runtime_authority_boundary`.

This is backend API/readback and diagnostic projection work only. It does not
create approvals, decide approvals, launch a Lens host, supervise or restart a
process, install/start/control a service, register tray presence, register or
bind a hotkey, open or control an overlay, capture screen content, write memory,
write runtime receipts, execute actions, claim resident status, or grant
execution, approval-decision, local-process-launch, process-supervision,
process-restart, service-install, service-control, tray-registration, tray-icon,
notification, hotkey-registration, overlay-control, window-management, capture,
summon, telemetry, sensing, or promotion authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens supervised
resident runtime plan readback:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident runtime authority boundary

Stage 6/Lens now has a governed, non-executing resident-runtime activation
boundary. `POST /lens/resident-runtime/execute` accepts the same exact
activation approval id and actor context used by the resident runtime plan, then
returns `kind: lens.resident_runtime.activation.execution_denial` with
`applied: false`, `executed: false`, no receipt write, and explicit false
projections for process launch, process supervision, process restart, service
install/start/control, tray registration, hotkey registration, overlay open/control,
screen capture, memory write, approval decision, and resident claim.

`/lens/resident-runtime/plan` now names `/lens/resident-runtime/execute` as the
future execute route. `/lens/host`, `/lens/status`, and
`/lens/resident-surface/activation` embed the resident runtime denial readback.
Stage 6 readiness now includes `resident_runtime_authority_boundary` with
evidence through `/lens/resident-runtime/execute`, `/lens/resident-runtime/plan`,
and `/lens/status`. The Stage 6 checkpoint now reports
`resident_runtime_authority_boundary` as observed and moves its next smallest
truthful gap from `supervised_resident_host_runtime_authority_boundary` to
`supervised_resident_host_runtime_execution_authority_grant`.

This is backend API/readback, denial-boundary, and checkpoint projection work
only. It does not grant resident runtime execution authority. It does not launch
a Lens host, supervise or restart a process, install/start/control a service,
register tray presence, register or bind a hotkey, open or control an overlay,
capture screen content, write memory, write runtime receipts, decide approvals,
claim resident status, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident runtime
authority boundary:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed after formatting tests\test_lens_stage6_checkpoint_script.py`
- `git diff --check`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident runtime grant preflight

Stage 6/Lens now has a read-only resident-runtime grant preflight at
`/lens/resident-runtime/preflight`. The preflight composes the exact activation
approval, actor permission, operator posture, resident supervision gate, summon
gate, tray gate, and overlay gate before any future resident-runtime execution
authority can be considered. It reports `grant_ready: false`,
`authority_grant_ready: false`, `runtime_ready: false`, and
`resident_claim_allowed: false`, with explicit blockers including
`resident_runtime_authority_grant_not_implemented`,
`resident_runtime_execution_authority_not_granted`,
`process_supervision_authority_not_granted`, service-control denial,
tray/hotkey/overlay denial, receipt-write denial, and resident-claim denial.

`/lens/resident-runtime/plan`, `/lens/host`, `/lens/status`, and
`/lens/resident-surface/activation` now embed or link the same preflight
readback. Stage 6 readiness now includes
`resident_runtime_authority_grant_preflight`, and the Stage 6 checkpoint now
reports `resident_runtime_authority_grant_preflight_observed: true`. Because the
authority boundary and grant preflight are now both observable, the checkpoint's
next smallest truthful gap moves from
`supervised_resident_host_runtime_execution_authority_grant` to
`supervised_resident_host_runtime_execution_policy_contract`.

This is backend API/readback, readiness, and checkpoint projection work only. It
does not grant resident runtime execution authority. It does not launch a Lens
host, supervise or restart a process, install/start/control a service, register
tray presence, register or bind a hotkey, open or control an overlay, capture
screen content, write memory, write runtime receipts, decide approvals, claim
resident status, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident runtime
grant preflight:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed after formatting src\francis\lens\activation.py and tests\test_lens_stage6_checkpoint_script.py`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`
- `git diff --check`
  Result: `passed with PowerShell LF-to-CRLF working-copy warnings only`

### 2026-04-29 - Stage 6/Lens resident runtime execution policy contract

Stage 6/Lens now has a read-only resident-runtime execution policy contract at
`/lens/resident-runtime/policy`. The contract is deny-by-default and composes
the resident runtime grant preflight before any future execution authority can
be considered. It names the required exact Lens activation approval,
`system.write` actor scope, operator posture, supervision, summon, tray, hotkey,
overlay, receipt, and resident-claim requirements while reporting
`policy_contract_ready: true`, `execution_policy_ready: true`,
`grant_ready: false`, `authority_grant_ready: false`, `runtime_ready: false`,
and `resident_claim_allowed: false`.

`/lens/status`, `/lens/host`, `/lens/resident-runtime/plan`, and
`/lens/resident-surface/activation` now embed or link the same policy contract.
Stage 6 readiness now includes `resident_runtime_execution_policy_contract`,
and the Stage 6 checkpoint reports
`resident_runtime_execution_policy_contract_observed: true`. Because the
authority boundary, grant preflight, and policy contract are now observable, the
checkpoint's next smallest truthful gap moves from
`supervised_resident_host_runtime_execution_policy_contract` to
`supervised_resident_host_runtime_execution_authority_grant_boundary`.

This is backend API/readback, readiness, checkpoint, and test work only. It
does not grant resident runtime execution authority. It does not launch a Lens
host, supervise or restart a process, install/start/control a service, register
tray presence, register or bind a hotkey, open or control an overlay, capture
screen content, write memory, write runtime receipts, decide approvals, claim
resident status, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident runtime
execution policy contract:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `failed before formatting, passed after formatting tests\test_lens_stage6_checkpoint_script.py and tests\test_lens_process_supervision_authority_boundary_proof_script.py`
- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`
- `git diff --check`
  Result: `passed with PowerShell LF-to-CRLF working-copy warnings only`

### 2026-04-29 - Stage 6/Lens resident runtime authority grant boundary

Stage 6/Lens now has a governed, non-mutating resident-runtime authority grant
denial boundary at `/lens/resident-runtime/authority-grant`. The boundary
answers attempted resident-runtime execution authority grants with
`authority_granted: false`, `applied: false`, `executed: false`,
`grant_ready: false`, `authority_grant_ready: false`, `runtime_ready: false`,
and `resident_claim_allowed: false`. It composes the resident-runtime grant
preflight and execution policy contract, then denies the grant with
`resident_runtime_authority_grant_not_implemented` while preserving the existing
process-supervision, service-control, tray, hotkey, overlay, receipt-write, and
resident-claim blockers.

`/lens/status`, `/lens/host`, `/lens/resident-runtime/policy`,
`/lens/resident-runtime/plan`, and `/lens/resident-surface/activation` now embed
or link the authority grant boundary. Stage 6 readiness now includes
`resident_runtime_execution_authority_grant_boundary`, and the Stage 6
checkpoint reports
`resident_runtime_execution_authority_grant_boundary_observed: true`. Because
the authority boundary, grant preflight, policy contract, and authority-grant
denial boundary are now observable, the checkpoint's next smallest truthful gap
moves from `supervised_resident_host_runtime_execution_authority_grant_boundary`
to
`supervised_resident_host_runtime_execution_authority_grant_denial_receipt_readback`.

This is backend API/readback, denial-boundary, readiness, checkpoint, and test
work only. It does not grant resident runtime execution authority. It does not
launch a Lens host, supervise or restart a process, install/start/control a
service, register tray presence, register or bind a hotkey, open or control an
overlay, capture screen content, write memory, write runtime receipts, decide
approvals, claim resident status, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident runtime
authority grant boundary:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident runtime authority grant denial receipt readback

Stage 6/Lens now has durable denial receipt persistence and readback for
resident-runtime authority-grant attempts. `POST
/lens/resident-runtime/authority-grant` still denies resident runtime execution
authority, but when the exact Lens activation approval, `system.write` actor
scope, and operator posture gates are ready, the denial now records a bounded
`lens.resident_runtime.execution_authority_grant.denial.receipt` under the Lens
data root. `GET /lens/resident-runtime/authority-grant/denials` returns those
receipts with approval, permission, policy, authority-grant, denial, and
governance summaries while remaining read-only.

`/lens/status` and `/lens/host` now expose
`resident_runtime_authority_grant_denial_receipts`, Stage 6 readiness includes
`resident_runtime_authority_grant_denial_receipt_readback`, and the Stage 6
checkpoint reports
`resident_runtime_execution_authority_grant_denial_receipt_readback_observed:
true`. Because the denial boundary and denial receipt readback are now
observable, the checkpoint's next smallest truthful gap moves from
`supervised_resident_host_runtime_execution_authority_grant_denial_receipt_readback`
to `supervised_resident_host_runtime_authority_grant_readiness_audit`.

This is backend API/readback, bounded denial-receipt persistence, readiness,
checkpoint, and test work only. It does not grant resident runtime execution
authority, approval decision authority, local process launch authority, process
supervision or restart authority, service install/control authority, tray,
hotkey, overlay, summon, capture, memory-write, or resident-claim authority. It
does not launch a Lens host, supervise or restart a process, install/start/control
a service, register tray presence, register or bind a hotkey, open or control an
overlay, capture screen content, write memory, decide approvals, claim resident
status, or add UI controls. The only new write behavior is the bounded denial
receipt for a denied authority-grant attempt after the existing approval/scope
gate is ready.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident runtime
authority grant denial receipt readback:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed after formatting`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident runtime authority grant readiness audit

Stage 6/Lens now has a read-only readiness audit for the resident-runtime
authority-grant path. `GET
/lens/resident-runtime/authority-grant/readiness` composes the existing resident
runtime preflight, execution policy contract, authority-grant denial boundary,
authority-grant denial receipt readback, runtime activation plan, and Lens host
enablement gates into one blocker-oriented audit record. The audit reports which
requirements are ready, which are blocked, and which exact blockers prevent
Francis from truthfully granting resident runtime execution authority.

`/lens/status` now projects
`resident_runtime_authority_grant_readiness`, Stage 6 readiness includes
`resident_runtime_authority_grant_readiness_audit`, and the Stage 6 checkpoint
reports
`resident_runtime_execution_authority_grant_readiness_audit_observed: true`.
Because the readiness audit is now observable, the checkpoint's next smallest
truthful gap moves from
`supervised_resident_host_runtime_authority_grant_readiness_audit` to
`resolve_supervised_resident_host_runtime_authority_grant_blockers`.

This is backend API/readback, diagnostic checkpoint, and test work only. It is
read-only and audit-only. It does not grant resident runtime execution authority,
approval decision authority, local process launch authority, process supervision
or restart authority, service install/control authority, tray, hotkey, overlay,
summon, capture, memory-write, receipt-write, denial-receipt-write, or
resident-claim authority. It does not launch a Lens host, supervise or restart a
process, install/start/control a service, register tray presence, register or
bind a hotkey, open or control an overlay, capture screen content, write memory,
write receipts, decide approvals, claim resident status, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident runtime
authority grant readiness audit:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed after formatting`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident host supervision authority preflight

Stage 6/Lens now has a read-only resident host supervision authority preflight at
`GET /lens/host/supervision/authority`. The preflight composes the existing Lens
host launch manifest, resident supervision enablement gate, service plan,
foreground process readback, service readback, and supervision readiness into one
authority-focused blocker record. It separates operational prerequisites from
authority prerequisites and makes the missing process-supervision, process-restart,
service-install, service-control, and resident-claim authority explicit before
any future resident host supervision implementation can be considered.

`/lens/status` now projects `supervision_authority_preflight` under
`resident_host`, Stage 6 readiness includes
`resident_host_supervision_authority_preflight`, and the Stage 6 checkpoint
reports `resident_host_supervision_authority_preflight_observed: true`. Because
the preflight is now observable, the checkpoint's next smallest truthful gap
moves from `resolve_supervised_resident_host_runtime_authority_grant_blockers`
to `supervised_resident_host_process_supervision_authority_denial_boundary`.

This is backend API/readback, diagnostic checkpoint, and test work only. It is
read-only and preflight-only. It does not grant resident runtime execution
authority, approval decision authority, local process launch authority, process
supervision or restart authority, service install/control authority, tray,
hotkey, overlay, summon, capture, memory-write, receipt-write,
denial-receipt-write, or resident-claim authority. It does not launch a Lens
host, supervise or restart a process, install/start/control a service, register
tray presence, register or bind a hotkey, open or control an overlay, capture
screen content, write memory, write receipts, decide approvals, claim resident
status, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident host
supervision authority preflight:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\host_manifest.py src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed after formatting`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident host supervision authority denial boundary

Stage 6/Lens now has a governed denial boundary for attempted resident host
supervision authority grants at `POST /lens/host/supervision/authority`. The
route is the write-attempt side of the existing read-only preflight: it evaluates
the actor through the existing `system.write` API permission gate, carries the
host supervision preflight blockers forward, and always returns a typed
`lens.host.supervision_authority.denial` response with `boundary_ready: true`,
`applied: false`, `executed: false`, and `authority_granted: false`.

`/lens/status` now projects `supervision_authority_denial` under
`resident_host`, Stage 6 readiness includes
`resident_host_supervision_authority_denial_boundary`, the resident runtime
authority readiness audit composes the host supervision authority denial boundary,
and the Stage 6 checkpoint reports
`resident_host_supervision_authority_denial_boundary_observed: true`. Because the
denial boundary is now observable, the checkpoint's next smallest truthful gap
moves from `supervised_resident_host_process_supervision_authority_denial_boundary`
to `resident_host_supervision_authority_denial_receipt_readback`.

This is backend API/readback, diagnostic checkpoint, and test work only. It does
not grant resident runtime execution authority, approval decision authority,
local process launch authority, process supervision or restart authority, service
install/control authority, tray, hotkey, overlay, summon, capture, memory-write,
receipt-write, denial-receipt-write, or resident-claim authority. It does not
launch a Lens host, supervise or restart a process, install/start/control a
service, register tray presence, register or bind a hotkey, open or control an
overlay, capture screen content, write memory, write receipts, decide approvals,
claim resident status, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident host
supervision authority denial boundary:

- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident host supervision authority denial receipt readback

Stage 6/Lens now has durable denial receipt persistence and readback for
resident host supervision authority denials. `POST /lens/host/supervision/authority`
still denies the attempted authority grant, but when the existing `system.write`
actor gate is ready it now writes a bounded
`lens.host.supervision_authority.denial.receipt` under local Lens data and returns
the receipt plus `/lens/host/supervision/authority/denials` as the readback route.

The new `GET /lens/host/supervision/authority/denials` route lists those denial
receipts with status filtering. `/lens/status` projects the readback under
`resident_host.supervision_authority_denial_receipts`, Stage 6 readiness includes
`resident_host_supervision_authority_denial_receipt_readback`, and the Stage 6
checkpoint now reports
`resident_host_supervision_authority_denial_receipt_readback_observed: true`.
Because the host supervision authority denial boundary and denial receipt
readback are now both observable, the checkpoint's next smallest truthful gap
moves from `resident_host_supervision_authority_denial_receipt_readback` to
`resident_host_supervision_authority_readiness_audit`.

This is backend API/readback, bounded receipt-persistence, diagnostic checkpoint,
and test work only. It does not grant resident runtime execution authority,
approval decision authority, local process launch authority, process supervision
or restart authority, service install/control authority, tray, hotkey, overlay,
summon, capture, memory-write, live resident-claim, or UI authority. It does not
launch a Lens host, supervise or restart a process, install/start/control a
service, register tray presence, register or bind a hotkey, open or control an
overlay, capture screen content, write memory, decide approvals, claim resident
status, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident host
supervision authority denial receipt readback:

- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`; `next_smallest_truthful_gap` is
  `resident_host_supervision_authority_readiness_audit`

### 2026-04-29 - Stage 6/Lens resident host supervision authority readiness audit

Stage 6/Lens now has a read-only readiness audit for resident host supervision
authority at `GET /lens/host/supervision/authority/readiness`. The audit
composes the existing host supervision enablement gate, supervision authority
preflight, governed authority-denial boundary, and denial-receipt readback into
one explicit blocker report before any future process-supervision or service
control implementation can be considered.

`/lens/status` now projects this audit under
`resident_host.supervision_authority_readiness`, Stage 6 readiness includes
`resident_host_supervision_authority_readiness_audit`, and the Stage 6
checkpoint now reports
`resident_host_supervision_authority_readiness_audit_observed: true`. Because
the host supervision authority preflight, denial boundary, denial receipt
readback, and readiness audit are now all observable, the checkpoint's next
smallest truthful gap moves from
`resident_host_supervision_authority_readiness_audit` to
`stage6_lens_completion_audit`.

This is backend API/readback, diagnostic checkpoint, and test work only. It does
not grant resident runtime execution authority, approval decision authority,
local process launch authority, process supervision or restart authority,
service install/control authority, tray, hotkey, overlay, summon, capture,
memory-write, receipt-write, live resident-claim, or UI authority. It does not
launch a Lens host, supervise or restart a process, install/start/control a
service, register tray presence, register or bind a hotkey, open or control an
overlay, capture screen content, write memory, decide approvals, claim resident
status, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident host
supervision authority readiness audit:

- `python -m pytest tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\api\routes\lens.py src\francis\lens\__init__.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m mypy src\francis\lens src\francis\api\routes\lens.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`; `next_smallest_truthful_gap` is
  `stage6_lens_completion_audit`

### 2026-04-29 - Stage 6/Lens completion audit diagnostic

Stage 6/Lens now has a status-only completion audit diagnostic.
`scripts/lens-stage6-completion-audit.ps1 -Mode Status` consumes the existing
Stage 6 checkpoint and turns it into an explicit closure decision. The current
repo truth is `kind: lens.stage6.completion_audit`, `status: blocked`,
`audit_status: complete`, `ready_to_close: false`, `can_close_stage6: false`,
`transition_allowed: false`, and `closure_decision: do_not_close_stage6`.

The audit preserves the checkpoint's two ready criteria (`mode_visibility` and
`pilot_visibility_groundwork`) and three blocked criteria (`summon_anywhere`,
`helpful_not_noisy`, and `system_resident_presence`). It also groups the closure
blockers by resident surface, summon/hotkey, tray, overlay, host supervision,
and authority so the next session does not have to infer the remaining Stage 6
work from a long checkpoint payload. Because the completion audit has now run,
the next smallest truthful gap moves from `stage6_lens_completion_audit` to the
concrete blocker `resident_surface_missing`.

This confirms Stage 6/Lens cannot truthfully close yet. Stage 7/Telemetry must
not begin until Stage 6 has either resolved the resident-surface and resident
presence blockers or a later audited roadmap decision explicitly narrows the
Stage 6 closure claim.

This is diagnostic/readback-only. It does not launch a Lens host, supervise or
restart a process, install/start/control a service, register tray presence,
register or bind a hotkey, open or control an overlay, capture screen content,
write memory, write receipts, decide approvals, claim resident status, grant
execution authority, grant resident runtime authority, grant process-supervision
authority, or add UI controls.

Latest targeted validation for the `2026-04-29` Stage 6/Lens completion audit
diagnostic:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1 -Mode Status`
  Result: `passed`; `next_smallest_truthful_gap` is
  `resident_surface_missing`
- `python -m pytest tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident surface proof consumes live operator proof

Stage 6/Lens resident-surface readiness proof now consumes the existing live
operator experience proof instead of carrying a stale operator-experience
blocker after that proof has passed. `scripts/lens-resident-surface-proof.ps1
-Mode Status` invokes `scripts/lens-live-operator-proof.ps1 -Mode Status`,
requires the live HTTP `/lens/status?limit=5` readback proof to pass, and
returns `operator_experience_proof: true`,
`live_operator_experience_proof: true`, and `live_http_status_readback: true`
while still reporting `resident_surface_ready: false`,
`ready_for_lens_resident_claim: false`, and `resident_claim_allowed: false`.

The proof no longer reports `operator_experience_proof_missing` when the live
operator proof is available. Its next smallest truthful gap is now
`resident_host_or_resident_overlay_runtime`, matching the current Stage 6
blocker posture: the operator readback proof exists, but Francis still lacks a
supervised resident host, resident overlay runtime, tray presence, hotkey
binding, and summon-anywhere behavior.

This is diagnostic/readback-only. It adds a nested temporary local API proof
process through the existing live-operator proof, but it does not create a
resident Lens host; install, start, stop, supervise, or control a service;
register tray presence; bind a global hotkey; open or control an overlay;
summon Francis anywhere; write memory; decide approvals; create new UI
controls; or grant execution, approval-decision, memory-write,
process-supervision, service-control, overlay-control, window-management,
summon, hotkey-registration, tray-registration, sensing, capture, telemetry, or
resident-claim authority.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident surface
proof/live-operator composition:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-resident-surface-proof.ps1 -Mode Status`
  Result: `passed`
- `python -m pytest tests\test_lens_resident_surface_proof_script.py tests\test_lens_live_operator_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_resident_surface_proof_script.py tests\test_lens_live_operator_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_resident_surface_proof_script.py tests\test_lens_live_operator_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status`
  Result: `passed`; Stage 6 remains `blocked` with `ready_total: 2`,
  `blocked_total: 3`, and `next_smallest_truthful_gap:
  stage6_lens_completion_audit`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1 -Mode Status`
  Result: `passed`; Stage 6 remains `blocked`, `closure_decision:
  do_not_close_stage6`, and `next_smallest_truthful_gap:
  resident_surface_missing`
- `python -m pytest tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `git diff --check`
  Result: `passed` with the expected PowerShell line-ending warning for
  `scripts/lens-resident-surface-proof.ps1`

### 2026-04-29 - Stage 6/Lens bounded host supervisor runner

Stage 6/Lens now has a reusable bounded host-supervisor diagnostic runner at
`scripts/lens-host-supervisor.ps1`. The runner has a status mode for read-only
host/supervisor posture readback and an observe mode that watches an
already-started bounded `scripts/lens-host.ps1 -Mode Foreground` process through
`foreground_running` and `foreground_stopped` runtime receipts. It writes only a
temporary diagnostic supervisor status receipt under the selected data root in
observe mode.

This is diagnostic/proof infrastructure only. It does not launch the host,
restart a process, supervise a resident process, install/start/stop/control a
service, register tray presence, bind a global hotkey, open or control an
overlay, summon Francis anywhere, write memory, decide approvals, create UI
controls, or grant execution, approval-decision, memory-write,
process-supervision, process-restart, service-control, overlay-control,
window-management, summon, hotkey-registration, tray-registration, sensing,
capture, telemetry, or resident-claim authority.

Stage 6 remains blocked. This slice makes the next resident host/supervision
work more truthful by separating "observe an existing bounded foreground host"
from "grant resident supervision or restart authority." It does not satisfy the
resident host, resident overlay runtime, tray, hotkey, or summon-anywhere
acceptance criteria by itself.

Latest targeted validation for the `2026-04-29` Stage 6/Lens bounded host
supervisor runner. The live lifecycle assertion is Windows-hosted because the
Lens resident host target is Windows-facing and Unix child reaping can keep an
exited process visible to process readback until the Python test parent reaps
it; status/read-only coverage remains cross-platform:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-supervisor.ps1 -Mode Status`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervisor_script.py tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_supervisor_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_supervisor_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens supervisor proof consumes bounded runner

Stage 6/Lens host-supervisor observation proof now consumes the reusable
`scripts/lens-host-supervisor.ps1 -Mode Observe` runner instead of duplicating
the lifecycle observation inline. The proof starts one bounded diagnostic
`scripts/lens-host.ps1 -Mode Launch` process asynchronously, lets the reusable
supervisor runner observe the `foreground_running` and `foreground_stopped`
runtime receipts, then verifies post-stop status readback.

The proof payload now records `supervisor_runner`,
`supervisor_runner_status`, `supervisor_runner_exit_code`,
`supervisor_state_path`, `running_state_source:
supervisor_runner_observe`, `stopped_process_alive`, and a
`supervisor_runner_consumed` check. Downstream resident-overlay, activation,
checkpoint, and process-supervision boundary proofs use a 10-second bounded
supervisor observation window because the previous 4-second window was too
tight when the reusable runner was consumed through nested proof chains. The
host launch wrapper and supervisor runner now wait up to the bounded run window
plus startup slack for the initial running-state receipt, and the Stage 6
checkpoint treats any passed
supervisor-consuming proof in the chain as evidence for bounded supervisor
observation. The supervisor runner also waits for the stopped host pid file to
be removed after the stopped-state receipt and uses the refreshed stopped-state
readback plus pid-file cleanup as the post-stop proof contract, avoiding
redundant live process probing after the stopped readback is already false.

This is diagnostic/readback proof wiring only. It does not create a resident
host, supervise or restart a process, install/start/stop/control a service,
register tray presence, bind a global hotkey, open or control an overlay,
summon Francis anywhere, write memory, decide approvals, create UI controls, or
grant execution, approval-decision, memory-write, process-supervision,
process-restart, service-control, overlay-control, window-management, summon,
hotkey-registration, tray-registration, sensing, capture, telemetry, or
resident-claim authority.

Stage 6 remains blocked. This removes a proof-chain duplication gap and makes
the existing supervisor runner a consumed source of truth, but it does not
satisfy the resident host, resident overlay runtime, tray, hotkey, or
summon-anywhere acceptance criteria.

Latest targeted validation for the `2026-04-29` Stage 6/Lens supervisor proof
runner consumption:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-supervisor-observation-proof.ps1 -Mode Status`
  Result: `passed`; proof reported `supervisor_runner_consumed` and
  `supervisor_runner_status: observation_completed`
- `python -m pytest tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed` after checkpoint governance aggregation used the strongest
  passed supervisor-consuming proof in the chain
- `python -m pytest tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed` with expected PowerShell LF-to-CRLF warnings only

### 2026-04-29 - Stage 6/Lens resident surface readback contract

Stage 6/Lens now has a direct read-only `/lens/resident-surface` backend
readback route for the future resident Lens surface. The route composes the
existing Lens status truth into an operator-facing content contract: mode and
scope, HUD summary, approval queue, mission feed, incident feed, command
palette, resident host, resident-runtime route links, enablement gates, and the
existing resident-surface activation boundary. The same readback is embedded in
`/lens/status` as `resident_surface`, and the receipts block now advertises
`lens_resident_surface_route` and
`lens_resident_surface_activation_route`.

This is backend readback/API truth only. It explicitly reports
`availability: backend_readback_only`, `status: blocked`,
`content_contract_ready: true`, `resident_surface_ready: false`,
`resident_overlay_runtime: false`, and the remaining
`resident_surface_missing`, `resident_overlay_runtime_missing`, and
`resident_host_process_missing` blockers. It does not create a resident host,
launch or supervise a process, install/start/stop/control a service, register
tray presence, bind a hotkey, open/control an overlay, summon Francis anywhere,
write memory, decide approvals, create UI controls, or grant execution,
approval-decision, memory-write, process-supervision, process-restart,
service-control, overlay-control, summon, hotkey-registration,
tray-registration, capture, telemetry, or resident-claim authority.

Stage 6 remains blocked. The direct resident-surface readback route makes the
future surface content contract inspectable before UI/runtime work, but the
completion audit still reports `do_not_close_stage6` with the next smallest
truthful gap at `resident_surface_missing`.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident surface
readback contract:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1 -Mode Status`
  Result: `passed`; audit reported `closure_decision:
  do_not_close_stage6`, `transition_allowed: false`, and
  `next_smallest_truthful_gap: resident_surface_missing`
- `python -m ruff check src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed` with non-fatal `.ruff_cache` access warnings
- `git diff --check`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident surface proof consumes direct readback

Stage 6/Lens resident-surface readiness proof now consumes the direct
`/lens/resident-surface?limit=5` backend readback contract before reporting the
surface content contract as ready. The proof verifies the route kind, blocked
status, `contract_status: readback_ready`, route links, content-contract flag,
remaining blocked resident-surface/runtime flags, and no execution, approval,
memory-write, overlay-control, summon, process-supervision, service-control, or
resident-claim authority.

The Stage 6 checkpoint now embeds this as
`resident_surface_content_readback`, adds `/lens/resident-surface` evidence to
the helpful-not-noisy and system-resident criteria, and reports
`helpful_not_noisy` as `resident_surface_content_readback_ready` while keeping
the criterion blocked on `resident_surface_runtime_missing`. The completion
audit now prefers `resident_surface_runtime_missing` over the older generic
`resident_surface_missing` gap when the content contract is directly readable.

This slice also stabilizes the bounded supervisor-observation proof chain that
feeds the resident overlay runtime proof. The supervisor runner now treats a
`foreground_stopped` runtime state with no pid file as no longer owning a live
host process, avoiding stale-PID/PID-reuse false positives during rapid nested
Windows PowerShell validation. The bounded supervisor proof defaults now use a
20-second observation window, and the existing final host-status readback remains
the separate check that the bounded host is not running.

This is readback/proof/checkpoint/audit truth only. It does not create a
resident host, launch or supervise a process, install/start/stop/control a
service, register tray presence, bind a hotkey, open/control an overlay, summon
Francis anywhere, write memory, decide approvals, create UI controls, or grant
execution, approval-decision, memory-write, process-supervision, process-restart,
service-control, overlay-control, summon, hotkey-registration, tray-registration,
capture, telemetry, or resident-claim authority.

Stage 6 remains blocked. The next smallest truthful gap is now sharper:
resident-surface content readback exists, but the actual resident surface runtime
is still missing.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident surface
proof direct-readback consumption:

- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: first run exposed a transient nested proof mismatch; rerun passed.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-resident-overlay-runtime-proof.ps1 -Mode Status`
  Result: `passed`; status `proof_passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-resident-overlay-activation-boundary-proof.ps1 -Mode Status`
  Result: `passed`; status `proof_passed`
- `python -m pytest tests\test_lens_host_supervisor_script.py tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py -q`
  Result: `passed` twice back-to-back
- `python -m pytest tests\test_lens_resident_surface_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: first run exposed a transient checkpoint nested runtime proof mismatch;
  rerun passed.
- `python -m pytest tests\test_lens_resident_surface_proof_script.py tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens resident surface blocker normalization

Stage 6/Lens resident surface readback, live operator proof, host supervision
proof, and resident surface activation boundary now consistently report the
remaining surface blocker as `resident_surface_runtime_missing` once the direct
`/lens/resident-surface` backend content contract is readable. This removes the
old generic `resident_surface_missing` claim from the direct readback and proof
payloads that already know the surface content contract exists.

The live operator proof now verifies the resident-surface readback from the live
`/lens/status?limit=5` API payload, exposes `resident_surface_content_readback:
true`, preserves `/lens/resident-surface` route/contract evidence in its proof
payload, and keeps `live_operator_experience_ready: false` and
`ready_for_stage6_closure: false`. The resident surface activation boundary and
runtime preflight/plan blockers now carry the same runtime-missing blocker
language.

This is readback/proof/blocker truth only. It does not create a resident host,
launch or supervise a product process, install/start/stop/control a service,
register tray presence, bind a hotkey, open/control an overlay, summon Francis
anywhere, write memory, decide approvals, create UI controls, or grant
execution, approval-decision, memory-write, process-supervision,
process-restart, service-control, overlay-control, summon, hotkey-registration,
tray-registration, capture, telemetry, or resident-claim authority.

Stage 6 remains blocked. The next smallest truthful gap remains the actual
resident surface/runtime path behind `resident_surface_runtime_missing`.

Latest targeted validation for the `2026-04-30` Stage 6/Lens resident surface
blocker normalization:

- `python -m pytest tests\test_api_lens.py tests\test_lens_live_operator_proof_script.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-live-operator-proof.ps1 -Mode Status`
  Result: `passed`; status `proof_passed`, blockers normalized to
  `resident_surface_runtime_missing`
- `python -m ruff check --no-cache src\francis\lens\status.py src\francis\lens\activation.py tests\test_api_lens.py tests\test_lens_live_operator_proof_script.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\status.py src\francis\lens\activation.py tests\test_api_lens.py tests\test_lens_live_operator_proof_script.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed` with expected PowerShell LF-to-CRLF warnings

### 2026-04-30 - Stage 6/Lens resident surface foreground runtime readback

Stage 6/Lens resident-surface readback now projects a dedicated
`resident_surface_runtime` readback from the existing Lens host process state.
When no bounded foreground Lens host process is observed, `/lens/resident-surface`
continues to report `resident_surface_runtime_missing`. When the existing
bounded foreground host state is present and the process is alive, the same
route reports `foreground_runtime_observed: true`,
`resident_surface_runtime.status: foreground_runtime_observed`, and replaces the
generic runtime-missing blocker with `resident_surface_runtime_not_supervised`
and `resident_surface_not_resident`.

This is a readback-only runtime observation. It does not make the foreground
host resident, supervise or restart the process, install/start/stop/control a
service, register tray presence, bind a hotkey, open/control an overlay, summon
Francis anywhere, write memory, decide approvals, create UI controls, or grant
execution, approval-decision, memory-write, process-supervision,
process-restart, service-control, overlay-control, summon, hotkey-registration,
tray-registration, capture, telemetry, or resident-claim authority.

Stage 6 remains blocked. The next smallest truthful gap is to consume this
foreground runtime readback in a focused resident-surface runtime proof/checkpoint
path, then continue toward a real supervised resident runtime only behind the
existing authority gates.

Latest targeted validation for the `2026-04-30` Stage 6/Lens resident surface
foreground runtime readback:

- `python -m pytest tests\test_api_lens.py::test_lens_api_observes_live_foreground_process_readback -q`
  Result: `failed` before fix because the new PID readback reused a bounded
  display helper that clamps values at `5000`; after scoping the PID readback to
  a larger maximum, result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_resident_surface_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`

### 2026-04-29 - Stage 6/Lens resident surface proof consumes foreground runtime readback

Stage 6/Lens resident-surface readiness proof now consumes the foreground
runtime readback that `/lens/resident-surface` exposes. The proof starts a
bounded foreground Lens host session against a temporary data root, reads
`/lens/resident-surface` while the host runtime state is live, verifies
`resident_surface_runtime.status: foreground_runtime_observed`, and carries the
normalized blockers `resident_surface_runtime_not_supervised` and
`resident_surface_not_resident` instead of treating the runtime as missing in
the proof's top-level blocker set.

The API host-manifest reader now accepts UTF-8 with BOM for runtime JSON files.
That matches the runtime state written by Windows PowerShell status scripts and
prevents the API from observing a live PID while losing the `foreground_running`
state field.

This is proof/readback and parser hardening only. It does not make the
foreground host resident, supervise or restart the process, install/start/stop
or control a service, register tray presence, bind a hotkey, open/control an
overlay, summon Francis anywhere, write memory, decide approvals, create UI
controls, or grant execution, approval-decision, memory-write,
process-supervision, process-restart, service-control, overlay-control, summon,
hotkey-registration, tray-registration, capture, telemetry, or resident-claim
authority.

Stage 6 remains blocked. The next smallest truthful gap is to consume this
resident-surface foreground runtime proof in the Stage 6 checkpoint and
completion-audit path, then continue toward a supervised resident runtime only
behind the existing authority gates.

Latest targeted validation for the `2026-04-29` Stage 6/Lens resident surface
foreground runtime proof:

- `python -m pytest tests\test_lens_resident_surface_proof_script.py -q`
  Result: `failed` before fix because the API host-manifest reader treated the
  PowerShell-written UTF-8 BOM runtime state as invalid JSON and therefore lost
  `foreground_running`; after accepting UTF-8 with BOM and widening the bounded
  diagnostic foreground window, result: `passed`
- `python -m pytest tests\test_api_lens.py::test_lens_api_observes_live_foreground_process_readback tests\test_lens_resident_surface_proof_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py tests\test_lens_resident_surface_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\host_manifest.py tests\test_lens_resident_surface_proof_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed` with expected PowerShell LF-to-CRLF warning for
  `scripts/lens-resident-surface-proof.ps1`

### 2026-04-30 - Stage 6/Lens checkpoint consumes foreground runtime proof

Stage 6/Lens completion checkpoint now consumes the resident-surface foreground
runtime proof. `scripts/lens-stage6-checkpoint.ps1` invokes
`scripts/lens-resident-surface-proof.ps1`, verifies the bounded foreground
runtime readback, exposes it as `resident_surface_foreground_runtime_proof`, and
moves the `helpful_not_noisy` criterion from
`resident_surface_content_readback_ready` with `resident_surface_runtime_missing`
to `resident_surface_foreground_runtime_observed` with
`resident_surface_runtime_not_supervised` and `resident_surface_not_resident`.

The Stage 6 completion audit now prefers
`resident_surface_runtime_not_supervised` as the next smallest truthful gap when
the checkpoint has consumed the foreground runtime proof. This keeps the audit
from reporting the older missing-runtime blocker after a bounded foreground
runtime has already been observed.

This is checkpoint/audit readback composition only. It does not make the
foreground host resident, supervise or restart the process, install/start/stop
or control a service, register tray presence, bind a hotkey, open/control an
overlay, summon Francis anywhere, write memory, decide approvals, create UI
controls, write receipts, or grant execution, approval-decision, memory-write,
process-supervision, process-restart, service-control, overlay-control, summon,
hotkey-registration, tray-registration, capture, telemetry, or resident-claim
authority.

Stage 6 remains blocked. The next smallest truthful gap is no longer proving
that a foreground resident-surface runtime can be observed; it is making a real
supervised resident runtime path truthful behind the existing approval,
supervision, service-control, tray, hotkey, overlay, and resident-claim gates.

Latest targeted validation for the `2026-04-30` Stage 6/Lens checkpoint
foreground runtime proof consumption:

- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `failed` before test contract update because the checkpoint/audit
  moved from `resident_surface_runtime_missing` to
  `resident_surface_runtime_not_supervised`; after updating the focused
  assertions and removing the stale blocker leak from system-resident
  aggregation, result: `passed`
- `python -m pytest tests\test_lens_resident_surface_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_resident_surface_proof_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_resident_surface_proof_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed` with expected PowerShell LF-to-CRLF warnings for
  `scripts/lens-stage6-checkpoint.ps1` and
  `scripts/lens-stage6-completion-audit.ps1`

### 2026-04-30 - Stage 6/Lens resident runtime activation blocker normalization

Stage 6/Lens resident runtime activation contracts now use the same foreground
runtime truth as `/lens/resident-surface`. When a bounded foreground Lens host
runtime is observed through the existing host process readback, the resident
runtime preflight, policy, authority-grant denial, activation plan, activation
denial, and resident-surface activation boundary no longer report
`resident_surface_runtime_missing`. They report the sharper blockers
`resident_surface_runtime_not_supervised` and `resident_surface_not_resident`.

This keeps the direct route contracts aligned with the current Stage 6 proof
chain: foreground runtime can be observed, but it is not supervised, not
resident, and not eligible for a resident Lens claim.

This is backend readback normalization only. It does not launch a Lens host,
supervise or restart a process, install/start/stop/control a service, register
tray presence, bind a hotkey, open/control an overlay, summon Francis anywhere,
write memory, decide approvals, create UI controls, write receipts, or grant
execution, approval-decision, memory-write, process-supervision,
process-restart, service-control, overlay-control, summon, hotkey-registration,
tray-registration, capture, telemetry, or resident-claim authority.

Stage 6 remains blocked. The next smallest truthful gap remains making the
supervised resident runtime path real behind the existing approval, supervision,
service-control, tray, hotkey, overlay, and resident-claim gates.

Latest targeted validation for the `2026-04-30` Stage 6/Lens resident runtime
activation blocker normalization:

- `python -m pytest tests\test_api_lens.py::test_lens_api_observes_live_foreground_process_readback -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\activation.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\activation.py tests\test_api_lens.py`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens proof observation window stabilization

Stage 6/Lens bounded host observation proofs now use wider observation and
process-exit grace windows for the future Lens host runtime. The host launch
runner, host-supervisor runner, and composed host-supervisor observation proof
still observe exactly one bounded foreground diagnostic host lifecycle, but the
readback now gives slower local/CI PowerShell process startup and teardown more
time before declaring the running or stopped state missing.

This is diagnostic stability only. It does not change the Lens runtime claim,
launch a resident host, supervise or restart a process, install/start/stop/control
a service, register tray presence, bind a hotkey, open/control an overlay, summon
Francis anywhere, write memory, decide approvals, create UI controls, or grant
execution, approval-decision, memory-write, process-supervision, process-restart,
service-control, overlay-control, summon, hotkey-registration, tray-registration,
capture, telemetry, or resident-claim authority.

Stage 6 remains blocked. The next truthful gap remains converting the bounded
diagnostic observation chain into a real supervised resident runtime only behind
the existing approval, authority, supervision, service-control, tray, hotkey,
overlay, and resident-claim gates.

Latest targeted validation for the `2026-04-30` Stage 6/Lens proof observation
window stabilization:

- `python -m pytest tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens host supervision process-state blockers

Stage 6/Lens direct resident-host supervision readback now normalizes host
process state into explicit blocker language on `/lens/host/supervision` and
the embedded `/lens/status` resident-host surface. When no foreground Lens host
process is present, the supervision gate includes
`resident_host_process_missing`. When a bounded foreground host process is
observed, the same gate reports `foreground_process_observed: true`,
`resident_host_process_state: foreground_observed_not_supervised`, and includes
`resident_host_process_not_supervised` instead of the missing-process blocker.

This is backend readback/API contract truth only. It does not launch a resident
host, supervise or restart a process, install/start/stop/control a service,
register tray presence, bind a hotkey, open/control an overlay, summon Francis
anywhere, write memory, decide approvals, create UI controls, or grant
execution, approval-decision, memory-write, process-supervision,
process-restart, service-control, overlay-control, summon, hotkey-registration,
tray-registration, capture, telemetry, or resident-claim authority.

Stage 6 remains blocked. The direct gate now gives downstream Lens surfaces a
truthful distinction between "no host process" and "foreground host observed but
not supervised"; the next truthful gap remains making a supervised resident
runtime real behind the existing approval, authority, supervision,
service-control, tray, hotkey, overlay, and resident-claim gates.

Latest targeted validation for the `2026-04-30` Stage 6/Lens host supervision
process-state blockers:

- `python -m pytest tests\test_api_lens.py::test_lens_status_projects_readonly_stage6_contract -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py::test_lens_api_observes_live_foreground_process_readback -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py tests\test_api_lens.py`
  Result: `passed` with expected local Ruff cache access warning.
- `python -m ruff format --check src\francis\lens\host_manifest.py tests\test_api_lens.py`
  Result: `passed` with expected local Ruff cache access warning.
- `git diff --check`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1 -Mode Status`
  Result: `passed`; status remains `blocked`, `ready_to_close: false`,
  `next_smallest_truthful_gap: resident_surface_runtime_not_supervised`.

### 2026-04-30 - Stage 6/Lens resident runtime denial receipt readback

Stage 6/Lens resident runtime activation attempts now have a durable denial
receipt/readback boundary. `POST /lens/resident-runtime/execute` still denies
resident runtime activation, but when the existing `system.write` API permission
gate is ready and the denial is specifically
`denied_no_resident_runtime_authority`, Francis writes a
`lens.resident_runtime.activation.denial.receipt` under
`data/lens/resident_runtime_activation_denials/`. The new read-only
`GET /lens/resident-runtime/denials` route lists those receipts with approval
and status filters, and `/lens/status` embeds the same receipt readback plus a
Stage 6 readiness criterion named
`resident_runtime_activation_denial_receipt_readback`.

This is backend route/API receipt persistence and readback truth only. It does
not launch a resident runtime, supervise or restart a process, install/start or
control a service, register tray presence, bind a hotkey, open/control an
overlay, summon Francis anywhere, write memory, decide approvals, create UI
controls, or grant execution, approval-decision, memory-write,
process-supervision, process-restart, service-control, overlay-control, summon,
hotkey-registration, tray-registration, capture, telemetry, or resident-claim
authority. Read-only status and boundary readbacks still do not write denial
receipts; receipt persistence is confined to the explicit POST execution-denial
attempt after the existing API permission gate is ready.

Stage 6 remains active and blocked. The completion audit still reports
`ready_to_close: false`, `transition_allowed: false`, and
`next_smallest_truthful_gap: resident_surface_runtime_not_supervised`.

Latest targeted validation for the `2026-04-30` Stage 6/Lens resident runtime
denial receipt readback:

- `python -m pytest tests\test_api_lens.py::test_lens_status_projects_readonly_stage6_contract -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py::test_lens_host_activation_readback_tracks_decision_without_execution -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m mypy src`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\api\routes\lens.py src\francis\lens\activation.py src\francis\lens\status.py src\francis\lens\__init__.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\api\routes\lens.py src\francis\lens\activation.py src\francis\lens\status.py src\francis\lens\__init__.py tests\test_api_lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1 -Mode Status`
  Result: `passed`; status remains `blocked`, `ready_to_close: false`,
  `next_smallest_truthful_gap: resident_surface_runtime_not_supervised`.

### 2026-04-30 - Stage 6/Lens bounded supervisor-owned host session

Stage 6/Lens now has a bounded supervisor-owned host session in
`scripts/lens-host-supervisor.ps1 -Mode SuperviseOnce`. The supervisor can
launch one temporary `scripts/lens-host.ps1 -Mode Foreground` process, observe
the same process through `foreground_running` and `foreground_stopped` runtime
states, write a supervisor state receipt under the selected runtime data root,
and report `supervised_session_completed` after the host self-stops and leaves
no pid file. This is the first Lens host supervisor mode that owns the temporary
host lifecycle instead of only observing an already-started foreground host.

This is a diagnostic local PowerShell process-launch and runtime-state proof
only. It does not install, start, stop, restart, or manage a Windows service;
does not register tray presence, bind a global hotkey, open/control an overlay,
summon Francis anywhere, write memory, decide approvals, expose an API launch
path, grant resident runtime execution authority, grant process-supervision or
process-restart authority, or claim a resident supervised runtime. The new mode
keeps `ready_for_resident_claim: false`, `resident_host_process: false`,
`resident_supervised_runtime: false`, `supervised: false`, and
`mutation_authority_granted: false`.

Stage 6 remains active and blocked. The new session removes a prerequisite gap
inside the supervisor runner itself, but it has not yet been consumed by the
Stage 6 checkpoint, the resident overlay runtime proof, or the API/operator
readback surfaces. The next smallest truthful gap is to consume this
supervisor-owned session in the checkpoint/readback chain without granting
resident, service, tray, hotkey, overlay, summon, memory-write, approval, or
API process-launch authority.

Latest targeted validation for the `2026-04-30` Stage 6/Lens bounded
supervisor-owned host session:

- `python -m pytest tests\test_lens_host_supervisor_script.py -q`
  Result: `failed before fix`, then `passed`
- `python -m pytest tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py -q`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens checkpoint consumes supervisor-owned host session

Stage 6/Lens checkpoint readback now consumes the bounded supervisor-owned host
session instead of leaving `SuperviseOnce` isolated in the standalone runner.
`scripts/lens-stage6-checkpoint.ps1 -Mode Status` invokes
`scripts/lens-host-supervisor.ps1 -Mode SuperviseOnce`, verifies the supervisor
started one temporary foreground host, observed running and stopped states, and
adds a `host_supervisor_owned_session` readback block. That block keeps
`ready_for_resident_claim`, `resident_host_process`,
`resident_supervised_runtime`, and `supervised` false while carrying the
remaining resident, process-supervision, restart, service-control, tray, hotkey,
overlay, and summon blockers.

This is checkpoint/readback consumption of an existing diagnostic proof only. It
does not grant API process-launch authority, activation process-launch
authority, process-supervision authority, process-restart authority,
service-control authority, tray or hotkey authority, overlay control, memory
writes, approval decisions, resident runtime authority, or a resident claim. The
checkpoint governance payload now records `bounded_supervisor_owned_session:
true` and keeps product execution and mutation authority false.

Stage 6 remains active and blocked. The completion audit still reports
`ready_to_close: false`, `transition_allowed: false`, and
`next_smallest_truthful_gap: resident_surface_runtime_not_supervised`. The next
smallest truthful gap is to move from diagnostic bounded supervision proof to
the resident-runtime authority boundary that still blocks real resident process
supervision, service/tray/hotkey/overlay behavior, and summon-anywhere.

Latest targeted validation for the `2026-04-30` Stage 6/Lens checkpoint
consumption of supervisor-owned host session:

- `python -m pytest tests\test_lens_stage6_checkpoint_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervisor_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_host_supervisor_script.py tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_host_supervisor_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_host_supervisor_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens completion audit consumes process supervision boundary proof

Stage 6/Lens completion audit now consumes the existing
process-supervision/service-activation authority boundary proof instead of
stopping at the checkpoint-only view. `scripts/lens-stage6-completion-audit.ps1
-Mode Status` invokes
`scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status`,
embeds a `process_supervision_authority_boundary_proof` readback block, and
groups the proof's process-supervision and service-activation blockers under
dedicated `closure_blockers.process_supervision` and
`closure_blockers.service_activation` sections.

The audit now carries the proof that the Stage 6 checkpoint, host-supervision
boundary, process-supervision denial, and service-activation plan are observed.
It keeps `supervision_ready`, `ready_for_resident_claim`,
`resident_claim_allowed`, `resident_host_supervised`, `service_installed`,
`service_managed`, `process_supervision_ready`, and `service_activation_ready`
false. It also keeps `would_supervise_process`, `would_restart_process`,
`would_install_service`, `would_start_service`, `would_write_memory`, and
`would_decide_approval` false.

This is stage-audit/readback wiring only. It does not grant execution
authority, approval authority, memory-write behavior, process-supervision
authority, process-restart authority, service-install authority, service-control
authority, tray/hotkey authority, overlay control, summon authority, telemetry
authority, or a resident claim. Stage 6 remains active and blocked:
`ready_to_close: false`, `transition_allowed: false`, and
`closure_decision: do_not_close_stage6`.

The audit's `next_smallest_truthful_gap` is now
`resident_host_process_not_supervised`, moving the active blocker from generic
resident-surface runtime readback to the specific unsupervised resident host
process. The remaining Stage 6 closure blockers still include summon-anywhere,
helpful-not-noisy, and system-resident presence.

Latest targeted validation for the `2026-04-30` Stage 6/Lens completion audit
consumption of process supervision boundary proof:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1 -Mode Status`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `failed before test contract update`, then `passed`
- `python -m pytest tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_completion_audit_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_stage6_completion_audit_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_stage6_completion_audit_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens host supervision proof names unsupervised resident host blocker

Stage 6/Lens host supervision readiness proof now uses the same foreground
runtime blocker vocabulary as the completion audit and direct Lens readbacks.
`scripts/lens-host-supervision-proof.ps1 -Mode Status` still composes host
lifecycle preflight, bounded foreground readiness proof, bounded host-launch
proof, service plan readback, service status readback, process-supervision
readiness, and service-control denial. It now reports
`foreground_process_observed: true`, `resident_host_process_state:
foreground_observed_not_supervised`, and `resident_host_process_blocker:
resident_host_process_not_supervised` when the bounded foreground host launch
proof is observed.

The proof's `next_smallest_truthful_gap` is now
`resident_host_process_not_supervised`, and its blockers use
`resident_surface_runtime_not_supervised` instead of the older generic
`resident_surface_runtime_missing` once bounded foreground process readback has
been observed. This keeps the standalone proof aligned with the Stage 6
completion audit's latest next gap.

This is diagnostic/readback alignment only. It does not grant execution
authority, approval authority, memory-write behavior, process-supervision
authority, process-restart authority, service-install authority, service-control
authority, tray/hotkey authority, overlay control, summon authority, API local
process-launch authority, or a resident claim. The proof still keeps
`supervision_ready`, `ready_for_resident_claim`, `resident_claim_allowed`,
`resident_host_process`, `service_installed`, `supervised`, and
`service_managed` false.

Stage 6 remains active and blocked. The next smallest truthful gap remains the
actual supervised resident host process path behind explicit authority gates,
not another readback rename.

Latest targeted validation for the `2026-04-30` Stage 6/Lens host supervision
proof blocker alignment:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-host-supervision-proof.ps1 -Mode Status -ForegroundRunSeconds 2 -HostLaunchRunSeconds 3`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervision_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervision_proof_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_host_supervision_proof_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_stage6_completion_audit_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_host_supervision_proof_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_stage6_completion_audit_script.py`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens host supervision authority request readback

Stage 6/Lens now has a governed approval-request seam for future resident host
supervision authority. `POST /lens/host/supervision/authority/request` creates a
pending approval request for action `lens.host.supervision_authority` only when
the caller has the existing `system.write` API scope. `GET
/lens/host/supervision/authority/requests` reads those approval requests back by
status. `/lens/status` now exposes the request and request-readback routes under
the resident host surface, and the Lens command-palette readback now advertises a
backend-truthful command for requesting host supervision review.

This slice does not grant process supervision, process restart, service install,
service control, local process launch, overlay, tray, hotkey, resident-claim,
approval-decision, memory-write, or execution authority. It does not start,
supervise, restart, install, or stop a Lens host process. It only makes the
operator approval-request step explicit and readable before any future host
supervision authority grant can be implemented.

Stage 6 remains active and blocked. The next smallest truthful gap moves to the
actual host supervision authority grant implementation and supervised resident
host process path, with approval binding and receipts, not more request/readback
scaffolding.

Latest targeted validation for the `2026-04-30` Stage 6/Lens host supervision
authority request readback:

- `python -m pytest tests\test_api_lens.py::test_lens_host_supervision_authority_request_requires_system_write_without_grant tests\test_api_lens.py::test_lens_host_supervision_authority_request_creates_approval_only_receipt -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff check tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py`
  Result: `passed`
- `python -m ruff format --check tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens host supervision authority grant approval binding

Stage 6/Lens now requires an exact approved host supervision authority request
before the `POST /lens/host/supervision/authority` grant boundary can advance
from `blocked` into its existing denial receipt path. The grant boundary now
accepts `approval_id`, verifies the request action `lens.host.supervision_authority`,
distinguishes missing, wrong, pending, and approved approval states, and records
the selected approval id/status in denial receipts only after the exact request
is approved. The denial receipt readback route and readiness audit now accept
`approval_id` filters, and the readiness audit includes an explicit
`exact_supervision_authority_approval` requirement.

This slice still does not grant process supervision, process restart, service
install, service control, local process launch, resident claim, approval-decision,
memory-write, overlay, tray, hotkey, summon, or execution authority. It does not
start, supervise, restart, install, or stop a Lens host process. It only tightens
the approval-bound grant preflight and receipt readback needed before a truthful
resident host supervision implementation can exist.

Stage 6 remains active and blocked. The next smallest truthful gap remains the
actual supervised resident host process path behind explicit process supervision,
restart, service-control, resident-claim, and receipt authority.

Latest targeted validation for the `2026-04-30` Stage 6/Lens host supervision
authority grant approval binding:

- `python -m pytest tests\test_api_lens.py::test_lens_host_supervision_authority_grant_requires_approved_request_before_denial_receipt -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py::test_lens_host_supervision_authority_request_creates_approval_only_receipt tests\test_api_lens.py::test_lens_host_supervision_authority_grant_requires_approved_request_before_denial_receipt -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens checkpoint proof timing stabilization

Stage 6/Lens checkpoint diagnostics now tolerate the timing sensitivity exposed
by the `42a1d4a` CI run without weakening the proof contract. The checkpoint
now gives live API startup a 30-second default window, retries the composed
resident overlay runtime and activation-boundary proof scripts once when the
first diagnostic run does not return `proof_passed`, and still requires a real
`proof_passed` payload before reporting those checkpoint proof blocks as passed.
The resident overlay activation-boundary proof also creates an isolated temp
data root when callers do not provide `-DataDir`, keeping its live API,
overlay-runtime, and activation-boundary reads on one proof-local state root.
The process-supervision authority boundary and completion audit now use the same
30-second startup window when they consume the Stage 6 checkpoint.

This is diagnostic stability only. It does not grant execution, approval
decision, memory-write, process-supervision, process-restart, service-install,
service-control, overlay-control, tray-registration, hotkey-registration,
summon, capture, telemetry, receipt-write, denial-receipt-write, resident-claim,
or UI authority. It does not start a resident host, supervise or restart a real
resident process, install or control a service, bind a global hotkey, create tray
presence, open an overlay, write memory, decide approvals, or claim Stage 6
closure.

Stage 6 remains active and blocked. This removes a CI/local timing flake from
the Stage 6 checkpoint and completion-audit proof chain so the next truthful
gap remains implementing a real supervised resident host process only behind the
existing approval, authority, service-control, tray, hotkey, overlay, and
resident-claim gates.

Latest targeted validation for the `2026-04-30` Stage 6/Lens checkpoint proof
timing stabilization:

- `python -m pytest tests\test_lens_stage6_checkpoint_script.py::test_lens_stage6_checkpoint_reports_blocked_done_criteria_without_authority -q`
  Result: `passed`
- `python -m pytest tests\test_lens_resident_overlay_activation_boundary_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervisor_observation_proof_script.py tests\test_lens_resident_overlay_runtime_proof_script.py tests\test_lens_resident_overlay_activation_boundary_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `failed before retry stabilization on resident overlay runtime proof timing, then passed after the checkpoint retry fix`

### 2026-04-30 - Stage 6/Lens completion-audit blocker ordering

Stage 6/Lens completion audit now consumes the checkpoint's bounded
supervisor-owned host session before selecting the next smallest truthful gap.
When that bounded `SuperviseOnce` proof is observed, the audit now reports
`resident_supervision_not_persistent` instead of asking for another bounded
`resident_host_process_not_supervised` proof. This makes the closure audit point
at the next real resident-host blocker: persistent supervised resident runtime,
not another diagnostic foreground/supervisor loop.

This is diagnostic/audit readback only. It does not grant execution, approval
decision, memory-write, local-process-launch, process-supervision,
process-restart, service-install, service-control, tray-registration,
hotkey-registration, overlay-control, summon, capture, receipt-write,
denial-receipt-write, resident-claim, telemetry, or UI authority. It does not
start, supervise, restart, install, or stop a resident Lens host process.

Stage 6 remains active and blocked. The next smallest truthful gap is now the
persistent resident supervision path behind explicit process supervision,
restart, service-control, resident-claim, and receipt authority.

Latest targeted validation for the `2026-04-30` Stage 6/Lens completion-audit
blocker-ordering slice:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-checkpoint.ps1 -Mode Status | ConvertFrom-Json | Select-Object -ExpandProperty host_supervisor_owned_session | ConvertTo-Json -Depth 8`
  Result: `passed; reported supervised_session_completed with bounded_supervised_session=true`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1 | ConvertFrom-Json | Select-Object next_smallest_truthful_gap,next_smallest_truthful_gap_basis | ConvertTo-Json -Depth 4`
  Result: `passed; reported resident_supervision_not_persistent`
- `python -m pytest tests\test_lens_stage6_completion_audit_script.py::test_lens_stage6_completion_audit_blocks_transition_without_authority -q`
  Result: `failed once during concurrent proof-state contention, then passed when rerun serially`
- `python -m ruff check tests\test_lens_stage6_completion_audit_script.py`
  Result: `passed`
- `python -m ruff format --check tests\test_lens_stage6_completion_audit_script.py`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens host supervisor stopped-state stabilization

Stage 6/Lens bounded host supervisor diagnostics now wait for the supervisor-owned
foreground host process to complete before finalizing stopped-state proof, then
poll for the matching stopped runtime state and PID cleanup through a shared
cleanup-aware stopped-state observer. The same observer is used by the
read-only `Observe` path. This stabilizes the Windows proof window exposed by
CI run `964`, where the bounded `SuperviseOnce` proof could miss the final
stopped/cleanup state under full-suite timing even though the focused local test
passed.

This is diagnostic/proof-stability work only. It does not grant execution,
approval decision, memory-write, resident process supervision, process restart,
service install, service control, tray registration, hotkey registration,
overlay control, summon, capture, receipt-write, telemetry, UI, or resident
claim authority. It still launches only one bounded diagnostic foreground host
inside `SuperviseOnce` and does not create a persistent resident host.

Stage 6 remains active and blocked. The next smallest truthful gap remains
persistent resident supervision behind explicit authority; this slice only makes
the existing bounded proof less timing-sensitive so audit/readback can be
trusted.

Latest targeted validation for the `2026-04-30` Stage 6/Lens host supervisor
stopped-state stabilization:

- `python -m pytest tests\test_lens_host_supervisor_script.py::test_lens_host_supervisor_supervises_one_bounded_host_without_resident_claim -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervisor_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_host_supervisor_observation_proof_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_resident_overlay_runtime_proof_script.py -q`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1`
  Result: `passed; reported next_smallest_truthful_gap=resident_supervision_not_persistent`
- `python -m pytest tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `failed once during concurrent proof-state contention with a simultaneously running raw audit, then passed when rerun serially`

### 2026-04-30 - Stage 6/Lens persistent supervision prerequisite readback

Stage 6/Lens resident supervision readback now names the remaining persistent
supervision prerequisites directly instead of leaving them implicit behind the
broader supervision blocker. The disabled Lens host service config declares
`persistent_supervision_enabled: false`, `process_restart_authority: false`,
`receipt_write_authority: false`, and `resident_claim_authority: false`.
`/lens/host`, `/lens/host/supervision`, `/lens/host/supervision/authority`,
and `/lens/status` now surface those values as blocked readiness requirements
and false governance authorities.

This is readback-only prerequisite disclosure. It does not grant execution,
approval decision, memory-write, local-process-launch, process-supervision,
process-restart, service-install, service-control, receipt-write, telemetry,
tray, hotkey, overlay, summon, or resident-claim authority. It does not start,
supervise, restart, install, or stop a Lens host process.

Stage 6 remains active and blocked. The next smallest truthful gap remains the
actual persistent resident supervision path behind explicit process-supervision,
restart, service-control, receipt-write, and resident-claim authority.

Latest targeted validation for the `2026-04-30` Stage 6/Lens persistent
supervision prerequisite readback:

- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check --no-cache src\francis\lens\host_manifest.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m json.tool config\runtime\services\lens-host.json`
  Result: `passed`
- `git diff --check`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens service manager authority enforcement

Stage 6/Lens service management now fails closed when a service config denies
install or control authority. `scripts/service-install.ps1` already projected a
blocked Lens host service plan in `Plan` mode; it now also checks config-declared
authority before mutating service modes. `Install` and `Update` are blocked when
`installable`, `install_authority`, `service_install_authority`, or
`service_control_authority` are false. `Start`, `Stop`, and `Restart` are blocked
when `service_control_authority` is false. `Uninstall` is blocked through a
config-driven path when service install/control authority is false. Blocked
attempts write a `BLOCKED` action into the service manager report and exit
nonzero before admin checks, wrapper creation, service install/update, or service
control.

This is fail-closed authority enforcement for the future resident Lens host
service path. It does not grant execution, approval decision, memory-write,
local-process-launch, process-supervision, process-restart, service-install,
service-control, receipt-write, telemetry, tray, hotkey, overlay, summon, or
resident-claim authority. It does not install, update, start, stop, restart, or
remove a Lens host service.

Stage 6 remains active and blocked. The next smallest truthful gap remains the
actual persistent resident supervision path behind explicit process-supervision,
restart, service-control, receipt-write, and resident-claim authority.

Latest targeted validation for the `2026-04-30` Stage 6/Lens service manager
authority enforcement:

- `python -m pytest tests\test_service_install_plan_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_host_preflight_script.py tests\test_lens_host_supervision_proof_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_service_install_plan_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_service_install_plan_script.py`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens persistent supervision plan proof

Stage 6/Lens now has a non-mutating persistent-supervision plan proof for the
remaining resident host blocker. `scripts/lens-persistent-supervision-plan.ps1`
emits `kind: lens.host.persistent_supervision_plan`, reads the disabled Lens host
service config, and reports the exact requirements that must become true before
Francis can claim persistent resident supervision. In the current repo posture,
the host entrypoint, service manager, and service config are present, while
process supervision enablement, persistent supervision enablement, process
restart authority, service install/control authority, receipt-write authority,
and resident-claim authority remain blocked.

The Stage 6 completion audit now consumes that proof and reports
`next_smallest_truthful_gap: persistent_supervision_authority_not_granted`
instead of the broader `resident_supervision_not_persistent`. This moves the
audit from another bounded foreground/supervisor proof toward the explicit
authority boundary required for a real persistent resident supervisor.

This is diagnostic/readback and plan-proof work only. It does not grant
execution, approval decision, memory-write, local-process-launch,
process-supervision, process-restart, service-install, service-control,
receipt-write, denial-receipt-write, resident-claim, telemetry, tray, hotkey,
overlay, summon, capture, or UI authority. It does not install, update, start,
stop, restart, supervise, or claim a resident Lens host process.

Stage 6 remains active and blocked. The next smallest truthful gap is the
explicit persistent-supervision authority boundary behind process-supervision,
restart, service-control, receipt-write, and resident-claim requirements.

Latest targeted validation for the `2026-04-30` Stage 6/Lens persistent
supervision plan proof:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-persistent-supervision-plan.ps1 -Mode Status | ConvertFrom-Json | Select-Object kind,status,next_smallest_truthful_gap,requirements_blocked_total | ConvertTo-Json -Depth 4`
  Result: `passed; reported persistent_supervision_authority_not_granted`
- `python -m pytest tests\test_lens_persistent_supervision_plan_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_persistent_supervision_plan_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py -q`
  Result: `passed`
- `python -m ruff check --no-cache tests\test_lens_persistent_supervision_plan_script.py tests\test_lens_stage6_completion_audit_script.py`
  Result: `passed`
- `python -m ruff format --check --no-cache tests\test_lens_persistent_supervision_plan_script.py tests\test_lens_stage6_completion_audit_script.py`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1 | ConvertFrom-Json | Select-Object next_smallest_truthful_gap,next_smallest_truthful_gap_basis,persistent_supervision_plan | ConvertTo-Json -Depth 6`
  Result: `passed; reported persistent_supervision_authority_not_granted`
- `git diff --check`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens persistent supervision API readback

Stage 6/Lens now exposes the persistent-supervision plan through a direct
read-only backend route at `GET /lens/host/persistent-supervision`. The route
projects the same current truth as the plan proof: the Lens host service config,
host entrypoint, and service manager are present, while process supervision
enablement, persistent supervision enablement, process-restart authority,
service install/control authority, receipt-write authority, and resident-claim
authority remain blocked.

`/lens/status` now embeds the same plan as
`resident_host.persistent_supervision_plan` with a stable
`persistent_supervision_plan_route`, so downstream operator surfaces can read
the blocker without shelling out to the proof script. The plan reports all
future `would_*` actions as `false` in the current repo posture and keeps
`next_smallest_truthful_gap: persistent_supervision_authority_not_granted`.

This is backend readback/API work only. It does not grant execution, approval
decision, memory-write, local-process-launch, process-supervision,
process-restart, service-install, service-control, receipt-write,
denial-receipt-write, resident-claim, telemetry, tray, hotkey, overlay, summon,
capture, or UI authority. It does not install, update, start, stop, restart,
supervise, write receipts, write memory, or claim a resident Lens host process.

Stage 6 remains active and blocked. The next smallest truthful gap remains the
explicit persistent-supervision authority boundary behind process-supervision,
restart, service-control, receipt-write, and resident-claim requirements.

Latest targeted validation for the `2026-04-30` Stage 6/Lens persistent
supervision API readback:

- `python -m pytest tests\test_api_lens.py::test_lens_persistent_supervision_plan_readback_blocks_without_authority -q`
  Result: `failed before fix; passed after importing the plan helper from the correct Lens module`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_persistent_supervision_plan_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_persistent_supervision_plan_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\host_manifest.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens completion-audit blocker priority stabilization

Stage 6/Lens completion audit blocker selection now prefers
`persistent_supervision_authority_not_granted` whenever the
persistent-supervision plan proof is present and blocked. The previous
selection still depended on observing a bounded supervisor-owned session in the
same audit pass, which allowed Windows CI timing to report the older
`resident_host_process_not_supervised` blocker even though the persistent
supervision plan proof was already available.

This is diagnostic/readback ordering only. It does not grant execution,
approval decision, memory-write, local-process-launch, process-supervision,
process-restart, service-install, service-control, receipt-write,
denial-receipt-write, resident-claim, telemetry, tray, hotkey, overlay, summon,
capture, or UI authority. It does not install, update, start, stop, restart,
supervise, write receipts, write memory, or claim a resident Lens host process.

Stage 6 remains active and blocked. The next smallest truthful gap remains the
explicit persistent-supervision authority boundary behind process-supervision,
restart, service-control, receipt-write, and resident-claim requirements.

Latest targeted validation for the `2026-04-30` Stage 6/Lens completion-audit
blocker priority stabilization:

- `python -m pytest tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lens-stage6-completion-audit.ps1 -Mode Status | ConvertFrom-Json | Select-Object kind,status,next_smallest_truthful_gap,next_smallest_truthful_gap_basis | ConvertTo-Json -Depth 4`
  Result: `passed; reported persistent_supervision_authority_not_granted`

### 2026-04-30 - Stage 6/Lens host supervision authority grant lease

Stage 6/Lens now has an approval-gated, receipt-backed host supervision
authority lease for the future persistent Lens host. `POST
/lens/host/supervision/authority` no longer treats the grant boundary as
not implemented when an exact approved `lens.host.supervision_authority`
approval and `system.write` actor scope are present. It writes a bounded local
grant receipt under `/lens/host/supervision/authority/grants`, and the direct
readiness audit, `/lens/status`, Stage 6 checkpoint, process-supervision
boundary proof, and completion audit now read that grant-receipt surface.

The lease only records bounded authority for later process-supervision,
process-restart, service-install, service-control, receipt-write, and
resident-claim review. It does not start, install, stop, supervise, restart, or
claim a Lens host; it does not write memory; it does not decide approvals; it
does not grant local process launch, tray, hotkey, overlay, summon, capture,
telemetry, or UI authority. In the normal empty runtime state, Stage 6 remains
blocked on `persistent_supervision_authority_not_granted` until an operator
approval produces an active grant receipt. In the approved-grant contract test,
the persistent-supervision plan advances to
`persistent_supervision_enablement_disabled`, because enablement and execution
remain separate follow-up boundaries.

Stage 6 remains active and blocked. The next smallest truthful gap is turning an
active, receipt-backed host supervision authority lease into an explicit
persistent-supervision enablement/execution boundary without broadening
resident authority or claiming a resident Lens host early.

Latest targeted validation for the `2026-04-30` Stage 6/Lens host supervision
authority grant lease:

- `python -m pytest tests\test_api_lens.py::test_lens_host_supervision_authority_grant_requires_approved_request_before_grant_receipt -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_persistent_supervision_plan_script.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `failed before checkpoint proof update on stale not-implemented blocker expectation; passed after checkpoint consumed grant-receipt readback`
- `python -m ruff check src\francis\lens\activation.py src\francis\api\routes\lens.py src\francis\lens\__init__.py src\francis\lens\status.py src\francis\lens\host_manifest.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\api\routes\lens.py src\francis\lens\__init__.py src\francis\lens\status.py src\francis\lens\host_manifest.py tests\test_api_lens.py tests\test_lens_stage6_checkpoint_script.py tests\test_lens_process_supervision_authority_boundary_proof_script.py`
  Result: `passed after formatting`

### 2026-04-30 - Stage 6/Lens persistent supervision proof consumes authority grants

Stage 6/Lens persistent-supervision proof script now reads the same active host
supervision authority grant receipt surface that the backend readback uses.
`scripts/lens-persistent-supervision-plan.ps1 -Mode Status` checks
`FRANCIS_DATA_DIR` when provided, otherwise the repo `data` directory, and only
accepts unexpired `lens.host.supervision_authority.grant.receipt` records with an
active lease and an authority-granted boundary.

This is readback-only proof alignment. An active grant receipt can now make the
script's authority requirements ready and move the proof's next gap from
`persistent_supervision_authority_not_granted` to
`persistent_supervision_enablement_disabled`, while the plan still refuses to
install, start, supervise, restart, write memory, write receipts, or claim a
resident host. Without an active grant receipt, the script preserves the prior
blocked posture.

Stage 6 remains active and blocked. The next smallest truthful gap remains an
explicit persistent-supervision enablement/execution boundary that consumes an
active grant receipt without granting resident execution, service mutation,
tray/hotkey/overlay control, memory writes, or resident-claim authority beyond
the existing bounded lease contract.

Latest targeted validation for the `2026-04-30` Stage 6/Lens persistent
supervision proof grant-readback alignment:

- `python -m pytest tests\test_lens_persistent_supervision_plan_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_persistent_supervision_plan_script.py tests\test_api_lens.py::test_lens_persistent_supervision_plan_readback_blocks_without_authority tests\test_api_lens.py::test_lens_host_supervision_authority_grant_requires_approved_request_before_grant_receipt tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py tests\test_lens_persistent_supervision_plan_script.py -q`
  Result: `passed`
- `python -m ruff check tests\test_lens_persistent_supervision_plan_script.py`
  Result: `passed`
- `python -m ruff format --check tests\test_lens_persistent_supervision_plan_script.py`
  Result: `passed`
- `git diff --check`
  Result: `passed; Git warned the PowerShell script will be normalized to CRLF when Git touches it`

### 2026-04-30 - Stage 6/Lens persistent supervision enablement preflight

Stage 6/Lens now exposes a read-only persistent-supervision enablement preflight
at `GET /lens/host/persistent-supervision/enablement`. The route composes the
existing persistent-supervision plan, the resident-host supervision readiness
readback, and active host supervision authority grant receipts into an explicit
enablement boundary.

Without an active authority grant, the route remains blocked on
`persistent_supervision_authority_not_granted`. With an active grant receipt, it
proves the next blocker is now `persistent_supervision_enablement_disabled`:
process supervision and persistent supervision are still disabled in the service
configuration. The route is also surfaced through `/lens/status` resident-host
readback for operator/API clients.

This is backend readback-only and preflight-only. It does not update service
configuration, install or start a service, supervise or restart a process, write
receipts, write memory, decide approvals, grant UI authority, or claim a
resident Lens host.

Stage 6 remains active and blocked. The next smallest truthful gap is a
governed non-mutating enablement attempt/denial boundary, or checkpoint/audit
consumption of this preflight if the closure proof needs to name it directly
before any execution boundary is added.

Latest targeted validation for the `2026-04-30` Stage 6/Lens persistent
supervision enablement preflight:

- `python -m pytest tests\test_api_lens.py::test_lens_persistent_supervision_plan_readback_blocks_without_authority tests\test_api_lens.py::test_lens_host_supervision_authority_grant_requires_approved_request_before_grant_receipt -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\host_manifest.py src\francis\lens\__init__.py src\francis\api\routes\lens.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\host_manifest.py src\francis\lens\__init__.py src\francis\api\routes\lens.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `failed before formatting; passed after formatting`
- `git diff --check`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens persistent supervision enablement denial boundary

Stage 6/Lens now has a governed, non-mutating persistent-supervision
enablement denial boundary at `POST /lens/host/persistent-supervision/enablement`.
The route consumes the existing enablement preflight and returns a typed
`lens.host.persistent_supervision_enablement.denial` response that keeps the
attempt blocked when no active host-supervision authority grant exists and
keeps it denied after an active grant because service-config write authority and
persistent-supervision execution authority are still not granted.

The boundary is surfaced through `/lens/status` resident-host readback and the
Stage 6 readiness criteria as `persistent_supervision_enablement_denial_boundary`.
It proves that the enablement path can be attempted and inspected without
updating service configuration, enabling process or persistent supervision,
installing or starting a service, supervising or restarting a process, writing
receipts, writing memory, deciding approvals, granting UI authority, or claiming
a resident Lens host.

Stage 6 remains active and blocked. The next smallest truthful gap is checkpoint
or audit consumption of this denial boundary if the completion proof still names
the older persistent-supervision blocker, then the next governed boundary toward
persistent resident supervision can be chosen from repo truth.

Latest targeted validation for the `2026-04-30` Stage 6/Lens persistent
supervision enablement denial boundary:

- `python -m pytest tests\test_api_lens.py::test_lens_persistent_supervision_plan_readback_blocks_without_authority tests\test_api_lens.py::test_lens_host_supervision_authority_grant_requires_approved_request_before_grant_receipt -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\__init__.py src\francis\api\routes\lens.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\__init__.py src\francis\api\routes\lens.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `failed before formatting; passed after formatting`
- `git diff --check`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens audit consumes persistent supervision enablement denial

Stage 6/Lens checkpoint and completion-audit proof now consume the
`persistent_supervision_enablement_denial_boundary` readiness criterion exposed
by `/lens/status`. `scripts/lens-stage6-checkpoint.ps1 -Mode Status` now
includes the denial boundary in its readback payload and requires it before
handing off to `stage6_lens_completion_audit`. The completion audit now
projects the same boundary into closure blockers, evidence, governance readback,
and `persistent_supervision_enablement_denial_boundary` details.

This is proof/readback-only. It does not update service configuration, enable
process or persistent supervision, install or start a service, supervise or
restart a process, write receipts, write memory, decide approvals, grant UI
authority, or claim a resident Lens host. Stage 6 remains active and blocked.
The audit now names the current next smallest truthful gap as
`persistent_supervision_enablement_authority_not_granted` instead of the older
plan-only `persistent_supervision_authority_not_granted` blocker.

Latest targeted validation for the `2026-04-30` Stage 6/Lens audit consumption
of persistent-supervision enablement denial:

- `python -m pytest tests\test_lens_stage6_checkpoint_script.py::test_lens_stage6_checkpoint_reports_blocked_done_criteria_without_authority tests\test_lens_stage6_completion_audit_script.py::test_lens_stage6_completion_audit_blocks_transition_without_authority -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py`
  Result: `passed`
- `python -m ruff format --check tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py`
  Result: `failed before formatting; passed after formatting`
- `git diff --check`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens persistent supervision enablement authority request readback

Stage 6/Lens now has a governed approval-request seam for future persistent
supervision enablement authority. `POST
/lens/host/persistent-supervision/enablement/authority/request` creates a
pending approval request under the existing `system.write` API permission gate,
and `GET /lens/host/persistent-supervision/enablement/authority/requests`
projects pending/approved/rejected/emergency request readback filtered to the
new `lens.host.persistent_supervision_enablement_authority` action. `GET
/lens/host/persistent-supervision/enablement/authority/readiness` composes the
approval state, existing persistent-supervision enablement preflight, existing
enablement denial boundary, and request readback into exact blockers for the
future grant boundary.

This is a request/readback/readiness slice only. It does not grant service
configuration write authority, persistent-supervision execution authority,
process supervision, service control, receipt-write authority, memory writes,
approval-decision authority, or resident-claim authority. `/lens/status` now
surfaces the request contract, request readback, readiness audit, and a
read-only command-palette entry for creating the approval request without
claiming persistent supervision enablement.

Stage 6 remains active and blocked. The next smallest truthful gap is an exact
approved-request-bound persistent-supervision enablement authority grant
boundary that still does not enable persistent supervision or mutate service
configuration until a separate execution boundary is proven.

Latest targeted validation for the `2026-04-30` Stage 6/Lens persistent
supervision enablement authority request readback:

- `python -m pytest tests\test_api_lens.py::test_lens_persistent_supervision_enablement_authority_request_requires_system_write_without_grant tests\test_api_lens.py::test_lens_persistent_supervision_enablement_authority_request_creates_approval_only_readback -q`
  Result: `failed before fix; passed after readiness used approved approval-record status`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\__init__.py src\francis\api\routes\lens.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\__init__.py src\francis\api\routes\lens.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `failed before formatting; passed after formatting`
- `git diff --check`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens persistent supervision enablement authority grant boundary

Stage 6/Lens now has an exact approved-request-bound grant boundary for future
persistent supervision enablement authority. `POST
/lens/host/persistent-supervision/enablement/authority` requires the exact
approved `lens.host.persistent_supervision_enablement_authority` approval
request, `system.write`, and an active host-supervision authority grant before
writing a bounded grant receipt. `GET
/lens/host/persistent-supervision/enablement/authority/grants` exposes filtered
grant receipt readback, and the persistent supervision enablement readiness
audit plus `/lens/status` now consume that grant/readback truth.

This grants only a receipt-backed persistent-supervision enablement authority
lease for a future service-configuration review boundary. It does not grant
service-configuration write authority, persistent-supervision execution
authority, approval-decision authority, process supervision, service control,
service installation, resident-claim authority, memory writes, UI authority, or
actual persistent supervision. The persistent supervision enablement denial
boundary now removes `persistent_supervision_enablement_authority_not_granted`
only when that active grant receipt exists; it still denies service config
mutation with `service_config_write_authority_not_granted` and
`persistent_supervision_execution_authority_not_granted`.

Stage 6 remains active and blocked. The next smallest truthful gap is the
service-configuration write / persistent-supervision execution boundary for
enablement, still without mutating service config or enabling persistent
supervision until that separate boundary is proven and validated.

Latest targeted validation for the `2026-04-30` Stage 6/Lens persistent
supervision enablement authority grant boundary:

- `python -m pytest tests\test_api_lens.py::test_lens_persistent_supervision_enablement_authority_grant_requires_approved_request_and_host_grant -q`
  Result: `failed before fix due Windows receipt path length; passed after shortening the internal receipt directory`
- `python -m pytest tests\test_api_lens.py::test_lens_persistent_supervision_enablement_authority_request_creates_approval_only_readback tests\test_api_lens.py::test_lens_host_supervision_authority_grant_requires_approved_request_before_grant_receipt -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\__init__.py src\francis\api\routes\lens.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\__init__.py src\francis\api\routes\lens.py src\francis\lens\status.py tests\test_api_lens.py`
  Result: `failed before formatting; passed after formatting`
- `git diff --check`
  Result: `passed`

### 2026-04-30 - Stage 6/Lens persistent supervision execution authority request readback

Stage 6/Lens now has a governed approval-request seam for future persistent
supervision service-configuration write and execution authority. `POST
/lens/host/persistent-supervision/enablement/execution/request` requires
`system.write` and an active persistent-supervision enablement-authority grant
before it creates a pending
`lens.host.persistent_supervision_enablement_execution_authority` approval
request. `GET
/lens/host/persistent-supervision/enablement/execution/requests` exposes
filtered request readback, and `GET
/lens/host/persistent-supervision/enablement/execution/readiness` composes the
exact approval state, active enablement-authority grant, existing enablement
denial boundary, and request readback into the remaining service-config-write,
persistent-supervision execution, receipt-write, and resident-claim blockers.
`/lens/status` now embeds the request contract, request readback, readiness
audit, Stage 6 criterion, receipt routes, and command-palette readback for this
request.

This is a request/readback/readiness slice only. It does not grant service
configuration write authority, persistent-supervision execution authority,
receipt-write authority, process supervision, service control, service
installation, approval-decision authority, memory writes, UI authority,
resident-claim authority, or actual persistent supervision. Approval of the new
request only changes the approval readback from pending to approved; it still
does not mutate service config or enable supervision.

Stage 6 remains active and blocked. The next smallest truthful gap is the
explicit service-configuration write / persistent-supervision execution grant or
denial boundary, still without enabling persistent supervision until that
separate boundary is proven and validated.

Latest targeted validation for the `2026-04-30` Stage 6/Lens persistent
supervision execution authority request readback:

- `python -m pytest tests\test_api_lens.py::test_lens_persistent_supervision_enablement_execution_request_requires_enablement_authority_grant -q`
  Result: `passed`
- `python -m pytest tests\test_api_lens.py -q`
  Result: `passed`
- `python -m pytest tests\test_lens_stage6_checkpoint_script.py tests\test_lens_stage6_completion_audit_script.py -q`
  Result: `passed`
- `python -m ruff check src\francis\lens\activation.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `passed`
- `python -m ruff format --check src\francis\lens\activation.py src\francis\lens\status.py src\francis\lens\__init__.py src\francis\api\routes\lens.py tests\test_api_lens.py`
  Result: `failed before formatting; passed after formatting`
- `git diff --check`
  Result: `passed`
