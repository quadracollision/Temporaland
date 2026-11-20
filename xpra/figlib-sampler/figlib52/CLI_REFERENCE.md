# figlib CLI Reference & Examples

Full documentation for **figlib** (The FiggyGen) audio engine.

> **(C) Quadracollision 2026**

## Quick Reference

| Command | Description |
|---|---|
| `--count N` | Generate N samples (default: 10) |
| `--out DIR` | Output directory (default: ./samples) |
| `--duration SEC` | Length in seconds (default: 2.0) |
| `--note NOTE` | Frequency/Note/Chord to play |
| `--genre GENRE` | 30 presets (see [Genre Presets](#genre-presets) below) |
| `--progression STR` | Chord progression string separated by `\|` |
| `--bus BUS` | Define a parallel bus: `'id:oscs>fx'` |
| `--loop` | Adjust duration for perfect integer-cycle loops |
| `--zeroc` | Apply fade-in/out to prevent clicks |
| `--fx-only LIST` | Force ONLY these effects |
| `--fx-include LIST` | Always add these effects |
| `--fx-exclude LIST` | Never use these effects |
| `--osc-only LIST` | Force ONLY these oscillators/drums |
| `--osc-include LIST` | Add oscillators to pool |
| `--osc-exclude LIST` | Remove oscillators from pool |
| `--lfo-rate MIN,MAX` | Force LFO rate range (Hz) |
| `--lfo-depth MIN,MAX` | Force LFO depth range (0-1) |
| `--fxpreset NAME` | Use FX-only preset (e.g. `tape_warmth`) |
| `--scale STR` | Scale name (`major`) or intervals (`0,2,4,7`) |
| `--seed INT` | Random seed for deterministic output |
| `--round-robin` | Generate variations of a base patch (Drift) |
| `--macro STR` | Macro Mod config: `rate=0.5,depth=1.0,targets=...` |
| `--wavetable` | Export 64-frame 2048-sample wavetable |
| `--sample FILE` | Process a single `.wav` sample |
| `--sample-folder DIR` | Process all `.wav` files in a folder (recursive) |
| `--destructive` | Overwrite original files when processing samples |
| `--copy` | Save processed samples to `--out` dir (default) |
| `--list` | List all available oscillators, FX, scales |
| `--nitro FOLDER` | Convert folder to DS format (16k/Mono) |
| `file.psy` | Run a script file (see below) |
| `--info NAME` | Show info (params) for a specific effect |
| `--osc-list` | List all available oscillators |
| `--repl` | Launch interactive REPL mode |

---

## Interactive Mode

When you launch figlib with no arguments (or `--repl`), it opens an interactive dual-mode session:

```
  __ _       _ _ _
 / _(_) __ _| (_) |__
| |_| |/ _` | | | '_ \
|  _| | (_| | | | |_) |
|_| |_|\__, |_|_|_.__/
       |___/
    (C) Quadracollision 2026

Mode: REPL (scripting). Type 'help' for commands.
Type 'cli' to switch to CLI arg mode, 'exit' to quit.

FG>
```

### REPL Mode (`FG>` prompt)
The scripting language — same syntax as `.psy` script files:

```
FG> set genre pad
FG> set note C4E4G4
FG> set count 5
FG> generate
FG> set fxpreset tape_warmth
FG> generate
FG> state               # show current settings
FG> help                # show all commands
```

### CLI Mode (`CLI>` prompt)
Type `cli` to switch. Use full `--arg` style commands:

```
FG> cli
[Switched to CLI mode]
CLI> --genre bass --note C2 --count 10
CLI> --genre pad --fxpreset ethereal --count 5
CLI> --list
CLI> --help             # show all flags
CLI> repl               # switch back to REPL mode
```

### Mode Switching
| Command | Action |
|---------|--------|
| `cli` | Switch from REPL to CLI mode |
| `repl` | Switch from CLI to REPL mode |
| `help` / `--help` / `-h` | Show help for current mode |
| `exit` / `quit` | Exit the session |

---

## Scripting (.psy files)

You can chain multiple generation commands in a single file using `.psy` scripts.

**Usage:** `python run.py my_script.psy`

**Script Syntax:**
```text
# Comments start with #
set out ./my_bank
set duration 2.0

# Batch 1: Bass
set genre bass
set note C2
set fx-include distortion(drive=0.5)
generate 10

# Batch 2: Pads
set genre pad
set note C4E4G4
generate 5
```

**Commands:**
*   `set [key] [value]` – Update a setting (see table below)
*   `generate [count]` – Run batch generation
*   `progression "A|B|C"` – Run progression generation

**Supported `set` keys:**

| Key | Value | Example |
|---|---|---|
| `out` | Output directory | `set out ./my_bank` |
| `note` | Note/chord string | `set note C4E4G4` |
| `genre` | Genre preset name | `set genre kick` |
| `duration` | Seconds (float) | `set duration 0.5` |
| `count` | Number of samples | `set count 20` |
| `passes` | Progression passes | `set passes 5` |
| `loop` | Perfect loop (`true`/`false`) | `set loop true` |
| `zeroc` | Zero-crossing fade (`true`/`false`) | `set zeroc true` |
| `round-robin` | Round-robin mode (`true`/`false`) | `set round-robin true` |
| `seed` | Random seed (int) | `set seed 42` |
| `scale` | Scale quantization | `set scale minor` |
| `fx-only` | Force specific FX | `set fx-only moog,tube` |
| `fx-include` | Add mandatory FX | `set fx-include warmth` |
| `fx-exclude` | Ban specific FX | `set fx-exclude reverb` |
| `osc-only` | Force oscillators | `set osc-only kick_808` |
| `osc-include` | Add oscillators | `set osc-include sine` |
| `osc-exclude` | Ban oscillators | `set osc-exclude noise_white` |
| `lfo-rate` | LFO rate range (Hz) | `set lfo-rate 0.1,2.0` |
| `lfo-depth` | LFO depth range (0-1) | `set lfo-depth 0.5,1.0` |
| `fxpreset` | Use FX-only preset | `set fxpreset glitch` |
| `macro` | Macro mod config | `set macro rate=0.5,depth=1.0,...` |
| `wavetable` | Wavetable export (`true`/`false`) | `set wavetable true` |
| `sample` | Process a single `.wav` file | `set sample ./my_sample.wav` |
| `sample-folder` | Process all `.wav` in folder | `set sample-folder ./folder` |
| `destructive` | Overwrite originals (`true`/`false`) | `set destructive true` |
| `nitro` | Convert folder to DS format | `set nitro ./folder` |

## Basic Generation

### Single Notes
```bash
# Launch interactive mode (default behavior)
python run.py

# Or use CLI args directly:

# Generate 50 bass samples at C2
python run.py --genre bass --note C2 --count 50

# Generate 20 percussive hits (general)
python run.py --genre perc --duration 0.5 --count 20

# Generate 10 808 kicks
python run.py --genre kick --duration 1.0 --count 10

# Generate snares with reverb
python run.py --genre snare --duration 0.5 --count 10

# Generate hi-hats
python run.py --genre hat --duration 0.3 --count 10

# Full drum kit batch
python run.py --genre kick --count 10 --out ./kit/kicks
python run.py --genre snare --count 10 --out ./kit/snares
python run.py --genre hat --count 10 --out ./kit/hats
python run.py --genre clap --count 10 --out ./kit/claps
python run.py --genre rim --count 5 --out ./kit/rims
python run.py --genre tom --count 5 --out ./kit/toms
python run.py --genre ride --count 5 --out ./kit/rides
```

### Chords & Polyphony
The engine treats all input as polyphonic.

```bash
# Basic C Major triad
python run.py --genre keys --note C4E4G4

# Space-separated syntax (same result)
python run.py --genre pad --note "C4 E4 G4"

# Complex voicing (Cm9)
python run.py --genre pad --note "C3 G3 Eb4 Bb4 D5"

# Raw frequencies
python run.py --note "440 550 660"
```

---

## Genre Presets

Each genre selects specific oscillators, envelopes, and effects.

| Genre | Character | Oscillators Used |
|---|---|---|
| | **Original** | |
| **bass** | Monophonic, heavy, filtered | SuperSaw, FM Op, Saw, Square, Organ, Brass |
| **pad** | Polyphonic, slow attack, spacious | Wavetable, Additive, Strings, Vocal, Pad Wash |
| **lead** | Monophonic, aggressive, cutting | Sync, PWM Sweep, Brass, Harsh, Saw |
| **keys** | Polyphonic, pluck/decay dynamics | Pluck, Bell, Glass, Organ, Electric Piano |
| **fx** | Experimental, noise-based, glitchy | Chip, Breath, Click, Harsh, FM Op |
| **perc** | General percussion, all types | Kick, Snare, Hat, Click, Noise (all machines) |
| | **Drum Kit** | |
| **kick** | Sub-heavy kicks, long boom | kick_808, kick_909, kick, kick_78, kick_707 |
| **snare** | Tight snares, crackle + body | snare_808, snare_909, snare, snare_78, snare_707 |
| **hat** | Crispy metallic hats | hat_808, hat_909, hat, hat_78, noise |
| **tom** | Pitched toms, resonant decay | tom, kick_808, kick, sine |
| **ride** | Shimmery rides + bells | cymbal_ride, hat_808, hat_909, bell, glass |
| **rim** | Sharp rimshots + woodblocks | rimshot, click, woodblock |
| **clap** | Layered claps + reverb tail | clap, noise_white, snare_808 |
| **perc_fx** | Experimental FX percussion | cowbell, shaker, zap, scratch, impact |
| | **Tonal** | |
| **sub** | Pure sub bass, clean + heavy | sine, triangle |
| **acid** | Squelchy 303 acid lines | saw, square, pulse, pwm_sweep |
| **pluck** | Plucked strings, kalimba, harp | pluck, glass, bell, fm_op, additive |
| **bell** | Bells, chimes, mallets | bell, glass, fm_op, additive |
| **stab** | Punchy chord stabs (house/techno) | saw, square, supersaw, pulse, brass, organ |
| **brass** | Brass stabs + swells | brass, saw, square, pulse, supersaw |
| **strings** | Orchestral string textures | strings, saw, supersaw, pad_wash |
| **organ** | Drawbar/church/electric organ | organ, sine, additive, fm_op |
| **chip** | 8-bit chiptune retro | chip, square, pulse, triangle |
| | **Textural** | |
| **drone** | Dark evolving long textures | drone_dark, pad_wash, saw, supersaw |
| **ambient** | Shimmery spacious pads | pad_wash, wavetable, additive, strings, glass |
| **vocal** | Vocal/choir textures | vocal, breath, pad_wash, additive |
| **noise** | Filtered noise sweeps + textures | noise_white/pink/brown/blue/purple, breath |
| | **Production** | |
| **lofi** | Tape-warped, dusty, warm | saw, sine, pluck, bell, organ, fm_op |
| **cinematic** | Impacts, booms, risers, swells | impact, drone_dark, noise, pad_wash, supersaw |
| **reese** | DnB reese bass, heavy modulation | saw, supersaw, pulse |

---


---

## Bussing & Parallel Chains

Create layered sounds or parallel processing chains using the `--bus` argument.

**Syntax:** `--bus "id:oscillators>effects"`

*   **id**: Unique name for the bus (e.g., `lead`, `bass`).
*   **oscillators**: Comma-separated list of oscillators (e.g., `saw,square`).
*   **effects**: Comma-separated list of effects (e.g., `delay,reverb`) or **FX Presets** (e.g., `tape_warmth`).

> **Pro-Tip:** Use the `rand` keyword for **oscillators** or **effects** to inject procedural variety into your buses:
> `--bus "texture:rand>rand,rand"` (Random oscillators + 2 random effects)

> **FX Presets in Buses:** You can use any FX preset name (e.g., `tape_warmth`, `ethereal`, `glitch`) as an effect in a bus. It will be expanded into its full randomized multi-FX chain.
> `--bus "warm_lead:saw>tape_warmth"`

> **Note:** Buses run in **parallel** and sum to the master output. You can use multiple `--bus` arguments to create complex layers.

### Examples

**1. Basic Split (Lead + Pad)**
`lead` saw with delay, `pad` sine with reverb.
```bash
python run.py --count 1 \
  --bus "lead:saw>delay(time=0.3)" \
  --bus "pad:sine>reverb(mix=0.5)" \
  --note C4
```

**2. Drum Layering**
Distorted kick with clean hi-hats.
```bash
python run.py --count 1 \
  --bus "kick:sine>distortion(drive=0.8),compressor" \
  --bus "hat:noise_white>filter(cutoff=8000,type=highpass)" \
  --note C2
```

**3. Advanced Texture (Drone + Sparkle)**
Deep saw drone with delicate high-end sparkles.
```bash
python run.py --count 1 \
  --bus "drone:saw,saw>filter(cutoff=400),reverb(room_size=0.9)" \
  --bus "sparkle:sine>arpeggiator,delay,shimmer" \
  --note C3
```

---

## Chord Progressions

Generates consistent patches across a sequence of chords.
Each "pass" creates **one** random synthesizer patch, then plays every chord in the progression with that same patch.

```bash
# Classic 4-chord loop (5 variations)
python run.py --progression "C4E4G4|A3C4E4|F3A3C4|G3B3D4" --passes 5

# Jazz ii-V-I with extensions
python run.py --genre keys --passes 10 \
    --progression "D3F3A3C4|G2F3A3B3|C3E3G3B3D4"

# Generative Ambient (Long duration pads)
python run.py --genre pad --duration 8.0 --passes 3 \
    --progression "C3G3E4B4|F3C4A4E5|G3D4B4F#5|A2E3C4G4"
```

**Output Naming:**

Standard: `{number}_{genre}_{oscillator}_{note}.wav`
```
0001_kick_kick_808_C2.wav
0003_pad_breath_C4-E4-G4.wav
RR_0002_bass_supersaw_A1.wav        (round-robin prefix)
```

Progression: `prog_p{pass}_c{chord}_{genre}_{oscillator}_{chord_notes}.wav`
```
prog_p01_c01_pad_wavetable_C4-E4-G4.wav
prog_p01_c02_pad_wavetable_A3-C4-E4.wav
```

---

## FX Filtering & Sound Design

You can override the genre's default effect choices.

### `--fx-only`: Precision Sound Design
Ignores the genre's internal effect pool. Uses **exactly** what you list.

```bash
# Pure Analog Chain: Moog Filter -> Tube Saturation -> Tape
python run.py --genre bass --fx-only moog,tube,studer

# Lo-Fi Texture: Bitcrush -> Vinyl -> Radio
python run.py --genre keys --fx-only bitcrush,vinyl,radio

# Massive Space: Granular -> Spectral Freeze -> Blackhole Reverb
python run.py --genre pad --fx-only granular,spectral_freeze,ams_reverb
```

### `--fx-include`: Mandatory Effects
Adds specific effects to whatever the genre randomizer picks.

```bash
# Force "Warmth" and "Limiter" on everything
python run.py --count 100 --fx-include warmth,1176

# Ensure every pad has stereo widening
python run.py --genre pad --fx-include stereo_imager,width_enhance
```

### `--fx-exclude`: Banned Effects
Prevents specific effects from appearing.

```bash
# Clean sounds only (no distortion/lofi)
python run.py --genre keys --fx-exclude distortion,bitcrush,lofi,glitch

# No reverb/delay (dry samples)
python run.py --fx-exclude reverb,delay,emt_plate,spring,lexicon
# No reverb/delay (dry samples)
python run.py --fx-exclude reverb,delay,emt_plate,spring,lexicon
```

## Advanced Oscillator & Modulation Control

### Oscillator Selection
Control the sound source directly. Useful for sound design or forcing specific drum models.

```bash
# Force 808 Kick and Snare only
python run.py --genre perc --osc-only kick_808,snare_808

# Create a "Super Saw" lead (force super_saw oscillator)
python run.py --genre lead --osc-only super_saw
```

### LFO Overrides
Override the genre's default modulation settings.

```bash
# Slow, deep modulation (e.g. for drones)
python run.py --genre pad --lfo-rate 0.1,0.3 --lfo-depth 0.8,1.0

# Audio-rate modulation (FM-like textures)
python run.py --genre fx --lfo-rate 20,100 --lfo-depth 1.0,1.0
```

### Musical Constraints (Scale & Seed)

```bash
# Quantize random notes to C Minor
python run.py --note "C4 D4 E4 F4" --scale minor

# Deterministic Generation (same output every time)
python run.py --count 1 --seed 12345
```

---

## Round Robin & Macro Modulation

### `--round-robin`
Generates **variations** of a single base patch. The first sample sets the "base" sound, and all subsequent samples in the batch are slight variations (drift) of that base. Ideal for creating multi-sample instruments that sound natural and non-repetitive.

```bash
# Generate 5 variations of a bass patch
python run.py --genre bass --count 5 --round-robin
```

### `--macro`
Applies a master LFO to modulate multiple effects parameters over the course of a batch (or long duration).

**Syntax:** `rate=Hz,depth=0-1,targets=TYPE:PARAM:AMT;TYPE:PARAM:AMT`

> **Note:** You can modulate **any numeric parameter** listed in the [91 Effect Reference](#91-effect-reference) below.
> *   Target must match the **Effect Name** (e.g. `moog`, `delay`).
> *   Param pseudo-match the **Parameter Name** (e.g. `cutoff`, `feedback`).
> *   Non-numeric parameters (modes, types) cannot be modulated.

```bash
# Modulate Filter Cutoff and Distortion Drive over 10 seconds
python run.py --count 20 --macro "rate=0.1,depth=1.0,targets=filter:cutoff:0.5;distortion:drive:0.2"
```

### `--wavetable`
Exports a single-cycle wavetable (64 frames, 2048 samples/frame) for use in synthesizers like Serum or Vital. Forces synthesis of a sweep (morph position) if supported by the oscillator.

```bash
# Export a wavetable from the 'wavetable' oscillator model
python run.py --wavetable --osc-only wavetable --count 1
```

---

---

## Sample Processing

Process existing `.wav` files through FiggyGen's synth engine and FX chain. The loaded sample becomes the primary oscillator — any genre FX, filters, and modulation are layered on top.

### Single File
```bash
# Process one sample, save to output dir
python run.py --sample ./my_sample.wav --genre pad

# Generate 5 variations of the same sample
python run.py --sample ./my_sample.wav --genre lead --count 5
```

### Folder (Recursive)
```bash
# Process all .wav files in a folder
python run.py --sample-folder ./samples/drums --genre perc

# Process folder with specific FX chain
python run.py --sample-folder ./vocals --fx-only "reverb(decay=3.0),delay(time=0.25)"
```

### Destructive Mode
```bash
# Overwrite originals in-place (be careful!)
python run.py --sample-folder ./samples --genre bass --destructive
```

**Output Naming:**

| Mode | Filename |
|---|---|
| Copy (default) | `{original_name}_FX.wav` |
| Copy + multiple | `{original_name}_FX01.wav`, `_FX02.wav`, ... |
| Destructive | Overwrites original filename |

### In Scripts
```text
set sample-folder ./my_samples
set genre pad
generate 3     # 3 variations per sample

# Or destructive:
set destructive true
generate 1
```

### FX Presets (31 total)
Curated FX chains in `fxpresets/` (`.psifx` files). Fully editable JSON.

| Preset | Style |
|--------|-------|
| **Analog & Vintage** | |
| `tape_warmth` | Tube/tape saturation, gentle filtering |
| `vinyl_crunch` | Vinyl degradation, wow/flutter, noise |
| `analog_console` | Studer, Neve, Pultec, Fairchild studio chain |
| `vintage_keys` | Tremolo, spring reverb, tube warmth |
| `vintage_synth` | Moog, Prophet, OBXa with classic chorus |
| `80s_synth` | Chorus, ensemble, dimension, vintage reverbs |
| **Production & Mixing** | |
| `clean_crisp` | Exciter, transient, SSL compression |
| `mastering_chain` | Multiband, SSL, parallel comp, maximizer |
| `drum_bus` | Transient shaping, gating, punchy compression |
| `punch` | Transient shaping and compression for drums |
| `vocal_plate` | Lexicon/EMT plate reverb, subtle chorus |
| `wide_stereo` | Stereo widening, haas, spatial processing |
| `edm_pump` | Sidechain, gating, parallel comp for pumping |
| `heavyweight` | Sub bass, heavy compression, maximizer |
| **Spatial & Atmospheric** | |
| `space_out` | Massive reverb, delay, spectral freeze |
| `dark_ambient` | Deep reverbs, granular stretch, slow LFO |
| `ethereal` | Shimmer, crystal, lush reverbs |
| `dub_delay` | Ping pong, space echo, TC2290, RE-301 |
| `cinematic` | Underwater, doppler, spectral freeze |
| **Lo-Fi & Texture** | |
| `lo_fi` | Vinyl, tape, bitcrush with bandpass filtering |
| `chiptune` | Bitcrush, lo-fi, radio for retro 8-bit |
| `texture` | Granular, spectral freeze, reverse |
| `hiphop_soul` | Vinyl warmth, tape, spring reverb |
| **Aggressive & Experimental** | |
| `destroy` | Aggressive distortion, bitcrushing, wavefolding |
| `industrial` | Heavy distortion, wavefolder, ring mod |
| `glitch` | Stutter, granular, random retriggering |
| `chaos` | Extreme distortion, wavefolder, rapid LFO |
| `acid` | 303/Moog filters, heavy resonance, filter LFO |
| `psychedelic` | Phaser, flanger, freq shift, doppler |
| `metallic` | Comb filters, resonators, ring mod |
| `guitar_amp` | Marshall, Fender Twin, Vox amp models |

```bash
# Apply tape warmth to a folder of drums
python run.py --sample-folder ./raw_drums --fxpreset tape_warmth

# REPL mode
FG> set fxpreset dark_ambient
FG> generate
```

---

## 🔍 Discovery
To see everything FiggyGen can do, use the list command:

```bash
python run.py --list
```

This will output all available:
*   **Genres** (Presets)
*   **Oscillators** (Model names like `kick_808`, `supersaw`, `plucked`)
*   **Effects** (Names like `reverb`, `h3000`, `bitcrush`)
*   **Scales** (Musical scales like `major`, `dorian`)

You can also list specific categories:
```bash
python run.py --fx-list    # List all effects
python run.py --osc-list   # List all oscillators
```

---

## Parametric Control

You can now pass specific parameters to any effect using `name(key=value)` syntax.
Unspecified parameters will still be randomized by the engine.

```bash
# Moog filter with specific cutoff, random resonance
python run.py --fx-only "moog(cutoff=500, drive=0.8)"

# Compresser with slow attack
python run.py --fx-include "compressor(attack=0.1, ratio=4)"

# Complex chain
python run.py --fx-only "lofi(amount=0.8), delay(time=0.5, feedback=0.7), reverb(mix=0.4)"
```

---
## Oscillator Models

You can use these names with `--osc-only` or via scripts.

### Classic Drums
*   **`kick_78`**, **`snare_78`**, **`hat_78`** (CR-78 Style)
*   **`kick_707`**, **`snare_707`** (TR-707 Style)
*   **`kick_808`**, **`snare_808`**, **`hat_808`**, **`cowbell_808`** (TR-808)
*   **`kick_909`**, **`snare_909`**, **`hat_909`** (TR-909)

### Percussion
*   **`clap`** (Handclap ensemble)
*   **`cymbal_crash`**, **`cymbal_ride`**
*   **`tom`**, **`rimshot`**, **`cowbell`**, **`woodblock`**, **`shaker`**

### Tonal & FX
*   **`bass_slap`** (FM Slap Bass)
*   **`piano_electric`** (FM Rhodes)
*   **`drone_dark`** (Detuned Saws + Filter)
*   **`zap`** (Laser sweep)
*   **`scratch`** (Vinyl scratch)
*   **`impact`** (Cinematic boom)

### Genres (Presets)

**Category** | **Presets**
--- | ---
**Drum Kit** | `kick`, `snare`, `hat`, `tom`, `ride`, `rim`, `clap`, `perc_fx`, `crash` (new)
**Tonal** | `sub`, `acid`, `pluck`, `bell`, `stab`, `brass`, `strings`, `organ`, `chip`, `bass`, `pad`, `lead`, `keys`, `arp` (new), `wobble` (new), `growl` (new), `mallet` (new)
**Textural** | `drone`, `ambient`, `vocal`, `noise`, `glitch` (new)
**Transition**| `riser` (new), `downlifter` (new), `impact` (new)
**Production** | `lofi`, `cinematic`, `reese`, `fx`
**General** | `perc` (all-purpose)

### Standard Waveforms & Synthesis
*   **Analog**: `sine`, `square`, `saw`, `triangle`, `pulse`, `morph`
*   **Digital**: `supersaw`, `wavetable`, `fm_op`, `additive`, `pwm_sweep`, `sync`, `harsh`, `chip`
*   **Physical**: `pluck`, `strings`, `brass`, `organ`, `bell`, `glass`
*   **Textural**: `vocal`, `breath`, `pad_wash`
*   **Utility**: `click`, `noise_white`, `noise_pink`, `noise_brown`, `noise_blue`, `noise_purple`

### Generic Percussion (Synthesized)
*   `kick`, `snare`, `hat` (Standard generic approximations)

---

## 91 Effect Reference

### Filters
*   **`filter`** (Standard Biquad) – `cutoff` (Hz), `resonance` (0-1), `gain_db` (-12..12), `filter_type` (lowpass, highpass, bandpass, notch, peaking)
*   **`moog`** (Ladder) – `cutoff` (Hz), `resonance` (0-1), `drive` (0-1)
*   **`303`** (Acid Diode) – `cutoff` (Hz), `resonance` (0-1), `env_mod` (0-1), `decay` (s), `accent` (0-1)
*   **`sem`** (Oberheim) – `cutoff` (Hz), `resonance` (0-1), `mode` (lowpass, highpass, bandpass, notch)
*   **`ms20`** (Korg) – `cutoff` (Hz), `resonance` (0-1)
*   **`prophet`** (Sequential) – `cutoff` (Hz), `resonance` (0-1)
*   **`obxa`** (Oberheim 12dB) – `cutoff` (Hz), `resonance` (0-1)
*   **`wasp`** (EDP Wasp) – `cutoff` (Hz), `resonance` (0-1)
*   **`juno_hpf`** (Roland HPF) – `cutoff` (Hz)
*   **`comb`** – `delay_ms` (1-20), `feedback` (0-0.95)
*   **`formant`** (Vowel) – `vowel` (a, e, i, o, u)

### Dynamics & Mastering
*   **`compressor`** – `threshold` (dB), `ratio` (1-20), `attack` (s), `release` (s), `makeup_gain` (dB)
*   **`limiter`** – `ceiling` (dB), `release` (s)
*   **`gate`** – `threshold` (dB), `attack` (s), `release` (s)
*   **`transient`** – `attack_gain` (>1 boost), `sustain_gain`, `sensitivity`
*   **`multiband`** – `low_cross` (Hz), `high_cross` (Hz), `threshold`, `ratio`
*   **`fairchild`** (Tube Comp) – `input_gain` (dB), `threshold` (0-10), `time_constant` (1-6)
*   **`la2a`** (Opto Comp) – `peak_reduction` (0-10), `gain` (0-10)
*   **`1176`** (FET Comp) – `input` (dB), `output` (dB), `attack` (0-1), `release` (0-1), `ratio` (4, 8, 12, 20)
*   **`dbx160`** (VCA Comp) – `threshold` (dB), `ratio`, `knee` (hard/soft)
*   **`ssl`** (Bus Comp) – `threshold` (dB), `ratio`, `attack` (s), `release` (s)
*   **`maximizer`** – `threshold` (dB), `ceiling` (dB)
*   **`parallel_comp`** – `threshold` (dB), `ratio`, `mix` (0-1)

### Distortion & Color
*   **`distortion`** – `drive` (0-1), `dist_type` (tanh, hard_clip, soft_clip, sine_fold, rectify, waveshape)
*   **`tube`** (Saturation) – `drive` (0-1), `asymmetry` (0-0.5)
*   **`tape`** (Magnetic) – `saturation` (0-1), `wow` (0-1), `flutter` (0-1)
*   **`studer`** (A800 Tape) – `ips` (15, 30), `bias` (0-1), `saturation` (0-1)
*   **`bitcrush`** – `bit_depth` (2-16), `sample_rate_reduction` (1-64)
*   **`exciter`** – `amount` (0-1), `cutoff` (Hz)
*   **`warmth`** – `drive` (0-1), `low_boost` (dB)
*   **`body`** – `amount` (0-1), `freq` (Hz)
*   **`neve`** (Preamp) – `input` (dB), `output` (dB), `drive` (0-1)
*   **`wavefolder`** – `folds` (1-10), `gain`, `symmetry`

### Modulation
*   **`chorus`** – `rate` (Hz), `depth` (s), `voices` (2-8), `mix` (0-1)
*   **`flanger`** – `rate` (Hz), `depth` (s), `feedback` (0-0.9), `mix` (0-1)
*   **`phaser`** – `rate` (Hz), `depth` (0-1), `stages` (2,4,6,8,12), `mix` (0-1)
*   **`tremolo`** – `rate` (Hz), `depth` (0-1)
*   **`vibrato`** – `rate` (Hz), `depth` (s)
*   **`autopan`** – `rate` (Hz), `depth` (0-1)
*   **`ensemble`** – `rate`, `depth`, `voices`, `mix`
*   **`dimension`** – `mode` (1-4)
*   **`dimension_d`** – `mode` (1-4)
*   **`small_stone`** – `rate` (Hz), `color` (bool)
*   **`ce1`** (Chorus) – `rate`, `depth`, `mode` (chorus/vibrato)
*   **`re301`** (Space Echo Chorus) – `rate`, `intensity`

### Reverb & Delay
*   **`delay`** – `time` (s), `feedback` (0-1), `mix` (0-1), `ping_pong` (true/false)
*   **`ping_pong`** – `time`, `feedback`, `mix`
*   **`reverb`** – `decay` (s), `mix` (0-1)
*   **`emt_plate`** – `decay` (s), `mix` (0-1)
*   **`spring`** – `decay` (s), `tension` (0-1), `mix`
*   **`lexicon`** (224) – `decay` (s), `predelay` (ms), `mix`
*   **`ams_reverb`** (RMX16) – `decay`, `mix`, `program` (ambience, nonlinear)
*   **`space_echo`** (RE-201) – `rate`, `intensity` (feedback), `mix`
*   **`tc2290`** (Digital Delay) – `time`, `feedback`, `mod_rate`, `mod_depth`

### Spectral & Creative
*   **`granular`** (Clouds) – `position` (0-1), `density` (0-1), `texture` (0-1), `size` (0-1), `pitch` (-12..12)
*   **`spectral_freeze`** – `mix` (0-1)
*   **`shimmer`** – `decay` (s), `pitch_shift` (intervals), `mix`
*   **`crystal`** – `reverse` (bool), `pitch` (semitones), `decay`, `mix`
*   **`resonator`** – `freq` (Hz), `decay` (0-1), `harmonics` (int)
*   **`buchla_lpg`** – `frequency`, `resonance`, `mode` (vactrol speed)
*   **`ring_mod`** – `freq` (Hz), `mix` (0-1)
*   **`freq_shift`** – `shift_hz` (Hz), `mix` (0-1)
*   **`vocoder`** – `bands` (int), `formant_shift` (ratio)
*   **`stereo_widen`** – `width` (0=mono, 1=wide)
*   **`lofi`** – `amount` (0-1)
*   **`stutter`** – `grain_size_ms`, `repeats`, `mix`
*   **`sub_bass`** – `mix` (0-1)
*   **`reverse`** – `mix` (0-1)
*   **`tape_stop`** – `duration_pct` (0-1)
*   **`vinyl`** – `crackle` (0-1), `hiss` (0-1), `wow` (0-1)
*   **`glitch`** – `amount` (0-1), `speed`
*   **`doppler`** – `speed`, `distance`

### Pitch
*   **`pitch_shift`** – `semitones` (-12..12), `mix` (0-1)
*   **`harmonizer`** – `interval` (semitones), `mix` (0-1)
*   **`octaver`** – `mix_down_1` (0-1), `mix_down_2` (0-1)
*   **`h3000`** – `shift_l`, `shift_r`, `feedback`

---

## Standalone Build

Build a standalone executable with PyInstaller:

```bash
venv/bin/pyinstaller figgygen.spec
cp -r presets fxpresets dist/figgygen/
```

The output layout:
```
dist/figgygen/
  figgygen          ← executable
  presets/           ← genre presets (editable)
  fxpresets/         ← FX presets (editable)
  _internal/         ← Python runtime
```

Double-click `figgygen` to launch the interactive session.

