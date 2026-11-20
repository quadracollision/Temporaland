# pySynth – The FiggyGen

## Automated Synthesizer & Sample Generator

## Automated Synthesizer & Sample Generator

A Python-based synthesizer engine with **91 audio effects**, **50+ oscillator types** (including classic drums & percussion), hardware emulations, intelligent genre-based randomization, **Round Robin** variations, **Wavetable Export**, and a powerful CLI.

---

## Quick Start

```bash
# Install dependencies
pip install numpy scipy soundfile

# Generate 10 random samples
python run.py

# Generate 20 pad sounds
python run.py --count 20 --genre pad --note C4

# Generate a 4-chord progression with 5 variations
python run.py --progression "C4E4G4|A3C4E4|F3A3C4|G3B3D4" --passes 5

# Run a batch script (new!)
python run.py examples/demo.psy
```

**[📖 Read the Scripting Guide](SCRIPTING_GUIDE.md)** for detailed instructions on creating `.psy` files.

---

## CLI Reference

### Core Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `--count` | int | 10 | Number of samples to generate |
| `--out` | string | `./samples` | Output directory |
| `--note` | string | `C4` | Note or chord (see Note Formats below) |
| `--duration` | float | 2.0 | Duration per sample in seconds |
| `--genre` | string | random | Genre preset: `bass`, `pad`, `lead`, `fx`, `keys`, `perc` |

### Chord Progression Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `--progression` | string | — | Chord progression separated by `\|` |
| `--passes` | int | 5 | Number of parameter variations per progression |

### FX Filtering Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `--fx-list` | flag | — | Print all available effects and exit |
| `--fx-only` | string | — | Comma-separated: use ONLY these effects |
| `--fx-include` | string | — | Comma-separated: always include these effects |
| `--fx-exclude` | string | — | Comma-separated: never use these effects |

---

## Note Formats

The `--note` argument accepts multiple formats:

| Format | Example | Result |
|---|---|---|
| Single note | `C4` | 261.63 Hz |
| Concatenated chord | `C4E4G4` | C major triad |
| Space-separated | `"C4 E4 G4"` | C major triad |
| Sharps | `F#4` or `C#3` | F#4, C#3 |
| Flats | `Bb3` or `Eb4` | Bb3, Eb4 |
| Raw frequency | `440` | 440 Hz |
| Complex chord | `C4E3F#4G3` | Four-note voicing |

---

## Genre Presets

Each genre preset controls oscillator selection, filter probability, effect pool, and reverb/delay likelihood.

### `bass`
Deep, heavy sounds. Prioritizes saw/square oscillators with lowpass filtering. Effects lean toward distortion, compression, and sub-bass enhancement. Low reverb probability.

```bash
python run.py --genre bass --note C2 --count 20
```

**Typical effects:** `moog`, `303`, `distortion`, `tube`, `compressor`, `sub_bass`, `wavefolder`, `1176`, `warmth`, `maximizer`, `multiband`

### `pad`
Lush, atmospheric textures. Multiple oscillators with wide unison and high detune. Heavy reverb and delay. Effects focus on spatial processing and modulation.

```bash
python run.py --genre pad --note C4E4G4 --count 20 --duration 4.0
```

**Typical effects:** `chorus`, `shimmer`, `dimension`, `emt_plate`, `lexicon`, `granular`, `spectral_freeze`, `stereo_imager`, `dimension_d`, `width_enhance`

### `lead`
Cutting, expressive sounds. Saw/square oscillators with moderate unison. Balanced reverb/delay. Effects emphasize distortion, filtering, and pitch processing.

```bash
python run.py --genre lead --note C4 --count 20
```

**Typical effects:** `moog`, `303`, `distortion`, `h3000`, `vox`, `wasp`, `1176`, `harmonic_enhance`, `parallel_comp`

### `fx`
Experimental, textural sounds. Uses noise oscillators, morphing waveforms, and unusual filter types. Heavy on creative and destructive effects.

```bash
python run.py --genre fx --note C3 --count 20 --duration 3.0
```

**Typical effects:** `bitcrush`, `glitch`, `reverse`, `granular`, `spectral_freeze`, `wasp`, `ams_reverb`, `buchla_lpg`, `doppler`

### `keys`
Clean, musical keyboard sounds. Sine/triangle oscillators with subtle unison. Moderate effects focusing on warmth and space.

```bash
python run.py --genre keys --note C4E4G4B4 --count 20
```

**Typical effects:** `chorus`, `tremolo`, `tape`, `dimension_d`, `fender_twin`, `warmth`, `body`, `pultec`, `stereo_imager`

