# FigSynth2

This directory contains the complete local FigLib v52 program plus a small
instrument front-end used by Temporaman and runnable on its own.

The main screen is intentionally short: make a synth sound or load a sample,
play it from the on-screen/computer keyboard, shape it with knobs, and save a
WAV to a location chosen in the standard file dialog. The Effects screen provides a searchable,
ordered, bypassable rack backed by all 92 entries in FigLib's
`EFFECT_DISPATCH`. FigLib's genre presets, FX recipes, oscillators, routing,
modulation, CLI, scripting engine, IDE modules, examples, and documentation are
kept under `figlib52/`.

Computer keys use the usual two-row layout: `Z` through `M` and `Q` through `I`.
The octave selector transposes that keyboard. In Chord shape mode, clicking any
key places the selected shape at that root. In Custom chord mode, keyboard notes
toggle into or out of the selection, including notes retained across octave
changes. The latest auditioned selection is what **Export audio** writes as WAV or MP3.

Right-click any knob in **Shape the sample**, choose an enabled effect, then
choose one of its numeric parameters to assign it. Choose **Default** from the
same menu to restore the knob's normal function. Base Shape knobs update the
currently playing preview as they move.

Use **Save patch…** to store the current sound as a versioned `.fig` file.
**Load patch…** restores oscillators, the effect rack and parameters, Shape
values, effect assignments, trim and LFO settings, or the referenced sample.
Sample audio is referenced rather than embedded so patch files remain small.

## Source layout

`figlib-sampler.py` remains the executable entry point and application
coordinator. Reusable behavior lives in the `figsynth/` package:

- `audio_logic.py` handles rendering, PulseAudio playback, and WAV/MP3 export.
- `effect_rack.py`, `knob.py`, and `waveform.py` contain the active UI widgets.
- `music.py` and `parameters.py` contain pure definitions and value mappings.
- `patches.py` reads, validates, writes, and applies `.fig` patch files.
- `piano_roll.py` and `piano_logic.py` retain the disabled piano-roll feature
  outside the active application file so it can be restored without rebuilding it.

Install and run:

```bash
python3 -m pip install -r figlib52/requirements.txt
python3 figlib-sampler.py
```

PulseAudio/PipeWire playback and `ffmpeg` for MP3 export are optional system
dependencies. On a standalone machine, set `TEMPORAMAN_IMPORTS`,
`TEMPORAMAN_EXPORTS`, and `TEMPORAMAN_PATCHES` to writable directories.

Run the headless characterization suite after changing these boundaries:

```bash
python3 -m unittest discover -s tests -v
```
