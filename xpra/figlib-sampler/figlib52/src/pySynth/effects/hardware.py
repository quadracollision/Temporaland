"""
pySynth Hardware Emulations
Models of iconic analog hardware – filters, compressors, amps, reverbs, delays.
Each function aims to capture the sonic character of the original unit.
"""
import numpy as np
from scipy import signal as sig


# ══════════════════════════════════════════════════════════════
# Moog Ladder Filter  (Moog Minimoog Model D – 24 dB/oct resonant LPF)
# ══════════════════════════════════════════════════════════════
def apply_moog_ladder(audio, cutoff=1000.0, resonance=0.7,
                      drive=0.1, sample_rate=44100, **kwargs):
    """
    Moog Ladder Filter (24 dB/oct).
    Famous for warm, fat low-end and self-oscillating resonance.

    Parameters:
    cutoff:    Filter cutoff in Hz.
    resonance: Resonance amount (0.0..1.0, 1.0 = self-oscillation).
    drive:     Input saturation amount (0.0..1.0).
    """
    n = len(audio)
    # Oversampling factor (2x) to reduce aliasing near Nyquist
    fc = cutoff / sample_rate
    fc = min(fc, 0.45)

    # Feedback amount (resonance → compensation factor)
    k = 4.0 * resonance

    # State variables for 4 cascaded 1-pole sections
    if audio.ndim == 2:
        channels = audio.shape[1]
        s = np.zeros((4, channels))
    else:
        channels = 0
        s = np.zeros(4)

    out = np.zeros_like(audio)

    # Thermal voltage constant (simulates transistor mismatch)
    thermal = 1.22

    for i in range(n):
        x = audio[i]

        # Input drive (soft-clip like transistor)
        if drive > 0:
            x = np.tanh(x * (1.0 + drive * 5.0))

        # Feedback path (resonance)
        x = x - k * s[3]

        # 4 cascaded 1-pole lowpass stages with tanh nonlinearity
        # Each stage: s[j] += 2*fc * (tanh(input/thermal) - tanh(s[j]/thermal))
        for j in range(4):
            inp = x if j == 0 else s[j - 1]
            s[j] += 2.0 * fc * (np.tanh(inp / thermal) - np.tanh(s[j] / thermal))

        out[i] = s[3]

    return out


# ══════════════════════════════════════════════════════════════
# TB-303 Diode Ladder Filter  (Roland TB-303 – acid squelch)
# ══════════════════════════════════════════════════════════════
def apply_303_filter(audio, cutoff=800.0, resonance=0.8, env_mod=0.5,
                     accent=0.3, decay=0.3, sample_rate=44100, **kwargs):
    """
    TB-303 Diode Ladder Filter.
    Creates the classic acid techno squelch with built-in envelope modulation.

    Parameters:
    cutoff:    Base cutoff frequency in Hz.
    resonance: Resonance / squelch amount (0.0..1.0).
    env_mod:   Envelope modulation depth.
    accent:    Accent level (sharper envelope, higher gain).
    decay:     Filter envelope decay time in seconds.
    """
    n = len(audio)

    # Build a simple decay envelope to modulate cutoff
    env_samples = int(decay * sample_rate)
    env = np.zeros(n)
    if env_samples > 0:
        env[:min(env_samples, n)] = np.linspace(1.0, 0.0, min(env_samples, n))

    # Accent makes the envelope sharper and louder
    env = env ** (1.0 + accent * 2.0)

    # Modulated cutoff
    max_cutoff = min(sample_rate * 0.45, cutoff + env_mod * 8000)
    cutoff_curve = cutoff + env * (max_cutoff - cutoff)

    # Resonance feedback
    k = 4.0 * resonance * 0.9  # 303 doesn't quite self-oscillate

    # Process sample-by-sample with 4-pole diode ladder
    if audio.ndim == 2:
        s = np.zeros((4, audio.shape[1]))
    else:
        s = np.zeros(4)

    out = np.zeros_like(audio)

    for i in range(n):
        fc = cutoff_curve[i] / sample_rate
        fc = min(fc, 0.45)

        x = audio[i]
        x = x - k * s[3]  # feedback

        # Diode clipping (asymmetric)
        x = np.tanh(x * 1.2) * 0.9

        for j in range(4):
            inp = x if j == 0 else s[j - 1]
            s[j] += 2.0 * fc * (inp - s[j])

        out[i] = s[3]

    # Accent-driven output gain
    out *= (1.0 + accent * 1.5)
    return out


# ══════════════════════════════════════════════════════════════
# Oberheim SEM Filter  (Oberheim SEM / OB-Xa – state variable filter)
# ══════════════════════════════════════════════════════════════
def apply_sem_filter(audio, cutoff=2000.0, resonance=0.5,
                     mode='lowpass', sample_rate=44100, **kwargs):
    """
    Oberheim SEM Filter (12 dB/oct).
    State Variable Filter with continuous mode morphing (not fully implemented yet).

    Parameters:
    cutoff:    Filter cutoff in Hz.
    resonance: Resonance amount.
    mode:      Filter mode ('lowpass', 'highpass', 'bandpass', 'notch').
    """
    n = len(audio)
    fc = 2.0 * np.sin(np.pi * min(cutoff, sample_rate * 0.45) / sample_rate)
    q = 1.0 - resonance * 0.95  # damp factor

    if audio.ndim == 2:
        lp = np.zeros(audio.shape[1])
        bp = np.zeros(audio.shape[1])
    else:
        lp = 0.0
        bp = 0.0

    out = np.zeros_like(audio)

    for i in range(n):
        x = audio[i]
        hp = x - lp - q * bp
        bp = bp + fc * hp
        lp = lp + fc * bp

        # Notch = hp + lp
        if mode == 'lowpass':
            out[i] = lp
        elif mode == 'highpass':
            out[i] = hp
        elif mode == 'bandpass':
            out[i] = bp
        elif mode == 'notch':
            out[i] = hp + lp
        else:
            out[i] = lp

    return out


# ══════════════════════════════════════════════════════════════
# Korg MS-20 Filter  (sallen-key HPF + diode clipper)
# ══════════════════════════════════════════════════════════════
def apply_ms20_filter(audio, cutoff=1500.0, resonance=0.7,
                      sample_rate=44100, **kwargs):
    """
    Korg MS-20 Filter.
    Aggressive, screaming resonance using Sallen-Key topology with diode clipping.

    Parameters:
    cutoff:    Filter cutoff in Hz.
    resonance: Resonance amount (0.0..1.0).
    """
    n = len(audio)
    fc = 2.0 * np.sin(np.pi * min(cutoff, sample_rate * 0.45) / sample_rate)
    k = resonance * 3.8  # MS-20 goes into self-oscillation easily

    if audio.ndim == 2:
        s1 = np.zeros(audio.shape[1])
        s2 = np.zeros(audio.shape[1])
    else:
        s1 = 0.0
        s2 = 0.0

    out = np.zeros_like(audio)

    for i in range(n):
        x = audio[i]

        # Feedback with diode-style saturation
        fb = np.tanh(s2 * k) * 0.8
        x = x - fb

        # Two cascaded integrators
        hp = x - s1
        s1 = s1 + fc * hp
        hp2 = s1 - s2
        s2 = s2 + fc * hp2

        out[i] = s2

    return out


