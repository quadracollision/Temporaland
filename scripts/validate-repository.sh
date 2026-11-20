#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

bash -n scripts/*.sh xpra/*.sh
python3 -m py_compile \
  xpra/audacity-studio-apps.py \
  xpra/audacity-studio-collab.py \
  xpra/audacity-studio-web.py \
  xpra/figlib-sampler/figlib-sampler.py \
  xpra/temporaman-downloader.py
node --check xpra/collab.js

if [[ ! -s xpra/audacity-plugins/peteshift.ny ]] ||
   ! grep -q '^\$name "PeteShift"' xpra/audacity-plugins/peteshift.ny ||
   ! grep -q '^\$author "Jacob Pereira"' xpra/audacity-plugins/peteshift.ny; then
  printf 'PeteShift Audacity plug-in is missing or has invalid metadata.\n' >&2
  exit 1
fi

if [[ ! -s VERSION ]] || ! grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+' VERSION; then
  printf 'VERSION is missing or invalid.\n' >&2
  exit 1
fi
for release_file in CHANGELOG.md docs/releasing.md docs/release-notes-v0.1.0.md .github/workflows/validate.yml; do
  if [[ ! -s "$release_file" ]]; then
    printf 'Missing release file: %s\n' "$release_file" >&2
    exit 1
  fi
done

if grep -Eq "printf .*(reddit|templeman|12345).*password|password=.*(reddit|templeman|12345)" \
    xpra/install-temporaland.sh; then
  printf 'The Temporaland installer contains a hard-coded deployment password.\n' >&2
  exit 1
fi

required_temporaland_guards=(
  'TEMPORALAND_PASSWORD_FILE'
  'path=temporaman/#path=temporaland/'
  'exclusiveControl:false'
  'InaccessiblePaths=/srv/audacity-studio'
  'temporaland-(helio|chipwave)'
)
for guard in "${required_temporaland_guards[@]}"; do
  if ! grep -Eq "$guard" xpra/install-temporaland.sh; then
    printf 'Missing Temporaland release guard: %s\n' "$guard" >&2
    exit 1
  fi
done

required_settings=(
  allow_kasm_sharing
  shared_session_full_control
  allow_kasm_audio
  allow_kasm_uploads
  allow_kasm_downloads
  allow_persistent_profile
)

for setting in "${required_settings[@]}"; do
  if ! grep -q "$setting" docs/configure-kasm.md; then
    printf 'Missing required Kasm setting in configuration guide: %s\n' "$setting" >&2
    exit 1
  fi
done

required_checks=(
  unauthenticated
  'exact running instance'
  'uploads and imports'
  'hear Audacity playback'
  'new session can open'
  '60-minute'
)

for check in "${required_checks[@]}"; do
  if ! grep -qi "$check" docs/pilot-checklist.md; then
    printf 'Missing required pilot check: %s\n' "$check" >&2
    exit 1
  fi
done

printf 'Repository validation passed.\n'
