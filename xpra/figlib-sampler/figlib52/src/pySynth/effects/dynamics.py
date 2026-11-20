import numpy as np

def apply_compressor(audio, threshold=-20.0, ratio=4.0, attack=0.01, release=0.1, makeup_gain=0.0, sample_rate=44100):
    """
    Simulated VCA/Digital Compressor.
    Reduces dynamic range by attenuating peaks above a threshold.

    Parameters:
    threshold:   Level above which compression starts (dBFS, e.g. -20).
    ratio:       Compression ratio (e.g. 4.0 for 4:1).
    attack:      Attack time in seconds.
    release:     Release time in seconds.
    makeup_gain: Output gain in dB.
    """
    # Convert threshold to linear
    thresh_lin = 10 ** (threshold / 20.0)
    
    # Envelope follower
    num_samples = len(audio)
    
    # Detect shape
    if audio.ndim == 1:
        channels = 1
        envelope = np.zeros(num_samples)
        current_env = 0.0
    else:
        channels = audio.shape[1]
        envelope = np.zeros_like(audio)
        current_env = np.zeros(channels)
    
    # Simple attack/release coeffs
    # alpha = exp(-1 / (time * fs))
    # We use a simple one-pole smoothing
    alpha_att = np.exp(-1.0 / (attack * sample_rate))
    alpha_rel = np.exp(-1.0 / (release * sample_rate))
    
    # Run envelope loop (slow in python, but necessary for feedback/feedforward dynamics)
    # Optimization: Numba could speed this up 100x. For now pure python/numpy.
    
    # Rectify
    abs_audio = np.abs(audio)
    
    # Vectorized envelope approximation? 
    # Hard to do true attack/release without loop.
    # Let's try a loop. 44k iterations is okay-ish for offline.
    
    for i in range(num_samples):
        inp = abs_audio[i]
        # In stereo, inp is (2,)
        # Logic matches for vector operations if alpha is scalar
        
        # Check attack/release condition per channel?
        # If inp > current_env: attack else release
        # This is conditional per channel.
        # Vectorized conditional:
        # env = where(inp > curr, att_eq, rel_eq)
        
        is_attack = inp > current_env
        
        # Calculate candidates
        val_att = alpha_att * current_env + (1.0 - alpha_att) * inp
        val_rel = alpha_rel * current_env + (1.0 - alpha_rel) * inp
        
        current_env = np.where(is_attack, val_att, val_rel)
        envelope[i] = current_env
        
    # Calculate gain reduction
    # if env < thresh, gain = 1
    # if env > thresh, output = thresh + (env - thresh) / ratio
    # Gain = output / input
    
    # Log domain calculation is easier
    # Avoid log(0)
    env_db = 20 * np.log10(envelope + 1e-9)
    
    gain_db = np.zeros_like(env_db)
    over_thresh = env_db > threshold
    
    # gain_db[over_thresh] = threshold + (env_db[over_thresh] - threshold) / ratio - env_db[over_thresh]
    # Simplified: reduction = (1 - 1/ratio) * (env - thresh)
    # Output dB = Thresh + (Input - Thresh)/Ratio
    # Gain dB = Output - Input = Thresh + (Input - Thresh)/Ratio - Input
    # = (Thresh - Input) * (1 - 1/Ratio)
    
    gain_db[over_thresh] = (threshold - env_db[over_thresh]) * (1.0 - 1.0/ratio)
    
    # Apply makeup
    gain_db += makeup_gain
    
    # Convert to linear
    gain_lin = 10 ** (gain_db / 20.0)
    
    return audio * gain_lin

def apply_limiter(audio, ceiling=-0.1, release=0.05, sample_rate=44100):
    """
    Lookahead Limiter.
    Prevents clipping by hard-limiting peaks to the ceiling.

    Parameters:
    ceiling: Maximum output level in dBFS (e.g. -0.1).
    release: Release time in seconds.
    """
    # Simply use compressor with Inf ratio and fast attack?
    # Ceiling in dB
    return apply_compressor(audio, threshold=ceiling, ratio=100.0, attack=0.001, release=release, makeup_gain=0.0, sample_rate=sample_rate)

