#!/usr/bin/env bash
set -euo pipefail

failures=0

pass() { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

if [[ "$(uname -s)" == "Linux" ]]; then pass "Linux host"; else fail "Kasm needs a supported Linux host"; fi

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  case "${ID:-}:${VERSION_ID:-}" in
    ubuntu:22.04|ubuntu:24.04|debian:11|debian:12|debian:13) pass "Supported OS: ${PRETTY_NAME:-$ID}" ;;
    *) warn "Check Kasm's current support matrix for ${PRETTY_NAME:-unknown OS}" ;;
  esac
else
  warn "Could not identify the operating system"
fi

arch="$(uname -m)"
case "$arch" in x86_64|aarch64|arm64) pass "Supported architecture: $arch" ;; *) fail "Unsupported architecture: $arch" ;; esac

cpu_count="$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '0')"
if (( cpu_count >= 4 )); then pass "$cpu_count CPU threads"; else warn "$cpu_count CPU threads; use at least 4 for an audio-editing pilot"; fi

memory_kib="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || printf '0')"
memory_gib=$((memory_kib / 1024 / 1024))
if (( memory_gib >= 7 )); then pass "Approximately ${memory_gib} GiB RAM"; else fail "Approximately ${memory_gib} GiB RAM; use at least 8 GiB"; fi

available_kib="$(df -Pk /opt 2>/dev/null | awk 'NR==2 {print $4}')"
available_gib=$((available_kib / 1024 / 1024))
if (( available_gib >= 74 )); then pass "Approximately ${available_gib} GiB free under /opt"; else fail "Approximately ${available_gib} GiB free under /opt; current Kasm requires at least 75 GiB SSD capacity"; fi

if command -v docker >/dev/null; then
  if docker info >/dev/null 2>&1; then pass "Docker daemon is accessible"; else warn "Docker exists but this user cannot access the daemon"; fi
else
  warn "Docker is not installed; the Kasm installer can install required dependencies on supported hosts"
fi

if command -v curl >/dev/null; then pass "curl is installed"; else fail "curl is required"; fi
if command -v sha256sum >/dev/null; then pass "sha256sum is installed"; else fail "sha256sum is required"; fi

if command -v ss >/dev/null; then
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq '(^|:)443$'; then fail "TCP port 443 is already in use"; else pass "TCP port 443 appears free"; fi
else
  warn "Could not check whether TCP port 443 is free"
fi

if (( failures > 0 )); then
  printf '\nHost check failed with %d blocking issue(s).\n' "$failures"
  exit 1
fi

printf '\nHost check passed. Review warnings before installing Kasm.\n'
