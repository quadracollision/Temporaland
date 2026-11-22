"""Rendering, realtime playback, and file export behavior for FigSynth2."""

import copy
import inspect
import math
import os
import subprocess
import tempfile
import threading
import time
from tkinter import filedialog, messagebox

import numpy as np
import soundfile as sf
from pySynth.modulation import Envelope
from pySynth.routing import EFFECT_DISPATCH
from pySynth.synth import FiggyGenSynth

from .music import note_name, notes_label

RATE = 44100
EXPORTS = os.environ.get("TEMPORAMAN_EXPORTS", "/srv/audacity-studio/exports")
PULSE_SINK = os.environ.get("PULSE_SINK", "studio")


class AudioLogicMixin:
    """Render notes, stream them to PulseAudio, and export WAV or MP3 files."""

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

    def render(self, notes, preview=False, live=False, duration=None):
        notes = [notes] if np.isscalar(notes) else list(notes)
        preview_duration = duration
        if preview_duration is None and preview and not live:
            preview_duration = min(.25, max(.05, float(self.duration.get())))
        if self.mode.get() == "sample":
            audio = self._sampler_audio(notes, preview_duration)
        elif live:
            audio = self._synth_audio(notes, duration)
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

    def _render_playback(self, notes, arpeggiate=False):
        if not arpeggiate:
            return self.render(notes, preview=True, live=True)
        step = max(.05, min(2.0, float(self.arp_step.get())))
        rendered = [self.render([note], preview=True, live=True, duration=step)
                    for note in notes]
        if not rendered:
            raise ValueError("Set an arpeggio note order first")
        return np.concatenate(rendered, axis=0)

    @staticmethod
    def _repeat_count(audio, count):
        count = max(1, int(count))
        return np.tile(audio, (count, 1)) if len(audio) else audio

    def play(self, notes, arpeggiate=False):
        notes = [int(notes)] if np.isscalar(notes) else [int(n) for n in notes]
        self.current_note = notes[0]
        if not arpeggiate:
            self.current_notes = notes
        label = notes_label(notes)
        cache_key = self._live_playback_key(notes, arpeggiate)
        self.status.set(f"Playing {'arpeggio ' if arpeggiate else ''}{label}…")
        threading.Thread(target=self._play_worker,
                         args=(notes, cache_key, arpeggiate), daemon=True).start()

    def _live_playback_key(self, notes, arpeggiate=False):
        return (
            tuple(notes), self.mode.get(), id(self.sample), self.sample_path,
            self.sample_rate, self.start, self.end, float(self.duration.get()),
            bool(self.loop.get()), self.lfo_target.get(),
            bool(arpeggiate), float(self.arp_step.get()) if arpeggiate else None,
            tuple((name, knob.get()) for name, knob in self.knobs.items()),
            repr(self.patch), repr(self.effects),
        )

    def _play_worker(self, notes, cache_key, arpeggiate=False):
        try:
            dry = self._render_playback(notes, arpeggiate)
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
                f"Live: {'arpeggio • ' if arpeggiate else ''}{notes_label(notes)} • "
                f"{active} active rack effect(s)"))
        except Exception as exc:
            self.root.after(0, lambda e=exc: messagebox.showerror("Playback failed", str(e)))

    def _start_stream(self, audio, repeats=None):
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
            if repeats is None:
                selected = max(0, min(64, int(self.loop_count.get())))
                repeats = (0 if selected == 0 else selected) if self.loop.get() else 1
            self._stream_repeats_remaining = max(0, int(repeats))
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
                    if audio is None or not len(audio):
                        break
                    if position >= len(audio):
                        if self._stream_repeats_remaining == 1:
                            break
                        if self._stream_repeats_remaining > 1:
                            self._stream_repeats_remaining -= 1
                        position = 0
                        self._stream_position = 0
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
        arpeggiate = bool(self.arpeggiator.get() and self.arp_order)
        notes = list(self.arp_order if arpeggiate else self.current_notes)
        cache_key = self._live_playback_key(notes, arpeggiate)
        selected_loops = max(0, min(64, int(self.loop_count.get())))
        export_loops = (selected_loops if selected_loops > 0 else 1) if (
            arpeggiate and self.loop.get()) else 1
        self._export_busy = True
        self.save_button.configure(state="disabled", text="Saving…")
        self.status.set(f"Exporting {os.path.basename(path)}…")
        threading.Thread(target=self._export_worker,
                         args=(path, notes, cache_key, arpeggiate,
                               export_loops), daemon=True).start()

    def _export_worker(self, path, notes, cache_key, arpeggiate=False,
                       export_loops=1):
        try:
            audio = self._live_wet_cache.get(cache_key)
            if audio is None:
                dry = self._render_playback(notes, arpeggiate)
                if export_loops > 1:
                    dry = self._repeat_count(dry, export_loops)
                audio = self._process_live_macros(dry)
            elif export_loops > 1:
                audio = self._repeat_count(audio, export_loops)
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
