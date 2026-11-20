# FigSynth2

This directory contains the complete local FigLib v52 program plus a small
instrument front-end designed for Temporaman.

The main screen is intentionally short: make a synth sound or load a sample,
play it from the on-screen/computer keyboard, shape it with knobs, and save a
WAV to a location chosen in the standard file dialog. The Effects screen provides a searchable,
ordered, bypassable rack backed by all 91 entries in FigLib's
`EFFECT_DISPATCH`. FigLib's genre presets, FX recipes, oscillators, routing,
modulation, CLI, scripting engine, IDE modules, examples, and documentation are
kept under `figlib52/`.

The Effects tab includes four assignable live macros. Choose M1–M4 beside any
numeric effect parameter, then turn that macro while audio is streaming. The
low-latency audition path swaps its processed cache in place; **Export audio** still
uses FigLib's complete offline-quality rack.

Computer keys use the usual two-row layout: `Z` through `M` and `Q` through `I`.
The octave selector transposes that keyboard. In Chord shape mode, clicking any
key places the selected shape at that root. In Custom chord mode, keyboard notes
toggle into or out of the selection, including notes retained across octave
changes. The latest auditioned selection is what **Export audio** writes as WAV or MP3.

Right-click any knob in **Shape the sample**, choose an enabled effect, then
choose one of its numeric parameters to assign it. Choose **Default** from the
same menu to restore the knob's normal function. Base Shape knobs update the
currently playing preview as they move.
