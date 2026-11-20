"""
pySynth Creative Effects – Wavefolder, Resonator, Lo-Fi, Granular Stutter,
Pitch Shifter, Sub-Bass Generator, Gate, Transient Shaper, Ensemble, DC Remove.
"""
import numpy as np
from scipy import signal as sig


# ══════════════════════════════════════════════════════════════
# Wavefolder  (West-Coast synthesis staple)
# ══════════════════════════════════════════════════════════════
def apply_wavefolder(audio, folds=3, gain=2.0, symmetry=1.0, **kwargs):
    """
    Wavefolder (West Coast Synthesis).
    Folds the waveform back on itself for rich harmonic generation.

    Parameters:
    folds:    Number of folding stages (1..8).
    gain:     Input drive (adds more folds).
    symmetry: Asymmetric folding (1.0 = symmetric).
    """
    x = audio * gain
    for _ in range(int(folds)):
        # Triangle fold: reflect at ±1
        x = np.arcsin(np.clip(np.sin(x * np.pi / 2.0), -1.0, 1.0)) * 2.0 / np.pi
        x *= symmetry
    # Compensate gain
    mx = np.max(np.abs(x))
    if mx > 0:
        x /= mx
    return x


# ══════════════════════════════════════════════════════════════
# Resonator  (tuned bandpass bank for metallic / body resonance)
# ══════════════════════════════════════════════════════════════
def apply_resonator(audio, freq=200.0, decay=0.98, mix=0.5,
                    harmonics=4, sample_rate=44100, **kwargs):
    """
    Tuned Resonator.
    Bank of bandpass filters tuned to harmonic series.

    Parameters:
    freq:      Base frequency (pitch).
    decay:     Resonance time (Q factor).
    harmonics: Number of harmonic partials.
    mix:       Wet/Dry mix.
    """
    out = np.zeros_like(audio)
    for h in range(1, harmonics + 1):
        f = freq * h
        if f >= sample_rate / 2:
            break
        Q = 10.0 + decay * 40.0  # higher decay = tighter Q
        w0 = 2.0 * np.pi * f / sample_rate
        alpha = np.sin(w0) / (2.0 * Q)
        cos_w0 = np.cos(w0)
        # BPF coefficients
        b = [alpha, 0, -alpha]
        a = [1 + alpha, -2 * cos_w0, 1 - alpha]
        filtered = sig.lfilter(b, a, audio, axis=0)
        out += filtered / h  # attenuate higher harmonics
    mx = np.max(np.abs(out))
    if mx > 0:
        out /= mx
    return (1.0 - mix) * audio + mix * out


# ══════════════════════════════════════════════════════════════
# Lo-Fi  (combined degradation: bit reduction + noise + filter)
# ══════════════════════════════════════════════════════════════
def apply_lofi(audio, amount=0.5, sample_rate=44100, **kwargs):
    """
    Lo-Fi Degradation.
    Combined bitcrushing, downsampling, noise, and filtering.

    Parameters:
    amount: Global degradation intensity (0.0..1.0).
    """
    x = np.copy(audio)

    # 1. Sample rate reduction  (hold samples)
    hold = max(1, int(1 + amount * 8))
    if hold > 1:
        if x.ndim == 2:
            for ch in range(x.shape[1]):
                for i in range(len(x)):
                    if i % hold != 0:
                        x[i, ch] = x[i - (i % hold), ch]
        else:
            for i in range(len(x)):
                if i % hold != 0:
                    x[i] = x[i - (i % hold)]

    # 2. Bit reduction
    bits = max(3, int(16 - amount * 12))
    levels = 2 ** bits
    x = np.round(x * levels) / levels

    # 3. Add hiss
    noise_level = amount * 0.03
    noise = np.random.randn(*x.shape) * noise_level
    x = x + noise

    # 4. LP filter (simulating cheap DAC)
    cutoff = max(500, 15000 - amount * 12000)
    sos = sig.butter(4, cutoff, 'lp', fs=sample_rate, output='sos')
    x = sig.sosfilt(sos, x, axis=0)

    return x


# ══════════════════════════════════════════════════════════════
# Granular Stutter
# ══════════════════════════════════════════════════════════════
def apply_stutter(audio, grain_size_ms=50, repeats=3, mix=0.5,
                  sample_rate=44100, **kwargs):
    """
    Granular Stutter.
    Chops audio into grains and repeats them for glitch effects.

    Parameters:
    grain_size_ms: Duration of each grain in milliseconds.
    repeats:       Number of times to repeat each grain.
    mix:           Wet/Dry mix.
    """
    grain_samples = max(1, int(grain_size_ms * sample_rate / 1000))
    out = np.copy(audio)
    n = len(audio)
    pos = 0
    while pos + grain_samples <= n:
        grain = audio[pos:pos + grain_samples].copy()
        # Repeat grain in-place
        for r in range(1, repeats + 1):
            write_pos = pos + r * grain_samples
            end = write_pos + grain_samples
            if end > n:
                break
            out[write_pos:end] = grain * (0.8 ** r)  # decay repeats
        pos += grain_samples * (repeats + 1)
    return (1.0 - mix) * audio + mix * out


# ══════════════════════════════════════════════════════════════
# Sub-Bass Generator  (octave-down via rectification)
# ══════════════════════════════════════════════════════════════
def apply_sub_bass(audio, mix=0.3, sample_rate=44100, **kwargs):
    """
    Sub-Bass Generator.
    Adds a synthesized sub-octave layer using rectification.

    Parameters:
    mix: Level of the added sub-bass.
    """
    # Rectify → creates octave-down fundamental
    rectified = np.abs(audio)

    # Heavy lowpass to extract the sub
    sos = sig.butter(6, 150, 'lp', fs=sample_rate, output='sos')
    sub = sig.sosfilt(sos, rectified, axis=0)

    # Remove DC
    sub -= np.mean(sub, axis=0)

    return audio + sub * mix