# ══════════════════════════════════════════════════════════════
# Roland Space Echo (RE-201)  (tape echo + spring reverb)
# ══════════════════════════════════════════════════════════════
def apply_space_echo(audio, time=0.375, feedback=0.6, wow=0.2,
                     flutter=0.15, tone=0.5, spring_mix=0.15,
                     mix=0.4, sample_rate=44100, **kwargs):
    """
    Roland RE-201 Space Echo.
    Tape delay with wow/flutter modulation and spring reverb.

    Parameters:
    time:       Delay time in seconds.
    feedback:   Feedback amount.
    wow:        Slow tape speed fluctuation intensity.
    flutter:    Fast tape irregularity intensity.
    tone:       Tape tone (0.0=dark, 1.0=bright).
    spring_mix: Built-in spring reverb amount.
    """
    n = len(audio)
    delay_samp = int(time * sample_rate)
    if delay_samp < 1 or delay_samp >= n:
        return audio

    # Tape buffer
    buf_size = delay_samp + int(0.01 * sample_rate)  # extra for modulation
    if audio.ndim == 2:
        buf = np.zeros((buf_size, audio.shape[1]))
    else:
        buf = np.zeros(buf_size)

    out = np.zeros_like(audio)
    t = np.arange(n) / sample_rate

    # Wow: slow ~0.5Hz, Flutter: fast ~6Hz
    wow_lfo = np.sin(2 * np.pi * 0.5 * t) * wow * 0.002 * sample_rate
    flutter_lfo = np.sin(2 * np.pi * 6.0 * t) * flutter * 0.0005 * sample_rate
    mod = wow_lfo + flutter_lfo

    idx_arr = np.arange(n, dtype=np.float64)

    # Simple tape echo: write input + feedback into buffer, read with modulation
    write_pos = 0
    for i in range(n):
        # Modulated read position
        read_delay = delay_samp + mod[i]
        read_pos = write_pos - int(read_delay)
        if read_pos < 0:
            read_pos += buf_size

        # Read from tape buffer (with linear interpolation)
        rp_int = int(read_pos) % buf_size
        rp_frac = read_pos - int(read_pos)
        rp_next = (rp_int + 1) % buf_size
        tape_out = buf[rp_int] * (1.0 - rp_frac) + buf[rp_next] * rp_frac

        # Tape saturation
        tape_out = np.tanh(tape_out * 1.1)

        # Write: input + feedback * tape output
        buf[write_pos] = audio[i] + feedback * tape_out

        out[i] = tape_out
        write_pos = (write_pos + 1) % buf_size

    # Tone control (simple LP/HP blend)
    if tone < 0.5:
        # Dark: lowpass
        cutoff = 800 + tone * 4000
        sos = sig.butter(2, cutoff, 'lp', fs=sample_rate, output='sos')
        out = sig.sosfilt(sos, out, axis=0)
    else:
        # Bright: just gentle HP to remove mud
        sos = sig.butter(1, 200, 'hp', fs=sample_rate, output='sos')
        out = sig.sosfilt(sos, out, axis=0)

    # Simple spring reverb (comb filter bank)
    if spring_mix > 0:
        spring = np.zeros_like(audio)
        for delay_ms in [29, 37, 43, 53]:
            d = int(delay_ms * sample_rate / 1000)
            if d < n:
                spring[d:] += out[:-d] * 0.15
        out = out + spring * spring_mix

    return (1.0 - mix) * audio + mix * out


# ══════════════════════════════════════════════════════════════
# Fairchild 670 Compressor  (tube vari-mu compressor)
# ══════════════════════════════════════════════════════════════
def apply_fairchild(audio, input_gain=0.5, threshold=-20.0,
                    time_constant=3, mix=1.0,
                    sample_rate=44100, **kwargs):
    """
    Fairchild 670 Tube Compressor.
    Vari-mu topology providing smooth, "glue" compression.

    Parameters:
    input_gain:    Input drive (0.0..1.0).
    threshold:     Threshold in dBFS.
    time_constant: Release preset (1=fastest, 6=slowest).
    """
    # Time constant lookup (seconds) – inspired by original 6-position selector
    tc_map = {1: (0.0002, 0.03), 2: (0.0002, 0.08), 3: (0.0004, 0.2),
              4: (0.001, 0.5), 5: (0.002, 1.0), 6: (0.004, 2.0)}
    attack_t, release_t = tc_map.get(int(time_constant), tc_map[3])

    thresh_lin = 10.0 ** (threshold / 20.0)
    n = len(audio)

    # Tube input stage saturation
    x = audio * (1.0 + input_gain * 4.0)
    x = np.tanh(x * 1.2) / 1.2  # soft tube warmth

    # Envelope follower
    if x.ndim == 2:
        env_input = np.max(np.abs(x), axis=1)
    else:
        env_input = np.abs(x)

    alpha_a = np.exp(-1.0 / max(1, attack_t * sample_rate))
    alpha_r = np.exp(-1.0 / max(1, release_t * sample_rate))

    env = np.zeros(n)
    cur = 0.0
    for i in range(n):
        inp = env_input[i]
        if inp > cur:
            cur = alpha_a * cur + (1.0 - alpha_a) * inp
        else:
            cur = alpha_r * cur + (1.0 - alpha_r) * inp
        env[i] = cur

    # Vari-mu gain reduction (smoother than VCA)
    # GR = (env/thresh)^0.5 – softer knee than standard compressor
    gain = np.ones(n)
    mask = env > thresh_lin
    gain[mask] = (thresh_lin / env[mask]) ** 0.5

    # Tube output stage – slight even harmonic coloring
    if x.ndim == 2:
        out = x * gain[:, np.newaxis]
    else:
        out = x * gain

    # Even harmonic warmth
    out = out + 0.02 * out ** 2 - 0.005 * out ** 3

    return (1.0 - mix) * audio + mix * out


# ══════════════════════════════════════════════════════════════
# SSL Bus Compressor  (SSL 4000 G / E Series)
# ══════════════════════════════════════════════════════════════
def apply_ssl_comp(audio, threshold=-15.0, ratio=4.0,
                   attack_ms=10.0, release_ms=100.0,
                   makeup_db=0.0, sample_rate=44100, **kwargs):
    """
    SSL 4000 G-Series Bus Compressor.
    VCA compressor known for "glueing" mixes together.

    Parameters:
    threshold:  Threshold in dBFS.
    ratio:      Compression ratio.
    attack_ms:  Attack time in milliseconds.
    release_ms: Release time in milliseconds.
    """
    thresh_lin = 10.0 ** (threshold / 20.0)
    n = len(audio)

    if audio.ndim == 2:
        env_input = np.max(np.abs(audio), axis=1)
    else:
        env_input = np.abs(audio)

    alpha_a = np.exp(-1.0 / max(1, (attack_ms / 1000) * sample_rate))
    alpha_r = np.exp(-1.0 / max(1, (release_ms / 1000) * sample_rate))

    env = np.zeros(n)
    cur = 0.0
    for i in range(n):
        inp = env_input[i]
        if inp > cur:
            cur = alpha_a * cur + (1.0 - alpha_a) * inp
        else:
            cur = alpha_r * cur + (1.0 - alpha_r) * inp
        env[i] = cur

    # Hard-knee compression (SSL-style)
    gain = np.ones(n)
    mask = env > thresh_lin
    over_db = 20.0 * np.log10(env[mask] / thresh_lin + 1e-12)
    reduced_db = over_db / ratio
    gain[mask] = 10.0 ** ((reduced_db - over_db) / 20.0)

    # Makeup gain
    makeup_lin = 10.0 ** (makeup_db / 20.0)
    gain *= makeup_lin

    if audio.ndim == 2:
        return audio * gain[:, np.newaxis]
    return audio * gain


# ══════════════════════════════════════════════════════════════
# Neve 1073 Preamp  (transformer coloration + harmonic saturation)
# ══════════════════════════════════════════════════════════════
def apply_neve_preamp(audio, gain=0.5, warmth=0.5,
                      sample_rate=44100, **kwargs):
    """
    Neve 1073 Preamp.
    Adds transformer saturation and harmonic warmth.

    Parameters:
    gain:   Input drive / saturation amount.
    warmth: Low-end transformer coloration magnitude.
    """
    x = audio * (1.0 + gain * 3.0)

    # Transformer saturation – asymmetric (creates even harmonics)
    x = np.tanh(x * 1.3) * 0.85 + 0.03 * x ** 2

    # Transformer low-end bump at ~60 Hz
    if warmth > 0:
        sos = sig.butter(2, 80, 'lp', fs=sample_rate, output='sos')
        lows = sig.sosfilt(sos, audio, axis=0)
        x = x + lows * warmth * 0.15

    # Slight high-end silk (gentle HF lift)
    sos_hf = sig.butter(1, 8000, 'hp', fs=sample_rate, output='sos')
    highs = sig.sosfilt(sos_hf, x, axis=0)
    x = x + highs * 0.05

    return x


