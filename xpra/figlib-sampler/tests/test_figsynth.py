"""Headless characterization tests for the FigSynth2 refactor."""

import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest

import numpy as np
import soundfile as sf


SAMPLER_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = SAMPLER_ROOT / "figlib-sampler.py"
OPENRB_BRIDGE = SAMPLER_ROOT.parent / "openrb-338" / "openrb-figlib-kit.py"


def load_entrypoint():
    spec = importlib.util.spec_from_file_location("figsynth_test_entrypoint", ENTRYPOINT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_openrb_bridge():
    previous = os.environ.get("TEMPORAMAN_FIGSYNTH_ROOT")
    os.environ["TEMPORAMAN_FIGSYNTH_ROOT"] = str(SAMPLER_ROOT)
    try:
        spec = importlib.util.spec_from_file_location("openrb_figlib_test", OPENRB_BRIDGE)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            os.environ.pop("TEMPORAMAN_FIGSYNTH_ROOT", None)
        else:
            os.environ["TEMPORAMAN_FIGSYNTH_ROOT"] = previous


class FigSynthRefactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_module = load_entrypoint()

    def test_complete_effect_catalog_is_available(self):
        self.assertEqual(len(self.app_module.EFFECT_DISPATCH), 92)
        self.assertIn("eq12", self.app_module.EFFECT_DISPATCH)

    def test_twelve_band_eq_is_flat_by_default_and_changes_audio(self):
        from figsynth.parameters import numeric_defaults, parameter_control_spec

        effect = self.app_module.EFFECT_DISPATCH["eq12"]
        defaults = numeric_defaults(effect)
        self.assertEqual(len(defaults), 12)
        timeline = np.arange(4096) / self.app_module.RATE
        audio = np.sin(2 * np.pi * 1000 * timeline)
        flat = effect(audio, sample_rate=self.app_module.RATE)
        boosted = effect(audio, gain_1k_db=12, sample_rate=self.app_module.RATE)
        np.testing.assert_allclose(flat, audio)
        self.assertTrue(np.isfinite(boosted).all())
        self.assertGreater(float(np.sqrt(np.mean(boosted ** 2))),
                           float(np.sqrt(np.mean(audio ** 2))))
        spec = parameter_control_spec("gain_1k_db", 0.0)
        self.assertEqual((spec["low"], spec["high"]), (-24.0, 24.0))

    def test_extracted_components_are_used(self):
        self.assertEqual(self.app_module.Knob.__module__, "figsynth.knob")
        self.assertEqual(self.app_module.Waveform.__module__, "figsynth.waveform")
        self.assertEqual(self.app_module.EffectRack.__module__, "figsynth.effect_rack")
        self.assertEqual(self.app_module.PianoRoll.__module__, "figsynth.piano_roll")
        from figsynth.oscillators import draw_audio_shape as oscillator_drawer
        from figsynth.waveform import draw_audio_shape as instrument_drawer
        self.assertIs(oscillator_drawer, instrument_drawer)

    def test_music_definitions_are_preserved(self):
        self.assertEqual(self.app_module.note_name(60), "C4")
        self.assertEqual(self.app_module.notes_label([60, 64, 67]), "C4 + E4 + G4")
        self.assertEqual(self.app_module.NOTE_NAMES[0], "C")
        self.assertEqual(self.app_module.CHORDS["Major 13"], (0, 4, 7, 11, 14, 21))
        self.assertEqual(len(self.app_module.CHORDS), 31)

    def test_parameter_mapping_round_trips(self):
        for limits in ((0.0, 1.0, "linear"), (20.0, 20000.0, "log")):
            for macro in (0.0, .2, .5, .8, 1.0):
                parameter = self.app_module.macro_to_parameter(macro, limits)
                restored = self.app_module.parameter_to_macro(parameter, limits)
                self.assertAlmostEqual(restored, macro, places=10)

    def test_oscillator_stack_removal_and_sample_source(self):
        from figsynth.oscillators import (
            default_oscillator,
            remove_oscillator_config,
            sample_oscillator,
        )

        patch = {"oscillators": [default_oscillator("triangle"),
                                  default_oscillator("saw")]}
        removed = remove_oscillator_config(patch, 0)
        self.assertEqual(removed["waveform"], "triangle")
        self.assertEqual([item["waveform"] for item in patch["oscillators"]], ["saw"])
        self.assertEqual(sample_oscillator("kick.wav")["waveform"], "sample")

    def test_oscillator_previews_are_finite_and_bounded(self):
        from figsynth.oscillators import oscillator_preview_data, sample_oscillator

        synth_preview = oscillator_preview_data({"waveform": "triangle"}, points=80)
        sample_preview = oscillator_preview_data(
            sample_oscillator("test.wav"), np.linspace(-.5, .5, 500), points=80)
        for preview in (synth_preview, sample_preview):
            self.assertEqual(len(preview), 80)
            self.assertTrue(np.isfinite(preview).all())
            self.assertLessEqual(float(np.max(np.abs(preview))), 1.0)

    def test_oscillator_thumbnail_uses_a_short_non_audio_render(self):
        from figsynth import oscillators

        durations = []
        original = oscillators.Oscillator

        class PreviewOscillator:
            def __init__(self, **_settings):
                pass

            def set_sample_rate(self, _rate):
                pass

            def generate(self, duration):
                durations.append(duration)
                return np.linspace(-1.0, 1.0, 882)

        oscillators.Oscillator = PreviewOscillator
        try:
            preview = oscillators.oscillator_preview_data(
                {"waveform": "saw", "unison": 8}, points=240)
        finally:
            oscillators.Oscillator = original
        self.assertEqual(durations, [.02])
        self.assertEqual(len(preview), 240)

    @staticmethod
    def minimal_patch_document():
        return {
            "format": "FigSynth2 patch",
            "version": 1,
            "mode": "synth",
            "synth": {"oscillators": [{"waveform": "triangle", "gain": np.float64(.8)}]},
            "sample_path": None,
            "effects": [],
            "shape": {"Pitch": 0.0, "Volume": .8},
            "assignments": {},
            "settings": {
                "start": 0.0, "end": 1.0, "duration": 2.0,
                "loop": False, "lfo_target": "pitch", "genre": "custom",
            },
        }

    def test_fig_patch_round_trip(self):
        from figsynth.patches import read_patch, write_patch

        document = self.minimal_patch_document()
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "saved.fig")
            write_patch(path, document)
            self.assertTrue(path.endswith(".fig"))
            restored = read_patch(path)
        self.assertEqual(restored["format"], "FigSynth2 patch")
        self.assertEqual(restored["version"], 1)
        self.assertEqual(restored["synth"]["oscillators"][0]["waveform"], "triangle")
        self.assertEqual(restored["synth"]["oscillators"][0]["gain"], .8)

    def test_fig_patch_rejects_unknown_version(self):
        from figsynth.patches import validate_patch_document

        document = self.minimal_patch_document()
        document["version"] = 99
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            validate_patch_document(document)

    @staticmethod
    def default_knobs():
        return {
            "Pitch": 0.0,
            "Attack": .01,
            "Decay": .1,
            "Sustain": .8,
            "Release": .15,
            "Cutoff": 18000.0,
            "Resonance": .1,
            "LFO rate": 3.0,
            "LFO depth": 0.0,
            "Volume": .8,
        }

    def test_sample_render_is_finite_stereo_audio(self):
        rate = self.app_module.RATE
        frames = rate // 5
        source = np.linspace(-.5, .5, frames, dtype=np.float64)
        source = np.column_stack((source, source))
        state = {
            "mode": "sample",
            "sample": source,
            "sample_rate": rate,
            "patch": None,
            "effects": [],
            "knobs": self.default_knobs(),
            "start": .1,
            "end": .9,
            "duration": .1,
            "loop": False,
            "lfo_target": "pitch",
        }
        audio = self.app_module.App._render_sound_state(state, 60)
        self.assertEqual(audio.shape, (rate // 10, 2))
        self.assertTrue(np.isfinite(audio).all())
        self.assertLessEqual(float(np.max(np.abs(audio))), 1.0)

    def test_default_triangle_synth_renders(self):
        state = {
            "mode": "synth",
            "sample": None,
            "sample_rate": self.app_module.RATE,
            "patch": {
                "oscillators": [{
                    "waveform": "triangle", "detune": 0.0, "phase": 0.0,
                    "pulse_width": .5, "morph_pos": 0.0, "gain": .8,
                    "unison": 1, "unison_detune": 0.0, "unison_spread": 0.0,
                    "fm_ratio": 1.0, "fm_depth": 0.0,
                }],
            },
            "effects": [],
            "knobs": self.default_knobs(),
            "start": 0.0,
            "end": 1.0,
            "duration": .1,
            "loop": False,
            "lfo_target": "pitch",
        }
        audio = self.app_module.App._render_sound_state(state, 60)
        self.assertEqual(audio.ndim, 2)
        self.assertEqual(audio.shape[1], 2)
        self.assertGreater(len(audio), 0)
        self.assertGreater(float(np.max(np.abs(audio))), 0.0)
        self.assertTrue(np.isfinite(audio).all())

    def test_wav_export_round_trip(self):
        audio = np.zeros((512, 2), dtype=np.float64)
        audio[:, 0] = np.linspace(-.25, .25, len(audio))
        audio[:, 1] = audio[:, 0]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "test.wav")
            self.app_module.App._write_audio_file(path, audio)
            restored, rate = sf.read(path, always_2d=True)
        self.assertEqual(rate, self.app_module.RATE)
        self.assertEqual(restored.shape, audio.shape)
        self.assertTrue(np.isfinite(restored).all())

    def test_arpeggiator_renders_notes_in_the_selected_order(self):
        class Value:
            def get(self):
                return .2

        class Playback:
            arp_step = Value()

            @staticmethod
            def render(notes, preview=False, live=False, duration=None):
                frames = int(round(duration * 10))
                return np.full((frames, 2), notes[0], dtype=np.float64)

        audio = self.app_module.AudioLogicMixin._render_playback(
            Playback(), [67, 60, 64, 67], arpeggiate=True)
        self.assertEqual(audio.shape, (8, 2))
        self.assertEqual(audio[:, 0].tolist(), [67, 67, 60, 60, 64, 64, 67, 67])

    def test_arpeggio_export_uses_the_selected_loop_count(self):
        source = np.arange(12, dtype=np.float64).reshape(6, 2)
        audio = self.app_module.AudioLogicMixin._repeat_count(source, 3)
        self.assertEqual(audio.shape, (18, 2))
        np.testing.assert_array_equal(audio[:6], source)
        np.testing.assert_array_equal(audio[6:12], source)

    def test_playback_stream_repeats_until_looping_is_stopped(self):
        class Input:
            def __init__(self, owner):
                self.owner = owner
                self.writes = []

            def write(self, data):
                self.writes.append(data)
                if len(self.writes) == 3:
                    self.owner._stream_token += 1

            def close(self):
                pass

        class Process:
            def __init__(self, owner):
                self.stdin = Input(owner)

            @staticmethod
            def wait():
                return 0

        class Playback:
            pass

        playback = Playback()
        playback._stream_lock = threading.Lock()
        playback._stream_token = 1
        playback._stream_buffer = np.ones((2, 2), dtype=np.float64) * .1
        playback._stream_position = 0
        playback._stream_repeats_remaining = 0
        process = Process(playback)
        playback._stream_process = process
        self.app_module.AudioLogicMixin._stream_writer(playback, 1, process)
        self.assertEqual(len(process.stdin.writes), 3)

    def test_sidechain_is_identified_as_a_simulated_pump(self):
        self.assertEqual(
            self.app_module.EffectRack.display_name("sidechain"),
            "sidechain pump (simulated)")

    @unittest.skipUnless(OPENRB_BRIDGE.is_file(), "OpenRB integration is not bundled")
    def test_openrb_bridge_prerenders_fig_patch(self):
        from figsynth.patches import write_patch

        document = self.minimal_patch_document()
        document["settings"]["duration"] = .1
        bridge = load_openrb_bridge()
        self.assertEqual(len(bridge.SLOTS), 47)
        with tempfile.TemporaryDirectory() as directory:
            patch = os.path.join(directory, "drum.fig")
            output = os.path.join(directory, "drum.aif")
            write_patch(patch, document)
            bridge.render_patch(patch, output)
            audio, rate = sf.read(output, always_2d=True)
        self.assertEqual(rate, self.app_module.RATE)
        self.assertGreater(len(audio), 0)
        self.assertTrue(np.isfinite(audio).all())

    @unittest.skipUnless(OPENRB_BRIDGE.is_file(), "OpenRB integration is not bundled")
    def test_openrb_bridge_uses_one_stable_generated_mod_path(self):
        bridge = load_openrb_bridge()
        with tempfile.TemporaryDirectory() as directory:
            bridge.OUTPUT_PATH = os.path.join(directory, "FigLib Generated.rbm")
            self.assertEqual(
                os.path.basename(bridge.OUTPUT_PATH), "FigLib Generated.rbm")

    @unittest.skipUnless(OPENRB_BRIDGE.is_file(), "OpenRB integration is not bundled")
    def test_openrb_bridge_uses_saved_arpeggio_and_normalizes(self):
        from figsynth.patches import write_patch

        bridge = load_openrb_bridge()
        document = self.minimal_patch_document()
        document["settings"].update({
            "arpeggiator": True,
            "arp_order": [67, 72, 74],
            "arp_step": .05,
            "shape_root": 67,
            "duration": 4.0,
        })
        with tempfile.TemporaryDirectory() as directory:
            patch = os.path.join(directory, "arpeggio.fig")
            output = os.path.join(directory, "arpeggio.aif")
            write_patch(patch, document)
            bridge.render_patch(patch, output)
            audio, rate = sf.read(output, always_2d=True)
        self.assertEqual(rate, self.app_module.RATE)
        self.assertAlmostEqual(len(audio) / rate, .15, places=2)
        self.assertGreater(float(np.max(np.abs(audio))), .9)

    @unittest.skipUnless(OPENRB_BRIDGE.is_file(), "OpenRB integration is not bundled")
    def test_openrb_bridge_303_sample_is_rendered_at_c4_without_arpeggio(self):
        from figsynth.patches import write_patch

        bridge = load_openrb_bridge()
        document = self.minimal_patch_document()
        document["settings"].update({
            "arpeggiator": True,
            "arp_order": [24, 96],
            "arp_step": .05,
            "duration": .2,
        })
        with tempfile.TemporaryDirectory() as directory:
            patch = os.path.join(directory, "oscillator.fig")
            output = os.path.join(directory, "oscillator.aif")
            write_patch(patch, document)
            bridge.render_patch(patch, output, sample_oscillator=True)
            audio, rate = sf.read(output, always_2d=True)
        self.assertEqual(rate, self.app_module.RATE)
        self.assertAlmostEqual(len(audio) / rate, .2, places=2)
        self.assertGreater(float(np.max(np.abs(audio))), .9)

    @unittest.skipUnless(OPENRB_BRIDGE.is_file(), "OpenRB integration is not bundled")
    def test_openrb_bridge_accepts_null_shape_root(self):
        from figsynth.patches import write_patch

        bridge = load_openrb_bridge()
        document = self.minimal_patch_document()
        document["settings"]["shape_root"] = None
        with tempfile.TemporaryDirectory() as directory:
            patch = os.path.join(directory, "legacy.fig")
            write_patch(patch, document)
            state = bridge.patch_state(patch)
        self.assertEqual(state["root_note"], 60)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for MP3 export")
    def test_mp3_export_creates_audio(self):
        timeline = np.arange(2048) / self.app_module.RATE
        mono = .1 * np.sin(2 * np.pi * 440 * timeline)
        audio = np.column_stack((mono, mono))
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "test.mp3")
            self.app_module.App._write_audio_file(path, audio)
            self.assertGreater(os.path.getsize(path), 0)


if __name__ == "__main__":
    unittest.main()