### `perc`
Punchy, transient-heavy percussive sounds. Noise and sine oscillators. Effects emphasize dynamics and impact.

```bash
python run.py --genre perc --note C3 --count 20 --duration 0.5
```

**Typical effects:** `distortion`, `transient`, `gate`, `1176`, `parallel_comp`, `multiband`, `maximizer`, `ams_reverb`

---

## Chord Progressions

Generate all chords in a progression with **identical synth parameters per pass**. Every chord in a single pass shares the same oscillators, effects, and settings — perfect for song construction.

```bash
# Classic I-vi-IV-V in C major, 5 variations
python run.py --progression "C4E4G4|A3C4E4|F3A3C4|G3B3D4" --passes 5

# Minor progression with pads
python run.py --progression "A3C4E4|F3A3C4|D3F3A3|E3G#3B3" \
    --passes 10 --genre pad --duration 4.0

# Jazz voicings
python run.py --progression "C4E4G4B4|F4A4C5E5|Bb3D4F4A4|Eb4G4Bb4D5" \
    --passes 3 --genre keys
```

**Output files:** `beast_prog_p01_c01_pad_saw.wav`, etc. — `p` = pass number, `c` = chord number.

---

## FX Filtering

### `--fx-list` — Browse Available Effects

```bash
python run.py --fx-list
```

Prints all 91 effects organized by category:

| Category | Count | Effects |
|---|---|---|
| **Filters** | 11 | `filter`, `comb`, `formant`, `moog`, `303`, `sem`, `ms20`, `prophet`, `juno_hpf`, `obxa`, `wasp` |
| **Distortion** | 4 | `distortion`, `bitcrush`, `tube`, `wavefolder` |
| **Amps** | 3 | `marshall`, `vox`, `fender_twin` |
| **Modulation** | 12 | `chorus`, `flanger`, `phaser`, `tremolo`, `vibrato`, `autopan`, `ce1`, `small_stone`, `re301`, `dimension`, `ensemble`, `dimension_d` |
| **Delay/Echo** | 3 | `delay`, `space_echo`, `tc2290` |
| **Reverb** | 5 | `reverb`, `emt_plate`, `spring`, `lexicon`, `ams_reverb` |
| **Dynamics** | 12 | `compressor`, `limiter`, `fairchild`, `ssl`, `dbx160`, `la2a`, `1176`, `gate`, `transient`, `maximizer`, `multiband`, `parallel_comp` |
| **EQ/Preamp** | 4 | `neve`, `pultec`, `exciter`, `harmonic_enhance` |
| **Tape** | 2 | `tape`, `studer` |
| **Pitch** | 4 | `pitch_shift`, `harmonizer`, `octaver`, `h3000` |
| **Stereo/Space** | 10 | `stereo_widen`, `haas`, `ring_mod`, `freq_shift`, `arp_ring`, `sidechain`, `dc_remove`, `stereo_imager`, `width_enhance`, `spatial` |
| **Creative** | 19 | `lofi`, `stutter`, `sub_bass`, `reverse`, `tape_stop`, `vinyl`, `radio`, `telephone`, `underwater`, `shimmer`, `glitch`, `doppler`, `crystal`, `fade`, `resonator`, `buchla_lpg`, `granular`, `spectral_freeze`, `granular_stretch` |
| **Mastering** | 2 | `warmth`, `body` |

### `--fx-only` — Restrict to Specific Effects

Use ONLY the listed effects, ignoring the genre pool entirely.

```bash
# Only Moog filter and reverb
python run.py --fx-only moog,reverb --genre bass --count 10

# Only tape and compression
python run.py --fx-only studer,1176,fairchild --count 10

# Minimal: just warmth and body
python run.py --fx-only warmth,body --count 10
```

### `--fx-include` — Force Effects Into Every Patch

These effects will **always** appear in the FX chain, in addition to the randomly selected genre effects.

```bash
# Every sample gets Fairchild compression + plate reverb
python run.py --fx-include fairchild,emt_plate --genre pad --count 20

# Always add warmth and stereo imaging
python run.py --fx-include warmth,stereo_imager --count 20
```

### `--fx-exclude` — Remove Effects From Pool

These effects will **never** be selected, even if they're in the genre pool.

```bash
# No distortion or amp effects
python run.py --fx-exclude distortion,marshall,vox --genre lead --count 20

# No reverb-type effects
python run.py --fx-exclude reverb,emt_plate,spring,lexicon,ams_reverb --count 20
```

