# pySynth Scripting Guide 📜

This guide explains how to use `.psy` script files to automate your sample generation. Scripts allow you to chain multiple commands together, execute complex chord progressions, and apply precise effects without typing long commands in the terminal.

## What is a `.psy` file?

A `.psy` file is just a plain text file containing a list of commands. pySynth reads it line-by-line and executes them.

**To run a script:**
```bash
python run.py my_script.psy
```

**To edit a script:**
```bash
python run.py --edit my_script.psy
```

---

## 🚀 Basic Commands

### `set [key] [value]`
Updates a global setting. This setting persists for all subsequent `generate` commands until you change it again.

| Key | Value Example | Description |
|---|---|---|
| `out` | `./my_pack` | Output directory |
| `note` | `C4` or `C2 E2` | Note(s) to play |
| `genre` | `bass`, `pad`, `keys` | Sonic palette / preset |
| `duration` | `2.0` | Length in seconds |
| `count` | `10` | Number of samples per batch |
| `passes` | `5` | Number of variation passes (for progressions) |
| `loop` | `true` | Optimize duration for perfect loops (integer cycles) |
| `zeroc` | `true` | Apply zero-crossing fade in/out |
| `seed` | `12345` | Random seed for deterministic generation |
| `scale` | `minor` | Quantize notes to scale (major, minor, pentatonic, etc.) |
| `round-robin` | `true` | Generate drift variations of a base patch |
| `macro` | `rate=0.1...` | Macro modulation config string |
| `wavetable` | `true` | Export as 64-frame wavetable |

**Example:**
```text
set out ./techno_bass
set genre bass
set note C2
```

### `generate [count]`
Generates a batch of samples using the current settings.

**Example:**
```text
# Generate 10 samples with current settings
generate 10

# Change note and generate 5 more
set note G2
generate 5
```

---

## 🎛️ Effects Control

You can precisely control the effects chain using the following `set` keys.
*Note: These support the "Parametric" syntax: `effect(param=value)`*

### `set fx-only ...`
**Overrides** the genre's default effects. Uses **ONLY** the effects you list.

```text
# Only use a Moog filter and some Reverb
set fx-only moog(cutoff=600, resonance=0.8), reverb(mix=0.3)
```

### `set fx-include ...`
**Adds** these effects to the end of the chain, on top of whatever the genre normally generates.

```text
# Always add a little bit of distortion
set fx-include distortion(drive=0.4)
```

### `set fx-exclude ...`
**Bans** these effects. Useful if you hate a specific effect (e.g., bitcrusher).

```text
# Never use bitcrush or flanger
set fx-exclude bitcrush, flanger
```

---

## 🎹 Chord Progressions

### `progression "..."`
Generates a full chord progression. The engine creates a "patch" (sound) and applies it to every chord in the sequence, then repeats for the number of `passes`.

**Syntax:** `progression "Chord1|Chord2|Chord3"`

**Example:**
```text
set genre pad
set duration 4.0
set passes 2

# Generate a ii-V-I progression
progression "Dm7|G7|Cmaj7"
```

---

## 🚌 Parallel Processing (Buses)

Create parallel signal chains to layer sounds or apply effects independently to different oscillators.

### `bus [id]:[oscillators]>[effects]`
Configures a new parallel bus.

- **`id`**: A unique name for the bus (e.g., `lead`, `sub`, `texture`).
- **`oscillators`**: Comma-separated list of waveforms for this bus.
- **`effects`**: Comma-separated list of effects for this bus signal chain. **FX Presets** (like `tape_warmth`) are also supported and will expand into their full chains.

**Example:**
```text
# Layer a clean sub-sine with a distorted saw lead
bus sub:sine>compressor
bus lead:saw>distortion(drive=0.5),reverb
generate
```

### `bus clear`
Removes all custom buses and reverts to the default "main" bus logic.

---

## 📝 Complete Example

Save this as `my_album.psy`:

