#!/usr/bin/env python3
"""FigSynth2: an easy instrument front-end for the complete FigLib engine."""
import inspect
import json
import math
import os
import random
import copy
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
FIGLIB_ROOT = os.path.join(HERE, "figlib52")
sys.path.insert(0, os.path.join(FIGLIB_ROOT, "src"))

import numpy as np
import soundfile as sf
from pySynth.generator import Randomizer
from pySynth.modulation import Envelope
from pySynth.oscillator import Oscillator
from pySynth.routing import EFFECT_DISPATCH
from pySynth.synth import FiggyGenSynth

RATE = 44100
IMPORTS = os.environ.get("TEMPORAMAN_IMPORTS", "/srv/audacity-studio/imports")
EXPORTS = os.environ.get("TEMPORAMAN_EXPORTS", "/srv/audacity-studio/exports")
PULSE_SINK = os.environ.get("PULSE_SINK", "studio")
KEY_NOTES = {
    "z": 48, "s": 49, "x": 50, "d": 51, "c": 52, "v": 53, "g": 54,
    "b": 55, "h": 56, "n": 57, "j": 58, "m": 59, ",": 60,
    "q": 60, "2": 61, "w": 62, "3": 63, "e": 64, "r": 65, "5": 66,
    "t": 67, "6": 68, "y": 69, "7": 70, "u": 71, "i": 72,
}
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
CHORDS = {
    "Major": (0, 4, 7),
    "Minor": (0, 3, 7),
    "Major 6": (0, 4, 7, 9),
    "Minor 6": (0, 3, 7, 9),
    "6/9": (0, 4, 7, 9, 14),
    "Major 7": (0, 4, 7, 11),
    "Minor 7": (0, 3, 7, 10),
    "Minor major 7": (0, 3, 7, 11),
    "Dominant 7": (0, 4, 7, 10),
    "Major 9": (0, 4, 7, 11, 14),
    "Diminished": (0, 3, 6),
    "Diminished 7": (0, 3, 6, 9),
    "Half-diminished 7": (0, 3, 6, 10),
    "Augmented": (0, 4, 8),
    "Augmented 7": (0, 4, 8, 10),
    "Sus 2": (0, 2, 7),
    "Sus 4": (0, 5, 7),
    "7 sus 4": (0, 5, 7, 10),
    "Power": (0, 7, 12),
    "Add 9": (0, 4, 7, 14),
    "Minor add 9": (0, 3, 7, 14),
    "Minor 9": (0, 3, 7, 10, 14),
    "Dominant 9": (0, 4, 7, 10, 14),
    "Major 11": (0, 4, 7, 11, 14, 17),
    "Minor 11": (0, 3, 7, 10, 14, 17),
    "Dominant 11": (0, 4, 7, 10, 14, 17),
    "Major 13": (0, 4, 7, 11, 14, 21),
    "Minor 13": (0, 3, 7, 10, 14, 21),
    "Dominant 13": (0, 4, 7, 10, 14, 21),
    "Quartal": (0, 5, 10, 15),
    "Quintal": (0, 7, 14, 21),
}


def note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def notes_label(notes):
    return " + ".join(note_name(int(round(n))) for n in notes)


def numeric_defaults(func):
    values = {}
    for p in inspect.signature(func).parameters.values():
        if p.name in ("audio", "sample_rate", "kwargs") or p.default is inspect.Parameter.empty:
            continue
        values[p.name] = p.default
    return values


def parameter_range(name, default):
    """Useful macro ranges for FigLib's heterogeneous numeric parameters."""
    key = name.lower()
    if key in ("cutoff", "freq", "frequency", "high_freq", "low_freq"):
        return (20.0, 20000.0, "log")
    if "threshold" in key or key in ("ceiling",):
        return (-60.0, 0.0, "linear")
    if "semitone" in key or "interval" in key or "detune" in key:
        return (-24.0, 24.0, "linear")
    if "ratio" in key:
        return (1.0, 20.0, "linear")
    if any(word in key for word in ("mix", "depth", "feedback", "amount", "resonance",
                                     "sustain", "warmth", "width", "drive", "gain",
                                     "tone", "presence", "bias", "position", "height",
                                     "density", "spray", "strike", "crackle", "hiss")):
        return (0.0, 1.0, "linear")
    if any(word in key for word in ("time", "decay", "release", "attack", "delay")):
        high = max(1.0, float(default) * 4.0) if isinstance(default, (int, float)) else 5.0
        return (0.0, min(10.0, high), "linear")
    if isinstance(default, (int, float)):
        high = max(1.0, abs(float(default)) * 2.0)
        low = -high if float(default) < 0 else 0.0
        return (low, high, "linear")
    return (0.0, 1.0, "linear")


def macro_to_parameter(value, limits):
    low, high, scale = limits
    if scale == "log":
        return low * ((high / low) ** value)
    return low + (high - low) * value


def parameter_to_macro(value, limits):
    low, high, scale = limits
    value = max(low, min(high, float(value)))
    if scale == "log":
        return math.log(value / low) / math.log(high / low)
    return (value - low) / max(1e-12, high - low)


ENUM_OPTIONS = {
    ("ams_reverb", "program"): ("nonlin", "ambience", "plate"),
    ("buchla_lpg", "mode"): ("filter", "vca", "both"),
    ("distortion", "dist_type"): (
        "tanh", "hard_clip", "soft_clip", "sine_fold",
        "rectify", "half_rectify", "waveshape"),
    ("filter", "filter_type"): (
        "lowpass", "highpass", "bandpass", "notch",
        "peaking", "low_shelf", "high_shelf", "allpass"),
    ("formant", "vowel"): ("a", "e", "i", "o", "u"),
    ("haas", "side"): ("left", "right"),
    ("la2a", "mode"): ("compress", "limit"),
    ("obxa", "mode"): ("lowpass", "bandpass", "highpass"),
    ("sem", "mode"): ("lowpass", "highpass", "bandpass", "notch"),
}

INTEGER_BOUNDS = {
    "bit_depth": (2, 16), "sample_rate_reduction": (1, 16),
    "voices": (1, 8), "stages": (1, 12), "repeats": (1, 16),
    "mode": (0, 4), "speed": (0, 2), "ratio": (1, 20),
}


def parameter_control_spec(name, default):
    key = name.lower()
    if isinstance(default, bool):
        return {"kind": "bool"}
    if not isinstance(default, (int, float)):
        return {"kind": "text"}
    if isinstance(default, int) and key in INTEGER_BOUNDS:
        low, high = INTEGER_BOUNDS[key]
        return {"kind": "knob", "low": low, "high": high, "integer": True}
    bounded_words = (
        "mix", "depth", "feedback", "amount", "resonance", "sustain",
        "warmth", "width", "drive", "gain", "tone", "presence", "bias",
        "position", "height", "density", "spray", "strike", "crackle",
        "hiss", "cutoff", "freq", "threshold", "ceiling", "ratio",
        "time", "decay", "release", "attack", "delay", "semitone",
        "interval", "detune",
    )
    if any(word in key for word in bounded_words):
        low, high, scale = parameter_range(name, default)
        return {"kind": "knob", "low": low, "high": high,
                "scale": scale, "integer": isinstance(default, int)}
    step = 1.0 if isinstance(default, int) else max(.01, abs(float(default)) * .02)
    return {"kind": "encoder", "step": step, "integer": isinstance(default, int)}


class Knob(tk.Canvas):
    def __init__(self, master, label, low, high, value, command=None, fmt="{:.2f}",
                 endless=False, step=None, **kw):
        super().__init__(master, width=82, height=102, bg="#d7d7d7", highlightthickness=0, **kw)
        self.label, self.low, self.high = label, float(low), float(high)
        self.value, self.command, self.fmt = float(value), command, fmt
        self.endless = endless
        self.step = float(step) if step is not None else max(.01, (self.high - self.low) / 100)
        self._last_y = None
        self.bind("<Button-1>", self._start)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<MouseWheel>", self._wheel)
        self.draw()

    def get(self):
        return self.value

    def set(self, value, notify=False):
        value = float(value)
        self.value = value if self.endless else max(self.low, min(self.high, value))
        self.draw()
        if notify and self.command:
            self.command(self.value)

    def _start(self, event):
        self._last_y = event.y

    def _drag(self, event):
        if self._last_y is None:
            self._last_y = event.y
        amount = self.step if self.endless else (self.high - self.low) / 150.0
        self.set(self.value + (self._last_y - event.y) * amount, True)
        self._last_y = event.y

    def _wheel(self, event):
        amount = self.step if self.endless else (self.high - self.low) / 100.0
        self.set(self.value + (1 if event.delta > 0 else -1) * amount, True)

    def set_control(self, label, low, high, value, fmt="{:.2f}", endless=False, step=None):
        self.label = label
        self.low, self.high = float(low), float(high)
        self.fmt = fmt
        self.endless = endless
        self.step = float(step) if step is not None else max(.01, (self.high - self.low) / 100)
        self.set(value)

    def draw(self):
        self.delete("all")
        self.create_text(41, 9, text=self.label, font=("Sans", 9, "bold"))
        self.create_oval(13, 22, 69, 78, fill="#eeeeee", outline="#555", width=2)
        if self.endless:
            frac = (self.value / max(self.step * 20, 1e-9)) % 1.0
        else:
            frac = 0 if self.high == self.low else (self.value - self.low) / (self.high - self.low)
        angle = math.radians(225 - frac * 270)
        self.create_line(41, 50, 41 + 22 * math.cos(angle), 50 - 22 * math.sin(angle),
                         fill="#202020", width=3)
        try:
            shown = self.fmt.format(self.value)
        except Exception:
            shown = str(self.value)
        self.create_text(41, 91, text=shown, font=("Sans", 8))


