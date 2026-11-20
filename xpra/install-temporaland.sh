#!/usr/bin/env bash
set -euo pipefail

# Clone the currently installed Temporaman runtime into a fully isolated
# Temporaland workspace without interrupting the original desktop.

if [[ "$(id -u)" -ne 0 ]]; then
  printf 'Run as root.\n' >&2
  exit 77
fi

land_home=/srv/temporaland
land_runtime=/run/temporaland
land_config=/etc/temporaland
land_web=/var/www/temporaland

if ! id -u temporaland >/dev/null 2>&1; then
  useradd --system --home-dir "$land_home" --shell /usr/sbin/nologin \
    --groups audio temporaland
fi

install -d -o temporaland -g temporaland -m 0750 \
  "$land_home" "$land_home/imports" "$land_home/exports" \
  "$land_home/projects" "$land_home/Documents" "$land_home/.config"
install -d -o root -g temporaland -m 0750 "$land_config"
install -d -o root -g root -m 0755 "$land_web"

if [[ ! -s "$land_config/password" ]]; then
  umask 0027
  if [[ -n "${TEMPORALAND_PASSWORD_FILE:-}" ]]; then
    if [[ ! -s "$TEMPORALAND_PASSWORD_FILE" ]]; then
      printf 'TEMPORALAND_PASSWORD_FILE does not name a readable, non-empty file.\n' >&2
      exit 66
    fi
    install -o root -g temporaland -m 0640 \
      "$TEMPORALAND_PASSWORD_FILE" "$land_config/password"
  elif [[ -n "${TEMPORALAND_PASSWORD:-}" ]]; then
    printf '%s\n' "$TEMPORALAND_PASSWORD" > "$land_config/password"
  else
    openssl rand -base64 24 | tr -d '\n' > "$land_config/password"
  fi
fi
chown root:temporaland "$land_config/password"
chmod 0640 "$land_config/password"

if [[ -f /srv/audacity-studio/.asoundrc ]]; then
  install -o temporaland -g temporaland -m 0644 \
    /srv/audacity-studio/.asoundrc "$land_home/.asoundrc"
fi

ln -sfn "$land_home/imports" "$land_home/Documents/Audacity imports"
ln -sfn "$land_home/imports" "$land_home/Documents/Helio to Audacity"
ln -sfn "$land_home/imports" "$land_home/Documents/Hydrogen to Audacity"

sed \
  -e 's#/srv/audacity-studio#/srv/temporaland#g' \
  -e 's#/run/audacity-studio#/run/temporaland#g' \
  -e 's#DISPLAY=:100#DISPLAY=:101#g' \
  -e 's#PULSE_SINK=studio#PULSE_SINK=land#g' \
  -e 's#audacity-studio#temporaland#g' \
  -e 's#audacity-studio-open-app#temporaland-open-app#g' \
  -e 's#temporaman-downloader#temporaland-downloader#g' \
  -e 's#temporaman-dl#temporaland-dl#g' \
  /usr/local/libexec/audacity-studio-open-app > /usr/local/libexec/temporaland-open-app
sed -i '/export LIBGL_ALWAYS_SOFTWARE=1/a export TEMPORAMAN_IMPORTS=/srv/temporaland/imports\nexport TEMPORAMAN_EXPORTS=/srv/temporaland/exports' \
  /usr/local/libexec/temporaland-open-app
chmod 0755 /usr/local/libexec/temporaland-open-app

sed \
  -e 's#/srv/audacity-studio#/srv/temporaland#g' \
  -e 's#/run/audacity-studio#/run/temporaland#g' \
  -e 's#/etc/audacity-studio/tint2rc#/etc/temporaland/tint2rc#g' \
  -e 's#:100#:101#g' \
  -e 's#X100#X101#g' \
  -e 's#sink_name=studio#sink_name=land#g' \
  -e 's#set-default-sink studio#set-default-sink land#g' \
  -e 's#studio.monitor#land.monitor#g' \
  -e 's#PULSE_SINK=studio#PULSE_SINK=land#g' \
  -e 's#Temporaman#Temporaland#g' \
  -e 's#audacity-studio-open-app#temporaland-open-app#g' \
  -e 's#audacity-studio-web#temporaland-web#g' \
  -e 's#5900#5901#g' \
  -e 's#14500#14600#g' \
  /usr/local/libexec/audacity-studio-launch > /usr/local/libexec/temporaland-launch
