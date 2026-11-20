"""
pySynth Music Theory Utility
Handles note-to-frequency conversion and scale quantization.
"""
import math
import re
import random

NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Scale intervals (semitones from root)
SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],  # Natural minor
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'melodic_minor': [0, 2, 3, 5, 7, 9, 11],
    'pentatonic_major': [0, 2, 4, 7, 9],
    'pentatonic_minor': [0, 3, 5, 7, 10],
    'blues': [0, 3, 5, 6, 7, 10],
    'dorian': [0, 2, 3, 5, 7, 9, 10],
    'phrygian': [0, 1, 3, 5, 7, 8, 10],
    'lydian': [0, 2, 4, 6, 7, 9, 11],
    'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'locrian': [0, 1, 3, 5, 6, 8, 10],
    'chromatic': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    
    # Symmetric
    'whole_tone': [0, 2, 4, 6, 8, 10],
    'diminished': [0, 2, 3, 5, 6, 8, 9, 11],  # Whole-Half
    'augmented': [0, 3, 4, 7, 8, 11],
    
    # Harmonic/Melodic Variations
    'harmonic_major': [0, 2, 4, 5, 7, 8, 11],
    'hungarian_minor': [0, 2, 3, 6, 7, 8, 11],  # Gypsy Minor
    'romanian_minor': [0, 2, 3, 6, 7, 9, 10],   # Dorian #4
    
    # Japanese
    'hirajoshi': [0, 2, 3, 7, 8],
    'in_scale': [0, 1, 5, 7, 8],      # Miyako-bushi
    'iwato': [0, 1, 5, 6, 10],
    
    # Middle Eastern / Exotic
    'byzantine': [0, 1, 4, 5, 7, 8, 11],    # Double Harmonic Major
    'phrygian_dominant': [0, 1, 4, 5, 7, 8, 10], # Hijaz
    'persian': [0, 1, 4, 5, 6, 8, 11],
    'enigmatic': [0, 1, 4, 6, 8, 10, 11],
    
    # Jazz / Bebop
    'bebop_dominant': [0, 2, 4, 5, 7, 9, 10, 11],
    'bebop_major': [0, 2, 4, 5, 7, 8, 9, 11],
    'bebop_minor': [0, 2, 3, 4, 5, 7, 9, 10],   # Dorian + maj7
    
    # Pentatonic Variations
    'egyptian': [0, 2, 5, 7, 10],
    'man_gong': [0, 3, 5, 7, 10],      # Chinese Pentatonic Heptatonic? No, it's penta.
    'ritusen': [0, 2, 5, 7, 9],        # Scottish/Chinese
    'yo': [0, 2, 5, 7, 9],             # Same as Ritusen? Actually Yo is usually [0, 2, 5, 7, 10]? 
                                       # Yo scale (Japan): 0, 2, 5, 7, 9? No that's Ryo. 
                                       # Yo is often [0, 3, 5, 7, 10] (Min'yo)
                                       # Let's use the common Yo definition: [0, 2, 5, 7, 9, 12]?? 
                                       # Actually [0, 2, 5, 7, 9] is Major Pentatonic.
                                       # Let's stick to distinctive ones.
    'minor_six_pentatonic': [0, 3, 5, 7, 9],
    
    # Hexatonic
    'prometheus': [0, 2, 4, 6, 9, 10],
    'prometheus_neapolitan': [0, 1, 4, 6, 9, 10],
    'tritone': [0, 1, 4, 6, 7, 10],        # Petrushka / Two semi-triads
    'wholetone': [0, 2, 4, 6, 8, 10],      # Alias
    
    # Modern Modes / Jazz Theory
    'lydian_dominant': [0, 2, 4, 6, 7, 9, 10], # Overtone / Lydian b7
    'lydian_augmented': [0, 2, 4, 6, 8, 9, 11],
    'locrian_major': [0, 2, 4, 5, 6, 8, 10],    # Locrian natural 2? No, Major Locrian? 
                                                # Locrian #2 is [0, 2, 3, 5, 6, 8, 10]
    'locrian_sharp2': [0, 2, 3, 5, 6, 8, 10],
    'altered': [0, 1, 3, 4, 6, 8, 10],          # Super Locrian
    'super_locrian': [0, 1, 3, 4, 6, 8, 10],    # Alias
    
    # World
    'spanish_gypsy': [0, 1, 4, 5, 7, 8, 10],    # Phrygian Dominant alias
    'pelog': [0, 1, 3, 7, 8],                   # Approximation (5-tone)
    'slendro': [0, 2, 5, 7, 9]                  # Approximation (Salendro) - close to Major Pentatonic
}

