# Changelog

## 0.1.0 - 2026-11-19

First GitHub-ready release of the lightweight shared music workspace.

- Browser-hosted Linux audio desktop using noVNC, Xvfb, PulseAudio, and Nginx.
- Browser listening starts automatically and retries/resumes after browser
  autoplay blocking; FigSynth2 follows each workspace's configured Pulse sink.
- Audacity, FigSynth2, Hydrogen, Shuriken, sample upload/download, chat, cursors,
  and streamed desktop audio.
- FigSynth2 instrument, oscillator, 91-effect rack, assignable macros, realtime
  auditioning, and WAV save dialog.
- Optional isolated Temporaland deployment with a distinct Unix user, display,
  PulseAudio sink, ports, storage, browser profile, chat database, and session
  cookie.
- Temporaland uses simultaneous open control, a minimal login page, and excludes
  Helio and ChipWave.
- FigSynth2 omits the resource-heavy piano roll. Shape knobs expose an Effect →
  Parameter assignment menu and update active previews audibly. Reset
  Defaults clears assignments and restores every Shape knob and related state.
- Installer passwords are generated or supplied at deployment time and are not
  embedded in the repository.
- Systemd sandboxing hides the other studio and sensitive host configuration
  from Temporaland processes.
- Adds Jacob Pereira's PeteShift 2.0 Audacity macro-effect. The time selection
  is the target size: PeteShift finds the complete underlying clip and grows or
  shrinks it without cutting audio, with keep-pitch and tape-speed modes.
- Prevents a slow or stale collaboration WebSocket from blocking presence and
  chat updates for every other visitor.