# ══════════════════════════════════════════════════════════════
# EMT 140 Plate Reverb
# ══════════════════════════════════════════════════════════════
def apply_emt_plate(audio, decay=2.5, damping=0.5, mix=0.3,
                    pre_delay_ms=20, sample_rate=44100, **kwargs):
    """
    EMT 140 Plate Reverb.
    Dense, smooth metallic reverb.

    Parameters:
    decay:        Reverb time (seconds).
    damping:      High-frequency damping (0.0=bright, 1.0=dark).
    pre_delay_ms: Pre-delay in milliseconds.
    """
    n = len(audio)

    # Pre-delay
    pd_samp = int(pre_delay_ms * sample_rate / 1000)
    if pd_samp > 0 and pd_samp < n:
        delayed = np.zeros_like(audio)
        delayed[pd_samp:] = audio[:-pd_samp]
    else:
        delayed = audio

    # All-pass diffuser network (4 stages, different prime delays)
    diffused = np.copy(delayed)
    ap_delays = [113, 199, 307, 421]
    ap_gain = 0.6

    for d in ap_delays:
        if d >= n:
            continue
        temp = np.zeros_like(diffused)
        for i in range(d, n):
            temp[i] = -ap_gain * diffused[i] + diffused[i - d] + ap_gain * temp[i - d]
        diffused = temp

    # Feedback delay network (4 delays for density)
    feedback_coeff = min(0.95, 0.3 + decay * 0.15)
    fb_delays = [1427, 1781, 2099, 2467]

    wet = np.zeros_like(audio)
    for fd in fb_delays:
        if fd >= n:
            continue
        line = np.zeros_like(diffused)
        for i in range(fd, n):
            line[i] = diffused[i] + feedback_coeff * line[i - fd]
        wet += line * 0.25

    # Damping (lowpass on wet signal)
    if damping > 0:
        cutoff = max(1000, 12000 - damping * 10000)
        sos = sig.butter(2, cutoff, 'lp', fs=sample_rate, output='sos')
        wet = sig.sosfilt(sos, wet, axis=0)

    # Normalize
    mx = np.max(np.abs(wet))
    if mx > 0:
        wet /= mx

    return (1.0 - mix) * audio + mix * wet


# ══════════════════════════════════════════════════════════════
# Fender Spring Reverb  (tank-style spring reverb)
# ══════════════════════════════════════════════════════════════
def apply_spring_reverb(audio, decay=1.5, tone=0.5, mix=0.25,
                        drip=0.3, sample_rate=44100, **kwargs):
    """
    Fender Spring Reverb.
    Characteristic "drip" and "boing" of a guitar amp reverb tank.

    Parameters:
    decay: Reverb time.
    tone:  Tone control (0.0=dark, 1.0=bright).
    drip:  "Splash" intensity of the spring.
    """
    n = len(audio)

    # Spring has ~3 modes of transmission, modeled as staggered delays
    spring_delays = [
        int(0.030 * sample_rate),  # fast transverse
        int(0.042 * sample_rate),  # medium
        int(0.067 * sample_rate),  # slow longitudinal
    ]

    fb = min(0.85, 0.4 + decay * 0.12)
    wet = np.zeros_like(audio)

    for sd in spring_delays:
        if sd >= n:
            continue
        line = np.zeros_like(audio)
        for i in range(sd, n):
            # Slight pitch wobble (spring vibration)
            line[i] = audio[i] + fb * np.tanh(line[i - sd] * 1.1)
        wet += line / len(spring_delays)

    # Spring drip: resonant bandpass at ~2-4 kHz
    if drip > 0:
        sos_drip = sig.butter(3, [2000, 4500], 'bp', fs=sample_rate, output='sos')
        drip_sig = sig.sosfilt(sos_drip, wet, axis=0) * drip
        wet = wet + drip_sig

    # Tone control
    if tone < 0.5:
        sos_tone = sig.butter(2, max(800, 1000 + tone * 6000), 'lp',
                              fs=sample_rate, output='sos')
        wet = sig.sosfilt(sos_tone, wet, axis=0)
    else:
        sos_tone = sig.butter(1, 300, 'hp', fs=sample_rate, output='sos')
        wet = sig.sosfilt(sos_tone, wet, axis=0)

    mx = np.max(np.abs(wet))
    if mx > 0:
        wet /= mx

    return (1.0 - mix) * audio + mix * wet


# ══════════════════════════════════════════════════════════════
# Marshall JCM800  (British tube amp simulation)
# ══════════════════════════════════════════════════════════════
def apply_marshall_amp(audio, gain=0.6, tone=0.5, presence=0.5,
                       cabinet=True, sample_rate=44100, **kwargs):
    """
    Marshall JCM800 Tube Amp.
    High-gain British amplifier emulation with tone stack and cabinet.

    Parameters:
    gain:     Preamp drive (distortion amount).
    tone:     Tone stack balance (0.0=warm/dark, 1.0=bright/biting).
    presence: High-frequency power amp lift.
    cabinet:  Enable/Disable 4x12 cabinet simulation (True/False).
    """
    x = audio * (1.0 + gain * 8.0)

    # Stage 1: first tube gain stage
    x = np.tanh(x * 1.5)

    # Stage 2: second tube (more break-up at higher gain)
    if gain > 0.3:
        x = np.tanh(x * (1.0 + gain * 2.0))

    # Stage 3: power tube (subtle compression + even harmonics)
    x = x + 0.1 * x ** 2  # even harmonics
    x = np.tanh(x)

    # Tone stack (passive mid-scoop EQ)
    # Low cut
    sos_lo = sig.butter(2, max(100, 80 + (1 - tone) * 300), 'hp',
                        fs=sample_rate, output='sos')
    x = sig.sosfilt(sos_lo, x, axis=0)

    # Mid scoop (gentle notch around 400-800 Hz)
    w0 = 2.0 * np.pi * 600 / sample_rate
    Q = 1.5
    alpha = np.sin(w0) / (2.0 * Q)
    cos_w0 = np.cos(w0)
    scoop_db = -3.0 * (1.0 - tone)
    A = 10.0 ** (scoop_db / 40.0)
    b_eq = [1 + alpha * A, -2 * cos_w0, 1 - alpha * A]
    a_eq = [1 + alpha / A, -2 * cos_w0, 1 - alpha / A]
    x = sig.lfilter(b_eq, a_eq, x, axis=0)

    # Presence
    if presence > 0:
        sos_pres = sig.butter(1, max(2000, 3000 + presence * 3000), 'hp',
                              fs=sample_rate, output='sos')
        highs = sig.sosfilt(sos_pres, x, axis=0)
        x = x + highs * presence * 0.2

    # Cabinet simulation (lowpass + resonance bump)
    if cabinet:
        # 4x12 cab: ~75 Hz resonance, ~5 kHz rolloff
        sos_cab = sig.butter(4, 5000, 'lp', fs=sample_rate, output='sos')
        x = sig.sosfilt(sos_cab, x, axis=0)

        # Resonance bump at ~120 Hz
        w0_cab = 2.0 * np.pi * 120 / sample_rate
        alpha_cab = np.sin(w0_cab) / (2.0 * 2.0)
        cos_cab = np.cos(w0_cab)
        A_cab = 10.0 ** (3.0 / 40.0)
        b_cab = [1 + alpha_cab * A_cab, -2 * cos_cab, 1 - alpha_cab * A_cab]
        a_cab = [1 + alpha_cab / A_cab, -2 * cos_cab, 1 - alpha_cab / A_cab]
        x = sig.lfilter(b_cab, a_cab, x, axis=0)

    mx = np.max(np.abs(x))
    if mx > 0:
        x /= mx
    return x


