#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  printf 'Run this installer as root.\n' >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_CODENAME:-}" != "noble" ]]; then
  printf 'This installer is pinned to Ubuntu 24.04 (noble).\n' >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  adwaita-icon-theme audacity automake build-essential calf-plugins cmake curl dbus-x11 eq10q ffmpeg guitarix-lv2 \
  invada-studio-plugins-lv2 libasound2-dev libaubio-dev lsp-plugins-lv2 \
  libgl1-mesa-dev libjack-jackd2-dev liblo-dev libqt5opengl5-dev \
  libpulse-dev librsvg2-common librubberband-dev libsamplerate0-dev libsndfile1-dev libtool mda-lv2 mousepad nginx \
  libsdl2-2.0-0 libxkbcommon-x11-0 novnc openbox padthv1-lv2 patch pcmanfm pkg-config pulseaudio pulseaudio-utils python3 python3-numpy python3-scipy python3-soundfile python3-tk rustup swh-lv2 \
  qt5-qmake qtbase5-dev samplv1-lv2 so-synth-lv2 synthv1-lv2 tint2 \
  unzip websockify x11-utils x11vnc x42-plugins xdotool xvfb

apt-get install -y --no-install-recommends -t noble-backports hydrogen
bash "$script_dir/install-speech-engines.sh"

if ! id audacity-studio >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /srv/audacity-studio --shell /usr/sbin/nologin audacity-studio
fi

install -d -o audacity-studio -g audacity-studio -m 0750 \
  /srv/audacity-studio /srv/audacity-studio/imports \
  /srv/audacity-studio/projects /srv/audacity-studio/exports
install -d -o audacity-studio -g audacity-studio -m 0700 /srv/audacity-studio/audio-inputs
if [[ ! -f /srv/audacity-studio/audio-inputs/asoundrc-inputs.conf ]]; then
  install -o audacity-studio -g audacity-studio -m 0600 /dev/null \
    /srv/audacity-studio/audio-inputs/asoundrc-inputs.conf
fi
install -d -o audacity-studio -g audacity-studio -m 0750 /srv/audacity-studio/Documents/Hydrogen
if [[ ! -e "/srv/audacity-studio/Documents/Hydrogen/Audacity imports" ]]; then
  ln -s /srv/audacity-studio/imports "/srv/audacity-studio/Documents/Hydrogen/Audacity imports"
fi
install -d -o audacity-studio -g audacity-studio -m 0750 \
  /srv/audacity-studio/Documents/SunVox /srv/audacity-studio/projects/SunVox
if [[ ! -e "/srv/audacity-studio/Documents/SunVox/Audacity imports" ]]; then
  ln -s /srv/audacity-studio/imports "/srv/audacity-studio/Documents/SunVox/Audacity imports"
fi
if [[ ! -e "/srv/audacity-studio/Documents/SunVox/Projects" ]]; then
  ln -s /srv/audacity-studio/projects/SunVox "/srv/audacity-studio/Documents/SunVox/Projects"
fi
install -d -o audacity-studio -g audacity-studio -m 0750 \
  /srv/audacity-studio/Documents/OpenRB-338 \
  /srv/audacity-studio/projects/OpenRB-338 \
  /srv/audacity-studio/projects/OpenRB-338/Mods
if [[ ! -e "/srv/audacity-studio/Documents/OpenRB-338/Mods" ]]; then
  ln -s /srv/audacity-studio/projects/OpenRB-338/Mods \
    "/srv/audacity-studio/Documents/OpenRB-338/Mods"
fi
if [[ ! -e "/srv/audacity-studio/Documents/OpenRB-338/Exports" ]]; then
  ln -s /srv/audacity-studio/exports \
    "/srv/audacity-studio/Documents/OpenRB-338/Exports"
fi
install -d -o root -g audacity-studio -m 0750 /etc/audacity-studio
install -d -o root -g root -m 0755 /var/www/temporaman \
  /usr/local/libexec /usr/local/share/applications /usr/local/share/icons

