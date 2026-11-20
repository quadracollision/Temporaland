"""
pySynth Filter Module – "Every Filter Type"
Biquad-based: LPF, HPF, BPF, Notch, Peaking EQ, Low Shelf, High Shelf, AllPass.
Also: Comb Filter, Formant/Vowel Filter.
All functions accept mono (N,) or stereo (N,2).
"""
import numpy as np
from scipy import signal as sig


# ========================================================================
# Biquad engine (Robert Bristow-Johnson cookbook)
# ========================================================================
def _biquad(audio, b, a):
    """Apply biquad filter along time axis."""
    return sig.lfilter(b, a, audio, axis=0)


def _biquad_coeffs(filter_type, cutoff, Q, gain_db, sample_rate):
    """
    Compute biquad coefficients for a given filter type.
    Returns (b, a) each length 3.
    """
    w0 = 2.0 * np.pi * cutoff / sample_rate
    alpha = np.sin(w0) / (2.0 * Q)
    cos_w0 = np.cos(w0)
    A = 10.0 ** (gain_db / 40.0)   # for peaking/shelving

    b = np.zeros(3)
    a = np.zeros(3)

    if filter_type == 'lowpass':
        b[0] = (1 - cos_w0) / 2
        b[1] =  1 - cos_w0
        b[2] = (1 - cos_w0) / 2
        a[0] =  1 + alpha
        a[1] = -2 * cos_w0
        a[2] =  1 - alpha

    elif filter_type == 'highpass':
        b[0] =  (1 + cos_w0) / 2
        b[1] = -(1 + cos_w0)
        b[2] =  (1 + cos_w0) / 2
        a[0] =  1 + alpha
        a[1] = -2 * cos_w0
        a[2] =  1 - alpha

    elif filter_type == 'bandpass':
        b[0] =  alpha
        b[1] =  0
        b[2] = -alpha
        a[0] =  1 + alpha
        a[1] = -2 * cos_w0
        a[2] =  1 - alpha

    elif filter_type == 'notch':
        b[0] =  1
        b[1] = -2 * cos_w0
        b[2] =  1
        a[0] =  1 + alpha
        a[1] = -2 * cos_w0
        a[2] =  1 - alpha

    elif filter_type == 'allpass':
        b[0] =  1 - alpha
        b[1] = -2 * cos_w0
        b[2] =  1 + alpha
        a[0] =  1 + alpha
        a[1] = -2 * cos_w0
        a[2] =  1 - alpha

    elif filter_type == 'peaking':
        b[0] =  1 + alpha * A
        b[1] = -2 * cos_w0
        b[2] =  1 - alpha * A
        a[0] =  1 + alpha / A
        a[1] = -2 * cos_w0
        a[2] =  1 - alpha / A

    elif filter_type == 'low_shelf':
        sq = 2 * np.sqrt(A) * alpha
        b[0] =     A * ((A + 1) - (A - 1) * cos_w0 + sq)
        b[1] = 2 * A * ((A - 1) - (A + 1) * cos_w0)
        b[2] =     A * ((A + 1) - (A - 1) * cos_w0 - sq)
        a[0] =          (A + 1) + (A - 1) * cos_w0 + sq
        a[1] =    -2 * ((A - 1) + (A + 1) * cos_w0)
        a[2] =          (A + 1) + (A - 1) * cos_w0 - sq

    elif filter_type == 'high_shelf':
        sq = 2 * np.sqrt(A) * alpha
        b[0] =     A * ((A + 1) + (A - 1) * cos_w0 + sq)
        b[1] = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b[2] =     A * ((A + 1) + (A - 1) * cos_w0 - sq)
        a[0] =          (A + 1) - (A - 1) * cos_w0 + sq
        a[1] =     2 * ((A - 1) - (A + 1) * cos_w0)
        a[2] =          (A + 1) - (A - 1) * cos_w0 - sq

    else:
        b[0] = 1; a[0] = 1  # passthrough

    return b, a


# ========================================================================
# Public API
# ========================================================================
def apply_filter(audio, filter_type='lowpass', cutoff=1000.0, resonance=0.5,
                 gain_db=0.0, sample_rate=44100, **kwargs):
    """
    Apply a standard biquad filter.
    
    Parameters:
    filter_type: lowpass, highpass, bandpass, notch, peaking, low_shelf, high_shelf, allpass.
    cutoff:      Frequency in Hz.
    resonance:   Maps to Q  (0.0..1.0 -> Q 0.5..12.0).
    gain_db:     Boost/cut in dB (peaking/shelving only).
    """
    nyq = sample_rate / 2.0
    cutoff = max(20.0, min(cutoff, nyq - 100.0))
    Q = 0.5 + resonance * 11.5
    b, a = _biquad_coeffs(filter_type, cutoff, Q, gain_db, sample_rate)
    return _biquad(audio, b, a)


def apply_comb(audio, delay_ms=5.0, feedback=0.7, mix=0.5,
               sample_rate=44100, **kwargs):
    """
    Feed-forward comb filter.
    Creates metallic / flanging tones by adding a delayed copy of the signal.

    Parameters:
    delay_ms: Delay time in milliseconds (pitch/tone).
    feedback: Feedback amount (0.0..0.99).
    mix:      Wet/Dry mix.
    """
    d = int(delay_ms * sample_rate / 1000.0)
    if d < 1 or d >= len(audio):
        return audio
    b_arr = np.zeros(d + 1)
    b_arr[0] = 1.0
    b_arr[-1] = feedback
    return sig.lfilter(b_arr, [1.0], audio, axis=0)


def apply_formant(audio, vowel='a', mix=1.0, sample_rate=44100, **kwargs):
    """
    Formant / Vowel filter.
    Simulates vocal tract resonances.

    Parameters:
    vowel: Target vowel ('a', 'e', 'i', 'o', 'u').
    mix:   Wet/Dry mix.
    """
    formants = {
        'a': [800, 1150, 2900, 3900, 4950],
        'e': [350,  2000, 2800, 3600, 4950],
        'i': [270,  2140, 2950, 3900, 4950],
        'o': [450,   800, 2830, 3800, 4950],
        'u': [325,   700, 2530, 3500, 4950],
    }
    freqs = formants.get(vowel, formants['a'])
    out = np.zeros_like(audio)
    for f in freqs:
        if f < sample_rate / 2:
            out = out + apply_filter(audio, 'bandpass', f, 0.3, sample_rate=sample_rate)
    return out * 0.3  # attenuate sum

