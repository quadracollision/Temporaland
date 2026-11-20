"""
pySynth CLI – The FiggyGen command-line interface.
Supports concatenated chord notation: --note C4E3F#4G3
"""
import argparse
import re
import sys
import inspect
import os
import random
import numpy as np
from .generator import SampleGenerator, load_presets
from .synth import EFFECT_DISPATCH
from .oscillator import Oscillator
from .utils.music_theory import (
    quantize_freq_to_scale, 
    SCALES as MUSIC_SCALES,
    note_to_freq,
    parse_chord,
    get_scale_sequence,
    get_key_root_semitone,
    get_key_accidentals,
    parse_roman_progression
)
from .parsing import (
    parse_fx_string, 
    parse_bus_string, 
    resolve_rand_macro, 
    resolve_rand_float, 
    resolve_rand_int, 
    resolve_rand_note,
    FX_PARAM_RANGES
)

# Load presets once at startup for CLI validation
PRESETS = load_presets()
GENRE_CHOICES = list(PRESETS.keys())

# Lazy import for utils to avoid circular deps if needed, but direct is fine
try:
    from .utils.nitro import convert_to_nitro
except ImportError:
    convert_to_nitro = None


def print_effect_info(effect_name=None):
    """Print documentation and parameters for effects."""
    if not effect_name or effect_name.lower() == 'all':
        print("\n[FiggyGen] Available Effects:")
        for name in sorted(EFFECT_DISPATCH.keys()):
            print(f"  - {name}")
        print("\nUse '--info [name]' for details on a specific effect.\n")
        return

    fx_func = EFFECT_DISPATCH.get(effect_name.lower())
    if not fx_func:
        print(f"\n[FiggyGen] Error: Effect '{effect_name}' not found.")
        return

    print(f"\n[FiggyGen] Effect: {effect_name.upper()}")
    
    # Docstring
    doc = inspect.getdoc(fx_func)
    if doc:
        print("\n  Description:")
        for line in doc.split('\n'):
            print(f"    {line.strip()}")
    
    # Parameters
    sig = inspect.signature(fx_func)
    print("\n  Parameters:")
    count = 0
    for name, param in sig.parameters.items():
        if name in ('audio', 'sample_rate', 'kwargs'):
            continue
        
        default = param.default
        if default == inspect.Parameter.empty:
            def_str = "(required)"
        else:
            def_str = f"(default: {default})"
            
        print(f"    {name:<15} {def_str}")
        count += 1
    
    if count == 0:
        print("    (No configurable parameters)")
    print("")


def print_effect_info(effect_name=None):
    """Print documentation and parameters for effects."""
    if not effect_name or effect_name.lower() == 'all':
        print("\n[FiggyGen] Available Effects:")
        for name in sorted(EFFECT_DISPATCH.keys()):
            print(f"  - {name}")
        print("\nUse '--info [name]' for details on a specific effect.\n")
        return

    fx_func = EFFECT_DISPATCH.get(effect_name.lower())
    if not fx_func:
        print(f"\n[FiggyGen] Error: Effect '{effect_name}' not found.")
        return

    print(f"\n[FiggyGen] Effect: {effect_name.upper()}")
    
    # Docstring
    doc = inspect.getdoc(fx_func)
    if doc:
        print("\n  Description:")
        for line in doc.split('\n'):
            print(f"    {line.strip()}")
    
    # Parameters
    sig = inspect.signature(fx_func)
    print("\n  Parameters:")
    count = 0
    for name, param in sig.parameters.items():
        if name in ('audio', 'sample_rate', 'kwargs'):
            continue
        
        default = param.default
        if default == inspect.Parameter.empty:
            def_str = "(required)"
        else:
            def_str = f"(default: {default})"
            
        print(f"    {name:<15} {def_str}")
        count += 1
    
    if count == 0:
        print("    (No configurable parameters)")
    
    print("\n  Usage Example:")
    print(f"    --fx-include \"{effect_name.lower()}({', '.join([f'{p}=...' for p in sig.parameters if p not in ('audio', 'sample_rate', 'kwargs')])})\"")
    print("")









