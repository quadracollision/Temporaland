#!/usr/bin/env bash
set -euo pipefail

applications=/usr/local/share/temporaman/applications
install -d -o root -g root -m 0755 "$applications"
for app in audacity sunvox figlib shuriken hydrogen openrb speech downloader files notepad; do
  launcher="temporaman-$app.desktop"
  test -f "/usr/local/share/applications/$launcher"
  ln -sfn "/usr/local/share/applications/$launcher" "$applications/$launcher"
done

runuser -u audacity-studio -- python3 - <<'PY'
from pathlib import Path

home = Path.home()
bookmarks = home / ".config/gtk-3.0/bookmarks"
legacy = home / ".gtk-bookmarks"
uri = "file:///usr/local/share/temporaman/applications"

bookmarks.parent.mkdir(parents=True, exist_ok=True)
if not bookmarks.exists() and legacy.is_file():
    bookmarks.write_bytes(legacy.read_bytes())

with bookmarks.open("a+", encoding="utf-8") as stream:
    stream.seek(0)
    current = stream.read()
    if not any(line.strip().partition(" ")[0] == uri for line in current.splitlines()):
        if current and not current.endswith("\n"):
            stream.write("\n")
        stream.write(f"{uri} Applications\n")
PY
