"""
FiggyGen Routing Engine.
Manages Audio Buses and the Render Graph for parallel processing.
"""
import numpy as np
from .oscillator import Oscillator
import inspect

# Effects imports
from .effects.filters import apply_filter, apply_eq12, apply_comb, apply_formant
from .effects.delays import apply_delay
from .effects.reverb import apply_reverb
from .effects.modulations import (apply_chorus, apply_flanger, apply_phaser,
                                   apply_tremolo, apply_vibrato, apply_autopan)
from .effects.distortions import apply_distortion, apply_bitcrush
from .effects.dynamics import apply_compressor, apply_limiter
from .effects.analog import apply_tube_saturation, apply_tape, apply_exciter
from .effects.spectral import apply_ring_mod, apply_freq_shift, apply_stereo_widen
from .effects.creative import (apply_wavefolder, apply_resonator, apply_lofi,
                                apply_stutter, apply_sub_bass, apply_gate,
                                apply_transient_shaper, apply_ensemble,
                                apply_dc_remove, apply_pitch_shift, apply_sidechain,
                                apply_reverse, apply_tape_stop, apply_vinyl,
                                apply_radio, apply_telephone, apply_underwater,
                                apply_shimmer, apply_glitch, apply_haas,
                                apply_harmonizer, apply_octaver, apply_doppler,
                                apply_crystal, apply_fade, apply_dimension,
                                apply_granular, apply_spectral_freeze,
                                apply_maximizer, apply_stereo_imager,
                                apply_multiband_comp, apply_harmonic_enhance,
                                apply_granular_stretch, apply_parallel_comp,
                                apply_body, apply_width_enhance,
                                apply_warmth, apply_spatial)
from .effects.hardware import (apply_moog_ladder, apply_303_filter,
                                apply_sem_filter, apply_ms20_filter,
                                apply_space_echo, apply_fairchild,
                                apply_ssl_comp, apply_neve_preamp,
                                apply_emt_plate, apply_spring_reverb,
                                apply_marshall_amp, apply_ce1_chorus,
                                apply_small_stone, apply_lexicon_224,
                                apply_dbx160, apply_prophet_filter,
                                apply_juno_hpf, apply_arp_ring_mod,
                                apply_h3000, apply_vox_ac30,
                                apply_fender_twin, apply_re301_chorus,
                                apply_studer_tape, apply_la2a,
                                apply_pultec_eq, apply_buchla_lpg,
                                apply_dimension_d, apply_obxa_filter,
                                apply_wasp_filter, apply_ams_reverb,
                                apply_tc2290, apply_1176)