# ══════════════════════════════════════════════════════════════
# Noise Gate
# ══════════════════════════════════════════════════════════════
def apply_gate(audio, threshold=-40.0, attack=0.001, release=0.05,
               sample_rate=44100, **kwargs):
    """
    Noise Gate.
    Silences audio below a set threshold.

    Parameters:
    threshold: Threshold in dBFS.
    attack:    Gate opening time (seconds).
    release:   Gate closing time (seconds).
    """
    thresh_lin = 10.0 ** (threshold / 20.0)
    n = len(audio)

    if audio.ndim == 2:
        env_input = np.max(np.abs(audio), axis=1)
    else:
        env_input = np.abs(audio)

    # Smooth envelope
    alpha_a = np.exp(-1.0 / max(1, attack * sample_rate))
    alpha_r = np.exp(-1.0 / max(1, release * sample_rate))

    env = np.zeros(n)
    cur = 0.0
    for i in range(n):
        inp = env_input[i]
        if inp > cur:
            cur = alpha_a * cur + (1.0 - alpha_a) * inp
        else:
            cur = alpha_r * cur + (1.0 - alpha_r) * inp
        env[i] = cur

    gate_gain = np.where(env > thresh_lin, 1.0, 0.0)

    # Smooth gate transitions to avoid clicks
    sos = sig.butter(2, 200, 'lp', fs=sample_rate, output='sos')
    gate_gain = sig.sosfilt(sos, gate_gain)
    gate_gain = np.clip(gate_gain, 0.0, 1.0)

    if audio.ndim == 2:
        gate_gain = gate_gain[:, np.newaxis]

    return audio * gate_gain


# ══════════════════════════════════════════════════════════════
# Transient Shaper
# ══════════════════════════════════════════════════════════════
def apply_transient_shaper(audio, attack_gain=1.5, sustain_gain=1.0,
                           sensitivity=0.01, sample_rate=44100, **kwargs):
    """
    Transient Shaper.
    Independent control over attack and sustain levels.

    Parameters:
    attack_gain:  Multiplier for attack phase (e.g. 1.5 = punchy).
    sustain_gain: Multiplier for sustain phase (e.g. 0.8 = tight).
    sensitivity:  Envelope follower speed (controls transient detection).
    """
    n = len(audio)

    if audio.ndim == 2:
        env_input = np.max(np.abs(audio), axis=1)
    else:
        env_input = np.abs(audio)

    # Fast envelope (attack detector)
    alpha_fast = np.exp(-1.0 / max(1, sensitivity * sample_rate))
    # Slow envelope (sustain detector)
    alpha_slow = np.exp(-1.0 / max(1, sensitivity * 10 * sample_rate))

    env_fast = np.zeros(n)
    env_slow = np.zeros(n)
    cf = 0.0
    cs = 0.0
    for i in range(n):
        inp = env_input[i]
        cf = max(inp, alpha_fast * cf)
        cs = max(inp, alpha_slow * cs)
        env_fast[i] = cf
        env_slow[i] = cs

    # Transient = fast - slow (positive during attacks)
    transient = np.maximum(env_fast - env_slow, 0.0)
    sustain_mask = 1.0 - transient / (np.max(transient) + 1e-9)

    # Build gain curve
    gain = transient * attack_gain + sustain_mask * sustain_gain
    gain /= (np.max(gain) + 1e-9)

    if audio.ndim == 2:
        gain = gain[:, np.newaxis]

    return audio * gain


# ══════════════════════════════════════════════════════════════
# Ensemble  (multi-voice detuned chorus for string/pad thickness)
# ══════════════════════════════════════════════════════════════
def apply_ensemble(audio, voices=5, depth=0.004, rate=0.8,
                   sample_rate=44100, **kwargs):
    """
    Ensemble Chorus.
    Multi-voice chorus optimized for lush pads and strings.

    Parameters:
    voices: Number of detuned voices.
    depth:  Modulation depth.
    rate:   LFO speed.
    """
    n = len(audio)
    t = np.arange(n) / sample_rate
    wet = np.zeros_like(audio)
    idx = np.arange(n, dtype=np.float64)

    for v in range(voices):
        phase_off = v * (2.0 * np.pi / voices)
        lfo = np.sin(2.0 * np.pi * rate * t + phase_off)
        delay_s = (depth + lfo * depth * 0.3) * sample_rate

        if audio.ndim == 2:
            for ch in range(audio.shape[1]):
                read = idx - delay_s
                wet[:, ch] += np.interp(read, idx, audio[:, ch],
                                        left=0.0, right=0.0)
        else:
            read = idx - delay_s
            wet += np.interp(read, idx, audio, left=0.0, right=0.0)

    wet /= voices
    return 0.5 * audio + 0.5 * wet


# ══════════════════════════════════════════════════════════════
# DC Offset Removal
# ══════════════════════════════════════════════════════════════
def apply_dc_remove(audio, sample_rate=44100, **kwargs):
    """
    Remove DC Offset.
    High-pass filter (10Hz) to center the waveform.
    """
    sos = sig.butter(2, 10.0, 'hp', fs=sample_rate, output='sos')
    return sig.sosfilt(sos, audio, axis=0)


# ══════════════════════════════════════════════════════════════
# Pitch Shifter  (simple time-domain via resampling)
# ══════════════════════════════════════════════════════════════
def apply_pitch_shift(audio, semitones=7, mix=0.5,
                      sample_rate=44100, **kwargs):
    """
    Simple pitch shifter via resampling.
    semitones: -12..+12
    """
    ratio = 2.0 ** (semitones / 12.0)
    n = len(audio)

    if audio.ndim == 2:
        shifted = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            new_len = int(n / ratio)
            resampled = sig.resample(audio[:, ch], new_len)
            if new_len >= n:
                shifted[:, ch] = resampled[:n]
            else:
                shifted[:new_len, ch] = resampled
    else:
        new_len = int(n / ratio)
        resampled = sig.resample(audio, new_len)
        shifted = np.zeros(n)
        if new_len >= n:
            shifted = resampled[:n]
        else:
            shifted[:new_len] = resampled

    return (1.0 - mix) * audio + mix * shifted


# ══════════════════════════════════════════════════════════════
# Sidechain Pump  (simulated sidechain compression)
# ══════════════════════════════════════════════════════════════
def apply_sidechain(audio, rate=2.0, depth=0.7, shape=0.5,
                    sample_rate=44100, **kwargs):
    """
    Simulated sidechain compression pump.
    rate:  Pumps per second (BPM/60).
    depth: How much the volume ducks 0..1.
    shape: Envelope curve shape (0=linear, 1=exponential).
    """
    n = len(audio)
    t = np.arange(n) / sample_rate

    # Generate a ducking envelope
    phase = (t * rate) % 1.0  # 0..1 per pump cycle

    # Shape the release curve
    if shape > 0.5:
        env = phase ** (1.0 + shape * 3.0)
    else:
        env = phase ** (0.5 + shape)

    gain = 1.0 - depth * (1.0 - env)

    if audio.ndim == 2:
        gain = gain[:, np.newaxis]

    return audio * gain


