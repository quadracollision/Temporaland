"""
FiggyGenSynth – The core synth engine.
Orchestrates oscillators, effects, envelopes, and stereo processing.
"""
import numpy as np
from .oscillator import Oscillator
from .modulation import Envelope, LFO
from .routing import RenderGraph, EFFECT_DISPATCH


class FiggyGenSynth:
    """The FiggyGen – multi-oscillator synth with a configurable FX chain."""

    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.graph = RenderGraph(sample_rate)
        # self.oscillators: list[Oscillator] = [] # Deprecated
        # self.effects_chain: list[dict] = [] # Deprecated
        self.envelope = Envelope()
        # LFO modulation sources
        self.pitch_lfo = None   # modulates oscillator pitch (FM)
        self.filter_lfo = None  # modulates filter cutoff
        self.amp_lfo = None     # modulates amplitude (tremolo)
        self.macro_lfo = None   # Master LFO for macro modulation
        self.macro_routes = []  # List of (fx_type, param, amount)

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def add_oscillator(self, bus='main', **kwargs):
        """Create and add an Oscillator.  Accepts any Oscillator.__init__ kwarg."""
        # Clean up kwargs just in case
        if 'bus' in kwargs: del kwargs['bus']
        
        # Check for 'sample_rate' in kwargs to avoid duplication or override
        if 'sample_rate' not in kwargs:
             kwargs['sample_rate'] = self.sample_rate

        self.graph.add_oscillator(bus, **kwargs)

    def clear_oscillators(self):
        self.graph.clear()

    def configure_lfos(self, pitch_lfo=None, filter_lfo=None, amp_lfo=None):
        """Set LFO modulation sources. Each is an LFO instance or None."""
        self.pitch_lfo = pitch_lfo
        self.filter_lfo = filter_lfo
        self.amp_lfo = amp_lfo
        for lfo in (pitch_lfo, filter_lfo, amp_lfo):
            if lfo is not None:
                lfo.set_sample_rate(self.sample_rate)

    def configure_macro(self, macro_lfo=None, routes=None):
        """Configure Macro LFO and routing."""
        self.macro_lfo = macro_lfo
        self.macro_routes = routes if routes else []
        if self.macro_lfo:
            self.macro_lfo.set_sample_rate(self.sample_rate)

    def set_effects(self, chain: list[dict], bus='main'):
        """Set effects for a specific bus."""
        self.graph.set_effects(bus, chain)

    def set_bus_properties(self, bus='main', mute=False, solo=False):
        """Set mute and solo states for a specific bus."""
        if bus in self.graph.buses:
            self.graph.buses[bus].mute = mute
            self.graph.buses[bus].solo = solo

    # ------------------------------------------------------------------
    # Render pipeline
    # ------------------------------------------------------------------
    def render(self, duration: float, frequencies=None) -> np.ndarray:
        """
        Render audio using the RenderGraph.
        """
        if frequencies is None:
            frequencies = [440.0]
        elif np.isscalar(frequencies):
            frequencies = [frequencies]
            
        # Graph render handles all mixing and effects
        audio = self.graph.render(duration, frequencies, 
                                  envelope=self.envelope.get_envelope(int(duration * self.sample_rate)))

        # --- ADVANCE LFO PHASES ---
        # Advance all LFOs by the duration of this note
        N = int(duration * self.sample_rate)
        if self.pitch_lfo: self.pitch_lfo.advance_phase(N)
        if self.filter_lfo: self.filter_lfo.advance_phase(N)
        if self.amp_lfo: self.amp_lfo.advance_phase(N)
        if self.macro_lfo: self.macro_lfo.advance_phase(N)

        return audio