NOTE_SEMITONES = {
    'C': 0, 'C#': 1, 'DB': 1, 'D': 2, 'D#': 3, 'EB': 3,
    'E': 4, 'F': 5, 'F#': 6, 'GB': 6, 'G': 7, 'G#': 8,
    'AB': 8, 'A': 9, 'A#': 10, 'BB': 10, 'B': 11,
}

# Suffix-to-intervals for symbolic chord parsing
# Each list is semitones from root (0)
CHORD_TYPES = {
    'm': [0, 3, 7],
    '7': [0, 4, 7, 10],
    'm7': [0, 3, 7, 10],
    'maj7': [0, 4, 7, 11],
    'mM7': [0, 3, 7, 11],
    '6': [0, 4, 7, 9],
    'm6': [0, 3, 7, 9],
    '6/9': [0, 4, 7, 9, 14],
    '5': [0, 7],
    '9': [0, 4, 7, 10, 14],
    'm9': [0, 3, 7, 10, 14],
    'maj9': [0, 4, 7, 11, 14],
    '11': [0, 4, 7, 10, 14, 17],
    'm11': [0, 3, 7, 10, 14, 17],
    'maj11': [0, 4, 7, 11, 14, 17],
    '13': [0, 4, 7, 10, 14, 17, 21],
    'm13': [0, 3, 7, 10, 14, 17, 21],
    'maj13': [0, 4, 7, 11, 14, 17, 21],
    'add': [0, 4, 7, 14], # Typically add9
    '7-5': [0, 4, 6, 10],
    '7+5': [0, 4, 8, 10],
    'sus': [0, 5, 7],
    'sus4': [0, 5, 7],
    'sus2': [0, 2, 7],
    'dim': [0, 3, 6],
    'dim7': [0, 3, 6, 9],
    'm7b5': [0, 3, 6, 10],
    'aug': [0, 4, 8],
    'aug7': [0, 4, 8, 10],
}

# Regex: One note = letter + optional #/b + digit
_NOTE_RE = re.compile(r'([A-Ga-g][#b]?)(\d)')


def note_to_freq(note_str: str) -> float:
    """Convert a single note string like 'C4' or 'F#3' to Hz."""
    m = _NOTE_RE.fullmatch(note_str.strip())
    if not m:
        # Try as raw frequency
        try:
            return float(note_str)
        except ValueError:
            return 440.0
    key = m.group(1).upper()
    octave = int(m.group(2))
    semitone = NOTE_SEMITONES.get(key, 0)
    midi = 12 * (octave + 1) + semitone
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def parse_chord(chord_str: str) -> list[float]:
    """
    Parse a chord string into a list of frequencies.

    Supported formats:
      - Single note:       'C4'        → [261.63]
      - Space-separated:   'C4 E4 G4'  → [261.63, 329.63, 392.00]
      - Concatenated:      'C4E4G4'    → [261.63, 329.63, 392.00]
      - With sharps/flats: 'C4E3F#4G3' → [261.63, 164.81, 369.99, 196.0]
      - Raw frequency:     '440'       → [440.0]
    """
    chord_str = chord_str.strip()

    # 1. Try space-separated first (e.g. 'C4 E4 G4')
    if ' ' in chord_str:
        return [note_to_freq(n) for n in chord_str.split()]

    # 2. Try Symbolic Chord parsing (e.g. 'Cmaj7', 'C4m7b5', 'C')
    # Pattern: [Root][Accidental]?[Octave]?[Suffix]
    # We restrict accidental to [#b] to avoid greediness with 'sus' or 'b5'
    chord_sym_re = re.compile(r'^([A-Ga-g][#bB]?)([0-9])?(.*)$')
    m = chord_sym_re.fullmatch(chord_str)
    if m:
        root_key = m.group(1)
        oct_match = m.group(2)
        suffix = m.group(3)
        
        # Logic to decide if it's a chord or a single note:
        # 1. Try treating (oct_match + suffix) as a single chord suffix (e.g. '7', '9', '11')
        # 2. Try treating suffix alone as a chord suffix with oct_match as the octave (e.g. '4maj7')
        # 3. If suffix is empty and no octave (e.g. 'C'), default to Major triad.
        
        intervals = None
        oct_val = 4 # Default
        
        full_suffix = (oct_match if oct_match else "") + suffix
        if full_suffix in CHORD_TYPES:
            intervals = CHORD_TYPES[full_suffix]
        elif suffix in CHORD_TYPES:
            intervals = CHORD_TYPES[suffix]
            oct_val = int(oct_match) if oct_match else 4
        elif not suffix and not oct_match:
            intervals = [0, 4, 7]
            
        if intervals is not None:
            root_semitone = get_key_root_semitone(root_key)
            root_midi = 12 * (oct_val + 1) + root_semitone
            return [midi_to_freq(root_midi + i) for i in intervals]

    # 3. Try as a single note (e.g. 'C4', '440')
    single_note_freq = note_to_freq(chord_str)
    # If it's a valid note (matches pattern) OR matches a raw frequency float
    if _NOTE_RE.fullmatch(chord_str) or re.fullmatch(r'^\d+(\.\d+)?$', chord_str):
        return [single_note_freq]

    # 4. Try concatenated notes (e.g. 'C4E4G4')
    matches = _NOTE_RE.findall(chord_str)
    if matches and not any(c.isspace() for c in chord_str):
        freqs = []
        for key, octave in matches:
            semitone = NOTE_SEMITONES.get(key.upper(), 0)
            midi = 12 * (int(octave) + 1) + semitone
            freqs.append(midi_to_freq(midi))
        return freqs

    # Fallback: try float
    try:
        return [float(chord_str)]
    except ValueError:
        return [440.0]

