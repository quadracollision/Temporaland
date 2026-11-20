"""
pySynth Generator – "The FiggyGen" Sample Factory.
Genre-aware intelligent randomization for massive sonic variety.
"""
import os
import random
import re
import math
import numpy as np
import scipy.signal
import soundfile as sf
import json
import glob
from .synth import FiggyGenSynth
from .oscillator import Oscillator
from .modulation import LFO, Envelope
from .utils.music_theory import get_diatonic_triad, get_random_scale_note

# ── Path resolution for PyInstaller builds ──
def _get_base_dir():
    """Resolve base directory: next to PyInstaller exe, or project root in dev."""
    if getattr(sys, 'frozen', False):
        # PyInstaller bundle: look next to the executable itself
        return os.path.dirname(sys.executable)
    # In dev: generator.py is at src/pySynth/generator.py, project root is 2 levels up
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

import sys  # needed for _MEIPASS check

# Note names for filename conversion
_NOTES = ['C', 'Cs', 'D', 'Ds', 'E', 'F', 'Fs', 'G', 'Gs', 'A', 'As', 'B']
_NOTES_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

def _freq_to_note_name(freq, force_flat=False):
    """Convert a frequency to a note name like 'C4' or 'Fs3' (file-safe)."""
    if freq <= 0:
        return 'X'
    midi = round(69 + 12 * math.log2(freq / 440.0))
    
    # Select note list
    n_list = _NOTES_FLAT if force_flat else _NOTES
    note = n_list[midi % 12]
    
    octave = (midi // 12) - 1
    return f"{note}{octave}"

def _freqs_to_chord_name(freqs, force_flat=False):
    """Convert a list of frequencies to a chord name like 'C4-E4-G4'."""
    if not freqs:
        return 'X'
    names = [_freq_to_note_name(f, force_flat) for f in freqs]
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for n in names:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    return '-'.join(unique)


def load_presets(presets_dir=None):
    """Load all .psi (JSON) presets from the directory."""
    if presets_dir is None:
        presets_dir = os.path.join(_get_base_dir(), 'presets')
    genres = {}
    if not os.path.exists(presets_dir):
        print(f"[FiggyGen] Warning: Preset directory '{presets_dir}' not found.")
    for filepath in glob.glob(os.path.join(presets_dir, '*.psi')):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                name = os.path.splitext(os.path.basename(filepath))[0]
                genres[name] = data
                # print(f"  - Loaded: {name}")
        except Exception as e:
            print(f"[FiggyGen] Error loading preset '{filepath}': {e}")
    return genres

def load_fx_presets(presets_dir=None):
    """Load all .psifx (JSON) FX-only presets from the directory."""
    if presets_dir is None:
        presets_dir = os.path.join(_get_base_dir(), 'fxpresets')
    fx_presets = {}
    if not os.path.exists(presets_dir):
        pass
    
    for filepath in glob.glob(os.path.join(presets_dir, '*.psifx')):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                name = os.path.splitext(os.path.basename(filepath))[0]
                fx_presets[name] = data
        except Exception as e:
            print(f"[FiggyGen] Error loading FX preset '{filepath}': {e}")
    return fx_presets


# Genre-specific envelope presets
ENVELOPE_PRESETS = {
    'bass': {'attack': (0.001, 0.02), 'hold': (0.0, 0.01), 'decay': (0.1, 0.4),
             'sustain': (0.6, 0.9), 'release': (0.05, 0.2)},
    'pad':  {'attack': (0.2, 1.5), 'hold': (0.0, 0.1), 'decay': (0.5, 2.0),
             'sustain': (0.5, 0.9), 'release': (0.5, 2.0)},
    'lead': {'attack': (0.005, 0.05), 'hold': (0.0, 0.02), 'decay': (0.1, 0.5),
             'sustain': (0.5, 0.8), 'release': (0.1, 0.5)},
    'fx':   {'attack': (0.01, 1.0), 'hold': (0.0, 0.5), 'decay': (0.1, 2.0),
             'sustain': (0.0, 1.0), 'release': (0.1, 2.0)},
    'keys': {'attack': (0.001, 0.01), 'hold': (0.0, 0.02), 'decay': (0.2, 0.8),
             'sustain': (0.3, 0.7), 'release': (0.1, 0.5)},
    'perc': {'attack': (0.0005, 0.005), 'hold': (0.0, 0.005), 'decay': (0.05, 0.3),
             'sustain': (0.0, 0.2), 'release': (0.02, 0.15)},
}

# Genre-specific LFO config
LFO_PRESETS = {
    'bass': {'prob': 0.2, 'rate': (0.5, 4.0), 'shapes': ['sine', 'triangle'],
             'targets': ['filter'], 'amount': (0.1, 0.4)},
    'pad':  {'prob': 0.6, 'rate': (0.1, 2.0), 'shapes': ['sine', 'triangle', 'random_walk'],
             'targets': ['filter', 'amp', 'pitch'], 'amount': (0.1, 0.5)},
    'lead': {'prob': 0.4, 'rate': (2.0, 8.0), 'shapes': ['sine', 'triangle', 'square'],
             'targets': ['pitch', 'filter'], 'amount': (0.1, 0.3)},
    'fx':   {'prob': 0.5, 'rate': (0.05, 10.0), 'shapes': ['sine', 'sample_hold', 'random_walk', 'saw'],
             'targets': ['filter', 'amp', 'pitch'], 'amount': (0.2, 0.8)},
    'keys': {'prob': 0.3, 'rate': (1.0, 5.0), 'shapes': ['sine', 'triangle'],
             'targets': ['amp', 'filter'], 'amount': (0.05, 0.2)},
    'perc': {'prob': 0.1, 'rate': (5.0, 20.0), 'shapes': ['sine', 'exp_fall'],
             'targets': ['filter'], 'amount': (0.1, 0.3)},
}


# ======================================================================
# Randomizer
# ======================================================================
class Randomizer:
    """Generates random patches based on genre definitions."""

    FILTER_TYPES = ['lowpass', 'highpass', 'bandpass', 'notch',
                    'allpass', 'peaking', 'low_shelf', 'high_shelf']
    DIST_TYPES = ['soft_clip', 'hard_clip', 'fold', 'crush']
    VOWELS = ['a', 'e', 'i', 'o', 'u']

    def __init__(self, presets_dir=None, fx_presets_dir=None):
        self.genres = load_presets(presets_dir)
        self.fx_presets = load_fx_presets(fx_presets_dir)
        if not self.genres:
            print("[FiggyGen] No presets loaded! Using built-in defaults.")
            self.genres = {'default': {
                'osc_waveforms': ['saw', 'square', 'triangle', 'sine'],
                'osc_count': [1, 3],
                'unison_range': [1, 3],
                'unison_detune': [0.0, 15.0],
                'fx_pool': ['reverb', 'delay', 'chorus'],
                'fx_count': [1, 3],
                'env_attack': [0.01, 0.3],
                'env_decay': [0.1, 0.5],
                'env_sustain': [0.3, 0.8],
                'env_release': [0.1, 1.0],
                'filter_type': ['lowpass'],
                'filter_cutoff': [200, 8000],
                'filter_res': [0.1, 0.8]
            }}

    def _resolve_value_or_range(self, val):
        """Helper to resolve a value or a 'min-max' range string."""
        if isinstance(val, str) and '-' in val and not val.startswith('-'):
            parts = val.split('-')
            if len(parts) == 2:
                try:
                    v1 = float(parts[0])
                    v2 = float(parts[1])
                    if v1 == int(v1) and v2 == int(v2):
                        return random.randint(int(v1), int(v2))
                    return random.uniform(v1, v2)
                except ValueError:
                    pass
        return val

    def _create_osc_config(self, wf, g):
        """Generate a random configuration for a single oscillator."""
        uni = random.randint(*g['unison_range'])
        ud = random.uniform(*g['unison_detune']) if uni > 1 else 0

        # Waveform-aware morph_pos
        if wf in ('morph', 'wavetable', 'vocal'):
            mp = random.random()
        elif wf == 'supersaw':
            mp = random.uniform(0.3, 1.0)
        else:
            mp = 0.0

        # FM params
        fm_r = random.choice([0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.0])
        fm_d = random.uniform(0.5, 5.0)

        # Harmonics
        harms = [random.uniform(0.0, 1.0) for _ in range(8)]
        harms[0] = max(0.5, harms[0])

        return {
            'waveform': wf,
            'detune': random.uniform(-10, 10),
            'phase': random.random(),
            'pulse_width': random.uniform(0.15, 0.85),
            'morph_pos': mp,
            'gain': random.uniform(0.5, 1.0),
            'unison': uni,
            'unison_detune': ud,
            'unison_spread': random.uniform(0.3, 1.0) if uni > 1 else 0,
            'fm_ratio': fm_r,
            'fm_depth': fm_d,
            'harmonics': harms,
        }
            
    def generate_patch(self, genre=None, fx_rules=None, osc_rules=None, lfo_rules=None, bus_rules=None, sample_data=None, fxpreset=None, exact=False):
        """
        Generate a random patch definition.
        """
        if exact:
            patch = {'genre': genre or 'exact', 'oscillators': [], 'effects': []}
            
            # Oscillators
            if osc_rules and ('only' in osc_rules and osc_rules['only']):
                osc_pool = osc_rules['only']
            elif osc_rules and ('include' in osc_rules and osc_rules['include']):
                osc_pool = osc_rules['include']
            else:
                osc_pool = ['sine']
                
            for wf in osc_pool:
                patch['oscillators'].append({
                    'waveform': wf, 'detune': 0.0, 'phase': 0.0, 'pulse_width': 0.5,
                    'morph_pos': 0.0, 'gain': 1.0, 'unison': 1, 'unison_detune': 0.0,
                    'unison_spread': 0.0, 'fm_ratio': 1.0, 'fm_depth': 0.0,
                    'harmonics': [1.0] + [0.0]*8,
                })

            # Exact Envelope
            patch['envelope'] = {'attack': 0.01, 'hold': 0.0, 'decay': 0.1, 'sustain_level': 1.0, 'release': 0.1}
            patch['lfos'] = {'pitch': None, 'filter': None, 'amp': None}

            # Exact Effects
            if fx_rules:
                if 'only' in fx_rules and fx_rules['only']:
                    fx_pool = fx_rules['only']
                elif 'include' in fx_rules and fx_rules['include']:
                    fx_pool = fx_rules['include']
                else:
                    fx_pool = []
                for item in fx_pool:
                    if isinstance(item, dict):
                        patch['effects'].append(item)
                    else:
                        patch['effects'].append({'type': item, 'params': {}})
            
            # Exact Buses
            if bus_rules:
                patch['buses'] = []
                for br in bus_rules:
                    # Filter 'rand' from oscillators
                    b_oscs = []
                    for wf in br['oscillators']:
                        if wf == 'rand': wf = 'sine'
                        b_oscs.append({
                            'waveform': wf, 'detune': 0.0, 'phase': 0.0, 'pulse_width': 0.5,
                            'morph_pos': 0.0, 'gain': 1.0, 'unison': 1, 'unison_detune': 0.0,
                            'unison_spread': 0.0, 'fm_ratio': 1.0, 'fm_depth': 0.0,
                            'harmonics': [1.0] + [0.0]*8,
                        })
                    bus_entry = {'id': br['id'], 'oscillators': b_oscs, 'effects': [fx for fx in br['effects']]}
                    if br.get('mute'): bus_entry['mute'] = True
                    if br.get('solo'): bus_entry['solo'] = True
                    if 'volume' in br: bus_entry['volume'] = br['volume']
                    patch['buses'].append(bus_entry)
            return patch

        if osc_rules is None: osc_rules = {}
        if fx_rules is None: fx_rules = {}
        if lfo_rules is None: lfo_rules = {}
        
        if genre is None or genre == 'rand':
             genre = random.choice(list(self.genres.keys()))
        
        # Determine the genre data dictionary
        # Safely fallback if genre not found
        if genre not in self.genres:
             print(f"[FiggyGen] Genre '{genre}' not found. Using random.")
             genre = random.choice(list(self.genres.keys()))
        
        g = self.genres[genre]
        
        # If FX preset provided, override genre settings for FX-related fields
        fx_source = g
        if fxpreset and fxpreset in self.fx_presets:
            fx_source = self.fx_presets[fxpreset]
            # print(f"[Debug] Using FX Preset: {fxpreset}")

        patch = {'genre': genre, 'oscillators': [], 'effects': []}

        # ── Inject Sample Oscillator if provided ──
        if sample_data is not None:
            patch['oscillators'].append({
                'waveform': 'sample',
                'sample_data': sample_data,
                'gain': 1.0,
                'unison': 1,
                'detune': 0.0
            })

        # ── Oscillators ──
        # Build waveform pool based on rules
        if 'only' in osc_rules and osc_rules['only']:
            osc_pool = list(osc_rules['only'])
        else:
            osc_pool = list(g['osc_waveforms'])
            
        if 'include' in osc_rules and osc_rules['include']:
            osc_pool.extend(osc_rules['include'])
            
        if 'exclude' in osc_rules and osc_rules['exclude']:
            osc_pool = [w for w in osc_pool if w not in osc_rules['exclude']]
            
        if not osc_pool:
            # Fallback if pool is empty
            osc_pool = ['sine']
        
        # DEBUG
        # print(f"Generate Patch Debug: Genre={genre}, Osc Rules={osc_rules}")
        # print(f"Osc Pool: {osc_pool}")

        # Determine number of oscillators
        osc_count_range = g['osc_count']
        if sample_data is not None and fxpreset:
            user_wants_oscs = (osc_rules and ('include' in osc_rules or 'only' in osc_rules))
            if not user_wants_oscs:
                osc_count_range = [0, 0]

        n_osc = random.randint(*osc_count_range)
        for _ in range(n_osc):
            wf = random.choice(osc_pool)
            patch['oscillators'].append(self._create_osc_config(wf, g))

        # ── Buses ──
        if bus_rules:
             patch['buses'] = []
             for br in bus_rules:
                 effects = []
                 for fx_item in br['effects']:
                      ftype = fx_item['type']
                      if ftype in self.fx_presets:
                           # Expand preset into a chain
                           preset_chain = self._generate_fx_chain(self.fx_presets[ftype])
                           effects.extend(preset_chain)
                      elif ftype == 'rand':
                           # Pick a random effect from the genre pool
                           main_pool = list(g.get('fx_pool', []))
                           if main_pool:
                               ft = random.choice(main_pool)
                               params = self._random_fx_params(ft) or {}
                               effects.append({'type': ft, 'params': params})
                      else:
                           # Resolve ranges in explicit effects
                           params = fx_item.get('params', {}).copy()
                           for k, v in params.items():
                               params[k] = self._resolve_value_or_range(v)
                           effects.append({'type': ftype, 'params': params})

                 b_conf = {'id': br['id'], 'oscillators': [], 'effects': effects}
                 if br.get('mute'): b_conf['mute'] = True
                 if br.get('solo'): b_conf['solo'] = True
                 if 'volume' in br: b_conf['volume'] = br['volume']
                 for wf in br['oscillators']:
                      if wf == 'rand':
                           wf = random.choice(osc_pool)
                      b_conf['oscillators'].append(self._create_osc_config(wf, g))
                 patch['buses'].append(b_conf)

        # ── Envelope (DAHDSR) ──
        # Use envelope config from the fx_source object (genre or fxpreset)
        env_p = fx_source.get('envelope', {
            'attack': (0.01, 0.1), 'hold': (0,0), 'decay': (0.1, 0.5), 
            'sustain': (0.5, 0.8), 'release': (0.1, 0.5)})

        patch['envelope'] = {
            'attack': random.uniform(*(env_p['attack'] or (0.01, 0.1))),
            'hold': random.uniform(*env_p['hold']),
            'decay': random.uniform(*env_p['decay']),
            'sustain_level': random.uniform(*env_p['sustain']),
            'release': random.uniform(*env_p['release']),
        }

        # ── LFO Modulation ──
        lfo_p = fx_source.get('lfo', {
            'prob': 0.0, 'targets': [], 'rate': (1,1), 'amount': (0,0), 'shapes': ['sine']})

        if lfo_rules is None:
            lfo_rules = {}

        # Merge user LFO rules with genre defaults
        lfo_rate_range = lfo_rules.get('rate', lfo_p['rate'])
        lfo_amt_range = lfo_rules.get('depth', lfo_p['amount'])
        
        # If user provided LFO rules, force LFO probability to 1.0 if not explicit
        # Or just use the prob? If user says --lfo-rate, they probably WANT an LFO.
        lfo_prob = lfo_p['prob']
        if lfo_rules:
            lfo_prob = 1.0

        patch['lfos'] = {'pitch': None, 'filter': None, 'amp': None}
        
        # Ensure targets exist before trying to choose
        if not lfo_p['targets']:
             lfo_p['targets'] = ['pitch']

        if random.random() < lfo_prob:
            target = random.choice(lfo_p['targets'])
            lfo_conf = {
                'waveform': random.choice(lfo_p['shapes']),
                'rate': self._resolve_value_or_range(random.uniform(*(lfo_rate_range or (1,1)))),
                'amount': self._resolve_value_or_range(random.uniform(*(lfo_amt_range or (0,0)))),
            }
            if isinstance(lfo_rate_range, str):
                 lfo_conf['rate'] = self._resolve_value_or_range(lfo_rate_range)
            if isinstance(lfo_amt_range, str):
                 lfo_conf['amount'] = self._resolve_value_or_range(lfo_amt_range)

            patch['lfos'][target] = lfo_conf
            # Sometimes add a second LFO on a different target
            if random.random() < 0.3 and len(lfo_p['targets']) > 1:
                remaining = [t for t in lfo_p['targets'] if t != target]
                target2 = random.choice(remaining)
                
                lfo_rate2 = lfo_rate_range
                lfo_amt2 = lfo_amt_range
                # Resolve if they are ranges, otherwise they are already resolved or defaults
                r2 = self._resolve_value_or_range(lfo_rate2) if isinstance(lfo_rate2, str) else random.uniform(*(lfo_rate_range or (1,1)))
                a2 = (self._resolve_value_or_range(lfo_amt2) if isinstance(lfo_amt2, str) else random.uniform(*(lfo_amt_range or (0,0)))) * 0.5

                lfo_conf2 = {
                    'waveform': random.choice(lfo_p['shapes']),
                    'rate': r2,
                    'amount': a2,
                }
                patch['lfos'][target2] = lfo_conf2

        # ── Effects chain ──
        patch['effects'] = self._generate_fx_chain(fx_source, fx_rules)
        return patch

    def _generate_fx_chain(self, fx_source, fx_rules=None):
        """Generates a randomized FX chain based on source pool and rules."""
        if fx_rules is None:
            fx_rules = {}
            
        # ── Build FX pool with rules ──
        if 'only' in fx_rules and fx_rules['only']:
            pool = list(fx_rules['only'])
        else:
            pool = list(fx_source.get('fx_pool', []))

        if 'exclude' in fx_rules and fx_rules['exclude']:
            pool = [f for f in pool if f not in fx_rules['exclude']]

        # ── Effects chain ──
        fx = []

        # Forced includes (always in the chain)
        if 'include' in fx_rules and fx_rules['include']:
            for item in fx_rules['include']:
                if isinstance(item, dict):
                    ftype = item['type']
                    user_params = item.get('params', {})
                else:
                    ftype = item
                    user_params = {}

                params = self._random_fx_params(ftype)
                if params is None:
                    params = {}
                
                params.update(user_params)
                
                # Per-sample range resolution
                for k, v in params.items():
                    params[k] = self._resolve_value_or_range(v)
                    
                fx.append({'type': ftype, 'params': params})

        # Pre-saturation?
        if random.random() < 0.3:
            fx.append({'type': 'tube',
                       'params': {'drive': random.uniform(0.05, 0.3),
                                  'asymmetry': random.uniform(0.0, 0.15)}})

        # Filter
        filter_prob = fx_source.get('filter_prob', 0.0)
        if random.random() < filter_prob:
            ft = random.choice(fx_source.get('filter_types', ['lowpass']))
            res_range = fx_source.get('resonance_range', (0.0, 0.6))
            p = {'filter_type': ft,
                 'cutoff': random.uniform(*fx_source.get('cutoff_range', [500, 2000])),
                 'resonance': random.uniform(*(res_range or (0.0, 0.6)))}
            if ft in ('peaking', 'low_shelf', 'high_shelf'):
                p['gain_db'] = random.uniform(-6, 6)
            fx.append({'type': 'filter', 'params': p})

        # Genre-specific FX (from filtered pool)
        random.shuffle(pool)
        
        if 'only' in fx_rules:
            loop_items = fx_rules['only'] 
        else:
            count_range = fx_source.get('fx_count', [0, 3])
            num_fx = random.randint(*count_range)
            num_fx = min(num_fx, len(pool))
            loop_items = pool[:num_fx]

        for i, item in enumerate(loop_items):
            if isinstance(item, dict):
                ftype = item['type']
                user_params = item.get('params', {})
            else:
                ftype = item
                user_params = {}

            params = self._random_fx_params(ftype) or {}
            params.update(user_params)
            fx.append({'type': ftype, 'params': params})

        # Space
        if random.random() < fx_source.get('delay_prob', 0.0):
            fx.append({'type': 'delay',
                       'params': {'time': random.uniform(0.15, 0.5),
                                  'feedback': random.uniform(0.2, 0.5),
                                  'mix': random.uniform(0.15, 0.35),
                                  'ping_pong': random.random() < 0.3}})
        if random.random() < fx_source.get('reverb_prob', 0.0):
            fx.append({'type': 'reverb',
                       'params': {'decay': random.uniform(0.5, 4.0),
                                  'mix': random.uniform(0.15, 0.4)}})

        # Stereo widener?
        if random.random() < 0.3:
            fx.append({'type': 'stereo_widen',
                       'params': {'width': random.uniform(0.4, 0.8)}})

        # Post: always limiter
        fx.append({'type': 'limiter',
                   'params': {'ceiling': random.uniform(-1.0, -0.3),
                              'release': 0.05}})
        return fx

    def drift_patch(self, base_patch, seed_offset, drift_amount=0.05):
        """
        Create a variation of base_patch by drifting parameters slightly.
        Deterministic based on seed_offset.
        """
        import copy
        # Deep copy to avoid mutating base
        patch = copy.deepcopy(base_patch)
        
        # Seed a local RNG unique to this drift instance
        # Use a hash of the base patch + offset to be deterministic but varied?
        # Or just use the global RNG state? 
        # The user wants "seed + small increment".
        # We'll use a local Random instance seeded with (base_seed + offset)
        # But we don't know the base seed here easily unless passed.
        # Let's just use the system random for now, or assume the caller set the seed properly.
        # Actually proper way:
        local_rnd = random.Random(seed_offset)
        
        def drift_val(val, amount=drift_amount):
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                # Drift by +/- amount * value (relative) or absolute?
                # Relative is safer for wide ranges (freq vs gain)
                # But for 0.0 values relative does nothing.
                # Let's do: val * (1 + uniform(-amt, amt))
                # Plus a tiny absolute jitter for 0-values?
                return val * (1.0 + local_rnd.uniform(-amount, amount))
            return val

        # Drift Oscillators
        for osc in patch['oscillators']:
            osc['detune'] = osc['detune'] + local_rnd.uniform(-2, 2) # add cents
            osc['phase'] = (osc['phase'] + local_rnd.uniform(0.0, 0.1)) % 1.0
            if 'pulse_width' in osc:
                osc['pulse_width'] = np.clip(drift_val(osc['pulse_width']), 0.01, 0.99)
            if 'morph_pos' in osc:
                osc['morph_pos'] = np.clip(drift_val(osc['morph_pos']), 0.0, 1.0)
            if 'unison_detune' in osc:
                osc['unison_detune'] = drift_val(osc['unison_detune'])
        
        # Drift Envelope
        if 'envelope' in patch:
            for k in patch['envelope']:
                patch['envelope'][k] = max(0, drift_val(patch['envelope'][k]))

        # Drift LFOs
        if 'lfos' in patch:
            for target, lfo in patch['lfos'].items():
                if lfo:
                    lfo['rate'] = drift_val(lfo['rate'])
                    lfo['amount'] = drift_val(lfo['amount'])

        # Drift Effects
        for fx in patch['effects']:
            for p, v in fx['params'].items():
                # Don't drift integer types that might be modes (like 'mode', 'type')
                # A simple heuristic: if it's a float, drift it.
                if isinstance(v, float):
                    fx['params'][p] = drift_val(v)
        
        return patch

    def _random_fx_params(self, ftype):
        """Return randomised params for a given FX type."""
        if ftype == 'distortion':
            return {'drive': random.uniform(0.05, 0.4),
                    'dist_type': random.choice(self.DIST_TYPES)}
        if ftype == 'bitcrush':
            return {'bit_depth': random.randint(5, 12),
                    'sample_rate_reduction': random.randint(1, 6)}
        if ftype == 'chorus':
            return {'rate': random.uniform(0.3, 3), 'depth': random.uniform(0.002, 0.006),
                    'voices': random.randint(2, 4), 'mix': 0.5}
        if ftype == 'flanger':
            return {'rate': random.uniform(0.1, 1), 'depth': random.uniform(0.001, 0.003),
                    'feedback': random.uniform(0.3, 0.7), 'mix': 0.4}
        if ftype == 'phaser':
            return {'rate': random.uniform(0.2, 2), 'depth': random.uniform(0.3, 0.8),
                    'stages': random.choice([4, 6, 8]), 'mix': 0.5}
        if ftype == 'tremolo':
            return {'rate': random.uniform(2, 10), 'depth': random.uniform(0.3, 0.7)}
        if ftype == 'vibrato':
            return {'rate': random.uniform(3, 8), 'depth': random.uniform(0.001, 0.005)}
        if ftype == 'autopan':
            return {'rate': random.uniform(0.5, 4), 'depth': random.uniform(0.4, 0.9)}
        if ftype == 'ring_mod':
            return {'freq': random.uniform(50, 1000), 'mix': random.uniform(0.3, 0.7)}
        if ftype == 'freq_shift':
            return {'shift_hz': random.uniform(-200, 200), 'mix': random.uniform(0.2, 0.5)}
        if ftype == 'tube':
            return {'drive': random.uniform(0.05, 0.3), 'asymmetry': random.uniform(0, 0.15)}
        if ftype == 'tape':
            return {'saturation': random.uniform(0.1, 0.4),
                    'wow': random.uniform(0.05, 0.2), 'flutter': random.uniform(0.05, 0.2)}
        if ftype == 'exciter':
            return {'amount': random.uniform(0.2, 0.5), 'cutoff': random.uniform(2000, 5000)}
        if ftype == 'compressor':
            return {'threshold': random.uniform(-30, -10), 'ratio': random.uniform(2, 8),
                    'attack': random.uniform(0.005, 0.03), 'release': random.uniform(0.05, 0.2)}
        if ftype == 'limiter':
            return {'ceiling': -0.5, 'release': 0.05}
        if ftype == 'stereo_widen':
            return {'width': random.uniform(0.4, 0.8)}
        # Creative effects
        if ftype == 'wavefolder':
            return {'folds': random.randint(1, 5), 'gain': random.uniform(1.0, 4.0),
                    'symmetry': random.uniform(0.5, 1.5)}
        if ftype == 'resonator':
            return {'freq': random.uniform(100, 2000), 'decay': random.uniform(0.8, 0.99),
                    'mix': random.uniform(0.2, 0.6), 'harmonics': random.randint(2, 6)}
        if ftype == 'lofi':
            return {'amount': random.uniform(0.2, 0.8)}
        if ftype == 'stutter':
            return {'grain_size_ms': random.uniform(20, 150),
                    'repeats': random.randint(1, 5), 'mix': random.uniform(0.3, 0.7)}
        if ftype == 'sub_bass':
            return {'mix': random.uniform(0.1, 0.4)}
        if ftype == 'gate':
            return {'threshold': random.uniform(-50, -20),
                    'attack': random.uniform(0.001, 0.01),
                    'release': random.uniform(0.02, 0.1)}
        if ftype == 'transient':
            return {'attack_gain': random.uniform(0.5, 3.0),
                    'sustain_gain': random.uniform(0.5, 1.5),
                    'sensitivity': random.uniform(0.005, 0.02)}
        if ftype == 'ensemble':
            return {'voices': random.randint(3, 7),
                    'depth': random.uniform(0.002, 0.006),
                    'rate': random.uniform(0.3, 1.5)}
        if ftype == 'dc_remove':
            return {}
        if ftype == 'pitch_shift':
            return {'semitones': random.choice([-12, -7, -5, 5, 7, 12]),
                    'mix': random.uniform(0.15, 0.4)}
        if ftype == 'sidechain':
            return {'rate': random.uniform(1, 4), 'depth': random.uniform(0.3, 0.8),
                    'shape': random.uniform(0.2, 0.8)}
        # ── New creative effects ──
        if ftype == 'reverse':
            return {'mix': random.uniform(0.5, 1.0)}
        if ftype == 'tape_stop':
            return {'duration_pct': random.uniform(0.2, 0.8)}
        if ftype == 'vinyl':
            return {'crackle': random.uniform(0.1, 0.5),
                    'hiss': random.uniform(0.05, 0.2),
                    'wow': random.uniform(0.05, 0.3)}
        if ftype == 'radio':
            return {'intensity': random.uniform(0.3, 0.8)}
        if ftype == 'telephone':
            return {'quality': random.uniform(0.2, 0.8)}
        if ftype == 'underwater':
            return {'depth_amount': random.uniform(0.3, 0.8)}
        if ftype == 'shimmer':
            return {'shift_semitones': random.choice([7, 12, 19]),
                    'feedback': random.uniform(0.2, 0.5),
                    'mix': random.uniform(0.2, 0.5)}
        if ftype == 'glitch':
            return {'density': random.uniform(0.1, 0.5),
                    'slice_ms': random.uniform(10, 80)}
        if ftype == 'haas':
            return {'delay_ms': random.uniform(5, 25),
                    'side': random.choice(['left', 'right'])}
        if ftype == 'harmonizer':
            return {'interval': random.choice([-12, -7, -5, 3, 4, 5, 7, 12]),
                    'mix': random.uniform(0.15, 0.4)}
        if ftype == 'octaver':
            return {'octave_up': random.uniform(0.0, 0.3),
                    'octave_down': random.uniform(0.1, 0.4)}
        if ftype == 'doppler':
            return {'speed': random.uniform(0.5, 2.0),
                    'depth': random.uniform(0.1, 0.5)}
        if ftype == 'crystal':
            return {'brightness': random.uniform(0.3, 0.8),
                    'decay': random.uniform(0.2, 0.5)}
        if ftype == 'fade':
            return {'fade_in_ms': random.uniform(10, 100),
                    'fade_out_ms': random.uniform(50, 500)}
        if ftype == 'dimension':
            return {'mode': random.randint(1, 4)}
        # ── Hardware emulations ──
        if ftype == 'moog':
            return {'cutoff': random.uniform(200, 8000),
                    'resonance': random.uniform(0.2, 0.9),
                    'drive': random.uniform(0.0, 0.5)}
        if ftype == '303':
            return {'cutoff': random.uniform(300, 3000),
                    'resonance': random.uniform(0.5, 0.95),
                    'env_mod': random.uniform(0.2, 0.8),
                    'accent': random.uniform(0.0, 0.6),
                    'decay': random.uniform(0.1, 0.5)}
        if ftype == 'sem':
            return {'cutoff': random.uniform(300, 8000),
                    'resonance': random.uniform(0.2, 0.8),
                    'mode': random.choice(['lowpass', 'highpass', 'bandpass', 'notch'])}
        if ftype == 'ms20':
            return {'cutoff': random.uniform(200, 6000),
                    'resonance': random.uniform(0.4, 0.9)}
        if ftype == 'space_echo':
            return {'time': random.uniform(0.15, 0.5),
                    'feedback': random.uniform(0.3, 0.7),
                    'wow': random.uniform(0.05, 0.3),
                    'flutter': random.uniform(0.05, 0.2),
                    'tone': random.uniform(0.2, 0.8),
                    'mix': random.uniform(0.2, 0.5)}
        if ftype == 'fairchild':
            return {'input_gain': random.uniform(0.2, 0.7),
                    'threshold': random.uniform(-30, -10),
                    'time_constant': random.randint(1, 6)}
        if ftype == 'ssl':
            return {'threshold': random.uniform(-25, -8),
                    'ratio': random.choice([2.0, 4.0, 10.0]),
                    'attack_ms': random.choice([0.1, 0.3, 1, 3, 10, 30]),
                    'release_ms': random.choice([100, 300, 600, 1200])}
        if ftype == 'neve':
            return {'gain': random.uniform(0.2, 0.7),
                    'warmth': random.uniform(0.2, 0.8)}
        if ftype == 'emt_plate':
            return {'decay': random.uniform(1.0, 4.0),
                    'damping': random.uniform(0.2, 0.7),
                    'mix': random.uniform(0.15, 0.45),
                    'pre_delay_ms': random.uniform(5, 40)}
        if ftype == 'spring':
            return {'decay': random.uniform(0.8, 2.5),
                    'tone': random.uniform(0.2, 0.8),
                    'mix': random.uniform(0.1, 0.4),
                    'drip': random.uniform(0.1, 0.5)}
        if ftype == 'marshall':
            return {'gain': random.uniform(0.3, 0.9),
                    'tone': random.uniform(0.3, 0.8),
                    'presence': random.uniform(0.2, 0.7)}
        if ftype == 'ce1':
            return {'rate': random.uniform(0.3, 1.2),
                    'intensity': random.uniform(0.3, 0.8)}
        if ftype == 'small_stone':
            return {'rate': random.uniform(0.2, 1.0),
                    'depth': random.uniform(0.4, 0.9),
                    'feedback': random.uniform(0.3, 0.7),
                    'color': random.choice([True, False])}
        if ftype == 'lexicon':
            return {'size': random.uniform(0.4, 1.0),
                    'decay': random.uniform(1.5, 5.0),
                    'damping': random.uniform(0.2, 0.6),
                    'mix': random.uniform(0.15, 0.4)}
        if ftype == 'dbx160':
            return {'threshold': random.uniform(-25, -10),
                    'ratio': random.choice([4.0, 6.0, 8.0, 12.0])}
        if ftype == 'prophet':
            return {'cutoff': random.uniform(300, 6000),
                    'resonance': random.uniform(0.3, 0.8)}
        if ftype == 'juno_hpf':
            return {'cutoff': random.uniform(100, 2000),
                    'resonance': random.uniform(0.1, 0.5)}
        if ftype == 'arp_ring':
            return {'freq': random.uniform(100, 800),
                    'depth': random.uniform(0.4, 0.9),
                    'diode_curve': random.uniform(0.0, 0.5)}
        if ftype == 'h3000':
            return {'detune_cents': random.uniform(5, 25),
                    'delay_ms': random.uniform(5, 30),
                    'mix': random.uniform(0.2, 0.5)}
        if ftype == 'vox':
            return {'gain': random.uniform(0.2, 0.7),
                    'treble': random.uniform(0.3, 0.8),
                    'cut': random.uniform(0.1, 0.6)}
        if ftype == 'fender_twin':
            return {'volume': random.uniform(0.2, 0.6),
                    'treble': random.uniform(0.3, 0.8),
                    'bass': random.uniform(0.3, 0.7),
                    'reverb_mix': random.uniform(0.1, 0.4)}
        if ftype == 're301':
            return {'rate': random.uniform(0.3, 1.0),
                    'depth': random.uniform(0.2, 0.7),
                    'tone': random.uniform(0.2, 0.8)}
        if ftype == 'studer':
            return {'input_level': random.uniform(0.2, 0.7),
                    'speed': random.randint(0, 2),
                    'bias': random.uniform(0.3, 0.7)}
        if ftype == 'la2a':
            return {'peak_reduction': random.uniform(0.2, 0.7),
                    'mode': random.choice(['compress', 'limit'])}
        if ftype == 'pultec':
            return {'low_boost': random.uniform(0.0, 0.5),
                    'low_atten': random.uniform(0.0, 0.3),
                    'low_freq': random.choice([30, 60, 100]),
                    'high_boost': random.uniform(0.0, 0.4),
                    'high_atten': random.uniform(0.0, 0.2),
                    'high_freq': random.choice([4000, 8000, 12000])}
        if ftype == 'buchla_lpg':
            return {'strike': random.uniform(0.3, 0.9),
                    'decay': random.uniform(0.1, 0.6),
                    'resonance': random.uniform(0.1, 0.4),
                    'mode': random.choice(['filter', 'vca', 'both'])}
        # -- Sonic Power effects --
        if ftype == 'granular':
            return {'grain_ms': random.uniform(15, 80),
                    'density': random.uniform(0.3, 0.9),
                    'spray': random.uniform(0.1, 0.5),
                    'pitch_spread': random.uniform(0.0, 0.3)}
        if ftype == 'spectral_freeze':
            return {'freeze_pos': random.uniform(0.1, 0.8),
                    'sustain': random.uniform(0.3, 0.8),
                    'mix': random.uniform(0.2, 0.5)}
        if ftype == 'maximizer':
            return {'ceiling': random.uniform(-1.0, -0.1),
                    'warmth': random.uniform(0.2, 0.7),
                    'release_ms': random.uniform(20, 100)}
        if ftype == 'stereo_imager':
            return {'width': random.uniform(0.8, 2.0),
                    'bass_mono_freq': random.choice([0, 100, 200, 300])}
        if ftype == 'multiband':
            return {'low_thresh': random.uniform(-25, -15),
                    'mid_thresh': random.uniform(-22, -12),
                    'high_thresh': random.uniform(-20, -10),
                    'crossover_low': random.choice([150, 200, 250]),
                    'crossover_high': random.choice([3000, 4000, 5000])}
        if ftype == 'harmonic_enhance':
            return {'low_harmonics': random.uniform(0.1, 0.5),
                    'high_harmonics': random.uniform(0.1, 0.4),
                    'air': random.uniform(0.0, 0.3)}
        if ftype == 'granular_stretch':
            return {'rate': random.uniform(0.3, 0.8),
                    'grain_ms': random.uniform(30, 100)}
        if ftype == 'parallel_comp':
            return {'threshold': random.uniform(-30, -15),
                    'ratio': random.choice([4.0, 6.0, 8.0, 12.0]),
                    'mix': random.uniform(0.2, 0.5)}
        if ftype == 'body':
            return {'size': random.uniform(0.2, 0.8),
                    'tone': random.uniform(0.3, 0.7),
                    'mix': random.uniform(0.15, 0.4)}
        if ftype == 'width_enhance':
            return {'low_width': random.uniform(0.5, 1.0),
                    'high_width': random.uniform(1.0, 2.0),
                    'crossover': random.choice([500, 800, 1200])}
        if ftype == 'warmth':
            return {'amount': random.uniform(0.2, 0.7)}
        if ftype == 'spatial':
            return {'room_size': random.uniform(0.2, 0.8),
                    'position': random.uniform(0.2, 0.8),
                    'height': random.uniform(0.0, 0.5)}
        if ftype == 'dimension_d':
            return {'mode': random.randint(1, 4)}
        if ftype == 'obxa':
            return {'cutoff': random.uniform(200, 8000),
                    'resonance': random.uniform(0.2, 0.8),
                    'mode': random.choice(['lowpass', 'bandpass', 'highpass'])}
        if ftype == 'wasp':
            return {'cutoff': random.uniform(200, 5000),
                    'resonance': random.uniform(0.3, 0.9)}
        if ftype == 'ams_reverb':
            return {'decay': random.uniform(0.5, 3.0),
                    'damping': random.uniform(0.2, 0.7),
                    'program': random.choice(['nonlin', 'ambience', 'plate']),
                    'mix': random.uniform(0.15, 0.4)}
        if ftype == 'tc2290':
            return {'time_ms': random.uniform(100, 600),
                    'feedback': random.uniform(0.2, 0.6),
                    'mod_rate': random.uniform(0.1, 0.5),
                    'mod_depth': random.uniform(0.001, 0.004),
                    'mix': random.uniform(0.2, 0.4)}
        if ftype == '1176':
            return {'input_gain': random.uniform(0.2, 0.7),
                    'ratio': random.choice([4, 8, 12, 20]),
                    'attack': random.uniform(0.1, 0.8),
                    'release': random.uniform(0.2, 0.7)}
        return None


# ======================================================================
# Sample Generator
# ======================================================================
class SampleGenerator:
    """Batch generation engine."""

    def __init__(self, output_dir='./output'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.randomizer = Randomizer()
        self.synth = FiggyGenSynth()

    def generate_batch(self, count=10, note_freq=440.0, duration=2.0,
                       genre=None, fx_rules=None, osc_rules=None, lfo_rules=None, bus_rules=None,
                       loop=False, zeroc=False,
                       round_robin=False, macro_spec=None, wavetable_export=False,
                       sample_path=None, sample_folder=None, destructive=False, fxpreset=None, scale=None, nitro=False,
                       force_flat=False, exact=False):
        """
        Generate *count* samples.
        If sample_path or sample_folder is provided, iterate through them.
        destructive: If True, overwrite input files.
        """
        print(f"Generating {count} samples → {self.output_dir}/")
        print(f"Genre: {genre}")
        if fxpreset:
            print(f"FX Preset: {fxpreset}")
        
        # Collect Input Samples
        input_files = [] # list of (path, filename_base)
        if sample_folder:
             # Recursive search
             for root, dirs, files in os.walk(sample_folder):
                 for f in files:
                     if f.lower().endswith('.wav'):
                         full_path = os.path.join(root, f)
                         rel_path = os.path.relpath(full_path, start=sample_folder) 
                         # Use relation for output structure mirroring? Or just flat?
                         # For now, let's keep it simple: flat output if copy, inplace if destructive
                         input_files.append(full_path)
             print(f"[FiggyGen] Found {len(input_files)} samples in {sample_folder}")
        elif sample_path:
             input_files.append(sample_path)
             print(f"[FiggyGen] Processing single sample: {sample_path}")
        
        # Logic toggle
        processing_mode = len(input_files) > 0

        if wavetable_export:
            print("[FiggyGen] Mode: Wavetable Export (2048 samples/frame)")
        if round_robin:
            print("[FiggyGen] Mode: Round Robin (Variations)")
        if nitro:
            print("[FiggyGen] Mode: Nitro (16kHz / Mono / 16-bit)")
        if macro_spec:
            print(f"[FiggyGen] Macro Mod: {macro_spec}")

        # Determine base frequencies
        freqs_base = [note_freq] if np.isscalar(note_freq) else list(note_freq)
        
        # Calculate perfect loop duration if requested
        calc_duration = duration
        if loop and len(freqs_base) > 0 and not wavetable_export and not processing_mode:
            root = freqs_base[0]
            if root > 0:
                cycles = max(1, round(root * duration))
                calc_duration = cycles / root
                print(f"[Loop] Adjusted duration: {duration:.4f}s -> {calc_duration:.4f}s ({cycles} cycles of {root}Hz)")

        # Prepare Round Robin Base Patch (only if not processing mode, or applied to all?)
        # If processing mode, base_patch might not make sense if it relies on oscs?
        # Actually we can still use it for FX settings.
        base_patch = None
        if round_robin:
            base_patch = self.randomizer.generate_patch(genre=genre, fx_rules=fx_rules,
                                                   osc_rules=osc_rules, lfo_rules=lfo_rules, bus_rules=bus_rules, fxpreset=fxpreset)

        # Prepare Macro LFO
        macro_lfo = None
        macro_routes = []
        if macro_spec:
            m_rate = 0.5
            m_depth = 1.0
            targets_str = ""
            parts = macro_spec.split(',')
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    k = k.strip().lower()
                    if k == 'rate': m_rate = float(v)
                    elif k == 'depth': m_depth = float(v)
                    elif k == 'targets': targets_str = v.strip()
            
            macro_lfo = LFO(waveform='triangle', rate=m_rate, amount=m_depth, bipolar=True)
            if targets_str:
                t_list = targets_str.split(';')
                for t in t_list:
                    t_parts = t.split(':')
                    if len(t_parts) == 3:
                        macro_routes.append((t_parts[0].strip(), t_parts[1].strip(), float(t_parts[2])))

        # --- GENERATION LOOP ---
        
        # If processing mode, we loop over input files
        # If normal mode, we loop range(count) (and use dummy list [None])
        
        loop_targets = input_files if processing_mode else [None]
        
        for input_idx, input_file in enumerate(loop_targets):
            
            # Load Sample Data if applicable
            sample_data = None
            sample_sr = 44100
            file_duration = calc_duration
            
            if input_file:
                try:
                    data, sr = sf.read(input_file)
                    # Helper to convert to mono/stereo handled in Synth?
                    # We pass raw data.
                    sample_data = data
                    sample_sr = sr
                    # Use sample duration if duration not explicitly set? 
                    # Actually args.duration default is 2.0. If user didn't change it...
                    # Logic: if duration is standard 2.0 (default), maybe use file length?
                    # But we don't know if '2.0' was user-set or default easily here without parsing args again.
                    # Let's assume: Use specified duration. If you want full sample, set duration high?
                    # Or maybe better: If processing mode, file_duration = len(data)/sr
                    file_duration = len(data) / sr
                    print(f"[{input_idx+1}/{len(loop_targets)}] Processing {os.path.basename(input_file)} ({file_duration:.2f}s)...")
                except Exception as e:
                    print(f"Error loading {input_file}: {e}")
                    continue

            # Determine Iterations for this file
            # If destructive, force 1 iteration
            # If normal processing, count iterations (variations)
            iterations = 1 if (processing_mode and destructive) else count

            # Find highest existing file number to avoid overwriting
            file_offset = 0
            if not processing_mode or not destructive:
                try:
                    existing = os.listdir(self.output_dir)
                    for ef in existing:
                        if ef.endswith('.wav') and ef[0:4].isdigit():
                            try:
                                num = int(ef[:4])
                                if num > file_offset:
                                    file_offset = num
                            except ValueError:
                                pass
                except FileNotFoundError:
                    pass

            for i in range(iterations):
                self.synth.clear_oscillators()
                
                # 1. Determine Patch
                if round_robin:
                    seed_off = (i * 9973) + (input_idx * 541) # offset by file too
                    patch = self.randomizer.drift_patch(base_patch, seed_off)
                    
                    # Inject sample data into drifted patch (since base_patch didn't have it)
                    if sample_data is not None:
                        patch['oscillators'].insert(0, {
                            'waveform': 'sample',
                            'sample_data': sample_data,
                            'gain': 1.0,
                            'unison': 1,
                            'detune': 0.0
                        })
                else:
                    patch = self.randomizer.generate_patch(genre=genre, fx_rules=fx_rules,
                                                           osc_rules=osc_rules, lfo_rules=lfo_rules, bus_rules=bus_rules,
                                                           sample_data=sample_data, fxpreset=fxpreset, exact=exact)

                # 2. Setup Synth — add oscillators
                tag = patch.get('genre', 'rand')
                wf = patch['oscillators'][0]['waveform'] if patch.get('oscillators') else 'mixed'
                for osc_conf in patch['oscillators']:
                    self.synth.add_oscillator(**osc_conf)

                if 'buses' in patch:
                    any_solo = any(b.get('solo', False) for b in patch['buses'])
                    for b in patch['buses']:
                        if b.get('mute', False) and not b.get('solo', False):
                            continue
                        if any_solo and not b.get('solo', False):
                            continue
                        for osc in b['oscillators']:
                            self.synth.add_oscillator(bus=b['id'], **osc)
                        self.synth.set_effects(b['effects'], bus=b['id'])

                # 3. Configure Effects / Envelope / LFOs / Macro
                if not wavetable_export:
                    self.synth.set_effects(patch['effects'])

                    env_conf = patch.get('envelope', {})
                    self.synth.envelope = Envelope(**env_conf) if env_conf else Envelope()

                    lfos = patch.get('lfos', {})
                    pitch_lfo = LFO(**lfos['pitch']) if lfos.get('pitch') else None
                    filter_lfo = LFO(**lfos['filter']) if lfos.get('filter') else None
                    amp_lfo = LFO(**lfos['amp']) if lfos.get('amp') else None
                    self.synth.configure_lfos(pitch_lfo, filter_lfo, amp_lfo)

                    if macro_lfo:
                        self.synth.configure_macro(macro_lfo, macro_routes)

                # 4. Render
                render_dur = file_duration if processing_mode else calc_duration

                if wavetable_export:
                    # WAVETABLE EXPORT MODE
                    frames = []
                    num_frames = 64
                    frame_size = 2048

                    self.synth.envelope = Envelope(attack=0, hold=10, decay=0, sustain_level=1, release=0)
                    self.synth.set_effects([])
                    wt_freq = self.synth.sample_rate / frame_size

                    for f_idx in range(num_frames):
                        morph = f_idx / (num_frames - 1)
                        for osc in self.synth.oscillators:
                            osc.frequency = wt_freq
                            osc.morph_pos = morph
                            if osc.waveform in ('square', 'pulse'):
                                osc.pulse_width = 0.5 + (morph - 0.5) * 0.9

                        frame = self.synth.render(frame_size / self.synth.sample_rate, [wt_freq])
                        if len(frame) != frame_size:
                            frame = frame[:frame_size]
                        frames.append(frame)

                    audio = np.concatenate(frames)
                    fname = f"wavetable_{i+1+file_offset:02d}_{patch['oscillators'][0]['waveform']}.wav"

                else:
                    # STANDARD / SAMPLE RENDER
                    # If processing mode, we don't change pitch (usually)
                    # If normal gen mode:
                    
                    # 1. Start with base freqs
                    current_freqs = [note_freq] if np.isscalar(note_freq) else list(note_freq)
                    
                    if not processing_mode:
                        # 2. Apply Scale Randomization (if single note & scale active)
                        # This turns "C4" into "Random note from C Minor" if scale=minor
                        if not exact and scale and len(current_freqs) == 1:
                            r_freq = current_freqs[0]
                            
                            # from .generator import _freq_to_note_name (Fixed: function is global)
                            
                            root_name_full = _freq_to_note_name(r_freq)
                            # import re (Fixed: module level)
                            m = re.match(r"([A-Ga-g][s#]?)", root_name_full)
                            key_root = m.group(1) if m else 'C'
                            
                            
                            # Randomize!
                            new_freq = get_random_scale_note(r_freq, scale, key_root, octave_range=1)
                            current_freqs = [new_freq]

                        # 3. Occasional chord for pads/keys (Standard genre logic)
                        # ONLY if scale is NOT set. If scale is set, user wants specific notes.
                        if not exact and not scale and not round_robin and patch.get('genre') in ('pad', 'keys') and random.random() < 0.25:
                            root = current_freqs[0]
                            current_freqs = [root, root * 1.25, root * 1.5]

                        # Determine note tag for filename
                        if len(current_freqs) > 1:
                           note_tag = _freqs_to_chord_name(current_freqs, force_flat)
                        else:
                           note_tag = _freq_to_note_name(current_freqs[0], force_flat)
                           
                        prefix = "RR" if round_robin else ""
                        if prefix:
                            fname = f"{prefix}_{i+1+file_offset:04d}_{tag}_{wf}_{note_tag}.wav"
                        else:
                            fname = f"{i+1+file_offset:04d}_{tag}_{wf}_{note_tag}.wav"

                        # 4. Percussion frequency override
                        PERC_FREQ_OVERRIDES = {
                            'kick': (35, 65), 'kick_808': (35, 65), 'kick_909': (40, 70),
                            'kick_78': (45, 80), 'kick_707': (45, 80),
                            'snare': (150, 250), 'snare_808': (150, 250), 'snare_909': (150, 250),
                            'snare_78': (150, 280), 'snare_707': (150, 250),
                            'hat': (300, 800), 'hat_808': (300, 800), 'hat_909': (300, 800),
                            'hat_78': (300, 800),
                            'tom': (60, 200), 'clap': (200, 500), 'rimshot': (800, 2000),
                            'cowbell': (400, 700), 'cowbell_808': (400, 700),
                            'cymbal_crash': (400, 800), 'cymbal_ride': (500, 1000),
                            'shaker': (500, 2000), 'woodblock': (600, 1200),
                            'impact': (30, 80),
                        }
                        osc_wfs = [o.get('waveform', o.get('type', '')) for o in patch['oscillators']]
                        perc_wfs = [wf for wf in osc_wfs if wf in PERC_FREQ_OVERRIDES]
                        if not exact and perc_wfs:
                            lo, hi = PERC_FREQ_OVERRIDES[perc_wfs[0]]
                            current_freqs = [random.uniform(lo, hi)]

                    audio = self.synth.render(render_dur, current_freqs)
                    
                    # Zero-crossing fade
                    if zeroc:
                        fade_samps = int(0.005 * self.synth.sample_rate)
                        if fade_samps > 0 and len(audio) > 2 * fade_samps:
                            fade_in = np.linspace(0.0, 1.0, fade_samps)
                            fade_out = np.linspace(1.0, 0.0, fade_samps)
                            if audio.ndim == 2:
                                audio[:fade_samps] *= fade_in[:, np.newaxis]
                                audio[-fade_samps:] *= fade_out[:, np.newaxis]
                            else:
                                audio[:fade_samps] *= fade_in
                                audio[-fade_samps:] *= fade_out

                    # Filename
                    if processing_mode:
                        base_name = os.path.splitext(os.path.basename(input_file))[0]
                        if destructive:
                            fname = os.path.basename(input_file)
                        elif iterations > 1:
                            fname = f"{base_name}_FX{i+1:02d}.wav"
                        else:
                            fname = f"{base_name}_FX.wav"
                    else:
                        wf = patch['oscillators'][0].get('waveform', 'sample')
                        tag = patch.get('genre', 'rand')
                        # Note tag determined above now
                        pass

                # 5. Save
                if processing_mode and destructive:
                    path = input_file  # overwrite original
                else:
                    path = os.path.join(self.output_dir, fname)

                # NITRO PROCESSING (Direct Generation)
                if nitro and not wavetable_export:
                    # 1. Convert to Mono
                    if audio.ndim > 1 and audio.shape[1] > 1:
                        audio = np.mean(audio, axis=1)
                    
                    # 2. Resample to 16000 Hz
                    target_sr = 16000
                    if self.synth.sample_rate != target_sr:
                        number_of_samples = round(len(audio) * float(target_sr) / self.synth.sample_rate)
                        audio = scipy.signal.resample(audio, number_of_samples)
                        
                    # 3. Clip
                    if audio.max() > 1.0 or audio.min() < -1.0:
                         audio = np.clip(audio, -1.0, 1.0)
                         
                    # Write with target settings
                    sf.write(path, audio, target_sr, subtype='PCM_16')
                else:
                    sf.write(path, audio, self.synth.sample_rate)

                if (i + 1) % 10 == 0 or (i + 1) == iterations:
                    print(f"  [{i+1}/{iterations}] {os.path.basename(path)}")

        print("[FiggyGen] Done.")

    def generate_progression(self, chord_list, passes=5, duration=2.0,
                             genre=None, fx_rules=None, osc_rules=None, lfo_rules=None, bus_rules=None,
                             loop=False, zeroc=False, nitro=False, force_flat=False, exact=False):
        """
        Generate a chord progression.

        Each 'pass' renders the entire chord_list with the SAME patch,
        so every chord in a pass shares identical synth settings —
        perfect for constructing songs.

        chord_list: List of lists-of-frequencies, one per chord.
                    e.g. [[261.63, 329.63, 392.0], [220.0, 277.18, 329.63], ...]
        passes:     Number of times to repeat the progression with new params.
        duration:   Duration per chord in seconds.
        fx_rules:   Optional dict with 'only', 'exclude', 'include' lists.
        """
        if passes is None:
            passes = 1
        total = passes * len(chord_list)
        print(f"[FiggyGen] Progression: {len(chord_list)} chords × {passes} passes = {total} samples → {self.output_dir}/")

        sample_num = 0
        for p in range(passes):
            # Generate ONE patch for this entire pass
            self.synth.clear_oscillators()
            patch = self.randomizer.generate_patch(genre=genre, fx_rules=fx_rules,
                                                   osc_rules=osc_rules, lfo_rules=lfo_rules, bus_rules=bus_rules, exact=exact)

            for osc_conf in patch['oscillators']:
                self.synth.add_oscillator(**osc_conf)

            if 'buses' in patch:
                any_solo = any(b.get('solo', False) for b in patch['buses'])
                for b in patch['buses']:
                    if b.get('mute', False) and not b.get('solo', False):
                        continue
                    if any_solo and not b.get('solo', False):
                        continue
                    for osc in b['oscillators']:
                        self.synth.add_oscillator(bus=b['id'], **osc)
                    self.synth.set_effects(b['effects'], bus=b['id'])

            self.synth.set_effects(patch['effects'])

            # Apply envelope
            env_conf = patch.get('envelope', {})
            self.synth.envelope = Envelope(**env_conf) if env_conf else Envelope()

            # Apply LFOs
            lfos = patch.get('lfos', {})
            pitch_lfo = LFO(**lfos['pitch']) if lfos.get('pitch') else None
            filter_lfo = LFO(**lfos['filter']) if lfos.get('filter') else None
            amp_lfo = LFO(**lfos['amp']) if lfos.get('amp') else None
            self.synth.configure_lfos(pitch_lfo, filter_lfo, amp_lfo)

            wf = patch['oscillators'][0]['waveform']
            tag = patch['genre']

            for chord_idx, freqs in enumerate(chord_list):
                # Calculate perfect loop duration per chord if requested
                calc_duration = duration
                if loop and len(freqs) > 0:
                    root = freqs[0]
                    if root > 0:
                         cycles = max(1, round(root * duration))
                         calc_duration = cycles / root

                audio = self.synth.render(calc_duration, freqs)

                # Apply Zero-Crossing / De-clicking fade
                if zeroc:
                    fade_samps = int(0.005 * self.synth.sample_rate)
                    if fade_samps > 0 and len(audio) > 2 * fade_samps:
                        fade_in = np.linspace(0.0, 1.0, fade_samps)
                        if audio.ndim == 2:
                            audio[:fade_samps] *= fade_in[:, np.newaxis]
                        else:
                            audio[:fade_samps] *= fade_in
                            
                        fade_out = np.linspace(1.0, 0.0, fade_samps)
                        if audio.ndim == 2:
                            audio[-fade_samps:] *= fade_out[:, np.newaxis]
                        else:
                            audio[-fade_samps:] *= fade_out

                sample_num += 1
                chord_tag = _freqs_to_chord_name(freqs, force_flat)
                fname = f"prog_p{p+1:02d}_c{chord_idx+1:02d}_{tag}_{wf}_{chord_tag}.wav"
                path = os.path.join(self.output_dir, fname)
                if nitro:
                    # 1. Convert to Mono
                    if audio.ndim > 1 and audio.shape[1] > 1:
                        audio = np.mean(audio, axis=1)

                    # 2. Resample to 16000 Hz
                    target_sr = 16000
                    if self.synth.sample_rate != target_sr:
                        number_of_samples = round(len(audio) * float(target_sr) / self.synth.sample_rate)
                        audio = scipy.signal.resample(audio, number_of_samples)

                    # 3. Clip
                    if audio.max() > 1.0 or audio.min() < -1.0:
                         audio = np.clip(audio, -1.0, 1.0)

                    sf.write(path, audio, target_sr, subtype='PCM_16')
                else:
                    sf.write(path, audio, self.synth.sample_rate)

                if sample_num % 10 == 0 or sample_num == total:
                    print(f"  [{sample_num}/{total}] {fname}")

            print(f"  Pass {p+1}/{passes} complete ({tag}/{wf})")
        print("[FiggyGen] Done.")