# Map effect name -> function
EFFECT_DISPATCH = {
    # Filters
    'filter':       apply_filter,
    'eq12':         apply_eq12,
    'comb':         apply_comb,
    'formant':      apply_formant,
    # Delays / Space
    'delay':        apply_delay,
    'reverb':       apply_reverb,
    # Modulation FX
    'chorus':       apply_chorus,
    'flanger':      apply_flanger,
    'phaser':       apply_phaser,
    'tremolo':      apply_tremolo,
    'vibrato':      apply_vibrato,
    'autopan':      apply_autopan,
    # Distortion
    'distortion':   apply_distortion,
    'bitcrush':     apply_bitcrush,
    # Dynamics
    'compressor':   apply_compressor,
    'limiter':      apply_limiter,
    # Analog
    'tube':         apply_tube_saturation,
    'tape':         apply_tape,
    'exciter':      apply_exciter,
    # Spectral
    'ring_mod':     apply_ring_mod,
    'freq_shift':   apply_freq_shift,
    'stereo_widen': apply_stereo_widen,
    # Creative
    'wavefolder':   apply_wavefolder,
    'resonator':    apply_resonator,
    'lofi':         apply_lofi,
    'stutter':      apply_stutter,
    'sub_bass':     apply_sub_bass,
    'gate':         apply_gate,
    'transient':    apply_transient_shaper,
    'ensemble':     apply_ensemble,
    'dc_remove':    apply_dc_remove,
    'pitch_shift':  apply_pitch_shift,
    'sidechain':    apply_sidechain,
    'reverse':      apply_reverse,
    'tape_stop':    apply_tape_stop,
    'vinyl':        apply_vinyl,
    'radio':        apply_radio,
    'telephone':    apply_telephone,
    'underwater':   apply_underwater,
    'shimmer':      apply_shimmer,
    'glitch':       apply_glitch,
    'haas':         apply_haas,
    'harmonizer':   apply_harmonizer,
    'octaver':      apply_octaver,
    'doppler':      apply_doppler,
    'crystal':      apply_crystal,
    'fade':         apply_fade,
    'dimension':    apply_dimension,
    # Hardware Emulations
    'moog':         apply_moog_ladder,
    '303':          apply_303_filter,
    'sem':          apply_sem_filter,
    'ms20':         apply_ms20_filter,
    'space_echo':   apply_space_echo,
    'fairchild':    apply_fairchild,
    'ssl':          apply_ssl_comp,
    'neve':         apply_neve_preamp,
    'emt_plate':    apply_emt_plate,
    'spring':       apply_spring_reverb,
    'marshall':     apply_marshall_amp,
    'ce1':          apply_ce1_chorus,
    'small_stone':  apply_small_stone,
    'lexicon':      apply_lexicon_224,
    'dbx160':       apply_dbx160,
    'prophet':      apply_prophet_filter,
    'juno_hpf':     apply_juno_hpf,
    'arp_ring':     apply_arp_ring_mod,
    'h3000':        apply_h3000,
    'vox':          apply_vox_ac30,
    'fender_twin':  apply_fender_twin,
    're301':        apply_re301_chorus,
    'studer':       apply_studer_tape,
    'la2a':         apply_la2a,
    'pultec':       apply_pultec_eq,
    'buchla_lpg':   apply_buchla_lpg,
    'dimension_d':  apply_dimension_d,
    'obxa':         apply_obxa_filter,
    'wasp':         apply_wasp_filter,
    'ams_reverb':   apply_ams_reverb,
    'tc2290':       apply_tc2290,
    '1176':         apply_1176,
    # Sonic Power
    'granular':     apply_granular,
    'spectral_freeze': apply_spectral_freeze,
    'maximizer':    apply_maximizer,
    'stereo_imager': apply_stereo_imager,
    'multiband':    apply_multiband_comp,
    'harmonic_enhance': apply_harmonic_enhance,
    'granular_stretch': apply_granular_stretch,
    'parallel_comp': apply_parallel_comp,
    'body':         apply_body,
    'width_enhance': apply_width_enhance,
    'warmth':       apply_warmth,
    'spatial':      apply_spatial,
}


