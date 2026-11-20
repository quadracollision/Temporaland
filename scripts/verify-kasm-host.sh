#!/usr/bin/env bash
set -euo pipefail

failures=0
warnings=0

pass() { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; warnings=$((warnings + 1)); }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

if [[ -d /opt/kasm/current ]]; then pass "Kasm installation directory exists"; else fail "/opt/kasm/current is missing"; fi

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    pass "Docker daemon is accessible"

    kasm_containers="$(docker ps --format '{{.Names}}' | grep -c '^kasm_' || true)"
    if (( kasm_containers >= 5 )); then pass "$kasm_containers Kasm containers are running"; else fail "Only $kasm_containers running Kasm containers were found"; fi

    unhealthy="$(docker ps --filter health=unhealthy --format '{{.Names}}' | grep '^kasm_' || true)"
    if [[ -z "$unhealthy" ]]; then pass "No unhealthy Kasm containers"; else fail "Unhealthy Kasm containers: $unhealthy"; fi

    audacity_images="$(docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -E '^kasmweb/audacity:' || true)"
    if [[ -n "$audacity_images" ]]; then
      pass "Audacity image is present: $(printf '%s' "$audacity_images" | paste -sd ',' -)"
    else
      warn "No local kasmweb/audacity image; install Audacity from the Workspace Registry and launch it once"
    fi
  else
    fail "Docker exists but this user cannot access its daemon"
  fi
else
  fail "Docker is not installed"
fi

if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq '(^|:)443$'; then
  pass "HTTPS is listening on TCP port 443"
else
  fail "Nothing appears to be listening on TCP port 443"
fi

if curl --silent --show-error --insecure --fail --max-time 10 https://127.0.0.1/ >/dev/null 2>&1; then
  pass "Local Kasm HTTPS endpoint responds"
else
  fail "Local Kasm HTTPS endpoint did not respond successfully"
fi

project_dir="/srv/doubletrack/projects"
if [[ -d "$project_dir" ]]; then
  owner="$(stat -c '%u:%g' "$project_dir")"
  mode="$(stat -c '%a' "$project_dir")"
  if [[ "$owner" == "1000:1000" ]]; then pass "$project_dir is owned by 1000:1000"; else fail "$project_dir owner is $owner, expected 1000:1000"; fi
  case "$mode" in 770|2770) pass "$project_dir mode is $mode" ;; *) warn "$project_dir mode is $mode; expected 770 or 2770" ;; esac
else
  warn "$project_dir is missing; configure durable storage before testing persistence"
fi

cat <<'EOF'

Manual checks still required in the Kasm admin UI:
  [ ] two separate named users exist
  [ ] both users belong to Audacity Collaborators
  [ ] effective allow_kasm_sharing is true
  [ ] effective shared_session_full_control is true
  [ ] effective allow_kasm_audio is true
  [ ] effective allow_kasm_uploads is true
  [ ] effective allow_kasm_downloads is true
  [ ] effective allow_persistent_profile is true
  [ ] Audacity Volume Mappings binds /srv/doubletrack/projects to /projects
EOF

printf '\nAutomated result: %d failure(s), %d warning(s).\n' "$failures" "$warnings"
(( failures == 0 ))