### Combining Filters

All three filters compose together:

```bash
# Use only analog hardware, always include Neve preamp, never use 303
python run.py --fx-only moog,fairchild,ssl,neve,emt_plate,studer \
    --fx-include neve --fx-exclude 303 --genre pad --count 20
```

---

## Complete Effect Reference

### Filters

| Effect | Model | Key Parameters |
|---|---|---|
| `filter` | Standard SVF | `filter_type`, `cutoff`, `resonance`, `gain_db` |
| `comb` | Comb filter | `delay_ms`, `feedback` |
| `formant` | Vowel formant | `vowel` (a/e/i/o/u) |
| `moog` | Minimoog Ladder (24dB/oct) | `cutoff`, `resonance`, `drive` |
| `303` | TB-303 Diode Ladder | `cutoff`, `resonance`, `env_mod`, `accent`, `decay` |
| `sem` | Oberheim SEM SVF | `cutoff`, `resonance`, `mode` |
| `ms20` | Korg MS-20 Sallen-Key | `cutoff`, `resonance`, `drive` |
| `prophet` | Prophet-5 CEM3320 | `cutoff`, `resonance` |
| `juno_hpf` | Roland Juno-6 HPF | `cutoff`, `resonance` |
| `obxa` | Oberheim OB-Xa CEM3320 | `cutoff`, `resonance`, `mode` |
| `wasp` | EDP Wasp (CMOS digital) | `cutoff`, `resonance` |

### Distortion & Saturation

| Effect | Description | Key Parameters |
|---|---|---|
| `distortion` | Multi-type distortion | `drive`, `type`, `mix` |
| `bitcrush` | Bit depth + sample rate reduction | `bits`, `downsample` |
| `tube` | Tube saturation | `drive`, `asymmetry` |
| `wavefolder` | West-Coast wavefolding | `folds`, `symmetry` |

### Amplifier Emulations

| Effect | Model | Key Parameters |
|---|---|---|
| `marshall` | Marshall JCM800 | `gain`, `tone`, `presence` |
| `vox` | Vox AC30 Top Boost | `gain`, `treble`, `cut` |
| `fender_twin` | Fender Twin Reverb | `volume`, `treble`, `bass`, `reverb_mix` |

### Modulation

| Effect | Model | Key Parameters |
|---|---|---|
| `chorus` | Standard chorus | `rate`, `depth`, `mix` |
| `flanger` | Flanging | `rate`, `depth`, `feedback` |
| `phaser` | Multi-stage phaser | `rate`, `depth`, `stages` |
| `tremolo` | Amplitude modulation | `rate`, `depth` |
| `vibrato` | Pitch modulation | `rate`, `depth` |
| `autopan` | Auto-panning | `rate`, `depth` |
| `ce1` | Boss CE-1 Chorus | `rate`, `depth`, `vibrato_mode` |
| `small_stone` | EHX Small Stone Phaser | `rate`, `color` |
| `re301` | Roland RE-301 Chorus | `rate`, `depth`, `tone` |
| `dimension` | Dimension-style processing | `size`, `mix` |
| `ensemble` | String ensemble | `voices`, `rate`, `depth` |
| `dimension_d` | Roland SDD-320 Dimension D | `mode` (1-4) |

### Delay & Echo

| Effect | Model | Key Parameters |
|---|---|---|
| `delay` | Standard stereo delay | `time`, `feedback`, `mix`, `ping_pong` |
| `space_echo` | Roland RE-201 Tape Echo | `delay_ms`, `feedback`, `wow`, `flutter`, `mix` |
| `tc2290` | TC Electronic 2290 | `time_ms`, `feedback`, `mod_rate`, `mod_depth`, `mix` |

### Reverb

| Effect | Model | Key Parameters |
|---|---|---|
| `reverb` | Algorithmic reverb | `decay`, `mix` |
| `emt_plate` | EMT 140 Plate | `decay`, `damping`, `mix` |
| `spring` | Fender Spring Tank | `decay`, `tone`, `mix` |
| `lexicon` | Lexicon 224 Digital | `decay`, `damping`, `mix` |
| `ams_reverb` | AMS RMX16 | `decay`, `damping`, `program`, `mix` |

### Dynamics

