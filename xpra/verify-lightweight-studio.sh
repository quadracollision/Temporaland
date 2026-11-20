#!/usr/bin/env bash
set -euo pipefail

failures=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

if systemctl is-active --quiet audacity-studio; then pass 'studio service is active'; else fail 'studio service is inactive'; fi
if systemctl is-enabled --quiet audacity-studio; then pass 'studio starts on boot'; else fail 'studio is not enabled'; fi
for port in 5900 14500 14501 14502; do
  if ss -ltn | awk '{print $4}' | grep -q "^127.0.0.1:$port$"; then pass "localhost:$port is listening"; else fail "localhost:$port is missing"; fi
done
for process in audacity Xvfb x11vnc pulseaudio; do
  if pgrep -u audacity-studio -x "$process" >/dev/null; then pass "$process is running"; else fail "$process is not running"; fi
done
if pgrep -u audacity-studio -f audacity-studio-web >/dev/null; then pass 'login/upload/audio server is running'; else fail 'web helper is not running'; fi
if systemctl is-active --quiet audacity-studio-collab; then pass 'collaboration sidecar is active'; else fail 'collaboration sidecar is inactive'; fi
if python3 -c "import sys; sys.path.insert(0, '/usr/local/share/temporaman/figlib-sampler/figlib52/src'); from pySynth.routing import EFFECT_DISPATCH; raise SystemExit(len(EFFECT_DISPATCH) != 91)"; then pass 'FigLib has all 91 effects'; else fail 'FigLib effect stack is incomplete'; fi
if runuser -u audacity-studio -- env XDG_RUNTIME_DIR=/run/audacity-studio pactl list short sinks | grep -q $'studio\t'; then pass 'Temporaman playback device exists'; else fail 'Temporaman playback device is missing'; fi
if nginx -t >/dev/null 2>&1; then pass 'nginx configuration is valid'; else fail 'nginx configuration is invalid'; fi

cookie_file="$(mktemp)"
trap 'rm -f "$cookie_file"' EXIT
studio_password="$(cat /etc/audacity-studio/password)"
login_status="$(curl -sS -o /dev/null -w '%{http_code}' -c "$cookie_file" --data-urlencode "password=$studio_password" https://margeux.com/temporaman/api/login)"
if [[ "$login_status" == 204 ]]; then pass 'password login works'; else fail "password login returned $login_status"; fi
for endpoint in shrine.html upload; do
  status="$(curl -sS -o /dev/null -w '%{http_code}' -b "$cookie_file" "https://margeux.com/temporaman/$endpoint")"
  if [[ "$status" == 200 ]]; then pass "$endpoint is available after login"; else fail "$endpoint returned $status"; fi
done
if [[ -s /etc/audacity-studio/password ]]; then pass 'studio password exists'; else fail 'studio password is missing'; fi
for dir in imports projects exports; do
  if [[ -d "/srv/audacity-studio/$dir" ]]; then pass "$dir directory exists"; else fail "$dir directory is missing"; fi
done

printf '\nResource snapshot:\n'
systemctl show audacity-studio -p MemoryCurrent -p MemoryPeak -p CPUUsageNSec --no-pager
printf '\nAutomated result: %d failure(s).\n' "$failures"
(( failures == 0 ))
