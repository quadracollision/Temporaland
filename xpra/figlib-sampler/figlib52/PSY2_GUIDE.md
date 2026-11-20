# PSY2 Language Reference & Programming Guide 📜

Welcome to the definitive guide for **PSY2**, the domain-specific language for the FiggyGen audio engine. 

PSY2 is designed to completely define audio generation patches (VST-like environments) in code. Unlike the older line-based `.psy` scripts which acted merely as command aliases, **PSY2 is a full language** with variables, loops, declarative audio routing, configurations, and complex UI definitions.

---

## 1. Core Concepts

A PSY2 script is evaluated first to build an **Abstract Syntax Tree (AST)**, which is then interpreted to generate a **UI Patcher** (visual canvas) and an **Engine State**.

The fundamental unit of audio generation is the **Bus**. A bus is an independent audio signal path containing oscillators, samples, and effect chains. Buses are routed to each other, and eventually to `master`. 

The general flow of a script is:
1. **Variable Declarations** (`let`)
2. **Loops** (`for`) to procedurally generate buses.
3. **Bus Definitions** (`bus`) to define sound sources and effects.
4. **Routing** (`->`) to connect buses.
5. **Configuration** (`config {}`) to define global batch settings.
6. **UI Definition** (`@ui {}`) to expose controls to the user interface.
7. **Execution** (`generate`) to trigger the actual rendering.

---

## 2. Lexical Structure

### Comments
Comments begin with `#` and continue to the end of the line.
```psy2
# This is a comment
bus Lead { # This is an inline comment
```

### Identifiers & Keywords
Identifiers (names of buses, variables, effects) can consist of alphanumeric characters, underscores `_`, dots `.`, and the `$` symbol.

**Note:** Unlike many languages, strings don't necessarily need quotes. `textbox out 10 20 200 25 ./output` is perfectly valid. Quotes are only required if the string contains spaces (e.g., `"C4 E4 G4"`). 

**Keywords:** `bus`, `config`, `generate`, `connect`, `osc`, `fx`, `volume`, `sample`, `range`, `let`, `for`, `in`, `master`, `@ui`, `knob`, `slider`, `textbox`, `toggle`, `button`.

### Symbols
Arithmetic operators `+`, `-`, `*`, `/` and parentheses `(` `)` are supported for math. Brackets `[` `]` are used for list literals.


---

## 3. Variables & Interpolation

Variables are declared using the `let` keyword. 
When referencing a variable anywhere later in the script (even inside strings), prefix it with `$`.

```psy2
let my_depth = 0.65
let my_rate = 2.4

bus Pad {
  osc saw
  fx chorus(depth=$my_depth, rate=$my_rate)
}

@ui {
  # You can use variables as the default value for UI widgets!
  knob chorus.depth 30 0.0 1.0 $my_depth
}
```

*Note: The engine tracks variables internally without the `$`. The `$` is just the syntax for interpolation/referencing.*

### 3.1 Mathematical Operations
You can perform math directly inside `let` declarations or as parameters.
```psy2
let base_cutoff = 0.2
let spacing = 0.1
# Basic arithmetic with variables and parentheses
let dynamic_cutoff = base_cutoff + (i * spacing)
```

### 3.2 Lists (Arrays)
PSY2 supports list literals using `[ ]`.
```psy2
let waveforms = ["saw", "square", "sine", "noise"]
```

### 3.3 Advanced Expressions `$()`
Use the `$()` syntax to evaluate complex Python expressions on the fly. This is extremely powerful for indexing into arrays using a loop variable.
```psy2
for i in 1..4 {
  bus Layer$i {
    # Dynamically select waveform based on loop index
    osc $(waveforms[i-1])
  }
}
```
*Note: Any variable in your current PSY2 context (like `i` or `waveforms`) is available inside the `$()` block.*


---

## 4. Loops

You can procedurally generate multiple buses or UI elements using `for` loops with range syntax (`start..end`).

```psy2
let base_cutoff = 0.2

for i in 1..4 {
  bus Layer$i {
    osc saw
    fx filter(cutoff=$base_cutoff, resonance=0.8)
  }
  Layer$i -> master
}
```
In the above example, the interpreter evaluates four independent buses: `Layer1`, `Layer2`, `Layer3`, and `Layer4`. The variable `$i` is dynamically interpolated into the identifier name.

---

## 5. Bus Definitions

A `bus` block defines an audio chain.
**Syntax:** `bus ID (param=val, ...) { ... }`

```psy2
bus Drone(volume=0.8) {
  osc saw, sine
  fx distortion(drive=0.4)
  fx delay(time=0.5, feedback=0.3)
}
```

### 5.1 Bus Body Directives
Inside a bus block, you can use the following directives:

*   **`osc [waveforms]`**: Comma-separated list of waveforms (e.g., `saw, square, sine, noise`).
*   **`sample [path]`**: Path to a sample folder or file to act as the primary oscillator.
*   **`volume [float]`**: Attenuation multiplier. (Can also be passed in the bus signature `bus ID(volume=0.5)`).
*   **`connect [Bus_ID]`**: Makes an internal sub-bus connection targeting another bus.

### 5.2 Effects (`fx`)
The `fx` directive appends an effect to the bus chain.

```psy2
fx reverb(mix=0.6, decay=2.0)
```

**Randomization Ranges**: Instead of an exact float, you can provide a hyphenated range (e.g. `0.2-0.8`). The engine will randomly pick a value in this range every time `generate` is called!
```psy2
fx chorus(depth=0.2-0.8, rate=0.5-2.0)
```

### 5.3 FX Presets (Crucial Feature!)
Did you know you can use **entire FX Presets** inside a bus? 

