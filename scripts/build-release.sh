#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(tr -d '[:space:]' < "$repo_root/VERSION")"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
  printf 'Invalid VERSION: %s\n' "$version" >&2
  exit 1
fi

"$repo_root/scripts/validate-repository.sh"
mkdir -p "$repo_root/dist"
archive="$repo_root/dist/temporaman-shrine-v${version}.tar.gz"

tar \
  --sort=name \
  --mtime='UTC 2026-11-19' \
  --owner=0 --group=0 --numeric-owner \
  --exclude='.git' \
  --exclude='.agents' \
  --exclude='.aws' \
  --exclude='.codex' \
  --exclude='dist' \
  --exclude='github-upload' \
  --exclude='uploads' \
  --exclude='__pycache__' \
  --transform="s#^\.#temporaman-shrine-v${version}#" \
  -czf "$archive" -C "$repo_root" .

(cd "$repo_root/dist" && sha256sum "$(basename "$archive")" > "$(basename "$archive").sha256")
printf 'Built %s\n' "$archive"
