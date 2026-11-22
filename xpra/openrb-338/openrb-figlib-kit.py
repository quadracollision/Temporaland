#!/usr/bin/env python3
"""OpenRB-owned UI that pre-renders FigLib patches into an RB-338 mod kit."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
import soundfile as sf

FIGSYNTH_ROOT = os.environ.get(
    "TEMPORAMAN_FIGSYNTH_ROOT", "/usr/local/share/temporaman/figlib-sampler")
FIGLIB_ROOT = os.path.join(FIGSYNTH_ROOT, "figlib52")
sys.path.insert(0, FIGSYNTH_ROOT)
sys.path.insert(0, os.path.join(FIGLIB_ROOT, "src"))

from figsynth.patches import read_patch  # noqa: E402
from figsynth.piano_logic import PianoRollLogicMixin  # noqa: E402


RATE = 44100
PROJECT_ROOT = os.environ.get(
    "TEMPORAMAN_OPENRB_PROJECTS", "/srv/audacity-studio/projects/OpenRB-338")
PATCH_ROOT = os.environ.get("TEMPORAMAN_PATCHES", "/srv/audacity-studio/projects")
MODS_ROOT = os.path.join(PROJECT_ROOT, "Mods")
MAPPING_PATH = os.path.join(PROJECT_ROOT, "figlib-kit.json")
OUTPUT_PATH = os.path.join(MODS_ROOT, "FigLib Generated.rbm")
TEMPLATE_ROOT = os.environ.get(
    "TEMPORAMAN_OPENRB_TEMPLATE", "/usr/local/share/openrb-338/standard-template")
ORB = os.environ.get("TEMPORAMAN_ORB", "/usr/local/bin/orb")
OPEN_APP = os.environ.get(
    "TEMPORAMAN_OPEN_APP", "/usr/local/libexec/audacity-studio-open-app")

SLOTS = (
    "FIG303A.aif", "FIG303B.aif",
    "TR808BD.aif", "TR808SD1.aif", "TR808SD2.aif", "TR808SD3.aif",
    "TR808SD4.aif", "TR808SD5.aif", "TR808N1.aif", "TR808N2.aif",
    "TR808N3.aif", "TR808N4.aif", "TR808CB.aif", "TR808CH.aif",
    "TR808CL.aif", "TR808CP.aif", "TR808CY.aif", "TR808HC.aif",
    "TR808HT.aif", "TR808LC.aif", "TR808LT.aif", "TR808MA.aif",
    "TR808MC.aif", "TR808MT.aif", "TR808OH.aif", "TR808RS.aif",
    "TR909bd1.aif", "TR909bd2.aif", "TR909bd3.aif", "TR909bd4.aif",
    "TR909sd1.aif", "TR909sd2.aif", "TR909sd3.aif", "TR909sd4.aif",
    "TR909sd5.aif", "TR909sdn1.aif", "TR909sdn2.aif", "TR909sdn3.aif",
    "TR909lt.aif", "TR909mt.aif", "TR909ht.aif", "TR909rs.aif",
    "TR909hc.aif", "TR909chh.aif", "TR909ohh.aif", "TR909ccy.aif",
    "TR909rcy.aif",
)

SLOT_LABELS = {
    "FIG303A.aif": "303 A sample oscillator",
    "FIG303B.aif": "303 B sample oscillator",
}

DEFAULT_KNOBS = {
    "Pitch": 0.0, "Attack": .01, "Decay": .1, "Sustain": .8,
    "Release": .15, "Cutoff": 18000.0, "Resonance": .1,
    "LFO rate": 3.0, "LFO depth": 0.0, "Volume": .8,
}


def number(value, default, cast=float):
    """Reads a numeric patch field while accepting null/legacy values."""
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def load_mapping():
    try:
        with open(MAPPING_PATH, "r", encoding="utf-8") as mapping_file:
            value = json.load(mapping_file)
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        return {}
    return {slot: path for slot, path in value.items()
            if slot in SLOTS and isinstance(path, str)}


def save_mapping(mapping):
    os.makedirs(PROJECT_ROOT, exist_ok=True)
    temporary = MAPPING_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as mapping_file:
        json.dump(mapping, mapping_file, indent=2, sort_keys=True)
        mapping_file.write("\n")
    os.replace(temporary, MAPPING_PATH)


def patch_state(path):
    document = read_patch(path)
    settings = document.get("settings", {})
    knobs = dict(DEFAULT_KNOBS)
    knobs.update({name: number(value, knobs[name])
                  for name, value in document.get("shape", {}).items()
                  if name in knobs})
    mode = document["mode"]
    sample = None
    sample_rate = RATE
    sample_path = None
    if mode == "sample":
        sample_path = document.get("sample_path")
        if not sample_path or not os.path.isfile(sample_path):
            raise ValueError(f"Referenced sample was not found: {sample_path}")
        sample, sample_rate = sf.read(
            sample_path, always_2d=True, dtype="float64")
    return {
        "mode": mode,
        "sample": sample,
        "sample_rate": sample_rate,
        "sample_path": sample_path,
        "patch": document.get("synth"),
        "effects": document.get("effects", []),
        "knobs": knobs,
        "start": number(settings.get("start"), 0.0),
        "end": number(settings.get("end"), 1.0),
        "duration": min(8.0, max(.05, number(settings.get("duration"), 2.0))),
        "loop": bool(settings.get("loop", False)),
        "lfo_target": settings.get("lfo_target", "pitch"),
        "root_note": max(0, min(127, number(settings.get("shape_root"), 60, int))),
        "arpeggiator": bool(settings.get("arpeggiator", False)),
        "arp_order": [max(0, min(127, number(note, 60, int)))
                      for note in (settings.get("arp_order") or [])],
        "arp_step": max(.05, min(2.0, number(settings.get("arp_step"), .2))),
    }


def render_patch(path, output, sample_oscillator=False):
    state = patch_state(path)
    if sample_oscillator:
        audio = PianoRollLogicMixin._render_sound_state(state, 60)
    elif state["arpeggiator"] and state["arp_order"]:
        hits = []
        for note in state["arp_order"]:
            hit_state = dict(state)
            hit_state["duration"] = state["arp_step"]
            hits.append(PianoRollLogicMixin._render_sound_state(hit_state, note))
        audio = np.concatenate(hits, axis=0)
    else:
        audio = PianoRollLogicMixin._render_sound_state(
            state, state["root_note"])
    audio = audio[:8 * RATE]
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    mono = np.nan_to_num(mono)
    peak = float(np.max(np.abs(mono))) if len(mono) else 0.0
    if peak > 0:
        mono *= .95 / peak
    sf.write(output, mono, RATE, format="AIFF", subtype="PCM_16")


def build_kit(mapping):
    if not os.path.isdir(TEMPLATE_ROOT):
        raise RuntimeError("The OpenRB standard-kit template is not installed")
    if not os.path.isfile(ORB):
        raise RuntimeError("The orb kit tool is not installed")
    os.makedirs(MODS_ROOT, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="openrb-figlib-", dir=PROJECT_ROOT) as work:
        source = os.path.join(work, "kit")
        shutil.copytree(TEMPLATE_ROOT, source)
        manifest = os.path.join(source, "mod.toml")
        with open(manifest, "r", encoding="utf-8") as manifest_file:
            text = manifest_file.read()
        text = re.sub(r'^name = ".*"$', 'name = "FigLib Generated"', text,
                      count=1, flags=re.MULTILINE)
        text = re.sub(
            r'^description = """.*?"""$',
            'description = """Drum and 303 oscillator samples pre-rendered from '
            'FigSynth2 .fig patches.\r\nUnassigned slots retain the stock sound."""',
            text, count=1, flags=re.MULTILINE | re.DOTALL)
        custom_slots = [slot for slot in ("FIG303A.aif", "FIG303B.aif")
                        if slot in mapping]
        if custom_slots:
            entries = "".join(f'    "{slot}",\n' for slot in custom_slots)
            text = re.sub(r'\n\]\s*$', f'\n{entries}]\n', text, count=1)
        with open(manifest, "w", encoding="utf-8") as manifest_file:
            manifest_file.write(text)
        for slot, patch_path in mapping.items():
            if slot in SLOTS:
                render_patch(
                    patch_path, os.path.join(source, slot),
                    sample_oscillator=slot.startswith("FIG303"))
        temporary = os.path.join(work, "FigLib Generated.rbm")
        subprocess.run([ORB, "mod", "pack", source, "-o", temporary],
                       check=True, capture_output=True, text=True)
        os.replace(temporary, OUTPUT_PATH)
    # Remove files made by the older alternating-path reload workaround.
    for stale in (".figlib-generated-a.rbm", ".figlib-generated-b.rbm"):
        try:
            os.unlink(os.path.join(MODS_ROOT, stale))
        except FileNotFoundError:
            pass
    return OUTPUT_PATH