# ══════════════════════════════════════════════════════════════
# Boss CE-1 Chorus Ensemble  (the original chorus pedal)
# ══════════════════════════════════════════════════════════════
def apply_ce1_chorus(audio, rate=0.5, intensity=0.5,
                     sample_rate=44100, **kwargs):
    """
    Boss CE-1 Chorus Ensemble.
    The original analog BBD chorus pedal.

    Parameters:
    rate:      LFO speed suitable for BBD modulation.
    intensity: Chorus depth / mix.
    """
    n = len(audio)
    t = np.arange(n) / sample_rate
    idx = np.arange(n, dtype=np.float64)

    # CE-1 uses a triangular LFO (not sine)
    lfo_phase = (rate * t) % 1.0
    lfo = 2.0 * np.abs(2.0 * lfo_phase - 1.0) - 1.0

    # BBD delay range ~5ms ± depth
    base_delay = 0.005 * sample_rate
    mod_depth = intensity * 0.003 * sample_rate
    delay = base_delay + lfo * mod_depth

    # BBD noise (subtle clock noise)
    bbd_noise = np.random.randn(n) * 0.003 * intensity

    wet = np.zeros_like(audio)
    read = idx - delay

    if audio.ndim == 2:
        for ch in range(audio.shape[1]):
            wet[:, ch] = np.interp(read, idx, audio[:, ch],
                                    left=0.0, right=0.0)
            wet[:, ch] += bbd_noise
    else:
        wet = np.interp(read, idx, audio, left=0.0, right=0.0)
        wet += bbd_noise

    # BBD lowpass (clock filter rolloff ~10kHz)
    sos = sig.butter(2, 10000, 'lp', fs=sample_rate, output='sos')
    wet = sig.sosfilt(sos, wet, axis=0)

    return 0.5 * audio + 0.5 * wet


# ══════════════════════════════════════════════════════════════
# EHX Small Stone Phaser
# ══════════════════════════════════════════════════════════════
def apply_small_stone(audio, rate=0.4, depth=0.7, feedback=0.6,
                      color=False, sample_rate=44100, **kwargs):
    """
    Electro-Harmonix Small Stone Phaser.
    4-stage OTA-based phaser.

    Parameters:
    rate:     LFO Sweep speed.
    depth:    Sweep range depth.
    feedback: Resonance / Feedback amount.
    color:    Color switch (adds more resonance/stages).
    """
    n = len(audio)
    t = np.arange(n) / sample_rate

    # Stages: 4 for normal, 6 for Color mode
    num_stages = 6 if color else 4

    # LFO → frequency sweep range
    lfo = (1.0 + np.sin(2 * np.pi * rate * t)) * 0.5  # 0..1
    min_freq = 200
    max_freq = 200 + depth * 6000
    sweep_freq = min_freq + lfo * (max_freq - min_freq)

    out = np.copy(audio).astype(np.float64)

    # All-pass chain (cascaded first-order all-pass filters)
    if audio.ndim == 2:
        ap_state = np.zeros((num_stages, audio.shape[1]))
    else:
        ap_state = np.zeros(num_stages)

    processed = np.zeros_like(audio, dtype=np.float64)
    fb_signal = np.zeros_like(audio[0], dtype=np.float64) if audio.ndim == 2 else 0.0

    for i in range(n):
        x = audio[i] + feedback * fb_signal

        # Compute all-pass coefficient from sweep frequency
        w = 2.0 * np.pi * sweep_freq[i] / sample_rate
        coeff = (1.0 - np.tan(w / 2)) / (1.0 + np.tan(w / 2))

        # Cascade all-pass stages
        for s in range(num_stages):
            inp = x if s == 0 else ap_state[s - 1]
            ap_out = coeff * inp + ap_state[s] - coeff * ap_state[s]
            ap_state[s] = inp
            x = ap_out

        fb_signal = x
        processed[i] = x

    return 0.5 * audio + 0.5 * processed


# ══════════════════════════════════════════════════════════════
# Lexicon 224 Digital Reverb  (early digital)
# ══════════════════════════════════════════════════════════════
def apply_lexicon_224(audio, size=0.7, decay=3.0, damping=0.4,
                      pre_delay_ms=15, mix=0.3,
                      sample_rate=44100, **kwargs):
    """
    Lexicon 224 Digital Reverb.
    Vintage digital reverb with modulated tails.

    Parameters:
    size:    Room size multiplier.
    decay:   Reverb tail length (seconds).
    damping: High-frequency damping.
    """
    n = len(audio)

    # Pre-delay
    pd = int(pre_delay_ms * sample_rate / 1000)
    if pd > 0 and pd < n:
        src = np.zeros_like(audio)
        src[pd:] = audio[:-pd]
    else:
        src = audio

    # Modulated all-pass diffusers
    t = np.arange(n) / sample_rate
    mod = np.sin(2 * np.pi * 0.7 * t) * 0.001 * sample_rate

    # Diffuser cascade
    diffused = np.copy(src)
    diff_delays = [int(d * size) for d in [142, 236, 379, 503]]
    for d in diff_delays:
        if d < 1 or d >= n:
            continue
        temp = np.zeros_like(diffused)
        g = 0.55
        for i in range(d, n):
            temp[i] = -g * diffused[i] + diffused[i - d] + g * temp[i - d]
        diffused = temp

    # FDN with modulated delays
    fb = min(0.92, 0.25 + decay * 0.12)
    fdn_delays = [int(d * size) for d in [1557, 1933, 2311, 2731]]

    wet = np.zeros_like(audio)
    for j, fd in enumerate(fdn_delays):
        if fd < 1 or fd >= n:
            continue
        line = np.zeros_like(diffused)
        mod_offset = int(3 * np.sin(2 * np.pi * (0.3 + j * 0.1) * 0))
        for i in range(fd, n):
            rd = fd + int(mod[i] * 0.15)
            rd = max(1, min(rd, i))
            line[i] = diffused[i] + fb * line[i - rd]
        wet += line * 0.25

    # Damping
    if damping > 0:
        fc = max(2000, 14000 - damping * 12000)
        sos = sig.butter(2, fc, 'lp', fs=sample_rate, output='sos')
        wet = sig.sosfilt(sos, wet, axis=0)

    mx = np.max(np.abs(wet))
    if mx > 0:
        wet /= mx

    return (1.0 - mix) * audio + mix * wet


# ══════════════════════════════════════════════════════════════
# DBX 160 VCA Compressor  (punchy drum compressor)
# ══════════════════════════════════════════════════════════════
def apply_dbx160(audio, threshold=-15.0, ratio=6.0,
                 sample_rate=44100, **kwargs):
    """
    DBX 160 VCA compressor emulation.
    Hard-knee, fast, punchy. The classic drum bus compressor.
    """
    thresh_lin = 10.0 ** (threshold / 20.0)
    n = len(audio)

    if audio.ndim == 2:
        env_input = np.max(np.abs(audio), axis=1)
    else:
        env_input = np.abs(audio)

    # VCA detector – very fast attack, medium release
    alpha_a = np.exp(-1.0 / max(1, 0.0001 * sample_rate))
    alpha_r = np.exp(-1.0 / max(1, 0.05 * sample_rate))

    env = np.zeros(n)
    cur = 0.0
    for i in range(n):
        inp = env_input[i]
        if inp > cur:
            cur = alpha_a * cur + (1.0 - alpha_a) * inp
        else:
            cur = alpha_r * cur + (1.0 - alpha_r) * inp
        env[i] = cur

    # Hard-knee compression
    gain = np.ones(n)
    mask = env > thresh_lin
    over = 20.0 * np.log10(env[mask] / thresh_lin + 1e-12)
    reduced = over / ratio
    gain[mask] = 10.0 ** ((reduced - over) / 20.0)

    # Auto-makeup
    gain *= 10.0 ** (threshold * (1.0 - 1.0 / ratio) / 40.0)

    if audio.ndim == 2:
        return audio * gain[:, np.newaxis]
    return audio * gain