# ══════════════════════════════════════════════════════════════
# Reverse  (full or partial buffer reversal)
# ══════════════════════════════════════════════════════════════
def apply_reverse(audio, mix=1.0, **kwargs):
    """
    Reverse the audio buffer.
    mix: 0 = dry, 1 = fully reversed.
    """
    rev = audio[::-1].copy()
    return (1.0 - mix) * audio + mix * rev


# ══════════════════════════════════════════════════════════════
# Tape Stop  (DJ-style slowdown effect)
# ══════════════════════════════════════════════════════════════
def apply_tape_stop(audio, duration_pct=0.5, sample_rate=44100, **kwargs):
    """
    Tape-stop / vinyl-brake effect.
    Gradually decelerates playback speed from normal to zero.

    duration_pct: Portion of audio where slowdown occurs (0.1..1.0).
    """
    n = len(audio)
    stop_start = int(n * (1.0 - duration_pct))
    out = np.copy(audio)

    # Before the stop region, audio plays normally
    # During stop region, we gradually slow down by resampling
    stop_len = n - stop_start
    if stop_len < 2:
        return audio

    # Build a read-position curve that decelerates
    # speed goes from 1.0 down to 0.0
    t_norm = np.linspace(0, 1, stop_len)
    speed = 1.0 - t_norm  # 1→0
    read_offsets = np.cumsum(speed)
    read_offsets = read_offsets / read_offsets[-1] * (stop_len - 1)
    read_positions = stop_start + read_offsets

    idx = np.arange(n, dtype=np.float64)
    if audio.ndim == 2:
        for ch in range(audio.shape[1]):
            out[stop_start:, ch] = np.interp(read_positions, idx,
                                              audio[:, ch],
                                              left=0.0, right=0.0)
    else:
        out[stop_start:] = np.interp(read_positions, idx, audio,
                                      left=0.0, right=0.0)

    # Fade out the tail
    fade = np.linspace(1.0, 0.0, stop_len)
    if audio.ndim == 2:
        out[stop_start:] *= fade[:, np.newaxis]
    else:
        out[stop_start:] *= fade

    return out


# ══════════════════════════════════════════════════════════════
# Vinyl Crackle  (add authentic vinyl noise layer)
# ══════════════════════════════════════════════════════════════
def apply_vinyl(audio, crackle=0.3, hiss=0.1, wow=0.15,
                sample_rate=44100, **kwargs):
    """
    Vinyl simulation: crackle pops, hiss noise, and pitch wobble (wow).
    """
    n = len(audio)
    out = np.copy(audio)

    # 1. Crackle pops – sparse random impulses
    if crackle > 0:
        pop_density = crackle * 0.001
        pops = np.random.random(n) < pop_density
        pop_signal = pops.astype(np.float64) * np.random.uniform(-0.15, 0.15, n)
        if audio.ndim == 2:
            out += pop_signal[:, np.newaxis]
        else:
            out += pop_signal

    # 2. Hiss – filtered noise
    if hiss > 0:
        noise = np.random.randn(n) * hiss * 0.05
        sos = sig.butter(3, 8000, 'lp', fs=sample_rate, output='sos')
        noise = sig.sosfilt(sos, noise)
        if audio.ndim == 2:
            out += noise[:, np.newaxis]
        else:
            out += noise

    # 3. Wow – slow pitch wobble via variable delay
    if wow > 0:
        t = np.arange(n) / sample_rate
        lfo = np.sin(2 * np.pi * 0.5 * t) * wow * 0.001 * sample_rate
        idx = np.arange(n, dtype=np.float64)
        read = idx - lfo
        if audio.ndim == 2:
            for ch in range(audio.shape[1]):
                out[:, ch] = np.interp(read, idx, out[:, ch],
                                        left=0.0, right=0.0)
        else:
            out = np.interp(read, idx, out, left=0.0, right=0.0)

    return out


# ══════════════════════════════════════════════════════════════
# Radio  (AM radio / walkie-talkie simulation)
# ══════════════════════════════════════════════════════════════
def apply_radio(audio, intensity=0.5, sample_rate=44100, **kwargs):
    """
    AM radio / walkie-talkie effect.
    Bandpass filter + distortion + noise + sample rate reduction.
    """
    x = np.copy(audio)

    # Narrow bandpass (300 Hz – 3000 Hz for telephone, wider for radio)
    low = 300 + (1.0 - intensity) * 200
    high = 3000 + (1.0 - intensity) * 2000
    sos = sig.butter(4, [low, high], 'bp', fs=sample_rate, output='sos')
    x = sig.sosfilt(sos, x, axis=0)

    # Add some crunch
    x = np.tanh(x * (1 + intensity * 5))

    # AM modulation hum (60Hz)
    n = len(x)
    t = np.arange(n) / sample_rate
    hum = 1.0 - intensity * 0.15 * (1 + np.sin(2 * np.pi * 60 * t))
    if x.ndim == 2:
        x *= hum[:, np.newaxis]
    else:
        x *= hum

    # Noise floor
    noise = np.random.randn(*x.shape) * intensity * 0.02
    x += noise

    return x


# ══════════════════════════════════════════════════════════════
# Telephone  (narrowband phone line effect)
# ══════════════════════════════════════════════════════════════
def apply_telephone(audio, quality=0.5, sample_rate=44100, **kwargs):
    """
    Telephone / narrowband communication effect.
    Tight bandpass + codec-style quantization.
    """
    x = np.copy(audio)

    # ITU-T telephone band: 300–3400 Hz
    sos = sig.butter(6, [300, 3400], 'bp', fs=sample_rate, output='sos')
    x = sig.sosfilt(sos, x, axis=0)

    # Slight compression / saturation
    x = np.tanh(x * 2.0) * 0.7

    # Quantize (8-bit quality range)
    bits = max(4, int(8 - quality * 4))
    levels = 2 ** bits
    x = np.round(x * levels) / levels

    return x


