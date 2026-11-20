"""
pySynth Delay Effects – Mono Delay, Stereo Delay, Ping-Pong.
"""
import numpy as np
from scipy import signal as sig


def apply_delay(audio, time=0.3, feedback=0.5, mix=0.5,
                sample_rate=44100, ping_pong=False, **kwargs):
    """
    Feedback Delay Line.

    Parameters:
    time:     Delay time in seconds.
    feedback: Feedback amount (0.0..0.99).
    mix:      Wet/Dry mix.
    """
    delay_samples = int(time * sample_rate)
    if delay_samples < 1:
        return audio
    if delay_samples >= len(audio):
        delay_samples = len(audio) - 1

    feedback = max(0.0, min(feedback, 0.95))   # safety

    if not ping_pong:
        # IIR comb:  H(z) = 1 / (1 - fb * z^-D)
        a = np.zeros(delay_samples + 1)
        a[0] = 1.0
        a[-1] = -feedback

        wet = sig.lfilter([1.0], a, audio, axis=0)
        return (1.0 - mix) * audio + mix * wet

    else:
        # Ping-pong: alternate echoes left / right
        # Only meaningful for stereo
        if audio.ndim == 1:
            audio = np.column_stack((audio, audio))

        N = len(audio)
        out = np.copy(audio)
        buf_L = np.zeros(delay_samples)
        buf_R = np.zeros(delay_samples)
        pos = 0

        for i in range(N):
            # Read from opposite channel's buffer (ping-pong)
            echo_L = buf_R[pos]
            echo_R = buf_L[pos]

            out_L = audio[i, 0] + echo_L * feedback
            out_R = audio[i, 1] + echo_R * feedback

            buf_L[pos] = out_L
            buf_R[pos] = out_R

            out[i, 0] = (1.0 - mix) * audio[i, 0] + mix * echo_L
            out[i, 1] = (1.0 - mix) * audio[i, 1] + mix * echo_R

            pos = (pos + 1) % delay_samples

        return out