# ══════════════════════════════════════════════════════════════
# Prophet-5 CEM3320 Filter  (Curtis Electromusic VCF)
# ══════════════════════════════════════════════════════════════
def apply_prophet_filter(audio, cutoff=2000.0, resonance=0.6,
                         keyboard_track=0.5,
                         sample_rate=44100, **kwargs):
    """
    Sequential Circuits Prophet-5 Rev 3 filter emulation.
    CEM3320 4-pole OTA lowpass. Smooth, warm, slightly rounded.

    cutoff:         Hz.
    resonance:      0..1.
    keyboard_track: How much cutoff follows pitch (not used in offline mode).
    """
    n = len(audio)
    fc = min(cutoff, sample_rate * 0.45)

    # CEM3320: 4-pole with internal soft limiting
    k = resonance * 3.7

    if audio.ndim == 2:
        s = np.zeros((4, audio.shape[1]))
    else:
        s = np.zeros(4)

    out = np.zeros_like(audio)
    g = 2.0 * np.sin(np.pi * fc / sample_rate)

    for i in range(n):
        x = audio[i]
        x = x - k * np.tanh(s[3])  # feedback with soft limit

        for j in range(4):
            inp = x if j == 0 else s[j - 1]
            # OTA integrator with slight nonlinearity
            s[j] = s[j] + g * (np.tanh(inp) - np.tanh(s[j]))

        out[i] = s[3]

    return out


# ══════════════════════════════════════════════════════════════
# Roland Juno-6 HPF  (the sweepable Juno highpass)
# ══════════════════════════════════════════════════════════════
def apply_juno_hpf(audio, cutoff=300.0, resonance=0.3,
                   sample_rate=44100, **kwargs):
    """
    Roland Juno-6/60 style highpass filter.
    2-pole SVF HPF with soft resonance – the classic Juno filter sweep.
    """
    n = len(audio)
    fc = 2.0 * np.sin(np.pi * min(cutoff, sample_rate * 0.45) / sample_rate)
    q = 1.0 - resonance * 0.9

    if audio.ndim == 2:
        lp = np.zeros(audio.shape[1])
        bp = np.zeros(audio.shape[1])
    else:
        lp = 0.0
        bp = 0.0

    out = np.zeros_like(audio)
    for i in range(n):
        hp = audio[i] - lp - q * bp
        bp = bp + fc * hp
        lp = lp + fc * bp
        out[i] = hp

    return out


# ══════════════════════════════════════════════════════════════
# ARP 2600 Ring Modulator  (analog ring mod with diode characteristics)
# ══════════════════════════════════════════════════════════════
def apply_arp_ring_mod(audio, freq=300.0, depth=0.8, diode_curve=0.3,
                       sample_rate=44100, **kwargs):
    """
    ARP 2600 ring modulator.
    Analog-style with diode nonlinearity for that slightly imperfect,
    thick modulation character.

    freq:       Carrier frequency (Hz).
    depth:      Modulation depth 0..1.
    diode_curve: Amount of diode knee nonlinearity.
    """
    n = len(audio)
    t = np.arange(n) / sample_rate

    # Carrier with slight waveshaping (diode characteristics)
    carrier = np.sin(2 * np.pi * freq * t)
    if diode_curve > 0:
        carrier = np.sign(carrier) * np.abs(carrier) ** (1.0 - diode_curve * 0.5)

    if audio.ndim == 2:
        carrier = carrier[:, np.newaxis]

    mod = audio * carrier * depth + audio * (1.0 - depth)
    return mod


# ══════════════════════════════════════════════════════════════
# Eventide H3000 Harmonizer  (micro pitch shift for stereo thickening)
# ══════════════════════════════════════════════════════════════
def apply_h3000(audio, detune_cents=12, delay_ms=15, feedback=0.1,
                mix=0.4, sample_rate=44100, **kwargs):
    """
    Eventide H3000 Ultra-Harmonizer micro-pitch effect.
    Tiny opposing pitch shifts + delay for huge stereo width
    and vocal/guitar thickening.

    detune_cents: Pitch shift in cents (±).
    delay_ms:     Pre-delay before shifted signal.
    """
    n = len(audio)
    ratio_up = 2.0 ** (detune_cents / 1200.0)
    ratio_down = 2.0 ** (-detune_cents / 1200.0)

    delay_samp = int(delay_ms * sample_rate / 1000)

    if audio.ndim == 2:
        out = np.copy(audio)
        for ch_idx, ratio in enumerate([ratio_up, ratio_down]):
            new_len = int(n / ratio)
            if new_len < 1:
                continue
            ch = ch_idx % audio.shape[1]
            resampled = sig.resample(audio[:, ch], new_len)
            shifted = np.zeros(n)
            if new_len >= n:
                shifted = resampled[:n]
            else:
                shifted[:new_len] = resampled
            # Apply delay
            if delay_samp > 0 and delay_samp < n:
                delayed = np.zeros(n)
                delayed[delay_samp:] = shifted[:-delay_samp]
                shifted = delayed
            out[:, ch] = (1.0 - mix) * audio[:, ch] + mix * shifted
    else:
        # Mono: just do up-shift
        new_len = int(n / ratio_up)
        shifted = np.zeros(n)
        if new_len > 0:
            resampled = sig.resample(audio, new_len)
            if new_len >= n:
                shifted = resampled[:n]
            else:
                shifted[:new_len] = resampled
        out = (1.0 - mix) * audio + mix * shifted

    return out


# ══════════════════════════════════════════════════════════════
# Vox AC30 Top Boost  (Class A amp with chimey top end)
# ══════════════════════════════════════════════════════════════
def apply_vox_ac30(audio, gain=0.5, treble=0.6, cut=0.4,
                   sample_rate=44100, **kwargs):
    """
    Vox AC30 Top Boost emulation.
    Class A topology: warm, chimey, slightly compressed character.
    Great for jangly cleans and crunchy breakup.
    """
    x = audio * (1.0 + gain * 5.0)

    # Class A: asymmetric clipping (bottom clips harder)
    pos = np.maximum(x, 0)
    neg = np.minimum(x, 0)
    x = np.tanh(pos * 1.2) + np.tanh(neg * 1.8) * 0.8

    # Top Boost EQ – characteristic high-mid presence
    w0 = 2.0 * np.pi * 2500 / sample_rate
    alpha = np.sin(w0) / (2.0 * 1.5)
    cos_w0 = np.cos(w0)
    A = 10.0 ** ((treble * 6.0) / 40.0)
    b = [1 + alpha * A, -2 * cos_w0, 1 - alpha * A]
    a = [1 + alpha / A, -2 * cos_w0, 1 - alpha / A]
    x = sig.lfilter(b, a, x, axis=0)

    # Cut control (lowpass roll-off)
    if cut > 0:
        fc = max(2000, 12000 - cut * 8000)
        sos = sig.butter(1, fc, 'lp', fs=sample_rate, output='sos')
        x = sig.sosfilt(sos, x, axis=0)

    # Cabinet (smaller open-back cab, brighter than Marshall)
    sos_cab = sig.butter(3, 7000, 'lp', fs=sample_rate, output='sos')
    x = sig.sosfilt(sos_cab, x, axis=0)

    mx = np.max(np.abs(x))
    if mx > 0:
        x /= mx
    return x


# ══════════════════════════════════════════════════════════════
# Fender Twin Reverb  (clean amp + spring reverb)
# ══════════════════════════════════════════════════════════════
def apply_fender_twin(audio, volume=0.4, treble=0.6, bass=0.5,
                      reverb_mix=0.3, sample_rate=44100, **kwargs):
    """
    Fender Twin Reverb clean amp emulation.
    Famous for pristine headroom, scooped mids, and lush spring reverb.
    """
    x = audio * (1.0 + volume * 3.0)

    # Fender clean: very subtle soft clip at high levels
    x = np.tanh(x * 0.8) / 0.8

    # Tone stack (Fender: bass-cut → treble interaction)
    if bass > 0:
        sos_bass = sig.butter(1, max(80, 100 + bass * 200), 'lp',
                              fs=sample_rate, output='sos')
        bass_sig = sig.sosfilt(sos_bass, x, axis=0)
        x = x + bass_sig * bass * 0.3

    if treble > 0:
        sos_treble = sig.butter(1, max(2000, 3000 + treble * 3000), 'hp',
                                fs=sample_rate, output='sos')
        treble_sig = sig.sosfilt(sos_treble, x, axis=0)
        x = x + treble_sig * treble * 0.15

    # Built-in spring reverb
    if reverb_mix > 0:
        n = len(x)
        wet = np.zeros_like(x)
        for d_ms in [33, 41, 57]:
            d = int(d_ms * sample_rate / 1000)
            if d < n:
                line = np.zeros_like(x)
                fb = 0.55
                for i in range(d, n):
                    line[i] = x[i] + fb * np.tanh(line[i - d] * 1.05)
                wet += line / 3.0
        wmx = np.max(np.abs(wet))
        if wmx > 0:
            wet /= wmx
        x = (1.0 - reverb_mix) * x + reverb_mix * wet

    mx = np.max(np.abs(x))
    if mx > 0:
        x /= mx
    return x


