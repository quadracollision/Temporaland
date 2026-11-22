"""Retained piano-roll state, rendering, playback, and export behavior."""

import copy
import inspect
import os
import threading
import time
from tkinter import filedialog, messagebox

import numpy as np
import soundfile as sf
from pySynth.modulation import Envelope
from pySynth.routing import EFFECT_DISPATCH
from pySynth.synth import FiggyGenSynth

from .music import note_name
from .parameters import numeric_defaults, parameter_control_spec

RATE = 44100
EXPORTS = os.environ.get("TEMPORAMAN_EXPORTS", "/srv/audacity-studio/exports")


class PianoRollLogicMixin:
    """Piano-roll behavior kept callable while its tab is disabled."""

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
            self._stream_repeats_remaining = 1
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
