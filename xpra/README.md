# Temporaman Shrine lightweight Audacity studio

Temporaman Shrine runs one native Audacity session at <https://margeux.com/temporaman/>. The authenticated workspace is `/temporaman/shrine.html`. noVNC carries the screen and shared controls. A small authenticated WebSocket carries raw stereo audio from a PulseAudio virtual output, avoiding a separate media server.

```text
browser ──HTTPS── nginx ── noVNC/websockify ── x11vnc ── Audacity + Helio
   │                   └── login, uploads, app launch, PCM audio
   └── Listen button                                      ▲
                                                 PulseAudio “Temporaman”
```

## Using the studio

Log in with the studio password, then click **Listen** in the top bar. Browser autoplay rules require this click before sound can play. Audacity starts with `Temporaman` as its default playback device; if it was changed, select it under **Audio Setup → Playback Device**.

Click **Upload samples** to add WAV, MP3, FLAC, Ogg, Opus, AIFF, M4A, CAF, or AU files. In Audacity, use **File → Import → Audio** and browse to `/srv/audacity-studio/imports`.

Audacity includes the **PeteShift** macro-effect by Jacob Pereira. Draw a time
selection showing the exact desired output length over an audio clip, then run
**Tools → PeteShift**. PeteShift finds and processes the complete source clip,
so a selection shorter than the clip compresses it without cutting its tail.
**Keep pitch** uses Audacity's tempo stretcher; **Tape speed** changes duration
and pitch together.

The **H** taskbar icon opens Helio in the same shared desktop as Audacity. The launcher permits exactly one Helio process for the studio; pressing the icon again does not create another instance. Helio provides the piano roll and hosts the installed LV2 instruments, including synthv1, padthv1, samplv1, SO Synths, and MDA instruments.

Render a pattern from Helio to WAV and choose **Documents → Helio → Audacity imports** as the destination. The WAV then appears in Audacity's import folder without being downloaded to the visitor's computer. Helio and Audacity share the same `Temporaman` PulseAudio output, so the browser's **Listen** button carries playback from either app.

The fixed **A**, **H**, **S**, **H₂**, blue **↓**, blue **↑**, and blue **→** icons in the bottom bar launch or focus Audacity, Helio, Shuriken, Hydrogen, the audio downloader, the sample uploader, and the browser file exporter. The right arrow lists audio in the shared imports and exports folders and downloads the selected file to the visitor's own computer. These icons remain in place when an application is closed. Closing a window terminates its process and releases its working memory; clicking the fixed icon starts one fresh instance. Running applications also have ordinary task buttons to the right of the fixed icons for minimizing and restoring their windows.

Hydrogen starts in its compact tabbed layout with its PulseAudio driver connected to Temporaman. Use **Project → Export Song** and choose **Documents → Hydrogen → Audacity imports** to render a pattern or song for Audacity. The optional large drumkit bundle is not installed.

Shuriken imports audio with **Ctrl+I**, detects onset or beat slice points, and commits them with **Slice**. Use **Ctrl+E**, set the output directory to `/srv/audacity-studio/imports`, and enter a folder name. It exports the individual WAV slices into that folder for Audacity to import.

The blue download icon opens a small native frontend for the open-source `yt-dlp` program. Paste a YouTube link, choose MP3, WAV, or FLAC, and click **Download audio**. Single videos up to two hours are saved directly into `/srv/audacity-studio/imports`; playlists and livestreams are disabled. Only download media that you own, have permission to copy, or that is licensed for reuse.

The bottom-bar **↑** asks the browser that currently has control to show an upload dialog. Its **Choose file** button opens that visitor's local file picker and uploads one audio sample of up to 10 MB directly into the shared imports folder.

The orange waveform taskbar icon opens ChipWave Studio, the primary lightweight synth and pattern editor. It provides a piano roll, built-in WaveForge/FM/analog/chip synths, per-parameter modulation, effects, arrangement, and WAV/MP3 rendering. Closing its window exits the process and releases its memory; clicking the icon starts it again. Export finished samples to `/srv/audacity-studio/imports` so Audacity can import them directly.

The gray-and-green waveform icon opens FigSynth2. Its Instrument tab makes the complete FigLib v52 engine quick to use: generate or load a sound, play it chromatically, shape it with clear knobs, and export WAV or MP3 through a standard file picker. Its Effects tab provides a searchable rack containing all 91 FigLib effects and the bundled FX presets. Oscillators can be edited directly. Right-clicking a Shape knob opens an enabled Effect → Parameter assignment menu.

The **Chat** panel lets each visitor set a nickname and cursor color. It includes persistent chat history and live colored cursor presence. When control is open, everyone may interact with the studio. A visitor can deliberately take exclusive control; if somebody else then clicks the studio, its controller is asked to hand it over and can accept or keep control. Releasing control or disconnecting returns the studio to open interaction.

After taking control, focus a text field in the shared desktop and click **Paste** in the top bar to send text or a copied link from the local device into it. Clipboard access requires a click because browsers do not allow websites to read the system clipboard silently. If clipboard permission is unavailable, Temporaman shows a small paste prompt instead.

Projects and exports persist under `/srv/audacity-studio/projects` and `/srv/audacity-studio/exports`. The collaboration sidecar stores chat history in `/srv/audacity-studio/collab.sqlite3`.

## Isolated Temporaland workspace

Run `install-temporaland.sh` only after the base workspace is installed. It
creates a second service set at `/temporaland/` with a distinct Unix user,
home, display, VNC and HTTP ports, PulseAudio sink, cookie, browser profile,
chat database, imports, exports, and projects. The two workspaces do not share
user files. Sensitive host configuration and Temporaman's paths are hidden
from Temporaland by the systemd sandbox.

Supply an initial password through a root-readable file:

```bash
sudo TEMPORALAND_PASSWORD_FILE=/root/temporaland-password ./install-temporaland.sh
```

If no password file or `TEMPORALAND_PASSWORD` value is provided, the installer
generates a random password in `/etc/temporaland/password`. Existing passwords
are preserved. Temporaland deliberately has simultaneous open control and does
not expose ownership controls. Its smaller launcher excludes Helio and
ChipWave.

## Operations

```bash
systemctl status audacity-studio
journalctl -u audacity-studio -f
systemctl restart audacity-studio
systemctl status audacity-studio-apps
systemctl restart audacity-studio-apps
systemctl status audacity-studio-collab
sudo /usr/local/sbin/audacity-studio-password
```

The unit is limited to 700 MB RAM and 85% of one CPU to protect the other services on the host.
