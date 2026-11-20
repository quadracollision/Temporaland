"""
PSY2 IDE — Premium dark-themed audio scripting environment.
"""
import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import re
import os
from .interpreter import PsyInterpreter

# ── Color Palette ──
COLORS = {
    'bg_dark':      '#0d1117',    # Main background
    'bg_mid':       '#161b22',    # Panel backgrounds
    'bg_light':     '#21262d',    # Editor background
    'bg_hover':     '#30363d',    # Hover / active
    'border':       '#30363d',    # Subtle borders
    'accent':       '#58a6ff',    # Primary accent (blue)
    'accent_green': '#3fb950',    # Success / run
    'accent_red':   '#f85149',    # Error / stop
    'accent_orange':'#d29922',    # Warning
    'accent_purple':'#bc8cff',    # Numbers
    'text':         '#c9d1d9',    # Primary text
    'text_dim':     '#8b949e',    # Secondary text
    'text_bright':  '#f0f6fc',    # Bright text
    'gutter':       '#1a1f26',    # Line number gutter
    'gutter_text':  '#484f58',    # Line number text
    'canvas_bg':    '#ffffff',    # Canvas background
    'selection':    '#264f78',    # Editor selection
}

# ── Syntax Colors ──
SYN = {
    'comment':    '#8b949e',
    'keyword':    '#ff7b72',    # bus, config, generate, for, let
    'builtin':    '#ffa657',    # osc, fx, volume, connect, sample
    'string':     '#a5d6ff',
    'number':     '#bc8cff',
    'variable':   '#ffa657',
    'operator':   '#ff7b72',   # ->, .., =
    'directive':  '#d2a8ff',   # @ui
    'type':       '#7ee787',   # master, true, false
    'widget':     '#79c0ff',   # knob, slider, textbox, toggle, button
}


class LineNumbers(tk.Canvas):
    """Line number gutter widget synced to a text widget."""
    def __init__(self, parent, text_widget, **kwargs):
        super().__init__(parent, width=45, bg=COLORS['gutter'],
                         highlightthickness=0, bd=0, **kwargs)
        self.text_widget = text_widget
        self.font = ("JetBrains Mono", 10)

    def redraw(self, *args):
        self.delete("all")
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(38, y, anchor="ne", text=linenum,
                            fill=COLORS['gutter_text'], font=self.font)
            i = self.text_widget.index(f"{i}+1line")


class IDEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("psy2 -- untitled")
        self.root.geometry("1280x850")
        self.root.configure(bg=COLORS['bg_dark'])
        self.current_file = None

        # ── Menu Bar ──
        self._build_menu()

        # ── Toolbar ──
        self._build_toolbar()

        # ── Main Layout: Vertical Split ──
        self.main_paned = tk.PanedWindow(root, orient=tk.VERTICAL,
            sashwidth=2, bg=COLORS['border'], borderwidth=0,
            opaqueresize=True)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        # ── Top: Editor + Canvas ──
        self.top_paned = tk.PanedWindow(self.main_paned, orient=tk.HORIZONTAL,
            sashwidth=2, bg=COLORS['border'], borderwidth=0,
            opaqueresize=True)
        self.main_paned.add(self.top_paned, stretch="always", height=580)

        self._build_editor_panel()
        self._build_canvas_panel()

        # ── Bottom: Console ──
        self._build_console_panel()

        # ── Status Bar ──
        self._build_status_bar()

        # ── Initialize Interpreter ──
        self.interp = PsyInterpreter(
            self.canvas, self.editor, console=self.console,
            highlight_callback=self.highlight_syntax
        )

        # ── Default Script ──
        self.default_script = """# PSY2 — Lush Pad Generator
# Buses are composable audio nodes connected via ->

bus Lead(volume=0.8) {
  osc saw, square
  fx chorus(depth=0.5, rate=1.2)
  fx reverb(decay=2.0, mix=0.6)
}

bus Bass(volume=0.9) {
  osc sine
  fx distortion(drive=0.3)
}

# Audio routing
Lead -> master
Bass -> master

# Generation settings
config {
  out "./psy2_output"
  count 3
  duration 2.0
  genre pad
  note C4
  exact true
}

# UI Controls
@ui {
  textbox "out" 10 20 200 25 "./psy2_output"
  textbox "genre" 10 60 100 25 "pad"
  textbox "note" 120 60 80 25 "C4"

  knob "chorus.depth" 10 120 25 0.0 1.0 0.5
    range 0.2 0.8
  knob "chorus.rate" 80 120 25 0.1 5.0 1.2
  knob "reverb.mix" 150 120 25 0.0 1.0 0.6

  button "Generate" 10 200 200 35
}

generate
"""
        self.editor.insert("1.0", self.default_script)
        self.highlight_syntax()
        self._update_line_numbers()
        self._set_status("Ready — PSY2 language active")

    # ═══════════════════════════════════════
    # BUILD METHODS
    # ═══════════════════════════════════════

    def _build_menu(self):
        menubar = tk.Menu(self.root, bg=COLORS['bg_mid'], fg=COLORS['text'],
                         activebackground=COLORS['bg_hover'],
                         activeforeground=COLORS['text_bright'],
                         font=("Consolas", 9), borderwidth=0)

        file_menu = tk.Menu(menubar, tearoff=0, bg=COLORS['bg_mid'],
                           fg=COLORS['text'], activebackground=COLORS['accent'],
                           activeforeground='white', font=("Consolas", 9))
        file_menu.add_command(label="New         Ctrl+N", command=self.file_new)
        file_menu.add_command(label="Open        Ctrl+O", command=self.file_open)
        file_menu.add_command(label="Save        Ctrl+S", command=self.file_save)
        file_menu.add_command(label="Save As...        ", command=self.file_save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Quit        Ctrl+Q", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        run_menu = tk.Menu(menubar, tearoff=0, bg=COLORS['bg_mid'],
                          fg=COLORS['text'], activebackground=COLORS['accent'],
                          activeforeground='white', font=("Consolas", 9))
        run_menu.add_command(label="Run / Render    Ctrl+R", command=self.run_script)

        menubar.add_cascade(label="Run", menu=run_menu)

        self.root.config(menu=menubar)

        # Keybindings
        self.root.bind("<Control-n>", lambda e: self.file_new())
        self.root.bind("<Control-o>", lambda e: self.file_open())
        self.root.bind("<Control-s>", lambda e: self.file_save())
        self.root.bind("<Control-r>", lambda e: self.run_script())
        self.root.bind("<Control-q>", lambda e: self.root.quit())

    def _build_toolbar(self):
        tb = tk.Frame(self.root, bg=COLORS['bg_mid'], pady=4, padx=8)
        tb.pack(fill=tk.X)

        btn_style = {
            'bg': COLORS['bg_mid'], 'activebackground': COLORS['bg_hover'],
            'fg': COLORS['text_dim'], 'activeforeground': COLORS['text'],
            'font': ("Consolas", 9), 'bd': 0, 'padx': 12, 'pady': 2,
            'relief': tk.FLAT, 'cursor': 'hand2',
        }

        tk.Button(tb, text="New", command=self.file_new, **btn_style).pack(side=tk.LEFT)
        tk.Button(tb, text="Open", command=self.file_open, **btn_style).pack(side=tk.LEFT)
        tk.Button(tb, text="Save", command=self.file_save, **btn_style).pack(side=tk.LEFT)

        # Separator
        tk.Frame(tb, width=2, bg=COLORS['border']).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)

        run_btn = tk.Button(tb, text="Run", command=self.run_script,
                           bg=COLORS['accent_green'], fg='white',
                           activebackground='#2ea043', activeforeground='white',
                           font=("Consolas", 10, "bold"), bd=0, padx=16, pady=2,
                           relief=tk.FLAT, cursor='hand2')
        run_btn.pack(side=tk.LEFT)

        tk.Frame(tb, width=2, bg=COLORS['border']).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)

        self.lock_var = tk.BooleanVar(value=False)
        lock_cb = tk.Checkbutton(tb, text="Lock Layout", variable=self.lock_var,
                                command=self.update_view_settings,
                                bg=COLORS['bg_mid'], fg=COLORS['text_dim'],
                                selectcolor=COLORS['bg_dark'],
                                activebackground=COLORS['bg_mid'],
                                activeforeground=COLORS['text'],
                                font=("Consolas", 9))
        lock_cb.pack(side=tk.LEFT, padx=8)

        # Right side: language badge
        tk.Label(tb, text="PSY2", bg=COLORS['accent'], fg='white',
                font=("Consolas", 8, "bold"), padx=8, pady=1).pack(side=tk.RIGHT, padx=4)

    def _build_editor_panel(self):
        frame = tk.Frame(self.top_paned, bg=COLORS['bg_dark'])
        self.top_paned.add(frame, width=560)

        # Tab bar
        tab_bar = tk.Frame(frame, bg=COLORS['bg_mid'], pady=0)
        tab_bar.pack(fill=tk.X)

        self.tab_label = tk.Label(tab_bar, text="  untitled.psy2",
                                  bg=COLORS['bg_light'], fg=COLORS['text'],
                                  font=("Consolas", 9), padx=12, pady=4, anchor='w')
        self.tab_label.pack(side=tk.LEFT)

        # Editor + line numbers wrapper
        editor_wrapper = tk.Frame(frame, bg=COLORS['bg_light'])
        editor_wrapper.pack(fill=tk.BOTH, expand=True)

        self.editor = tk.Text(editor_wrapper, bg=COLORS['bg_light'], fg=COLORS['text'],
                             insertbackground=COLORS['accent'], selectbackground=COLORS['selection'],
                             selectforeground=COLORS['text_bright'],
                             font=("JetBrains Mono", 10), undo=True,
                             borderwidth=0, padx=8, pady=8,
                             wrap=tk.NONE, tabs='28')
        
        # Scrollbar
        self.editor_scroll_y = tk.Scrollbar(editor_wrapper, orient=tk.VERTICAL,
                                       bg=COLORS['bg_dark'], troughcolor=COLORS['bg_mid'])
        editor_scroll_x = tk.Scrollbar(editor_wrapper, orient=tk.HORIZONTAL,
                                       command=self.editor.xview,
                                       bg=COLORS['bg_dark'], troughcolor=COLORS['bg_mid'])

        # Custom scroll command: scroll editor AND redraw line numbers
        def on_scroll(*args):
            self.editor.yview(*args)
            self.line_numbers.redraw()

        self.editor_scroll_y.config(command=on_scroll)

        def on_text_scroll(*args):
            self.editor_scroll_y.set(*args)
            self.line_numbers.redraw()

        self.editor.config(yscrollcommand=on_text_scroll,
                          xscrollcommand=editor_scroll_x.set)

        # Line numbers
        self.line_numbers = LineNumbers(editor_wrapper, self.editor)

        # Grid layout
        self.line_numbers.grid(row=0, column=0, sticky='ns')
        self.editor.grid(row=0, column=1, sticky='nsew')
        self.editor_scroll_y.grid(row=0, column=2, sticky='ns')
        editor_scroll_x.grid(row=1, column=1, sticky='ew')
        editor_wrapper.grid_rowconfigure(0, weight=1)
        editor_wrapper.grid_columnconfigure(1, weight=1)

        # Syntax Highlighting Tags
        self.editor.tag_configure("comment",   foreground=SYN['comment'], font=("JetBrains Mono", 10, "italic"))
        self.editor.tag_configure("keyword",   foreground=SYN['keyword'], font=("JetBrains Mono", 10, "bold"))
        self.editor.tag_configure("builtin",   foreground=SYN['builtin'])
        self.editor.tag_configure("string",    foreground=SYN['string'])
        self.editor.tag_configure("number",    foreground=SYN['number'])
        self.editor.tag_configure("variable",  foreground=SYN['variable'])
        self.editor.tag_configure("directive", foreground=SYN['directive'], font=("JetBrains Mono", 10, "bold"))
        self.editor.tag_configure("type",      foreground=SYN['type'])
        self.editor.tag_configure("widget",    foreground=SYN['widget'])
        self.editor.tag_configure("operator",  foreground=SYN['operator'])

        # Sync line numbers on scroll/edit
        self.editor.bind("<KeyRelease>", self._on_editor_change)
        self.editor.bind("<MouseWheel>", lambda e: self.root.after(1, self.line_numbers.redraw))
        self.editor.bind("<Button-4>", lambda e: self.root.after(1, self.line_numbers.redraw))
        self.editor.bind("<Button-5>", lambda e: self.root.after(1, self.line_numbers.redraw))
        self.editor.bind("<Configure>", lambda e: self.line_numbers.redraw())

    def _build_canvas_panel(self):
        frame = tk.Frame(self.top_paned, bg=COLORS['bg_dark'])
        self.top_paned.add(frame)

        # Tab bar
        tab_bar = tk.Frame(frame, bg=COLORS['bg_mid'])
        tab_bar.pack(fill=tk.X)
        tk.Label(tab_bar, text="  patcher", bg=COLORS['bg_mid'],
                fg=COLORS['text_dim'], font=("Consolas", 9), padx=8, pady=4).pack(side=tk.LEFT)

        self.canvas = tk.Canvas(frame, bg=COLORS['canvas_bg'], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Coordinates tracking
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Leave>", self._on_canvas_leave)

    def _build_console_panel(self):
        frame = tk.Frame(self.main_paned, bg=COLORS['bg_dark'])
        self.main_paned.add(frame, stretch="always", height=200)

        # Tab bar
        tab_bar = tk.Frame(frame, bg=COLORS['bg_mid'])
        tab_bar.pack(fill=tk.X)

        tk.Label(tab_bar, text="  console", bg=COLORS['bg_mid'],
                fg=COLORS['text_dim'], font=("Consolas", 9), padx=8, pady=4).pack(side=tk.LEFT)

        clear_btn = tk.Button(tab_bar, text="clear", command=self._clear_console,
                             bg=COLORS['bg_mid'], fg=COLORS['text_dim'],
                             activebackground=COLORS['bg_hover'], activeforeground=COLORS['text'],
                             font=("Consolas", 8), bd=0, padx=8, cursor='hand2')
        clear_btn.pack(side=tk.RIGHT, padx=8)

        self.console = scrolledtext.ScrolledText(frame,
            bg=COLORS['bg_dark'], fg=COLORS['accent_green'],
            font=("JetBrains Mono", 9), borderwidth=0, padx=12, pady=8,
            insertbackground=COLORS['accent'])
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.config(state=tk.DISABLED)

    def _build_status_bar(self):
        self.status_bar = tk.Frame(self.root, bg=COLORS['bg_mid'], pady=1)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = tk.Label(self.status_bar, text="Ready",
                                     bg=COLORS['bg_mid'], fg=COLORS['text_dim'],
                                     font=("Consolas", 8), anchor='w', padx=10)
        self.status_label.pack(side=tk.LEFT)

        self.canvas_coords_label = tk.Label(self.status_bar, text="",
                                            bg=COLORS['bg_mid'], fg=COLORS['accent'],
                                            font=("Consolas", 8, "bold"), padx=10)
        self.canvas_coords_label.pack(side=tk.LEFT)

        self.cursor_label = tk.Label(self.status_bar, text="Ln 1, Col 1",
                                     bg=COLORS['bg_mid'], fg=COLORS['text_dim'],
                                     font=("Consolas", 8), anchor='e', padx=10)
        self.cursor_label.pack(side=tk.RIGHT)

        self.mode_label = tk.Label(self.status_bar, text="PSY2",
                                   bg=COLORS['accent'], fg='white',
                                   font=("Consolas", 8, "bold"), padx=6)
        self.mode_label.pack(side=tk.RIGHT, padx=4)

    # ═══════════════════════════════════════
    # FILE OPERATIONS
    # ═══════════════════════════════════════

    def file_new(self):
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", self.default_script)
        self.current_file = None
        self._update_title()
        self.highlight_syntax()
        self._set_status("New file created")

    def file_open(self):
        path = filedialog.askopenfilename(
            filetypes=[("PSY2 Scripts", "*.psy2"), ("PSY Scripts", "*.psy"), ("All Files", "*")],
            defaultextension=".psy2"
        )
        if path:
            with open(path, 'r') as f:
                content = f.read()
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", content)
            self.current_file = path
            self._update_title()
            self.highlight_syntax()
            self._set_status(f"Opened: {os.path.basename(path)}")

    def file_save(self):
        if self.current_file:
            self._save_to(self.current_file)
        else:
            self.file_save_as()

    def file_save_as(self):
        path = filedialog.asksaveasfilename(
            filetypes=[("PSY2 Scripts", "*.psy2"), ("PSY Scripts", "*.psy")],
            defaultextension=".psy2"
        )
        if path:
            self._save_to(path)
            self.current_file = path
            self._update_title()

    def _save_to(self, path):
        content = self.editor.get("1.0", tk.END)
        with open(path, 'w') as f:
            f.write(content)
        self._set_status(f"Saved: {os.path.basename(path)}")

    # ═══════════════════════════════════════
    # RUN / SYNC
    # ═══════════════════════════════════════

    def run_script(self):
        code = self.editor.get("1.0", tk.END)
        self._set_status("Running...")
        self.interp.execute(code, clear_widgets=True, ui_only=True)
        self.update_view_settings()
        self.highlight_syntax()
        self._set_status("Run complete — widgets rendered")

    def sync_layout(self):
        pass  # Removed — was buggy

    def update_view_settings(self):
        self.interp.toggle_lock(self.lock_var.get())

    # ═══════════════════════════════════════
    # SYNTAX HIGHLIGHTING
    # ═══════════════════════════════════════

    def highlight_syntax(self, event=None):
        content = self.editor.get("1.0", tk.END)

        all_tags = ["comment", "keyword", "builtin", "string", "number",
                     "variable", "directive", "type", "widget", "operator"]
        for tag in all_tags:
            self.editor.tag_remove(tag, "1.0", tk.END)

        patterns = [
            # Order matters — later patterns override earlier where they overlap
            ("comment",   r"#.*$"),
            ("string",    r'"[^"\\]*(?:\\.[^"\\]*)*"' + r"|'[^'\\]*(?:\\.[^'\\]*)*'"),
            ("number",    r"\b\d+(\.\d+)?\b"),
            ("variable",  r"\$[a-zA-Z0-9_]+"),
            ("directive", r"@ui"),
            ("operator",  r"->|\.\."),
            ("keyword",   r"\b(bus|config|generate|let|for|in|if|else)\b"),
            ("builtin",   r"\b(osc|fx|volume|connect|sample|range|set|exact|loop|zeroc)\b"),
            ("type",      r"\b(master|true|false)\b"),
            ("widget",    r"\b(knob|slider|textbox|toggle|button)\b"),
        ]

        for tag, pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                start_idx = f"1.0 + {match.start()} chars"
                end_idx = f"1.0 + {match.end()} chars"
                self.editor.tag_add(tag, start_idx, end_idx)

    # ═══════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════

    def _on_editor_change(self, event=None):
        self.highlight_syntax()
        self._update_line_numbers()
        self._update_cursor_pos()

    def _update_line_numbers(self):
        self.line_numbers.redraw()

    def _update_cursor_pos(self):
        try:
            pos = self.editor.index(tk.INSERT)
            line, col = pos.split(".")
            self.cursor_label.config(text=f"Ln {line}, Col {int(col)+1}")
        except:
            pass

    def _update_title(self):
        name = os.path.basename(self.current_file) if self.current_file else "untitled.psy2"
        self.root.title(f"psy2 -- {name}")
        self.tab_label.config(text=f"  {name}")

    def _set_status(self, msg):
        self.status_label.config(text=msg)

    def _clear_console(self):
        self.console.config(state=tk.NORMAL)
        self.console.delete("1.0", tk.END)
        self.console.config(state=tk.DISABLED)

    def _on_canvas_motion(self, event):
        self.canvas_coords_label.config(text=f"X: {event.x}, Y: {event.y}")

    def _on_canvas_leave(self, event):
        self.canvas_coords_label.config(text="")


def start_ide():
    root = tk.Tk()
    app = IDEApp(root)
    root.mainloop()

if __name__ == "__main__":
    start_ide()

