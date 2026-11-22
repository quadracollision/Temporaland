"""Reusable rotary control used throughout FigSynth2."""

import math
import tkinter as tk


class Knob(tk.Canvas):
    def __init__(self, master, label, low, high, value, command=None, fmt="{:.2f}",
                 endless=False, step=None, **kw):
        super().__init__(master, width=82, height=102, bg="#d7d7d7",
                         highlightthickness=0, **kw)
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
            fraction = (self.value / max(self.step * 20, 1e-9)) % 1.0
        else:
            fraction = (0 if self.high == self.low
                        else (self.value - self.low) / (self.high - self.low))
        angle = math.radians(225 - fraction * 270)
        self.create_line(
            41, 50, 41 + 22 * math.cos(angle), 50 - 22 * math.sin(angle),
            fill="#202020", width=3)
        try:
            shown = self.fmt.format(self.value)
        except Exception:
            shown = str(self.value)
        self.create_text(41, 91, text=shown, font=("Sans", 8))