# ══════════════════════════════════════════════════════════════
# Roland RE-301 Chorus Echo  (chorus mode of the Space Echo successor)
# ══════════════════════════════════════════════════════════════
def apply_re301_chorus(audio, rate=0.6, depth=0.5, tone=0.5,
                       sample_rate=44100, **kwargs):
    """
    Roland RE-301 Chorus Echo – chorus mode.
    Triple-tap BBD chorus with darker, grainier character than
    modern chorus effects. Beautiful for pads and keys.
    """
    n = len(audio)
    t = np.arange(n) / sample_rate
    idx = np.arange(n, dtype=np.float64)

    # Three BBD taps at staggered phases
    wet = np.zeros_like(audio)
    for tap in range(3):
        phase = tap * 2.0 * np.pi / 3.0
        lfo = np.sin(2 * np.pi * rate * t + phase)
        delay = (0.006 + lfo * depth * 0.003) * sample_rate

        read = idx - delay
        if audio.ndim == 2:
            for ch in range(audio.shape[1]):
                wet[:, ch] += np.interp(read, idx, audio[:, ch],
                                         left=0.0, right=0.0)
        else:
            wet += np.interp(read, idx, audio, left=0.0, right=0.0)

    wet /= 3.0

    # BBD rolloff + subtle noise
    fc_tone = max(3000, 5000 + tone * 7000)
    sos = sig.butter(2, fc_tone, 'lp', fs=sample_rate, output='sos')
    wet = sig.sosfilt(sos, wet, axis=0)
    wet += np.random.randn(*wet.shape) * 0.002

    return 0.5 * audio + 0.5 * wet


# ══════════════════════════════════════════════════════════════
# Studer A800 Tape Machine  (2-inch multitrack tape)
# ══════════════════════════════════════════════════════════════
def apply_studer_tape(audio, input_level=0.5, speed=1,
                      bias=0.5, sample_rate=44100, **kwargs):
    """
    Studer A800 2-inch tape machine emulation.
    Warm compression, subtle HF rolloff, head bump, and wow/flutter.

    input_level: 0..1 (hotter = more saturation).
    speed:       0 = 7.5 ips (warmer), 1 = 15 ips (standard), 2 = 30 ips (open).
    bias:        Tape bias adjustment (affects HF response).
    """
    x = np.copy(audio)
    n = len(x)

    # Tape saturation (level-dependent)
    drive = 1.0 + input_level * 3.0
    x = np.tanh(x * drive) / np.tanh(drive)

    # Head bump (low-frequency resonance)
    bump_freq = [40, 60, 100][min(speed, 2)]
    w0 = 2.0 * np.pi * bump_freq / sample_rate
    alpha = np.sin(w0) / (2.0 * 3.0)
    cos_w0 = np.cos(w0)
    A = 10.0 ** (3.0 / 40.0)
    b = [1 + alpha * A, -2 * cos_w0, 1 - alpha * A]
    a = [1 + alpha / A, -2 * cos_w0, 1 - alpha / A]
    x = sig.lfilter(b, a, x, axis=0)

    # HF rolloff (tape speed dependent)
    hf_cutoff = [10000, 14000, 18000][min(speed, 2)]
    hf_cutoff = hf_cutoff - (1.0 - bias) * 3000
    hf_cutoff = max(4000, hf_cutoff)
    sos_hf = sig.butter(2, hf_cutoff, 'lp', fs=sample_rate, output='sos')
    x = sig.sosfilt(sos_hf, x, axis=0)

    # Wow & flutter
    t = np.arange(n) / sample_rate
    wow = np.sin(2 * np.pi * 0.4 * t) * 0.001 * sample_rate
    flutter = np.sin(2 * np.pi * 7.5 * t) * 0.0003 * sample_rate
    mod = wow + flutter
    idx = np.arange(n, dtype=np.float64)
    read = idx - mod

    if x.ndim == 2:
        for ch in range(x.shape[1]):
            x[:, ch] = np.interp(read, idx, x[:, ch], left=0.0, right=0.0)
    else:
        x = np.interp(read, idx, x, left=0.0, right=0.0)

    # Subtle hiss
    x += np.random.randn(*x.shape) * 0.001

    return x


# ══════════════════════════════════════════════════════════════
# Teletronix LA-2A  (optical compressor / leveling amplifier)
# ══════════════════════════════════════════════════════════════
def apply_la2a(audio, peak_reduction=0.5, mode='compress',
               sample_rate=44100, **kwargs):
    """
    Teletronix LA-2A optical leveling amplifier.
    Program-dependent attack/release via optical cell (T4 opto).
    Silky smooth compression. Legendary on vocals and bass.

    peak_reduction: 0..1 (amount of gain reduction).
    mode:           'compress' (gentler) or 'limit' (harder).
    """
    n = len(audio)
    ratio = 3.0 if mode == 'compress' else 10.0
    threshold = -20.0 + (1.0 - peak_reduction) * 15.0
    thresh_lin = 10.0 ** (threshold / 20.0)

    if audio.ndim == 2:
        env_input = np.max(np.abs(audio), axis=1)
    else:
        env_input = np.abs(audio)

    # Optical cell: program-dependent timing
    # Attack: ~10ms, Release: ~60ms (initial) then ~1-5s (secondary)
    alpha_a = np.exp(-1.0 / max(1, 0.01 * sample_rate))
    alpha_r1 = np.exp(-1.0 / max(1, 0.06 * sample_rate))  # fast release
    alpha_r2 = np.exp(-1.0 / max(1, 1.0 * sample_rate))   # slow release

    env = np.zeros(n)
    cur = 0.0
    for i in range(n):
        inp = env_input[i]
        if inp > cur:
            cur = alpha_a * cur + (1.0 - alpha_a) * inp
        else:
            # Dual-time release (optical cell behavior)
            if cur > thresh_lin * 1.5:
                cur = alpha_r1 * cur + (1.0 - alpha_r1) * inp
            else:
                cur = alpha_r2 * cur + (1.0 - alpha_r2) * inp
        env[i] = cur

    # Soft-knee gain reduction
    gain = np.ones(n)
    mask = env > thresh_lin
    over = env[mask] / thresh_lin
    gain[mask] = 1.0 / (1.0 + (over - 1.0) * (ratio - 1.0) / ratio)

    if audio.ndim == 2:
        return audio * gain[:, np.newaxis]
    return audio * gain