chmod 0755 /usr/local/libexec/temporaland-launch

sed \
  -e 's#/etc/audacity-studio#/etc/temporaland#g' \
  -e 's#/srv/audacity-studio#/srv/temporaland#g' \
  -e 's#temporaman_session#temporaland_session#g' \
  -e 's#/temporaman#/temporaland#g' \
  -e 's#studio.monitor#land.monitor#g' \
  -e 's#Temporaman#Temporaland#g' \
  -e 's#14501#14601#g' \
  /usr/local/libexec/audacity-studio-web > /usr/local/libexec/temporaland-web
chmod 0755 /usr/local/libexec/temporaland-web

sed \
  -e 's#audacity-studio-open-app#temporaland-open-app#g' \
  -e 's#14503#14603#g' \
  -e 's#Temporaman#Temporaland#g' \
  /usr/local/libexec/audacity-studio-apps > /usr/local/libexec/temporaland-apps
sed -i 's#{"/helio": "helio", "/downloader": "downloader"}#{"/downloader": "downloader"}#' \
  /usr/local/libexec/temporaland-apps
chmod 0755 /usr/local/libexec/temporaland-apps

sed \
  -e 's#/srv/audacity-studio#/srv/temporaland#g' \
  -e 's#Temporaman#Temporaland#g' \
  -e 's#14502#14602#g' \
  /usr/local/libexec/audacity-studio-collab > /usr/local/libexec/temporaland-collab
chmod 0755 /usr/local/libexec/temporaland-collab

sed \
  -e 's#/srv/audacity-studio#/srv/temporaland#g' \
  -e 's#temporaman-chrome#temporaland-chrome#g' \
  -e 's#temporaman-dl#temporaland-dl#g' \
  -e 's#Temporaman#Temporaland#g' \
  /usr/local/libexec/temporaman-downloader > /usr/local/libexec/temporaland-downloader
chmod 0755 /usr/local/libexec/temporaland-downloader

rm -rf "$land_web"
cp -a /var/www/temporaman "$land_web"
find "$land_web" -type f \( -name '*.html' -o -name '*.js' -o -name '*.md' \) -print0 | \
  xargs -0 sed -i \
    -e 's#/temporaman#/temporaland#g' \
    -e 's#path=temporaman/#path=temporaland/#g' \
    -e 's#temporaman_#temporaland_#g' \
    -e 's#Temporaman#Temporaland#g'
find "$land_web" -type f -name '*.html' -print0 | \
  xargs -0 sed -i 's/TemporalandCollab.mount({/TemporalandCollab.mount({exclusiveControl:false,/'
sed -i \
  -e 's#<h1>Temporaland Shrine</h1>#<h1>Temporaland: shared music workspace for laughs</h1>#' \
  -e 's#<button type="submit">Temporaland Shrine</button>#<button type="submit">Enter</button>#' \
  -e '/<\/style>/i\    body{background:#ececec;background-image:none;color:#222;font:14px Arial,sans-serif}.page{width:380px;margin:12vh auto 20px}.window{background:#fff;border:1px solid #999;box-shadow:2px 2px 0 #bbb}.titlebar,hr{display:none}.content{padding:28px}h1{margin:0 0 22px;color:#222;font:bold 21px Arial,sans-serif;text-shadow:none;line-height:1.35}.notice{display:none}form{margin:0 auto}input{padding:9px;border:1px solid #888;font:16px Arial,sans-serif}button{padding:8px 18px;background:#ddd;border:1px solid #777;font:bold 14px Arial,sans-serif}' \
  "$land_web/login.html"
chown -R root:root "$land_web"

for source in /usr/local/share/applications/temporaman-*.desktop; do
  name="$(basename "$source")"
  target="/usr/local/share/applications/${name/temporaman-/temporaland-}"
  sed \
    -e 's#audacity-studio-open-app#temporaland-open-app#g' \
    -e 's#temporaman-downloader#temporaland-downloader#g' \
    -e 's#127.0.0.1:14502#127.0.0.1:14602#g' \
    -e 's#Temporaman#Temporaland#g' \
    "$source" > "$target"
  chmod 0644 "$target"
done
rm -f /usr/local/share/applications/temporaland-helio.desktop \
  /usr/local/share/applications/temporaland-chipwave.desktop
