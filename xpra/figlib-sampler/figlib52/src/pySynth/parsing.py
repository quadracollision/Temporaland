"""
FiggyGen Text Parsers.
Handles parsing of complex FX strings, bus configurations, and randomization macros.
"""
import re
import random
from .synth import EFFECT_DISPATCH

# Parameter ranges for 'rand' resolution
FX_PARAM_RANGES = {
    'delay': {'time': (0.01, 1.0), 'feedback': (0.0, 0.95), 'mix': (0.0, 0.5)},
    'reverb': {'room_size': (0.1, 1.0), 'damping': (0.0, 1.0), 'width': (0.0, 1.0), 'mix': (0.0, 0.6)},
    'distortion': {'drive': (0.0, 1.0), 'gain': (0.0, 1.0), 'mix': (0.0, 1.0)},
    'bitcrush': {'bits': (2, 16), 'sample_rate': (1000, 44100), 'mix': (0.0, 1.0)},
    'filter': {'cutoff': (50, 10000), 'resonance': (0.0, 0.9), 'gain': (0.0, 2.0)},
    'chorus': {'rate': (0.1, 5.0), 'depth': (0.0, 1.0), 'feedback': (0.0, 0.8), 'mix': (0.0, 1.0)},
    'flanger': {'rate': (0.1, 5.0), 'depth': (0.0, 1.0), 'feedback': (0.0, 0.9), 'mix': (0.0, 1.0)},
    'phaser': {'rate': (0.1, 5.0), 'depth': (0.0, 1.0), 'feedback': (0.0, 0.9), 'mix': (0.0, 1.0)},
    'tremolo': {'rate': (1.0, 10.0), 'depth': (0.0, 1.0)},
    'vibrato': {'rate': (1.0, 10.0), 'depth': (0.0, 1.0)},
    'compressor': {'threshold': (-60.0, 0.0), 'ratio': (1.0, 20.0), 'attack': (0.001, 0.1), 'release': (0.01, 0.5)},
    'limiter': {'threshold': (-20.0, 0.0), 'release': (0.01, 0.5)},
    'tube': {'drive': (0.0, 1.0), 'mix': (0.0, 1.0)},
    'tape': {'drive': (0.0, 1.0), 'wow': (0.0, 1.0), 'flutter': (0.0, 1.0)},
    'exciter': {'amount': (0.0, 1.0), 'mix': (0.0, 1.0)},
    'stereo_widen': {'width': (0.0, 2.0)},
    'lofi': {'bits': (2, 12), 'sample_rate': (1000, 22000), 'mix': (0.0, 1.0)},
    'pitch_shift': {'semitones': (-12, 12), 'mix': (0.0, 1.0)},
    'shimmer': {'mix': (0.0, 1.0), 'pitch_shift': (7.0, 12.0)},
    'moog': {'cutoff': (50.0, 10000.0), 'resonance': (0.0, 0.95), 'drive': (0.0, 1.0)},
    '303': {'cutoff': (100.0, 5000.0), 'resonance': (0.5, 0.99), 'env_mod': (0.0, 1.0), 'decay': (0.1, 1.0), 'accent': (0.0, 1.0)},
    'sem': {'cutoff': (50.0, 8000.0), 'resonance': (0.0, 0.9)},
    'ms20': {'cutoff': (50.0, 8000.0), 'resonance': (0.0, 0.95)},
    'space_echo': {'time': (0.05, 1.0), 'feedback': (0.0, 0.9), 'wow': (0.0, 1.0), 'flutter': (0.0, 1.0), 'tone': (0.0, 1.0), 'spring_mix': (0.0, 1.0), 'mix': (0.0, 0.7)},
    'ssl': {'threshold': (-30.0, 0.0), 'ratio': (1.0, 10.0), 'gain': (0.0, 20.0), 'attack_ms': (0.1, 30.0), 'release_ms': (50.0, 1200.0)},
    'neve': {'gain': (0.0, 40.0), 'warmth': (0.0, 1.0)},
    'lexicon': {'size': (0.1, 1.0), 'decay': (0.1, 10.0), 'mix': (0.0, 0.8)},
}

def resolve_rand_float(val, min_val, max_val):
    if isinstance(val, str):
        if val.lower() == 'rand':
            return random.uniform(min_val, max_val)
        if '-' in val and not val.startswith('-'):
            parts = val.split('-')
            if len(parts) == 2:
                try: return random.uniform(float(parts[0]), float(parts[1]))
                except ValueError: pass
    return float(val)

def resolve_rand_int(val, min_val, max_val):
    if isinstance(val, str):
        if val.lower() == 'rand':
            return random.randint(min_val, max_val)
        if '-' in val and not val.startswith('-'):
            parts = val.split('-')
            if len(parts) == 2:
                try: return random.randint(int(float(parts[0])), int(float(parts[1])))
                except ValueError: pass
    try:
        if isinstance(val, (int, float)): return int(val)
        return int(float(val))
    except (ValueError, TypeError):
        return int(min_val)