# ══════════════════════════════════════════════════════════════
# Underwater  (heavy lowpass + modulated chorus)
# ══════════════════════════════════════════════════════════════
def apply_underwater(audio, depth_amount=0.5, sample_rate=44100, **kwargs):
    """
    Underwater / submerged effect.
    Heavy lowpass with slow modulation to simulate water distortion.
    """
    x = np.copy(audio)

    # Heavy lowpass – deeper = lower cutoff
    cutoff = max(200, 2000 - depth_amount * 1800)
    sos = sig.butter(6, cutoff, 'lp', fs=sample_rate, output='sos')
    x = sig.sosfilt(sos, x, axis=0)

    # Slow chorus-like modulation
    n = len(x)
    t = np.arange(n) / sample_rate
    idx = np.arange(n, dtype=np.float64)
    lfo = np.sin(2 * np.pi * 0.3 * t) * depth_amount * 0.003 * sample_rate
    read = idx - lfo

    if x.ndim == 2:
        for ch in range(x.shape[1]):
            x[:, ch] = np.interp(read, idx, x[:, ch], left=0.0, right=0.0)
    else:
        x = np.interp(read, idx, x, left=0.0, right=0.0)

    # Slight resonance bump
    sos2 = sig.butter(2, max(100, cutoff * 0.8), 'lp', fs=sample_rate, output='sos')
    x = sig.sosfilt(sos2, x, axis=0)

    return x


# ══════════════════════════════════════════════════════════════
# Shimmer  (pitch-shifted reverb tail for ethereal atmospheres)
# ══════════════════════════════════════════════════════════════
def apply_shimmer(audio, shift_semitones=12, feedback=0.3, mix=0.4,
                  sample_rate=44100, **kwargs):
    """
    Shimmer effect – pitch-shifted reverb tail.
    Creates ethereal, angelic atmosphere found in ambient music.
    """
    n = len(audio)
    ratio = 2.0 ** (shift_semitones / 12.0)

    # Generate pitched-up version
    if audio.ndim == 2:
        shifted = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            new_len = int(n / ratio)
            if new_len < 1:
                continue
            resampled = sig.resample(audio[:, ch], new_len)
            if new_len >= n:
                shifted[:, ch] = resampled[:n]
            else:
                shifted[:new_len, ch] = resampled
    else:
        new_len = int(n / ratio)
        resampled = sig.resample(audio, new_len) if new_len > 0 else audio
        shifted = np.zeros(n)
        if new_len >= n:
            shifted = resampled[:n]
        else:
            shifted[:new_len] = resampled

    # Simple diffuse delay for shimmer tail
    delay_samples = int(0.08 * sample_rate)
    wet = np.zeros_like(shifted)
    for i in range(delay_samples, n):
        wet[i] = shifted[i] + feedback * wet[i - delay_samples]

    wet_max = np.max(np.abs(wet))
    if wet_max > 0:
        wet /= wet_max

    return (1.0 - mix) * audio + mix * wet


# ══════════════════════════════════════════════════════════════
# Glitch  (random buffer manipulation, slice-and-dice)
# ══════════════════════════════════════════════════════════════
def apply_glitch(audio, density=0.3, slice_ms=30, sample_rate=44100, **kwargs):
    """
    Glitch / buffer manipulation effect.
    Randomly reverses, repeats, or silences small slices.
    """
    n = len(audio)
    slice_samp = max(1, int(slice_ms * sample_rate / 1000))
    out = np.copy(audio)

    pos = 0
    while pos + slice_samp <= n:
        if np.random.random() < density:
            mode = np.random.choice(['reverse', 'repeat', 'silence', 'shuffle'])
            end = min(pos + slice_samp, n)
            chunk = audio[pos:end].copy()

            if mode == 'reverse':
                out[pos:end] = chunk[::-1]
            elif mode == 'repeat':
                half = len(chunk) // 2
                if half > 0:
                    out[pos:pos + half] = chunk[:half]
                    out[pos + half:end] = chunk[:half][:end - pos - half]
            elif mode == 'silence':
                out[pos:end] = 0.0
            elif mode == 'shuffle':
                # Random offset reshuffle
                offset = np.random.randint(0, max(1, n - slice_samp))
                alt = audio[offset:offset + (end - pos)]
                if len(alt) == end - pos:
                    out[pos:end] = alt

        pos += slice_samp

    return out


# ══════════════════════════════════════════════════════════════
# Haas Effect  (tiny stereo delay for width without phase issues)
# ══════════════════════════════════════════════════════════════
def apply_haas(audio, delay_ms=15, side='right', sample_rate=44100, **kwargs):
    """
    Haas effect – tiny delay on one channel to widen the stereo image.
    """
    if audio.ndim == 1:
        # Can't apply Haas to mono
        return audio

    delay_samp = int(delay_ms * sample_rate / 1000)
    out = np.copy(audio)

    ch = 1 if side == 'right' else 0
    if delay_samp > 0 and delay_samp < len(audio):
        out[delay_samp:, ch] = audio[:-delay_samp, ch]
        out[:delay_samp, ch] = 0.0

    return out


# ══════════════════════════════════════════════════════════════
# Harmonizer  (add a harmony voice at a musical interval)
# ══════════════════════════════════════════════════════════════
def apply_harmonizer(audio, interval=7, mix=0.3,
                     sample_rate=44100, **kwargs):
    """
    Add a pitched harmony voice.
    interval: Semitones offset (e.g. 7 = perfect fifth, 4 = major third).
    """
    ratio = 2.0 ** (interval / 12.0)
    n = len(audio)
    new_len = int(n / ratio)

    if audio.ndim == 2:
        harmony = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            if new_len > 0:
                resampled = sig.resample(audio[:, ch], new_len)
                if new_len >= n:
                    harmony[:, ch] = resampled[:n]
                else:
                    harmony[:new_len, ch] = resampled
    else:
        harmony = np.zeros(n)
        if new_len > 0:
            resampled = sig.resample(audio, new_len)
            if new_len >= n:
                harmony = resampled[:n]
            else:
                harmony[:new_len] = resampled

    return audio + harmony * mix