| Effect | Model | Key Parameters |
|---|---|---|
| `compressor` | Standard compressor | `threshold`, `ratio`, `attack`, `release` |
| `limiter` | Brickwall limiter | `ceiling` |
| `fairchild` | Fairchild 670 Vari-mu | `input_gain`, `threshold`, `time_constant` |
| `ssl` | SSL 4000G Bus Comp | `threshold`, `ratio`, `attack`, `release` |
| `dbx160` | DBX 160 VCA Comp | `threshold`, `ratio` |
| `la2a` | Teletronix LA-2A Opto | `peak_reduction`, `mode` |
| `1176` | UREI 1176 FET Limiter | `input_gain`, `ratio`, `attack`, `release` |
| `gate` | Noise gate | `threshold`, `attack`, `release` |
| `transient` | Transient shaper | `attack`, `sustain` |
| `maximizer` | Loudness maximizer | `ceiling`, `warmth`, `release_ms` |
| `multiband` | 3-band multiband comp | `low_thresh`, `mid_thresh`, `high_thresh`, `crossover_low`, `crossover_high` |
| `parallel_comp` | New York compression | `threshold`, `ratio`, `mix` |

### EQ & Preamp

| Effect | Model | Key Parameters |
|---|---|---|
| `neve` | Neve 1073 Preamp | `drive`, `hf_boost`, `hf_freq` |
| `pultec` | Pultec EQP-1A | `low_boost`, `low_atten`, `low_freq`, `high_boost`, `high_atten`, `high_freq` |
| `exciter` | Aural exciter | `amount`, `freq` |
| `harmonic_enhance` | Harmonic generator | `low_harmonics`, `high_harmonics`, `air` |

### Tape

| Effect | Model | Key Parameters |
|---|---|---|
| `tape` | Standard tape emulation | `drive`, `wow`, `flutter`, `hiss` |
| `studer` | Studer A800 2-inch | `input_level`, `speed`, `bias` |

### Pitch

| Effect | Description | Key Parameters |
|---|---|---|
| `pitch_shift` | Pitch shifter | `semitones`, `fine_cents` |
| `harmonizer` | Intelligent harmonizer | `interval`, `mix` |
| `octaver` | Octave generator | `octave_down`, `octave_up`, `mix` |
| `h3000` | Eventide H3000 Micropitch | `detune_cents`, `delay_ms`, `mix` |

### Stereo & Spatial

| Effect | Description | Key Parameters |
|---|---|---|
| `stereo_widen` | Stereo width | `width` |
| `haas` | Haas effect | `delay_ms` |
| `ring_mod` | Ring modulator | `freq`, `depth` |
| `freq_shift` | Frequency shifter | `shift_hz` |
| `arp_ring` | ARP 2600 Ring Mod | `freq`, `depth`, `diode_curve` |
| `sidechain` | Sidechain ducking | `rate`, `depth` |
| `dc_remove` | DC offset removal | — |
| `stereo_imager` | Mid/Side imaging | `width`, `bass_mono_freq` |
| `width_enhance` | Freq-dependent width | `low_width`, `high_width`, `crossover` |
| `spatial` | 3D positioning | `room_size`, `position`, `height` |

### Creative & Sound Design

| Effect | Description | Key Parameters |
|---|---|---|
| `lofi` | Lo-fi degradation | `bits`, `noise`, `filter_cutoff` |
| `stutter` | Buffer stutter | `rate`, `chance`, `gate` |
| `sub_bass` | Sub-bass generator | `octaves_down`, `mix` |
| `reverse` | Reverse audio | — |
| `tape_stop` | Tape stop slowdown | `speed`, `duration` |
| `vinyl` | Vinyl crackle | `crackle`, `dust`, `wow` |
| `radio` | Radio tuning effect | `freq`, `static` |
| `telephone` | Phone filter | `quality` |
| `underwater` | Underwater muffling | `depth`, `bubbles` |
| `shimmer` | Octave-up reverb | `shift`, `feedback`, `mix` |
| `glitch` | Buffer glitch | `density`, `length`, `reverse_prob` |
| `doppler` | Doppler fly-by | `speed`, `distance` |
| `crystal` | Crystalline shimmer | `shimmer`, `brightness` |
| `fade` | Fade in/out | `fade_in`, `fade_out` |
| `resonator` | Resonant body | `freq`, `decay` |
| `buchla_lpg` | Buchla 292 LPG | `strike`, `decay`, `resonance`, `mode` |
| `granular` | Granular cloud | `grain_ms`, `density`, `spray`, `pitch_spread` |
| `spectral_freeze` | Spectral freeze | `freeze_pos`, `sustain`, `mix` |
| `granular_stretch` | Time stretch | `rate`, `grain_ms` |

### Mastering