# ──────────────────────────────────────────────────────────────
# FX list printer
# ──────────────────────────────────────────────────────────────
FX_CATEGORIES = {
    'Filters':      ['filter', 'comb', 'formant', 'moog', '303', 'sem',
                     'ms20', 'prophet', 'juno_hpf', 'obxa', 'wasp'],
    'Distortion':   ['distortion', 'bitcrush', 'tube', 'wavefolder'],
    'Amps':         ['marshall', 'vox', 'fender_twin'],
    'Modulation':   ['chorus', 'flanger', 'phaser', 'tremolo', 'vibrato',
                     'autopan', 'ce1', 'small_stone', 're301', 'dimension',
                     'ensemble', 'dimension_d'],
    'Delay/Echo':   ['delay', 'space_echo', 'tc2290'],
    'Reverb':       ['reverb', 'emt_plate', 'spring', 'lexicon', 'ams_reverb'],
    'Dynamics':     ['compressor', 'limiter', 'fairchild', 'ssl', 'dbx160',
                     'la2a', '1176', 'gate', 'transient', 'maximizer',
                     'multiband', 'parallel_comp'],
    'EQ/Preamp':    ['neve', 'pultec', 'exciter', 'harmonic_enhance'],
    'Tape':         ['tape', 'studer'],
    'Pitch':        ['pitch_shift', 'harmonizer', 'octaver', 'h3000'],
    'Stereo/Space': ['stereo_widen', 'haas', 'ring_mod', 'freq_shift',
                     'arp_ring', 'sidechain', 'dc_remove',
                     'stereo_imager', 'width_enhance', 'spatial'],
    'Creative':     ['lofi', 'stutter', 'sub_bass', 'reverse', 'tape_stop',
                     'vinyl', 'radio', 'telephone', 'underwater', 'shimmer',
                     'glitch', 'doppler', 'crystal', 'fade', 'resonator',
                     'buchla_lpg', 'granular', 'spectral_freeze',
                     'granular_stretch'],
    'Mastering':    ['warmth', 'body'],
}




def print_fx_list():
    """Print all available effects grouped by category."""
    print("\n╔═══════════════════════════════════════════════════╗")
    print("║          pySynth – Available Effects              ║")
    print(f"║          {len(EFFECT_DISPATCH)} effects total"
          f"{' ' * (34 - len(str(len(EFFECT_DISPATCH))))}║")
    print("╚═══════════════════════════════════════════════════╝\n")

    for cat, effects in FX_CATEGORIES.items():
        valid = [e for e in effects if e in EFFECT_DISPATCH]
        if not valid:
            continue
        print(f"  {cat}:")
        # Print in rows of 5
        for i in range(0, len(valid), 5):
            row = ', '.join(valid[i:i+5])
            print(f"    {row}")
        print()

    print("Use these names with --fx-only, --fx-include, --fx-exclude")
    print("Example: --fx-only moog,reverb,tape --fx-include fairchild\n")


