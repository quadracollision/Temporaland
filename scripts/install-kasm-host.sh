#!/usr/bin/env bash
set -euo pipefail

KASM_VERSION="1.19.0"
KASM_ARCHIVE="kasm_release_${KASM_VERSION}.tar.gz"
KASM_URL="https://kasm-static-content.s3.amazonaws.com/${KASM_ARCHIVE}"

if [[ "${I_UNDERSTAND_THIS_INSTALLS_KASM:-}" != "yes" ]]; then
  cat >&2 <<'EOF'
This installs Kasm Workspaces system-wide and is intended for a fresh, dedicated server.
Read docs/configure-kasm.md first, then run:

  I_UNDERSTAND_THIS_INSTALLS_KASM=yes ./scripts/install-kasm-host.sh
EOF
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"$script_dir/check-host.sh"

install_tmp="$(mktemp -d /tmp/doubletrack-kasm.XXXXXX)"
cleanup() {
  case "$install_tmp" in /tmp/doubletrack-kasm.*) rm -rf -- "$install_tmp" ;; esac
}
trap cleanup EXIT

cd "$install_tmp"
curl --fail --location --remote-name "$KASM_URL"
curl --fail --location --remote-name "${KASM_URL}.sha256sum"
sha256sum --check "${KASM_ARCHIVE}.sha256sum"
tar -xf "$KASM_ARCHIVE"

cat <<'EOF'

The verified Kasm installer is about to run. It will install system services and containers.
Kasm will print randomly generated admin and user passwords at the end. Save them immediately.

EOF
sudo bash kasm_release/install.sh --accept-eula --use-static-images

cat <<'EOF'

Kasm installation finished.
Open https://YOUR_SERVER/ and continue with docs/configure-kasm.md.
Do not expose the service publicly until TLS, accounts, group permissions, and storage are configured.
EOF