def resolve_rand_note(val):
    if isinstance(val, str) and val.lower() == 'rand':
        # Pick a random note C2-C5
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = random.randint(2, 5)
        note = random.choice(notes)
        return f"{note}{octave}"
    return val

def resolve_rand_macro(val_str):
    if not val_str: return val_str
    # format: rate=0.5,depth=1.0,targets=filter:cutoff:0.5
    parts = val_str.split(',')
    resolved = []
    for p in parts:
        if '=' not in p:
             resolved.append(p)
             continue
        k, v = p.split('=', 1)
        k = k.strip().lower()
        if v.strip().lower() == 'rand':
             if k == 'rate': v = f"{random.uniform(0.1, 8.0):.2f}"
             elif k == 'depth': v = f"{random.uniform(0.0, 1.0):.2f}"
        
        if k == 'targets':
             # targets=filter:cutoff:rand
             targets = v.split(';') # support multiple targets
             new_targets = []
             for t in targets:
                  subparts = t.split(':')
                  if len(subparts) == 3 and subparts[2].lower() == 'rand':
                       amt = random.uniform(0.0, 1.0)
                       new_targets.append(f"{subparts[0]}:{subparts[1]}:{amt:.2f}")
                  else:
                       new_targets.append(t)
             v = ";".join(new_targets)
        
        resolved.append(f"{k}={v}")
    return ",".join(resolved)

def parse_fx_string(s: str) -> list[dict]:
    """
    Parse a comma-separated FX string with optional parameters.
    Format: "effect1, effect2(param=val), effect3(p1=v1, p2=v2)"
    Returns: [{'type': 'effect1', 'params': {}}, {'type': 'effect2', 'params': {'param': val}}, ...]
    """
    if not s:
        return []

    # Regex to capture "name(params)" or "name"
    pattern = re.compile(r'([a-zA-Z0-9_]+)(?:\(([^)]*)\))?')
    
    # Custom split handling nested parens
    first_pass_items = []
    buffer = ""
    depth = 0
    for char in s:
        if char == ',' and depth == 0:
            first_pass_items.append(buffer.strip())
            buffer = ""
        else:
            if char == '(': depth += 1
            if char == ')': depth -= 1
            buffer += char
    if buffer.strip():
        first_pass_items.append(buffer.strip())
    
    results = []
    for item in first_pass_items:
        m = pattern.fullmatch(item)
        if not m:
            continue
        
        fx_type = m.group(1)
        params_str = m.group(2)
        params = {}

        if params_str:
            # Parse key=value pairs
            pairs = params_str.split(',')
            for p in pairs:
                if '=' in p:
                    k, v = p.split('=', 1)
                    k = k.strip()
                    v = v.strip()
                    # Auto-type conversion
                    if v.lower() == 'true': v = True
                    elif v.lower() == 'false': v = False
                    else:
                        try:
                            if '-' in v and not v.startswith('-'):
                                # Potential range e.g. "0.2-0.8"
                                parts = v.split('-')
                                if len(parts) == 2:
                                    # Verify both are numbers
                                    float(parts[0])
                                    float(parts[1])
                                    # Keep as string for generator to resolve per-sample
                                    pass 
                                else:
                                    v = float(v) if '.' in v else int(v)
                            elif '.' in v:
                                v = float(v)
                            else:
                                v = int(v)
                        except ValueError:
                            # Check for 'rand'
                             if isinstance(v, str) and v.lower() == 'rand':
                                 ranges = FX_PARAM_RANGES.get(fx_type, {})
                                 if k in ranges:
                                     min_v, max_v = ranges[k]
                                     if isinstance(min_v, int) and isinstance(max_v, int):
                                         v = random.randint(min_v, max_v)
                                     else:
                                         v = random.uniform(min_v, max_v)
                                 else:
                                     v = random.random()
                    params[k] = v
        
        results.append({'type': fx_type, 'params': params})
    
    return results

def parse_bus_string(s: str) -> dict:
    """
    Parse a bus configuration string.
    Format: "bus_id:osc1,osc2>fx1,fx2"
    Example: "lead:saw,square>distortion,delay(time=0.2)"
    Returns: {
        'id': 'lead',
        'oscillators': ['saw', 'square'],
        'effects': [{'type': 'distortion'...}, ...]
    }
    """
    if not s: return None
    
    bus_id = "main"
    content = s
    
    # 1. Split ID from Content
    if ':' in s:
        bus_id, content = s.split(':', 1)
        bus_id = bus_id.strip()
        content = content.strip()
        
    # 2. Split Oscillators from Effects ('>')
    if '>' in content:
        osc_part, fx_part = content.split('>', 1)
    else:
        osc_part = content
        fx_part = ""
        
    # 3. Parse Oscillators (comma separated)
    oscillators = [o.strip() for o in osc_part.split(',') if o.strip()]
    
    # 4. Parse Effects (using existing parser)
    effects = parse_fx_string(fx_part)
    
    return {
        'id': bus_id,
        'oscillators': oscillators,
        'effects': effects
    }

