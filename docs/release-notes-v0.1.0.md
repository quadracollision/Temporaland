# Temporaman Shrine v0.1.0

Temporaman Shrine is a browser-accessible shared Linux music workspace. One
server-side desktop runs Audacity and lightweight music tools while multiple
authenticated visitors share its screen, streamed audio, chat, cursors, sample
transfer, and optional exclusive-control handoff.

## Highlights

- Audacity, FigSynth2, Hydrogen, Helio, Shuriken, and ChipWave launch inside one
  noVNC desktop.
- FigSynth2 exposes the FigLib v52 oscillator engine, 91-effect rack, assignable
  Shape macros, chord keyboard, realtime auditioning, reset-to-factory behavior,
  and WAV/MP3 export.
- PeteShift 2.0 by Jacob Pereira fits the complete clip under a time selection
  to that selection's duration. It supports pitch-preserving tempo change and
  tape-speed pitch movement, including shrinking without cutting the clip.
- Curated realtime LV2 effects from LSP, x42, Calf, Guitarix, SWH, Invada,
  EQ10Q, and MDA provide EQ, dynamics, delay, reverb, modulation, saturation,
  guitar processing, stereo tools, meters, and creative effects.
- Authenticated upload and download flows move samples between a visitor's
  computer and the shared imports/exports folders.
- Persistent chat, nicknames, colored cursors, open control, and optional
  request/grant exclusive control.
- Browser audio starts automatically when browser policy permits and resumes
  after interruptions.
- Systemd sandboxing, generated deployment credentials, and an optional fully
  isolated second workspace installer.

## Requirements

- Ubuntu 24.04 (Noble), installed as root.
- A DNS name with HTTPS termination in Nginx.
- At least 2 GB RAM is recommended for the lightweight workspace and its music
  applications.

## Install

```bash
tar -xzf temporaman-shrine-v0.1.0.tar.gz
cd temporaman-shrine-v0.1.0
sudo ./xpra/install-lightweight-studio.sh
```

The installer generates the initial studio password when none exists. It does
not embed a deployment password in the release.

## PeteShift

After installation or upgrade, rescan Audacity plug-ins once. PeteShift appears
under **Tools → PeteShift**. Draw a time selection over a clip to describe the
desired output duration, then choose **Keep pitch** or **Tape speed**. PeteShift
processes the complete clip even when the target selection is shorter.

## Known limitations

- This is a shared remote desktop, not a conflict-free collaborative DAW. All
  visitors share the applications, projects, pointer state, and undo history.
- Remote audio is intended for composition, editing, and review rather than
  low-latency live performance or overdubbing.
- Browser autoplay rules may require one interaction before audio begins.
- PeteShift expects one clear source clip under the selection start; overlapping
  clips can make the intended source ambiguous.
- The repository does not yet declare a project-wide license. Bundled third-party
  material retains its own license. Choose a project license before describing
  the GitHub repository as open source.

## Verification

```bash
sha256sum -c temporaman-shrine-v0.1.0.tar.gz.sha256
./scripts/validate-repository.sh
```

The release archive deliberately excludes deployment passwords, session
cookies, SSH keys, chat databases, server backups, uploaded media, and generated
project/export files.
