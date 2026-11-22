"""Versioned `.fig` patch persistence for FigSynth2."""

import copy
import json
import os
import tempfile
import threading
from tkinter import filedialog, messagebox

import numpy as np
import soundfile as sf
from pySynth.routing import EFFECT_DISPATCH

from .oscillators import sample_oscillator
from .parameters import numeric_defaults
from .music import CHORDS

FORMAT_NAME = "FigSynth2 patch"
FORMAT_VERSION = 1
MAX_PATCH_BYTES = 2 * 1024 * 1024
RATE = 44100
IMPORTS = os.environ.get("TEMPORAMAN_IMPORTS", "/srv/audacity-studio/imports")
PATCH_DIRECTORY = os.environ.get("TEMPORAMAN_PATCHES", "/srv/audacity-studio/projects")


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def validate_patch_document(document):
    if not isinstance(document, dict):
        raise ValueError("Patch must contain a JSON object")
    if document.get("format") != FORMAT_NAME:
        raise ValueError("This is not a FigSynth2 patch")
    if document.get("version") != FORMAT_VERSION:
        raise ValueError(f"Unsupported FigSynth2 patch version: {document.get('version')!r}")
    if document.get("mode") not in ("synth", "sample"):
        raise ValueError("Patch mode must be synth or sample")
    if document.get("mode") == "synth" and not isinstance(document.get("synth"), dict):
        raise ValueError("Synth patch data is missing")
    if not isinstance(document.get("effects", []), list):
        raise ValueError("Patch effects must be a list")
    if len(document.get("effects", [])) > 256:
        raise ValueError("Patch contains too many effects")
    if not isinstance(document.get("shape", {}), dict):
        raise ValueError("Patch Shape values must be an object")
    if not isinstance(document.get("assignments", {}), dict):
        raise ValueError("Patch knob assignments must be an object")
    if not isinstance(document.get("settings", {}), dict):
        raise ValueError("Patch settings must be an object")
    return document


def read_patch(path):
    if os.path.getsize(path) > MAX_PATCH_BYTES:
        raise ValueError("Patch file is larger than 2 MB")
    with open(path, "r", encoding="utf-8") as patch_file:
        document = json.load(patch_file)
    return validate_patch_document(document)