```text
# Album Generation Script

# 1. Setup
set out ./album_kit
set duration 2.0

# 2. Deep Basses
set genre bass
set note C2
set fx-include tube(drive=0.3)
generate 10

# 3. Atmospheric Pads
set genre pad
set note "C4 E4 G4 B4"
set fx-only reverb(decay=5.0, mix=0.5), phaser
generate 5

# 4. Glitch Drums
set genre perc
set duration 0.5
set fx-include stutter, glitch
generate 20

# 5. Song Idea (Progression)
set duration 2.0
set passes 3
set genre keys
progression "Am|F|C|G"
```

---

## 🎛️ Oscillator & Modulation Control

Just like effects, you can now control the sound sources and modulation sources.

### Oscillator Selection (`set osc-...`)
Control which waveforms or drum models are used.

*   `set osc-only`: Use **ONLY** these waveforms.
*   `set osc-include`: **Add** these to the pool.
*   `set osc-exclude`: **Ban** these from the pool.

**Example:**
```text
# Force 808 drums
set genre perc
set osc-only kick_808, snare_808, hat_808

# Bass without saw waves
set genre bass
set osc-exclude saw, super_saw
```

### Modulation Overrides (`set lfo-...`)
Override the genre-default LFO settings.

*   `set lfo-rate [min,max]`: Force LFO speed in Hz.
*   `set lfo-depth [min,max]`: Force modulation intensity (0.0-1.0).

**Example:**
```text
# Super fast FM-style modulation
set lfo-rate 20.0, 50.0
set lfo-depth 1.0, 1.0
```

### Musical Constraints

### Musical Constraints
213: 
214: *   `set scale [name]`: Quantizes all notes to the nearest scale degree.
215: *   `set scale "0,2,4,7,9"`: Define a **custom scale** using semitone intervals.
216: *   `set seed [int]`: Forces the random number generator to a specific state.
217: 
218: **Example:**
219: ```text
220: # Use one of 47 built-in scales (e.g. whole_tone, hirajoshi, bebop_dominant)
221: set scale whole_tone
222: 
223: # Or define your own (e.g. a custom Hexatonic scale)
224: set scale "0,1,4,6,8,11"
225: 
226: generate 5
227: ```

### Advanced Features

#### Round Robin
Generate natural variations of a single patch.
```text
set genre bass
set round-robin true
generate 5  # 5 variations of the same bass sound
set round-robin false # Turn it off for next batch
```

#### Macro Modulation
Modulate parameters over time across a batch.
```text
set genre pad
set count 20
set macro rate=0.2,depth=1.0,targets=filter:cutoff:0.5
generate 20
```

---

---

## 📚 Reference Guide

### Global Settings (`set`)

| Key | Description | Valid Values | Example |
|---|---|---|---|
| `out` | Output folder | Any path | `set out ./my_samples` |
| `note` | Musical note(s) | Notes (`C4`), Chords (`C4E4G4`), Freq (`440`) | `set note C#3` |
| `genre` | Sound palette | `bass`, `pad`, `lead`, `fx`, `keys`, `perc` | `set genre bass` |
| `duration` | Length (seconds) | Float `0.1` to `30.0` | `set duration 2.5` |
| `count` | Batch size | Integer `1` to `1000` | `set count 20` |
| `passes` | Progression variations | Integer `1` to `100` | `set passes 5` |
| `loop` | Perfect looping | `true`, `false` | `set loop true` |
| `zeroc` | No-click fades | `true`, `false` | `set zeroc true` |
| `fx-only` | Force specific effects | Comma-separated list | `set fx-only reverb` |
| `fx-include`| Add effects to chain | Comma-separated list | `set fx-include distortion`|
| `fx-exclude`| Ban effects | Comma-separated list | `set fx-exclude bitcrush` |
| `osc-only` | Force specific oscillators | Comma-separated list | `set osc-only saw,square` |
| `osc-include`| Add oscillators to pool | Comma-separated list | `set osc-include kick_808`|
| `osc-exclude`| Ban oscillators | Comma-separated list | `set osc-exclude noise` |
| `lfo-rate` | LFO Speed Range (Hz) | `min,max` floats | `set lfo-rate 0.1,0.5` |
| `lfo-depth` | LFO Depth Range (0-1) | `min,max` floats | `set lfo-depth 0.8,1.0` |
| `scale` | Quantize to Scale | Name or "intervals" | `set scale minor` or `set scale 0,2,4,7,9` |
| `seed` | Random Seed | Integer | `set seed 123` |
| `round-robin` | Drift Variations | `true`, `false` | `set round-robin true` |
| `macro` | Macro Mod Config | String | `set macro rate=0.1...` |
| `wavetable` | Wavetable Export | `true`, `false` | `set wavetable true` |