class Waveform(tk.Canvas):
    def __init__(self, master, app):
        super().__init__(master, bg="#111318", height=185, highlightthickness=1,
                         highlightbackground="#666")
        self.app = app
        self.bind("<Configure>", lambda _e: self.draw())
        self.bind("<Button-1>", self._pick)
        self.bind("<B1-Motion>", self._move)
        self.dragging = None

    def _pick(self, event):
        w = max(1, self.winfo_width())
        x1, x2 = self.app.start * w, self.app.end * w
        self.dragging = "start" if abs(event.x - x1) < abs(event.x - x2) else "end"
        self._move(event)

    def _move(self, event):
        if not self.dragging:
            return
        value = max(0.0, min(1.0, event.x / max(1, self.winfo_width())))
        if self.dragging == "start":
            self.app.start = min(value, self.app.end - .005)
        else:
            self.app.end = max(value, self.app.start + .005)
        self.app.sync_trim_knobs()
        self.draw()
        self.app.schedule_waveform()

    def draw(self, data=None):
        self.delete("all")
        w, h = max(2, self.winfo_width()), max(2, self.winfo_height())
        audio = self.app.preview_data if data is None else data
        self.create_line(0, h / 2, w, h / 2, fill="#343b46")
        if audio is not None and len(audio):
            mono = audio.mean(axis=1) if audio.ndim == 2 else audio
            # One polygon is dramatically cheaper over X11/noVNC than creating
            # one Canvas line object for every screen pixel.
            columns = min(360, w, len(mono))
            step = max(1, len(mono) // columns)
            upper, lower = [], []
            for column in range(columns):
                chunk = mono[column * step:min(len(mono), (column + 1) * step)]
                if len(chunk):
                    lo = float(np.min(chunk))
                    hi = float(np.max(chunk))
                    x = column * (w - 1) / max(1, columns - 1)
                    upper.append((x, h / 2 - hi * (h * .43)))
                    lower.append((x, h / 2 - lo * (h * .43)))
            if len(upper) >= 2:
                polygon = upper + list(reversed(lower))
                flattened = [coordinate for point in polygon for coordinate in point]
                self.create_polygon(*flattened, fill="#245c38", outline="#71e38b", width=1)
        self._draw_modulation_guides(w, h)
        x1, x2 = self.app.start * w, self.app.end * w
        self.create_rectangle(0, 0, x1, h, fill="#07080a", stipple="gray50", outline="")
        self.create_rectangle(x2, 0, w, h, fill="#07080a", stipple="gray50", outline="")
        self.create_line(x1, 0, x1, h, fill="#ffca57", width=3)
        self.create_line(x2, 0, x2, h, fill="#ffca57", width=3)
        if audio is None:
            self.create_text(w / 2, h / 2, text="Load a sample or make a new sound",
                             fill="#aeb5c0", font=("Sans", 12))

    def _draw_modulation_guides(self, w, h):
        if not hasattr(self.app, "knobs") or not hasattr(self.app, "duration"):
            return
        try:
            duration = max(.01, float(self.app.duration.get()))
            attack = self.app.knobs["Attack"].get()
            decay = self.app.knobs["Decay"].get()
            sustain = self.app.knobs["Sustain"].get()
            release = self.app.knobs["Release"].get()
        except (KeyError, ValueError, tk.TclError):
            return

        release_start = max(attack + decay, duration - release)
        upper, lower = [], []
        for x in range(0, w + 1, 3):
            t = duration * x / max(1, w)
            if attack > 0 and t < attack:
                gain = t / attack
            elif decay > 0 and t < attack + decay:
                gain = 1.0 - (1.0 - sustain) * ((t - attack) / decay)
            elif release > 0 and t >= release_start:
                gain = sustain * max(0.0, (duration - t) / release)
            else:
                gain = sustain
            y = gain * h * .43
            upper.extend((x, h / 2 - y))
            lower.extend((x, h / 2 + y))
        if len(upper) >= 4:
            self.create_line(*upper, fill="#58c7ff", width=2, dash=(5, 3))
            self.create_line(*lower, fill="#58c7ff", width=2, dash=(5, 3))

        depth = self.app.knobs["LFO depth"].get()
        if depth > .001:
            rate = self.app.knobs["LFO rate"].get()
            points = []
            for x in range(0, w + 1, 3):
                t = duration * x / max(1, w)
                y = h / 2 - math.sin(2 * math.pi * rate * t) * depth * h * .16
                points.extend((x, y))
            self.create_line(*points, fill="#d985ff", width=1, dash=(3, 3))


class EffectRack(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg="#d7d7d7")
        self.app = app
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.refresh_catalog())
        left = tk.Frame(self, bg="#d7d7d7")
        left.pack(side="left", fill="y", padx=6, pady=6)
        tk.Label(left, text="All 91 FigLib effects", bg="#d7d7d7", font=("Sans", 10, "bold")).pack(anchor="w")
        tk.Entry(left, textvariable=self.search, width=24).pack(fill="x", pady=3)
        self.catalog = tk.Listbox(left, width=27, height=21, exportselection=False)
        self.catalog.pack(fill="both", expand=True)
        tk.Button(left, text="Add effect →", command=self.add, relief="raised").pack(fill="x", pady=4)

        middle = tk.Frame(self, bg="#d7d7d7")
        middle.pack(side="left", fill="y", padx=4, pady=6)
        tk.Label(middle, text="Effect rack (top to bottom)", bg="#d7d7d7",
                 font=("Sans", 10, "bold")).pack(anchor="w")
        self.chain = tk.Listbox(middle, width=30, height=21, exportselection=False)
        self.chain.pack(fill="both", expand=True, pady=3)
        self.chain.bind("<<ListboxSelect>>", lambda _e: self.show_params())
        row = tk.Frame(middle, bg="#d7d7d7")
        row.pack(fill="x")
        for text, cmd in (("↑", lambda: self.move(-1)), ("↓", lambda: self.move(1)),
                          ("Bypass", self.bypass), ("Remove", self.remove)):
            tk.Button(row, text=text, command=cmd).pack(side="left", expand=True, fill="x")

        right = tk.Frame(self, bg="#d7d7d7", width=360)
        right.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.param_title = tk.Label(right, text="Select an effect", bg="#d7d7d7",
                                    font=("Sans", 11, "bold"))
        self.param_title.pack(anchor="w")
        self.param_canvas = tk.Canvas(right, bg="#d7d7d7", highlightthickness=0)
        scroll = tk.Scrollbar(right, orient="vertical", command=self.param_canvas.yview)
        scroll.pack(side="right", fill="y")
        self.param_canvas.pack(side="left", fill="both", expand=True)
        self.param_canvas.configure(yscrollcommand=scroll.set)
        self.params = tk.Frame(self.param_canvas, bg="#d7d7d7")
        self.param_canvas.create_window((0, 0), window=self.params, anchor="nw")
        self.params.bind("<Configure>", lambda _e: self.param_canvas.configure(
            scrollregion=self.param_canvas.bbox("all")))
        self.refresh_catalog()

    def refresh_catalog(self):
        query = self.search.get().strip().lower()
        self.catalog.delete(0, "end")
        for name in sorted(EFFECT_DISPATCH):
            if query in name:
                self.catalog.insert("end", name)

    def refresh_chain(self, select=None):
        self.chain.delete(0, "end")
        for fx in self.app.effects:
            prefix = "  " if fx.get("enabled", True) else "× "
            self.chain.insert("end", prefix + fx["type"])
        if select is not None and self.app.effects:
            select = max(0, min(select, len(self.app.effects) - 1))
            self.chain.selection_set(select)
            self.chain.see(select)
        self.show_params()

    def selected(self):
        sel = self.chain.curselection()
        return sel[0] if sel else None

    def add(self):
        sel = self.catalog.curselection()
        if not sel:
            return
        name = self.catalog.get(sel[0])
        self.app.effects.append({"type": name, "params": numeric_defaults(EFFECT_DISPATCH[name]),
                                 "enabled": True})
        self.refresh_chain(len(self.app.effects) - 1)
        self.app.refresh_assignment_targets()
        self.app.schedule_waveform()
        self.app.schedule_macro_rebuild()

    def remove(self):
        i = self.selected()
        if i is not None:
            removed = self.app.effects.pop(i)
            self.app.unassign_effect(removed)
            self.refresh_chain(max(0, i - 1))
            self.app.refresh_assignment_targets()
            self.app.schedule_waveform()
            self.app.schedule_macro_rebuild()

    def bypass(self):
        i = self.selected()
        if i is not None:
            self.app.effects[i]["enabled"] = not self.app.effects[i].get("enabled", True)
            self.refresh_chain(i)
            self.app.schedule_waveform()
            self.app.schedule_macro_rebuild()

    def move(self, direction):
        i = self.selected()
        if i is None or not 0 <= i + direction < len(self.app.effects):
            return
        self.app.effects[i], self.app.effects[i + direction] = self.app.effects[i + direction], self.app.effects[i]
        self.refresh_chain(i + direction)
        self.app.schedule_waveform()
        self.app.schedule_macro_rebuild()

    def show_params(self):
        for child in self.params.winfo_children():
            child.destroy()
        i = self.selected()
        if i is None:
            self.param_title.configure(text="Select an effect")
            return
        fx = self.app.effects[i]
        self.param_title.configure(text=fx["type"].replace("_", " ").title())
        func = EFFECT_DISPATCH[fx["type"]]
        defaults = numeric_defaults(func)
        numeric_index = 0
        text_row = 20
        for name, default in defaults.items():
            value = fx["params"].get(name, default)
            enum_values = ENUM_OPTIONS.get((fx["type"], name))
            spec = parameter_control_spec(name, default)
            if enum_values:
                row = text_row
                text_row += 1
                tk.Label(self.params, text=name, width=18, anchor="e",
                         bg="#d7d7d7").grid(row=row, column=0, sticky="e", padx=4, pady=4)
                var = tk.StringVar(value=str(value))
                box = ttk.Combobox(self.params, textvariable=var, values=enum_values,
                                   state="readonly", width=16)
                box.grid(row=row, column=1, columnspan=2, sticky="w", padx=4, pady=4)
                box.bind("<<ComboboxSelected>>",
                         lambda _event, effect=fx, n=name, v=var:
                         self.app.effect_parameter_changed(effect, n, v.get()))
            elif spec["kind"] == "bool":
                row = text_row
                text_row += 1
                var = tk.BooleanVar(value=bool(value))
                tk.Checkbutton(
                    self.params, text=name, variable=var, bg="#d7d7d7",
                    command=lambda effect=fx, n=name, v=var:
                    self.app.effect_parameter_changed(effect, n, v.get())
                ).grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=4)
            elif spec["kind"] in ("knob", "encoder"):
                row, column = divmod(numeric_index, 3)
                numeric_index += 1
                endless = spec["kind"] == "encoder"
                low = spec.get("low", float(value) - 1.0)
                high = spec.get("high", float(value) + 1.0)
                fmt = "{:.0f}" if spec.get("integer") else "{:.3g}"
                control = Knob(
                    self.params, name, low, high, value, fmt=fmt,
                    endless=endless, step=spec.get("step"),
                    command=lambda new_value, effect=fx, n=name, meta=spec:
                    self.app.effect_parameter_changed(
                        effect, n, int(round(new_value)) if meta.get("integer") else new_value))
                control.grid(row=row, column=column, padx=4, pady=3)
            else:
                row = text_row
                text_row += 1
                tk.Label(self.params, text=name, width=18, anchor="e",
                         bg="#d7d7d7").grid(row=row, column=0, sticky="e", padx=4, pady=4)
                var = tk.StringVar(value=str(value))
                entry = tk.Entry(self.params, textvariable=var, width=18)
                entry.grid(row=row, column=1, columnspan=2, sticky="w", padx=4, pady=4)
                entry.bind("<Return>", lambda _event, effect=fx, n=name, v=var:
                           self.app.effect_parameter_changed(effect, n, v.get()))
        if not defaults:
            tk.Label(self.params, text="This effect has no adjustable parameters.",
                     bg="#d7d7d7").pack(anchor="w", pady=10)