# ══════════════════════════════════════════════════════════════
# Octaver  (add octave-up and/or octave-down layers)
# ══════════════════════════════════════════════════════════════
def apply_octaver(audio, octave_up=0.0, octave_down=0.3,
                  sample_rate=44100, **kwargs):
    """
    Add octave-shifted layers.
    octave_up:   Mix level (0..1) for +12 semitones.
    octave_down: Mix level (0..1) for -12 semitones.
    """
    n = len(audio)
    out = np.copy(audio)

    if octave_up > 0:
        up_len = n // 2
        if audio.ndim == 2:
            for ch in range(audio.shape[1]):
                resampled = sig.resample(audio[:, ch], up_len)
                up = np.zeros(n)
                up[:up_len] = resampled
                out[:, ch] += up * octave_up
        else:
            resampled = sig.resample(audio, up_len)
            up = np.zeros(n)
            up[:up_len] = resampled
            out += up * octave_up

    if octave_down > 0:
        down_len = n * 2
        if audio.ndim == 2:
            for ch in range(audio.shape[1]):
                resampled = sig.resample(audio[:, ch], down_len)
                out[:, ch] += resampled[:n] * octave_down
        else:
            resampled = sig.resample(audio, down_len)
            out += resampled[:n] * octave_down

    return out


# ══════════════════════════════════════════════════════════════
# Doppler  (approaching-then-receding Doppler pitch + pan shift)
# ══════════════════════════════════════════════════════════════
def apply_doppler(audio, speed=1.0, depth=0.3,
                  sample_rate=44100, **kwargs):
    """
    Doppler effect – simulates a sound source moving past the listener.
    Pitch rises, peaks in the center, then falls.
    """
    n = len(audio)
    t = np.linspace(-1, 1, n)  # -1 = approaching, 0 = passing, +1 = receding

    # Pitch curve (higher when approaching, lower when receding)
    pitch_shift = -depth * t * speed
    # Convert to sample offsets
    offsets = np.cumsum(pitch_shift)
    idx = np.arange(n, dtype=np.float64)
    read = idx + offsets

    if audio.ndim == 2:
        out = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            out[:, ch] = np.interp(read, idx, audio[:, ch],
                                    left=0.0, right=0.0)
        # Pan: left when approaching, right when receding
        pan_l = np.clip(0.5 - t * 0.4 * depth, 0, 1)
        pan_r = np.clip(0.5 + t * 0.4 * depth, 0, 1)
        out[:, 0] *= pan_l
        out[:, 1] *= pan_r
    else:
        out = np.interp(read, idx, audio, left=0.0, right=0.0)

    return out


# ══════════════════════════════════════════════════════════════
# Crystal  (high-harmonic shimmer / glass-like resonance)
# ══════════════════════════════════════════════════════════════
def apply_crystal(audio, brightness=0.5, decay=0.3,
                  sample_rate=44100, **kwargs):
    """
    Crystal / glass resonance effect.
    Emphasizes high harmonics with a tight comb filter for sparkle.
    """
    # High-shelf boost
    sos = sig.butter(2, 5000 + brightness * 5000, 'hp', fs=sample_rate, output='sos')
    highs = sig.sosfilt(sos, audio, axis=0)

    # Tight comb filter on highs for resonance
    delay_samp = max(1, int(sample_rate / (3000 + brightness * 5000)))
    combed = np.zeros_like(highs)
    for i in range(delay_samp, len(highs)):
        combed[i] = highs[i] + decay * combed[i - delay_samp]

    mx = np.max(np.abs(combed))
    if mx > 0:
        combed /= mx

    return audio + combed * brightness * 0.3


# ══════════════════════════════════════════════════════════════
# Fade In / Fade Out
# ══════════════════════════════════════════════════════════════
def apply_fade(audio, fade_in_ms=50, fade_out_ms=200,
               sample_rate=44100, **kwargs):
    """
    Apply fade-in and fade-out envelopes.
    """
    n = len(audio)
    fi = min(n, int(fade_in_ms * sample_rate / 1000))
    fo = min(n, int(fade_out_ms * sample_rate / 1000))

    gain = np.ones(n)
    if fi > 0:
        gain[:fi] = np.linspace(0, 1, fi)
    if fo > 0:
        gain[-fo:] = np.linspace(1, 0, fo)

    if audio.ndim == 2:
        gain = gain[:, np.newaxis]

    return audio * gain


# ══════════════════════════════════════════════════════════════
# Dimension  (Roland Juno-style BBD chorus – warm stereo spread)
# ══════════════════════════════════════════════════════════════
def apply_dimension(audio, mode=2, sample_rate=44100, **kwargs):
    """
    Juno-60 inspired Dimension chorus.
    mode: 1 (subtle), 2 (warm), 3 (deep), 4 (extreme).
    Applies inverted-phase chorus to L/R for natural stereo.
    """
    configs = {
        1: {'rate': 0.5, 'depth': 0.001},
        2: {'rate': 0.8, 'depth': 0.002},
        3: {'rate': 0.6, 'depth': 0.004},
        4: {'rate': 1.2, 'depth': 0.006},
    }
    cfg = configs.get(int(mode), configs[2])
    n = len(audio)
    t = np.arange(n) / sample_rate
    idx = np.arange(n, dtype=np.float64)

    lfo = np.sin(2 * np.pi * cfg['rate'] * t) * cfg['depth'] * sample_rate

    if audio.ndim == 2:
        out = np.zeros_like(audio)
        # Left: positive LFO, Right: inverted LFO
        read_l = idx - lfo
        read_r = idx + lfo
        out[:, 0] = np.interp(read_l, idx, audio[:, 0], left=0.0, right=0.0)
        out[:, 1] = np.interp(read_r, idx, audio[:, 1], left=0.0, right=0.0)
        return 0.5 * audio + 0.5 * out
    else:
        # For mono, just do a chorus
        read = idx - lfo
        wet = np.interp(read, idx, audio, left=0.0, right=0.0)
        return 0.5 * audio + 0.5 * wet