def freq_to_midi(freq):
    """Convert Hz to MIDI note number (float)."""
    if freq <= 0: return 0
    return 69 + 12 * math.log2(freq / 440.0)

def midi_to_freq(midi_note):
    """Convert MIDI note number to Hz."""
    return 440.0 * 2**((midi_note - 69) / 12.0)

def get_key_root_semitone(root_note) -> int:
    """Helper to parse root note string (e.g. 'C', 'Cs', 'Bb') to semitone index 0-11."""
    if not isinstance(root_note, str): return 0
    rn = root_note.upper().replace('S', '#')
    # Handle Flats and redundant names
    flats = {'DB': 'C#', 'EB': 'D#', 'GB': 'F#', 'AB': 'G#', 'BB': 'A#', 'CB': 'B', 'FB': 'E'}
    if rn in flats:
        rn = flats[rn]
    return NOTES.index(rn) if rn in NOTES else 0

def _get_scale_intervals(scale_name_or_def):
    """
    Resolve scale name (e.g. 'major') or definition (e.g. '0,2,4') to interval list.
    Returns None if invalid.
    """
    if not scale_name_or_def:
        return None
        
    s = str(scale_name_or_def).lower().strip()
    
    # Check known presets
    if s in SCALES:
        return SCALES[s]
        
    # Check custom definition "0,2,4,7,9"
    # Must contain commas and digits
    if ',' in s and any(c.isdigit() for c in s):
        try:
            parts = [int(x.strip()) for x in s.split(',')]
            # Sort and ensure 0 is present? Or just trust user?
            # Standardize: sorted, unique, starts with 0?
            # Let's just return normalized sorted list modulo 12?
            # Actually user might want spacing > 12? Unlikely for "scale".
            # Let's keep it simple: trusted values modulo 12, then unique sorted.
            intervals = sorted(list(set([p % 12 for p in parts])))
            return intervals
        except ValueError:
            pass
            
    return None

def quantize_freq_to_scale(freq, scale_name='major', root_note='C'):
    """
    Quantize a frequency to the nearest note in the specified scale.
    """
    scale_intervals = _get_scale_intervals(scale_name)
    if not scale_intervals:
        # Fallback or silent error? Let's return original
        return freq

    midi_float = freq_to_midi(freq)
    midi_int = round(midi_float)
    
    # 0 = C, 1 = C#, etc.
    # Find root offset
    # 0 = C, 1 = C#, etc.
    # Find root offset
    root_idx = get_key_root_semitone(root_note)
        
    # scale_intervals already populated above
    
    # Find nearest valid note
    # Simplest way: check neighbors
    # This is a bit brute force but safe
    
    min_dist = 100.0
    best_midi = midi_int
    
    # Check a range of +/- 12 semitones to be sure (overkill but safe)
    # Actually just checking range within octave is enough but we need to map to absolute midi
    
    # To optimize: map midi_int to (note_class, octave)
    # note_class is 0..11 relative to C
    # We want (note_class - root_idx) % 12 to be in scale_intervals
    
    for offset in range(-6, 7):
        candidate = midi_int + offset
        note_class = candidate % 12
        interval = (note_class - root_idx) % 12
        
        if interval in scale_intervals:
            dist = abs(midi_float - candidate)
            if dist < min_dist:
                min_dist = dist
                best_midi = candidate
                
    return midi_to_freq(best_midi)


