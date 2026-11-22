# Changelog

## Unreleased

- Connect a local audio interface from the studio toolbar and select its named
  recording device in Audacity. Shared playback uses the existing Listen stream.
- Add a 12-band graphic EQ with vertical faders to FigSynth2.

## 0.1.0 - 2026-11-19

First GitHub-ready release of the lightweight shared music workspace.

- Browser-hosted Linux audio desktop using noVNC, Xvfb, PulseAudio, and Nginx.
- Browser listening starts automatically and retries/resumes after browser
  autoplay blocking; FigSynth2 follows each workspace's configured Pulse sink.
- Audacity, FigSynth2, Hydrogen, Shuriken, sample upload/download, chat, cursors,
  and streamed desktop audio.
- FigSynth2 instrument, oscillator, 91-effect rack, assignable macros, realtime
  auditioning, and WAV save dialog.
- FigSynth2 omits the resource-heavy piano roll. Shape knobs expose an Effect →
  Parameter assignment menu and update active previews audibly. Reset
  Defaults clears assignments and restores every Shape knob and related state.
- Installer passwords are generated or supplied at deployment time and are not
  embedded in the repository.
- Adds Jacob Pereira's PeteShift 2.0 Audacity macro-effect. The time selection
  is the target size: PeteShift finds the complete underlying clip and grows or
  shrinks it without cutting audio, with keep-pitch and tape-speed modes.
- Prevents a slow or stale collaboration WebSocket from blocking presence and
  chat updates for every other visitor.
- Adds curated realtime LV2 effect suites: LSP, x42, Calf, Guitarix, SWH,
  Invada, and EQ10Q alongside the existing MDA collection.
- Refactors FigSynth2 into focused modules and adds reusable, versioned `.fig`
  patch files for oscillators, effects, assignments, Shape values, and samples.
- Removes the retired Temporaland installer, WebSynth, and Tiny-LV2 launcher.
- Replaces ChipWave with the official SunVox 2.1.4d Linux build and adds
  persistent project and Audacity-import shortcuts for SunVox exports.
- Removes Helio and uses the original SunVox application artwork for its
  taskbar launcher.
- Fixes oscillator removal in FigSynth2, represents loaded audio as a sample
  oscillator, and shows the selected oscillator's waveform in its editor.
- Uses one shared lightweight waveform renderer for both the Instrument and
  Oscillators tabs.
- Dismisses the Shape-knob assignment menu whenever the user clicks elsewhere
  in FigSynth2.
- Adds OpenRB-338 with an OpenRB-owned FigLib kit builder. The builder assigns
  unchanged `.fig` patches to any of the 45 playable drum slots, pre-renders every
  assigned source, packs a real `.rbm`, and keeps the stock kit available.
- Adds a shared FigSynth2 playback-loop count for live notes, chords, and
  arpeggios plus arpeggio export, with `0` meaning infinite live playback and
  one exported pass, and adds Stop.
  Adds a chord/custom-chord arpeggiator whose clicked key order, repeated notes,
  step length, playback, export, and `.fig` persistence all agree.
- Identifies FigLib's clocked ducking effect as **Sidechain pump (simulated)**;
  it has no external kick/key input.
- Replaces placeholder application launchers with their original icons and uses
  the supplied fig artwork for FigSynth2.
- Keeps Oscillator-tab knob dragging responsive by updating a 20 ms lightweight
  source thumbnail in place and debouncing the heavier Instrument/audio refresh;
  the editor no longer destroys and recreates controls during a drag.
- Alternates the internal OpenRB FigLib-kit `.rbm` path after each successful
  build so Refresh List plus reselecting FigLib Generated reloads new samples
  instead of OpenRB treating the active path as an unchanged kit.
- Renders OpenRB FigLib drum slots from a patch's saved root note and
  arpeggiator order instead of a hardcoded C4, and normalizes generated samples
  to a consistent drum-kit level.
- Adds optional FigSynth2 sample oscillators for both OpenRB-338 TB-303s. The
  sequencer pitches and slides the looping C4 sample while the existing 303
  accent, filter, resonance, envelope modulation, and decay stages remain live.
- Reloads an active FigLib mod automatically when the builder atomically
  replaces it, fixing later assignments being hidden behind the previous kit.
