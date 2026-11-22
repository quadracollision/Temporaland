"""Lightweight waveform and modulation-envelope display."""

import math
import tkinter as tk

import numpy as np


def draw_audio_shape(canvas, audio, width, height, *, fill="#245c38",
                     outline="#71e38b", max_columns=360):
    """Draw the shared, X11-friendly min/max waveform used across FigSynth2."""
    if audio is None or not len(audio):
        return False
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    columns = min(max_columns, width, len(mono))
    step = max(1, len(mono) // columns)
    upper, lower = [], []
    for column in range(columns):
        chunk = mono[column * step:min(len(mono), (column + 1) * step)]
        if len(chunk):
            low = float(np.min(chunk))
            high = float(np.max(chunk))
            x = column * (width - 1) / max(1, columns - 1)
            upper.append((x, height / 2 - high * (height * .43)))
            lower.append((x, height / 2 - low * (height * .43)))
    if len(upper) < 2:
        return False
    polygon = upper + list(reversed(lower))
    flattened = [coordinate for point in polygon for coordinate in point]
    canvas.create_polygon(*flattened, fill=fill, outline=outline, width=1)
    return True


class Waveform(tk.Canvas):
    def __init__(self, master, app):
        super().__init__(master, bg="#111318", height=185, highlightthickness=1,
                         highlightbackground="#666")
        self.app = app
        self.bind("<Configure>", lambda _event: self.draw())
        self.bind("<Button-1>", self._pick)
        self.bind("<B1-Motion>", self._move)
        self.dragging = None

    def _pick(self, event):
        width = max(1, self.winfo_width())
        start_x, end_x = self.app.start * width, self.app.end * width
        self.dragging = "start" if abs(event.x - start_x) < abs(event.x - end_x) else "end"
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
        width, height = max(2, self.winfo_width()), max(2, self.winfo_height())
        audio = self.app.preview_data if data is None else data
        self.create_line(0, height / 2, width, height / 2, fill="#343b46")
        draw_audio_shape(self, audio, width, height)
        self._draw_modulation_guides(width, height)
        start_x, end_x = self.app.start * width, self.app.end * width
        self.create_rectangle(0, 0, start_x, height, fill="#07080a",
                              stipple="gray50", outline="")
        self.create_rectangle(end_x, 0, width, height, fill="#07080a",
                              stipple="gray50", outline="")
        self.create_line(start_x, 0, start_x, height, fill="#ffca57", width=3)
        self.create_line(end_x, 0, end_x, height, fill="#ffca57", width=3)
        if audio is None:
            self.create_text(
                width / 2, height / 2, text="Load a sample or make a new sound",
                fill="#aeb5c0", font=("Sans", 12))

    def _draw_modulation_guides(self, width, height):
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
        for x in range(0, width + 1, 3):
            time = duration * x / max(1, width)
            if attack > 0 and time < attack:
                gain = time / attack
            elif decay > 0 and time < attack + decay:
                gain = 1.0 - (1.0 - sustain) * ((time - attack) / decay)
            elif release > 0 and time >= release_start:
                gain = sustain * max(0.0, (duration - time) / release)
            else:
                gain = sustain
            y = gain * height * .43
            upper.extend((x, height / 2 - y))
            lower.extend((x, height / 2 + y))
        if len(upper) >= 4:
            self.create_line(*upper, fill="#58c7ff", width=2, dash=(5, 3))
            self.create_line(*lower, fill="#58c7ff", width=2, dash=(5, 3))

        depth = self.app.knobs["LFO depth"].get()
        if depth > .001:
            rate = self.app.knobs["LFO rate"].get()
            points = []
            for x in range(0, width + 1, 3):
                time = duration * x / max(1, width)
                y = height / 2 - math.sin(2 * math.pi * rate * time) * depth * height * .16
                points.extend((x, y))
            self.create_line(*points, fill="#d985ff", width=1, dash=(3, 3))