class KitBuilder:
    def __init__(self, root):
        self.root = root
        self.root.title("OpenRB-338 — FigLib Kit")
        self.root.geometry("850x650")
        self.root.configure(bg="#d7d7d7")
        self.mapping = load_mapping()
        self.status = tk.StringVar(value="Assign .fig patches, then build the kit.")
        self.rows = tk.Listbox(root, exportselection=False, font=("Monospace", 10))
        self.rows.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.rows.bind("<Double-Button-1>", lambda _event: self.assign_patch())
        buttons = tk.Frame(root, bg="#d7d7d7")
        buttons.pack(fill="x", padx=10, pady=5)
        tk.Button(buttons, text="Assign .fig…", command=self.assign_patch).pack(side="left")
        tk.Button(buttons, text="Use stock", command=self.use_stock).pack(side="left", padx=4)
        tk.Button(buttons, text="Open FigSynth2", command=self.open_figsynth).pack(side="left", padx=4)
        self.build_button = tk.Button(
            buttons, text="Build FigLib kit", command=self.build, bg="#d8f2d8",
            font=("Sans", 10, "bold"))
        self.build_button.pack(side="right")
        tk.Label(root, textvariable=self.status, anchor="w", bg="#242730", fg="white",
                 padx=8, pady=5).pack(fill="x", side="bottom")
        self.refresh()

    def refresh(self, select=None):
        previous = self.rows.curselection()
        index = select if select is not None else (previous[0] if previous else 0)
        self.rows.delete(0, "end")
        for slot in SLOTS:
            assigned = self.mapping.get(slot)
            source = os.path.basename(assigned) if assigned else "[stock]"
            missing = "  MISSING" if assigned and not os.path.isfile(assigned) else ""
            label = SLOT_LABELS.get(slot, slot)
            self.rows.insert("end", f"{label:<25}  {source}{missing}")
        index = max(0, min(index, len(SLOTS) - 1))
        self.rows.selection_set(index)
        self.rows.activate(index)
        self.rows.see(index)

    def selected(self):
        selection = self.rows.curselection()
        return (selection[0], SLOTS[selection[0]]) if selection else (None, None)

    def assign_patch(self):
        index, slot = self.selected()
        if slot is None:
            return
        path = filedialog.askopenfilename(
            parent=self.root, initialdir=PATCH_ROOT, title=f"FigLib patch for {slot}",
            filetypes=(("FigSynth2 patches", "*.fig"), ("All files", "*")))
        if not path:
            return
        try:
            read_patch(path)
        except Exception as error:
            messagebox.showerror("Invalid FigSynth2 patch", str(error), parent=self.root)
            return
        self.mapping[slot] = path
        save_mapping(self.mapping)
        self.refresh(index)
        self.status.set(f"{slot} will use {os.path.basename(path)}.")

    def use_stock(self):
        index, slot = self.selected()
        if slot is None:
            return
        self.mapping.pop(slot, None)
        save_mapping(self.mapping)
        self.refresh(index)
        self.status.set(f"{slot} restored to the stock sound.")

    def open_figsynth(self):
        try:
            subprocess.Popen([OPEN_APP, "figlib"], close_fds=True)
            self.status.set("FigSynth2 opened. Save a .fig patch, then assign it here.")
        except OSError as error:
            messagebox.showerror("Could not open FigSynth2", str(error), parent=self.root)

    def build(self):
        missing = [path for path in self.mapping.values() if not os.path.isfile(path)]
        if missing:
            messagebox.showerror(
                "Missing patches", "These assigned patches no longer exist:\n\n" +
                "\n".join(missing), parent=self.root)
            return
        self.build_button.configure(state="disabled")
        self.status.set(f"Rendering {len(self.mapping)} FigLib slot(s) before packing…")
        threading.Thread(target=self._build_worker, daemon=True).start()

    def _build_worker(self):
        try:
            output = build_kit(dict(self.mapping))
            self.root.after(0, lambda: self._built(output))
        except Exception as error:
            self.root.after(0, lambda e=error: self._failed(e))

    def _built(self, output):
        self.build_button.configure(state="normal")
        self.status.set(
            "Built FigLib Generated. An active FigLib kit reloads automatically.")

    def _failed(self, error):
        self.build_button.configure(state="normal")
        self.status.set("Kit build failed.")
        messagebox.showerror("Could not build FigLib kit", str(error), parent=self.root)


if __name__ == "__main__":
    os.makedirs(PROJECT_ROOT, exist_ok=True)
    os.makedirs(MODS_ROOT, exist_ok=True)
    window = tk.Tk(className="OpenRBFigLibKit")
    KitBuilder(window)
    window.mainloop()
