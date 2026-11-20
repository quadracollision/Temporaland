"""
pySynth CLI – The FiggyGen command-line interface.
"""
import argparse
import sys
import os
import random
import numpy as np

from pySynth.main import (
    get_default_state, run_script, execute_generation, 
    execute_progression, execute_scale_sweep, execute_interpreter_command,
    print_effect_info
)
from pySynth.generator import Oscillator, load_presets
from pySynth.synth import EFFECT_DISPATCH
from pySynth.utils.music_theory import SCALES as MUSIC_SCALES
from pySynth.parsing import (
    parse_fx_string, parse_bus_string, resolve_rand_macro,
    resolve_rand_float, resolve_rand_int, resolve_rand_note,
    FX_PARAM_RANGES
)

try:
    from pySynth.utils.nitro import convert_to_nitro
except ImportError:
    convert_to_nitro = None

PRESETS = load_presets()
GENRE_CHOICES = list(PRESETS.keys())

def _build_cli_parser():
    """Build and return the argparse parser for CLI mode."""
    import shlex
    parser = argparse.ArgumentParser(
        prog='figgygen',
        description="FiggyGen CLI Mode",
        exit_on_error=False,  # Don't sys.exit on parse errors
    )
    parser.add_argument('--count', type=str, default='10')
    parser.add_argument('--out', type=str, default='./samples')
    parser.add_argument('--note', type=str, default='C4')
    parser.add_argument('--duration', type=str, default='2.0')
    parser.add_argument('--genre', type=str, default=None)
    parser.add_argument('--progression', type=str, default=None)
    parser.add_argument('--passes', type=str, default=None)
    parser.add_argument('--fxpreset', type=str, default=None)
    parser.add_argument('--fx-only', type=str, default=None)
    parser.add_argument('--fx-include', type=str, default=None)
    parser.add_argument('--fx-exclude', type=str, default=None)
    parser.add_argument('--osc-only', type=str, default=None)
    parser.add_argument('--osc-include', type=str, default=None)
    parser.add_argument('--osc-exclude', type=str, default=None)
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--lfo-rate', type=str, default=None)
    parser.add_argument('--lfo-depth', type=str, default=None)
    parser.add_argument('--scale', type=str, default=None)
    parser.add_argument('--sample', type=str, default=None)
    parser.add_argument('--sample-folder', type=str, default=None)
    parser.add_argument('--destructive', action='store_true')
    parser.add_argument('--loop', action='store_true')
    parser.add_argument('--zeroc', action='store_true')
    parser.add_argument('--round-robin', action='store_true')
    parser.add_argument('--macro', type=str, default=None)
    parser.add_argument('--wavetable', action='store_true')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--fx-list', action='store_true')
    parser.add_argument('--osc-list', action='store_true')
    parser.add_argument('--bus', action='append', default=[])
    parser.add_argument('--nitro', nargs='?', const='true', default=None)
    parser.add_argument('--info', nargs='?', const='all', default=None,
                        help='Show info for a specific effect (e.g. --info reverb) or list all.')
    parser.add_argument('--edit', type=str, default=None,
                        help='Open the built-in script editor for a .psy file.')
    return parser


