"""
pySynth Oscillator Module - "The FiggyGen"
Supports: Sine, Square, Saw, Triangle, Pulse (PWM), Morph,
          SuperSaw (JP-8000 style), Wavetable, FM Operator, Additive,
          White/Pink/Brown/Blue/Purple Noise,
          FM synthesis, AM synthesis, Phase Modulation,
          Super-Unison with Stereo Spread.
"""
import numpy as np
from scipy import signal


class Oscillator:
    """Multi-mode oscillator with unison, detune, and stereo spread."""

    WAVEFORMS = [
        # Classic analog
        'sine', 'square', 'saw', 'triangle', 'pulse',
        'morph',       # morphs triangle -> saw -> square via morph_pos
        'supersaw',    # 7-voice JP-8000 style detuned saws
        # Digital / synthesis
        'wavetable',   # 8-frame morphable wavetable
        'fm_op',       # 2-operator FM synthesis
        'additive',    # 8-harmonic additive synthesis
        'sync',        # Hard oscillator sync
        'pwm_sweep',   # Auto-sweeping pulse width
        'harsh',       # Rectified + folded aggressive
        'chip',        # 8-bit quantized (chiptune)
        # Physical modeling
        'pluck',       # Karplus-Strong plucked string
        'strings',     # Bowed string (saw + filtered noise)
        'brass',       # Brass-like (saw + formant)
        'organ',       # Hammond drawbar organ
        'bell',        # FM bell (inharmonic)
        'glass',       # Struck glass (inharmonic partials)
        # Textural
        'vocal',       # Vowel-shaped formant oscillator
        'breath',      # Filtered noise with tonal core
        'pad_wash',    # Multiple detuned sines
        'click',       # Short impulse burst
        # Percussive
        'kick',        # TR-808 style exponential pitch sweep
        'snare',       # Tone + noise mix
        'hat',         # Metallic inharmonic partials
        # 808 Emulation
        'kick_808', 'snare_808', 'hat_808', 'cowbell_808',
        # 909 Emulation
        'kick_909', 'snare_909', 'hat_909',
        # Classic Machines (CR-78 / TR-707 Style)
        'kick_78', 'snare_78', 'hat_78',
        'kick_707', 'snare_707',
        # Percussion
        'clap', 'cymbal_crash', 'cymbal_ride', 'tom', 'rimshot',
        'shaker', 'woodblock', 'cowbell',
        # FX / Glitch
        'zap', 'scratch', 'impact',
        # Bass / Tonal
        'bass_slap', 'piano_electric', 'drone_dark',
        # Noise
        'noise_white', 'noise_pink', 'noise_brown', 'noise_blue', 'noise_purple',
        # Sample Playback
        'sample',
    ]

    def __init__(self, waveform='sine', frequency=440.0, detune=0.0, phase=0.0,
                 pulse_width=0.5, morph_pos=0.0, gain=1.0,
                 unison=1, unison_detune=0.0, unison_spread=0.0,
                 fm_ratio=2.0, fm_depth=1.0,
                 harmonics=None, **kwargs):
        """
        Args:
            waveform: One of WAVEFORMS.
            frequency: Base frequency in Hz (overridden by note in render).
            detune: Master detune in cents.
            phase: Initial phase 0..1.
            pulse_width: Duty cycle for square/pulse 0.01..0.99.
            morph_pos: Morph position 0..1.
                       morph:     0=triangle, 0.5=saw, 1=square.
                       wavetable: 0..1 scans through 8 frames.
                       supersaw:  detune spread amount 0..1.
            gain: Amplitude multiplier 0..2.
            unison: Number of unison voices 1..10.
            unison_detune: Spread of detune across voices in cents.
            unison_spread: Stereo spread 0..1.
            fm_ratio: Modulator/carrier frequency ratio (fm_op only).
            fm_depth: FM modulation depth in radians (fm_op only).
            harmonics: List of 8 harmonic amplitudes (additive only).
        """
        self.waveform = waveform
        self.frequency = frequency
        self.detune = detune
        self.phase = phase
        self.pulse_width = max(0.01, min(0.99, pulse_width))
        self.morph_pos = morph_pos
        self.gain = gain
        self.unison = max(1, int(unison))
        self.unison_detune = unison_detune
        self.unison_spread = unison_spread
        self.fm_ratio = fm_ratio
        self.fm_depth = fm_depth
        self.harmonics = harmonics if harmonics is not None else [
            1.0, 0.5, 0.3, 0.25, 0.2, 0.15, 0.1, 0.08
        ]
        self.sample_data = kwargs.get('sample_data', None)
        self.sample_rate = 44100

    def set_sample_rate(self, sr):
        self.sample_rate = sr

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self, duration, fm_mod=None, pm_mod=None):
        """
        Render oscillator for *duration* seconds.

        Returns:
            np.ndarray – shape (N,) mono  if unison==1 & spread==0
                         shape (N,2) stereo otherwise.
        """
        N = int(duration * self.sample_rate)

        # Fast path: single voice, mono
        if self.unison <= 1 and self.unison_spread == 0:
            return self._voice(N, 0.0, fm_mod, pm_mod, 0) * self.gain

        # Multi-voice with stereo panning
        out = np.zeros((N, 2))
        detunes = np.linspace(-self.unison_detune, self.unison_detune, self.unison)
        pans = np.linspace(-self.unison_spread, self.unison_spread, self.unison)

        for i in range(self.unison):
            mono = self._voice(N, detunes[i], fm_mod, pm_mod, i)
            p = (pans[i] + 1.0) / 2.0          # 0..1
            L = np.sqrt(1.0 - p)
            R = np.sqrt(p)
            out[:, 0] += mono * L
            out[:, 1] += mono * R

        out *= self.gain / np.sqrt(self.unison)
        return out

    # ------------------------------------------------------------------
    # Internal voice renderer
    # ------------------------------------------------------------------
    def _voice(self, N, extra_cents, fm_mod, pm_mod, idx):
        """Render a single mono voice."""
        cents = self.detune + extra_cents
        freq = self.frequency * (2.0 ** (cents / 1200.0))

        freqs = np.full(N, freq)
        if fm_mod is not None:
            freqs = freqs + fm_mod[:N]

        phase = 2.0 * np.pi * np.cumsum(freqs) / self.sample_rate
        phase += self.phase * 2.0 * np.pi
        # Golden-ratio phase offset for each voice
        if idx > 0:
            phase += idx * (2.0 * np.pi / 1.618033988749895)
        if pm_mod is not None:
            phase = phase + pm_mod[:N]

        wf = self.waveform

        if wf == 'sample':
            return self._gen_sample(N)

        if wf == 'sine':
            return np.sin(phase)

        if wf == 'square':
            return signal.square(phase, duty=self.pulse_width)

        if wf == 'pulse':
            return signal.square(phase, duty=self.pulse_width)

        if wf == 'saw':
            return signal.sawtooth(phase)

        if wf == 'triangle':
            return signal.sawtooth(phase, width=0.5)

        if wf == 'morph':
            # morph_pos 0 = triangle, 0.5 = saw, 1 = square
            m = self.morph_pos
            tri = signal.sawtooth(phase, width=0.5)
            saw = signal.sawtooth(phase)
            sqr = signal.square(phase, duty=0.5)
            if m <= 0.5:
                t = m * 2.0
                return tri * (1.0 - t) + saw * t
            else:
                t = (m - 0.5) * 2.0
                return saw * (1.0 - t) + sqr * t

        # ----- SuperSaw (JP-8000 style) -----
        if wf == 'supersaw':
            spread = max(0.01, self.morph_pos)  # morph_pos controls detune spread
            num_saws = 7
            # Fixed detune ratios (JP-8000 style distribution)
            ratios = [-0.11002, -0.06288, -0.01952, 0.0,
                       0.01991, 0.06216, 0.10745]
            out = np.zeros(N)
            for r in ratios:
                cents_off = r * spread * 100  # max ~11 cents per voice
                f = freq * (2.0 ** (cents_off / 1200.0))
                ph = 2.0 * np.pi * np.cumsum(np.full(N, f)) / self.sample_rate
                ph += np.random.uniform(0, 2 * np.pi)  # random start phase
                out += signal.sawtooth(ph)
            out /= num_saws * 0.7  # Normalize but keep it loud
            return out

        # ----- Wavetable -----
        if wf == 'wavetable':
            # 8 pre-built frames: sine -> complex -> saw -> aggressive
            pos = max(0.0, min(1.0, self.morph_pos))

            frames = []
            # Frame 0: pure sine
            frames.append(np.sin(phase))
            # Frame 1: sine + 2nd harmonic
            frames.append(np.sin(phase) * 0.7 + np.sin(phase * 2) * 0.3)
            # Frame 2: sine + 2nd + 3rd
            frames.append(np.sin(phase) * 0.5 + np.sin(phase * 2) * 0.3
                          + np.sin(phase * 3) * 0.2)
            # Frame 3: hollow square-like (odd harmonics)
            frames.append(np.sin(phase) * 0.6 + np.sin(phase * 3) * 0.25
                          + np.sin(phase * 5) * 0.15)
            # Frame 4: triangle + harmonics
            frames.append(signal.sawtooth(phase, width=0.5) * 0.5
                          + np.sin(phase * 4) * 0.3 + np.sin(phase * 6) * 0.2)
            # Frame 5: soft saw
            frames.append(signal.sawtooth(phase) * 0.6
                          + np.sin(phase) * 0.4)
            # Frame 6: hard saw + even harmonics
            frames.append(signal.sawtooth(phase) * 0.8
                          + np.sin(phase * 2) * 0.15 + np.sin(phase * 4) * 0.05)
            # Frame 7: aggressive digital
            frames.append(signal.square(phase, duty=0.5) * 0.5
                          + signal.sawtooth(phase) * 0.3
                          + np.sin(phase * 5) * 0.2)

            # Interpolate between frames
            f_idx = pos * 7.0  # 0..7
            lo = int(f_idx)
            hi = min(lo + 1, 7)
            frac = f_idx - lo
            return frames[lo] * (1.0 - frac) + frames[hi] * frac

        # ----- FM Operator (2-op FM synthesis) -----
        if wf == 'fm_op':
            # Carrier + modulator = rich harmonic content
            mod_freq = freq * self.fm_ratio
            mod_phase = 2.0 * np.pi * np.cumsum(
                np.full(N, mod_freq)) / self.sample_rate
            modulator = np.sin(mod_phase) * self.fm_depth
            return np.sin(phase + modulator)

        # ----- Additive Synthesis (8 harmonics) -----
        if wf == 'additive':
            harmonics = self.harmonics[:8]
            out = np.zeros(N)
            for h, amp in enumerate(harmonics):
                if amp > 0.001:
                    harm_freq = freq * (h + 1)
                    # Skip harmonics above Nyquist
                    if harm_freq < self.sample_rate * 0.45:
                        harm_phase = 2.0 * np.pi * np.cumsum(
                            np.full(N, harm_freq)) / self.sample_rate
                        out += np.sin(harm_phase) * amp
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        # ----- Hard Sync -----
        if wf == 'sync':
            # Slave oscillator resets at master frequency; ratio sets slave pitch
            slave_ratio = max(1.01, self.fm_ratio)  # reuse fm_ratio
            slave_phase = phase * slave_ratio
            # Hard sync = reset slave phase each master cycle
            master_cycles = np.floor(phase / (2.0 * np.pi))
            slave_reset = slave_phase - (master_cycles * slave_ratio * 2.0 * np.pi)
            return np.sin(slave_reset)

        # ----- PWM Sweep -----
        if wf == 'pwm_sweep':
            # Auto-sweeping pulse width modulation
            sweep_rate = self.fm_ratio * 0.5  # reuse as sweep speed
            t = np.arange(N) / self.sample_rate
            pw = 0.5 + 0.35 * np.sin(2.0 * np.pi * sweep_rate * t)
            pw = np.clip(pw, 0.05, 0.95)
            # Generate pulse with varying width
            normalized = (phase % (2.0 * np.pi)) / (2.0 * np.pi)
            return np.where(normalized < pw, 1.0, -1.0)

        # ----- Harsh -----
        if wf == 'harsh':
            # Full-wave rectified saw + wavefold = aggressive digital
            saw = signal.sawtooth(phase)
            rectified = np.abs(saw)
            # Simple wavefold
            folded = np.sin(rectified * np.pi * 3)
            return folded * 0.7 + saw * 0.3

        # ----- Chip (8-bit) -----
        if wf == 'chip':
            # Quantized waveform for chiptune/retro sounds
            levels = 16  # 4-bit quantization
            raw = signal.sawtooth(phase)
            quantized = np.round(raw * levels) / levels
            return quantized

        # ----- Pluck (Karplus-Strong) -----
        if wf == 'pluck':
            delay_samples = max(2, int(self.sample_rate / freq))
            buf = np.random.uniform(-1, 1, delay_samples).astype(np.float64)
            out = np.zeros(N)
            decay = 0.996  # controls sustain
            write_pos = 0
            for i in range(N):
                out[i] = buf[write_pos]
                # Average adjacent samples (KS algorithm)
                next_pos = (write_pos + 1) % delay_samples
                buf[write_pos] = decay * 0.5 * (buf[write_pos] + buf[next_pos])
                write_pos = next_pos
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        # ----- Strings (bowed) -----
        if wf == 'strings':
            # Sawtooth + filtered noise for bowed texture
            saw = signal.sawtooth(phase) * 0.7
            bow_noise = np.random.randn(N) * 0.05
            # Simple lowpass on noise
            b, a = signal.butter(2, min(freq * 4, self.sample_rate * 0.45),
                                 btype='low', fs=self.sample_rate)
            bow_filtered = signal.lfilter(b, a, bow_noise)
            # Add harmonics 2, 3 for richness
            return saw + bow_filtered + np.sin(phase * 2) * 0.15 + np.sin(phase * 3) * 0.08

        # ----- Brass -----
        if wf == 'brass':
            # Bright saw with formant-like resonance peaks
            saw = signal.sawtooth(phase) * 0.6
            # Formant peaks at typical brass frequencies
            h2 = np.sin(phase * 2) * 0.25
            h3 = np.sin(phase * 3) * 0.2
            h5 = np.sin(phase * 5) * 0.1
            h7 = np.sin(phase * 7) * 0.05
            return saw + h2 + h3 + h5 + h7

        # ----- Organ (Hammond drawbar) -----
        if wf == 'organ':
            # Hammond B3 drawbar registration: 16' 8' 5-1/3' 4' 2-2/3' 2' 1-3/5' 1-1/3' 1'
            drawbar_ratios = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
            # Default registration (Gospel/Full)
            levels = [0.8, 1.0, 0.6, 0.8, 0.5, 0.7, 0.3, 0.4, 0.3]
            out = np.zeros(N)
            for ratio, level in zip(drawbar_ratios, levels):
                h_freq = freq * ratio
                if h_freq < self.sample_rate * 0.45:
                    h_phase = 2.0 * np.pi * np.cumsum(
                        np.full(N, h_freq)) / self.sample_rate
                    out += np.sin(h_phase) * level
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        # ----- Bell (FM inharmonic) -----
        if wf == 'bell':
            # FM with inharmonic ratio for bell/chime tones
            mod_ratio = 1.414  # sqrt(2) = inharmonic
            mod_freq = freq * mod_ratio
            mod_phase = 2.0 * np.pi * np.cumsum(
                np.full(N, mod_freq)) / self.sample_rate
            # Decaying modulation depth for bell-like attack
            t = np.arange(N) / self.sample_rate
            mod_env = np.exp(-t * 5.0) * self.fm_depth * 3.0
            modulator = np.sin(mod_phase) * mod_env
            carrier = np.sin(phase + modulator)
            # Apply amplitude decay
            amp_env = np.exp(-t * 2.0)
            return carrier * amp_env

        # ----- Glass -----
        if wf == 'glass':
            # Multiple inharmonic partials like struck glass
            ratios = [1.0, 2.17, 3.31, 4.57, 5.84, 7.12]
            amps = [1.0, 0.6, 0.4, 0.25, 0.15, 0.08]
            t = np.arange(N) / self.sample_rate
            out = np.zeros(N)
            for ratio, amp in zip(ratios, amps):
                h_freq = freq * ratio
                if h_freq < self.sample_rate * 0.45:
                    h_phase = 2.0 * np.pi * np.cumsum(
                        np.full(N, h_freq)) / self.sample_rate
                    decay = np.exp(-t * (1.5 + ratio * 0.5))
                    out += np.sin(h_phase) * amp * decay
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        # ----- Vocal (formant oscillator) -----
        if wf == 'vocal':
            # Vowel-shaped using morph_pos: 0=ah, 0.25=eh, 0.5=ee, 0.75=oh, 1=oo
            m = max(0.0, min(1.0, self.morph_pos))
            # Formant frequency pairs (F1, F2) for vowels
            vowels = [(800, 1200), (600, 1800), (300, 2500),
                      (500, 900), (350, 700)]
            idx = m * 4.0
            lo_v = int(idx)
            hi_v = min(lo_v + 1, 4)
            frac = idx - lo_v
            f1 = vowels[lo_v][0] * (1 - frac) + vowels[hi_v][0] * frac
            f2 = vowels[lo_v][1] * (1 - frac) + vowels[hi_v][1] * frac
            # Generate glottal pulse (saw) + formant resonances
            glottal = signal.sawtooth(phase) * 0.5
            formant1 = np.sin(2.0 * np.pi * f1 * np.arange(N) / self.sample_rate) * 0.3
            formant2 = np.sin(2.0 * np.pi * f2 * np.arange(N) / self.sample_rate) * 0.2
            return glottal + formant1 + formant2

        # ----- Breath -----
        if wf == 'breath':
            # Filtered noise with a tonal core
            noise = np.random.randn(N) * 0.3
            tone = np.sin(phase) * 0.4
            combined = noise + tone
            # Bandpass around the fundamental
            lo = max(20, freq * 0.5)
            hi = min(freq * 3.0, self.sample_rate * 0.45)
            if hi > lo:
                b, a = signal.butter(2, [lo, hi], btype='band', fs=self.sample_rate)
                combined = signal.lfilter(b, a, combined)
            mx = np.max(np.abs(combined))
            return combined / mx if mx > 0 else combined

        # ----- Pad Wash -----
        if wf == 'pad_wash':
            # Multiple slightly detuned sines for shimmering pad texture
            num_voices = 5
            detunes = [-7, -3, 0, 3, 7]  # cents
            out = np.zeros(N)
            for d in detunes:
                f = freq * (2.0 ** (d / 1200.0))
                ph = 2.0 * np.pi * np.cumsum(np.full(N, f)) / self.sample_rate
                ph += np.random.uniform(0, 2 * np.pi)
                out += np.sin(ph)
            return out / num_voices

        # ----- Click -----
        if wf == 'click':
            # Short impulse burst — useful for percussive attacks
            click_len = min(int(0.005 * self.sample_rate), N)  # 5ms
            out = np.zeros(N)
            click = np.sin(2.0 * np.pi * freq * np.arange(click_len) / self.sample_rate)
            click *= np.exp(-np.arange(click_len) / (click_len * 0.3))
            out[:click_len] = click
            return out

        # ----- Kick (TR-808 style) -----
        if wf == 'kick':
            # Clamp settling freq to kick territory; use input freq for character
            t = np.arange(N) / self.sample_rate
            end_freq = np.clip(freq, 30, 80)
            start_freq = max(end_freq * 5, 150) + freq * 0.3
            sweep = end_freq + (start_freq - end_freq) * np.exp(-t * 40)
            ph = 2.0 * np.pi * np.cumsum(sweep) / self.sample_rate
            tone = np.sin(ph)
            # Amplitude envelope: fast attack, medium decay
            env = np.exp(-t * 6)
            return tone * env

        # ----- Snare -----
        if wf == 'snare':
            t = np.arange(N) / self.sample_rate
            # Tone component (pitch sweep)
            sweep = freq + 80 * np.exp(-t * 50)
            ph = 2.0 * np.pi * np.cumsum(sweep) / self.sample_rate
            tone = np.sin(ph) * np.exp(-t * 15) * 0.6
            # Noise component (bandpass filtered)
            noise = np.random.randn(N) * np.exp(-t * 10) * 0.5
            lo_f = max(20, 1000)
            hi_f = min(8000, self.sample_rate * 0.45)
            if hi_f > lo_f:
                b, a = signal.butter(2, [lo_f, hi_f], btype='band', fs=self.sample_rate)
                noise = signal.lfilter(b, a, noise)
            return tone + noise

        # ----- Hat -----
        if wf == 'hat':
            # Metallic inharmonic tones + high noise
            ratios = [1.0, 1.47, 1.84, 2.55, 3.17, 3.72]
            t = np.arange(N) / self.sample_rate
            out = np.zeros(N)
            for r in ratios:
                h_freq = min(freq * r, self.sample_rate * 0.45)
                ph = 2.0 * np.pi * np.cumsum(np.full(N, h_freq)) / self.sample_rate
                out += np.sin(ph) * 0.15
            # High-passed noise
            noise = np.random.randn(N) * 0.5
            hp_freq = min(5000, self.sample_rate * 0.45)
            b, a = signal.butter(2, hp_freq, btype='high', fs=self.sample_rate)
            noise = signal.lfilter(b, a, noise)
            out += noise
            # Sharp decay
            env = np.exp(-t * 25)
            out *= env
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        # ======================================================================
        # TR-808 Emulation
        # ======================================================================
        if wf == 'kick_808':
            # Bridged-T network simulation: Sine with pitch envelope
            t = np.arange(N) / self.sample_rate
            # Clamp settling freq to sub-bass kick territory
            end_freq = np.clip(freq, 30, 80)
            # Higher input freq = more aggressive pitch sweep (more click/punch)
            start_freq = max(150, end_freq * 4) + freq * 0.5
            # Pitch envelope decay
            p_env = np.exp(-t * 25)
            f_inst = end_freq + (start_freq - end_freq) * p_env
            phase_acc = 2 * np.pi * np.cumsum(f_inst) / self.sample_rate
            tone = np.sin(phase_acc)
            
            # Amplitude envelope: Click (transient) + Body (long 808 boom)
            click = np.exp(-t * 1000) * 0.5  # sharp click
            amp_env = np.exp(-t * 2.0)  # long decay for 808 boom
            
            out = tone * amp_env + click
            
            # Soft saturation for warmth
            out = np.tanh(out * 1.5)
            return out

        if wf == 'snare_808':
            # Two components: Tonal (T-bridge) + Noise (Snappy)
            t = np.arange(N) / self.sample_rate
            
            # 1. Tonal: High sine + slightly lower sine
            f1 = freq * 2.0  # e.g., ~350Hz
            f2 = f1 * 1.5    # e.g., ~525Hz
            # 808 snare tone decay is very fast
            tone_env = np.exp(-t * 35.0)
            tone = (np.sin(2 * np.pi * f1 * t) * 0.6 + 
                    np.sin(2 * np.pi * f2 * t) * 0.4) * tone_env
            
            # 2. Noise: White noise -> Bandpass -> Envelope
            noise = np.random.uniform(-1, 1, N)
            # 808 Snare is somewhat broad, centered around 2-4kHz
            b, a = signal.butter(2, [1000, 6000], btype='band', fs=self.sample_rate)
            snappy = signal.lfilter(b, a, noise)
            
            if len(snappy) > 0:
                mx = np.max(np.abs(snappy))
                if mx > 0: snappy /= mx
            
            snappy_env = np.exp(-t * 15.0)  # separate envelope for snares
            snappy *= snappy_env
            
            out = tone * 0.7 + snappy * 0.9
            return out

        if wf == 'hat_808':
            # 6 Schmitt Trigger Oscillators (Square waves) summed
            # Result is a metallic "hash"
            t = np.arange(N) / self.sample_rate
            ratios = [263, 400, 421, 474, 587, 845] # Theoretical 808 ratios relative to ~1Hz? No, these are Hz values typically
            # Let's scale them by freq to allow tuning
            base_f = freq if freq > 100 else 300
            osc_freqs = [base_f * (r/300.0) for r in ratios]
            
            metal = np.zeros(N)
            for f in osc_freqs:
                if f < self.sample_rate * 0.45:
                    ph = 2.0 * np.pi * np.cumsum(np.full(N, f)) / self.sample_rate
                    # 808 use square waves
                    metal += signal.square(ph)
            
            # Highpass filter ~ 7kHz
            b, a = signal.butter(2, min(7000, self.sample_rate*0.4), btype='high', fs=self.sample_rate)
            metal_filtered = signal.lfilter(b, a, metal)
            
            # Decay envelope: short for CH, longer for OH?
            # We'll assume a generic decay driven by duration
            env = np.exp(-t * 20.0) # fairly short
            out = metal_filtered * env
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        if wf == 'cowbell_808':
            # Two square waves passed through a bandpass filter
            t = np.arange(N) / self.sample_rate
            f1 = 540.0
            f2 = 800.0
            # Allow tuning
            ratio = freq / 440.0 if freq > 0 else 1.0
            f1 *= ratio
            f2 *= ratio
            
            osc1 = signal.square(2 * np.pi * f1 * t)
            osc2 = signal.square(2 * np.pi * f2 * t)
            raw = osc1 + osc2
            
            # Bandpass filter
            bp_lo = min(f1 * 0.8, self.sample_rate * 0.45)
            bp_hi = min(f2 * 1.5, self.sample_rate * 0.45)
            if bp_hi > bp_lo:
                b, a = signal.butter(2, [bp_lo, bp_hi], btype='band', fs=self.sample_rate)
                filtered = signal.lfilter(b, a, raw)
            else:
                filtered = raw
                
            # Envelope
            env = np.exp(-t * 5.0)
            return filtered * env

        # ======================================================================
        # TR-909 Emulation
        # ======================================================================
        if wf == 'kick_909':
            # 909 Kick: More aggressive pitch sweep, distorted sine
            t = np.arange(N) / self.sample_rate
            # Clamp to kick territory (909 slightly higher than 808)
            end_freq = np.clip(freq, 40, 90)
            start_freq = max(200, end_freq * 5) + freq * 0.3
            
            # PITCH ENV: Very fast decay at start
            p_env = np.exp(-t * 60)
            f_inst = end_freq + (start_freq - end_freq) * p_env
            phase_acc = 2 * np.pi * np.cumsum(f_inst) / self.sample_rate
            
            # Introduce some harmonics/distortion by squashing the sine
            tone = np.sin(phase_acc)
            # 909 overdrive/clipper
            tone = np.tanh(tone * 2.0) 
            
            # Click is part of the attack transients (pulse)
            click = np.zeros(N)
            click_len = min(N, int(0.003 * self.sample_rate)) # 3ms click
            click[:click_len] = np.random.choice([-1.0, 1.0], click_len) * 0.5
            
            # Amplitude Envelope
            amp_env = np.exp(-t * 3.5)
            out = tone * amp_env + click * np.exp(-t * 200)
            
            return out

        if wf == 'snare_909':
            # Similar to 808 but different tuning and noise character
            t = np.arange(N) / self.sample_rate
            
            # Tone
            f_tone = max(freq, 180) # 909 snare is distinctively tuned ~180-250Hz
            # Slight pitch sweep
            f_sweep = f_tone + 50 * np.exp(-t * 30)
            ph = 2 * np.pi * np.cumsum(f_sweep) / self.sample_rate
            tone = np.sin(ph) * np.exp(-t * 20)
            
            # Noise (Snappy)
            noise = np.random.uniform(-1, 1, N)
            # Lowpass filter for the noise (unlike 808's bandpass, 909 feels 'chunkier')
            # Actually 909 has a specific distinct complex filter
            # Approximation: Highpass then Lowpass
            b, a = signal.butter(1, 1000, btype='high', fs=self.sample_rate)
            noise = signal.lfilter(b, a, noise)
            b, a = signal.butter(1, 8000, btype='low', fs=self.sample_rate)
            noise = signal.lfilter(b, a, noise)
            
            snappy_env = np.exp(-t * 12)
            noise *= snappy_env
            
            out = tone * 0.6 + noise * 0.8
            return out

        if wf == 'hat_909':
            # 909 Hat comes from 6-bit PCM samples on original hardware.
            # Synthesis approximation:
            # FM-rich metallic noise or Ring Mod
            t = np.arange(N) / self.sample_rate
            
            # Use PM (Phase Modulation) cluster
            carriers = [300, 420, 680, 800]
            out = np.zeros(N)
            for fc in carriers:
                # Modulate carrier with a ratio ~ 1.4-1.7
                fm = fc * 1.414
                mod = np.sin(2 * np.pi * fm * t) * 5.0 # high index
                car = np.sin(2 * np.pi * fc * t + mod)
                out += car
            
            # Highpass aggressively
            b, a = signal.butter(2, 6000, btype='high', fs=self.sample_rate)
            out = signal.lfilter(b, a, out)
            
            # Amplitude env
            env = np.exp(-t * 18.0)
            out *= env
            
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        # ======================================================================
        # Classic Machines & Percussion
        # ======================================================================
        
        # --- CR-78 Style ---
        if wf == 'kick_78':
            # Soft blip, very short decay. High resonance filter ping.
            t = np.arange(N) / self.sample_rate
            end_freq = np.clip(freq, 40, 100)
            f_sweep = end_freq * (1.0 + 3.0 * np.exp(-t * 40.0)) # subtle sweep
            ph = 2 * np.pi * np.cumsum(f_sweep) / self.sample_rate
            tone = np.sin(ph)
            env = np.exp(-t * 12.0) 
            # Add a tiny bit of click
            click = np.zeros(N)
            click[0:50] = 0.5
            out = tone * env + click * 0.1
            return out

        if wf == 'snare_78':
            # Metallic ring mod + noise
            t = np.arange(N) / self.sample_rate
            # Ring mod part
            f1, f2 = 230.0, 340.0
            tone = np.sin(2*np.pi*f1*t) * np.sin(2*np.pi*f2*t)
            tone_env = np.exp(-t * 20.0)
            # Noise part (high passed)
            noise = np.random.uniform(-1, 1, N)
            b, a = signal.butter(2, 2000, 'high', fs=self.sample_rate)
            noise = signal.lfilter(b, a, noise)
            noise_env = np.exp(-t * 15.0)
            
            out = tone * tone_env * 0.6 + noise * noise_env * 0.4
            return out

        if wf == 'hat_78':
            # Bandpassed metallic noise
            t = np.arange(N) / self.sample_rate
            # Metal hash: 4 square waves
            out = np.zeros(N)
            freqs = [300, 350, 420, 600]
            for f in freqs:
                out += signal.square(2*np.pi*f*t)
            
            # Bandpass 5k-9k
            b, a = signal.butter(2, [5000, 9000], 'band', fs=self.sample_rate)
            out = signal.lfilter(b, a, out)
            
            env = np.exp(-t * 30.0) # Short
            return out * env
            
        # --- TR-707 Style ---
        if wf == 'kick_707':
            # Boxy, low-mid thump. Square-ish pulse with lowpass.
            t = np.arange(N) / self.sample_rate
            # Clamp to kick territory
            end_freq = np.clip(freq, 40, 100)
            f_inst = end_freq + (end_freq * 1.5) * np.exp(-t * 20.0)
            ph = 2 * np.pi * np.cumsum(f_inst) / self.sample_rate
            # Rounded square/pulse
            raw = np.tanh(np.sin(ph) * 5.0)
            # Lowpass hard
            b, a = signal.butter(2, 400, 'low', fs=self.sample_rate)
            tone = signal.lfilter(b, a, raw)
            env = np.exp(-t * 5.0)
            # Transient click
            click = np.random.randn(N) * np.exp(-t * 500)
            return tone * env + click * 0.2

        if wf == 'snare_707':
            # Tight, papery. 
            t = np.arange(N) / self.sample_rate
            # Low tone
            tone = np.sin(2*np.pi * 200 * t) * np.exp(-t * 25.0)
            # Noise burst
            noise = np.random.uniform(-1, 1, N)
            env = np.exp(-t * 12.0)
            out = tone * 0.3 + noise * env * 0.7
            return out

        # --- Percussion ---
        if wf == 'clap':
            # Multi-burst noise
            t = np.arange(N) / self.sample_rate
            noise = np.random.uniform(-1, 1, N)
            
            # Filter noise (Bandpass 800 - 4000)
            b, a = signal.butter(2, [800, 4000], 'band', fs=self.sample_rate)
            noise = signal.lfilter(b, a, noise)
            
            # Burst envelope: 3-4 bursts then decay
            # Envelopes spaced by ~10ms
            env = np.zeros(N)
            bursts = [0.0, 0.012, 0.025, 0.038] # seconds
            for onset in bursts:
                idx = int(onset * self.sample_rate)
                if idx < N:
                    # Individual burst decay
                    remaining = N - idx
                    sub_t = np.arange(remaining) / self.sample_rate
                    # Very fast decay for first ones
                    e = np.exp(-sub_t * 300.0) 
                    env[idx:] += e * 0.8
            
            # Main tail
            tail_idx = int(0.030 * self.sample_rate)
            if tail_idx < N:
                sub_t = np.arange(N - tail_idx) / self.sample_rate
                # Reverb-like tail
                env[tail_idx:] += np.exp(-sub_t * 10.0) * 0.6

            return noise * np.clip(env, 0, 1)

        if wf == 'cymbal_crash':
            # Complex metallic splash
            t = np.arange(N) / self.sample_rate
            # Sum of 6 square waves with non-integer ratios
            freqs = [300, 380, 520, 890, 1100, 1400]
            metal = np.zeros(N)
            for f in freqs:
                metal += signal.square(2*np.pi*f*t)
            
            # Ring modulate with high freq
            metal *= signal.square(2*np.pi * 3500 * t)
            
            # Highpass mix
            b, a = signal.butter(1, 2000, 'high', fs=self.sample_rate)
            metal = signal.lfilter(b, a, metal)
            
            # Add white noise highpass
            noise = np.random.randn(N)
            b2, a2 = signal.butter(1, 4000, 'high', fs=self.sample_rate)
            noise = signal.lfilter(b2, a2, noise)
            
            out = metal * 0.4 + noise * 0.6
            env = np.exp(-t * 2.5) # Long decay
            return out * env

        if wf == 'cymbal_ride':
            # Higher pitch, pingier
            t = np.arange(N) / self.sample_rate
            # FM Bell-ish core
            car = 2500
            mod = 3200
            fm = np.sin(2*np.pi*mod*t) * 1000 * np.exp(-t*10)
            tone = np.sin(2*np.pi*car*t + fm)
            
            # Metallic noise layer
            noise = np.random.uniform(-1,1,N)
            b, a = signal.butter(1, 6000, 'high', fs=self.sample_rate)
            noise = signal.lfilter(b, a, noise)
            
            out = tone * 0.5 + noise * 0.5
            env = np.exp(-t * 8.0)
            return out * env

        if wf == 'tom':
            # Pitch sweep resonant sine usually
            t = np.arange(N) / self.sample_rate
            start_f = freq * 1.5
            end_f = freq * 0.8
            f_inst = end_f + (start_f - end_f) * np.exp(-t * 15.0)
            ph = 2*np.pi*np.cumsum(f_inst)/self.sample_rate
            tone = np.sin(ph)
            # Add saturation
            tone = np.tanh(tone * 2.0)
            env = np.exp(-t * 5.0)
            return tone * env

        if wf == 'rimshot':
            # High Q filter ring
            t = np.arange(N) / self.sample_rate
            impulse = np.zeros(N)
            impulse[0:10] = 1.0 # Short click
            
            # Ringing bandpass
            f_ring = 1800
            b, a = signal.butter(2, [f_ring-50, f_ring+50], 'band', fs=self.sample_rate)
            ring = signal.lfilter(b, a, impulse) # impulse response of filter is ring
            
            # Add body
            body = np.sin(2*np.pi*400*t) * np.exp(-t*80)
            
            return ring*50.0 + body*0.5

        if wf == 'shaker':
            # Filtered noise bursts
            t = np.arange(N) / self.sample_rate
            white = np.random.uniform(-1, 1, N)
            b, a = signal.butter(1, 6000, 'high', fs=self.sample_rate)
            filt = signal.lfilter(b, a, white)
            env = np.exp(-t * 25.0)
            # Granular-ish texture?
            # AM mod
            mod = np.random.choice([0,1], N, p=[0.3, 0.7]) # subtle dropouts
            return filt * env * mod

        if wf == 'woodblock':
            # Hollow sine/square
            t = np.arange(N) / self.sample_rate
            f = freq if freq > 400 else 800
            tone = np.sin(2*np.pi*f*t) * 0.7 + signal.square(2*np.pi*f*t) * 0.3
            env = np.exp(-t * 40.0) # Fast decay
            return tone * env

        if wf == 'cowbell':
            # 808 cowbell is classic, let's do real cowbell (inharmonic metallic)
            t = np.arange(N) / self.sample_rate
            f = freq if freq > 300 else 580
            # Two tones, flat 5ht interval or similar
            t1 = np.square(2*np.pi*f*t) 
            t2 = np.square(2*np.pi*(f*1.45)*t)
            
            # Bandpass
            raw = t1 + t2
            b, a = signal.butter(2, [f, f*2.5], 'band', fs=self.sample_rate)
            out = signal.lfilter(b, a, raw)
            env = np.exp(-t * 10.0)
            return out * env
            
        # --- FX / Glitch ---
        if wf == 'zap':
            # Log sweep
            t = np.arange(N) / self.sample_rate
            f_start = 2000
            f_end = 50
            f_inst = f_end * (f_start/f_end)**(1 - t*10) # fast sweep?
            # clamp
            f_inst = np.clip(f_inst, 50, 2000)
            ph = 2*np.pi*np.cumsum(f_inst)/self.sample_rate
            return np.sin(ph)

        if wf == 'scratch':
            # Filtered noise with pitch modulation to simulate varying playback speed
            t = np.arange(N) / self.sample_rate
            # Random walk speed
            speed = 1.0 + np.sin(2*np.pi*5*t) * 0.5 + np.sin(2*np.pi*1.3*t)*0.5
            # Noise source
            noise = np.random.uniform(-1, 1, N)
            # Re-sample noise? Too complex.
            # AM modulation of filtered noise
            b, a = signal.butter(2, [800, 1600], 'band', fs=self.sample_rate)
            filt = signal.lfilter(b, a, noise)
            
            # Apply 'speed' as pitch shifting via resampling approximation?
            # Or just filter sweep
            b2, a2 = signal.butter(2, 1000, 'low', fs=self.sample_rate)
            # Let's do AM scrub
            scrub = np.clip(speed, 0, 1) # simple gating
            return filt * scrub

        if wf == 'impact':
            # Cinematic boom
            t = np.arange(N) / self.sample_rate
            # Sub sine
            sweep = 60 * np.exp(-t*2)
            sub = np.sin(2*np.pi*np.cumsum(sweep)/self.sample_rate)
            # Noise blast
            noise = np.random.randn(N) * np.exp(-t*5)
            # Distortion
            out = np.tanh(sub + noise * 0.5)
            # Lowpass
            b, a = signal.butter(1, 200, 'low', fs=self.sample_rate)
            return signal.lfilter(b, a, out)

        # --- Tonal ---
        if wf == 'bass_slap':
            # FM Bright
            t = np.arange(N) / self.sample_rate
            f = freq
            # Modulator 2 octaves up
            mod_f = f * 4.0
            mod_env = np.exp(-t * 20.0)
            fm = np.sin(2*np.pi*mod_f*t) * mod_env * 5.0
            
            car = np.sin(2*np.pi*f*t + fm)
            # Add pluck transient
            pluck = (np.random.rand(N)-0.5) * np.exp(-t*100)
            
            return car + pluck*0.5

        if wf == 'piano_electric':
            # FM Rhodes approx
            t = np.arange(N) / self.sample_rate
            # 1:1 ratio for body, 1:14 for tine
            mod1 = np.sin(2*np.pi*freq*t) * np.exp(-t*2.0) # body mod
            mod2 = np.sin(2*np.pi*(freq*14.0)*t) * np.exp(-t*15.0) * 0.1 # tine
            
            car = np.sin(2*np.pi*freq*t + mod1 + mod2)
            return car

        if wf == 'drone_dark':
            # Low rumble + slow moog drift
            t = np.arange(N) / self.sample_rate
            # 3 detuned saws
            s1 = signal.sawtooth(2*np.pi*freq*t)
            s2 = signal.sawtooth(2*np.pi*(freq*1.01)*t)
            s3 = signal.sawtooth(2*np.pi*(freq*0.99)*t)
            raw = (s1+s2+s3)/3.0
            
            # Lowpass
            b, a = signal.butter(1, freq*4, 'low', fs=self.sample_rate)
            dark = signal.lfilter(b, a, raw)
            return dark

        # ----- Noise types -----
        if wf == 'noise_white':
            return np.random.uniform(-1, 1, N)

        if wf == 'noise_pink':
            w = np.random.randn(N)
            b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
            a = [1.0, -2.494956002, 2.017265875, -0.522189400]
            out = signal.lfilter(b, a, w)
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        if wf == 'noise_brown':
            w = np.random.randn(N)
            out = np.cumsum(w)
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        if wf == 'noise_blue':
            # Differentiated white noise
            w = np.random.randn(N)
            out = np.diff(w, prepend=0)
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        if wf == 'noise_purple':
            # Double-differentiated white noise
            w = np.random.randn(N)
            d1 = np.diff(w, prepend=0)
            out = np.diff(d1, prepend=0)
            mx = np.max(np.abs(out))
            return out / mx if mx > 0 else out

        # Fallback
        return np.sin(phase)

    # ------------------------------------------------------------------
    # Sample Playback
    # ------------------------------------------------------------------
    def _gen_sample(self, N):
        """Play back the loaded sample_data, trimming or zero-padding to N."""
        if self.sample_data is None:
            return np.zeros(N)

        data = np.array(self.sample_data, dtype=np.float64)

        # Convert stereo to mono if needed
        if data.ndim == 2:
            data = data.mean(axis=1)

        # Trim or pad
        if len(data) >= N:
            return data[:N]
        else:
            out = np.zeros(N)
            out[:len(data)] = data
            return out

