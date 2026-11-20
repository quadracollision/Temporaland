"""
pySynth Spectral Effects – Ring Mod, Frequency Shifter, Stereo Widener.
"""
import numpy as np
from scipy import signal as sig


def apply_ring_mod(audio, freq=200.0, mix=0.5, sample_rate=44100, **kwargs):
    """Ring Modulator – multiply signal by a carrier sine."""
    N = len(audio)
    t = np.arange(N) / sample_rate
    carrier = np.sin(2.0 * np.pi * freq * t)
    if audio.ndim == 2:
        carrier = carrier[:, np.newaxis]
    wet = audio * carrier
    return (1.0 - mix) * audio + mix * wet


def apply_freq_shift(audio, shift_hz=50.0, mix=0.5, sample_rate=44100, **kwargs):
    """
    Frequency Shifter via Hilbert transform (single-sideband modulation).
    Shifts all frequencies by shift_hz (can be negative).
    """
    N = len(audio)
    t = np.arange(N) / sample_rate
    carrier = np.exp(1j * 2.0 * np.pi * shift_hz * t)

    if audio.ndim == 2:
        wet = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            analytic = sig.hilbert(audio[:, ch])
            wet[:, ch] = np.real(analytic * carrier)
    else:
        analytic = sig.hilbert(audio)
        wet = np.real(analytic * carrier)

    return (1.0 - mix) * audio + mix * wet


def apply_stereo_widen(audio, width=0.5, **kwargs):
    """
    Mid/Side stereo widener.
    width 0 = mono, 0.5 = normal, 1.0 = extra wide.
    Only works on stereo (N,2). Passes mono through unchanged.
    """
    if audio.ndim != 2 or audio.shape[1] != 2:
        return audio

    mid  = (audio[:, 0] + audio[:, 1]) * 0.5
    side = (audio[:, 0] - audio[:, 1]) * 0.5

    # width 0..1 scales side.  At 0.5 = unity.
    side_gain = width * 2.0  # 0->0, 0.5->1, 1->2

    out = np.zeros_like(audio)
    out[:, 0] = mid + side * side_gain
    out[:, 1] = mid - side * side_gain
    return out

