#!/usr/bin/env python3
"""FigSynth2: an easy instrument front-end for the complete FigLib engine."""
import inspect
import math
import os
import copy
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
FIGLIB_ROOT = os.path.join(HERE, "figlib52")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FIGLIB_ROOT, "src"))

import numpy as np
import soundfile as sf
from pySynth.generator import Randomizer
from pySynth.modulation import Envelope
from pySynth.oscillator import Oscillator
from pySynth.routing import EFFECT_DISPATCH
from pySynth.synth import FiggyGenSynth

from figsynth.audio_logic import AudioLogicMixin
from figsynth.effect_rack import EffectRack
from figsynth.knob import Knob
from figsynth.music import CHORDS, KEY_NOTES, NOTE_NAMES, note_name, notes_label
from figsynth.oscillators import (
    OscillatorForm,
    default_oscillator,
    remove_oscillator_config,
    sample_oscillator,
)
from figsynth.parameters import (
    macro_to_parameter,
    numeric_defaults,
    parameter_control_spec,
    parameter_range,
    parameter_to_macro,
)
from figsynth.piano_roll import PianoRoll
from figsynth.piano_logic import PianoRollLogicMixin
from figsynth.patches import PatchLogicMixin
from figsynth.waveform import Waveform

RATE = 44100
IMPORTS = os.environ.get("TEMPORAMAN_IMPORTS", "/srv/audacity-studio/imports")
EXPORTS = os.environ.get("TEMPORAMAN_EXPORTS", "/srv/audacity-studio/exports")
PULSE_SINK = os.environ.get("PULSE_SINK", "studio")
class App(PatchLogicMixin, PianoRollLogicMixin, AudioLogicMixin):
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
        self._osc_visual_after = None
        self.osc_form = None
        self._knob_assignment_menu = None
        self._knob_menu_click_binding = None
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
        self._stream_repeats_remaining = 1
        self._stream_token = 0
        self._live_wet_cache = {}
        self._export_busy = False
        self.randomizer = Randomizer(os.path.join(FIGLIB_ROOT, "presets"),
                                     os.path.join(FIGLIB_ROOT, "fxpresets"))
        self.mode = tk.StringVar(value="synth")
        self.genre = tk.StringVar(value="keys")
        self.loop = tk.BooleanVar(value=False)
        self.loop_count = tk.IntVar(value=2)
        self.status = tk.StringVar(value="Ready. Make a sound or load a WAV.")
        self.current_note = 60
        self.current_notes = [60]
        self.chord_type = tk.StringVar(value="Major")
        self.play_mode = tk.StringVar(value="Note")
        self.keyboard_choice = tk.StringVar(value="Single note")
        self.arpeggiator = tk.BooleanVar(value=False)
        self.arp_step = tk.DoubleVar(value=.25)
        self.arp_order = []
        self.arp_capture = False
        self.arp_order_text = tk.StringVar(value="Order: —")
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
        tk.Button(top, text="Load patch…", command=self.load_patch).pack(side="left", padx=3)
        tk.Button(top, text="Save patch…", command=self.save_patch).pack(side="left", padx=3)
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
        tk.Checkbutton(
            options, text="Loop playback", variable=self.loop,
            command=self.loop_changed, bg="#d7d7d7").pack(side="left")
        tk.Label(options, text="×", bg="#d7d7d7").pack(side="left", padx=(4, 1))
        loop_count = tk.Spinbox(
            options, from_=0, to=64, increment=1, width=3,
            textvariable=self.loop_count, command=self.loop_changed)
        loop_count.pack(side="left")
        loop_count.bind("<Return>", lambda _event: self.loop_changed())
        loop_count.bind("<FocusOut>", lambda _event: self.loop_changed())
        tk.Label(options, text="(0 = forever)", bg="#d7d7d7", fg="#555").pack(
            side="left", padx=(2, 0))
        tk.Button(options, text="Stop", command=self.stop_audio).pack(side="left", padx=(4, 0))
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

        arpbar = tk.Frame(main, bg="#d7d7d7")
        arpbar.pack(fill="x", padx=10, pady=(0, 2))
        tk.Checkbutton(
            arpbar, text="Arpeggiator", variable=self.arpeggiator,
            command=self.arpeggiator_changed, bg="#d7d7d7").pack(side="left")
        self.arp_order_button = tk.Button(
            arpbar, text="Set note order", command=self.begin_arp_order)
        self.arp_order_button.pack(side="left", padx=(8, 3))
        self.arp_play_button = tk.Button(
            arpbar, text="Play arpeggio", command=self.play_arpeggio)
        self.arp_play_button.pack(side="left", padx=3)
        tk.Button(arpbar, text="Clear order", command=self.clear_arp_order).pack(
            side="left", padx=3)
        tk.Label(arpbar, text="Step", bg="#d7d7d7").pack(side="left", padx=(12, 2))
        tk.Spinbox(
            arpbar, from_=.05, to=2.0, increment=.05, width=5,
            textvariable=self.arp_step).pack(side="left")
        tk.Label(arpbar, text="seconds", bg="#d7d7d7").pack(side="left", padx=(2, 10))
        tk.Label(arpbar, textvariable=self.arp_order_text,
                 bg="#d7d7d7", fg="#333").pack(side="left")

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
            self.osc_list.selection_clear(0, "end")
            self.osc_list.selection_set(select)
            self.osc_list.activate(select)
            self.osc_list.see(select)
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
        is_sample = config.get("waveform") == "sample"
        heading = "Sample oscillator" if is_sample else "Oscillator"
        tk.Label(self.osc_editor, text=f"{heading} {index + 1}",
                 bg="#d7d7d7", font=("Sans", 12, "bold")).grid(
                     row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.osc_form = OscillatorForm(self.osc_editor)
        self.osc_form.grid(row=1, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 8))
        self.osc_editor.grid_columnconfigure(3, weight=1)
        self.osc_form.show(config, self.sample if is_sample else None)
        tk.Label(self.osc_editor, text="Waveform", bg="#d7d7d7").grid(
            row=2, column=0, sticky="e", padx=5)
        waveform = tk.StringVar(value=config.get("waveform", "sine"))
        waveforms = ("sample",) if is_sample else tuple(
            w for w in Oscillator.WAVEFORMS if w != "sample")
        box = ttk.Combobox(self.osc_editor, textvariable=waveform,
                           values=waveforms, state="disabled" if is_sample else "readonly",
                           width=18)
        box.grid(row=2, column=1, sticky="w", padx=5)
        box.bind("<<ComboboxSelected>>",
                 lambda _event, c=config, v=waveform:
                 self.set_oscillator_parameter(c, "waveform", v.get()))

        if is_sample:
            tk.Label(self.osc_editor,
                     text=os.path.basename(config.get("sample_name", "Loaded sample")),
                     bg="#d7d7d7", fg="#444").grid(
                         row=3, column=0, columnspan=4, sticky="w", padx=5, pady=8)
            return

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
            knob.grid(row=row + 3, column=column, padx=5, pady=4)

    def set_oscillator_parameter(self, config, name, value):
        config[name] = value
        self.oscillator_changed()

    def oscillator_changed(self):
        self._live_dry_buffer = None
        self._live_wet_cache.clear()
        # The selected-source waveform is cheap, so keep it responsive while
        # dragging. Never rebuild the editor here: destroying the knob under an
        # active pointer grab caused the remote UI to stutter and skip events.
        if self._osc_visual_after is None:
            self._osc_visual_after = self.root.after(24, self._refresh_oscillator_visual)
        if self._osc_after is not None:
            try:
                self.root.after_cancel(self._osc_after)
            except tk.TclError:
                pass
        # The Instrument waveform and any sounding preview use the full synth.
        # Debounce that work until the user pauses instead of launching it for
        # every pixel of knob motion.
        self._osc_after = self.root.after(325, self._refresh_oscillator_preview)

    def _refresh_oscillator_visual(self):
        self._osc_visual_after = None
        index, config = self.selected_oscillator()
        if config is None:
            return
        if self.osc_form is not None and self.osc_form.winfo_exists():
            sample = self.sample if config.get("waveform") == "sample" else None
            self.osc_form.show(config, sample)

    def _refresh_oscillator_preview(self):
        self._osc_after = None
        oscillators = (self.patch or {}).get("oscillators", [])
        if self.mode.get() == "synth" and oscillators:
            self.source_label.configure(
                text=", ".join(item.get("waveform", "?") for item in oscillators))
            self.schedule_waveform()
            self.schedule_live_refresh()

    def add_oscillator(self):
        if not self.patch:
            self.blank_synth()
        if self.mode.get() == "sample":
            self.mode.set("synth")
            self.sample = None
            self.sample_path = None
            self.patch = {"genre": "custom", "oscillators": [], "effects": [],
                          "envelope": {}, "lfos": {}}
        config = default_oscillator()
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
            self.status.set("Select an oscillator to remove.")
            return
        if self._osc_after is not None:
            try:
                self.root.after_cancel(self._osc_after)
            except tk.TclError:
                pass
            self._osc_after = None
        removed = remove_oscillator_config(self.patch, index)
        if removed is None:
            self.status.set("That oscillator is no longer in the stack.")
            return
        remaining = self.patch.get("oscillators", [])
        if (removed.get("waveform") == "sample"
                and not any(item.get("waveform") == "sample" for item in remaining)):
            self.sample = None
            self.sample_path = None
            self.sample_rate = RATE
            self.mode.set("synth")
        self.stop_audio()
        self.live_source = None
        self.live_effect_source = None
        self._live_dry_buffer = None
        self._live_wet_cache.clear()
        self.refresh_oscillator_list(max(0, index - 1))
        if remaining:
            self.source_label.configure(
                text=", ".join(item.get("waveform", "?") for item in remaining))
            self.status.set(f"Removed {removed.get('waveform', 'oscillator')} oscillator.")
            self._osc_after = self.root.after(50, self._refresh_oscillator_preview)
        else:
            self.preview_data = None
            self.source_label.configure(text="No oscillators")
            self.wave.draw()
            self.status.set("Oscillator removed. Add one to make sound.")

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
            "oscillators": [default_oscillator("triangle")],
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
        self.loop_count.set(2)
        self.lfo_target.set("pitch")
        self.keyboard_choice.set("Single note")
        self.arpeggiator.set(False)
        self.arp_step.set(.25)
        self.arp_order.clear()
        self.arp_capture = False
        self.update_arp_controls()
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
            order = self.arp_positions(midi)
            text = note_name(midi) + (f"\n{order}" if order else "")
            b = tk.Button(frame, text=text,
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
                order = self.arp_positions(midi)
                text = NOTE_NAMES[midi % 12] + (f"\n{order}" if order else "")
                b = tk.Button(frame, text=text,
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
        self.arp_order.clear()
        self.arp_capture = False
        self.update_arp_controls()
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

    def chord_notes(self):
        if self.play_mode.get() == "Chord shape":
            return set(self.shape_notes)
        if self.play_mode.get() == "Custom chord":
            return set(self.custom_notes)
        return {self.current_note}

    def arp_positions(self, midi):
        positions = [str(index + 1) for index, note in enumerate(self.arp_order)
                     if note == midi]
        return ",".join(positions)

    def update_arp_controls(self):
        if not hasattr(self, "arp_order_button"):
            return
        enabled = bool(self.arpeggiator.get())
        state = "normal" if enabled else "disabled"
        self.arp_order_button.configure(
            state=state, text="Done ordering" if self.arp_capture else "Set note order")
        self.arp_play_button.configure(state=state)
        label = " → ".join(note_name(note) for note in self.arp_order) or "—"
        self.arp_order_text.set(f"Order: {label}")

    def arpeggiator_changed(self):
        if not self.arpeggiator.get():
            self.arp_capture = False
            self.status.set("Arpeggiator off.")
        else:
            self.status.set("Choose a chord, then set its note order.")
        self._live_wet_cache.clear()
        self.update_arp_controls()
        self.redraw_keyboard()

    def loop_changed(self):
        try:
            count = max(0, min(64, int(self.loop_count.get())))
        except (tk.TclError, ValueError):
            count = 2
        self.loop_count.set(count)
        with self._stream_lock:
            self._stream_repeats_remaining = (0 if count == 0 else count) if self.loop.get() else 1
        self._live_wet_cache.clear()
        self.schedule_waveform()
        if not self.loop.get():
            self.status.set("Playback looping off.")
        elif count == 0:
            self.status.set("Playback will loop until Stop; export will contain one pass.")
        else:
            self.status.set(f"Playback and arpeggio export will use {count} passes.")

    def clear_arp_order(self):
        self.arp_order.clear()
        self.arp_capture = False
        self.update_arp_controls()
        self.redraw_keyboard()
        self.status.set("Arpeggio order cleared.")

    def begin_arp_order(self):
        if not self.arpeggiator.get():
            return
        if self.arp_capture:
            self.arp_capture = False
            self.update_arp_controls()
            self.status.set("Arpeggio order finished. Press Play arpeggio.")
            return
        available = self.chord_notes()
        if self.play_mode.get() == "Chord shape" and self.shape_root is None:
            self.status.set("Click a root key first, then click chord notes in playback order.")
            return
        if self.play_mode.get() == "Custom chord" and not self.custom_notes:
            self.status.set("Choose custom chord notes first, then set their playback order.")
            return
        if self.play_mode.get() == "Note" or len(available) < 2:
            self.status.set("Choose a chord or custom chord before setting an arpeggio order.")
            return
        self.arp_order.clear()
        self.arp_capture = True
        self.update_arp_controls()
        self.redraw_keyboard()
        self.status.set("Click highlighted chord keys in the order they should play; repeats are allowed.")

    def play_arpeggio(self):
        if not self.arpeggiator.get() or not self.arp_order:
            self.status.set("Set an arpeggio note order first.")
            return
        self.arp_capture = False
        self.update_arp_controls()
        self.play(list(self.arp_order), arpeggiate=True)

    def chord_shape_changed(self):
        if self.shape_root is None:
            return
        self.arp_order.clear()
        self.arp_capture = False
        self.update_arp_controls()
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
        self.clear_arp_order()
        self.current_notes = [self.current_note]
        self.redraw_keyboard()
        self.status.set("Custom chord cleared. Click any notes you want.")

    def trigger_key(self, midi):
        mode = self.play_mode.get()
        self.current_note = midi
        if self.arp_capture:
            if midi not in self.chord_notes():
                self.status.set("That key is not part of the selected chord.")
                return
            self.arp_order.append(midi)
            self.update_arp_controls()
            self.redraw_keyboard()
            self.status.set(
                f"Arpeggio step {len(self.arp_order)}: {note_name(midi)}. "
                "Add another note or press Done ordering.")
            return
        if mode == "Note":
            notes = [midi]
        elif mode == "Chord shape":
            notes = [midi + interval for interval in CHORDS[self.chord_type.get()]]
            self.shape_root = midi
            self.shape_notes = set(notes)
            if self.arpeggiator.get():
                self.arp_order.clear()
                self.arp_capture = True
                self.update_arp_controls()
                self.redraw_keyboard()
                self.chord_help.configure(text=self.shape_description())
                self.status.set(
                    "Root selected. Click highlighted chord keys in arpeggio order; repeats are allowed.")
                return
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
            arpeggiate = bool(self.arpeggiator.get() and self.arp_order)
            play_notes = list(self.arp_order) if arpeggiate else notes
            dry = self._render_playback(play_notes, arpeggiate)
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
        self.dismiss_knob_assignment_menu()
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(
            label=f"Default: {self.knob_specs[name]['label']}",
            command=lambda: self._choose_knob_assignment(name, None))
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
                    self._choose_knob_assignment(name, target))
            menu.add_cascade(label=f"{effect_index}. {effect['type']}", menu=submenu)
        if not active:
            menu.add_command(label="No active numeric effects", state="disabled")
        self._knob_assignment_menu = menu
        menu.post(event.x_root, event.y_root)
        self._knob_menu_click_binding = self.root.bind(
            "<ButtonPress-1>", self.dismiss_knob_assignment_menu, add="+")

    def dismiss_knob_assignment_menu(self, _event=None):
        """Close the assignment popup without consuming the outside click."""
        menu = self._knob_assignment_menu
        self._knob_assignment_menu = None
        if menu is not None:
            try:
                menu.unpost()
                menu.destroy()
            except tk.TclError:
                pass
        binding = self._knob_menu_click_binding
        self._knob_menu_click_binding = None
        if binding is not None:
            try:
                self.root.unbind("<ButtonPress-1>", binding)
            except tk.TclError:
                pass

    def _choose_knob_assignment(self, name, target):
        self.dismiss_knob_assignment_menu()
        self._assign_knob_target(name, target)

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
            self.preview_data = data
            self.patch = {
                "genre": "sample",
                "oscillators": [sample_oscillator(path)],
                "effects": [],
                "envelope": {},
                "lfos": {},
            }
            self.mode.set("sample")
            self.start, self.end = 0, 1
            self.sync_trim_knobs()
            self.source_label.configure(text=f"Sample: {os.path.basename(path)}  •  {len(data)/sr:.2f}s  •  {sr} Hz")
            self.refresh_oscillator_list()
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



if __name__ == "__main__":
    os.makedirs(IMPORTS, exist_ok=True)
    root = tk.Tk(className="FigLibSampler")
    App(root)
    root.mainloop()