def get_diatonic_triad(freq, scale_name='major', root_note='C'):
    """
    Return a list of 3 frequencies [root, 3rd, 5th] forming a diatonic triad
    based on the input frequency within the given scale key.
    If the input frequency is not in the scale, it is quantized first.
    """
    scale_intervals = _get_scale_intervals(scale_name)
    if not scale_intervals:
        # Fallback to Major triad logic if scale unknown
        return [freq, freq * 1.2599, freq * 1.4983] # approx maj 3rd, perf 5th
    
    # 1. Be sure we start on the grid
    root_freq = quantize_freq_to_scale(freq, scale_name, root_note)
    
    # 2. Get scale data
    scale_len = len(scale_intervals)
    
    # 3. Find where our note is in the scale
    # Normalize everything to MIDI math
    midi_val = freq_to_midi(root_freq)
    midi_int = int(round(midi_val))
    
    
    # Resolve Key Root MIDI (0-11)
    # Resolve Key Root MIDI (0-11)
    key_root_semitone = get_key_root_semitone(root_note)
        
    # Find scale index
    # (Note MIDI - Key Root) % 12 should match an interval in SCALES
    rel_semitone = (midi_int - key_root_semitone) % 12
    
    try:
        scale_idx = scale_intervals.index(rel_semitone)
    except ValueError:
        # Should be impossible due to quantize step, but safety fallback
        scale_idx = 0
        
    # 4. Pick diatonic intervals (Root, 3rd, 5th -> Indices: i, i+2, i+4)
    # We must handle octave wrapping logic carefully
    
    chord_freqs = []
    for degree_offset in [0, 2, 4]:
        target_idx_raw = scale_idx + degree_offset
        
        # Calculate how many octaves we wrapped
        octave_shift = target_idx_raw // scale_len
        target_idx_norm = target_idx_raw % scale_len
        
        # Get the semitone interval from the scale Key
        target_semitone_rel = scale_intervals[target_idx_norm]
        
        # Reconstruct absolute MIDI note
        # We need the original octave of the Key Root that matches our current note's octave context?
        # Actually simpler: 
        # Base MIDI = (midi_int // 12) * 12 + key_root_semitone
        # If midi_int < Base MIDI, we are in prev octave?
        # Let's rely on the difference from the current note's 'rel_semitone'
        
        # Delta in semitones within the scale structure
        # (Target Interval + 12*OctaveShift) - Start Interval
        semitone_delta = (target_semitone_rel + (12 * octave_shift)) - rel_semitone
        
        chord_note_midi = midi_int + semitone_delta
        chord_freqs.append(midi_to_freq(chord_note_midi))
        
    return chord_freqs


def get_random_scale_note(root_freq, scale_name='major', root_note='C', octave_range=1):
    """
    Return a random frequency from the scale, centered around root_freq.
    octave_range: +/- octaves to pick from (default 1 = spanning 2 octaves total)
    """
    scale_intervals = _get_scale_intervals(scale_name)
    if not scale_intervals:
        return root_freq
    
    # 1. Be sure root is on grid
    root_freq = quantize_freq_to_scale(root_freq, scale_name, root_note)
    
    # 2. Get scale data
    scale_len = len(scale_intervals)
    
    # 3. Find root index/midi
    midi_val = freq_to_midi(root_freq)
    root_midi = int(round(midi_val))
    
    # We want to pick a random interval offset from the root
    # Range of scale degrees to pick from
    # E.g. octave_range=1 means +/- 1 octave = +/- len(scale) degrees
    
    max_degree = scale_len * octave_range
    min_degree = -max_degree
    
    degree_offset = random.randint(min_degree, max_degree)
    
    # Calculate note similar to triad logic
    # But just for one note
    
    # Current note index in scale relative to key?
    # Actually we can just treat root_midi as our anchor
    # But we need to stay IN key.
    # If root_midi is already in key (it is, quantized), we just move by scale degrees.
    
    # Find current scale index relative to Key Root
    # Find current scale index relative to Key Root
    key_root_semitone = get_key_root_semitone(root_note)
        
    rel_semitone = (root_midi - key_root_semitone) % 12
    try:
        current_scale_idx = scale_intervals.index(rel_semitone)
    except ValueError:
        current_scale_idx = 0
        
    target_idx_raw = current_scale_idx + degree_offset
    
    octave_shift = target_idx_raw // scale_len
    target_idx_norm = target_idx_raw % scale_len
    
    target_semitone_rel = scale_intervals[target_idx_norm]
    
    semitone_delta = (target_semitone_rel + (12 * octave_shift)) - rel_semitone
    
    result_midi = root_midi + semitone_delta
    return midi_to_freq(result_midi)




