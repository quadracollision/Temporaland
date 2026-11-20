"""
pySynth Modulation Effects – Chorus, Flanger, Phaser, Tremolo, Vibrato, Auto-Pan.
All handle mono (N,) and stereo (N,2).
"""
import numpy as np
from scipy import signal as sig


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _interp_delay(audio_1d, delay_samples):
    """Linearly-interpolated variable delay for a 1-D signal."""
    n = len(audio_1d)
    idx = np.arange(n, dtype=np.float64)
    read = idx - delay_samples
    return np.interp(read, idx, audio_1d, left=0.0, right=0.0)


# ──────────────────────────────────────────────────────────────
# Chorus
# ──────────────────────────────────────────────────────────────
def apply_chorus(audio, rate=1.5, depth=0.003, voices=2, mix=0.5,
                 sample_rate=44100, **kwargs):
    """
    Multi-voice Chorus.
    Thickens the sound using multiple detuned delay lines.

    Parameters:
    rate:   LFO speed in Hz.
    depth:  Modulation depth (seconds).
    voices: Number of voices.
    mix:    Wet/Dry mix.
    """
    n = len(audio)
    t = np.arange(n) / sample_rate
    wet = np.zeros_like(audio)

    for v in range(voices):
        phase_off = v * (2.0 * np.pi / max(voices, 1))
        lfo = np.sin(2.0 * np.pi * rate * t + phase_off)
        delay_s = (depth + lfo * depth * 0.5) * sample_rate

        if audio.ndim == 2:
            for ch in range(audio.shape[1]):
                wet[:, ch] += _interp_delay(audio[:, ch], delay_s)
        else:
            wet += _interp_delay(audio, delay_s)

    wet /= max(voices, 1)
    return (1.0 - mix) * audio + mix * wet


# ──────────────────────────────────────────────────────────────
# Flanger
# ──────────────────────────────────────────────────────────────
def apply_flanger(audio, rate=0.25, depth=0.002, feedback=0.5, mix=0.5,
                  sample_rate=44100, **kwargs):
    """
    Flanger Effect.
    Creates a sweeping comb filter effect using short delay with feedback.

    Parameters:
    rate:     LFO speed in Hz.
    depth:    Sweep depth (seconds).
    feedback: Feedback amount (0.0..0.99).
    mix:      Wet/Dry mix.
    """
    n = len(audio)
    t = np.arange(n) / sample_rate
    lfo = (np.sin(2.0 * np.pi * rate * t) + 1.0) * 0.5 # 0..1
    
    # Delay range: 1ms to 1ms + depth
    delay_samples = (0.001 + lfo * depth) * sample_rate
    
    def _process_1d(x):
        out = np.zeros_like(x)
        max_d = int((0.001 + depth) * sample_rate) + 2
        buf = np.zeros(max_d)
        ptr = 0
        
        for i in range(n):
            d = delay_samples[i]
            # Linear interpolation
            d_int = int(d)
            d_frac = d - d_int
            
            read_ptr = (ptr - d_int) % max_d
            read_ptr_next = (read_ptr - 1) % max_d
            
            delayed_sample = buf[read_ptr] * (1.0 - d_frac) + buf[read_ptr_next] * d_frac
            
            # Output is wet (delayed)
            out[i] = delayed_sample
            
            # Update buffer with feedback
            buf[ptr] = x[i] + delayed_sample * feedback
            ptr = (ptr + 1) % max_d
            
        return out

    if audio.ndim == 2:
        wet = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            wet[:, ch] = _process_1d(audio[:, ch])
    else:
        wet = _process_1d(audio)

    return (1.0 - mix) * audio + mix * wet


# ──────────────────────────────────────────────────────────────
# Phaser  (series allpass filters modulated by LFO)
# ──────────────────────────────────────────────────────────────
def apply_phaser(audio, rate=0.5, depth=0.5, stages=4, mix=0.5,
                 sample_rate=44100, **kwargs):
    """
    Phaser Effect.
    Creates sweeping notches using cascaded all-pass filters.

    Parameters:
    rate:   LFO speed in Hz.
    depth:  Sweep depth.
    stages: Number of all-pass stages (e.g., 4, 8).
    mix:    Wet/Dry mix.
    """
    n = len(audio)
    t = np.arange(n) / sample_rate
    # LFO sweeps allpass coeff between 0.1 and 0.9
    lfo = np.sin(2.0 * np.pi * rate * t)
    coeff = 0.5 + depth * 0.4 * lfo   # 0.1 .. 0.9

    # Process sample-by-sample (slow but correct for feedback allpass)
    # For speed, process in mono or per-channel
    def _process_1d(x):
        y = np.copy(x)
        # state per stage
        z = np.zeros(stages)
        for i in range(n):
            s = y[i]
            c = coeff[i]
            for st in range(stages):
                allpass_out = -c * s + z[st]
                z[st] = c * allpass_out + s
                s = allpass_out
            y[i] = s
        return y

    if audio.ndim == 2:
        wet = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            wet[:, ch] = _process_1d(audio[:, ch])
    else:
        wet = _process_1d(audio)

    return (1.0 - mix) * audio + mix * wet


# ──────────────────────────────────────────────────────────────
# Tremolo
# ──────────────────────────────────────────────────────────────
def apply_tremolo(audio, rate=5.0, depth=0.5, sample_rate=44100, **kwargs):
    """
    Tremolo Effect.
    Modulates amplitude (volume) with an LFO.

    Parameters:
    rate:  LFO speed in Hz.
    depth: Modulation depth (0.0..1.0).
    """
    n = len(audio)
    t = np.arange(n) / sample_rate
    lfo = np.sin(2.0 * np.pi * rate * t)
    gain = 1.0 - depth * 0.5 * (1.0 + lfo)
    if audio.ndim == 2:
        gain = gain[:, np.newaxis]
    return audio * gain


# ──────────────────────────────────────────────────────────────
# Vibrato  (pitch modulation)
# ──────────────────────────────────────────────────────────────
def apply_vibrato(audio, rate=5.0, depth=0.003, sample_rate=44100, **kwargs):
    """
    Vibrato Effect.
    Modulates pitch using a variable delay line.

    Parameters:
    rate:  LFO speed in Hz.
    depth: Pitch modulation depth.
    """
    n = len(audio)
    t = np.arange(n) / sample_rate
    lfo = np.sin(2.0 * np.pi * rate * t)
    delay_s = depth * (1.0 + lfo) * sample_rate

    if audio.ndim == 2:
        out = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            out[:, ch] = _interp_delay(audio[:, ch], delay_s)
        return out
    return _interp_delay(audio, delay_s)


# ──────────────────────────────────────────────────────────────
# Auto-Pan
# ──────────────────────────────────────────────────────────────
def apply_autopan(audio, rate=2.0, depth=0.8, sample_rate=44100, **kwargs):
    """
    Auto-Pan Effect.
    Pans signal left and right using an LFO.

    Parameters:
    rate:  LFO speed in Hz.
    depth: Panning width (0.0..1.0).
    """
    n = len(audio)
    t = np.arange(n) / sample_rate
    lfo = np.sin(2.0 * np.pi * rate * t)

    if audio.ndim == 1:
        audio = np.column_stack((audio, audio))

    pan = 0.5 + depth * 0.5 * lfo   # 0..1
    out = np.zeros_like(audio)
    out[:, 0] = audio[:, 0] * np.sqrt(1.0 - pan)
    out[:, 1] = audio[:, 1] * np.sqrt(pan)
    return out

