# Uploading this folder to GitHub

Upload the **contents** of the `temporaman-shrine` folder as the repository
root. Do not upload its parent `github-upload` folder.

The repository contains the complete Ubuntu 24.04 installer, web interface,
systemd and Nginx configuration, Audacity PeteShift plug-in, FigSynth2 and
FigLib sources, launchers, validation scripts, and deployment documentation.
The installer downloads Ubuntu packages and pinned third-party application
builds, so the target server requires internet access during installation.

After cloning the repository onto an Ubuntu 24.04 server:

```bash
./scripts/validate-repository.sh
sudo ./xpra/install-lightweight-studio.sh
```

No deployment password, cookie, SSH key, uploaded sample, chat database, or
server backup is included. The installer generates a password when necessary.

This project does not yet declare a repository-wide license. Keep the GitHub
repository private, or choose and add an appropriate project license before
describing it as open source. Bundled third-party material retains its own
license.
