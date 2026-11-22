# Temporaman Shrine lightweight Audacity studio

Temporaman Shrine runs one native Audacity session at <https://margeux.com/temporaman/>. The authenticated workspace is `/temporaman/shrine.html`. noVNC carries the screen and shared controls. A small authenticated WebSocket carries raw stereo audio from a PulseAudio virtual output, avoiding a separate media server.

```text
browser ──HTTPS── nginx ── noVNC/websockify ── x11vnc ── shared music apps
   │                   └── login, uploads, app launch, PCM audio
   └── Listen button                                      ▲
                                                 PulseAudio “Temporaman”
```

## Using the studio

Log in with the studio password, then click **Listen** in the top bar. Browser autoplay rules require this click before sound can play. Audacity starts with `Temporaman` as its default playback device; if it was changed, select it under **Audio Setup → Playback Device**.

To record an interface connected to your computer, click **Input → Connect to Audacity** in the studio toolbar and grant browser audio access. In Audacity, choose **Transport → Rescan Audio Devices**, then select the device name shown in the Input dialog under **Audio Setup → Recording Device**. Keep the studio tab open while recording. This workflow was tested in Chrome. Shared **Listen** playback stays available to everyone.

Click **Upload samples** to add WAV, MP3, FLAC, Ogg, Opus, AIFF, M4A, CAF, or AU files. In Audacity, use **File → Import → Audio** and browse to `/srv/audacity-studio/imports`.

Audacity includes the **PeteShift** macro-effect by Jacob Pereira. Draw a time
selection showing the exact desired output length over an audio clip, then run
**Tools → PeteShift**. PeteShift finds and processes the complete source clip,
so a selection shorter than the clip compresses it without cutting its tail.
**Keep pitch** uses Audacity's tempo stretcher; **Tape speed** changes duration
and pitch together.

The installer also supplies a broad LV2 effects collection for Audacity's
realtime effects rack: LSP, x42, Calf, Guitarix, SWH, Invada, EQ10Q, and MDA.
Together these cover EQ and filters, compression and limiting, gates, delays,
reverbs, modulation, saturation and distortion, guitar processing, stereo
tools, metering, and creative utilities. Audacity must rescan plug-ins once
after an upgrade; an installed plug-in uses working memory only when loaded.

The fixed application and transfer icons in the bottom bar launch or focus Audacity, SunVox, FigSynth2, Shuriken, Hydrogen, OpenRB-338, the audio downloader, the sample uploader, and the browser file exporter. The application launchers use their original artwork; FigSynth2 uses the supplied fig icon. The right arrow lists audio in the shared imports and exports folders and downloads the selected file to the visitor's own computer. These icons remain in place when an application is closed. Closing a window terminates its process and releases its working memory; clicking the fixed icon starts one fresh instance. Running applications also have ordinary task buttons to the right of the fixed icons for minimizing and restoring their windows.

Hydrogen starts in its compact tabbed layout with its PulseAudio driver connected to Temporaman. Use **Project → Export Song** and choose **Documents → Hydrogen → Audacity imports** to render a pattern or song for Audacity. The optional large drumkit bundle is not installed.

Shuriken imports audio with **Ctrl+I**, detects onset or beat slice points, and commits them with **Slice**. Use **Ctrl+E**, set the output directory to `/srv/audacity-studio/imports`, and enter a folder name. It exports the individual WAV slices into that folder for Audacity to import.

The blue download icon opens a small native frontend for the open-source `yt-dlp` program. Paste a YouTube link, choose MP3, WAV, or FLAC, and click **Download audio**. Single videos up to two hours are saved directly into `/srv/audacity-studio/imports`; playlists and livestreams are disabled. Only download media that you own, have permission to copy, or that is licensed for reuse.

The bottom-bar **↑** asks the browser that currently has control to show an upload dialog. Its **Choose file** button opens that visitor's local file picker and uploads one audio sample of up to 10 MB directly into the shared imports folder.

The orange sun taskbar icon opens SunVox, a compact modular synthesizer and pattern-based tracker. It includes built-in synth and effect modules, automation, sample playback, microtonal sequencing, and multitrack WAV export. Save projects under **Documents → SunVox → Projects** and export finished audio through **Documents → SunVox → Audacity imports** so Audacity can import it directly. Closing its window exits the process and releases its memory; clicking the fixed icon starts it again.

The fig icon opens FigSynth2. Its Instrument tab makes the complete FigLib v52 engine quick to use: generate or load a sound, play it chromatically, shape it with clear knobs, and export WAV or MP3 through a standard file picker. **Loop playback × N** plays a note, chord, or completed arpeggio for `N` total passes; `0` loops until **Stop**. The arpeggiator works with a named chord or custom chord: choose the chord, enable **Arpeggiator**, click **Set note order**, then click highlighted piano keys in the desired order. Repeated notes are allowed, and **Play arpeggio** and audio export use that exact order and step length. Arpeggio export uses the same loop count; infinite (`0`) playback exports one pass. Its Effects tab provides a searchable rack containing all 92 FigLib effects and the bundled FX presets. The effect named **Sidechain pump (simulated)** is timed volume ducking; it has no external kick/key input. Oscillators can be edited and removed directly, with a lightweight waveform view for the selected source; loaded audio appears as a sample oscillator. Right-clicking a Shape knob opens an enabled Effect → Parameter assignment menu. **Save patch…** and **Load patch…** store reusable `.fig` files containing the complete sound configuration, including arpeggiator settings.

The OpenRB-338 icon opens the stock drum machine with its original sounds available. **Mods → FigLib Kit…** opens an OpenRB-owned editor with 45 drum slots plus **303 A sample oscillator** and **303 B sample oscillator**. Assign saved `.fig` patches to any slots and build **FigLib Generated**; unassigned devices retain their stock sounds. Drum slots preserve a patch's saved root/arpeggio performance. A 303 assignment renders one C4 sample, loops it as that 303's oscillator, and pitch-shifts it with the sequencer. The existing tune, cutoff, resonance, envelope modulation, decay, accent, and slide controls continue processing it. An active FigLib kit reloads automatically after a rebuild, so adding another assignment no longer leaves OpenRB playing the previous version. **Open FigSynth2** starts the normal, unchanged FigSynth2 editor for designing and saving patches; the kit integration itself lives under OpenRB and does not add controls to FigSynth2.

The **Chat** panel lets each visitor set a nickname and cursor color. It includes persistent chat history and live colored cursor presence. When control is open, everyone may interact with the studio. A visitor can deliberately take exclusive control; if somebody else then clicks the studio, its controller is asked to hand it over and can accept or keep control. Releasing control or disconnecting returns the studio to open interaction.

After taking control, focus a text field in the shared desktop and click **Paste** in the top bar to send text or a copied link from the local device into it. Clipboard access requires a click because browsers do not allow websites to read the system clipboard silently. If clipboard permission is unavailable, Temporaman shows a small paste prompt instead.

Projects and exports persist under `/srv/audacity-studio/projects` and `/srv/audacity-studio/exports`. The collaboration sidecar stores chat history in `/srv/audacity-studio/collab.sqlite3`.

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
