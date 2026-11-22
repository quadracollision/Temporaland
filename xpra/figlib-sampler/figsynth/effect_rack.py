"""FigLib effect catalog, rack, and parameter editor."""

import tkinter as tk
from tkinter import ttk

from pySynth.routing import EFFECT_DISPATCH

from .knob import Knob
from .parameters import ENUM_OPTIONS, numeric_defaults, parameter_control_spec


class EffectRack(tk.Frame):
    DISPLAY_NAMES = {
        "eq12": "12-band EQ",
        "sidechain": "sidechain pump (simulated)",
    }
    PARAMETER_NAMES = {
        ("eq12", "gain_31_db"): "31 Hz",
        ("eq12", "gain_63_db"): "63 Hz",
        ("eq12", "gain_125_db"): "125 Hz",
        ("eq12", "gain_250_db"): "250 Hz",
        ("eq12", "gain_500_db"): "500 Hz",
        ("eq12", "gain_1k_db"): "1 kHz",
        ("eq12", "gain_2k_db"): "2 kHz",
        ("eq12", "gain_4k_db"): "4 kHz",
        ("eq12", "gain_8k_db"): "8 kHz",
        ("eq12", "gain_12k_db"): "12 kHz",
        ("eq12", "gain_16k_db"): "16 kHz",
        ("eq12", "gain_20k_db"): "20 kHz",
    }

    @classmethod
    def display_name(cls, name):
        return cls.DISPLAY_NAMES.get(name, name)

    def __init__(self, master, app):
        super().__init__(master, bg="#d7d7d7")
        self.app = app
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_args: self.refresh_catalog())

        left = tk.Frame(self, bg="#d7d7d7")
        left.pack(side="left", fill="y", padx=6, pady=6)
        tk.Label(left, text=f"All {len(EFFECT_DISPATCH)} FigLib effects", bg="#d7d7d7",
                 font=("Sans", 10, "bold")).pack(anchor="w")
        tk.Entry(left, textvariable=self.search, width=24).pack(fill="x", pady=3)
        self.catalog = tk.Listbox(left, width=27, height=21, exportselection=False)
        self.catalog.pack(fill="both", expand=True)
        tk.Button(left, text="Add effect →", command=self.add,
                  relief="raised").pack(fill="x", pady=4)

        middle = tk.Frame(self, bg="#d7d7d7")
        middle.pack(side="left", fill="y", padx=4, pady=6)
        tk.Label(middle, text="Effect rack (top to bottom)", bg="#d7d7d7",
                 font=("Sans", 10, "bold")).pack(anchor="w")
        self.chain = tk.Listbox(middle, width=30, height=21, exportselection=False)
        self.chain.pack(fill="both", expand=True, pady=3)
        self.chain.bind("<<ListboxSelect>>", lambda _event: self.show_params())
        row = tk.Frame(middle, bg="#d7d7d7")
        row.pack(fill="x")
        for text, command in (
                ("↑", lambda: self.move(-1)), ("↓", lambda: self.move(1)),
                ("Bypass", self.bypass), ("Remove", self.remove)):
            tk.Button(row, text=text, command=command).pack(
                side="left", expand=True, fill="x")

        right = tk.Frame(self, bg="#d7d7d7", width=360)
        right.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.param_title = tk.Label(
            right, text="Select an effect", bg="#d7d7d7",
            font=("Sans", 11, "bold"))
        self.param_title.pack(anchor="w")
        self.param_canvas = tk.Canvas(right, bg="#d7d7d7", highlightthickness=0)
        scrollbar = tk.Scrollbar(right, orient="vertical", command=self.param_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.param_canvas.pack(side="left", fill="both", expand=True)
        self.param_canvas.configure(yscrollcommand=scrollbar.set)
        self.params = tk.Frame(self.param_canvas, bg="#d7d7d7")
        self.param_canvas.create_window((0, 0), window=self.params, anchor="nw")
        self.params.bind(
            "<Configure>",
            lambda _event: self.param_canvas.configure(
                scrollregion=self.param_canvas.bbox("all")))
        self.refresh_catalog()

    def refresh_catalog(self):
        query = self.search.get().strip().lower()
        self.catalog.delete(0, "end")
        for name in sorted(EFFECT_DISPATCH):
            if query in name:
                self.catalog.insert("end", self.display_name(name))

    def refresh_chain(self, select=None):
        self.chain.delete(0, "end")
        for effect in self.app.effects:
            prefix = "  " if effect.get("enabled", True) else "× "
            self.chain.insert("end", prefix + self.display_name(effect["type"]))
        if select is not None and self.app.effects:
            select = max(0, min(select, len(self.app.effects) - 1))
            self.chain.selection_set(select)
            self.chain.see(select)
        self.show_params()

    def selected(self):
        selection = self.chain.curselection()
        return selection[0] if selection else None

    def add(self):
        selection = self.catalog.curselection()
        if not selection:
            return
        displayed = self.catalog.get(selection[0])
        name = next((key for key in EFFECT_DISPATCH
                     if self.display_name(key) == displayed), displayed)
        self.app.effects.append({
            "type": name,
            "params": numeric_defaults(EFFECT_DISPATCH[name]),
            "enabled": True,
        })
        self.refresh_chain(len(self.app.effects) - 1)
        self.app.refresh_assignment_targets()
        self.app.schedule_waveform()
        self.app.schedule_macro_rebuild()

    def remove(self):
        index = self.selected()
        if index is not None:
            removed = self.app.effects.pop(index)
            self.app.unassign_effect(removed)
            self.refresh_chain(max(0, index - 1))
            self.app.refresh_assignment_targets()
            self.app.schedule_waveform()
            self.app.schedule_macro_rebuild()

    def bypass(self):
        index = self.selected()
        if index is not None:
            self.app.effects[index]["enabled"] = not self.app.effects[index].get("enabled", True)
            self.refresh_chain(index)
            self.app.schedule_waveform()
            self.app.schedule_macro_rebuild()

    def move(self, direction):
        index = self.selected()
        if index is None or not 0 <= index + direction < len(self.app.effects):
            return
        effects = self.app.effects
        effects[index], effects[index + direction] = effects[index + direction], effects[index]
        self.refresh_chain(index + direction)
        self.app.schedule_waveform()
        self.app.schedule_macro_rebuild()

    def show_params(self):
        for child in self.params.winfo_children():
            child.destroy()
        index = self.selected()
        if index is None:
            self.param_title.configure(text="Select an effect")
            return
        effect = self.app.effects[index]
        title = self.display_name(effect["type"]).replace("_", " ").title()
        if effect["type"] == "sidechain":
            title += " — timed ducking; no external input"
        self.param_title.configure(text=title)
        defaults = numeric_defaults(EFFECT_DISPATCH[effect["type"]])
        if effect["type"] == "eq12":
            self._show_eq_faders(effect, defaults)
            return
        numeric_index = 0
        text_row = 20
        for name, default in defaults.items():
            value = effect["params"].get(name, default)
            label = self.PARAMETER_NAMES.get((effect["type"], name), name)
            enum_values = ENUM_OPTIONS.get((effect["type"], name))
            spec = parameter_control_spec(name, default)
            if enum_values:
                row = text_row
                text_row += 1
                tk.Label(self.params, text=name, width=18, anchor="e",
                         bg="#d7d7d7").grid(
                             row=row, column=0, sticky="e", padx=4, pady=4)
                variable = tk.StringVar(value=str(value))
                box = ttk.Combobox(
                    self.params, textvariable=variable, values=enum_values,
                    state="readonly", width=16)
                box.grid(row=row, column=1, columnspan=2, sticky="w", padx=4, pady=4)
                box.bind(
                    "<<ComboboxSelected>>",
                    lambda _event, fx=effect, parameter=name, var=variable:
                    self.app.effect_parameter_changed(fx, parameter, var.get()))
            elif spec["kind"] == "bool":
                row = text_row
                text_row += 1
                variable = tk.BooleanVar(value=bool(value))
                tk.Checkbutton(
                    self.params, text=name, variable=variable, bg="#d7d7d7",
                    command=lambda fx=effect, parameter=name, var=variable:
                    self.app.effect_parameter_changed(fx, parameter, var.get())
                ).grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=4)
            elif spec["kind"] in ("knob", "encoder"):
                row, column = divmod(numeric_index, 3)
                numeric_index += 1
                endless = spec["kind"] == "encoder"
                low = spec.get("low", float(value) - 1.0)
                high = spec.get("high", float(value) + 1.0)
                fmt = "{:.0f}" if spec.get("integer") else "{:.3g}"
                control = Knob(
                    self.params, label, low, high, value, fmt=fmt,
                    endless=endless, step=spec.get("step"),
                    command=lambda new_value, fx=effect, parameter=name, metadata=spec:
                    self.app.effect_parameter_changed(
                        fx, parameter,
                        int(round(new_value)) if metadata.get("integer") else new_value))
                control.grid(row=row, column=column, padx=4, pady=3)
            else:
                row = text_row
                text_row += 1
                tk.Label(self.params, text=name, width=18, anchor="e",
                         bg="#d7d7d7").grid(
                             row=row, column=0, sticky="e", padx=4, pady=4)
                variable = tk.StringVar(value=str(value))
                entry = tk.Entry(self.params, textvariable=variable, width=18)
                entry.grid(row=row, column=1, columnspan=2, sticky="w", padx=4, pady=4)
                entry.bind(
                    "<Return>",
                    lambda _event, fx=effect, parameter=name, var=variable:
                    self.app.effect_parameter_changed(fx, parameter, var.get()))
        if not defaults:
            tk.Label(
                self.params, text="This effect has no adjustable parameters.",
                bg="#d7d7d7").pack(anchor="w", pady=10)

    def _show_eq_faders(self, effect, defaults):
        """Draw the 12-band EQ as a conventional bank of vertical faders."""
        for column, (name, default) in enumerate(defaults.items()):
            value = float(effect["params"].get(name, default))
            label = self.PARAMETER_NAMES.get(("eq12", name), name)
            strip = tk.Frame(self.params, bg="#d7d7d7")
            strip.grid(row=0, column=column, sticky="n", padx=1, pady=4)
            tk.Label(
                strip, text=label, bg="#d7d7d7", font=("Sans", 8, "bold")
            ).pack()
            variable = tk.DoubleVar(value=value)
            fader = tk.Scale(
                strip, variable=variable, from_=24.0, to=-24.0,
                resolution=0.1, orient="vertical", length=300,
                width=13, sliderlength=20, showvalue=True, digits=3,
                bg="#d7d7d7", troughcolor="#b9b9b9",
                activebackground="#777777", highlightthickness=0,
                command=lambda raw, fx=effect, parameter=name:
                self.app.effect_parameter_changed(fx, parameter, float(raw)))
            fader.pack()
            tk.Label(strip, text="dB", bg="#d7d7d7", fg="#555555").pack()
