import numpy as np
from scipy import signal

class DAHDSR:
    def __init__(self, delay=0.0, attack=0.01, hold=0.0, decay=0.1, sustain_level=0.7, release=0.1):
        """
        DAHDSR Envelope Generator.
        Times are in seconds. Levels are 0.0 to 1.0.
        """
        self.delay = delay
        self.attack = attack
        self.hold = hold
        self.decay = decay
        self.sustain_level = sustain_level
        self.release = release
        self.sample_rate = 44100

    def get_envelope(self, duration_samples):
        """
        Generate envelope array for the given total duration (in samples).
        If the total duration is longer than D+A+H+D+R, the Sustain phase is extended.
        If shorter, phases are truncated (this determines priority).
        """
        total_samples = duration_samples
        envelope = np.zeros(total_samples)
        
        # Convert times to samples
        d_samples = int(self.delay * self.sample_rate)
        a_samples = int(self.attack * self.sample_rate)
        h_samples = int(self.hold * self.sample_rate)
        dc_samples = int(self.decay * self.sample_rate)
        r_samples = int(self.release * self.sample_rate)
        
        current_idx = 0
        
        # Delay
        if current_idx + d_samples > total_samples: d_samples = total_samples - current_idx
        # envelope[...] is already 0
        current_idx += d_samples
        if current_idx >= total_samples: return envelope
        
        # Attack (0 -> 1)
        if current_idx + a_samples > total_samples: a_samples = total_samples - current_idx
        envelope[current_idx:current_idx+a_samples] = np.linspace(0.0, 1.0, a_samples)
        current_idx += a_samples
        if current_idx >= total_samples: return envelope
        
        # Hold (1)
        if current_idx + h_samples > total_samples: h_samples = total_samples - current_idx
        envelope[current_idx:current_idx+h_samples] = 1.0
        current_idx += h_samples
        if current_idx >= total_samples: return envelope
        
        # Decay (1 -> S)
        if current_idx + dc_samples > total_samples: dc_samples = total_samples - current_idx
        envelope[current_idx:current_idx+dc_samples] = np.linspace(1.0, self.sustain_level, dc_samples)
        current_idx += dc_samples
        if current_idx >= total_samples: return envelope
        
        # Sustain (S)
        # Calculate remaining samples for release
        sustain_samples = total_samples - current_idx - r_samples
        if sustain_samples < 0:
            # Not enough time for full release, shorten sustain to 0 or whatever fits?
            # Actually if sustain_samples < 0, it means we are already chewing into release time.
            # Let's just fill until total_samples - r_samples
            sustain_samples = 0
            # If we simply don't have space for release, we might just finish decay and go straight to release?
            # Let's say Sustain fills the gap.
            
        if sustain_samples > 0:
            envelope[current_idx:current_idx+sustain_samples] = self.sustain_level
            current_idx += sustain_samples
        
        # Release (S -> 0)
        remaining = total_samples - current_idx
        if remaining > 0:
            # We start from whatever level we are at (should be Sustain level usually)
            start_val = self.sustain_level
            # But if we skipped phases, we might be at 1.0 or 0.0. 
            # For simplicity, assume we are at sustain level if we reached here.
            # If we are strictly implementing DAHDSR for a fixed duration container:
            envelope[current_idx:] = np.linspace(start_val, 0.0, remaining)
            
        return envelope

class LFO:
    SHAPES = ['sine', 'square', 'saw', 'triangle', 'noise',
              'sample_hold', 'random_walk', 'exp_rise', 'exp_fall']

    def __init__(self, waveform='sine', rate=1.0, amount=1.0, phase=0.0,
                 bipolar=True):
        self.waveform = waveform
        self.rate = rate
        self.amount = amount
        self.phase = phase
        self.bipolar = bipolar
        self.sample_rate = 44100

    def set_sample_rate(self, sr):
        self.sample_rate = sr

    def get_lfo(self, duration_samples):
        t = np.arange(duration_samples) / self.sample_rate
        phase_in = 2 * np.pi * self.rate * t + self.phase

        wf = self.waveform
        if wf == 'sine':
            output = np.sin(phase_in)
        elif wf == 'square':
            output = signal.square(phase_in)
        elif wf == 'saw':
            output = signal.sawtooth(phase_in)
        elif wf == 'triangle':
            output = signal.sawtooth(phase_in, width=0.5)
        elif wf == 'noise':
            output = np.random.uniform(-1, 1, duration_samples)
        elif wf == 'sample_hold':
            # Stepped random values at LFO rate
            cycle_len = max(1, int(self.sample_rate / max(0.01, self.rate)))
            num_steps = (duration_samples // cycle_len) + 2
            values = np.random.uniform(-1, 1, num_steps)
            output = np.repeat(values, cycle_len)[:duration_samples]
        elif wf == 'random_walk':
            # Smooth drunk-walk modulation
            steps = np.random.randn(duration_samples) * 0.01
            output = np.cumsum(steps)
            # Constrain to -1..1
            output = np.tanh(output)
        elif wf == 'exp_rise':
            # Exponential rise per LFO cycle
            cycle = np.linspace(0, 1, max(1, int(self.sample_rate / max(0.01, self.rate))))
            exp_cycle = np.exp(cycle * 3) / np.exp(3) * 2 - 1
            reps = (duration_samples // len(exp_cycle)) + 2
            output = np.tile(exp_cycle, reps)[:duration_samples]
        elif wf == 'exp_fall':
            cycle = np.linspace(0, 1, max(1, int(self.sample_rate / max(0.01, self.rate))))
            exp_cycle = 1 - np.exp(cycle * 3) / np.exp(3)
            exp_cycle = exp_cycle * 2 - 1
            reps = (duration_samples // len(exp_cycle)) + 2
            output = np.tile(exp_cycle, reps)[:duration_samples]
        else:
            output = np.sin(phase_in)

        if not self.bipolar:
            output = (output + 1.0) * 0.5  # 0..1 range

        return output * self.amount

    def advance_phase(self, duration_samples):
        """Advance the LFO phase by the given number of samples."""
        # Calculate phase increment
        # phase = 2 * pi * rate * t
        # delta_phase = 2 * pi * rate * (duration_samples / sample_rate)
        delta = 2 * np.pi * self.rate * (duration_samples / self.sample_rate)
        self.phase += delta
        # Keep phase within reasonable bounds to prevent float precision issues
        self.phase %= (2 * np.pi)


class ModMatrix:
    def __init__(self):
        self.routes = [] # List of (source, dest_param_name, amount)
        
    def add_route(self, source, dest_name, amount):
        self.routes.append((source, dest_name, amount))
        
    def apply(self, params, duration_samples):
        # This is tricky because params might be scalar or arrays.
        # "source" should be an object with .get_values(duration)
        pass

# Convenience alias
Envelope = DAHDSR