def write_patch(path, document):
    validate_patch_document(document)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".figsynth-", suffix=".fig.tmp", dir=directory, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as patch_file:
            json.dump(document, patch_file, indent=2, sort_keys=True, default=_json_default)
            patch_file.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class PatchLogicMixin:
    """Save and restore complete reusable FigSynth2 sound configurations."""

    def patch_document(self):
        assignments = {}
        for knob_name, assignment in self.control_assignments.items():
            try:
                effect_index = next(
                    index for index, effect in enumerate(self.effects)
                    if effect is assignment["effect"])
            except StopIteration:
                continue
            assignments[knob_name] = {
                "effect_index": effect_index,
                "parameter": assignment["parameter"],
                "integer": bool(assignment.get("integer", False)),
            }
        return {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "mode": self.mode.get(),
            "synth": copy.deepcopy(self.patch),
            "sample_path": self.sample_path if self.mode.get() == "sample" else None,
            "effects": copy.deepcopy(self.effects),
            "shape": {name: knob.get() for name, knob in self.knobs.items()},
            "assignments": assignments,
            "settings": {
                "start": float(self.start),
                "end": float(self.end),
                "duration": float(self.duration.get()),
                "loop": bool(self.loop.get()),
                "loop_count": int(self.loop_count.get()),
                "arpeggiator": bool(self.arpeggiator.get()),
                "arp_step": float(self.arp_step.get()),
                "arp_order": list(self.arp_order),
                "keyboard_choice": self.keyboard_choice.get(),
                "custom_notes": sorted(self.custom_notes),
                "shape_root": self.shape_root,
                "octave": int(self.octave.get()),
                "range_shift": int(self.range_shift),
                "lfo_target": self.lfo_target.get(),
                "genre": self.genre.get(),
            },
        }

    def save_patch(self):
        initial = PATCH_DIRECTORY if os.path.isdir(PATCH_DIRECTORY) else os.path.expanduser("~")
        path = filedialog.asksaveasfilename(
            initialdir=initial,
            initialfile="figsynth_patch.fig",
            title="Save FigSynth2 patch",
            defaultextension=".fig",
            filetypes=(("FigSynth2 patches", "*.fig"), ("All files", "*")))
        if not path:
            return
        try:
            write_patch(path, self.patch_document())
            self.status.set(f"Saved patch {os.path.basename(path)}.")
        except Exception as error:
            messagebox.showerror("Could not save patch", str(error))

    def load_patch(self):
        initial = PATCH_DIRECTORY if os.path.isdir(PATCH_DIRECTORY) else os.path.expanduser("~")
        path = filedialog.askopenfilename(
            initialdir=initial,
            title="Load FigSynth2 patch",
            filetypes=(("FigSynth2 patches", "*.fig"), ("All files", "*")))
        if not path:
            return
        try:
            document = read_patch(path)
            self.apply_patch_document(document)
            self.status.set(f"Loaded patch {os.path.basename(path)}.")
        except Exception as error:
            messagebox.showerror("Could not load patch", str(error))

    def apply_patch_document(self, document):
        document = validate_patch_document(document)
        effects = copy.deepcopy(document.get("effects", []))
        for effect in effects:
            if not isinstance(effect, dict) or effect.get("type") not in EFFECT_DISPATCH:
                raise ValueError(f"Unknown effect in patch: {effect.get('type') if isinstance(effect, dict) else effect!r}")
            if not isinstance(effect.get("params", {}), dict):
                raise ValueError(f"Invalid parameters for {effect['type']}")
            effect["enabled"] = bool(effect.get("enabled", True))

        mode = document["mode"]
        sample = None
        sample_rate = RATE
        sample_path = None
        if mode == "sample":
            sample_path = document.get("sample_path")
            if not isinstance(sample_path, str) or not sample_path:
                raise ValueError("This sample patch has no sample-file reference")
            if not os.path.isfile(sample_path):
                raise ValueError(f"Referenced sample was not found: {sample_path}")
            sample, sample_rate = sf.read(sample_path, always_2d=True, dtype="float64")
            if len(sample) > sample_rate * 120:
                raise ValueError("Samples are limited to 2 minutes")

        settings = document.get("settings", {})
        start = max(0.0, min(1.0, float(settings.get("start", 0.0))))
        end = max(start + .005, min(1.0, float(settings.get("end", 1.0))))
        duration = max(.1, min(12.0, float(settings.get("duration", 2.0))))
        lfo_target = settings.get("lfo_target", "pitch")
        if lfo_target not in ("pitch", "volume", "filter"):
            raise ValueError(f"Invalid LFO target: {lfo_target!r}")

        self.stop_audio()
        self.clear_macro_assignments()
        for name in self.knobs:
            self._restore_main_knob(name)
        self.patch = (copy.deepcopy(document.get("synth")) if mode == "synth" else {
            "genre": "sample",
            "oscillators": [sample_oscillator(sample_path)],
            "effects": [],
            "envelope": {},
            "lfos": {},
        })
        self.effects = effects
        self.mode.set(mode)
        self.sample, self.sample_rate, self.sample_path = sample, sample_rate, sample_path
        self.start, self.end = start, end
        self.duration.set(duration)
        self.loop.set(bool(settings.get("loop", False)))
        self.loop_count.set(max(0, min(64, int(settings.get("loop_count", 2)))))
        self.arpeggiator.set(bool(settings.get("arpeggiator", False)))
        self.arp_step.set(max(.05, min(2.0, float(settings.get("arp_step", .25)))))
        choice = settings.get("keyboard_choice", "Single note")
        allowed_choices = {"Single note", "Custom chord", *
                           (f"Chord — {name}" for name in CHORDS)}
        if choice not in allowed_choices:
            choice = "Single note"
        self.keyboard_choice.set(choice)
        self.octave.set(max(0, min(8, int(settings.get("octave", 4)))))
        base = self.octave.get() * 12
        self.range_shift = max(-base, min(103 - base, int(settings.get("range_shift", 0))))
        self.custom_notes = {
            int(note) for note in settings.get("custom_notes", [])
            if isinstance(note, (int, float)) and 0 <= int(note) <= 127
        }
        saved_root = settings.get("shape_root")
        self.shape_root = (int(saved_root)
                           if isinstance(saved_root, (int, float)) and 0 <= int(saved_root) <= 127
                           else None)
        if choice == "Custom chord":
            self.play_mode.set("Custom chord")
            self.shape_notes.clear()
            self.current_notes = sorted(self.custom_notes) or [self.current_note]
        elif choice.startswith("Chord — "):
            chord = choice.removeprefix("Chord — ")
            self.play_mode.set("Chord shape")
            self.chord_type.set(chord)
            self.shape_notes = ({self.shape_root + interval for interval in CHORDS[chord]}
                                if self.shape_root is not None else set())
            self.current_notes = sorted(self.shape_notes) or [self.current_note]
        else:
            self.play_mode.set("Note")
            self.shape_notes.clear()
        raw_order = settings.get("arp_order", [])
        self.arp_order = [int(note) for note in raw_order
                          if isinstance(note, (int, float)) and 0 <= int(note) <= 127][:64]
        self.arp_capture = False
        self.update_arp_controls()
        self.lfo_target.set(lfo_target)
        genre = settings.get("genre")
        if genre in self.randomizer.genres:
            self.genre.set(genre)

        shape = document.get("shape", {})
        for name, knob in self.knobs.items():
            if name in shape:
                knob.set(float(shape[name]))
        self.sync_trim_knobs()

        self.control_assignments.clear()
        for knob_name, assignment in document.get("assignments", {}).items():
            if knob_name not in self.knobs or not isinstance(assignment, dict):
                continue
            effect_index = assignment.get("effect_index")
            if not isinstance(effect_index, int) or not 0 <= effect_index < len(self.effects):
                continue
            effect = self.effects[effect_index]
            parameter = assignment.get("parameter")
            defaults = numeric_defaults(EFFECT_DISPATCH[effect["type"]])
            default = defaults.get(parameter)
            if not isinstance(default, (int, float)) or isinstance(default, bool):
                continue
            self._assign_knob_target(knob_name, (effect, parameter, default))

        self.live_source = None
        self.live_effect_source = None
        self._live_dry_buffer = None
        self._live_wet_cache.clear()
        self.rack.refresh_chain()
        self.refresh_assignment_targets()
        self.refresh_oscillator_list()
        self.mode_changed()
        if mode == "sample":
            self.preview_data = sample
            self.source_label.configure(
                text=f"Sample: {os.path.basename(sample_path)}  •  {len(sample)/sample_rate:.2f}s  •  {sample_rate} Hz")
            self.wave.draw()
            self.schedule_waveform()
        else:
            oscillators = ", ".join(
                oscillator.get("waveform", "?")
                for oscillator in (self.patch or {}).get("oscillators", []))
            self.source_label.configure(text=oscillators or "mixed")
            threading.Thread(target=self._update_synth_preview, daemon=True).start()