class AudioBus:
    """
    A single audio path (buffer) with its own oscillators and effects.
    """
    def __init__(self, bus_id, sample_rate=44100):
        self.id = bus_id
        self.sample_rate = sample_rate
        self.oscillators: list[Oscillator] = []
        self.effects_chain: list[dict] = []
        self.gain = 1.0
        self.pan = 0.0 # -1.0 to 1.0
        self.mute = False
        self.solo = False

    def add_oscillator(self, **kwargs):
        """Add an oscillator to this bus."""
        osc = Oscillator(**kwargs)
        osc.set_sample_rate(self.sample_rate)
        self.oscillators.append(osc)

    def set_effects(self, chain: list[dict]):
        """Set the effects chain for this bus."""
        self.effects_chain = chain

    def render(self, duration, frequencies, envelope=None, lfos=None) -> np.ndarray:
        """
        Render this bus's audio buffer in isolation.
        """
        N = int(duration * self.sample_rate)
        buffer = np.zeros((N, 2))
        
        if self.mute:
            return buffer

        # 1. Render Oscillators
        # Initialize buffer with silence
        buffer = np.zeros((N, 2))
        
        if not self.oscillators:
            return buffer

        # Temporary mix buffer for oscillators before FX
        osc_mix = np.zeros((N, 2))
        
        for freq in frequencies:
            for osc in self.oscillators:
                osc.frequency = freq
                
                # Render Oscillator
                raw = osc.generate(duration)
                
                # Stereo handling
                if raw.ndim == 1:
                    stereo = np.column_stack((raw, raw))
                else:
                    stereo = raw
                
                # Resize to match buffer
                if len(stereo) > N: 
                    stereo = stereo[:N]
                elif len(stereo) < N: 
                    pad = np.zeros((N - len(stereo), 2))
                    stereo = np.vstack((stereo, pad))
                    
                osc_mix += stereo

        # Normalize oscillator sum
        num_voices = max(1, len(self.oscillators) * len(frequencies))
        osc_mix /= np.sqrt(num_voices)
        
        # 2. Apply Envelope (Global for now, TODO: Per-Bus Envelopes)
        if envelope is not None:
             # Ensure envelope shape matches
             env_view = envelope
             if len(env_view) > N: env_view = env_view[:N]
             elif len(env_view) < N: env_view = np.pad(env_view, (0, N - len(env_view)))
             osc_mix *= env_view[:, np.newaxis]

        # 3. Apply Effects
        audio = osc_mix
        for fx in self.effects_chain:
            fx_type = fx.get('type', '')
            params = dict(fx.get('params', {}))
            params['sample_rate'] = self.sample_rate
            
            func = EFFECT_DISPATCH.get(fx_type)
            if func:
                try:
                    # Filter params based on function signature
                    sig = inspect.signature(func)
                    valid_params = {k: v for k, v in params.items() if k in sig.parameters}
                    
                    # Special check for **kwargs
                    has_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
                    if has_kwargs:
                        valid_params = params

                    processed = func(audio, **valid_params)
                    if processed is not None:
                        audio = processed
                    else:
                        print(f"[FiggyGen] Warning: Effect '{fx_type}' returned None. Skipping.")
                except Exception as e:
                    print(f"[FiggyGen] Error applying effect '{fx_type}': {e}")
        
        # 4. Apply Bus Gain/Pan
        audio *= self.gain
        
        # Simple Pan (Constant Power)
        # Pan -1.0 (Left) to 1.0 (Right)
        if self.pan != 0.0:
            p = np.clip(self.pan, -1.0, 1.0)
            left_gain = np.cos((p + 1) * np.pi / 4)
            right_gain = np.sin((p + 1) * np.pi / 4)
            audio[:, 0] *= left_gain
            audio[:, 1] *= right_gain
            
        return np.clip(audio, -1.0, 1.0)


class RenderGraph:
    """
    Manages multiple AudioBuses and sums them to a master output.
    """
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.buses = {} # id -> AudioBus
        self.master_bus_id = 'main'
        # Always create master bus
        self.get_bus(self.master_bus_id)
            
    def get_bus(self, bus_id):
        """Get or create a bus."""
        if bus_id not in self.buses:
            self.buses[bus_id] = AudioBus(bus_id, self.sample_rate)
        return self.buses[bus_id]

    def add_oscillator(self, bus_id, **kwargs):
        """Add an oscillator to a specific bus."""
        bus = self.get_bus(bus_id)
        bus.add_oscillator(**kwargs)

    def set_effects(self, bus_id, chain):
        """Set effects for a specific bus."""
        bus = self.get_bus(bus_id)
        bus.set_effects(chain)
        
    def clear(self):
        """Reset the graph."""
        self.buses.clear()
        self.get_bus(self.master_bus_id)

    def render(self, duration, frequencies, envelope=None, lfos=None) -> np.ndarray:
        """
        Render all buses and sum them.
        """
        N = int(duration * self.sample_rate)
        master_mix = np.zeros((N, 2))
        
        # Check Solo state
        solo_active = any(b.solo for b in self.buses.values())
        
        active_buses = [b for b in self.buses.values() if not b.mute]
        if solo_active:
            active_buses = [b for b in active_buses if b.solo]
            
        for bus in active_buses:
            # Render Bus
            bus_out = bus.render(duration, frequencies, envelope)
            
            # Sum into Master
            # Expand to match usage if needed, but bus.render returns (N, 2)
            if len(bus_out) < N:
                pad = np.zeros((N - len(bus_out), 2))
                bus_out = np.vstack((bus_out, pad))
            elif len(bus_out) > N:
                bus_out = bus_out[:N]
                
            master_mix += bus_out
            
        # Final Clip
        return np.clip(master_mix, -1.0, 1.0)

