"""Dormant piano-roll implementation retained outside the main application file."""

import tkinter as tk

from .music import note_name


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
        tk.Label(toolbar, text="Lowest note", bg="#d7d7d7").pack(
            side="left", padx=(18, 3))
        low = tk.Spinbox(toolbar, from_=0, to=103, increment=1, width=5,
                         textvariable=self.low_note, command=self.draw)
        low.pack(side="left")
        low.bind("<Return>", lambda _event: self.draw())
        low.bind("<FocusOut>", lambda _event: self.draw())
        tk.Label(
            toolbar,
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
        left, top, cell_width, cell_height = self.geometry()
        step = int((event.x - left) // cell_width)
        row = int((event.y - top) // cell_height)
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
        palette = (
            "#e7a84a", "#5cb7d8", "#d672a8", "#78bf68",
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
        canvas = self.canvas
        canvas.delete("all")
        left, top, cell_width, cell_height = self.geometry()
        low = max(0, min(103, int(self.low_note.get())))
        black = {1, 3, 6, 8, 10}
        for row in range(self.ROWS):
            note = low + self.ROWS - 1 - row
            y0, y1 = top + row * cell_height, top + (row + 1) * cell_height
            fill = "#292d34" if note % 12 in black else "#343942"
            canvas.create_rectangle(
                left, y0, left + self.STEPS * cell_width, y1,
                fill=fill, outline="")
            canvas.create_text(
                left - 5, (y0 + y1) / 2, text=note_name(note),
                anchor="e", fill="#e2e2e2", font=("Sans", 8))
        for step in range(self.STEPS + 1):
            x = left + step * cell_width
            canvas.create_line(
                x, top, x, top + self.ROWS * cell_height,
                fill="#858b95" if step % 4 == 0 else "#50555d",
                width=2 if step % 4 == 0 else 1)
            if step < self.STEPS:
                canvas.create_text(
                    x + cell_width / 2, 12, text=str(step + 1),
                    fill="#eeeeee", font=("Sans", 8, "bold"))
        for row in range(self.ROWS + 1):
            y = top + row * cell_height
            canvas.create_line(
                left, y, left + self.STEPS * cell_width, y, fill="#454a52")
        for (step, note), hit in self.hits.items():
            row = low + self.ROWS - 1 - note
            if not 0 <= row < self.ROWS:
                continue
            x0 = left + step * cell_width + 2
            y0 = top + row * cell_height + 2
            x1 = left + (step + 1) * cell_width - 2
            y1 = top + (row + 1) * cell_height - 2
            canvas.create_rectangle(
                x0, y0, x1, y1, fill=hit["color"],
                outline="#fff3ba", width=1)
            if cell_width > 45 and cell_height > 13:
                canvas.create_text(
                    (x0 + x1) / 2, (y0 + y1) / 2,
                    text=hit["label"][:10], fill="#111",
                    font=("Sans", 7, "bold"))