If the name of the effect matches a `.psifx` preset defined in your `/fxpresets` folder (e.g., `acid`, `80s_synth`, `analog_console`), the engine will automatically expand it into its full, randomized multi-effect chain!

```psy2
bus AcidBass {
  osc saw
  fx acid      # Will expand to 303 filter, distortion, resonator, etc!
}
```

---

## 6. Routing

Signal flow between buses is explicitly defined using the `->` operator. The ultimate destination for heard audio is `master`.

```psy2
Sub -> master
Rhythm -> master
Lead -> DelayAux
DelayAux -> master
```

---

## 7. The Configuration Block

The `config {}` block outlines the global environment for the patch. It instructs the generator how to render the final audio.

```psy2
config {
  out "./lush_pads" # Where to save audio
  genre pad         # The algorithmic preset for random fill-in
  count 5           # How many files to generate
  note D2           # Root note or Space-separated chords
}
```

### Complete List of Config Keys

| Key | Type | Description |
|-----|------|-------------|
| `out` | `string` | Output folder path |
| `genre` | `string` | Base preset (e.g., `pad`, `bass`, `fx`) |
| `note` | `string` | Note (`C4`), chord (`Cmaj7`), or sequence (`C4 E4 G4`) |
| `duration` | `float` | Duration per render in seconds |
| `count` | `int` | Number of renders per batch |
| `passes` | `int` | Number of processing passes (crucial for progressions) |
| `progression` | `string` | Roman numeral or literal progression (e.g., `i-VI-IV-v`) |
| `scale` | `string` | Quantize output to a scale (e.g., `minor`, `dorian`) |
| `exact` | `bool` | Disable random jitter/drift |
| `loop` | `bool` | Optimize length for perfect beat looping |
| `zeroc` | `bool` | Apply zero-crossing micro-fades to prevent clicks |
| `wavetable` | `bool` | Export as 64-frame/2048-sample wavetable |
| `destructive` | `bool` | Process destructively over time |
| `round-robin` | `bool` | Generate organic drift variations of a base patch |
| `nitro` | `bool` | Apply Nitro tracking format rendering |
| `seed` | `int` | Global RNG seed for deterministic regeneration |
| `macro` | `string` | Mod config string (`rate=0.1,depth=1.0...`) |
| `lfo-rate` | `float` | Force genre-LFO speed (e.g., `0.5, 2.0`) |
| `lfo-depth` | `float` | Force genre-LFO depth (e.g., `0.0, 1.0`) |

---

## 8. UI Generation (`@ui`)

PSY2 is more than a script; it's a UI framework. The `@ui {}` block defines interactive widgets that appear on the IDE canvas. 

**Widgets bidirectionally sync with the state.** If you turn a UI knob mapped to `chorus.depth`, the engine's state updates instantly. If you add a config property in code, a matching textbox automatically populates.

### 8.1 Widget Syntax
*If `x` and `y` are omitted, the interpreter auto-layouts the widgets in a grid.*

**`textbox target [x y width height] default`**
Binds to config variables or parameters.
```psy2
textbox genre 10 20 80 25 pad
textbox note C4
```

**`knob target [x y] radius min max default`**
A continuous rotary dial.
```psy2
knob chorus.depth 10 120 25 0.0 1.0 0.5
  range 0.2 0.8  # Optional: Adds random bounds indicators
```

**`slider target [x y] width height min max default`**
A continuous linear fader.
```psy2
slider volume 10 200 200 25 0.0 1.0 0.8
```

**`toggle target [x y] size default`**
A boolean switch.
```psy2
toggle exact 10 250 15 false
```

**`button label [x y width height]`**
A trigger action. 
```psy2
button Generate 10 300 200 40
```

### 8.2 Widget Targeting (Variables & Overrides)
Widgets map to engine state using their `target` name.
*   **Global Config**: Target keywords like `volume`, `seed`, `duration`, `passes`.
*   **Global FX**: Target an effect generically: `distortion.drive`.
*   **Bus Specific FX**: Target precisely: `Lead.distortion.drive`.

### 8.3 Bus UI Macros (Auto-Expansion)
Typing out 20 knobs for a complex chain is tedious. PSY2 offers an incredible macro feature: **Bus Expansion**.

If you target an entire bus with a knob or slider (e.g., `knob bus.Lead`), **the interpreter will automatically generate a separate UI knob/slider for every single parameter of every effect defined in that bus!**

```psy2
bus Atmosphere {
  osc saw
  fx chorus(mix=0.5, depth=0.2)
  fx reverb(decay=3.0, mix=0.7)
}

@ui {
  knob bus.Atmosphere  # MAGIC! Auto-generates 4 knobs.
}
```
The auto-generated knobs inherit the default values specified in your `fx` declarations, saving you hundreds of lines of code.

### 8.4 Bus Mute/Solo Macros
You can easily create toggles to control the activity of buses to save CPU:
```psy2
toggle bus.Atmosphere.mute 10 10 15 false
toggle bus.Atmosphere.solo 10 30 15 false
```
*Note: The engine aggressively optimizes muted buses by completely omitting them from generation processing.*

---

## 9. Execution Engine

### `generate`
The `generate N` statement initiates audio rendering.
*   If `N` is provided, it acts as the `count`.
*   If executed inside the IDE via the 'Run' button, the engine evaluates in "UI Only" mode first to render the canvas. Audio generation is only triggered when the user explicitly clicks a UI `button` or runs via the CLI.

---

## 10. File Integration

PSY2 scripts seamlessly integrate with the `run.py` CLI. 

```bash
# Execute headless and immediately generate
python run.py my_script.psy2

# Open the CLI editor
python run.py --edit my_script.psy2
```

**Enjoy building complex audio patches with PSY2!**