cp -f /usr/local/share/icons/temporaman-downloader.svg \
  /usr/local/share/icons/temporaland-downloader.svg

sed \
  -e 's#temporaman-#temporaland-#g' \
  /etc/audacity-studio/tint2rc > "$land_config/tint2rc"
sed -i -E '/temporaland-(helio|chipwave)\.desktop/d' "$land_config/tint2rc"
chmod 0644 "$land_config/tint2rc"

sed \
  -e 's#Two-player Audacity#Temporaland Audacity#g' \
  -e 's#User=audacity-studio#User=temporaland#g' \
  -e 's#Group=audacity-studio#Group=temporaland#g' \
  -e 's#/srv/audacity-studio#/srv/temporaland#g' \
  -e 's#/run/audacity-studio#/run/temporaland#g' \
  -e 's#RuntimeDirectory=audacity-studio#RuntimeDirectory=temporaland#g' \
  -e 's#audacity-studio-launch#temporaland-launch#g' \
  /etc/systemd/system/audacity-studio.service > /etc/systemd/system/temporaland.service
# Xvfb must create /tmp/.X11-unix/X101 alongside the existing X100 socket.
sed -i '/^PrivateTmp=true$/d' /etc/systemd/system/temporaland.service

sed \
  -e 's#Temporaman#Temporaland#g' \
  -e 's#audacity-studio.service#temporaland.service#g' \
  -e 's#User=audacity-studio#User=temporaland#g' \
  -e 's#Group=audacity-studio#Group=temporaland#g' \
  -e 's#/srv/audacity-studio#/srv/temporaland#g' \
  -e 's#/run/audacity-studio#/run/temporaland#g' \
  -e 's#DISPLAY=:100#DISPLAY=:101#g' \
  -e 's#PULSE_SINK=studio#PULSE_SINK=land#g' \
  -e 's#audacity-studio-apps#temporaland-apps#g' \
  /etc/systemd/system/audacity-studio-apps.service > /etc/systemd/system/temporaland-apps.service

sed \
  -e 's#Temporaman#Temporaland#g' \
  -e 's#audacity-studio.service#temporaland.service#g' \
  -e 's#User=audacity-studio#User=temporaland#g' \
  -e 's#Group=audacity-studio#Group=temporaland#g' \
  -e 's#/srv/audacity-studio#/srv/temporaland#g' \
  -e 's#audacity-studio-collab#temporaland-collab#g' \
  /etc/systemd/system/audacity-studio-collab.service > /etc/systemd/system/temporaland-collab.service

# Treat the two studios as separate security boundaries. Temporaland keeps its
# own writable state and cannot even read Temporaman's home, configuration,
# runtime sockets, or web files.
for unit in temporaland.service temporaland-apps.service temporaland-collab.service; do
  if ! grep -q '^InaccessiblePaths=' "/etc/systemd/system/$unit"; then
    sed -i '/^ReadWritePaths=/a InaccessiblePaths=/srv/audacity-studio /etc/audacity-studio /var/www/temporaman /run/audacity-studio /root /home /etc/ssh /etc/ssl/private /etc/nginx /etc/systemd' \
      "/etc/systemd/system/$unit"
  fi
done

sed \
  -e 's#/temporaman#/temporaland#g' \
  -e 's#/var/www/temporaman#/var/www/temporaland#g' \
  -e 's#14500#14600#g' \
  -e 's#14501#14601#g' \
  -e 's#14502#14602#g' \
  -e 's#14503#14603#g' \
  /etc/nginx/snippets/margeux-temporaman.conf > /etc/nginx/snippets/margeux-temporaland.conf

for config in /etc/nginx/sites-available/margeux /etc/nginx/sites-enabled/margeux; do
  [[ -f "$config" ]] || continue
  include_line='    include /etc/nginx/snippets/margeux-temporaland.conf;'
  if ! grep -qxF "$include_line" "$config"; then
    sed -i "/include \/etc\/nginx\/snippets\/margeux-temporaman.conf;/a\\$include_line" "$config"
  fi
done

chown -R temporaland:temporaland "$land_home"
systemctl daemon-reload
nginx -t
systemctl enable --now temporaland.service temporaland-apps.service temporaland-collab.service
systemctl reload nginx

printf 'Temporaland installed at https://margeux.com/temporaland/\n'
printf 'Password is stored in %s (existing passwords are preserved).\n' "$land_config/password"