# ══════════════════════════════════════════════════════════════
# Granular Cloud  (granular synthesis texture)
# ══════════════════════════════════════════════════════════════
def apply_granular(audio, grain_ms=40, density=0.6, spray=0.3,
                   pitch_spread=0.1, sample_rate=44100, **kwargs):
    """
    Granular cloud effect – breaks audio into micro-grains and
    scatters them with random pitch/position variation.
    Creates shimmering, textured clouds from any source.
    """
    n = len(audio)
    grain_samp = max(64, int(grain_ms * sample_rate / 1000))
    out = np.zeros_like(audio)
    num_grains = int(n / grain_samp * density * 3)

    for _ in range(num_grains):
        # Random source position
        pos = int(np.random.random() * max(1, n - grain_samp))
        # Destination offset by spray amount
        dest = pos + int((np.random.random() - 0.5) * spray * n)
        dest = max(0, min(dest, n - grain_samp))

        grain = audio[pos:pos + grain_samp].copy()

        # Pitch variation via simple resampling
        pitch_factor = 1.0 + (np.random.random() - 0.5) * pitch_spread * 2
        if abs(pitch_factor - 1.0) > 0.01:
            new_len = int(grain_samp / pitch_factor)
            if new_len > 1 and new_len < grain_samp * 4:
                if audio.ndim == 2:
                    resampled = np.zeros((new_len, audio.shape[1]))
                    for ch in range(audio.shape[1]):
                        resampled[:, ch] = np.interp(
                            np.linspace(0, grain_samp - 1, new_len),
                            np.arange(grain_samp), grain[:, ch])
                else:
                    resampled = np.interp(
                        np.linspace(0, grain_samp - 1, new_len),
                        np.arange(grain_samp), grain)
                grain = resampled

        # Hann window for smooth overlap
        g_len = len(grain)
        window = np.hanning(g_len)
        if audio.ndim == 2:
            window = window[:, np.newaxis]

        end = min(dest + g_len, n)
        actual = end - dest
        if actual > 0:
            out[dest:end] += grain[:actual] * window[:actual] * 0.3

    return audio * 0.6 + out * 0.4


# ══════════════════════════════════════════════════════════════
# Spectral Freeze  (freeze a moment in time)
# ══════════════════════════════════════════════════════════════
def apply_spectral_freeze(audio, freeze_pos=0.3, sustain=0.6,
                          mix=0.4, sample_rate=44100, **kwargs):
    """
    Freezes the spectral content at a specific time position.
    Creates sustained, evolving drone textures from any source.
    """
    n = len(audio)
    fft_size = 2048
    hop = fft_size // 4
    pos = int(freeze_pos * n)
    pos = max(0, min(pos, n - fft_size))

    # Extract the frozen frame
    if audio.ndim == 2:
        frame = audio[pos:pos + fft_size, 0]
    else:
        frame = audio[pos:pos + fft_size]

    window = np.hanning(fft_size)
    spectrum = np.fft.rfft(frame * window)
    magnitudes = np.abs(spectrum)

    # Reconstruct with random phase evolution for movement
    frozen = np.zeros(n)
    for start in range(0, n - fft_size, hop):
        phase_offset = np.random.uniform(0, 2 * np.pi, len(magnitudes))
        recon = magnitudes * np.exp(1j * phase_offset)
        chunk = np.fft.irfft(recon, n=fft_size) * window
        frozen[start:start + fft_size] += chunk

    # Normalize
    mx = np.max(np.abs(frozen))
    if mx > 0:
        frozen /= mx

    # Apply sustain envelope
    env = np.ones(n) * sustain + (1.0 - sustain) * np.exp(
        -np.arange(n) / max(1, sustain * n))

    frozen *= env

    if audio.ndim == 2:
        frozen_2d = np.column_stack([frozen, frozen])
        return (1.0 - mix) * audio + mix * frozen_2d
    return (1.0 - mix) * audio + mix * frozen


# ══════════════════════════════════════════════════════════════
# Saturation Maximizer  (loudness maximizer with warmth)
# ══════════════════════════════════════════════════════════════
def apply_maximizer(audio, ceiling=-0.3, warmth=0.5,
                    release_ms=50, sample_rate=44100, **kwargs):
    """
    Loudness maximizer with analog-style warmth.
    Brings up the average level while maintaining transients
    and adding gentle harmonic saturation.
    """
    n = len(audio)
    ceiling_lin = 10.0 ** (ceiling / 20.0)

    # Envelope follower for gain calculation
    if audio.ndim == 2:
        env_in = np.max(np.abs(audio), axis=1)
    else:
        env_in = np.abs(audio)

    alpha = np.exp(-1.0 / max(1, (release_ms / 1000) * sample_rate))
    env = np.zeros(n)
    cur = 0.0
    for i in range(n):
        cur = max(env_in[i], alpha * cur)
        env[i] = cur

    # Gain to bring peaks to ceiling
    gain = np.ones(n)
    mask = env > ceiling_lin
    gain[mask] = ceiling_lin / (env[mask] + 1e-12)

    if audio.ndim == 2:
        out = audio * gain[:, np.newaxis]
    else:
        out = audio * gain

    # Warmth (subtle saturation)
    if warmth > 0:
        out = np.tanh(out * (1.0 + warmth)) / (1.0 + warmth * 0.5)

    return out


# ══════════════════════════════════════════════════════════════
# Stereo Imager  (mid/side processing)
# ══════════════════════════════════════════════════════════════
def apply_stereo_imager(audio, width=1.5, bass_mono_freq=200,
                        sample_rate=44100, **kwargs):
    """
    Mid/Side stereo imaging processor.
    Adjusts stereo width and mono-ifies bass frequencies
    for tight low end. Width < 1 narrows, > 1 widens.
    """
    if audio.ndim != 2 or audio.shape[1] < 2:
        return audio

    n = len(audio)
    mid = (audio[:, 0] + audio[:, 1]) * 0.5
    side = (audio[:, 0] - audio[:, 1]) * 0.5

    # Width control
    side *= width

    # Mono bass (keep low frequencies in center)
    if bass_mono_freq > 0:
        sos = sig.butter(2, bass_mono_freq, 'lp', fs=sample_rate, output='sos')
        bass_mid = sig.sosfilt(sos, mid)
        bass_side = sig.sosfilt(sos, side)
        # Remove bass from side, keep only in mid
        side = side - bass_side * 0.8

    out = np.zeros_like(audio)
    out[:, 0] = mid + side
    out[:, 1] = mid - side
    return out


