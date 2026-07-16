#!/bin/sh
set -eu

config=/francis/runtime-config.json
state=/francis/state
tenant=/francis/tenant/authorized.txt

runtime_identity=$(sed -n 's/.*"runtime_identity": "\([^"]*\)".*/\1/p' "$config")
runtime_nonce=$(sed -n 's/.*"runtime_nonce": "\([^"]*\)".*/\1/p' "$config")
lease_id=$(sed -n 's/.*"lease_id": "\([^"]*\)".*/\1/p' "$config")
tenant_key=$(sed -n 's/.*"tenant_key": "\([^"]*\)".*/\1/p' "$config")
copy_id=$(sed -n 's/.*"copy_id": "\([^"]*\)".*/\1/p' "$config")
lease_seconds=$(sed -n 's/.*"lease_seconds": \([0-9]*\).*/\1/p' "$config")

[ -r "$tenant" ]
if cat /francis/tenant-b/forbidden.txt >/dev/null 2>&1; then
  printf 'unexpected tenant B access\n' > "$state/tenant-b-visible"
  exit 42
fi
uid_value=$(id -u)
cap_eff=$(awk '/^CapEff:/ {print $2}' /proc/self/status)
sequence=1
while [ "$sequence" -le "$lease_seconds" ]; do
  now_ms=$(($(date +%s) * 1000))
  tmp="$state/heartbeat.tmp"
  printf '{"cap_eff":"%s","copy_id":"%s","lease_id":"%s","recorded_at_unix_ms":%s,"runtime_identity":"%s","runtime_nonce":"%s","sequence":%s,"tenant_a_readable":true,"tenant_b_visible":false,"tenant_key":"%s","uid":"%s"}\n' \
    "$cap_eff" "$copy_id" "$lease_id" "$now_ms" "$runtime_identity" "$runtime_nonce" "$sequence" "$tenant_key" "$uid_value" > "$tmp"
  mv "$tmp" "$state/heartbeat.json"
  sequence=$((sequence + 1))
  sleep 1
done