# ══════════════════════════════════════════════════════════════
# Pultec EQP-1A  (passive tube EQ – boost + cut magic)
# ══════════════════════════════════════════════════════════════
def apply_pultec_eq(audio, low_boost=0.3, low_atten=0.0, low_freq=60,
                    high_boost=0.3, high_atten=0.0, high_freq=8000,
                    sample_rate=44100, **kwargs):
    """
    Pultec EQP-1A passive tube equalizer.
    Famous trick: boosting AND attenuating the same low frequency
    creates a unique resonant shelf shape with tightened bass.

    low_boost/atten: 0..1 for low frequency.
    high_boost/atten: 0..1 for high frequency.
    """
    x = np.copy(audio)

    # Low band
    if low_boost > 0 or low_atten > 0:
        sos = sig.butter(2, max(30, low_freq), 'lp', fs=sample_rate, output='sos')
        lows = sig.sosfilt(sos, x, axis=0)
        # Boost adds low, atten subtracts with slightly different curve
        x = x + lows * low_boost * 0.4 - lows * low_atten * 0.3
        # The simultaneous boost+cut creates a resonant peak above cutoff
        if low_boost > 0 and low_atten > 0:
            # Resonant bump just above the frequency
            bump_freq = low_freq * 1.5
            w0 = 2.0 * np.pi * bump_freq / sample_rate
            alpha = np.sin(w0) / (2.0 * 2.0)
            cos_w0 = np.cos(w0)
            boost_db = min(4.0, low_boost * 3.0)
            A = 10.0 ** (boost_db / 40.0)
            b = [1 + alpha * A, -2 * cos_w0, 1 - alpha * A]
            a = [1 + alpha / A, -2 * cos_w0, 1 - alpha / A]
            x = sig.lfilter(b, a, x, axis=0)

    # High band
    if high_boost > 0 or high_atten > 0:
        sos_hi = sig.butter(1, min(high_freq, sample_rate * 0.45), 'hp',
                            fs=sample_rate, output='sos')
        highs = sig.sosfilt(sos_hi, x, axis=0)
        x = x + highs * high_boost * 0.3 - highs * high_atten * 0.25

    # Tube warmth (subtle even harmonics from tube stages)
    x = x + 0.01 * x ** 2

    return x


# ══════════════════════════════════════════════════════════════
# Buchla 292 Lowpass Gate  (LPG – vactrol-based filter/VCA)
# ══════════════════════════════════════════════════════════════
def apply_buchla_lpg(audio, strike=0.7, decay=0.3, resonance=0.2,
                     mode='both', sample_rate=44100, **kwargs):
    """
    Buchla 292 Lowpass Gate emulation.
    Vactrol-based: acts as combined filter + VCA with organic,
    bongo-like pluck response. Core of West Coast synthesis.

    strike:    Initial hit intensity 0..1.
    decay:     Vactrol decay time in seconds.
    resonance: Filter resonance.
    mode:      'filter', 'vca', 'both' (combined LPF + VCA).
    """
    n = len(audio)

    # Vactrol envelope – fast attack, slow asymptotic decay
    # Characteristic non-linear decay (fast initial, then slow tail)
    decay_samp = int(decay * sample_rate)
    env = np.zeros(n)
    if decay_samp > 0:
        t_env = np.arange(min(decay_samp, n)) / sample_rate
        # Double-exponential vactrol curve
        fast = np.exp(-t_env / max(0.001, decay * 0.15))
        slow = np.exp(-t_env / max(0.001, decay * 0.8))
        env[:len(t_env)] = strike * (0.7 * fast + 0.3 * slow)

    if mode in ('vca', 'both'):
        if audio.ndim == 2:
            audio = audio * env[:, np.newaxis]
        else:
            audio = audio * env

    if mode in ('filter', 'both'):
        # Cutoff follows envelope
        max_fc = min(sample_rate * 0.45, 12000)
        min_fc = 50

        if audio.ndim == 2:
            s = np.zeros((2, audio.shape[1]))
        else:
            s = np.zeros(2)

        out = np.zeros_like(audio)
        k = resonance * 2.5

        for i in range(n):
            fc = min_fc + env[i] * (max_fc - min_fc)
            g = 2.0 * np.sin(np.pi * fc / sample_rate)

            x = audio[i] - k * s[1]
            s[0] = s[0] + g * (x - s[0])
            s[1] = s[1] + g * (s[0] - s[1])
            out[i] = s[1]

        return out

    return audio


# ══════════════════════════════════════════════════════════════
# Roland Dimension D  (SDD-320 spatial chorus)
# ══════════════════════════════════════════════════════════════
def apply_dimension_d(audio, mode=2, sample_rate=44100, **kwargs):
    """
    Roland SDD-320 Dimension D.
    Legendary BBD-based spatial chorus with 4 preset modes.
    Adds lush stereo width without obvious modulation.
    mode: 1-4 (1 = subtle, 4 = wide)
    """
    n = len(audio)
    mode = max(1, min(4, int(mode)))

    # Mode parameters: (rate, depth, spread)
    mode_params = {
        1: (0.3, 0.0008, 0.3),
        2: (0.5, 0.0015, 0.5),
        3: (0.8, 0.0025, 0.7),
        4: (1.2, 0.0035, 0.9),
    }
    rate, depth, spread = mode_params[mode]

    t = np.arange(n) / sample_rate

    if audio.ndim == 2:
        out = np.copy(audio)
        # Two BBD lines with opposing modulation
        lfo_l = depth * sample_rate * np.sin(2 * np.pi * rate * t)
        lfo_r = depth * sample_rate * np.sin(2 * np.pi * rate * t + np.pi)

        idx = np.arange(n, dtype=float)
        read_l = idx - lfo_l - 200
        read_r = idx - lfo_r - 250
        read_l = np.clip(read_l, 0, n - 1)
        read_r = np.clip(read_r, 0, n - 1)

        wet_l = np.interp(read_l, idx, audio[:, 0])
        wet_r = np.interp(read_r, idx, audio[:, 1])

        out[:, 0] = audio[:, 0] * (1.0 - spread * 0.5) + wet_l * spread * 0.5
        out[:, 1] = audio[:, 1] * (1.0 - spread * 0.5) + wet_r * spread * 0.5
        return out
    else:
        lfo = depth * sample_rate * np.sin(2 * np.pi * rate * t)
        idx = np.arange(n, dtype=float)
        read = idx - lfo - 200
        read = np.clip(read, 0, n - 1)
        wet = np.interp(read, idx, audio)
        return 0.6 * audio + 0.4 * wet


# ══════════════════════════════════════════════════════════════
# Oberheim OB-Xa Multimode Filter
# ══════════════════════════════════════════════════════════════
def apply_obxa_filter(audio, cutoff=2000, resonance=0.6,
                      mode='lowpass', sample_rate=44100, **kwargs):
    """
    Oberheim OB-Xa CEM3320 multimode filter.
    Warm, fat filter with 12dB/oct slopes and smooth resonance.
    Signature Oberheim warmth with musical Q curve.
    """
    n = len(audio)
    fc = max(20, min(cutoff, sample_rate * 0.45))
    k = resonance * 3.5  # Resonance range

    if audio.ndim == 2:
        out = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            hp = np.zeros(n)
            bp = np.zeros(n)
            lp = np.zeros(n)
            s1, s2 = 0.0, 0.0
            for i in range(n):
                g = 2.0 * np.sin(np.pi * fc / sample_rate)
                hp[i] = audio[i, ch] - s1 * k - s2
                bp[i] = hp[i] * g + s1
                lp[i] = bp[i] * g + s2
                s1 = bp[i]
                s2 = lp[i]
            if mode == 'bandpass':
                out[:, ch] = bp
            elif mode == 'highpass':
                out[:, ch] = hp
            else:
                out[:, ch] = lp
        # Oberheim warmth
        out = np.tanh(out * 1.1) * 0.95
        return out
    else:
        hp = np.zeros(n)
        bp = np.zeros(n)
        lp = np.zeros(n)
        s1, s2 = 0.0, 0.0
        for i in range(n):
            g = 2.0 * np.sin(np.pi * fc / sample_rate)
            hp[i] = audio[i] - s1 * k - s2
            bp[i] = hp[i] * g + s1
            lp[i] = bp[i] * g + s2
            s1 = bp[i]
            s2 = lp[i]
        if mode == 'bandpass':
            result = bp
        elif mode == 'highpass':
            result = hp
        else:
            result = lp
        return np.tanh(result * 1.1) * 0.95