# ──────────────────────────────────────────────────────────────
# Execution Logic
# ──────────────────────────────────────────────────────────────
def execute_generation(count, out, note, duration, genre, fx_rules, osc_rules={}, lfo_rules={}, bus_rules=[], scale=None,
                       loop=False, zeroc=False, round_robin=False, macro_spec=None, wavetable_export=False,
                       sample_path=None, sample_folder=None, destructive=False, fxpreset=None, nitro=False, exact=False):

    """Execute a single batch generation."""
    freqs = parse_chord(note)
    if not freqs:
        freqs = [440.0]

    # Quantize to scale
    if scale:
        scale = scale.lower()
        import pySynth.utils.music_theory as mt
        if not mt._get_scale_intervals(scale):
            print(f"[FiggyGen] Warning: Unknown scale '{scale}'. Ignoring.")
            scale = None
        else:
            print(f"[FiggyGen] Quantizing to {scale} scale...")
            # Detect root from first note in the input string
            # This allows --note A3 --scale minor to equal "Key of A Minor"
            root = 'C'
            import re
            # Find first occurrence of a note name (e.g. C, F#, Bb, etc.)
            m = re.search(r"([A-Ga-g][s#b]?)", str(note))
            if m:
                root = m.group(1)
            
            freqs = [quantize_freq_to_scale(f, scale, root) for f in freqs]


    print(f"[FiggyGen] Generating {count} samples...")
    print(f"[FiggyGen] Genre: {genre if genre else 'Random'}")
    print(f"[FiggyGen] Notes: {note} → {[round(f, 2) for f in freqs]} Hz")
    
    if fx_rules:
        parts = []
        if 'only' in fx_rules:
            names = [f"{x['type']}({x['params']})" if x['params'] else x['type'] for x in fx_rules['only']]
            parts.append(f"only={names}")
        if 'include' in fx_rules:
            names = [f"{x['type']}({x['params']})" if x['params'] else x['type'] for x in fx_rules['include']]
            parts.append(f"include={names}")
        if 'exclude' in fx_rules:
            parts.append(f"exclude={fx_rules['exclude']}")
        print(f"[FiggyGen] FX rules: {', '.join(parts)}")

    if osc_rules:
        parts = []
        if 'only' in osc_rules and osc_rules['only']:
            parts.append(f"only={osc_rules['only']}")
        if 'include' in osc_rules and osc_rules['include']:
            parts.append(f"include={osc_rules['include']}")
        if 'exclude' in osc_rules and osc_rules['exclude']:
            parts.append(f"exclude={osc_rules['exclude']}")
        if parts:
            print(f"[FiggyGen] Osc rules: {', '.join(parts)}")

    if bus_rules:
        bus_ids = [f"'{b['id']}'" for b in bus_rules]
        print(f"[FiggyGen] Audio Buses: {', '.join(bus_ids)}")

    gen = SampleGenerator(output_dir=out)
    gen.generate_batch(count=count, note_freq=freqs,
                       duration=duration, genre=genre,
                       fx_rules=fx_rules, osc_rules=osc_rules, lfo_rules=lfo_rules,
                       loop=loop, zeroc=zeroc,
                       round_robin=round_robin, macro_spec=macro_spec, wavetable_export=wavetable_export,
                       sample_path=sample_path, sample_folder=sample_folder, destructive=destructive, fxpreset=fxpreset,
                       scale=scale, nitro=nitro, bus_rules=bus_rules, exact=exact)
    print(f"[FiggyGen] Batch complete.\n")


def execute_progression(progression, passes, out, duration, genre, fx_rules, osc_rules={}, lfo_rules={}, bus_rules=[], scale=None, loop=False, zeroc=False, nitro=False, exact=False):
    """Execute a chord progression generation."""
    print(f"[FiggyGen] Generating Progression: {progression}")
    print(f"[FiggyGen] Passes (Patches): {passes}")
    
    # Detect Roman Numerals (contain i, v, x, or I, V, X and hyphens/spaces)
    if re.search(r'\b[ivIVxX]+([- ]+[ivIVxX]+)*\b', progression):
        print(f"[FiggyGen] Detected Roman Numeral Progression. Mapping to {scale if scale else 'minor'} scale...")
        # Resolve root from genre or state? Usually it's in the state's 'note'
        # But here we don't have full state access easily, let's assume 'C' if not obvious
        # Actually, let's look for a note in the 'note' param if provided?
        # For now, use 'C' and 'minor' as defaults for pads if not specified
        root_name = 'C'
        s_type = scale if scale else 'minor'
        parsed_chords = parse_roman_progression(progression, root_name, s_type)
    else:
        chords = progression.split('|')
        parsed_chords = []
        for c in chords:
            f = parse_chord(c)
            if not f: f = [440.0]
            
            if scale:
                scale = scale.lower()
                if scale in MUSIC_SCALES:
                     f = [quantize_freq_to_scale(freq, scale, 'C') for freq in f]

            parsed_chords.append(f)
    
    gen = SampleGenerator(output_dir=out)
    gen.generate_progression(chord_list=parsed_chords, passes=passes,
                             duration=duration, genre=genre,
                             fx_rules=fx_rules, osc_rules=osc_rules, lfo_rules=lfo_rules,
                             loop=loop, zeroc=zeroc, nitro=nitro, bus_rules=bus_rules, exact=exact)
    if bus_rules:
        bus_ids = [f"'{b['id']}'" for b in bus_rules]
        print(f"[FiggyGen] Audio Buses: {', '.join(bus_ids)}")

    print(f"[FiggyGen] Progression complete.\n")