def _execute_cli_line(line, cli_parser):
    """Parse and execute a single CLI-style command line."""
    import shlex
    try:
        argv = shlex.split(line)
    except ValueError as e:
        print(f"[CLI] Parse error: {e}")
        return

    try:
        args = cli_parser.parse_args(argv)
    except (SystemExit, argparse.ArgumentError) as e:
        # argparse prints its own error; just catch the exit
        return

    # Handle Info Command (Interactive)
    if args.info:
        print_effect_info(args.info)
        return

    if args.edit:
        from pySynth.main import run_editor
        run_editor(args.edit)
        return



    # List modes
    if args.list:
        print(f"\n[ Genres ] ({len(GENRE_CHOICES)})")
        print(", ".join(sorted(GENRE_CHOICES)))
        print(f"\n[ Oscillators ] ({len(Oscillator.WAVEFORMS)})")
        print(", ".join(sorted(Oscillator.WAVEFORMS)))
        print(f"\n[ Effects ] ({len(EFFECT_DISPATCH)})")
        print(", ".join(sorted(EFFECT_DISPATCH.keys())))
        return

    if args.fx_list:
        from pySynth.main import print_fx_list
        print_fx_list()
        return

    if args.osc_list:
        print(f"\n[ Oscillators ] ({len(Oscillator.WAVEFORMS)})")
        print(", ".join(sorted(Oscillator.WAVEFORMS)))
        return

    # Seed
    if args.seed is not None:
        print(f"[CLI] Seeding RNG with {args.seed}")
        random.seed(args.seed)
        np.random.seed(args.seed)

    # Resolve values
    final_count = resolve_rand_int(args.count, 1, 50)
    final_duration = resolve_rand_float(args.duration, 0.5, 5.0)
    final_passes = resolve_rand_int(args.passes, 1, 10) if args.passes else None
    final_note = resolve_rand_note(args.note)
    final_genre = args.genre
    if final_genre and final_genre.lower() == 'rand':
        final_genre = random.choice(GENRE_CHOICES)
    final_macro = resolve_rand_macro(args.macro)

    # Build rules
    fx_rules = {}
    if args.fx_only:
        fx_rules['only'] = parse_fx_string(args.fx_only)
    if args.fx_include:
        fx_rules['include'] = parse_fx_string(args.fx_include)
    if args.fx_exclude:
        parsed = parse_fx_string(args.fx_exclude)
        fx_rules['exclude'] = [p['type'] for p in parsed]

    osc_rules = {
        'only': args.osc_only.split(',') if args.osc_only else [],
        'include': args.osc_include.split(',') if args.osc_include else [],
        'exclude': args.osc_exclude.split(',') if args.osc_exclude else []
    }

    lfo_rules = {}
    if args.lfo_rate:
        try:
            parts = [float(x) for x in args.lfo_rate.split(',')]
            lfo_rules['rate'] = tuple(parts) if len(parts) > 1 else (parts[0], parts[0])
        except ValueError:
            print("[CLI] Error: invalid --lfo-rate format")
    if args.lfo_depth:
        try:
            parts = [float(x) for x in args.lfo_depth.split(',')]
            lfo_rules['depth'] = tuple(parts) if len(parts) > 1 else (parts[0], parts[0])
        except ValueError:
            print("[CLI] Error: invalid --lfo-depth format")

    # Bus Rules
    bus_rules = []
    if args.bus:
         for b in args.bus:
             parsed = parse_bus_string(b)
             if parsed:
                 bus_rules.append(parsed)

    # Execute
    try:
        if args.progression:
            execute_progression(progression=args.progression,
                                passes=final_passes, out=args.out,
                                duration=final_duration, genre=final_genre,
                                fx_rules=fx_rules, osc_rules=osc_rules,
                                lfo_rules=lfo_rules, bus_rules=bus_rules, scale=args.scale,
                                loop=args.loop, zeroc=args.zeroc,
                                nitro=(args.nitro == 'true'))
        elif args.scale and final_passes:
             # Scale Sweep from CLI
             execute_scale_sweep(scale=args.scale, passes=final_passes, out=args.out,
                                 duration=final_duration, genre=final_genre, note=final_note,
                                 fx_rules=fx_rules, osc_rules=osc_rules, lfo_rules=lfo_rules, bus_rules=bus_rules,
                                 loop=args.loop, zeroc=args.zeroc, nitro=(args.nitro == 'true'))
        else:
            execute_generation(count=final_count, out=args.out,
                               note=final_note, duration=final_duration,
                               genre=final_genre, fx_rules=fx_rules,
                               osc_rules=osc_rules, lfo_rules=lfo_rules, bus_rules=bus_rules,
                               scale=args.scale, loop=args.loop,
                               zeroc=args.zeroc,
                               round_robin=args.round_robin,
                               macro_spec=final_macro,
                               wavetable_export=args.wavetable,
                               sample_path=args.sample,
                               sample_folder=args.sample_folder,
                               destructive=args.destructive,
                               fxpreset=args.fxpreset,
                               nitro=(args.nitro == 'true'))
        
        # Post-process nitro if it's a path
        if args.nitro and args.nitro != 'true' and convert_to_nitro:
             if os.path.exists(args.nitro):
                 convert_to_nitro(args.nitro)
    except Exception as e:
        print(f"[CLI] Error during generation: {e}")


