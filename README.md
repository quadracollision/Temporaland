# Temporaman Shrine

Temporaman Shrine is a shared browser-accessible Linux music workspace. It
runs native audio applications on the server and exposes one collaborative
desktop through noVNC, with streamed PulseAudio output, sample transfer, chat,
colored cursors, and optional control handoff. It does not reimplement
Audacity.

The active lightweight deployment lives under [`xpra/`](xpra/README.md). Its
Ubuntu 24.04 installer configures Audacity, FigSynth2, Hydrogen, Shuriken,
SunVox, OpenRB-338, Nginx, systemd services, persistent project storage, and
the browser UI.

```bash
sudo ./xpra/install-lightweight-studio.sh
./scripts/validate-repository.sh
./scripts/build-release.sh
```

Passwords are generated at install time or read from an external file; they
are not stored in the repository. The current release is recorded in
[`CHANGELOG.md`](CHANGELOG.md). Release procedure and security checks are in
[`docs/releasing.md`](docs/releasing.md).

The Kasm material below is retained as an alternative architecture for a
larger host.

Kasm already supplies the missing framework around Audacity:

- a web login and user accounts;
- an official browser-accessible Audacity container (`kasmweb/audacity`);
- audio streaming from Audacity to each browser;
- browser-to-workspace file upload and download;
- session links that authenticated collaborators can join;
- shared mouse and keyboard control for the same Audacity process;
- isolated Docker workspaces and optional persistent profiles.

The result is literally one copy of Audacity with two people connected to the same desktop. It is remote co-control, not Google-Docs-style conflict-free editing: both users share one pointer, one keyboard focus, and Audacity's single undo history.

## Recommended proof of concept

1. Provision one Ubuntu 24.04 or 22.04 server with Docker support. Start with 4 CPU cores, 8 GB RAM, 100+ GB SSD, and low network latency to both musicians. Current Kasm minimums are 2 cores, 4 GB RAM, and 75 GB SSD, but the Audacity session and existing workloads need headroom.
2. Run `./scripts/check-host.sh`, then install the no-cost Kasm Workspaces Community Edition with `scripts/install-kasm-host.sh`.
3. In the Kasm admin UI, install Audacity from the official first-party Workspace Registry. The current deployment guide is pinned to Kasm 1.19.0.
4. Create two named Kasm users. Do not put a second basic-auth proxy in front of Kasm; Kasm itself is the login boundary.
5. In the users' Group Settings, enable:
   - `allow_kasm_sharing: true`
   - `shared_session_full_control: true`
   - `allow_kasm_audio: true`
   - `allow_kasm_uploads: true`
   - `allow_kasm_downloads: true`
   - `allow_persistent_profile: true`
6. Give the workspace a persistent profile or persistent storage mapping for Audacity projects and imported media.
7. User A launches Audacity, opens the Kasm control panel, selects **Share Instance**, and sends the generated URL to User B.
8. User B signs in, follows the URL, and joins the same running Audacity process.

The exact admin steps are in [`docs/configure-kasm.md`](docs/configure-kasm.md). After installation, run `./scripts/verify-kasm-host.sh`, then validate the real two-user experience with [`docs/pilot-checklist.md`](docs/pilot-checklist.md).

Repository-only checks can be run at any time with `./scripts/validate-repository.sh`.


## File workflow

Use Kasm's upload control to place WAV/MP3/project files in the session's upload directory, then open or import them from Audacity. For reliable projects, map a durable host or object-backed folder into the workspace and save the `.aup3` project plus exports there. Set storage quotas and a retention policy before inviting more users.

Do not open arbitrary host directories to the container. Treat uploaded audio as untrusted input, restrict accepted file sizes, and keep Audacity/Kasm images patched.

## Why Kasm instead of BoxedWine

Audacity has a native Linux build, so running the Windows build through Wine or BoxedWine adds an extra compatibility layer without helping collaboration. Kasm's Audacity image runs the actual application in Linux and streams its display and audio to a browser. Use Wine only if a required Windows-only plug-in cannot be replaced and survives testing in the container.

## Important limitations to test first

- **Control collisions:** both people can type or move the pointer at once. In practice, use a “driver/navigator” convention and verbally hand off control.
- **Monitoring latency:** remote playback is suitable for editing and review, not synchronized live performance or overdubbing. Record locally and upload takes.
- **Microphone routing:** browser microphone pass-through is not a substitute for a low-latency local DAW recording path.
- **Audio quality:** test Kasm's stream quality with representative sessions and headphones before choosing hosting.
- **Session access:** a shared-session URL may be usable by any authenticated Kasm user who knows it. Keep the user group private and stop sharing when finished.

## Production shape

```text
Browser A ─┐
           ├─ HTTPS ─ Kasm login/session service ─ one Audacity container
Browser B ─┘                                      └─ persistent project storage
```

For the first version, use Kasm's own UI rather than building a custom login site. A branded portal can be added later through Kasm's API/SSO, after the shared Audacity interaction has proven usable.

## Go/no-go test

Before building anything custom, run one 60-minute session with two users and verify:

- both accounts can join the same session;
- both can take control and edit;
- both hear playback acceptably;
- each can upload an audio file;
- the `.aup3` project survives logout/restart;
- an export can be downloaded;
- the experience is usable at each participant's real network latency.

If that test succeeds, the remaining work is ordinary hosting, branding, storage, backups, and access policy. If simultaneous control is too awkward, no wrapper will fix that; the next step would be a collaboration-aware DAW rather than Audacity.