### Genres

| Genre | Description | Best For |
|---|---|---|
| `bass` | Low, heavy, distorted | Techno, DnB, House basslines |
| `pad` | Lush, atmospheric, spacious | Ambient, Cinematic textures |
| `lead` | Bright, cutting, melodic | Solos, Hooks |
| `fx` | Weird, noisy, glitchy | Risers, Downlifters, Foley |
| `keys` | Clean, electric piano-ish | Chords, Lo-fi hiphop |
| `perc` | Short, punchy, noisy | Drums, Percussion loops |

### Effect Categories & Common Parameters

*For the full list of all 92 effects and every single parameter, see [CLI_REFERENCE.md](CLI_REFERENCE.md).*

**Common Effects:**

*   **Filters:** `cutoff`, `resonance`
    *   `filter`, `moog` (adds `drive`), `303` (adds `env_mod`, `accent`, `decay`)
*   **Time-Based:** `mix`, `decay`, `time`, `feedback`
    *   `reverb`, `delay`, `chorus`, `flanger`, `phaser`
*   **Distortion:** `drive`, `mix`
    *   `distortion`, `tube`, `bitcrush` (`bits`, `downsample`)
*   **Dynamics:** `threshold`, `ratio`, `attack`, `release`
    *   `compressor`, `limiter`, `gate` (`threshold`, `attack`, `release`)
*   **Hardware Emulations:**
    *   `tape`: `drive`, `wow`, `flutter`, `hiss`
    *   `1176`: `input_gain`, `ratio`, `attack`, `release`
    *   `pultec`: `low_boost`, `low_atten`, `high_boost`, `high_atten`
*   **Creative:**
    *   `glitch`: `density`, `length`, `reverse_prob`
    *   `stutter`: `rate`, `chance`, `gate`
    *   `shimmer`: `shift`, `feedback`, `mix`
    *   `lofi`: `bits`, `noise`, `filter_cutoff`

---

## 🧪 Example: Filter Showcase

To test different filter types, you can write a script that switches the effect for each generation.

```text
# Filter Audition Script
set out ./filter_test
set note C2
set duration 1.0
set genre bass

# 1. Moog Ladder
set fx-only moog(cutoff=300,resonance=0.8)
generate 1

# 2. TB-303 Acid
set fx-only 303(cutoff=300,resonance=0.8)
generate 1

# 3. Korg MS-20
set fx-only ms20(cutoff=300,resonance=0.8)
generate 1

# 4. Prophet-5
set fx-only prophet(cutoff=300,resonance=0.6)
generate 1

# 5. Oberheim SEM
set fx-only sem(cutoff=300,resonance=0.5,mode=lowpass)
generate 1

# 6. Oberheim OB-Xa
set fx-only obxa(cutoff=300,resonance=0.6,mode=lowpass)
generate 1

# 7. EDP Wasp
set fx-only wasp(cutoff=300,resonance=0.7)
generate 1

# 8. Juno-106 HPF
set fx-only juno_hpf(cutoff=500,resonance=0.3)
generate 1

# 9. Generic Digital Filter
set fx-only filter(filter_type=lowpass,cutoff=300,resonance=0.5)
generate 1
```

---

## 🏗️ Built-in Editor

FiggyGen includes a simple, line-based text editor for quick modifications without leaving the terminal.

**To open the editor:**
```bash
./dist/figgygen/figgygen --edit my_script.psy
```

### Editor Commands
- `[number] [text]`: Replace the content of line `[number]`.
- `+ [text]`: Append a new line at the end.
- `- [number]`: Delete line at `[number]`.
- `ins [number] [text]`: Insert before `[number]`.
- `save`: Write changes to disk.
- `run`: Execute the current buffer in memory (great for testing).
- `help`: Show all commands.
- `exit`: Quit the editor.

**Pro-Tip**: You can also open the editor from within the REPL by typing `edit filename.psy`.