# ══════════════════════════════════════════════════════════════
# Multiband Compressor  (3-band dynamics)
# ══════════════════════════════════════════════════════════════
def apply_multiband_comp(audio, low_thresh=-20, mid_thresh=-18,
                         high_thresh=-15, crossover_low=200,
                         crossover_high=4000,
                         sample_rate=44100, **kwargs):
    """
    3-band multiband compressor.
    Independently compresses bass, mid, and treble for a polished,
    professional sound. Essential for mastering.
    """
    n = len(audio)

    # Split into 3 bands
    sos_lo = sig.butter(4, crossover_low, 'lp', fs=sample_rate, output='sos')
    sos_mid = sig.butter(4, [crossover_low, crossover_high], 'bp',
                         fs=sample_rate, output='sos')
    sos_hi = sig.butter(4, crossover_high, 'hp', fs=sample_rate, output='sos')

    low = sig.sosfilt(sos_lo, audio, axis=0)
    mid_band = sig.sosfilt(sos_mid, audio, axis=0)
    high = sig.sosfilt(sos_hi, audio, axis=0)

    # Compress each band
    def compress_band(band, threshold_db, ratio=4.0, att=0.005, rel=0.1):
        thresh = 10.0 ** (threshold_db / 20.0)
        if band.ndim == 2:
            env_in = np.max(np.abs(band), axis=1)
        else:
            env_in = np.abs(band)

        alpha_a = np.exp(-1.0 / max(1, att * sample_rate))
        alpha_r = np.exp(-1.0 / max(1, rel * sample_rate))
        env = np.zeros(len(band))
        c = 0.0
        for i in range(len(band)):
            if env_in[i] > c:
                c = alpha_a * c + (1.0 - alpha_a) * env_in[i]
            else:
                c = alpha_r * c + (1.0 - alpha_r) * env_in[i]
            env[i] = c

        gain = np.ones(len(band))
        mask = env > thresh
        over = 20.0 * np.log10(env[mask] / thresh + 1e-12)
        gain[mask] = 10.0 ** ((over / ratio - over) / 20.0)

        if band.ndim == 2:
            return band * gain[:, np.newaxis]
        return band * gain

    low = compress_band(low, low_thresh, ratio=3.0, att=0.01, rel=0.15)
    mid_band = compress_band(mid_band, mid_thresh, ratio=4.0, att=0.005, rel=0.1)
    high = compress_band(high, high_thresh, ratio=3.5, att=0.002, rel=0.08)

    return low + mid_band + high


# ══════════════════════════════════════════════════════════════
# Harmonic Enhancer  (adds musical harmonics)
# ══════════════════════════════════════════════════════════════
def apply_harmonic_enhance(audio, low_harmonics=0.3, high_harmonics=0.2,
                           air=0.15, sample_rate=44100, **kwargs):
    """
    Generates and adds musical harmonics to fatten and brighten sound.
    Low harmonics add warmth, high harmonics add sparkle, 'air' adds
    ultra-high sheen.
    """
    out = np.copy(audio)

    # Low harmonics (2nd + 3rd) for warmth
    if low_harmonics > 0:
        sos = sig.butter(2, 500, 'lp', fs=sample_rate, output='sos')
        lows = sig.sosfilt(sos, audio, axis=0)
        # 2nd harmonic (even = warm)
        h2 = lows * lows * np.sign(lows) * 0.5
        out = out + h2 * low_harmonics

    # High harmonics (subtle distortion of highs)
    if high_harmonics > 0:
        sos_hi = sig.butter(2, 3000, 'hp', fs=sample_rate, output='sos')
        highs = sig.sosfilt(sos_hi, audio, axis=0)
        h_sat = np.tanh(highs * 3.0) * 0.3
        out = out + h_sat * high_harmonics

    # Air band (~10kHz+)
    if air > 0:
        sos_air = sig.butter(1, min(10000, sample_rate * 0.45), 'hp',
                             fs=sample_rate, output='sos')
        air_band = sig.sosfilt(sos_air, audio, axis=0)
        out = out + air_band * air * 0.5

    return out


# ══════════════════════════════════════════════════════════════
# Granular Stretch  (time stretch without pitch change)
# ══════════════════════════════════════════════════════════════
def apply_granular_stretch(audio, rate=0.5, grain_ms=60,
                           sample_rate=44100, **kwargs):
    """
    Time stretch using granular overlap-add.
    rate < 1 = slower (stretched), rate > 1 = faster (compressed).
    Preserves pitch while changing duration.
    """
    n = len(audio)
    grain_samp = max(128, int(grain_ms * sample_rate / 1000))
    hop_in = grain_samp // 2
    hop_out = int(hop_in * rate)
    if hop_out < 1:
        hop_out = 1

    # Calculate output length
    out_len = int(n / rate) if rate > 0 else n
    out_len = max(n, out_len)  # never shorter than input for this effect

    if audio.ndim == 2:
        out = np.zeros((out_len, audio.shape[1]))
    else:
        out = np.zeros(out_len)

    window = np.hanning(grain_samp)
    if audio.ndim == 2:
        window = window[:, np.newaxis]

    read_pos = 0
    write_pos = 0
    while read_pos + grain_samp <= n and write_pos + grain_samp <= out_len:
        grain = audio[read_pos:read_pos + grain_samp] * window
        out[write_pos:write_pos + grain_samp] += grain
        read_pos += hop_in
        write_pos += hop_out

    # Return only input-length portion
    return out[:n]


# ══════════════════════════════════════════════════════════════
# Parallel Compression  (New York compression)
# ══════════════════════════════════════════════════════════════
def apply_parallel_comp(audio, threshold=-25, ratio=8.0,
                        mix=0.4, sample_rate=44100, **kwargs):
    """
    New York / parallel compression.
    Blends heavily compressed signal with dry for punchy,
    dynamic sound that retains transients.
    """
    thresh_lin = 10.0 ** (threshold / 20.0)
    n = len(audio)

    if audio.ndim == 2:
        env_in = np.max(np.abs(audio), axis=1)
    else:
        env_in = np.abs(audio)

    alpha_a = np.exp(-1.0 / max(1, 0.001 * sample_rate))
    alpha_r = np.exp(-1.0 / max(1, 0.05 * sample_rate))

    env = np.zeros(n)
    cur = 0.0
    for i in range(n):
        if env_in[i] > cur:
            cur = alpha_a * cur + (1.0 - alpha_a) * env_in[i]
        else:
            cur = alpha_r * cur + (1.0 - alpha_r) * env_in[i]
        env[i] = cur

    gain = np.ones(n)
    mask = env > thresh_lin
    over_db = 20.0 * np.log10(env[mask] / thresh_lin + 1e-12)
    gain[mask] = 10.0 ** ((over_db / ratio - over_db) / 20.0)

    if audio.ndim == 2:
        crushed = audio * gain[:, np.newaxis]
    else:
        crushed = audio * gain

    # Makeup gain on compressed signal
    mx_c = np.max(np.abs(crushed))
    mx_d = np.max(np.abs(audio))
    if mx_c > 0 and mx_d > 0:
        crushed *= mx_d / mx_c * 0.9

    return (1.0 - mix) * audio + mix * crushed


