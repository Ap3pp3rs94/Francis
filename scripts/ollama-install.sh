#!/usr/bin/env bash
# C:\Francis\scripts\ollama-install.sh
#
# Installs / updates Ollama on Linux (including WSL2 Linux) using the official installer.
# Logs under: <FrancisRoot>/data/logs/operations/
#
# Safer than curl|sh: downloads installer to a temp file, sanity-checks, then runs it.
#
# Usage:
#   chmod +x ./ollama-install.sh
#   ./ollama-install.sh
#
# Options:
#   --version 0.3.14        Pin version (passes OLLAMA_VERSION to installer)
#   --model llama3.1        Pull model after install
#   --inspect / --dry-run   Download installer, show preview, do not run
#   --url <url>             Override installer URL
#   --no-service            Do not attempt systemctl enable/start
#   --force                 Reinstall even if ollama exists
#   --root <path>           Override Francis root (e.g., /mnt/c/Francis)
#
# Health check hits: http://127.0.0.1:11434/api/tags

set -euo pipefail
IFS=$'\n\t'

ts() { date +"%Y%m%d_%H%M%S"; }
log()  { printf "[%s] %s\n" "$(date +"%F %T")" "$*"; }
warn() { printf "[%s] WARN: %s\n" "$(date +"%F %T")" "$*" >&2; }
err()  { printf "[%s] ERROR: %s\n" "$(date +"%F %T")" "$*" >&2; }
die()  { err "$*"; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

is_wsl() {
  [[ -n "${WSL_INTEROP-}" ]] && return 0
  [[ -n "${WSL_DISTRO_NAME-}" ]] && return 0
  grep -qi microsoft /proc/version 2>/dev/null && return 0
  return 1
}

as_root_prefix() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    echo ""
    return 0
  fi
  if have sudo; then
    echo "sudo"
    return 0
  fi
  return 1
}

run() {
  log "+ $*"
  "$@"
}

run_root() {
  local sudo_prefix
  if ! sudo_prefix="$(as_root_prefix)"; then
    die "Need root privileges (run as root or install sudo)."
  fi
  if [[ -n "$sudo_prefix" ]]; then
    log "+ $sudo_prefix $*"
    $sudo_prefix "$@"
  else
    log "+ $*"
    "$@"
  fi
}

install_pkgs_if_missing() {
  local pkgs=("$@")

  if have apt-get; then
    run_root apt-get update
    run_root apt-get install -y "${pkgs[@]}"
    return 0
  fi
  if have dnf; then
    run_root dnf install -y "${pkgs[@]}"
    return 0
  fi
  if have yum; then
    run_root yum install -y "${pkgs[@]}"
    return 0
  fi
  if have pacman; then
    run_root pacman -Sy --noconfirm "${pkgs[@]}"
    return 0
  fi
  if have zypper; then
    run_root zypper --non-interactive install "${pkgs[@]}"
    return 0
  fi
  if have apk; then
    run_root apk add --no-cache "${pkgs[@]}"
    return 0
  fi

  die "No supported package manager found. Install manually: ${pkgs[*]}"
}