def execute_scale_sweep(scale, passes, out, duration, genre, note, fx_rules, osc_rules={}, lfo_rules={}, bus_rules=[], loop=False, zeroc=False, nitro=False, exact=False):
    """Execute a scale sweep generation."""
    print(f"[FiggyGen] Scale Sweep Mode: {scale} ({passes} passes)")
    
    chord_freqs = parse_chord(note)
    if not chord_freqs: chord_freqs = [440.0]
    
    # Determine Root Key Name
    root_name = 'C'
    import re
    m = re.search(r"([A-Ga-g][s#b]?)", str(note))
    if m:
        root_name = m.group(1)
    
    # Check for flat key
    acc = get_key_accidentals(root_name)
    use_flats = (acc == 'b')
    if use_flats:
        print("[FiggyGen] Detected Flat Key -> enforcing flat naming.")

    root_freq = chord_freqs[0]
    
    scale_seq = get_scale_sequence(root_freq, scale, root_name, octaves=1)
    
    gen = SampleGenerator(output_dir=out)
    gen.generate_progression(chord_list=scale_seq,
                             passes=passes,
                             duration=duration,
                             genre=genre,
                             fx_rules=fx_rules,
                             osc_rules=osc_rules,
                             lfo_rules=lfo_rules,
                             loop=loop,
                             zeroc=zeroc,
                             nitro=nitro,
                             force_flat=use_flats,
                             bus_rules=bus_rules,
                             exact=exact)
    if bus_rules:
        bus_ids = [f"'{b['id']}'" for b in bus_rules]
        print(f"[FiggyGen] Audio Buses: {', '.join(bus_ids)}")

    print(f"[FiggyGen] Sweep complete.\n")


# ──────────────────────────────────────────────────────────────
# Script Interpreter
# ──────────────────────────────────────────────────────────────

    
def get_default_state():
    """Returns a fresh default state dictionary."""
    return {
        'count': 10,
        'out': './samples',
        'note': 'C4',
        'duration': 2.0,
        'genre': None,
        'passes': None,
        'fx_rules': {},
        'osc_rules': {'only': [], 'include': [], 'exclude': []},
        'bus_rules': [],
        'lfo_rules': {'rate': None, 'depth': None},
        'scale': None,
        'loop': False,
        'zeroc': False,
        'round_robin': False,
        'macro': None,
        'wavetable': False,
        'sample': None, 
        'sample_folder': None, 
        'destructive': False,
        'nitro': None,
        'fxpreset': None,
        'exact': False
    }

