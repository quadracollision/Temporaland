"""
pySynth Distortion Effects – Drive, Hard Clip, Soft Clip, Tape Saturation,
Bitcrush, Sample Rate Reduction, Sine Fold, Waveshaper, Rectifier.
"""
import numpy as np


def apply_distortion(audio, drive=0.5, dist_type='tanh', **kwargs):
    """
    Multi-mode Distortion / Waveshaping.

    Parameters:
    drive:     Input gain boost (0.0..1.0 -> 1x..21x).
    dist_type: Algorithm ('tanh', 'hard_clip', 'soft_clip', 'sine_fold', 
               'rectify', 'waveshape').
    """
    gain = 1.0 + drive * 20.0
    x = audio * gain

    if dist_type == 'tanh':
        out = np.tanh(x)
    elif dist_type == 'hard_clip':
        out = np.clip(x, -1.0, 1.0)
    elif dist_type == 'soft_clip':
        out = x / (1.0 + np.abs(x))
    elif dist_type == 'sine_fold':
        out = np.sin(x)
    elif dist_type == 'rectify':
        out = np.abs(x)
        out /= max(np.max(np.abs(out)), 1e-9)
    elif dist_type == 'half_rectify':
        out = np.maximum(x, 0.0)
        out /= max(np.max(np.abs(out)), 1e-9)
    elif dist_type == 'waveshape':
        # Chebyshev-style odd harmonics
        out = 1.5 * x - 0.5 * x ** 3
        out = np.clip(out, -1.0, 1.0)
    else:
        out = np.tanh(x)

    # Compensate gain
    out /= (1.0 + drive * 2.0)
    return out


def apply_bitcrush(audio, bit_depth=8, sample_rate_reduction=1, **kwargs):
    """
    Bitcrusher / Downsampler.
    Reduces audio fidelity.

    Parameters:
    bit_depth:             Resolution (2..16 bits).
    sample_rate_reduction: Downsampling factor (1=none, N=keep every Nth sample).
    """
    bd = max(2, min(16, int(bit_depth)))
    levels = 2 ** bd
    out = np.round(audio * levels) / levels

    sr_red = max(1, int(sample_rate_reduction))
    if sr_red > 1:
        if out.ndim == 2:
            for ch in range(out.shape[1]):
                for i in range(len(out)):
                    if i % sr_red != 0:
                        out[i, ch] = out[i - (i % sr_red), ch]
        else:
            for i in range(len(out)):
                if i % sr_red != 0:
                    out[i] = out[i - (i % sr_red)]
    return out