usage() {
  cat <<'EOF'
ollama-install.sh

Installs/updates Ollama using the official install script (download -> execute),
then checks local API health.

Options:
  --version <ver>     Pin version via OLLAMA_VERSION (if supported by installer)
  --model <name>      After install, run: ollama pull <name>
  --inspect           Download installer + show preview, do not execute
  --dry-run           Same as --inspect
  --url <url>         Override installer URL (default: https://ollama.com/install.sh)
  --no-service        Skip systemctl enable/start
  --force             Reinstall even if ollama exists
  --root <path>       Override Francis root (e.g., /mnt/c/Francis)
  -h, --help          Show help

Examples:
  ./ollama-install.sh
  ./ollama-install.sh --model llama3.1
  ./ollama-install.sh --version 0.3.14
  ./ollama-install.sh --inspect
EOF
}

# ----------------------------
# Args
# ----------------------------
INSTALL_URL="https://ollama.com/install.sh"
OLLAMA_VERSION_ARG=""
PULL_MODEL=""
INSPECT=0
NO_SERVICE=0
FORCE=0
ROOT_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)   [[ $# -ge 2 ]] || die "--version requires a value"; OLLAMA_VERSION_ARG="$2"; shift 2 ;;
    --model)     [[ $# -ge 2 ]] || die "--model requires a value";   PULL_MODEL="$2"; shift 2 ;;
    --url)       [[ $# -ge 2 ]] || die "--url requires a value";     INSTALL_URL="$2"; shift 2 ;;
    --root)      [[ $# -ge 2 ]] || die "--root requires a value";    ROOT_OVERRIDE="$2"; shift 2 ;;
    --inspect|--dry-run) INSPECT=1; shift ;;
    --no-service) NO_SERVICE=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1 (use --help)" ;;
  esac
done

# ----------------------------
# Root + logging paths (Francis-style)
# ----------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "$ROOT_OVERRIDE" ]]; then
  ROOT="$ROOT_OVERRIDE"
else
  # Prefer explicit Francis root if it exists (common WSL location)
  if [[ -n "${FRANCIS_ROOT:-}" ]]; then
    ROOT="$FRANCIS_ROOT"
  elif [[ -d "/mnt/c/Francis" ]]; then
    ROOT="/mnt/c/Francis"
  elif [[ -d "/c/Francis" ]]; then
    ROOT="/c/Francis"
  else
    # Fallback: parent folder of scripts/
    ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  fi
fi

OUTDIR="$ROOT/data/logs/operations"
mkdir -p "$OUTDIR" 2>/dev/null || true

LOGFILE="$OUTDIR/ollama_install_$(ts).log"
# Tee everything to logfile
exec > >(tee -a "$LOGFILE") 2>&1

log "Root: $ROOT"
log "Log:  $LOGFILE"
log "URL:  $INSTALL_URL"

if is_wsl; then
  warn "WSL detected. If systemd isn't enabled in this distro, service start may fail; you can still run: ollama serve"
fi

# ----------------------------
# Ensure prerequisites
# ----------------------------
if ! have curl; then
  warn "curl not found; attempting to install curl + ca-certificates..."
  install_pkgs_if_missing curl ca-certificates
fi

# ----------------------------
# Short-circuit if already installed (unless forced)
# ----------------------------
if have ollama && [[ $FORCE -eq 0 ]]; then
  log "ollama already installed at: $(command -v ollama)"
  log "Use --force to reinstall."
else
  # ----------------------------
  # Download installer (safer than curl|sh)
  # ----------------------------
  TMP_DIR="$(mktemp -d)"
  INSTALLER="$TMP_DIR/ollama_install.sh"
  cleanup() { rm -rf "$TMP_DIR"; }
  trap cleanup EXIT

  log "Downloading installer to: $INSTALLER"
  run curl -fsSL "$INSTALL_URL" -o "$INSTALLER"

  # Basic sanity check so we don't execute an HTML error page
  first_line="$( { IFS= read -r line <"$INSTALLER" && printf '%s' "$line"; } 2>/dev/null || true )"
  if [[ "$first_line" != \#!*sh* && "$first_line" != \#!*bash* ]]; then
    log "Installer first line: $first_line"
    die "Downloaded content does not look like a shell script. Refusing to execute."
  fi

  chmod +x "$INSTALLER" || true

  if [[ $INSPECT -eq 1 ]]; then
    log "INSPECT MODE: Not executing installer."
    log "Installer saved at: $INSTALLER"
    echo
    echo "----- BEGIN installer preview (first 120 lines) -----"
    sed -n '1,120p' "$INSTALLER"
    echo "----- END installer preview -----"
    exit 0
  fi

  # ----------------------------
  # Run installer
  # ----------------------------
  log "Installing/updating Ollama..."
  if [[ -n "$OLLAMA_VERSION_ARG" ]]; then
    run_root env OLLAMA_VERSION="$OLLAMA_VERSION_ARG" sh "$INSTALLER"
  else
    run_root sh "$INSTALLER"
  fi
fi

# ----------------------------
# Verify binary
# ----------------------------
if ! have ollama; then
  die "Install completed but 'ollama' is not on PATH. Try reopening your shell, or locate the binary."
fi

log "Ollama binary: $(command -v ollama)"
if ollama --version >/dev/null 2>&1; then
  log "Ollama version: $(ollama --version 2>/dev/null | { IFS= read -r line; printf '%s' \"$line\"; })"
else
  warn "Could not read ollama version (ollama --version failed)."
fi

# ----------------------------
# Start service if possible (optional)
# ----------------------------
if [[ $NO_SERVICE -eq 1 ]]; then
  warn "Skipping service management (--no-service)."
else
  if have systemctl; then
    log "systemd detected; attempting to enable/start ollama service..."
    run_root systemctl enable --now ollama || warn "systemctl enable/start failed (may be normal in WSL/container)."
  else
    warn "systemctl not found. If Ollama isn't already running, start it with: ollama serve"
  fi
fi

# ----------------------------
# Optional: pull a model
# ----------------------------
if [[ -n "$PULL_MODEL" ]]; then
  log "Pulling model: $PULL_MODEL"
  run ollama pull "$PULL_MODEL"
fi

# ----------------------------
# Health check (local API)
# ----------------------------
API_URL="http://127.0.0.1:11434/api/tags"
log "Health check: $API_URL"
if curl -fsS --max-time 5 "$API_URL" >/dev/null 2>&1; then
  log "Health check PASSED (API reachable)."
else
  warn "Health check FAILED (API not reachable)."

  if have systemctl; then
    warn "Try: sudo systemctl status ollama --no-pager"
    warn "Logs: sudo journalctl -u ollama -n 200 --no-pager"
  fi

  warn "If service management isn't available, run this in a terminal:"
  warn "  ollama serve"
  warn "Then retry the API check."
fi

log "Done."
log "Saved log: $LOGFILE"
