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
  audacity automake build-essential curl dbus-x11 ffmpeg libasound2-dev libaubio-dev \
  libgl1-mesa-dev libjack-jackd2-dev liblo-dev libqt5opengl5-dev \
  liblilv-dev libsuil-dev libpulse-dev librubberband-dev libsamplerate0-dev libsndfile1-dev libtool mda-lv2 nginx \
  novnc openbox padthv1-lv2 pkg-config pulseaudio pulseaudio-utils python3 python3-numpy python3-scipy python3-soundfile python3-tk \
  qt5-qmake qtbase5-dev samplv1-lv2 so-synth-lv2 synthv1-lv2 tint2 \
  unzip websockify x11-utils x11vnc xdotool xvfb

apt-get install -y --no-install-recommends -t noble-backports hydrogen

if ! id audacity-studio >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /srv/audacity-studio --shell /usr/sbin/nologin audacity-studio
fi

install -d -o audacity-studio -g audacity-studio -m 0750 \
  /srv/audacity-studio /srv/audacity-studio/imports \
  /srv/audacity-studio/projects /srv/audacity-studio/exports
install -d -o audacity-studio -g audacity-studio -m 0750 /srv/audacity-studio/Documents/Helio
if [[ ! -e "/srv/audacity-studio/Documents/Helio/Audacity imports" ]]; then
  ln -s /srv/audacity-studio/imports "/srv/audacity-studio/Documents/Helio/Audacity imports"
fi
install -d -o audacity-studio -g audacity-studio -m 0750 /srv/audacity-studio/Documents/Hydrogen
if [[ ! -e "/srv/audacity-studio/Documents/Hydrogen/Audacity imports" ]]; then
  ln -s /srv/audacity-studio/imports "/srv/audacity-studio/Documents/Hydrogen/Audacity imports"
fi
install -d -o root -g audacity-studio -m 0750 /etc/audacity-studio
install -d -o root -g root -m 0755 /var/www/temporaman /var/www/temporaman/synth \
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
install -o root -g root -m 0755 "$script_dir/audacity-studio-web.py" /usr/local/libexec/audacity-studio-web
install -o root -g root -m 0755 "$script_dir/audacity-studio-apps.py" /usr/local/libexec/audacity-studio-apps
install -o root -g root -m 0755 "$script_dir/audacity-studio-collab.py" /usr/local/libexec/audacity-studio-collab
install -o root -g root -m 0644 "$script_dir/audacity-plugins/peteshift.ny" /usr/share/audacity/plug-ins/peteshift.ny
install -d -o root -g root -m 0755 /usr/local/share/temporaman/figlib-sampler
cp -a "$script_dir/figlib-sampler/." /usr/local/share/temporaman/figlib-sampler/
chown -R root:root /usr/local/share/temporaman/figlib-sampler
find /usr/local/share/temporaman/figlib-sampler -type d -exec chmod 0755 {} +
chmod 0755 /usr/local/share/temporaman/figlib-sampler/figlib-sampler.py
install -o root -g root -m 0644 "$script_dir/login.html" /var/www/temporaman/login.html
install -o root -g root -m 0644 "$script_dir/shrine.html" /var/www/temporaman/shrine.html
install -o root -g root -m 0644 "$script_dir/collab.js" /var/www/temporaman/collab.js
install -o root -g root -m 0644 "$script_dir/vendor/web-synth/index.html" /var/www/temporaman/synth/index.html
install -o root -g root -m 0644 "$script_dir/vendor/web-synth/LICENSE" /var/www/temporaman/synth/LICENSE
install -o root -g root -m 0644 "$script_dir/vendor/web-synth/UPSTREAM.md" /var/www/temporaman/synth/UPSTREAM.md
install -o root -g root -m 0644 "$script_dir/launchers/"*.desktop /usr/local/share/applications/
install -o root -g root -m 0644 "$script_dir/icons/"*.svg /usr/local/share/icons/
install -o audacity-studio -g audacity-studio -m 0644 "$script_dir/asoundrc" /srv/audacity-studio/.asoundrc

chipwave_download="$(mktemp)"
curl -fsSL https://github.com/postmanpat-303/ChipWaveStudio/releases/download/v0.2.22.0/ChipWave-0.2.22.0-linux-x86_64.AppImage -o "$chipwave_download"
printf '%s  %s\n' '86b61d1ca298b9fe0c5e17c2cbb3a21b8f1172f7193d003352b52ace49ff226c' "$chipwave_download" | sha256sum -c -
install -o root -g root -m 0755 "$chipwave_download" /usr/local/bin/chipwave-studio
chipwave_directory="$(mktemp -d)"
(
  cd "$chipwave_directory"
  "$chipwave_download" --appimage-extract >/dev/null
)
install -d -o root -g root -m 0755 /usr/local/lib/chipwave-studio-0.2.22.0
cp -a "$chipwave_directory/squashfs-root/." /usr/local/lib/chipwave-studio-0.2.22.0/
chown -R root:root /usr/local/lib/chipwave-studio-0.2.22.0
find /usr/local/lib/chipwave-studio-0.2.22.0 -type d -exec chmod 0755 {} +
rm -rf "$chipwave_directory"
rm -f "$chipwave_download"

tiny_lv2_binary="$(mktemp)"
g++ -O2 -pipe -std=c++17 $(pkg-config --cflags lilv-0 suil-0 libpulse-simple x11) \
  "$script_dir/tiny-lv2/temporaman-lv2.cpp" -o "$tiny_lv2_binary" \
  $(pkg-config --libs lilv-0 suil-0 libpulse-simple x11)
install -o root -g root -m 0755 "$tiny_lv2_binary" /usr/local/bin/temporaman-lv2
rm -f "$tiny_lv2_binary"

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

helio_archive="$(mktemp)"
helio_directory="$(mktemp -d)"
curl -fsSL https://ci.helio.fm/helio-3.18-x64.tar.gz -o "$helio_archive"
printf '%s  %s\n' '23f224cd01bc171705d605c757125f89ed9971a658627f00bf80fdb28865fb6a' "$helio_archive" | sha256sum -c -
tar -xzf "$helio_archive" -C "$helio_directory"
install -o root -g root -m 0755 "$helio_directory/helio" /usr/local/bin/helio
rm -f "$helio_archive"
rm -r "$helio_directory"

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