def get_key_accidentals(root_note: str) -> str:
    """
    Return '#' or 'b' based on standard key signatures.
    Flat Keys: F, Bb, Eb, Ab, Db, Gb, Cb
    Sharp Keys: G, D, A, E, B, F#, C#
    C is neutral (defaults to sharp in our system, so we return '#')
    """
    if not root_note: return '#'
    rn = root_note[0].upper()
    if len(root_note) > 1:
        acc = root_note[1]
        if acc == 'b': return 'b'
        if acc == '#': return '#'
    
    # Naturals that are flat keys
    if rn == 'F': return 'b'
    return '#'


def get_scale_sequence(root_freq, scale_name='major', root_note='C', octaves=1):
    """
    Return a list of single-note frequency lists (chord format) for the scale.
    E.g. [[261.6], [293.6], ...] for C Major.
    """
    scale_intervals = _get_scale_intervals(scale_name)
    if not scale_intervals:
        return [[root_freq]]

    # 1. Be sure root is on grid
    root_freq = quantize_freq_to_scale(root_freq, scale_name, root_note)
    
    # 2. Get scale data
    scale_len = len(scale_intervals)
    
    # 3. Find root midi
    midi_val = freq_to_midi(root_freq)
    root_midi = int(round(midi_val))
    
    key_root_semitone = get_key_root_semitone(root_note)
    rel_semitone = (root_midi - key_root_semitone) % 12

    try:
        current_scale_idx = scale_intervals.index(rel_semitone)
    except ValueError:
        current_scale_idx = 0

    sequence = []
    # Generate notes from degree 0 to (len * octaves)
    # We start from current_scale_idx? 
    # Or do we want the scale starting from the root note provided?
    # Yes, from root_freq upwards.
    
    total_steps = scale_len * octaves + 1 # +1 to include octave at top? Usually sweep includes octave.
    
    for i in range(total_steps):
        degree_offset = i
        
        target_idx_raw = current_scale_idx + degree_offset
        octave_shift = target_idx_raw // scale_len
        target_idx_norm = target_idx_raw % scale_len
        
        target_semitone_rel = scale_intervals[target_idx_norm]
        semitone_delta = (target_semitone_rel + (12 * octave_shift)) - rel_semitone
        
        note_midi = root_midi + semitone_delta
        freq = midi_to_freq(note_midi)
        sequence.append([freq])
        
    return sequence
ROMAN_MAP = {
    'i': 0, 'ii': 2, 'iii': 4, 'iv': 5, 'v': 7, 'vi': 9, 'vii': 11,
    'I': 0, 'II': 2, 'III': 4, 'IV': 5, 'V': 7, 'VI': 9, 'VII': 11
}

def parse_roman_progression(prog_str, root_note='C', scale_name='major'):
    """
    Convert a Roman numeral string (e.g., 'i-VI-IV-v') into a list of frequency lists.
    Each frequency list represents a diatonic triad.
    """
    scale_intervals = _get_scale_intervals(scale_name)
    if not scale_intervals:
        scale_intervals = SCALES['major']
        
    root_idx = get_key_root_semitone(root_note)
    # Start at octave 4 for chord progression if not specified
    base_midi = 12 * 5 + root_idx 
    
    # Split by hyphen or space
    tokens = re.split(r'[- ]+', prog_str.strip())
    chord_list = []
    
    for token in tokens:
        # 1. Clean token (remove 7ths, etc. for now, just look at root)
        m = re.match(r'([ivIV]+)', token)
        if not m: continue
        roman = m.group(1)
        
        # 2. Get the degree (0-indexed from root of scale)
        degree_map = {
            'i': 0, 'ii': 1, 'iii': 2, 'iv': 3, 'v': 4, 'vi': 5, 'vii': 6,
            'I': 0, 'II': 1, 'III': 2, 'IV': 3, 'V': 4, 'VI': 5, 'VII': 6
        }
        degree = degree_map.get(roman, 0)
        
        # 3. Get the semitone offset for this degree in the scale
        if degree < len(scale_intervals):
            interval = scale_intervals[degree]
        else:
            interval = 0
            
        chord_root_midi = base_midi + interval
        chord_root_freq = midi_to_freq(chord_root_midi)
        
        # 4. Generate diatonic triad
        triad = get_diatonic_triad(chord_root_freq, scale_name, root_note)
        chord_list.append(triad)
        
    return chord_list

