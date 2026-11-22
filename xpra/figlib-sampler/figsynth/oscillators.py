"""Oscillator-stack data helpers and lightweight waveform previews."""

import tkinter as tk

import numpy as np
from pySynth.oscillator import Oscillator

from .waveform import draw_audio_shape


def default_oscillator(waveform="sine"):
    return {
        "waveform": waveform,
        "detune": 0.0,
        "phase": 0.0,
        "pulse_width": 0.5,
        "morph_pos": 0.0,
        "gain": 0.8,
        "unison": 1,
        "unison_detune": 0.0,
        "unison_spread": 0.0,
        "fm_ratio": 1.0,
        "fm_depth": 0.0,
    }


def sample_oscillator(path=None):
    config = default_oscillator("sample")
    config["sample_name"] = path or "Loaded sample"
    return config


def remove_oscillator_config(patch, index):
    """Remove exactly one source and return it, without regenerating a patch."""
    oscillators = patch.get("oscillators", []) if patch else []
    if not isinstance(index, int) or not 0 <= index < len(oscillators):
        return None
    return oscillators.pop(index)


def oscillator_preview_data(config, sample=None, points=220):
    """Return normalized mono display data without running a full synth render."""
    points = max(8, int(points))
    waveform = config.get("waveform", "sine")
    if waveform == "sample":
        audio = np.asarray(sample if sample is not None else [], dtype=np.float64)
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
    else:
        try:
            allowed = {
                "waveform", "detune", "phase", "pulse_width", "morph_pos",
                "gain", "unison", "unison_detune", "unison_spread",
                "fm_ratio", "fm_depth", "harmonics",
            }
            settings = {key: value for key, value in config.items() if key in allowed}
            oscillator = Oscillator(frequency=220.0, **settings)
            oscillator.set_sample_rate(44100)
            # This is a shape thumbnail, not an audio render. A short window is
            # enough to show phase, pulse width, morph, FM and unison changes and
            # keeps continuous knob dragging responsive over the shared desktop.
            audio = np.asarray(oscillator.generate(0.02), dtype=np.float64)
            if audio.ndim == 2:
                audio = audio.mean(axis=1)
        except Exception:
            phase = np.linspace(0.0, 4.0 * np.pi, points, endpoint=False)
            audio = np.sin(phase)
    if not len(audio):
        return np.zeros(points, dtype=np.float64)
    indices = np.linspace(0, len(audio) - 1, points).astype(np.int64)
    display = np.nan_to_num(audio[indices])
    peak = float(np.max(np.abs(display)))
    return display / peak if peak > 1e-9 else display


class OscillatorForm(tk.Canvas):
    """Small selected-source waveform view designed to stay cheap over noVNC."""

    def __init__(self, master):
        super().__init__(master, height=125, bg="#111318", highlightthickness=1,
                         highlightbackground="#666")
        self._config = None
        self._sample = None
        self.bind("<Configure>", lambda _event: self._draw())

    def show(self, config, sample=None):
        self._config = dict(config)
        self._sample = sample
        self._draw()

    def _draw(self):
        self.delete("all")
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.create_line(0, height / 2, width, height / 2, fill="#343b46")
        if not self._config:
            return
        # Keep several samples per screen column so the shared min/max renderer
        # produces the same filled waveform silhouette as the Instrument tab.
        values = oscillator_preview_data(self._config, self._sample, points=240)
        draw_audio_shape(self, values, width, height, max_columns=220)
        self.create_text(8, 8, anchor="nw",
                         text=self._config.get("waveform", "sine").replace("_", " "),
                         fill="#d6dbe3", font=("Sans", 10, "bold"))