def execute_interpreter_command(cmd, arg, state, context="Script"):
    """Execute a single interpreter command (set/generate/progression)."""
    cmd = cmd.strip()
    if not cmd or cmd.startswith('#'):
        return
        
    if cmd == 'set':
        # Syntax: set key value
        if ' ' not in arg:
            print(f"[{context}] Error: 'set' requires key and value")
            return
        key, val = arg.split(maxsplit=1)
        # Strip quotes if present (mimic shell behavior)
        val = val.strip('"').strip("'")
        key = key.lower()
        
        if key in ('out', 'output_folder'): 
            state['out'] = val
            # Ensure target directory exists
            if val and not val.startswith('$'):
                os.makedirs(val, exist_ok=True)
        elif key == 'note': state['note'] = resolve_rand_note(val)
        elif key == 'genre': 
            if val.lower() == 'rand':
                state['genre'] = random.choice(GENRE_CHOICES)
            else:
                state['genre'] = val
        elif key == 'duration': state['duration'] = resolve_rand_float(val, 0.5, 5.0)
        elif key in ('exact', 'exact_mode'): 
            state['exact'] = val.lower() == 'true'
        elif key == 'passes': state['passes'] = resolve_rand_int(val, 1, 10)
        elif key == 'count': state['count'] = resolve_rand_int(val, 1, 100)
        elif key == 'progression': state['progression'] = val
        elif key == 'loop': state['loop'] = (val.lower() == 'true')
        elif key == 'zeroc': state['zeroc'] = (val.lower() == 'true')
        elif key == 'fxpreset': state['fxpreset'] = val
        
        # FX setters
        elif key == 'fx-only':
            state['fx_rules']['only'] = parse_fx_string(val)
        elif key == 'fx-include':
            state['fx_rules']['include'] = parse_fx_string(val)
        elif key == 'fx-exclude':
            parsed = parse_fx_string(val)
            state['fx_rules']['exclude'] = [p['type'] for p in parsed]

        # Oscillator setters
        elif key == 'osc-only':
            state['osc_rules']['only'] = val.split(',')
        elif key == 'osc-include':
            state['osc_rules']['include'] = val.split(',')
        elif key == 'osc-exclude':
            state['osc_rules']['exclude'] = val.split(',')

        # Advanced controls
        elif key == 'seed':
            try:
                s = int(val)
                print(f"[{context}] Seeding RNG with {s}")
                random.seed(s)
                np.random.seed(s)
            except ValueError:
                print(f"[{context}] Error: Invalid seed '{val}'")
        
        elif key == 'scale':
            state['scale'] = val

        elif key == 'lfo-rate':
            try:
                parts = [float(x) for x in val.split(',')]
                state['lfo_rules']['rate'] = tuple(parts) if len(parts) > 1 else (parts[0], parts[0])
            except ValueError:
                print(f"[{context}] Error: invalid lfo-rate format")

        elif key == 'lfo-depth':
            try:
                parts = [float(x) for x in val.split(',')]
                state['lfo_rules']['depth'] = tuple(parts) if len(parts) > 1 else (parts[0], parts[0])
            except ValueError:
                print(f"[{context}] Error: invalid lfo-depth format")

        elif key == 'round-robin':
            state['round_robin'] = (val.lower() == 'true')

        elif key == 'macro':
            state['macro'] = resolve_rand_macro(val)

        elif key == 'wavetable':
            state['wavetable'] = (val.lower() == 'true')

        elif key == 'sample':
            state['sample'] = val
        elif key == 'sample-folder':
            state['sample_folder'] = val
        elif key == 'destructive':
            state['destructive'] = (val.lower() == 'true')

        elif key == 'nitro':
            state['nitro'] = val

        elif key == 'bus':
            # e.g. bus lead:saw>reverb
            # Check if this bus ID already exists and replace it, or just append?
            # Append is safer for now, but user might want to clear.
            # Let's add 'clear_buses' command or handle 'bus clear'
            if val.lower() == 'clear':
                state['bus_rules'] = []
                print(f"[{context}] Cleared all buses.")
            else:
                parsed = parse_bus_string(val)
                if parsed:
                    state['bus_rules'].append(parsed)
                    print(f"[{context}] Added bus '{parsed['id']}'")

        else:
            print(f"[{context}] Warning: Unknown setting '{key}'")

    elif cmd == 'bus':
        # Alias for 'set bus ...' but handles 'bus clear' intuitively
        if arg.lower() == 'clear':
            state['bus_rules'] = []
            print(f"[{context}] Cleared all buses.")
        else:
            parsed = parse_bus_string(arg)
            if parsed:
                state['bus_rules'].append(parsed)
                print(f"[{context}] Added bus '{parsed['id']}'")

    elif cmd == 'osc':
        # Alias for 'set osc-only ...'
        # Clean arg: remove redundant 'only' or quotes
        cleaned_arg = arg.strip().replace('only', '').replace('"', '').replace("'", "").strip()
        state['osc_rules']['only'] = [x.strip() for x in cleaned_arg.split(',') if x.strip()]
        print(f"[{context}] Target Oscillators: {state['osc_rules']['only']}")

    elif cmd == 'exact':
        # Alias for 'set exact true' or 'set exact false'
        state['exact'] = (arg.lower() != 'false')
        print(f"[{context}] Exact Mode: {state['exact']}")

    elif cmd == 'generate':
        try:
            if state['scale'] and state['passes']:
                 execute_scale_sweep(scale=state['scale'], passes=state['passes'], out=state['out'],
                                     duration=state['duration'], genre=state['genre'], note=state['note'],
                                     fx_rules=state['fx_rules'], osc_rules=state['osc_rules'], 
                                     lfo_rules=state['lfo_rules'], bus_rules=state['bus_rules'],
                                     loop=state['loop'], zeroc=state['zeroc'], 
                                     nitro=(str(state['nitro']).lower() == 'true'),
                                     exact=state.get('exact', False))
            else:
                 cnt = int(arg) if arg else state['count']
                 execute_generation(count=cnt,
                                    out=state['out'],
                                    note=state['note'],
                                    duration=state['duration'],
                                    genre=state['genre'],
                                    fx_rules=state['fx_rules'],
                                    osc_rules=state['osc_rules'],
                                    lfo_rules=state['lfo_rules'],
                                    scale=state['scale'],
                                    loop=state['loop'],
                                    zeroc=state['zeroc'],
                                    round_robin=state['round_robin'],
                                    macro_spec=state['macro'],
                                    wavetable_export=state['wavetable'],
                                    sample_path=state['sample'],
                                    sample_folder=state['sample_folder'],
                                    destructive=state['destructive'],
                                    fxpreset=state['fxpreset'],
                                    bus_rules=state['bus_rules'],
                                    nitro=(str(state['nitro']).lower() == 'true'),
                                    exact=state.get('exact', False))
        except Exception as e:
            print(f"[{context}] Error during generation: {e}")
        
        if state['nitro'] and convert_to_nitro:
           if os.path.exists(state['nitro']) and state['nitro'].lower() != 'true':
               convert_to_nitro(state['nitro'])
                            
    elif cmd == 'progression':
        prog = arg.strip('"').strip("'")
        try:
            execute_progression(progression=prog,
                                passes=state['passes'] if state['passes'] is not None else 5,
                                out=state['out'],
                                duration=state['duration'],
                                genre=state['genre'],
                                fx_rules=state['fx_rules'],
                                osc_rules=state['osc_rules'],
                                lfo_rules=state['lfo_rules'],
                                scale=state['scale'],
                                loop=state['loop'],

                                zeroc=state['zeroc'],
                                bus_rules=state['bus_rules'],
                                nitro=(str(state['nitro']).lower() == 'true'),
                                exact=state.get('exact', False))
        except Exception as e:
            print(f"[{context}] Error during progression: {e}")

        if state['nitro'] and convert_to_nitro:
           if os.path.exists(state['nitro']) and state['nitro'].lower() != 'true':
               convert_to_nitro(state['nitro'])
    elif cmd == 'run':
        # Recursive script execution
        script_file = arg.strip('"').strip("'")
        if os.path.exists(script_file):
            run_script(script_file)
        else:
             print(f"[{context}] Error: Script '{script_file}' not found.")
    else:
         print(f"[{context}] Warning: Unknown command '{cmd}'")