def run_repl():
    """Run an interactive dual-mode session (REPL scripting + CLI args)."""
    print(r"""
  __ _       _ _ _     
 / _(_) __ _| (_) |__  
| |_| |/ _` | | | '_ \ 
|  _| | (_| | | | |_) |
|_| |_|\__, |_|_|_.__/ 
       |___/           
    (C) Quadracollision 2026
    """)
    print("Mode: REPL (scripting). Type 'help' for commands.")
    print("Type 'cli' to switch to CLI arg mode, 'exit' to quit.\n")
    
    state = get_default_state()
    cli_parser = _build_cli_parser()
    mode = 'repl'  # 'repl' or 'cli'
    
    while True:
        prompt = "FG> " if mode == 'repl' else "CLI> "
        try:
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
            
        if not line or line.startswith('#'):
            continue

        # ── Universal commands (work in both modes) ──
        lower = line.lower().split()[0] if line.split() else ''

        if lower in ('exit', 'quit'):
            print("Exiting.")
            break

        if lower == 'cli' and mode == 'repl':
            mode = 'cli'
            print("[Switched to CLI mode] Type full --arg commands. Type 'repl' to switch back.")
            continue

        if lower == 'repl' and mode == 'cli':
            mode = 'repl'
            print("[Switched to REPL mode] Type set/generate commands. Type 'cli' to switch back.")
            continue

        if lower == 'run':
            parts = line.split(maxsplit=1)
            if len(parts) > 1:
                script_file = parts[1].strip('"').strip("'")
                run_script(script_file)
            else:
                print("[REPL] Error: 'run' requires a filename.")
            continue

        if lower == 'edit':
            parts = line.split(maxsplit=1)
            if len(parts) > 1:
                script_file = parts[1].strip('"').strip("'")
                from pySynth.main import run_editor
                run_editor(script_file)
            else:
                print("[REPL] Error: 'edit' requires a filename.")
            continue

        if lower in ('help', '--help', '-h'):
            if mode == 'repl':
                print("\n── REPL Mode Commands ──")
                print("  set [key] [value]   - Update a setting")
                print("  generate            - Generate batch with current settings")
                print("  progression '...'   - Generate progression")
                print("  state               - Show current configuration")
                print("  cli                 - Switch to CLI arg mode")
                print("  exit                - Quit")
                print("\nKeys: genre, note, duration, count, out, fx-only, fx-include,")
                print("      osc-only, seed, lfo-rate, round-robin, wavetable,")
                print("      sample, sample-folder, destructive, fxpreset\n")
            else:
                print("\n── CLI Mode ──")
                print("Type commands with --flags, e.g.:")
                print("  --count 5 --genre pad --note C4")
                print("  --sample ./kick.wav --fxpreset tape_warmth --count 1")
                print("  --list")
                print("  --fx-list")
                print("  repl                - Switch back to REPL mode")
                print("  exit                - Quit\n")
                cli_parser.print_help()
                print()
            continue

        # ── Mode-specific execution ──
        if mode == 'repl':
            if lower == 'state':
                import pprint
                pprint.pprint(state)
                continue
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            execute_interpreter_command(cmd, arg, state, "REPL")
        else:
            # CLI mode: parse as argparse args
            _execute_cli_line(line, cli_parser)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main():
    # Check for edit arg in sys.argv (simple check)
    if '--edit' in sys.argv:
        idx = sys.argv.index('--edit')
        if idx + 1 < len(sys.argv):
            from pySynth.main import run_editor
            run_editor(sys.argv[idx+1])
            return

    # Check for script file in args (simple check before full argparse)
    # If first arg ends in .psy, treat as script
    if len(sys.argv) > 1 and sys.argv[1].endswith(('.psy', '.psy2')):
        run_script(sys.argv[1])
        return

    parser = argparse.ArgumentParser(
        description="figlib, a modular sample generation and fx engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python run.py --count 20 --genre pad --note C4
  python run.py --count 10 --note C4E4G4          # C major chord
  python run.py --count 5 --note "C4 E3 F#4 G3"   # space-separated

Chord Progressions:
  python run.py --progression "C4E4G4|A3C4E4|F3A3C4|G3B3D4" --passes 5

Oscillator:
  python run.py --osc-only saw,square,triangle,noise

FX Filtering:
  python run.py --fx-list                          # show all effects
  python run.py --fx-only moog,reverb,tape         # use ONLY these
  python run.py --fx-exclude marshall,distortion   # never use these
  python run.py --fx-include fairchild,ssl         # always include these

Scripting:
  python run.py my_script.psy      # Run a script file
""")
    parser.add_argument('script', nargs='?', help="Optional .psy script file to run")
    parser.add_argument('--count', type=str, default='10',
                        help="Number of samples to generate (default: 10, or 'rand')")
    parser.add_argument('--out', type=str, default='./samples',
                        help="Output directory (default: ./samples)")
    parser.add_argument('--note', type=str, default='C4',
                        help="Note(s) / chord.  E.g. C4, 'rand', C4E4G4")
    parser.add_argument('--duration', type=str, default='2.0',
                        help="Duration in seconds (default: 2.0, or 'rand')")
    parser.add_argument('--genre', type=str, default=None,
                        help="Genre preset (default: random mix, or 'rand' to pick one)")
    parser.add_argument('--progression', type=str, default=None,
                        help="Chord progression separated by |.  "
                             "E.g. 'C4E4G4|A3C4E4|F3A3C4|G3B3D4'")
    parser.add_argument('--passes', type=str, default=None,
                        help="Number of parameter passes for progressions (default: 5, or 'rand')")
    parser.add_argument('--fxpreset', type=str, default=None,
                        help="Use an FX-only preset (from fxpresets folder) to override genre FX/Env/LFO settings.")

    # FX filtering
    parser.add_argument('--fx-list', action='store_true',
                        help="Show all available effects and exit")
    parser.add_argument('--fx-only', type=str, default=None,
                        help="Comma-separated: use ONLY these effects.")
    parser.add_argument('--fx-include', type=str, default=None,
                        help="Comma-separated: always include these effects.")
    parser.add_argument('--fx-exclude', type=str, default=None,
                        help="Comma-separated: never use these effects.")

    # Oscillator Control
    parser.add_argument('--osc-only', type=str, default=None,
                        help="Comma-separated: use ONLY these oscillators.")
    parser.add_argument('--osc-include', type=str, default=None,
                        help="Comma-separated: also include these oscillators.")
    parser.add_argument('--repl', action='store_true',
                        help="Run in interactive REPL mode.")
    parser.add_argument('--osc-exclude', type=str, default=None,
                        help="Comma-separated: never use these oscillators.")
    parser.add_argument('--osc-list', action='store_true',
                        help="Show all available oscillators and exit.")

    # Bus Routing
    parser.add_argument('--bus', action='append', default=[],
                        help="Define a bus: 'id:oscs>fx'. E.g. --bus 'lead:saw,square>delay,reverb'")

    # Advanced Control
    parser.add_argument('--seed', type=int, default=None,
                        help="Random seed for deterministic generation.")
    parser.add_argument('--lfo-rate', type=str, default=None,
                        help="Override LFO rate range (min,max e.g. '0.1,1.0').")
    parser.add_argument('--lfo-depth', type=str, default=None,
                        help="Override LFO depth range (min,max e.g. '0.5,1.0').")
    parser.add_argument('--scale', type=str, default=None,
                        help="Quantize notes to scale (e.g. 'major', 'minor', 'pentatonic').")
    parser.add_argument('--list', action='store_true',
                        help="List all available oscillators, effects, scales, and genres.")

    # Interactive tools
    parser.add_argument('--create-preset', nargs='?', const=True, default=None,
                        help="Launch interactive preset creator wizard. Optional: provide preset name.")

    parser.add_argument('--gui', action='store_true',
                        help="Launch the simple GUI frontend.")

    parser.add_argument('--ide', action='store_true',
                        help="Launch the advanced patching IDE.")

    # Sample Processing
    parser.add_argument('--sample', type=str, default=None,
                        help="Path to input .wav file to use as oscillator source.")
    parser.add_argument('--sample-folder', type=str, default=None,
                        help="Path to input folder to recursively process samples.")
    parser.add_argument('--destructive', action='store_true',
                        help="Overwrite input files (destructive processing).")
    parser.add_argument('--copy', action='store_true', default=True,
                        help="Save processed files to output directory (default).")

    parser.add_argument('--nitro', nargs='?', const='true', default=None,
                        help="Convert a folder of samples to DS format (16kHz/Mono/16-bit).")
    
    parser.add_argument('--loop', action='store_true',
                        help="Optimize duration for perfect looping (integer cycles).")

    parser.add_argument('--zeroc', action='store_true',
                        help="Apply zero-crossing fade in/out to prevent clicking.")


    parser.add_argument('--round-robin', action='store_true',
                        help="Generate variations of a single patch (Drift Mode).")
    parser.add_argument('--macro', type=str, default=None,
                        help="Macro Mod config: 'rate=0.5,depth=1.0,targets=filter:cutoff:0.5'")
    parser.add_argument('--exact', action='store_true',
                        help="Disable randomization for deterministic output.")
    parser.add_argument('--wavetable', action='store_true',
                            help="Export 64-frame 2048-sample wavetable (Serum format).")
    
    parser.add_argument('--info', nargs='?', const='all', default=None,
                        help='Show info for a specific effect (e.g. --info reverb) or list all.')


    args = parser.parse_args()

    # Handle Info Command
    if args.info:
        print_effect_info(args.info)
        return

    # REPL Mode
    if args.repl:
        run_repl()
        return

    # Force REPL if no args? Or just help?
    # If no args are passed, argparse typically prints help or exits? No, it defaults.
    # User might want to double-cick a build.
    # If len(sys.argv) == 1, maybe default to REPL?
    if len(sys.argv) == 1:
        run_repl()
        return

    # ── FX list mode ──
    if args.list:
        print("\n=== 🎹 FiggyGen Resource List ===")
        
        print(f"\n[ Genres ] ({len(GENRE_CHOICES)})")
        print(", ".join(sorted(GENRE_CHOICES)))
        
        print(f"\n[ Oscillators/Models ] ({len(Oscillator.WAVEFORMS)})")
        # Simple word wrap
        osc_list = sorted(Oscillator.WAVEFORMS)
        print(", ".join(osc_list))

        print(f"\n[ Effects ] ({len(EFFECT_DISPATCH)})")
        fx_list = sorted(EFFECT_DISPATCH.keys())
        print(", ".join(fx_list))

        print(f"\n[ Musical Scales ] ({len(MUSIC_SCALES)})")
        print(", ".join(sorted(MUSIC_SCALES.keys())))
        
        print("\n================================")
        return
    
    # If script arg provided
    if args.script and args.script.endswith('.psy'):
        run_script(args.script)
        return

    # ── GUI Mode ──
    if args.gui:
        from .gui import run_gui
        run_gui()
        return

    # ── IDE Mode ──
    if args.ide:
        from ide.editor import start_ide
        start_ide()
        return

    # ── Preset Creator ──
    if args.create_preset:
        from .preset_creator import create_preset_wizard
        # If user provided a name via --create-preset NAME, use it.
        # If they just used --create-preset (const=True), pass None.
        name = args.create_preset if isinstance(args.create_preset, str) else None
        create_preset_wizard(name)
        return

    # ── FX list mode ──
    if args.fx_list:
        from pySynth.main import print_fx_list
        print_fx_list()
        return

    # ── Osc list mode ──
    if args.osc_list:
        print(f"\n[ Oscillators/Models ] ({len(Oscillator.WAVEFORMS)})")
        print(", ".join(sorted(Oscillator.WAVEFORMS)))
        print("")
        return

    # ── Nitro Conversion ──
    # ── Nitro Conversion ──
    if args.nitro and args.nitro != 'true':
        if convert_to_nitro:
            if os.path.isdir(args.nitro):
                convert_to_nitro(args.nitro)
            else:
                print(f"[FiggyGen] Error: Directory '{args.nitro}' not found.")
        else:
            print("[FiggyGen] Error: Could not import nitro utility.")
        return


    # Set random seed if provided
    if args.seed is not None:
        print(f"[FiggyGen] Seeding RNG with {args.seed}")
        random.seed(args.seed)
        np.random.seed(args.seed)

    # Validating/Resolving CLI args
    
    # Resolve 'rand' or string numbers to actual types
    final_count = resolve_rand_int(args.count, 1, 50)
    final_duration = resolve_rand_float(args.duration, 0.5, 5.0)
    final_passes = resolve_rand_int(args.passes, 1, 10) if args.passes else None
    final_note = resolve_rand_note(args.note)
    
    final_genre = args.genre
    if final_genre and final_genre.lower() == 'rand':
        final_genre = random.choice(GENRE_CHOICES)

    final_macro = resolve_rand_macro(args.macro)

    # ── Build fx_rules ──
    fx_rules = {}
    if args.fx_only:
        fx_rules['only'] = parse_fx_string(args.fx_only)
    if args.fx_include:
        fx_rules['include'] = parse_fx_string(args.fx_include)
    if args.fx_exclude:
        # exclude is just a list of names, params don't matter (but we parse them to ignore)
        parsed = parse_fx_string(args.fx_exclude)
        fx_rules['exclude'] = [p['type'] for p in parsed]

    # Validate effect names
    all_valid = set(EFFECT_DISPATCH.keys())
    
    # Check 'only' and 'include' which are lists of dicts
    for key in ('only', 'include'):
        if key in fx_rules:
            # Filter out invalid effects and print warnings
            valid_list = []
            for item in fx_rules[key]:
                if item['type'] in all_valid:
                    valid_list.append(item)
                else:
                    print(f"[FiggyGen] Warning: unknown effect '{item['type']}' in --fx-{key}")
            fx_rules[key] = valid_list

    # Check 'exclude' which is a list of strings
    if 'exclude' in fx_rules:
        # Filter out invalid effects and print warnings
        valid_ex = []
        for name in fx_rules['exclude']:
            if name in all_valid:
                valid_ex.append(name)
            else:
                 print(f"[FiggyGen] Warning: unknown effect '{name}' in --fx-exclude")
        fx_rules['exclude'] = valid_ex

    # Build oscillator rules
    osc_rules = {
        'only': args.osc_only.split(',') if args.osc_only else [],
        'include': args.osc_include.split(',') if args.osc_include else [],
        'exclude': args.osc_exclude.split(',') if args.osc_exclude else []
    }

    # Build LFO rules
    lfo_rules = {}
    if args.lfo_rate:
        try:
            parts = [float(x) for x in args.lfo_rate.split(',')]
            lfo_rules['rate'] = tuple(parts) if len(parts) > 1 else (parts[0], parts[0])
        except ValueError:
            print("[FiggyGen] Error: invalid format for --lfo-rate (expected 'min,max')")
    if args.lfo_depth:
        try:
            parts = [float(x) for x in args.lfo_depth.split(',')]
            lfo_rules['depth'] = tuple(parts) if len(parts) > 1 else (parts[0], parts[0])
        except ValueError:
            print("[FiggyGen] Error: invalid format for --lfo-depth (expected 'min,max')")

    # Bus Rules
    bus_rules = []
    if args.bus:
         for b in args.bus:
             parsed = parse_bus_string(b)
             if parsed:
                 bus_rules.append(parsed)

    # ── Execution ──
    if args.progression:
        p_count = final_passes if final_passes is not None else 5
        execute_progression(progression=args.progression,
                            passes=p_count,
                            out=args.out,
                            duration=final_duration,
                            genre=final_genre,
                            fx_rules=fx_rules,
                            osc_rules=osc_rules,
                            lfo_rules=lfo_rules,
                            bus_rules=bus_rules,
                            scale=args.scale,
                            loop=args.loop,
                            zeroc=args.zeroc,
                            nitro=(args.nitro == 'true'),
                            exact=args.exact)
    elif args.scale and final_passes:
        execute_scale_sweep(scale=args.scale, passes=final_passes, out=args.out,
                            duration=final_duration, genre=final_genre, note=final_note,
                            fx_rules=fx_rules, osc_rules=osc_rules, lfo_rules=lfo_rules, bus_rules=bus_rules,
                            loop=args.loop, zeroc=args.zeroc, nitro=(args.nitro == 'true'), exact=args.exact)

    else:
        # Standard batch
        execute_generation(count=final_count,
                           out=args.out,
                           note=final_note,
                           duration=final_duration,
                           genre=final_genre,
                           fx_rules=fx_rules,
                           osc_rules=osc_rules,
                           lfo_rules=lfo_rules,
                           bus_rules=bus_rules,
                           scale=args.scale,
                           loop=args.loop,
                           zeroc=args.zeroc,
                           round_robin=args.round_robin,
                           macro_spec=final_macro,
                           wavetable_export=args.wavetable,
                           sample_path=args.sample,
                           sample_folder=args.sample_folder,
                           destructive=args.destructive,
                           fxpreset=args.fxpreset,
                           nitro=(args.nitro == 'true'),
                           exact=args.exact)


if __name__ == '__main__':
    main()