if [[ ! -s /etc/audacity-studio/password ]]; then
  umask 0027
  openssl rand -base64 24 | tr -d '\n' > /etc/audacity-studio/password
fi
chown root:audacity-studio /etc/audacity-studio/password
chmod 0640 /etc/audacity-studio/password
install -o root -g root -m 0644 "$script_dir/tint2rc" /etc/audacity-studio/tint2rc

install -o root -g root -m 0755 "$script_dir/audacity-studio-launch" /usr/local/libexec/audacity-studio-launch
install -o root -g root -m 0755 "$script_dir/audacity-studio-open-app" /usr/local/libexec/audacity-studio-open-app
install -o root -g root -m 0755 "$script_dir/temporaman-downloader.py" /usr/local/libexec/temporaman-downloader
install -o root -g root -m 0755 "$script_dir/temporaman-speech.py" /usr/local/libexec/temporaman-speech
rm -f /usr/local/libexec/temporaman-files
install -o root -g root -m 0755 "$script_dir/audacity-studio-web.py" /usr/local/libexec/audacity-studio-web
install -o root -g root -m 0755 "$script_dir/audacity-studio-apps.py" /usr/local/libexec/audacity-studio-apps
install -o root -g root -m 0755 "$script_dir/audacity-studio-collab.py" /usr/local/libexec/audacity-studio-collab
install -o root -g root -m 0755 "$script_dir/openrb-338/openrb-figlib-kit.py" \
  /usr/local/libexec/openrb-figlib-kit
install -o root -g root -m 0644 "$script_dir/audacity-plugins/peteshift.ny" /usr/share/audacity/plug-ins/peteshift.ny
install -d -o root -g root -m 0755 /usr/local/share/temporaman/figlib-sampler
cp -a "$script_dir/figlib-sampler/." /usr/local/share/temporaman/figlib-sampler/
chown -R root:root /usr/local/share/temporaman/figlib-sampler
find /usr/local/share/temporaman/figlib-sampler -type d -exec chmod 0755 {} +
chmod 0755 /usr/local/share/temporaman/figlib-sampler/figlib-sampler.py
install -o root -g root -m 0644 "$script_dir/login.html" /var/www/temporaman/login.html
install -o root -g root -m 0644 "$script_dir/shrine.html" /var/www/temporaman/shrine.html
install -o root -g root -m 0644 "$script_dir/collab.js" /var/www/temporaman/collab.js
install -o root -g root -m 0644 "$script_dir/audio-input.js" /var/www/temporaman/audio-input.js
install -o root -g root -m 0644 "$script_dir/launchers/"*.desktop /usr/local/share/applications/
install -o root -g root -m 0644 "$script_dir/icons/"* /usr/local/share/icons/
bash "$script_dir/install-application-place.sh"
install -o audacity-studio -g audacity-studio -m 0644 "$script_dir/asoundrc" /srv/audacity-studio/.asoundrc
# Remove artifacts from releases that still bundled WebSynth and Tiny-LV2.
rm -rf /var/www/temporaman/synth
rm -f /usr/local/bin/temporaman-lv2 \
  /usr/local/share/applications/temporaman-lv2.desktop \
  /usr/local/share/icons/temporaman-lv2.svg

sunvox_download="$(mktemp)"
sunvox_directory="$(mktemp -d)"
curl -fsSL https://www.warmplace.ru/soft/sunvox/sunvox-2.1.4d.zip -o "$sunvox_download"
printf '%s  %s\n' 'acd94ae4acd6ab60bee1f5ba117082cd2ea51f7e87871f1776d11cfd24a59880' "$sunvox_download" | sha256sum -c -
unzip -q "$sunvox_download" -d "$sunvox_directory"
install -o root -g root -m 0755 \
  "$sunvox_directory/sunvox/sunvox/linux_x86_64/sunvox" /usr/local/bin/sunvox
install -d -o root -g root -m 0755 /usr/local/share/doc/sunvox
install -o root -g root -m 0644 \
  "$sunvox_directory/sunvox/docs/license/sunvox.txt" \
  /usr/local/share/doc/sunvox/LICENSE