def run_script(filename):
    """Parse and execute a .psy or .psy2 script file."""
    print(f"[FiggyGen] Running script: {filename}")

    # PSY2 files use the new lexer/parser/evaluator pipeline
    if filename.endswith('.psy2'):
        try:
            from psy2.evaluator import evaluate
            with open(filename, 'r') as f:
                source = f.read()
            result = evaluate(source)
            state = result['state']

            if result.get('should_generate'):
                all_fx = []
                all_osc = set()
                for bus_rule in result.get('bus_rules', []):
                    for fx in bus_rule.get('effects', []):
                        all_fx.append({'type': fx['type'], 'params': fx.get('params', {})})
                    for osc in bus_rule.get('oscillators', []):
                        all_osc.add(osc)

                fx_rules = {'only': all_fx} if all_fx else {}
                osc_rules = {'only': list(all_osc)} if all_osc else {}
                lfo_rules = state.get('lfo_rules', {})

                seed = state.get('seed')
                if seed is not None:
                    import random
                    import numpy as np
                    print(f"[FiggyGen] Seeding RNG with {seed}")
                    random.seed(seed)
                    np.random.seed(seed)

                progression = state.get('progression', None)
                if progression and str(progression).strip():
                    from pySynth.main import execute_progression
                    execute_progression(
                        progression=str(progression),
                        passes=state.get('passes', state.get('count', 1)),
                        out=state.get('out', './output'),
                        duration=state.get('duration', 4.0),
                        genre=state.get('genre', 'pad'),
                        fx_rules=fx_rules,
                        osc_rules=osc_rules,
                        lfo_rules=lfo_rules,
                        bus_rules=result.get('bus_rules', []),
                        scale=state.get('scale', None),
                        loop=state.get('loop', False),
                        zeroc=state.get('zeroc', False),
                        nitro=state.get('nitro', False),
                        exact=state.get('exact', False),
                    )
                elif state.get('scale') and state.get('passes'):
                    from pySynth.main import execute_scale_sweep
                    execute_scale_sweep(
                        scale=state['scale'],
                        passes=state['passes'],
                        out=state.get('out', './output'),
                        duration=state.get('duration', 4.0),
                        genre=state.get('genre', 'pad'),
                        note=state.get('note', 'C4'),
                        fx_rules=fx_rules,
                        osc_rules=osc_rules,
                        lfo_rules=lfo_rules,
                        bus_rules=result.get('bus_rules', []),
                        loop=state.get('loop', False),
                        zeroc=state.get('zeroc', False),
                        nitro=state.get('nitro', False),
                        exact=state.get('exact', False),
                    )
                else:
                    execute_generation(
                        count=state.get('count', 1),
                        out=state.get('out', './output'),
                        note=state.get('note', None),
                        duration=state.get('duration', 4.0),
                        genre=state.get('genre', 'pad'),
                        fx_rules=fx_rules,
                        osc_rules=osc_rules,
                        lfo_rules=lfo_rules,
                        bus_rules=result.get('bus_rules', []),
                        scale=state.get('scale', None),
                        loop=state.get('loop', False),
                        zeroc=state.get('zeroc', False),
                        round_robin=state.get('round_robin', False),
                        macro_spec=state.get('macro', None),
                        wavetable_export=state.get('wavetable', False),
                        sample_path=state.get('sample', None),
                        sample_folder=state.get('sample_folder', None),
                        destructive=state.get('destructive', False),
                        fxpreset=state.get('fxpreset', None),
                        nitro=state.get('nitro', False),
                        exact=state.get('exact', False),
                    )
        except Exception as e:
            print(f"[FiggyGen] PSY2 error: {e}")
        return

    # Old .psy format — line-by-line
    state = get_default_state()

    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"[FiggyGen] Error: Script file '{filename}' not found.")
        return

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        execute_interpreter_command(cmd, arg, state, f"Script L{line_num}")