class PianoRoll(tk.Frame):
    """A small sample sequencer whose cells retain complete sound snapshots."""

    STEPS = 16
    ROWS = 24

    def __init__(self, master, app):
        super().__init__(master, bg="#d7d7d7")
        self.app = app
        self.hits = {}
        self.low_note = tk.IntVar(value=48)
        self.bpm = tk.DoubleVar(value=120.0)
        self._serial = 0

        toolbar = tk.Frame(self, bg="#d7d7d7")
        toolbar.pack(fill="x", padx=8, pady=(7, 3))
        tk.Button(toolbar, text="Play pattern", command=app.play_pattern,
                  bg="#d8f2d8", font=("Sans", 10, "bold")).pack(side="left")
        tk.Button(toolbar, text="Stop", command=app.stop_audio).pack(side="left", padx=3)
        tk.Button(toolbar, text="Save pattern WAV…", command=app.export_pattern).pack(
            side="left", padx=(8, 3))
        tk.Button(toolbar, text="Clear pattern", command=self.clear).pack(side="left", padx=3)
        tk.Label(toolbar, text="BPM", bg="#d7d7d7").pack(side="left", padx=(18, 3))
        tk.Spinbox(toolbar, from_=30, to=300, increment=1, width=6,
                   textvariable=self.bpm).pack(side="left")
        tk.Label(toolbar, text="Lowest note", bg="#d7d7d7").pack(side="left", padx=(18, 3))
        low = tk.Spinbox(toolbar, from_=0, to=103, increment=1, width=5,
                         textvariable=self.low_note, command=self.draw)
        low.pack(side="left")
        low.bind("<Return>", lambda _event: self.draw())
        low.bind("<FocusOut>", lambda _event: self.draw())
        tk.Label(toolbar,
                 text="Left-click: place/remove current sound   •   Right-click: load hit back into sampler",
                 bg="#d7d7d7", fg="#444").pack(side="right", padx=8)

        self.canvas = tk.Canvas(self, bg="#22252b", highlightthickness=1,
                                highlightbackground="#555")
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.canvas.bind("<Configure>", lambda _event: self.draw())
        self.canvas.bind("<Button-1>", self.left_click)
        self.canvas.bind("<Button-3>", self.right_click)

    def geometry(self):
        width = max(300, self.canvas.winfo_width())
        height = max(240, self.canvas.winfo_height())
        return 58, 25, (width - 60) / self.STEPS, (height - 27) / self.ROWS

    def cell_at(self, event):
        left, top, cw, ch = self.geometry()
        step = int((event.x - left) // cw)
        row = int((event.y - top) // ch)
        if not (0 <= step < self.STEPS and 0 <= row < self.ROWS):
            return None
        low = max(0, min(103, int(self.low_note.get())))
        return step, low + self.ROWS - 1 - row

    def left_click(self, event):
        cell = self.cell_at(event)
        if cell is None:
            return
        if cell in self.hits:
            del self.hits[cell]
            self.app.status.set(f"Removed piano-roll hit at step {cell[0] + 1}.")
            self.draw()
            return
        self.app.place_piano_hit(*cell)

    def right_click(self, event):
        cell = self.cell_at(event)
        hit = self.hits.get(cell) if cell else None
        if hit:
            self.app.restore_piano_hit(hit)

    def add_hit(self, step, note, snapshot):
        palette = ("#e7a84a", "#5cb7d8", "#d672a8", "#78bf68",
                   "#9a83db", "#d77a64", "#65c4ae", "#c5b957")
        self._serial += 1
        hit = {
            "snapshot": snapshot, "audio": None, "pending": False,
            "color": palette[(self._serial - 1) % len(palette)],
            "label": snapshot["label"],
        }
        self.hits[(step, note)] = hit
        self.draw()
        return hit

    def clear(self):
        self.hits.clear()
        self.draw()
        self.app.status.set("Piano roll cleared.")

    def draw(self):
        if not hasattr(self, "canvas"):
            return
        c = self.canvas
        c.delete("all")
        left, top, cw, ch = self.geometry()
        low = max(0, min(103, int(self.low_note.get())))
        black = {1, 3, 6, 8, 10}
        for row in range(self.ROWS):
            note = low + self.ROWS - 1 - row
            y0, y1 = top + row * ch, top + (row + 1) * ch
            fill = "#292d34" if note % 12 in black else "#343942"
            c.create_rectangle(left, y0, left + self.STEPS * cw, y1,
                               fill=fill, outline="")
            c.create_text(left - 5, (y0 + y1) / 2, text=note_name(note),
                          anchor="e", fill="#e2e2e2", font=("Sans", 8))
        for step in range(self.STEPS + 1):
            x = left + step * cw
            c.create_line(x, top, x, top + self.ROWS * ch,
                          fill="#858b95" if step % 4 == 0 else "#50555d",
                          width=2 if step % 4 == 0 else 1)
            if step < self.STEPS:
                c.create_text(x + cw / 2, 12, text=str(step + 1),
                              fill="#eeeeee", font=("Sans", 8, "bold"))
        for row in range(self.ROWS + 1):
            y = top + row * ch
            c.create_line(left, y, left + self.STEPS * cw, y, fill="#454a52")
        for (step, note), hit in self.hits.items():
            row = low + self.ROWS - 1 - note
            if not 0 <= row < self.ROWS:
                continue
            x0, y0 = left + step * cw + 2, top + row * ch + 2
            x1, y1 = left + (step + 1) * cw - 2, top + (row + 1) * ch - 2
            fill = hit["color"]
            c.create_rectangle(x0, y0, x1, y1, fill=fill,
                               outline="#fff3ba", width=1)
            if cw > 45 and ch > 13:
                label = hit["label"]
                c.create_text((x0 + x1) / 2, (y0 + y1) / 2,
                              text=label[:10], fill="#111", font=("Sans", 7, "bold"))


class App:
    def __init__(self, root):
        self.root = root
        root.title("FigSynth2")
        root.geometry("1180x720")
        root.minsize(1050, 650)
        root.configure(bg="#d7d7d7")
        self.sample = None
        self.sample_rate = RATE
        self.sample_path = None
        self.live_source = None
        self.live_effect_source = None
        self.live_loop_start = 0
        self._live_dry_buffer = None
        self.preview_data = None
        self.start, self.end = 0.0, 1.0
        self.patch = None
        self.effects = []
        self.control_assignments = {}
        self.assignment_targets = {}
        self.knob_specs = {}
        self.default_snapshot = None
        self.piano_roll = None
        self._piano_audio_cache = {}
        self._pattern_busy = False
        self._osc_after = None
        self.macro_assignments = [None, None, None, None]
        self.macro_knobs = []
        self.macro_labels = []
        self._macro_after = None
        self._macro_generation = 0
        self._macro_busy = False
        self._macro_pending = False
        self._live_refresh_after = None
        self._live_refresh_generation = 0
        self._live_refresh_busy = False
        self._live_refresh_pending = False
        self._stream_lock = threading.Lock()
        self._stream_process = None
        self._stream_buffer = None
        self._stream_position = 0
        self._stream_token = 0
        self._live_wet_cache = {}
        self._export_busy = False
        self.randomizer = Randomizer(os.path.join(FIGLIB_ROOT, "presets"),
                                     os.path.join(FIGLIB_ROOT, "fxpresets"))
        self.mode = tk.StringVar(value="synth")
        self.genre = tk.StringVar(value="keys")
        self.loop = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Ready. Make a sound or load a WAV.")
        self.current_note = 60
        self.current_notes = [60]
        self.chord_type = tk.StringVar(value="Major")
        self.play_mode = tk.StringVar(value="Note")
        self.keyboard_choice = tk.StringVar(value="Single note")
        self.custom_notes = set()
        self.shape_root = None
        self.shape_notes = set()
        self.octave = tk.IntVar(value=4)
        self.range_shift = 0
        self._players = []
        self._wave_after = None
        self._wave_exact_after = None
        self._wave_generation = 0
        self._wave_quick_busy = False
        self._wave_quick_pending = False
        self._build()
        self.new_sound()
        root.bind("<KeyPress>", self.key_press)
        # Fit the shared desktop's usable area so labels cannot spill over an
        # edge or sit on top of a neighboring application.
        root.after(250, self._fit_desktop)

    def _fit_desktop(self):
        try:
            self.root.attributes("-zoomed", True)
        except tk.TclError:
            width = max(1050, self.root.winfo_screenwidth())
            height = max(650, self.root.winfo_screenheight() - 42)
            self.root.geometry(f"{width}x{height}+0+0")

    def _build(self):
        top = tk.Frame(self.root, bg="#c6c6c6", bd=2, relief="raised")
        top.pack(fill="x")
        tk.Label(top, text="FIGSYNTH2", bg="#c6c6c6",
                 font=("Sans", 14, "bold")).pack(side="left", padx=8, pady=6)
        tk.Button(top, text="Reset defaults", command=self.reset_defaults).pack(side="left", padx=3)
        genres = sorted(self.randomizer.genres)
        genre_box = ttk.Combobox(top, textvariable=self.genre, values=genres,
                                 state="readonly", width=12)
        genre_box.pack(side="left", padx=3)
        genre_box.bind("<<ComboboxSelected>>", lambda _event: self.new_sound())
        tk.Button(top, text="Load sample…", command=self.load_sample).pack(side="left", padx=3)
        self.save_button = tk.Button(top, text="Export audio", command=self.export,
                                     font=("Sans", 10, "bold"), bg="#d8f2d8")
        self.save_button.pack(side="left", padx=10)

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=6, pady=(5, 0))
        main = tk.Frame(self.tabs, bg="#d7d7d7")
        fx = tk.Frame(self.tabs, bg="#d7d7d7")
        oscillators = tk.Frame(self.tabs, bg="#d7d7d7")
        self.tabs.add(main, text=" Instrument ")
        self.tabs.add(fx, text=" Effects ")
        self.tabs.add(oscillators, text=" Oscillators ")

        wave_box = tk.LabelFrame(main, text="Sound", bg="#d7d7d7", padx=5, pady=5)
        wave_box.pack(fill="x", padx=6, pady=5)
        self.source_label = tk.Label(wave_box, text="", bg="#d7d7d7", anchor="w")
        self.source_label.pack(fill="x")
        self.wave = Waveform(wave_box, self)
        self.wave.pack(fill="x", expand=True)

        knob_box = tk.Frame(main, bg="#d7d7d7", bd=1, relief="groove")
        knob_box.pack(fill="x", padx=6, pady=4)
        specs = [
            ("Pitch", -24, 24, 0, "{:+.0f} st"),
            ("Start", 0, 100, 0, "{:.0f}%"),
            ("End", 0, 100, 100, "{:.0f}%"),
            ("Attack", 0, 2, .01, "{:.2f}s"),
            ("Decay", 0, 2, .1, "{:.2f}s"),
            ("Sustain", 0, 1, .8, "{:.2f}"),
            ("Release", 0, 3, .15, "{:.2f}s"),
            ("Cutoff", 80, 18000, 18000, "{:.0f}Hz"),
            ("Resonance", 0, 1, .1, "{:.2f}"),
            ("LFO rate", .05, 20, 3, "{:.2f}Hz"),
            ("LFO depth", 0, 1, 0, "{:.2f}"),
            ("Volume", 0, 1.25, .8, "{:.2f}"),
        ]
        self.knobs = {}
        for label, low, high, value, fmt in specs:
            self.knob_specs[label] = {
                "label": label, "low": low, "high": high,
                "value": value, "fmt": fmt,
            }
            cmd = lambda _value, name=label: self.knob_changed(name)
            knob = Knob(knob_box, label, low, high, value, command=cmd, fmt=fmt)
            knob.bind("<Button-3>",
                      lambda event, name=label: self.show_knob_assignment_menu(event, name))
            knob.pack(side="left", expand=True, fill="x", padx=1, pady=2)
            self.knobs[label] = knob

        options = tk.Frame(main, bg="#d7d7d7")
        options.pack(fill="x", padx=10, pady=2)
        tk.Checkbutton(options, text="Loop sample", variable=self.loop, bg="#d7d7d7").pack(side="left")
        tk.Label(options, text="Length", bg="#d7d7d7").pack(side="left", padx=(12, 2))
        self.duration = tk.DoubleVar(value=2.0)
        tk.Spinbox(options, from_=.1, to=12, increment=.1, textvariable=self.duration,
                   width=6).pack(side="left")
        tk.Label(options, text="seconds", bg="#d7d7d7").pack(side="left")
        tk.Label(options, text="LFO →", bg="#d7d7d7").pack(side="left", padx=(15, 2))
        self.lfo_target = tk.StringVar(value="pitch")
        ttk.Combobox(options, textvariable=self.lfo_target,
                     values=("pitch", "volume", "filter"), state="readonly", width=8).pack(side="left")
        chordbar = tk.Frame(main, bg="#d7d7d7")
        chordbar.pack(fill="x", padx=10, pady=2)
        tk.Label(chordbar, text="Keyboard", bg="#d7d7d7").pack(side="left")
        keyboard_box = ttk.Combobox(
            chordbar, textvariable=self.keyboard_choice,
            values=("Single note", *(f"Chord — {name}" for name in CHORDS), "Custom chord"),
            state="readonly", width=24)
        keyboard_box.pack(side="left", padx=(3, 14))
        keyboard_box.bind("<<ComboboxSelected>>", lambda _event: self.keyboard_choice_changed())
        tk.Label(chordbar, text="Octave", bg="#d7d7d7").pack(side="left")
        octave_spin = tk.Spinbox(chordbar, from_=0, to=8, width=3, textvariable=self.octave,
                                 command=self.change_octave)
        octave_spin.pack(side="left", padx=(3, 14))
        octave_spin.bind("<Return>", lambda _event: self.change_octave())
        octave_spin.bind("<FocusOut>", lambda _event: self.change_octave())
        tk.Label(chordbar, text="Range", bg="#d7d7d7").pack(side="left")
        tk.Button(chordbar, text="−1", width=3,
                  command=lambda: self.shift_keyboard(-1)).pack(side="left", padx=(3, 1))
        tk.Button(chordbar, text="+1", width=3,
                  command=lambda: self.shift_keyboard(1)).pack(side="left", padx=(1, 14))
        self.clear_custom_button = tk.Button(chordbar, text="Clear custom notes",
                                             command=self.clear_custom_notes)
        self.clear_custom_button.pack(side="left", padx=(14, 4))
        self.chord_help = tk.Label(chordbar, text="",
                                   bg="#d7d7d7", fg="#555")
        self.chord_help.pack(side="left", padx=6)

        keys = tk.LabelFrame(main, text="Play (computer keys: Z row / Q row)", bg="#d7d7d7")
        keys.pack(fill="both", expand=True, padx=6, pady=5)
        self._keyboard(keys)

        self.rack = EffectRack(fx, self)
        self.rack.pack(fill="both", expand=True)
        presetbar = tk.Frame(fx, bg="#d7d7d7")
        presetbar.pack(side="bottom", fill="x", padx=8, pady=6)
        tk.Label(presetbar, text="FX presets:", bg="#d7d7d7").pack(side="left")
        self.fx_preset = tk.StringVar(value="tape_warmth")
        fx_recipe_box = ttk.Combobox(presetbar, textvariable=self.fx_preset,
                                     values=sorted(self.randomizer.fx_presets),
                                     state="readonly", width=20)
        fx_recipe_box.pack(side="left", padx=4)
        fx_recipe_box.bind("<<ComboboxSelected>>",
                           lambda _event: self.apply_fx_preset())
        tk.Button(presetbar, text="Apply", command=self.apply_fx_preset).pack(side="left")
        tk.Button(presetbar, text="Clear rack", command=self.clear_fx).pack(side="left", padx=4)

        self._build_oscillator_tab(oscillators)

        status = tk.Label(self.root, textvariable=self.status, anchor="w",
                          bg="#242730", fg="white", padx=7, pady=4)
        status.pack(side="bottom", fill="x")
        self.duration.trace_add("write", self.schedule_waveform)
        self.loop.trace_add("write", self.schedule_waveform)
        self.lfo_target.trace_add("write", self.schedule_waveform)
        self.mode_changed()

    def _build_oscillator_tab(self, parent):
        left = tk.Frame(parent, bg="#d7d7d7")
        left.pack(side="left", fill="y", padx=8, pady=8)
        tk.Label(left, text="Oscillator stack", bg="#d7d7d7",
                 font=("Sans", 11, "bold")).pack(anchor="w")
        self.osc_list = tk.Listbox(left, width=28, height=20, exportselection=False)
        self.osc_list.pack(fill="both", expand=True, pady=4)
        self.osc_list.bind("<<ListboxSelect>>", lambda _event: self.show_oscillator())
        buttons = tk.Frame(left, bg="#d7d7d7")
        buttons.pack(fill="x")
        tk.Button(buttons, text="Add", command=self.add_oscillator).pack(
            side="left", expand=True, fill="x")
        tk.Button(buttons, text="Duplicate", command=self.duplicate_oscillator).pack(
            side="left", expand=True, fill="x")
        tk.Button(buttons, text="Remove", command=self.remove_oscillator).pack(
            side="left", expand=True, fill="x")
        self.osc_editor = tk.Frame(parent, bg="#d7d7d7")
        self.osc_editor.pack(side="left", fill="both", expand=True, padx=8, pady=8)

    def refresh_oscillator_list(self, select=0):
        if not hasattr(self, "osc_list"):
            return
        self.osc_list.delete(0, "end")
        oscillators = self.patch.get("oscillators", []) if self.patch else []
        for index, config in enumerate(oscillators):
            self.osc_list.insert(
                "end", f"{index + 1}. {config.get('waveform', 'sine')}  "
                f"gain {config.get('gain', 1.0):.2f}")
        if oscillators:
            select = max(0, min(select, len(oscillators) - 1))
            self.osc_list.selection_set(select)
            self.show_oscillator()
        else:
            for child in self.osc_editor.winfo_children():
                child.destroy()
            tk.Label(self.osc_editor, text="Add an oscillator to begin.",
                     bg="#d7d7d7").pack(anchor="nw")

    def selected_oscillator(self):
        selection = self.osc_list.curselection()
        if not selection or not self.patch:
            return None, None
        index = selection[0]
        oscillators = self.patch.get("oscillators", [])
        return (index, oscillators[index]) if index < len(oscillators) else (None, None)

    def show_oscillator(self):
        for child in self.osc_editor.winfo_children():
            child.destroy()
        index, config = self.selected_oscillator()
        if config is None:
            return
        tk.Label(self.osc_editor, text=f"Oscillator {index + 1}",
                 bg="#d7d7d7", font=("Sans", 12, "bold")).grid(
                     row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        tk.Label(self.osc_editor, text="Waveform", bg="#d7d7d7").grid(
            row=1, column=0, sticky="e", padx=5)
        waveform = tk.StringVar(value=config.get("waveform", "sine"))
        waveforms = tuple(w for w in Oscillator.WAVEFORMS if w != "sample")
        box = ttk.Combobox(self.osc_editor, textvariable=waveform,
                           values=waveforms, state="readonly", width=18)
        box.grid(row=1, column=1, sticky="w", padx=5)
        box.bind("<<ComboboxSelected>>",
                 lambda _event, c=config, v=waveform:
                 self.set_oscillator_parameter(c, "waveform", v.get()))

        specs = (
            ("gain", 0.0, 1.5, False, .01),
            ("detune", -100.0, 100.0, False, .1),
            ("phase", 0.0, 1.0, False, .01),
            ("pulse_width", .01, .99, False, .01),
            ("morph_pos", 0.0, 1.0, False, .01),
            ("unison", 1, 8, True, 1),
            ("unison_detune", 0.0, 50.0, False, .1),
            ("unison_spread", 0.0, 1.0, False, .01),
            ("fm_ratio", .1, 10.0, False, .05),
            ("fm_depth", 0.0, 10.0, False, .05),
        )
        for item, (name, low, high, integer, step) in enumerate(specs):
            row, column = divmod(item, 4)
            value = config.get(name, 1 if name in ("gain", "unison", "fm_ratio") else
                               .5 if name == "pulse_width" else 0)
            knob = Knob(
                self.osc_editor, {
                    "pulse_width": "pulse width",
                    "morph_pos": "morph",
                    "unison_detune": "uni detune",
                    "unison_spread": "uni spread",
                    "fm_ratio": "FM ratio",
                    "fm_depth": "FM depth",
                }.get(name, name), low, high, value,
                fmt="{:.0f}" if integer else "{:.3g}", step=step,
                command=lambda new_value, c=config, n=name, is_int=integer:
                self.set_oscillator_parameter(
                    c, n, int(round(new_value)) if is_int else new_value))
            knob.grid(row=row + 2, column=column, padx=5, pady=4)

    def set_oscillator_parameter(self, config, name, value):
        config[name] = value
        self.oscillator_changed()

    def oscillator_changed(self):
        self._live_dry_buffer = None
        if self._osc_after is not None:
            try:
                self.root.after_cancel(self._osc_after)
            except tk.TclError:
                pass
        self._osc_after = self.root.after(250, self._refresh_oscillator_preview)

    def _refresh_oscillator_preview(self):
        self._osc_after = None
        self.refresh_oscillator_list(
            self.osc_list.curselection()[0] if self.osc_list.curselection() else 0)
        threading.Thread(target=self._update_synth_preview, daemon=True).start()

    def add_oscillator(self):
        if not self.patch:
            self.blank_synth()
        config = {
            "waveform": "sine", "detune": 0.0, "phase": 0.0,
            "pulse_width": .5, "morph_pos": 0.0, "gain": .8,
            "unison": 1, "unison_detune": 0.0, "unison_spread": 0.0,
            "fm_ratio": 1.0, "fm_depth": 0.0,
        }
        self.patch.setdefault("oscillators", []).append(config)
        self.refresh_oscillator_list(len(self.patch["oscillators"]) - 1)
        self.oscillator_changed()

    def duplicate_oscillator(self):
        index, config = self.selected_oscillator()
        if config is None:
            return
        self.patch["oscillators"].insert(index + 1, copy.deepcopy(config))
        self.refresh_oscillator_list(index + 1)
        self.oscillator_changed()

    def remove_oscillator(self):
        index, config = self.selected_oscillator()
        if config is None:
            return
        self.patch["oscillators"].pop(index)
        self.refresh_oscillator_list(max(0, index - 1))
        self.oscillator_changed()

    def blank_synth(self):
        self.clear_macro_assignments()
        self.patch = {
            "genre": "custom",
            "oscillators": [],
            "effects": [],
            "envelope": {"attack": .01, "hold": 0.0, "decay": .1,
                         "sustain_level": .8, "release": .15},
            "lfos": {"pitch": None, "filter": None, "amp": None},
        }
        self.effects = []
        self.mode.set("synth")
        self.sample = None
        self.rack.refresh_chain()
        self.refresh_assignment_targets()
        self.add_oscillator()
        self.default_snapshot = {
            "patch": copy.deepcopy(self.patch),
            "effects": copy.deepcopy(self.effects),
        }
        self.source_label.configure(text="Custom synth")
        self.status.set("Blank custom synth created.")

    def reset_defaults(self):
        self.clear_macro_assignments()
        for name in self.knobs:
            self._restore_main_knob(name)
        self.patch = {
            "genre": "custom",
            "oscillators": [{
                "waveform": "triangle", "detune": 0.0, "phase": 0.0,
                "pulse_width": .5, "morph_pos": 0.0, "gain": .8,
                "unison": 1, "unison_detune": 0.0, "unison_spread": 0.0,
                "fm_ratio": 1.0, "fm_depth": 0.0,
            }],
            "effects": [],
            "envelope": {"attack": .01, "hold": 0.0, "decay": .1,
                         "sustain_level": .8, "release": .15},
            "lfos": {"pitch": None, "filter": None, "amp": None},
        }
        self.effects = []
        self.mode.set("synth")
        self.sample = None
        self.sample_path = None
        self.sample_rate = RATE
        self.start, self.end = 0.0, 1.0
        self.duration.set(2.0)
        self.loop.set(False)
        self.lfo_target.set("pitch")
        self.keyboard_choice.set("Single note")
        self.play_mode.set("Note")
        self.chord_type.set("Major")
        self.custom_notes.clear()
        self.shape_root = None
        self.shape_notes.clear()
        self.octave.set(4)
        self.range_shift = 0
        self.current_note = 60
        self.current_notes = [60]
        self.live_source = None
        self.live_effect_source = None
        self.default_snapshot = {
            "patch": copy.deepcopy(self.patch),
            "effects": [],
        }
        self.rack.refresh_chain()
        self.refresh_assignment_targets()
        self.refresh_oscillator_list()
        self.mode_changed()
        self.source_label.configure(text="triangle")
        self._live_dry_buffer = None
        self._live_wet_cache.clear()
        self.status.set("Factory defaults: one triangle oscillator, no FX, Single note mode.")
        self.schedule_live_refresh()
        threading.Thread(target=self._update_synth_preview, daemon=True).start()

    def _keyboard(self, parent):
        self.keyboard_frame = tk.Frame(parent, bg="#777", height=105)
        self.keyboard_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.redraw_keyboard()

    def redraw_keyboard(self):
        frame = self.keyboard_frame
        for child in frame.winfo_children():
            child.destroy()
        black = {1, 3, 6, 8, 10}
        first = self.keyboard_first()
        notes = range(first, first + 25)
        white_notes = [n for n in notes if n % 12 not in black]
        for i, midi in enumerate(white_notes):
            custom_selected = self.play_mode.get() == "Custom chord" and midi in self.custom_notes
            shape_selected = self.play_mode.get() == "Chord shape" and midi in self.shape_notes
            shape_root = self.play_mode.get() == "Chord shape" and midi == self.shape_root
            color = "#ffca57" if shape_root else "#9fe3aa" if shape_selected else "#9fd4ff" if custom_selected else "white"
            b = tk.Button(frame, text=note_name(midi),
                          bg=color,
                          activebackground="#d8f2d8",
                          command=lambda n=midi: self.trigger_key(n))
            b.place(relx=i / len(white_notes), rely=0, relwidth=1 / len(white_notes), relheight=1)
        for midi in notes:
            if midi % 12 in black:
                previous_whites = len([n for n in white_notes if n < midi])
                x = previous_whites / len(white_notes) - .3 / len(white_notes)
                custom_selected = self.play_mode.get() == "Custom chord" and midi in self.custom_notes
                shape_selected = self.play_mode.get() == "Chord shape" and midi in self.shape_notes
                shape_root = self.play_mode.get() == "Chord shape" and midi == self.shape_root
                color = "#ffca57" if shape_root else "#3d9955" if shape_selected else "#2c78c4" if custom_selected else "#202020"
                b = tk.Button(frame, text=NOTE_NAMES[midi % 12],
                              fg="#111" if shape_root else "white",
                              bg=color,
                              activebackground="#4b6a50",
                              command=lambda n=midi: self.trigger_key(n))
                b.place(relx=x, rely=0, relwidth=.6 / len(white_notes), relheight=.62)

    def mode_changed(self):
        mode = self.play_mode.get()
        if mode == "Note":
            text = ""
            self.clear_custom_button.configure(state="disabled")
        elif mode == "Chord shape":
            text = "" if self.shape_root is None else self.shape_description()
            self.clear_custom_button.configure(state="disabled")
        else:
            text = ""
            self.clear_custom_button.configure(state="normal")
        self.chord_help.configure(text=text)
        self.redraw_keyboard()

    def keyboard_choice_changed(self):
        choice = self.keyboard_choice.get()
        if choice == "Single note":
            self.play_mode.set("Note")
        elif choice == "Custom chord":
            self.play_mode.set("Custom chord")
        else:
            shape = choice.removeprefix("Chord — ")
            if shape not in CHORDS:
                return
            self.play_mode.set("Chord shape")
            self.chord_type.set(shape)
            self.chord_shape_changed()
        self.mode_changed()

    def chord_shape_changed(self):
        if self.shape_root is None:
            return
        self.shape_notes = {self.shape_root + interval for interval in CHORDS[self.chord_type.get()]}
        self.current_notes = sorted(self.shape_notes)
        self.redraw_keyboard()
        self.chord_help.configure(text=self.shape_description())
        self.schedule_waveform()

    def shape_description(self):
        if self.shape_root is None:
            return ""
        first = self.keyboard_first()
        outside = sum(note < first or note > first + 24 for note in self.shape_notes)
        suffix = f"  (+{outside} outside view)" if outside else ""
        return f"{self.chord_type.get()} at {note_name(self.shape_root)}{suffix}"

    def clear_custom_notes(self):
        self.custom_notes.clear()
        self.current_notes = [self.current_note]
        self.redraw_keyboard()
        self.status.set("Custom chord cleared. Click any notes you want.")

    def trigger_key(self, midi):
        mode = self.play_mode.get()
        self.current_note = midi
        if mode == "Note":
            notes = [midi]
        elif mode == "Chord shape":
            notes = [midi + interval for interval in CHORDS[self.chord_type.get()]]
            self.shape_root = midi
            self.shape_notes = set(notes)
            self.redraw_keyboard()
            self.chord_help.configure(text=self.shape_description())
        else:
            if midi in self.custom_notes:
                self.custom_notes.remove(midi)
            else:
                self.custom_notes.add(midi)
            self.redraw_keyboard()
            if not self.custom_notes:
                self.current_notes = [midi]
                self.status.set("Custom chord is empty. Click notes to add them.")
                return
            notes = sorted(self.custom_notes)
        self.play(notes)

    def change_octave(self):
        octave = max(0, min(8, int(self.octave.get())))
        self.octave.set(octave)
        self.range_shift = max(-octave * 12, min(103 - octave * 12, self.range_shift))
        self.current_note = (octave + 1) * 12 + self.current_note % 12
        self.current_notes = [self.current_note]
        if self.shape_root is not None:
            self.shape_root = (octave + 1) * 12 + self.shape_root % 12
            self.shape_notes = {self.shape_root + interval for interval in CHORDS[self.chord_type.get()]}
            self.current_notes = sorted(self.shape_notes)
        self.redraw_keyboard()
        if self.play_mode.get() == "Chord shape":
            self.chord_help.configure(text=self.shape_description())
        self.status.set(f"Keyboard octave {octave}; chord root is {note_name(self.current_note)}.")

    def keyboard_first(self):
        return max(0, min(103, self.octave.get() * 12 + self.range_shift))

    def shift_keyboard(self, semitones):
        base = self.octave.get() * 12
        self.range_shift = max(-base, min(103 - base, self.range_shift + semitones))
        self.redraw_keyboard()
        if self.play_mode.get() == "Chord shape":
            self.chord_help.configure(text=self.shape_description())
        first = self.keyboard_first()
        self.status.set(
            f"Keyboard range {note_name(first)}–{note_name(first + 24)} "
            f"({self.range_shift:+d} semitone offset).")

    def key_press(self, event):
        if isinstance(event.widget, (tk.Entry, tk.Spinbox, ttk.Combobox)):
            return
        key = event.keysym.lower()
        if key in KEY_NOTES:
            first = self.keyboard_first()
            self.trigger_key(first + KEY_NOTES[key] - 48)

    def knob_changed(self, name):
        assignment = self.control_assignments.get(name)
        if assignment:
            value = self.knobs[name].get()
            if assignment.get("integer"):
                value = int(round(value))
            assignment["effect"].setdefault("params", {})[assignment["parameter"]] = value
            self.status.set(
                f"{name} → {assignment['effect']['type']}.{assignment['parameter']} = {value:.4g}")
            self.schedule_macro_rebuild()
            self.schedule_waveform()
            return
        if name in ("Start", "End"):
            requested_start = self.knobs["Start"].get() / 100
            requested_end = self.knobs["End"].get() / 100
            self.start = max(0.0, min(requested_start, requested_end - .005))
            self.end = min(1.0, max(requested_end, self.start + .005))
            self.sync_trim_knobs()
            with self._stream_lock:
                self._stream_position = 0
        # Move visual guides synchronously with the knob. Audio follows through
        # the quick/exact render pipeline below.
        self.wave.draw()
        self.schedule_waveform()
        self.schedule_live_refresh()

    def schedule_live_refresh(self):
        """Make the default Shape knobs audible in the active preview."""
        self._live_refresh_generation += 1
        self._live_wet_cache.clear()
        if self._live_refresh_busy:
            self._live_refresh_pending = True
            return
        if self._live_refresh_after is None:
            self._live_refresh_after = self.root.after(45, self._start_live_refresh)

    def _start_live_refresh(self):
        self._live_refresh_after = None
        with self._stream_lock:
            process = self._stream_process
        if not process or process.poll() is not None:
            return
        if self._live_refresh_busy:
            self._live_refresh_pending = True
            return
        self._live_refresh_busy = True
        generation = self._live_refresh_generation
        notes = list(self.current_notes)
        threading.Thread(target=self._live_refresh_worker,
                         args=(generation, notes), daemon=True).start()

    def _live_refresh_worker(self, generation, notes):
        audio = None
        error = None
        try:
            dry = self.render(notes, preview=True, live=True)
            audio = self._process_realtime_effects(dry)
        except Exception as exc:
            error = exc
        self.root.after(0, lambda: self._finish_live_refresh(generation, dry if audio is not None else None,
                                                             audio, error))

    def _finish_live_refresh(self, generation, dry, audio, error):
        self._live_refresh_busy = False
        if error is not None:
            self.status.set(f"Live knob update failed: {error}")
        elif generation == self._live_refresh_generation and audio is not None:
            self._live_dry_buffer = dry
            self._replace_stream_buffer(audio)
        if self._live_refresh_pending or generation != self._live_refresh_generation:
            self._live_refresh_pending = False
            if self._live_refresh_after is None:
                self._live_refresh_after = self.root.after(35, self._start_live_refresh)

    def refresh_assignment_targets(self):
        targets = {"Default": None}
        for effect_index, effect in enumerate(self.effects, 1):
            func = EFFECT_DISPATCH.get(effect["type"])
            if not func:
                continue
            for parameter, default in numeric_defaults(func).items():
                if isinstance(default, (int, float)) and not isinstance(default, bool):
                    label = f"{effect_index}:{effect['type']}.{parameter}"
                    targets[label] = (effect, parameter, default)
        self.assignment_targets = targets
        if hasattr(self, "assign_target_box"):
            self.assign_target_box.configure(values=tuple(targets))
            if self.assign_target.get() not in targets:
                self.assign_target.set("Default")

    def assign_main_knob(self):
        name = self.assign_knob.get()
        target = self.assignment_targets.get(self.assign_target.get())
        self._assign_knob_target(name, target)

    def show_knob_assignment_menu(self, event, name):
        """Assign a Shape knob through Effect → Parameter context menus."""
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(
            label=f"Default: {self.knob_specs[name]['label']}",
            command=lambda: self._assign_knob_target(name, None))
        menu.add_separator()
        active = 0
        for effect_index, effect in enumerate(self.effects, 1):
            if not effect.get("enabled", True):
                continue
            func = EFFECT_DISPATCH.get(effect["type"])
            if not func:
                continue
            parameters = []
            for parameter, default in numeric_defaults(func).items():
                if isinstance(default, (int, float)) and not isinstance(default, bool):
                    parameters.append((parameter, default))
            if not parameters:
                continue
            active += 1
            submenu = tk.Menu(menu, tearoff=False)
            for parameter, default in parameters:
                current = effect.get("params", {}).get(parameter, default)
                submenu.add_command(
                    label=f"{parameter}  ({current:.4g})",
                    command=lambda target=(effect, parameter, default):
                    self._assign_knob_target(name, target))
            menu.add_cascade(label=f"{effect_index}. {effect['type']}", menu=submenu)
        if not active:
            menu.add_command(label="No active numeric effects", state="disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _assign_knob_target(self, name, target):
        self._restore_main_knob(name)
        if target is None:
            self.status.set(f"{name} restored to its default control.")
            return
        effect, parameter, default = target
        spec = parameter_control_spec(parameter, default)
        current = effect.get("params", {}).get(parameter, default)
        if spec["kind"] == "knob":
            low, high = spec["low"], spec["high"]
            endless, step = False, None
        else:
            step = spec.get("step", max(.01, abs(float(default)) * .02))
            low, high, endless = float(current) - step * 10, float(current) + step * 10, True
        self.control_assignments[name] = {
            "effect": effect, "parameter": parameter,
            "integer": spec.get("integer", False),
        }
        self.knobs[name].set_control(
            parameter, low, high, current,
            "{:.0f}" if spec.get("integer") else "{:.3g}",
            endless=endless, step=step)
        self.status.set(f"{name} now controls {effect['type']}.{parameter}.")
        self.schedule_macro_rebuild()

    def _restore_main_knob(self, name):
        self.control_assignments.pop(name, None)
        spec = self.knob_specs[name]
        self.knobs[name].set_control(
            spec["label"], spec["low"], spec["high"], spec["value"], spec["fmt"])

    def effect_parameter_changed(self, effect, parameter, value):
        effect.setdefault("params", {})[parameter] = value
        for name, assignment in self.control_assignments.items():
            if assignment["effect"] is effect and assignment["parameter"] == parameter:
                self.knobs[name].set(value)
        self.schedule_waveform()
        # Every enabled rack effect is part of live playback. Updating a field
        # or knob should therefore be audible without requiring a main-knob
        # assignment or another keyboard press.
        self.schedule_macro_rebuild()

    def schedule_waveform(self, *_args):
        if not hasattr(self, "wave"):
            return
        self._wave_generation += 1
        # Throttle the lightweight preview instead of debouncing it: continuous
        # knob movement still produces visible frames.
        if self._wave_quick_busy:
            self._wave_quick_pending = True
        elif self._wave_after is None:
            self._wave_after = self.root.after(35, lambda: self._start_waveform_render(False))
        # Cancel any older exact-preview timer. Full rack rendering happens only
        # for deliberate playback/export; it must never steal the one server CPU
        # merely to repaint a widget.
        if self._wave_exact_after is not None:
            try:
                self.root.after_cancel(self._wave_exact_after)
            except tk.TclError:
                pass
            self._wave_exact_after = None

    def _start_waveform_render(self, exact=False):
        if exact:
            self._wave_exact_after = None
        else:
            self._wave_after = None
            if self._wave_quick_busy:
                self._wave_quick_pending = True
                return
            self._wave_quick_busy = True
        generation = self._wave_generation
        notes = list(self.current_notes)
        threading.Thread(target=self._waveform_worker,
                         args=(generation, notes, exact), daemon=True).start()

    def _waveform_worker(self, generation, notes, exact):
        try:
            audio = self.render(notes, preview=not exact, live=False)
        except Exception:
            audio = None
        if audio is not None and generation == self._wave_generation:
            self.preview_data = audio
            self.root.after(0, self.wave.draw)
        if not exact:
            self.root.after(0, self._finish_quick_waveform)

    def _finish_quick_waveform(self):
        self._wave_quick_busy = False
        if self._wave_quick_pending:
            self._wave_quick_pending = False
            if self._wave_after is None:
                self._wave_after = self.root.after(
                    35, lambda: self._start_waveform_render(False))

    def sync_trim_knobs(self):
        self.knobs["Start"].set(self.start * 100)
        self.knobs["End"].set(self.end * 100)

    def load_sample(self):
        initial = IMPORTS if os.path.isdir(IMPORTS) else os.path.expanduser("~")
        path = filedialog.askopenfilename(initialdir=initial, title="Load a sample",
                                          filetypes=(("Audio", "*.wav *.flac *.ogg *.aif *.aiff"),
                                                     ("All files", "*")))
        if not path:
            return
        try:
            data, sr = sf.read(path, always_2d=True, dtype="float64")
            if len(data) > sr * 120:
                raise ValueError("Samples are limited to 2 minutes")
            self.sample, self.sample_rate, self.sample_path = data, sr, path
            self.preview_data, self.patch = data, None
            self.mode.set("sample")
            self.start, self.end = 0, 1
            self.sync_trim_knobs()
            self.source_label.configure(text=f"Sample: {os.path.basename(path)}  •  {len(data)/sr:.2f}s  •  {sr} Hz")
            self.wave.draw()
            self.status.set("Sample loaded. Play the keyboard or shape it with the knobs.")
            self.schedule_waveform()
        except Exception as exc:
            messagebox.showerror("Could not load sample", str(exc))

    def new_sound(self):
        try:
            self.patch = self.randomizer.generate_patch(genre=self.genre.get())
            self.clear_macro_assignments()
            self.effects = []
            for fx in self.patch.get("effects", []):
                item = {"type": fx["type"], "params": dict(fx.get("params", {})), "enabled": True}
                self.effects.append(item)
            if hasattr(self, "rack"):
                self.rack.refresh_chain()
            self.refresh_assignment_targets()
            self.mode.set("synth")
            self.sample = None
            self.live_source = None
            self.live_effect_source = None
            self._live_dry_buffer = None
            self.start, self.end = 0, 1
            self.sync_trim_knobs()
            oscs = ", ".join(o.get("waveform", "?") for o in self.patch.get("oscillators", []))
            self.source_label.configure(text=oscs or "mixed")
            if hasattr(self, "osc_list"):
                self.refresh_oscillator_list()
            self.default_snapshot = {
                "patch": copy.deepcopy(self.patch),
                "effects": copy.deepcopy(self.effects),
            }
            self.status.set("New sound made. Click a keyboard key; choose a genre for another sound.")
            threading.Thread(target=self._update_synth_preview, daemon=True).start()
        except Exception as exc:
            messagebox.showerror("FigLib error", str(exc))

    def _update_synth_preview(self):
        try:
            self.preview_data = self.render(self.current_notes, preview=True, live=False)
            self.root.after(0, self.wave.draw)
        except Exception as exc:
            self.root.after(0, lambda: self.status.set(f"Preview error: {exc}"))

    def _render_live_source(self):
        """Bake a short, flat C4 oscillator cache for immediate keyboard audition."""
        if not self.patch:
            raise ValueError("Make a sound first")
        synth = FiggyGenSynth(RATE)
        for osc in self.patch.get("oscillators", []):
            synth.add_oscillator(**osc)
        synth.set_effects([])
        synth.envelope = Envelope(attack=0.0, decay=0.0, sustain_level=1.0, release=0.0)
        source = synth.render(.5, 261.625565)
        if source.ndim == 1:
            source = np.column_stack((source, source))
        # Blend the tail toward the corresponding start segment so repeating
        # the cache does not click at its loop boundary.
        fade_len = min(int(.015 * RATE), len(source) // 4)
        if fade_len > 1:
            fade = np.linspace(0.0, 1.0, fade_len)[:, None]
            source[-fade_len:] = source[-fade_len:] * (1.0 - fade) + source[:fade_len] * fade
        self.live_loop_start = fade_len
        return source

    def apply_fx_preset(self):
        preset = self.randomizer.fx_presets.get(self.fx_preset.get())
        if not preset:
            return
        chain = self.randomizer._generate_fx_chain(preset)
        self.clear_macro_assignments()
        self.effects = [{"type": fx["type"], "params": dict(fx.get("params", {})),
                         "enabled": True} for fx in chain]
        self.rack.refresh_chain()
        self.refresh_assignment_targets()
        self.schedule_waveform()
        self.schedule_macro_rebuild()
        self.status.set(f"Applied {self.fx_preset.get()} recipe ({len(self.effects)} effects).")

    def clear_fx(self):
        self.clear_macro_assignments()
        self.effects = []
        self.rack.refresh_chain()
        self.refresh_assignment_targets()
        self.schedule_waveform()
        self.schedule_macro_rebuild()

    def macro_for(self, effect, parameter):
        for index, assignment in enumerate(self.macro_assignments):
            if assignment and assignment["effect"] is effect and assignment["parameter"] == parameter:
                return f"M{index + 1}"
        return "—"

    def assign_macro(self, choice, effect, parameter, default):
        for index, assignment in enumerate(self.macro_assignments):
            if assignment and assignment["effect"] is effect and assignment["parameter"] == parameter:
                self.macro_assignments[index] = None
                self.macro_labels[index].set("unassigned")
        if choice != "—":
            index = int(choice[1:]) - 1
            limits = parameter_range(parameter, default)
            assignment = {
                "effect": effect,
                "parameter": parameter,
                "limits": limits,
                "integer": isinstance(default, int) and not isinstance(default, bool),
            }
            self.macro_assignments[index] = assignment
            current = effect.get("params", {}).get(parameter, default)
            self.macro_knobs[index].set(parameter_to_macro(current, limits))
            self._update_macro_label(index)
        self.schedule_macro_rebuild()

    def _update_macro_label(self, index):
        assignment = self.macro_assignments[index]
        if not assignment:
            self.macro_labels[index].set("unassigned")
            return
        effect = assignment["effect"]
        parameter = assignment["parameter"]
        value = effect.get("params", {}).get(parameter, 0)
        self.macro_labels[index].set(f"{effect['type']}.{parameter} = {value:.3g}")

    def macro_changed(self, index, value):
        assignment = self.macro_assignments[index]
        if not assignment:
            return
        mapped = macro_to_parameter(value, assignment["limits"])
        if assignment["integer"]:
            mapped = int(round(mapped))
        assignment["effect"].setdefault("params", {})[assignment["parameter"]] = mapped
        self._update_macro_label(index)
        self.schedule_macro_rebuild()
        self.schedule_waveform()

    def unassign_effect(self, effect):
        changed = False
        for index, assignment in enumerate(self.macro_assignments):
            if assignment and assignment["effect"] is effect:
                self.macro_assignments[index] = None
                self.macro_labels[index].set("unassigned")
                changed = True
        if changed:
            self.schedule_macro_rebuild()
        for name, assignment in list(self.control_assignments.items()):
            if assignment["effect"] is effect:
                self._restore_main_knob(name)
        self.refresh_assignment_targets()

    def clear_macro_assignments(self):
        for index in range(4):
            self.macro_assignments[index] = None
            if index < len(self.macro_labels):
                self.macro_labels[index].set("unassigned")
        self.live_effect_source = self.live_source
        for name in list(self.control_assignments):
            self._restore_main_knob(name)

    def schedule_macro_rebuild(self):
        # Editing an effect never launches a render. The next keypress is the
        # render command and will use the new active-rack state.
        self._macro_generation += 1
        if self._macro_after is not None:
            try:
                self.root.after_cancel(self._macro_after)
            except tk.TclError:
                pass
            self._macro_after = None
        self._live_wet_cache.clear()

    def _start_macro_rebuild(self):
        self._macro_after = None
        if self._live_dry_buffer is None:
            return
        if self._macro_busy:
            self._macro_pending = True
            return
        self._macro_busy = True
        generation = self._macro_generation
        threading.Thread(target=self._macro_rebuild_worker,
                         args=(generation,), daemon=True).start()

    def _macro_rebuild_worker(self, generation):
        try:
            audio = self._process_live_macros(
                self._live_dry_buffer,
                cancel=lambda: generation != self._macro_generation)
            if audio is None or generation != self._macro_generation:
                return
            audio = np.nan_to_num(audio)
            if audio.ndim == 1:
                audio = np.column_stack((audio, audio))
            self.root.after(0, lambda data=audio: self._replace_stream_buffer(data))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self.status.set(f"Live macro preview: {e}"))
        finally:
            self.root.after(0, self._finish_macro_rebuild)

    def _finish_macro_rebuild(self):
        self._macro_busy = False
        if self._macro_pending:
            self._macro_pending = False
            if self._macro_after is None:
                self._macro_after = self.root.after(55, self._start_macro_rebuild)

    def _process_live_macros(self, source, cancel=None):
        audio = np.array(source, copy=True)
        for effect in self.effects:
            if cancel is not None and cancel():
                return None
            if not effect.get("enabled", True):
                continue
            func = EFFECT_DISPATCH.get(effect["type"])
            if not func:
                continue
            params = dict(effect.get("params", {}))
            params["sample_rate"] = RATE
            signature = inspect.signature(func)
            if not any(p.kind == p.VAR_KEYWORD for p in signature.parameters.values()):
                params = {k: v for k, v in params.items() if k in signature.parameters}
            processed = func(audio, **params)
            if processed is not None:
                audio = processed
            if cancel is not None and cancel():
                return None
        audio = np.nan_to_num(audio)
        if audio.ndim == 1:
            audio = np.column_stack((audio, audio))
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak > .99:
            audio *= .99 / peak
        return audio

    @staticmethod
    def _fast_delay(audio, params):
        delay = max(1, int(float(params.get("time", .3)) * RATE))
        feedback = max(0.0, min(.95, float(params.get("feedback", .5))))
        mix = max(0.0, min(1.0, float(params.get("mix", .5))))
        wet = np.zeros_like(audio)
        for repeat in range(1, 5):
            offset = delay * repeat
            if offset >= len(audio):
                break
            part = audio[:-offset]
            if params.get("ping_pong") and repeat % 2:
                part = part[:, ::-1]
            wet[offset:] += part * (feedback ** (repeat - 1))
        return audio * (1.0 - mix) + wet * mix

    @staticmethod
    def _fast_reverb(audio, params):
        mix = max(0.0, min(1.0, float(params.get("mix", .3))))
        decay = max(.1, float(params.get("decay", params.get("size", 1.5))))
        wet = np.zeros_like(audio)
        # Sparse, stereo-offset reflection taps give an immediate room/plate
        # impression without FigLib's sample-by-sample offline loops.
        taps = (.019, .031, .047, .071, .103, .149, .211, .293)
        for index, seconds in enumerate(taps):
            offset = int(seconds * RATE)
            if offset >= len(audio):
                break
            gain = math.exp(-seconds * 3.0 / decay) * .34
            part = audio[:-offset]
            wet[offset:] += (part[:, ::-1] if index % 2 else part) * gain
        return audio * (1.0 - mix) + wet * mix

    @staticmethod
    def _fast_dynamics(audio, params, limiter=False):
        peak = np.max(np.abs(audio), axis=1, keepdims=True) + 1e-9
        if limiter:
            ceiling = 10 ** (float(params.get("ceiling", -.1)) / 20.0)
            gain = np.minimum(1.0, ceiling / peak)
        else:
            threshold = 10 ** (float(params.get("threshold", -20.0)) / 20.0)
            ratio = max(1.0, float(params.get("ratio", 4.0)))
            compressed = threshold * np.power(np.maximum(peak / threshold, 1.0), 1.0 / ratio)
            gain = np.where(peak > threshold, compressed / peak, 1.0)
            gain *= 10 ** (float(params.get("makeup_gain", 0.0)) / 20.0)
        return audio * gain

    def _process_realtime_effects(self, source):
        """Low-latency path for only the enabled effects in the rack."""
        audio = np.array(source, copy=True)
        filter_like = {"303", "juno_hpf", "moog", "ms20", "prophet", "sem", "wasp"}
        reverb_like = {"ams_reverb", "emt_plate", "lexicon", "reverb", "spring"}
        compressor_like = {"compressor", "fairchild", "ssl", "dbx160", "la2a", "1176"}
        for effect in self.effects:
            if not effect.get("enabled", True):
                continue
            name = effect["type"]
            params = dict(effect.get("params", {}))
            if name in filter_like:
                cutoff = float(params.get("cutoff", 1200.0))
                resonance = float(params.get("resonance", .5))
                filter_type = "highpass" if name == "juno_hpf" else params.get("mode", "lowpass")
                if filter_type not in ("lowpass", "highpass", "bandpass", "notch"):
                    filter_type = "lowpass"
                audio = EFFECT_DISPATCH["filter"](
                    audio, filter_type=filter_type, cutoff=cutoff,
                    resonance=resonance, sample_rate=RATE)
            elif name == "buchla_lpg":
                audio = EFFECT_DISPATCH["filter"](
                    audio, cutoff=400 + 5000 * float(params.get("strike", .7)),
                    resonance=float(params.get("resonance", .2)), sample_rate=RATE)
                if params.get("mode", "both") in ("vca", "both"):
                    curve = np.exp(-np.arange(len(audio)) / max(1, RATE * float(params.get("decay", .3))))
                    audio *= curve[:, None]
            elif name == "delay":
                audio = self._fast_delay(audio, params)
            elif name in reverb_like:
                audio = self._fast_reverb(audio, params)
            elif name == "limiter":
                audio = self._fast_dynamics(audio, params, limiter=True)
            elif name in compressor_like:
                audio = self._fast_dynamics(audio, params)
            elif name in ("phaser", "small_stone"):
                audio = EFFECT_DISPATCH["chorus"](
                    audio, rate=float(params.get("rate", .5)),
                    depth=.002 + .004 * float(params.get("depth", .5)),
                    voices=2, mix=float(params.get("mix", .5)), sample_rate=RATE)
            elif name == "flanger":
                audio = EFFECT_DISPATCH["chorus"](
                    audio, rate=float(params.get("rate", .25)),
                    depth=float(params.get("depth", .002)), voices=2,
                    mix=float(params.get("mix", .5)), sample_rate=RATE)
            elif name == "transient":
                level = np.max(np.abs(audio), axis=1)
                onset = np.maximum(0.0, np.diff(level, prepend=level[:1]))
                scale = onset / (float(np.max(onset)) + 1e-9)
                attack = max(0.0, float(params.get("attack_gain", 1.5)) - 1.0)
                sustain = float(params.get("sustain_gain", 1.0))
                audio *= (sustain + attack * scale)[:, None]
            elif name == "multiband":
                threshold = (float(params.get("low_thresh", -20))
                             + float(params.get("mid_thresh", -18))
                             + float(params.get("high_thresh", -15))) / 3.0
                audio = self._fast_dynamics(
                    audio, {"threshold": threshold, "ratio": 3.0})
            elif name == "crystal":
                audio = self._fast_delay(audio, {
                    "time": .055 + .08 * float(params.get("brightness", .5)),
                    "feedback": .25 + .5 * float(params.get("decay", .3)),
                    "mix": .35,
                    "ping_pong": True,
                })
            elif name == "glitch":
                audio = EFFECT_DISPATCH["stutter"](
                    audio, grain_size_ms=float(params.get("slice_ms", 30)),
                    repeats=max(2, int(2 + 4 * float(params.get("density", .3)))),
                    mix=float(params.get("density", .3)), sample_rate=RATE)
            elif name == "fender_twin":
                audio = EFFECT_DISPATCH["tube"](
                    audio, drive=.2 + float(params.get("volume", .4)), asymmetry=.15)
                audio = self._fast_reverb(audio, {"mix": params.get("reverb_mix", .3), "decay": 1.2})
            else:
                func = EFFECT_DISPATCH.get(name)
                if not func:
                    continue
                params["sample_rate"] = RATE
                signature = inspect.signature(func)
                if not any(p.kind == p.VAR_KEYWORD for p in signature.parameters.values()):
                    params = {key: value for key, value in params.items() if key in signature.parameters}
                processed = func(audio, **params)
                if processed is not None:
                    audio = processed
        audio = np.nan_to_num(audio)
        if audio.ndim == 1:
            audio = np.column_stack((audio, audio))
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak > .99:
            audio *= .99 / peak
        return audio

    def capture_sound_state(self):
        """Capture everything needed to reproduce and later edit one roll hit."""
        assignment_state = {}
        for name, assignment in self.control_assignments.items():
            try:
                effect_index = next(
                    i for i, effect in enumerate(self.effects)
                    if effect is assignment["effect"])
            except StopIteration:
                continue
            assignment_state[name] = {
                "effect_index": effect_index,
                "parameter": assignment["parameter"],
                "integer": assignment.get("integer", False),
            }
        if self.mode.get() == "sample":
            label = os.path.splitext(os.path.basename(self.sample_path or "sample"))[0]
        else:
            waves = [osc.get("waveform", "osc") for osc in
                     (self.patch or {}).get("oscillators", [])]
            label = "+".join(waves[:2]) or "synth"
        return {
            "label": label,
            "mode": self.mode.get(),
            # Sample arrays are immutable in this UI. Retaining the reference
            # avoids duplicating a potentially large file for every grid hit.
            "sample": self.sample,
            "sample_rate": self.sample_rate,
            "sample_path": self.sample_path,
            "patch": copy.deepcopy(self.patch),
            "effects": copy.deepcopy(self.effects),
            "knobs": {name: knob.get() for name, knob in self.knobs.items()},
            "assignments": assignment_state,
            "start": self.start,
            "end": self.end,
            "duration": float(self.duration.get()),
            "loop": bool(self.loop.get()),
            "lfo_target": self.lfo_target.get(),
            "genre": self.genre.get(),
        }

    def restore_piano_hit(self, hit):
        state = hit["snapshot"]
        self.clear_macro_assignments()
        self.mode.set(state["mode"])
        self.sample = state["sample"]
        self.sample_rate = state["sample_rate"]
        self.sample_path = state["sample_path"]
        self.patch = copy.deepcopy(state["patch"])
        self.effects = copy.deepcopy(state["effects"])
        self.start, self.end = state["start"], state["end"]
        self.duration.set(state["duration"])
        self.loop.set(state["loop"])
        self.lfo_target.set(state["lfo_target"])
        if state["genre"] in self.randomizer.genres:
            self.genre.set(state["genre"])
        for name in self.knobs:
            self._restore_main_knob(name)
            self.knobs[name].set(state["knobs"].get(name, self.knob_specs[name]["value"]))
        self.control_assignments.clear()
        for name, saved in state.get("assignments", {}).items():
            index = saved["effect_index"]
            if name not in self.knobs or not 0 <= index < len(self.effects):
                continue
            effect = self.effects[index]
            parameter = saved["parameter"]
            defaults = numeric_defaults(EFFECT_DISPATCH[effect["type"]])
            if parameter not in defaults:
                continue
            default = defaults[parameter]
            spec = parameter_control_spec(parameter, default)
            value = effect.get("params", {}).get(parameter, default)
            if spec["kind"] == "knob":
                low, high, endless, step = spec["low"], spec["high"], False, None
            else:
                step = spec.get("step", max(.01, abs(float(default)) * .02))
                low, high, endless = float(value) - step * 10, float(value) + step * 10, True
            self.control_assignments[name] = {
                "effect": effect, "parameter": parameter,
                "integer": saved.get("integer", False),
            }
            self.knobs[name].set_control(
                parameter, low, high, value,
                "{:.0f}" if saved.get("integer") else "{:.3g}",
                endless=endless, step=step)
        self._live_dry_buffer = None
        self.rack.refresh_chain()
        self.refresh_assignment_targets()
        self.refresh_oscillator_list()
        if state["mode"] == "sample":
            seconds = len(self.sample) / self.sample_rate if self.sample is not None else 0
            self.source_label.configure(
                text=f"Sample: {os.path.basename(self.sample_path or 'sample')}  •  {seconds:.2f}s")
        else:
            self.source_label.configure(text=f"Piano-roll synth: {state['label']}")
        self.preview_data = hit.get("audio")
        self.wave.draw()
        self.tabs.select(0)
        self.status.set(f"Loaded piano-roll hit “{state['label']}” back into the sampler.")

    def place_piano_hit(self, step, note):
        if self.mode.get() == "sample" and self.sample is None:
            self.status.set("Load a sample before placing a sample hit.")
            return
        if self.mode.get() == "synth" and not self.patch:
            self.status.set("Make a synth sound before placing a hit.")
            return
        snapshot = self.capture_sound_state()
        hit = self.piano_roll.add_hit(step, note, snapshot)
        key = self._piano_render_key(snapshot, note)
        hit["render_key"] = key
        cached = self._piano_audio_cache.get(key)
        if cached is not None:
            hit["audio"] = cached
        self.status.set(
            f"Placed {snapshot['label']} at step {step + 1}, {note_name(note)}.")

    @staticmethod
    def _piano_render_key(snapshot, note):
        return (
            snapshot["mode"], id(snapshot["sample"]), snapshot["sample_path"], note,
            snapshot["start"], snapshot["end"], snapshot["duration"], snapshot["loop"],
            snapshot["lfo_target"], tuple(sorted(snapshot["knobs"].items())),
            repr(snapshot["patch"]), repr(snapshot["effects"]),
        )

    @staticmethod
    def _render_sound_state(state, note):
        """Render a captured hit without reading or mutating Tk UI state."""
        knobs = state["knobs"]
        duration = max(.05, float(state["duration"]))
        if state["mode"] == "sample":
            sample = state["sample"]
            if sample is None:
                raise ValueError("The captured sample is no longer available")
            lo = int(state["start"] * len(sample))
            hi = int(state["end"] * len(sample))
            source = sample[lo:max(lo + 1, hi)]
            ratio = (2 ** ((note - 60 + knobs["Pitch"]) / 12.0)
                     * state["sample_rate"] / RATE)
            wanted = max(1, int(duration * RATE))
            positions = np.arange(wanted, dtype=np.float64) * ratio
            if state["loop"]:
                positions %= max(1, len(source) - 1)
            valid = positions < len(source) - 1
            audio = np.zeros((wanted, source.shape[1]), dtype=np.float64)
            points = positions[valid]
            left = points.astype(np.int64)
            frac = (points - left)[:, None]
            audio[valid] = (source[left] * (1 - frac)
                            + source[np.minimum(left + 1, len(source) - 1)] * frac)
            env = Envelope(attack=knobs["Attack"], decay=knobs["Decay"],
                           sustain_level=knobs["Sustain"], release=knobs["Release"])
            audio *= env.get_envelope(len(audio))[:, None]
        else:
            patch = state["patch"] or {}
            synth = FiggyGenSynth(RATE)
            for osc in patch.get("oscillators", []):
                synth.add_oscillator(**osc)
            synth.set_effects([])
            synth.envelope = Envelope(attack=knobs["Attack"], decay=knobs["Decay"],
                                      sustain_level=knobs["Sustain"], release=knobs["Release"])
            frequency = 440 * 2 ** ((note + knobs["Pitch"] - 69) / 12)
            audio = synth.render(duration, frequency)
        if audio.ndim == 1:
            audio = np.column_stack((audio, audio))
        if state["mode"] == "synth" and (state["start"] > 0.0 or state["end"] < 1.0):
            lo = max(0, min(len(audio) - 1, int(state["start"] * len(audio))))
            hi = max(lo + 1, min(len(audio), int(state["end"] * len(audio))))
            audio = audio[lo:hi]
        cutoff, resonance = knobs["Cutoff"], knobs["Resonance"]
        if cutoff < 17950:
            audio = EFFECT_DISPATCH["filter"](
                audio, cutoff=cutoff, resonance=resonance, sample_rate=RATE)
        depth = knobs["LFO depth"]
        if depth > .001:
            rate, target = knobs["LFO rate"], state["lfo_target"]
            if target == "pitch":
                audio = EFFECT_DISPATCH["vibrato"](
                    audio, rate=rate, depth=.008 * depth, sample_rate=RATE)
            elif target == "volume":
                audio = EFFECT_DISPATCH["tremolo"](
                    audio, rate=rate, depth=depth, sample_rate=RATE)
            else:
                timeline = np.arange(len(audio)) / RATE
                lfo = .5 + .5 * np.sin(2 * np.pi * rate * timeline)
                wet = EFFECT_DISPATCH["filter"](
                    audio, cutoff=max(80, cutoff * .25),
                    resonance=resonance, sample_rate=RATE)
                audio = audio * (1 - lfo[:, None] * depth) + wet * lfo[:, None] * depth
        for effect in state["effects"]:
            if not effect.get("enabled", True):
                continue
            func = EFFECT_DISPATCH.get(effect["type"])
            if not func:
                continue
            params = dict(effect.get("params", {}))
            params["sample_rate"] = RATE
            signature = inspect.signature(func)
            if not any(p.kind == p.VAR_KEYWORD for p in signature.parameters.values()):
                params = {k: v for k, v in params.items() if k in signature.parameters}
            processed = func(audio, **params)
            if processed is not None:
                audio = processed
        audio = np.nan_to_num(audio) * knobs["Volume"]
        peak = float(np.max(np.abs(audio))) if len(audio) else 0
        if peak > .99:
            audio *= .99 / peak
        return np.clip(audio, -1, 1)

    def _pattern_request(self):
        hits = list(self.piano_roll.hits.items())
        if not hits:
            raise ValueError("Place at least one hit in the piano roll")
        bpm = max(30.0, min(300.0, float(self.piano_roll.bpm.get())))
        return hits, bpm

    def _mixed_pattern(self, hits, bpm):
        for (_step, note), hit in hits:
            if hit.get("audio") is not None:
                continue
            key = hit.get("render_key") or self._piano_render_key(hit["snapshot"], note)
            audio = self._piano_audio_cache.get(key)
            if audio is None:
                audio = self._render_sound_state(hit["snapshot"], note).astype(np.float32)
                self._piano_audio_cache[key] = audio
                while len(self._piano_audio_cache) > 64:
                    self._piano_audio_cache.pop(next(iter(self._piano_audio_cache)))
            hit["audio"] = audio
        step_frames = max(1, int(RATE * 60.0 / bpm / 4.0))
        total = self.piano_roll.STEPS * step_frames
        for (step, _note), hit in hits:
            total = max(total, step * step_frames + len(hit["audio"]))
        mix = np.zeros((total, 2), dtype=np.float32)
        for (step, _note), hit in hits:
            audio = hit["audio"]
            start = step * step_frames
            mix[start:start + len(audio)] += audio
        peak = float(np.max(np.abs(mix))) if len(mix) else 0
        if peak > .99:
            mix *= .99 / peak
        return mix

    def play_pattern(self):
        if self._pattern_busy:
            self.status.set("The piano roll is already rendering a pattern.")
            return
        try:
            hits, bpm = self._pattern_request()
        except Exception as exc:
            self.status.set(str(exc))
            return
        self._pattern_busy = True
        self.status.set(f"Rendering {len(hits)} piano-roll hit(s)…")
        threading.Thread(target=self._play_pattern_worker,
                         args=(hits, bpm), daemon=True).start()

    def _play_pattern_worker(self, hits, bpm):
        try:
            audio = self._mixed_pattern(hits, bpm)
            self.root.after(0, lambda: self._finish_pattern_play(audio, hits, bpm))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._finish_pattern_play(None, hits, bpm, e))

    def _finish_pattern_play(self, audio, hits, bpm, error=None):
        self._pattern_busy = False
        if error is not None:
            self.status.set(f"Pattern render failed: {error}")
            return
        self.preview_data = audio
        self.wave.draw()
        self.piano_roll.draw()
        self._start_stream(audio)
        self.status.set(f"Playing {len(hits)} piano-roll hit(s) at {bpm:.0f} BPM.")

    def stop_audio(self):
        with self._stream_lock:
            self._stream_token += 1
            process = self._stream_process
            self._stream_process = None
            self._stream_buffer = None
        if process and process.poll() is None:
            process.terminate()
        self.status.set("Playback stopped.")

    def export_pattern(self):
        if self._pattern_busy:
            self.status.set("The piano roll is already rendering a pattern.")
            return
        try:
            hits, bpm = self._pattern_request()
        except Exception as exc:
            self.status.set(str(exc))
            return
        os.makedirs(EXPORTS, exist_ok=True)
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save piano-roll pattern as WAV",
            initialdir=EXPORTS,
            initialfile=f"figsynth_pattern_{time.strftime('%H%M%S')}.wav",
            defaultextension=".wav", filetypes=(("WAV audio", "*.wav"),))
        if not path:
            return
        self._pattern_busy = True
        self.status.set(f"Rendering {len(hits)} hit(s) for {os.path.basename(path)}…")
        threading.Thread(target=self._export_pattern_worker,
                         args=(path, hits, bpm), daemon=True).start()

    def _export_pattern_worker(self, path, hits, bpm):
        try:
            audio = self._mixed_pattern(hits, bpm)
            sf.write(path, audio, RATE, subtype="PCM_16")
            self.root.after(0, lambda: self._finish_pattern_export(path))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._finish_pattern_export(None, e))

    def _finish_pattern_export(self, path, error=None):
        self._pattern_busy = False
        self.piano_roll.draw()
        if error is not None:
            messagebox.showerror("Pattern export failed", str(error))
            return
        self.status.set(f"Saved pattern {os.path.basename(path)}.")

    def _sampler_voice(self, midi, duration=None):
        if self.sample is None:
            raise ValueError("Load a sample first")
        lo, hi = int(self.start * len(self.sample)), int(self.end * len(self.sample))
        source = self.sample[lo:max(lo + 1, hi)]
        semitones = midi - 60 + self.knobs["Pitch"].get()
        ratio = 2 ** (semitones / 12.0) * self.sample_rate / RATE
        wanted = max(1, int((float(self.duration.get()) if duration is None else duration) * RATE))
        positions = np.arange(wanted, dtype=np.float64) * ratio
        if self.loop.get():
            positions %= max(1, len(source) - 1)
        valid = positions < len(source) - 1
        output = np.zeros((wanted, source.shape[1]), dtype=np.float64)
        p = positions[valid]
        left = p.astype(np.int64)
        frac = (p - left)[:, None]
        output[valid] = source[left] * (1 - frac) + source[np.minimum(left + 1, len(source) - 1)] * frac
        return output

    def _sampler_audio(self, notes, duration=None):
        voices = [self._sampler_voice(note, duration) for note in notes]
        return sum(voices) / math.sqrt(len(voices))

    def _synth_audio(self, notes, duration=None):
        if not self.patch:
            raise ValueError("Make a sound first")
        synth = FiggyGenSynth(RATE)
        for osc in self.patch.get("oscillators", []):
            synth.add_oscillator(**osc)
        synth.set_effects([])
        synth.envelope = Envelope(attack=self.knobs["Attack"].get(),
                                  decay=self.knobs["Decay"].get(),
                                  sustain_level=self.knobs["Sustain"].get(),
                                  release=self.knobs["Release"].get())
        transpose = self.knobs["Pitch"].get()
        frequencies = [440 * 2 ** ((note + transpose - 69) / 12) for note in notes]
        render_duration = float(self.duration.get()) if duration is None else duration
        return synth.render(render_duration, frequencies)

    def _cached_synth_audio(self, notes):
        source = self.live_effect_source if self.live_effect_source is not None else self.live_source
        if source is None or not len(source):
            return self._synth_audio(notes, .25)
        wanted = max(1, int(float(self.duration.get()) * RATE))
        voices = []
        loop_start = min(self.live_loop_start, max(0, len(source) - 2))
        loop_span = max(1, len(source) - loop_start)
        for note in notes:
            semitones = note - 60 + self.knobs["Pitch"].get()
            ratio = 2 ** (semitones / 12.0)
            positions = loop_start + (
                np.arange(wanted, dtype=np.float64) * ratio
            ) % loop_span
            left = positions.astype(np.int64)
            frac = (positions - left)[:, None]
            voice = source[left] * (1.0 - frac) + source[np.minimum(left + 1, len(source) - 1)] * frac
            voices.append(voice)
        return sum(voices) / math.sqrt(len(voices))

    def render(self, notes, preview=False, live=False):
        notes = [notes] if np.isscalar(notes) else list(notes)
        preview_duration = (min(.25, max(.05, float(self.duration.get())))
                            if preview and not live else None)
        if self.mode.get() == "sample":
            audio = self._sampler_audio(notes, preview_duration)
        elif live:
            audio = self._synth_audio(notes)
        else:
            audio = self._synth_audio(notes, preview_duration)
        if audio.ndim == 1:
            audio = np.column_stack((audio, audio))
        if self.mode.get() == "synth" and (self.start > 0.0 or self.end < 1.0):
            lo = max(0, min(len(audio) - 1, int(self.start * len(audio))))
            hi = max(lo + 1, min(len(audio), int(self.end * len(audio))))
            audio = audio[lo:hi]
        env = Envelope(attack=self.knobs["Attack"].get(), decay=self.knobs["Decay"].get(),
                       sustain_level=self.knobs["Sustain"].get(),
                       release=self.knobs["Release"].get())
        if self.mode.get() == "sample":
            audio *= env.get_envelope(len(audio))[:, None]
        cutoff = self.knobs["Cutoff"].get()
        resonance = self.knobs["Resonance"].get()
        if cutoff < 17950:
            audio = EFFECT_DISPATCH["filter"](audio, cutoff=cutoff, resonance=resonance,
                                               sample_rate=RATE)
        depth = self.knobs["LFO depth"].get()
        if depth > .001:
            target, rate = self.lfo_target.get(), self.knobs["LFO rate"].get()
            if target == "pitch":
                audio = EFFECT_DISPATCH["vibrato"](audio, rate=rate, depth=.008 * depth,
                                                    sample_rate=RATE)
            elif target == "volume":
                audio = EFFECT_DISPATCH["tremolo"](audio, rate=rate, depth=depth,
                                                    sample_rate=RATE)
            else:
                t = np.arange(len(audio)) / RATE
                lfo = .5 + .5 * np.sin(2 * np.pi * rate * t)
                wet = EFFECT_DISPATCH["filter"](audio, cutoff=max(80, cutoff * .25),
                                                resonance=resonance, sample_rate=RATE)
                audio = audio * (1 - lfo[:, None] * depth) + wet * lfo[:, None] * depth
        if not preview and not live:
            for fx in self.effects:
                if not fx.get("enabled", True):
                    continue
                func = EFFECT_DISPATCH.get(fx["type"])
                if not func:
                    continue
                params = dict(fx.get("params", {}))
                params["sample_rate"] = RATE
                sig = inspect.signature(func)
                if not any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
                    params = {k: v for k, v in params.items() if k in sig.parameters}
                audio = func(audio, **params)
                if audio is None:
                    raise RuntimeError(f"{fx['type']} returned no audio")
        audio = np.nan_to_num(audio) * self.knobs["Volume"].get()
        peak = float(np.max(np.abs(audio))) if len(audio) else 0
        if peak > .99:
            audio *= .99 / peak
        return np.clip(audio, -1, 1)

    def play(self, notes):
        notes = [int(notes)] if np.isscalar(notes) else [int(n) for n in notes]
        self.current_note = notes[0]
        self.current_notes = notes
        label = notes_label(notes)
        cache_key = self._live_playback_key(notes)
        self.status.set(f"Playing {label}…")
        threading.Thread(target=self._play_worker,
                         args=(notes, cache_key), daemon=True).start()

    def _live_playback_key(self, notes):
        return (
            tuple(notes), self.mode.get(), id(self.sample), self.sample_path,
            self.sample_rate, self.start, self.end, float(self.duration.get()),
            bool(self.loop.get()), self.lfo_target.get(),
            tuple((name, knob.get()) for name, knob in self.knobs.items()),
            repr(self.patch), repr(self.effects),
        )

    def _play_worker(self, notes, cache_key):
        try:
            dry = self.render(notes, preview=True, live=True)
            self._live_dry_buffer = dry
            cached = self._live_wet_cache.get(cache_key)
            audio = cached if cached is not None else self._process_realtime_effects(dry)
            if cached is None:
                self._live_wet_cache[cache_key] = audio
                while len(self._live_wet_cache) > 24:
                    self._live_wet_cache.pop(next(iter(self._live_wet_cache)))
            self.preview_data = audio
            self.root.after(0, self.wave.draw)
            self._start_stream(audio)
            active = sum(effect.get("enabled", True) for effect in self.effects)
            self.root.after(0, lambda: self.status.set(
                f"Live: {notes_label(notes)} • {active} active rack effect(s)"))
        except Exception as exc:
            self.root.after(0, lambda e=exc: messagebox.showerror("Playback failed", str(e)))

    def _start_stream(self, audio):
        with self._stream_lock:
            self._stream_token += 1
            token = self._stream_token
            previous = self._stream_process
            if previous and previous.poll() is None:
                previous.terminate()
            process = subprocess.Popen(
                ["pacat", "--playback", "--raw", "--format=s16le",
                 f"--rate={RATE}", "--channels=2", f"--device={PULSE_SINK}",
                 "--latency-msec=25"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, bufsize=0)
            self._stream_process = process
            self._stream_buffer = np.asarray(audio, dtype=np.float64)
            self._stream_position = 0
        threading.Thread(target=self._stream_writer,
                         args=(token, process), daemon=True).start()
        return token

    def _stream_writer(self, token, process):
        try:
            while True:
                with self._stream_lock:
                    if token != self._stream_token or process is not self._stream_process:
                        break
                    audio = self._stream_buffer
                    position = self._stream_position
                    if audio is None or position >= len(audio):
                        break
                    end = min(len(audio), position + 512)
                    chunk = np.array(audio[position:end], copy=True)
                    self._stream_position = end
                pcm = (np.clip(chunk, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
                process.stdin.write(pcm)
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                process.stdin.close()
            except (BrokenPipeError, OSError, AttributeError):
                pass
            process.wait()
            with self._stream_lock:
                if process is self._stream_process:
                    self._stream_process = None

    def _replace_stream_buffer(self, audio, expected_token=None):
        if expected_token is not None and expected_token != self._stream_token:
            return
        self.preview_data = audio
        self.wave.draw()
        with self._stream_lock:
            if expected_token is not None and expected_token != self._stream_token:
                return
            process = self._stream_process
            if not process or process.poll() is not None:
                return
            position = self._stream_position
            self._stream_buffer = np.asarray(audio, dtype=np.float64)
            self._stream_position = min(position, max(0, len(audio) - 1))

    def export(self):
        if self._export_busy:
            self.status.set("A sample is already being saved.")
            return
        os.makedirs(EXPORTS, exist_ok=True)
        rendered = "-".join(note_name(n).replace("#", "s") for n in self.current_notes)
        base = f"figlib_{self.genre.get()}_{rendered}_{time.strftime('%H%M%S')}.wav"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export audio",
            initialdir=EXPORTS,
            initialfile=base,
            defaultextension=".wav",
            filetypes=(("WAV audio", "*.wav"), ("MP3 audio", "*.mp3")),
        )
        if not path:
            return
        notes = list(self.current_notes)
        cache_key = self._live_playback_key(notes)
        self._export_busy = True
        self.save_button.configure(state="disabled", text="Saving…")
        self.status.set(f"Exporting {os.path.basename(path)}…")
        threading.Thread(target=self._export_worker,
                         args=(path, notes, cache_key), daemon=True).start()

    def _export_worker(self, path, notes, cache_key):
        try:
            audio = self._live_wet_cache.get(cache_key)
            if audio is None:
                dry = self.render(notes, preview=True, live=True)
                audio = self._process_live_macros(dry)
            self._write_audio_file(path, audio)
            self.root.after(0, lambda: self._finish_export(path))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._finish_export(None, e))

    def _finish_export(self, path, error=None):
        self._export_busy = False
        self.save_button.configure(state="normal", text="Export audio")
        if error is not None:
            messagebox.showerror("Export failed", str(error))
            return
        self.status.set(f"Saved {os.path.basename(path)}.")

    @staticmethod
    def _write_audio_file(path, audio):
        suffix = os.path.splitext(path)[1].lower()
        if suffix == ".wav":
            sf.write(path, audio, RATE, subtype="PCM_16")
            return
        if suffix != ".mp3":
            raise ValueError("Choose a .wav or .mp3 filename")
        descriptor, temporary = tempfile.mkstemp(prefix="figsynth-export-", suffix=".wav")
        os.close(descriptor)
        try:
            sf.write(temporary, audio, RATE, subtype="PCM_16")
            subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                 "-i", temporary, "-codec:a", "libmp3lame", "-q:a", "2", path],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    os.makedirs(IMPORTS, exist_ok=True)
    root = tk.Tk(className="FigLibSampler")
    App(root)
    root.mainloop()