# ══════════════════════════════════════════════════════════════
# EDP Wasp Filter  (dirty digital-analog hybrid)
# ══════════════════════════════════════════════════════════════
def apply_wasp_filter(audio, cutoff=1500, resonance=0.7,
                      sample_rate=44100, **kwargs):
    """
    EDP Wasp filter – notorious for using CMOS digital chips as
    'analog' filter elements. Produces dirty, buzzy resonance
    with digital artifacts. Beloved for aggressive bass sounds.
    """
    n = len(audio)
    fc = max(20, min(cutoff, sample_rate * 0.45))
    k = resonance * 3.8

    if audio.ndim == 2:
        mono = np.mean(audio, axis=1)
    else:
        mono = np.copy(audio)

    out = np.zeros(n)
    s1, s2 = 0.0, 0.0

    for i in range(n):
        g = 2.0 * np.sin(np.pi * fc / sample_rate)

        # CMOS digital quantization artifact
        x = mono[i] - k * s2
        # Simulate CMOS digital stepping (4-bit style)
        x_quant = np.round(x * 8.0) / 8.0
        mix = 0.7 * x + 0.3 * x_quant

        s1 = s1 + g * (mix - s1)
        s2 = s2 + g * (s1 - s2)
        out[i] = s2

    # Wasp distortion character
    out = np.tanh(out * 1.5) * 0.9

    if audio.ndim == 2:
        return np.column_stack([out, out])
    return out


# ══════════════════════════════════════════════════════════════
# AMS RMX16  (non-linear digital reverb)
# ══════════════════════════════════════════════════════════════
def apply_ams_reverb(audio, decay=2.0, damping=0.5, program='nonlin',
                     mix=0.3, sample_rate=44100, **kwargs):
    """
    AMS RMX16 digital reverb.
    Famous for its 'Non-Linear' program used on 80s drums.
    Creates gated, reverse-envelope reverb tails.
    programs: 'nonlin' (gated), 'ambience', 'plate'
    """
    n = len(audio)

    if audio.ndim == 2:
        mono = np.mean(audio, axis=1)
    else:
        mono = np.copy(audio)

    # FDN reverb core
    delays = [int(d * sample_rate / 1000) for d in [29, 37, 43, 53, 67, 79]]
    num_lines = len(delays)
    max_delay = max(delays) + 1
    buf = np.zeros((num_lines, max_delay))
    pos = np.zeros(num_lines, dtype=int)

    reverb_out = np.zeros(n)
    fb = 0.7 + decay * 0.05
    fb = min(fb, 0.95)

    for i in range(n):
        inp = mono[i]
        out_sum = 0.0
        for j in range(num_lines):
            d = delays[j]
            read_pos = (pos[j] - d) % max_delay
            delayed = buf[j, read_pos]
            # Damping
            damped = delayed * (1.0 - damping * 0.5)
            buf[j, pos[j]] = inp + damped * fb
            pos[j] = (pos[j] + 1) % max_delay
            out_sum += delayed
        reverb_out[i] = out_sum / num_lines

    # Program-specific envelope shaping
    if program == 'nonlin':
        # Gated reverb envelope – sharp attack, abrupt cutoff
        gate_time = int(min(decay, 0.8) * sample_rate)
        env = np.ones(n)
        if gate_time < n:
            # Reverse slope then gate
            ramp = np.linspace(1.0, 0.2, gate_time)
            env[:gate_time] = ramp
            env[gate_time:] = 0.0
        reverb_out *= env
    elif program == 'ambience':
        # Short decay envelope
        env = np.exp(-np.arange(n) / max(1, decay * 0.3 * sample_rate))
        reverb_out *= env
    # 'plate' uses natural decay, no extra envelope

    mx = np.max(np.abs(reverb_out))
    if mx > 0:
        reverb_out /= mx

    if audio.ndim == 2:
        wet = np.column_stack([reverb_out, reverb_out])
        return (1.0 - mix) * audio + mix * wet
    return (1.0 - mix) * audio + mix * reverb_out


# ══════════════════════════════════════════════════════════════
# TC Electronic 2290  (digital delay with modulation)
# ══════════════════════════════════════════════════════════════
def apply_tc2290(audio, time_ms=350, feedback=0.4, mod_rate=0.3,
                 mod_depth=0.002, mix=0.35, sample_rate=44100, **kwargs):
    """
    TC Electronic 2290 digital delay.
    Pristine digital delay with subtle modulation.
    Famous for its clean repeats and musical feedback.
    """
    n = len(audio)
    delay_samp = int(time_ms * sample_rate / 1000)
    delay_samp = max(1, min(delay_samp, n - 1))

    if audio.ndim == 2:
        mono = np.mean(audio, axis=1)
    else:
        mono = np.copy(audio)

    buf = np.zeros(delay_samp + int(mod_depth * sample_rate) + 100)
    buf_len = len(buf)
    out = np.zeros(n)
    write_pos = 0

    t = np.arange(n) / sample_rate
    lfo = mod_depth * sample_rate * np.sin(2 * np.pi * mod_rate * t)

    for i in range(n):
        # Modulated read position
        read_offset = delay_samp + lfo[i]
        read_pos = (write_pos - int(read_offset)) % buf_len

        # Linear interpolation
        frac = read_offset - int(read_offset)
        r1 = buf[read_pos]
        r2 = buf[(read_pos + 1) % buf_len]
        delayed = r1 + frac * (r2 - r1)

        out[i] = delayed

        # Write with feedback
        buf[write_pos] = mono[i] + delayed * feedback
        write_pos = (write_pos + 1) % buf_len

    if audio.ndim == 2:
        wet = np.column_stack([out, out])
        return (1.0 - mix) * audio + mix * wet
    return (1.0 - mix) * audio + mix * out


# ══════════════════════════════════════════════════════════════
# UREI 1176  (FET peak limiter)
# ══════════════════════════════════════════════════════════════
def apply_1176(audio, input_gain=0.5, ratio=4, attack=0.3,
               release=0.5, sample_rate=44100, **kwargs):
    """
    UREI 1176 FET Peak Limiter.
    Ultra-fast FET-based compression with program-dependent attack.
    ratio: 4, 8, 12, 20 (or 'all' for all-buttons-in mode)
    Famous for aggressive, punchy compression.

    Parameters:
    input_gain: Drives the input stage (higher = more compression).
    ratio: Compression ratio (4, 8, 12, 20).
    attack: Attack time (0.0..1.0).
    release: Release time (0.0..1.0).
    """
    n = len(audio)

    # Input gain stage
    x = audio * (1.0 + input_gain * 3.0)

    # Ratios (integer mapped)
    ratio_val = ratio if isinstance(ratio, (int, float)) else 20
    ratio_val = max(1, ratio_val)

    # All-buttons-in mode = extreme distorted compression
    all_buttons = ratio_val >= 20

    # FET attack/release (very fast)
    att_ms = 0.02 + attack * 0.8  # 0.02ms to 0.82ms
    rel_ms = 50 + release * 1050  # 50ms to 1100ms

    alpha_a = np.exp(-1.0 / max(1, (att_ms / 1000) * sample_rate))
    alpha_r = np.exp(-1.0 / max(1, (rel_ms / 1000) * sample_rate))

    if x.ndim == 2:
        env_in = np.max(np.abs(x), axis=1)
    else:
        env_in = np.abs(x)

    threshold = 0.25  # Fixed threshold (1176 uses input gain instead)
    env = np.zeros(n)
    cur = 0.0
    for i in range(n):
        if env_in[i] > cur:
            cur = alpha_a * cur + (1.0 - alpha_a) * env_in[i]
        else:
            cur = alpha_r * cur + (1.0 - alpha_r) * env_in[i]
        env[i] = cur

    gain = np.ones(n)
    mask = env > threshold
    if np.any(mask):
        over_db = 20.0 * np.log10(env[mask] / threshold + 1e-12)
        gain[mask] = 10.0 ** ((over_db / ratio_val - over_db) / 20.0)

    if x.ndim == 2:
        out = x * gain[:, np.newaxis]
    else:
        out = x * gain

    # FET harmonic distortion (odd harmonics, slight)
    harm = 0.03 if not all_buttons else 0.1
    out = out + harm * out ** 3

    # All-buttons-in adds aggressive saturation
    if all_buttons:
        out = np.tanh(out * 2.0) * 0.7

    return out