rm -rf "$sunvox_directory"
rm -f "$sunvox_download"
# Remove the application replaced by SunVox when upgrading an older host.
rm -f /usr/local/bin/chipwave-studio \
  /usr/local/share/applications/temporaman-chipwave.desktop \
  /usr/local/share/icons/temporaman-chipwave.svg
rm -rf /usr/local/lib/chipwave-studio-0.2.22.0
# Remove Helio when upgrading an older host. Saved user files are preserved.
rm -f /usr/local/bin/helio \
  /usr/local/share/applications/temporaman-helio.desktop \
  /usr/local/share/icons/temporaman-helio.svg

yt_dlp_download="$(mktemp)"
curl -fsSL https://github.com/yt-dlp/yt-dlp/releases/download/2026.10.26/yt-dlp -o "$yt_dlp_download"
printf '%s  %s\n' 'e51e69e89489f199530f13d32a4342da3ddb2cf34842f364603a066db05afbf3' "$yt_dlp_download" | sha256sum -c -
install -o root -g root -m 0755 "$yt_dlp_download" /usr/local/bin/yt-dlp
rm -f "$yt_dlp_download"

deno_download="$(mktemp)"
deno_directory="$(mktemp -d)"
curl -fsSL https://github.com/denoland/deno/releases/download/v2.9.8/deno-x86_64-unknown-linux-gnu.zip -o "$deno_download"
printf '%s  %s\n' 'e890975bc2549807bbcc0b584ffafda72cc7c93349dd99c80483dd784f6c4609' "$deno_download" | sha256sum -c -
unzip -q "$deno_download" -d "$deno_directory"
install -o root -g root -m 0755 "$deno_directory/deno" /usr/local/bin/deno
rm -f "$deno_download"
rm -r "$deno_directory"

shuriken_archive="$(mktemp)"
shuriken_directory="$(mktemp -d)"
curl -fsSL https://codeload.github.com/rock-hopper/shuriken/tar.gz/d09afc719d813c1436c702ab0c33f9d50d652dc1 -o "$shuriken_archive"
printf '%s  %s\n' 'bedcf22ff61361c6f10fc7902b5d97a693993e69272b81f70e6ad034f3d4f895' "$shuriken_archive" | sha256sum -c -
tar -xzf "$shuriken_archive" --strip-components=1 -C "$shuriken_directory"
(
  cd "$shuriken_directory"
  nice -n 15 ./build
)
install -o root -g root -m 0755 "$shuriken_directory/release/shuriken" /usr/local/bin/shuriken
rm -f "$shuriken_archive"
rm -r "$shuriken_directory"

openrb_version=2026.1118.0919
openrb_release="$(mktemp)"
openrb_release_directory="$(mktemp -d)"
curl -fsSL \
  "https://github.com/pingw33n/OpenRB-338/releases/download/v${openrb_version}/OpenRB-338-${openrb_version}-x86_64-unknown-linux-gnu.tar.gz" \
  -o "$openrb_release"
printf '%s  %s\n' \
  '90eeacc44b7881efdc39531af1b98ef0751b03b3642f4c78e38cdad990ef5fa9' \
  "$openrb_release" | sha256sum -c -
tar -xzf "$openrb_release" -C "$openrb_release_directory"
openrb_release_root="$openrb_release_directory/OpenRB-338-${openrb_version}-x86_64-unknown-linux-gnu"
install -o root -g root -m 0755 "$openrb_release_root/orb" /usr/local/bin/orb
install -d -o root -g root -m 0755 /usr/local/share/doc/openrb-338
install -o root -g root -m 0644 "$openrb_release_root/LICENSE" \
  /usr/local/share/doc/openrb-338/LICENSE

openrb_standard="$(mktemp)"
curl -fsSL https://raw.githubusercontent.com/pingw33n/OpenRB-338/v2026.1118.0919/assets/Standard.rbm \
  -o "$openrb_standard"
