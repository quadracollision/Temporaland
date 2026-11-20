import numpy as np
from scipy import signal

def apply_reverb(audio, decay=0.5, mix=0.3, sample_rate=44100):
    """
    Schroeder Reverb Implementation.
    Classic digital reverb using parallel comb filters and series allpass filters.

    Parameters:
    decay:  Reverb time (0.0..1.0, maps to ~0.5s..5.0s).
    mix:    Wet/Dry mix (0.0..1.0).
    """
    t60 = 0.5 + (decay * 4.5)
    
    delays_ms = [29.7, 37.1, 41.1, 43.7]
    delays_samples = [int(d * sample_rate / 1000.0) for d in delays_ms]
    
    combs_out = np.zeros_like(audio)
    
    for d_samples in delays_samples:
        # Calculate gain for this comb
        # g = 10 ^ (-3 * (d/fs) / T60) = 10 ^ (-3 * d_sec / t60)
        d_sec = d_samples / sample_rate
        g = 10 ** (-3 * d_sec / t60)
        
        # Comb Filter: y[n] = x[n] + g * y[n-D]
        # b = [1], a = [1, 0... -g]
        b = [1.0]
        a = np.zeros(d_samples + 1)
        a[0] = 1.0
        a[-1] = -g
        
        comb_signal = signal.lfilter(b, a, audio, axis=0)
        combs_out += comb_signal
        
    # Series Allpass Filters
    # Delays: 5.0, 1.7 ms
    # Gain usually 0.7
    ap_delays_ms = [5.0, 1.7]
    ap_delays_samples = [int(d * sample_rate / 1000.0) for d in ap_delays_ms]
    ap_gain = 0.7
    
    last_out = combs_out
    
    for d_samples in ap_delays_samples:
        # Allpass: H(z) = (-g + z^-D) / (1 - g*z^-D)
        # b = [-g, 0... 1]
        # a = [1, 0... -g]
        b = np.zeros(d_samples + 1)
        b[0] = -ap_gain
        b[-1] = 1.0
        
        a = np.zeros(d_samples + 1)
        a[0] = 1.0
        a[-1] = -ap_gain
        
        last_out = signal.lfilter(b, a, last_out, axis=0)
        
    # Wet/Dry Mix
    # Reverb output can be loud, maybe normalize?
    # Simple mix
    output = (1.0 - mix) * audio + mix * (last_out * 0.2) # attenuate wet a bit
    
    return output

