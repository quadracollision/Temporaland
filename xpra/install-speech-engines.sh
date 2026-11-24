#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends espeak-ng python3-venv xterm

piper_env=/opt/temporaman-piper-1.8.0
if ! "$piper_env/bin/python" -c 'import piper' 2>/dev/null; then
  python3 -m venv "$piper_env"
  "$piper_env/bin/python" -m pip install --disable-pip-version-check \
    --only-binary=:all: 'piper-tts==1.8.0'
fi

models=/usr/local/share/temporaman/speech
model=en_US-libritts_r-medium.onnx
model_hash=10bb85e071d616fcf4071f369f1799d0491492ab3c5d552ec19fb548fac13195
voice_url=https://huggingface.co/rhasspy/piper-voices/resolve/e9c8a39444359388adaa94255becb37a5a2b8e51/en/en_US/libritts_r/medium
install -d -m 0755 "$models"
if ! printf '%s  %s\n' "$model_hash" "$models/$model" | sha256sum -c --status || \
   [[ ! -s "$models/$model.json" || ! -s "$models/MODEL_CARD" ]]; then
  download_dir="$(mktemp -d)"
  trap 'rm -r -- "$download_dir"' EXIT
  for file in "$model" "$model.json" MODEL_CARD; do
    curl -fsSL --retry 3 --max-time 180 "$voice_url/$file?download=true" -o "$download_dir/$file"
  done
  printf '%s  %s\n' "$model_hash" "$download_dir/$model" | sha256sum -c -
  install -m 0644 "$download_dir/$model" "$download_dir/$model.json" "$download_dir/MODEL_CARD" "$models/"
fi