printf '%s  %s\n' \
  '6355b5f14fc2ebfe7ed9e6e42208f97817f96c5e30ed42fdca4205d3cdab5fbe' \
  "$openrb_standard" | sha256sum -c -
rm -rf /usr/local/share/openrb-338/standard-template
install -d -o root -g root -m 0755 /usr/local/share/openrb-338/standard-template
/usr/local/bin/orb mod unpack -o /usr/local/share/openrb-338/standard-template \
  "$openrb_standard"
chown -R root:root /usr/local/share/openrb-338

openrb_source="$(mktemp)"
openrb_source_directory="$(mktemp -d)"
curl -fsSL \
  https://codeload.github.com/pingw33n/OpenRB-338/tar.gz/79e003326a657e0ebfa92fdb18101069fe1f55a3 \
  -o "$openrb_source"
printf '%s  %s\n' \
  'f3356f851748bd77df4adc8726d558121d8a6792ac4d83ef69c5fa9ee1da5bbf' \
  "$openrb_source" | sha256sum -c -
tar -xzf "$openrb_source" --strip-components=1 -C "$openrb_source_directory"
patch -d "$openrb_source_directory" -p1 < "$script_dir/openrb-338/figlib-menu.patch"
rustup toolchain install 1.99.1 --profile minimal
(
  cd "$openrb_source_directory"
  rustup run 1.99.1 cargo build --release \
    -p orb-ui --bin OpenRB-338 -p orb-cli --bin orb
)
install -o root -g root -m 0755 \
  "$openrb_source_directory/target/release/OpenRB-338" /usr/local/bin/OpenRB-338
install -o root -g root -m 0755 \
  "$openrb_source_directory/target/release/orb" /usr/local/bin/orb
rm -rf "$openrb_release_directory" "$openrb_source_directory"
rm -f "$openrb_release" "$openrb_standard" "$openrb_source"

install -o root -g root -m 0644 "$script_dir/audacity-studio.service" /etc/systemd/system/audacity-studio.service
install -o root -g root -m 0644 "$script_dir/audacity-studio-apps.service" /etc/systemd/system/audacity-studio-apps.service
install -o root -g root -m 0644 "$script_dir/audacity-studio-collab.service" /etc/systemd/system/audacity-studio-collab.service
install -o root -g root -m 0644 "$script_dir/audacity-studio.nginx" /etc/nginx/snippets/margeux-temporaman.conf

for margeux_config in /etc/nginx/sites-available/margeux /etc/nginx/sites-enabled/margeux; do
  if [[ -f "$margeux_config" ]] && ! grep -qxF '    include /etc/nginx/snippets/margeux-temporaman.conf;' "$margeux_config"; then
    sed -i '/include \/etc\/nginx\/snippets\/margeux-gable.conf;/i\    include /etc/nginx/snippets/margeux-temporaman.conf;' "$margeux_config"
  fi
done

install -o root -g root -m 0750 /dev/stdin /usr/local/sbin/audacity-studio-password <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'Studio URL: https://margeux.com/temporaman/\nPassword: '
cat /etc/audacity-studio/password
printf '\n'
EOF

systemctl disable --now xpra-server.socket xpra-server.service 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now audacity-studio
systemctl enable --now audacity-studio-apps
systemctl enable --now audacity-studio-collab

for attempt in $(seq 1 30); do
  if ss -ltn | awk '{print $4}' | grep -q '^127.0.0.1:14500$' && \
     ss -ltn | awk '{print $4}' | grep -q '^127.0.0.1:14501$' && \
     ss -ltn | awk '{print $4}' | grep -q '^127.0.0.1:14502$' && \
     ss -ltn | awk '{print $4}' | grep -q '^127.0.0.1:14503$'; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    systemctl --no-pager --full status audacity-studio || true
    journalctl -u audacity-studio -n 100 --no-pager || true
    printf 'The studio did not become ready.\n' >&2
    exit 1
  fi
  sleep 1
done

nginx -t
systemctl reload nginx
printf '\nTemporaman installed at https://margeux.com/temporaman/\n'
/usr/local/sbin/audacity-studio-password