def run_editor(filename):
    """Simple line-based built-in editor for .psy scripts."""
    print(f"\n[FiggyGen Editor] Editing: {filename}")
    print("Commands: [num] content (repl), + content (add), - num (del), ins num content, save, run, help, exit\n")
    
    lines = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = [line.rstrip('\n') for line in f.readlines()]
        except Exception as e:
            print(f"Error reading file: {e}")

    while True:
        # Display
        if not lines:
            print("  (Empty file)")
        else:
            for i, line in enumerate(lines, 1):
                print(f"{i:3} | {line}")
        
        try:
            cmd_line = input("\nediting> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting editor (unsaved).")
            break
            
        if not cmd_line: continue
        
        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == 'exit':
            break
        elif cmd == 'help':
            print("\n── Editor Commands ──")
            print("  [number] [text]    - Replace line at [number]")
            print("  + [text]           - Append line to end")
            print("  - [number]         - Delete line at [number]")
            print("  ins [number] [txt] - Insert line before [number]")
            print("  save               - Write changes to disk")
            print("  run                - Execute current buffer without saving")
            print("  exit               - Return to program\n")
        elif cmd == 'save':
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("\n".join(lines) + ("\n" if lines else ""))
                print(f"Saved to {filename}")
            except Exception as e:
                print(f"Error saving file: {e}")
        elif cmd == 'run':
            print(f"Running current buffer...")
            state = get_default_state()
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'): continue
                p = line.split(maxsplit=1)
                c = p[0].lower()
                a = p[1] if len(p) > 1 else ""
                execute_interpreter_command(c, a, state, f"Buffer L{line_num}")
                if 'exit' in c: break
        elif cmd == '+':
            lines.append(arg)
        elif cmd == '-':
            try:
                idx = int(arg) - 1
                if 0 <= idx < len(lines):
                    del lines[idx]
                else:
                    print("Invalid line number.")
            except ValueError:
                print("Usage: - [line_number]")
        elif cmd == 'ins':
            try:
                subparts = arg.split(maxsplit=1)
                idx = int(subparts[0]) - 1
                content = subparts[1] if len(subparts) > 1 else ""
                lines.insert(max(0, min(len(lines), idx)), content)
            except (ValueError, IndexError):
                 print("Usage: ins [line_number] [content]")
        elif cmd.isdigit():
            # Replace line
            try:
                idx = int(cmd) - 1
                if 0 <= idx < len(lines):
                    lines[idx] = arg
                elif idx == len(lines):
                    lines.append(arg)
                else:
                    print("Line number out of range. Use '+' to append.")
            except ValueError:
                print("Invalid format.")
        else:
            print("Unknown editor command. Type 'help' for options.")