| Effect | Description | Key Parameters |
|---|---|---|
| `warmth` | Analog warming | `amount` |
| `body` | Acoustic body resonance | `size`, `tone`, `mix` |

---

## Example Workflows

### Song Production

```bash
# 1. Generate a pad progression
python run.py --progression "C4E4G4|A3C4E4|F3A3C4|G3B3D4" \
    --passes 5 --genre pad --duration 4.0 --out song/pads

# 2. Generate bass lines for the same chords
python run.py --progression "C2|A1|F2|G2" \
    --passes 5 --genre bass --duration 4.0 --out song/bass

# 3. Generate lead melodies
python run.py --count 20 --genre lead --note C4 \
    --fx-include h3000,warmth --out song/leads

# 4. Generate percussion
python run.py --count 30 --genre perc --duration 0.5 \
    --fx-include 1176 --out song/perc
```

### Sound Design Exploration

```bash
# Extreme granular textures
python run.py --count 10 --genre fx --fx-only granular,spectral_freeze,shimmer \
    --duration 5.0 --out sounds/textures

# Pure analog warmth
python run.py --count 20 --fx-only moog,fairchild,studer,neve,warmth \
    --genre pad --out sounds/analog

# Aggressive industrial
python run.py --count 20 --fx-only wasp,ms20,marshall,bitcrush,1176 \
    --genre lead --out sounds/industrial

# Clean and pristine
python run.py --count 20 --fx-exclude distortion,bitcrush,wavefolder,marshall,vox \
    --genre keys --out sounds/clean
```

### Targeted Effect Testing

```bash
# Test a specific effect in isolation
python run.py --count 5 --fx-only moog --note C4 --out test/moog
python run.py --count 5 --fx-only dimension_d --note C4E4G4 --out test/dimension

# Compare compressor characters
python run.py --count 5 --fx-only fairchild --out test/fairchild
python run.py --count 5 --fx-only ssl --out test/ssl
python run.py --count 5 --fx-only 1176 --out test/1176
python run.py --count 5 --fx-only la2a --out test/la2a
python run.py --count 5 --fx-only dbx160 --out test/dbx160
```

---

## Architecture

```
pySynth/
├── run.py                          # Entry point
└── src/pySynth/
    ├── main.py                     # CLI argument parsing + routing
    ├── synth.py                    # FiggyGenSynth engine + EFFECT_DISPATCH (91 effects)
    ├── oscillator.py               # Oscillator engine (31 waveform types)
    ├── envelope.py                 # DAHDSR envelope generator
    ├── modulation.py               # LFO (9 shapes) + modulation matrix
    ├── generator.py                # Randomizer + SampleGenerator + genre presets
    └── effects/
        ├── ... (effect modules)
```

---

## Oscillator & Modulation Engine

The synth engine has been massively upgraded with **31 oscillator types** and a dedicated modulation system.

### Oscillator Types
| Category | Waveforms | Description |
|---|---|---|
| **Analog** | `saw`, `square`, `pulse`, `triangle`, `sine`, `morph`, `supersaw` | Classic waveforms. `supersaw` is a 7-voice stereo detuned saw (JP-8000 style). |
| **Digital** | `wavetable`, `fm_op`, `additive`, `sync`, `pwm_sweep`, `harsh`, `chip` | `wavetable` scans 8 frames. `fm_op` is 2-op FM. `additive` uses 8 harmonics. `chip` is 8-bit quantized. |
| **Physical** | `pluck`, `strings`, `brass`, `organ`, `bell`, `glass` | Karplus-Strong pluck, bowed strings, drawbar organ, inharmonic bells. |
| **Textural** | `vocal`, `breath`, `pad_wash`, `click` | `vocal` is a formant morpher (ah-eh-ee-oh-oo). `pad_wash` is 5-voice sine unison. |
| **Percussive** | `kick`, `snare`, `hat` | Synthesized drum sounds (TR-808 style pitch sweeps, filtered noise). |
| **Noise** | `noise_white`, `noise_pink`, `noise_brown`, `noise_blue`, `noise_purple` | 5 colors of noise for texture and percussion. |

### Modulation
- **LFOs**: 9 shapes including `sample_hold` (stepped random), `random_walk` (drift), `exp_rise/fall`.
- **Targets**: LFOs can modulate **Pitch** (vibrato/FM), **Filter Cutoff** (wobble/sweep), and **Amplitude** (tremolo).
- **Envelopes**: Genre-aware DAHDSR envelopes (Delay-Attack-Hold-Decay-Sustain-Release) are randomized per patch.


