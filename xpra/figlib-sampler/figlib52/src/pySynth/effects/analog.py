import numpy as np
from scipy import signal

def apply_tube_saturation(audio, drive=0.5, asymmetry=0.2):
    """
    Tube Saturation.
    Adds even harmonics for warmth and asymmetric clipping.

    Parameters:
    drive:     Input gain / saturation amount (0.0..1.0).
    asymmetry: DC offset / asymmetric balance (0.0..1.0).
    """
    # y = (x + bias) - (x + bias)^2 ...
    # Simplified: Mix of tanh and x^2
    
    gain = 1.0 + drive * 10.0
    x = audio * gain
    
    # Asymmetry: add simpler even harmonic
    # x_asym = x + asymmetry * (x**2) # This adds DC offset!
    # Better: Soft clip positive differently than negative?
    
    # Transfer function:
    # if x < -1: -1
    # if x > 1: 1
    # else: x - a*x^2 ? 
    
    # Let's use a standard waveshaper approach
    q = x + asymmetry
    output = np.tanh(q)
    
    # Remove DC offset caused by asymmetry
    # If stereo, mean per channel
    output -= np.mean(output, axis=0)
    
    # Normalize level preservation roughly
    output /= (1.0 + drive)
    
    return output

def apply_tape(audio, saturation=0.5, wow=0.1, flutter=0.1, sample_rate=44100):
    """
    Tape Emulation.
    Simulates magnetic tape saturation, wow, and flutter.

    Parameters:
    saturation: Drive / compression amount.
    wow:        Slow pitch wobble intensity.
    flutter:    Fast pitch jitter intensity.
    """
    
    # 1. Saturation (Soft clip)
    saturated = np.tanh(audio * (1.0 + saturation * 5.0))
    # Compensate gain roughly
    saturated *= (0.8 / (1.0 + saturation))
    
    # 2. Wow & Flutter (Pitch wobble)
    
    n = len(audio)
    t = np.arange(n) / sample_rate
    
    wow_freq = 1.0 # Hz
    flut_freq = 12.0 # Hz
    
    wow_depth = 0.005 * wow # +/- 5ms max
    flut_depth = 0.001 * flutter # +/- 1ms max
    
    # LFOs
    mod = wow_depth * np.sin(2*np.pi*wow_freq*t) + flut_depth * np.sin(2*np.pi*flut_freq*t)
    
    # Apply interpolation
    indices = np.arange(n)
    delay_samples = mod * sample_rate
    read_indices = indices - delay_samples 
    
    if audio.ndim == 2:
        output = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            output[:, ch] = np.interp(read_indices, indices, saturated[:, ch], left=0.0, right=0.0)
    else:
        output = np.interp(read_indices, indices, saturated, left=0.0, right=0.0)
    
    return output

def apply_exciter(audio, amount=0.5, cutoff=3000, sample_rate=44100):
    """
    Harmonic Exciter.
    Adds high-frequency harmonics to brighten the sound.

    Parameters:
    amount: Exciter mix / intensity.
    cutoff: Highpass frequency for harmonic generation.
    """
    # Highpass
    # sosfilt supports axis, default -1. 
    # For (N, 2), axis=0 is needed? 
    # sosfilt docs: axis=-1 by default. 
    # If input is (N, 2), axis=-1 is channels (2). We want to filter along N (time).
    # So axis=0.
    
    sos = signal.butter(10, cutoff, 'hp', fs=sample_rate, output='sos')
    highs = signal.sosfilt(sos, audio, axis=0)
    
    # Generate harmonics (rectify or distortion)
    harmonics = np.tanh(highs * 5.0) 
    
    # Highpass again to remove DC/lows introduced by distortion
    harmonics = signal.sosfilt(sos, harmonics, axis=0)
    
    # Mix
    return audio + harmonics * amount * 0.5

