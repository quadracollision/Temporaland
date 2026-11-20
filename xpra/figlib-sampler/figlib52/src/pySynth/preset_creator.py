import os
import json
import sys

# Available options for validation/prompting
WAVEFORMS = ['saw', 'square', 'pulse', 'sine', 'morph', 'supersaw', 
             'triangle', 'noise_white', 'noise_pink', 'wavetable']
FILTER_TYPES = ['lowpass', 'highpass', 'bandpass', 'notch', 'peaking', 'low_shelf', 'high_shelf']
LFO_TARGETS = ['pitch', 'filter', 'amp', 'pan']
LFO_SHAPES = ['sine', 'triangle', 'square', 'saw', 'sample_hold', 'random_walk']

# Common FX categories for display
FX_CATEGORIES = {
    'Basic': ['distortion', 'bitcrush', 'chorus', 'flanger', 'phaser', 'delay', 'reverb'],
    'Dynamics': ['compressor', 'limiter', 'gate', 'transient'],
    'Filter/EQ': ['filter', 'moog', '303', 'sem', 'neve', 'pultec'],
    'Creative': ['lofi', 'stutter', 'glitch', 'shimmer', 'tape', 'vinyl', 'reverse'],
    'Space': ['stereo_widen', 'haas', 'ring_mod', 'freq_shift'],
}

def get_input(prompt, default=None, val_type=str, valid_options=None):
    """Helper to get and validate user input."""
    while True:
        p_str = f"{prompt} [{default}]: " if default is not None else f"{prompt}: "
        user_in = input(p_str).strip()
        
        if not user_in:
            if default is not None:
                return default
            print("  Value required.")
            continue
            
        # Type conversion
        try:
            if val_type == list:
                # Comma separated
                val = [x.strip() for x in user_in.split(',') if x.strip()]
            elif val_type == float:
                val = float(user_in)
            elif val_type == int:
                val = int(user_in)
            else:
                val = user_in
        except ValueError:
            print(f"  Invalid type. Expected {val_type.__name__}.")
            continue
            
        # Option validation
        if valid_options:
            if isinstance(val, list):
                if not all(v in valid_options for v in val):
                    print(f"  Invalid option(s). Allowed: {', '.join(valid_options)}")
                    continue
            else:
                if val not in valid_options:
                    print(f"  Invalid option. Allowed: {', '.join(valid_options)}")
                    continue
                    
        return val

def create_preset_wizard(preset_name=None):
    """Run the interactive preset creator wizard."""
    print("\n╔════════════════════════════════════╗")
    print("║     pySynth Preset Creator         ║")
    print("╚════════════════════════════════════╝\n")
    
    if not preset_name:
        preset_name = get_input("Preset Name (e.g., 'dark_bass')")
    
    # Ensure filename safety
    safe_name = "".join(x for x in preset_name if x.isalnum() or x in "_-").lower()
    filepath = os.path.join("presets", f"{safe_name}.psi")
    
    if os.path.exists(filepath):
        overwrite = get_input(f"Preset '{safe_name}' exists. Overwrite?", default="n", valid_options=["y", "n"])
        if overwrite.lower() != 'y':
            print("Cancelled.")
            return

    data = {}

    # ── Oscillators ──
    print("\n[1/5] Oscillators")
    data['osc_waveforms'] = get_input("Waveforms (comma-sep)", default="saw,square", val_type=list, valid_options=WAVEFORMS)
    
    min_osc = get_input("Min Oscillator Count", default=1, val_type=int)
    max_osc = get_input("Max Oscillator Count", default=2, val_type=int)
    data['osc_count'] = [min_osc, max_osc]
    
    min_freq = get_input("Freq Range Min (Hz)", default=40, val_type=int)
    max_freq = get_input("Freq Range Max (Hz)", default=400, val_type=int)
    data['freq_range'] = [min_freq, max_freq]
    
    data['unison_range'] = [1, get_input("Max Unison Voices", default=3, val_type=int)]
    data['unison_detune'] = [5, get_input("Max Unison Detune (cents)", default=15, val_type=int)]

    # ── Filters ──
    print("\n[2/5] Filters")
    data['filter_prob'] = get_input("Filter Probability (0.0-1.0)", default=0.7, val_type=float)
    if data['filter_prob'] > 0:
        data['filter_types'] = get_input("Filter Types", default="lowpass", val_type=list, valid_options=FILTER_TYPES)
        min_cut = get_input("Cutoff Min (Hz)", default=200, val_type=int)
        max_cut = get_input("Cutoff Max (Hz)", default=5000, val_type=int)
        data['cutoff_range'] = [min_cut, max_cut]

    # ── Envelope ──
    print("\n[3/5] Envelope (ADSR)")
    # Defaults
    data['envelope'] = {
        'attack': [0.001, 0.05], 'hold': [0.0, 0.0], 'decay': [0.1, 0.5],
        'sustain': [0.5, 1.0], 'release': [0.1, 0.5]
    }
    # Optional prompt for detail
    if get_input("Customize Envelope ranges?", default="n", valid_options=["y", "n"]) == "y":
        data['envelope']['attack'][0] = get_input("Attack Min (s)", default=0.001, val_type=float)
        data['envelope']['attack'][1] = get_input("Attack Max (s)", default=0.05, val_type=float)
        data['envelope']['decay'][0] = get_input("Decay Min (s)", default=0.1, val_type=float)
        data['envelope']['decay'][1] = get_input("Decay Max (s)", default=0.5, val_type=float)
        data['envelope']['release'][0] = get_input("Release Min (s)", default=0.1, val_type=float)
        data['envelope']['release'][1] = get_input("Release Max (s)", default=0.5, val_type=float)

    # ── LFO ──
    print("\n[4/5] LFO")
    data['lfo'] = {'prob': 0.0, 'rate': [1,1], 'amount': [0,0], 'shapes': ['sine'], 'targets': []}
    data['lfo']['prob'] = get_input("LFO Probability (0.0-1.0)", default=0.5, val_type=float)
    
    if data['lfo']['prob'] > 0:
        data['lfo']['targets'] = get_input("Targets", default="filter", val_type=list, valid_options=LFO_TARGETS)
        data['lfo']['shapes'] = get_input("Shapes", default="sine,triangle", val_type=list, valid_options=LFO_SHAPES)
        data['lfo']['rate'] = [
            get_input("Rate Min (Hz)", default=0.5, val_type=float),
            get_input("Rate Max (Hz)", default=5.0, val_type=float)
        ]
        data['lfo']['amount'] = [0.1, get_input("Max Amount (0.0-1.0)", default=0.5, val_type=float)]

    # ── FX ──
    print("\n[5/5] Effects")
    print("Available Categories:")
    for cat, effs in FX_CATEGORIES.items():
        print(f"  {cat}: {', '.join(effs)}")
    
    data['fx_pool'] = get_input("FX Pool (comma-sep)", default="distortion,chorus,reverb", val_type=list)
    data['reverb_prob'] = get_input("Reverb Prob", default=0.3, val_type=float)
    data['delay_prob'] = get_input("Delay Prob", default=0.2, val_type=float)

    # Save
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"\n[Success] Preset saved to: {filepath}")
        print(f"Use it with: python run.py --genre {safe_name}")
    except Exception as e:
        print(f"\n[Error] Failed to save preset: {e}")

if __name__ == "__main__":
    create_preset_wizard()