# ══════════════════════════════════════════════════════════════
# Body / Convolution Resonance  (adds acoustic body)
# ══════════════════════════════════════════════════════════════
def apply_body(audio, size=0.5, tone=0.5, mix=0.3,
               sample_rate=44100, **kwargs):
    """
    Adds acoustic body resonance – simulates a resonant chamber
    or body (like a guitar body, piano soundboard, etc.)
    Makes synths sound more physical and organic.
    """
    n = len(audio)

    # Generate a simple synthetic body impulse response
    ir_len = int(size * 0.05 * sample_rate) + 256
    ir_len = min(ir_len, n // 2)

    t_ir = np.arange(ir_len) / sample_rate
    # Multi-mode resonance
    ir = np.zeros(ir_len)
    freqs = [120, 250, 500, 1200]  # body modes
    for i, f in enumerate(freqs):
        decay = 0.02 + size * 0.03
        amp = (1.0 - i * 0.2) * (0.5 + tone * 0.5 if f > 300 else 1.0 - tone * 0.3)
        ir += amp * np.sin(2 * np.pi * f * t_ir) * np.exp(-t_ir / decay)

    ir /= np.max(np.abs(ir)) + 1e-12

    # Convolve
    if audio.ndim == 2:
        wet = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            conv = np.convolve(audio[:, ch], ir, mode='full')[:n]
            wet[:, ch] = conv
    else:
        wet = np.convolve(audio, ir, mode='full')[:n]

    mx = np.max(np.abs(wet))
    if mx > 0:
        wet /= mx

    return (1.0 - mix) * audio + mix * wet


# ══════════════════════════════════════════════════════════════
# Width Enhancer  (frequency-dependent stereo widening)
# ══════════════════════════════════════════════════════════════
def apply_width_enhance(audio, low_width=0.8, high_width=1.5,
                        crossover=800, sample_rate=44100, **kwargs):
    """
    Frequency-dependent stereo width.
    Keeps bass tight/narrow while expanding highs for a spacious mix.
    """
    if audio.ndim != 2 or audio.shape[1] < 2:
        return audio

    n = len(audio)
    mid = (audio[:, 0] + audio[:, 1]) * 0.5
    side = (audio[:, 0] - audio[:, 1]) * 0.5

    # Split side into low and high
    sos_lo = sig.butter(2, crossover, 'lp', fs=sample_rate, output='sos')
    sos_hi = sig.butter(2, crossover, 'hp', fs=sample_rate, output='sos')

    side_lo = sig.sosfilt(sos_lo, side) * low_width
    side_hi = sig.sosfilt(sos_hi, side) * high_width

    side_new = side_lo + side_hi

    out = np.zeros_like(audio)
    out[:, 0] = mid + side_new
    out[:, 1] = mid - side_new
    return out


# ══════════════════════════════════════════════════════════════
# Warmth  (analog-style warming)
# ══════════════════════════════════════════════════════════════
def apply_warmth(audio, amount=0.5, sample_rate=44100, **kwargs):
    """
    Analog warmth processor. Adds subtle even harmonics,
    gentle low-end boost, and soft high-frequency rolloff.
    Makes digital synths sound more organic and full.
    """
    # Even harmonics
    x = audio + amount * 0.03 * audio ** 2

    # Gentle saturation
    x = np.tanh(x * (1.0 + amount * 0.5)) / (1.0 + amount * 0.3)

    # Low warmth boost
    sos_lo = sig.butter(1, 150, 'lp', fs=sample_rate, output='sos')
    lows = sig.sosfilt(sos_lo, audio, axis=0)
    x = x + lows * amount * 0.1

    # Gentle HF rolloff (like analog circuits)
    hf_cut = max(8000, 16000 - amount * 6000)
    sos_hf = sig.butter(1, hf_cut, 'lp', fs=sample_rate, output='sos')
    x = sig.sosfilt(sos_hf, x, axis=0)

    return x


# ══════════════════════════════════════════════════════════════
# Spatial  (3D spatialization with early reflections)
# ══════════════════════════════════════════════════════════════
def apply_spatial(audio, room_size=0.5, position=0.5, height=0.3,
                  sample_rate=44100, **kwargs):
    """
    3D spatial positioning with early reflections.
    Places the sound in a virtual room with configurable position,
    room size, and vertical placement.
    """
    n = len(audio)
    if audio.ndim != 2:
        audio = np.column_stack([audio, audio])

    out = np.copy(audio)

    # Position = L/R pan (0 = left, 1 = right)
    pan_l = np.cos(position * np.pi / 2)
    pan_r = np.sin(position * np.pi / 2)
    out[:, 0] *= pan_l
    out[:, 1] *= pan_r

    # Early reflections (6 delay taps at different positions)
    ref_delays = [int(d * room_size * sample_rate / 1000)
                  for d in [5, 11, 17, 23, 31, 41]]
    ref_gains = [0.4, 0.3, 0.25, 0.2, 0.15, 0.1]
    # Alternate L/R for spatial spread
    ref_pans = [(0.3, 0.8), (0.7, 0.2), (0.4, 0.6),
                (0.6, 0.4), (0.2, 0.9), (0.9, 0.1)]

    for d, g, (pl, pr) in zip(ref_delays, ref_gains, ref_pans):
        if d > 0 and d < n:
            out[d:, 0] += audio[:-d, 0] * g * pl * room_size
            out[d:, 1] += audio[:-d, 1] * g * pr * room_size

    # Height simulation (subtle filtering)
    if height > 0:
        sos = sig.butter(1, max(2000, 4000 + height * 8000), 'hp',
                         fs=sample_rate, output='sos')
        h_component = sig.sosfilt(sos, audio, axis=0) * height * 0.15
        out += h_component

    return out

