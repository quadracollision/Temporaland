import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import sys
import os
import threading
import json
import inspect

# Import from local package
try:
    from .generator import load_presets
    from .synth import EFFECT_DISPATCH
    from .preset_creator import WAVEFORMS, FILTER_TYPES, LFO_TARGETS, LFO_SHAPES, FX_CATEGORIES
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.pySynth.generator import load_presets
    from src.pySynth.synth import EFFECT_DISPATCH
    from src.pySynth.preset_creator import WAVEFORMS, FILTER_TYPES, LFO_TARGETS, LFO_SHAPES, FX_CATEGORIES

class VerticalScrolledFrame(ttk.Frame):
    """A scrolling frame for the FX list."""
    def __init__(self, parent, *args, **kw):
        super().__init__(parent, *args, **kw)
        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

class PySynthGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("pySynth FiggyGen Frontend v3 - Power User")
        self.root.geometry("800x600")
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        self.presets = load_presets(os.path.join(os.path.dirname(__file__), '..', '..', 'presets'))
        self.genre_list = sorted(list(self.presets.keys()))
        
        # FX State
        self.fx_rows = {} # name -> widget_frame
        self.fx_vars = {} # name -> {inc, exc, params: {p_name: var}}
        self.fx_labels = {} # name -> label widget

        self._init_ui()

    def _init_ui(self):
        # ─── Notebook ───
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tab_main = ttk.Frame(self.notebook)
        self.tab_fx = ttk.Frame(self.notebook)
        self.tab_prog = ttk.Frame(self.notebook)
        self.tab_preset = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_main, text=" Main Controls ")
        self.notebook.add(self.tab_fx, text=" FX Params ")
        self.notebook.add(self.tab_prog, text=" Progression ")
        self.notebook.add(self.tab_preset, text=" Preset Editor ")
        
        # ─── Tab 1: Main (Compact Grid) ───
        main_grid = ttk.Frame(self.tab_main, padding=10)
        main_grid.pack(fill="x")
        
        # Row 0: Genre & Output
        ttk.Label(main_grid, text="Genre Preset:").grid(row=0, column=0, sticky="w", pady=5)
        self.var_genre = tk.StringVar()
        self.cb_genre = ttk.Combobox(main_grid, textvariable=self.var_genre, values=self.genre_list, state="readonly", width=15)
        self.cb_genre.grid(row=0, column=1, sticky="w", padx=5)
        self.cb_genre.bind("<<ComboboxSelected>>", self._on_genre_change)
        if self.genre_list: self.cb_genre.current(0)
        
        ttk.Label(main_grid, text="Output Dir:").grid(row=0, column=2, sticky="w", padx=(15,0))
        self.var_out = tk.StringVar(value="./samples")
        ttk.Entry(main_grid, textvariable=self.var_out, width=20).grid(row=0, column=3, sticky="w", padx=5)

        # Row 1: Note, Duration, Count
        ttk.Label(main_grid, text="Note/Chord:").grid(row=1, column=0, sticky="w", pady=5)
        self.var_note = tk.StringVar(value="C4")
        ttk.Entry(main_grid, textvariable=self.var_note, width=15).grid(row=1, column=1, sticky="w", padx=5)
        
        ttk.Label(main_grid, text="Duration (s):").grid(row=1, column=2, sticky="w", padx=(15,0))
        self.var_dur = tk.StringVar(value="2.0")
        ttk.Entry(main_grid, textvariable=self.var_dur, width=8).grid(row=1, column=3, sticky="w", padx=5)
        
        ttk.Label(main_grid, text="Count:").grid(row=2, column=0, sticky="w", pady=5)
        self.var_count = tk.StringVar(value="10")
        ttk.Entry(main_grid, textvariable=self.var_count, width=8).grid(row=2, column=1, sticky="w", padx=5)

        # Info Label
        info_frame = ttk.LabelFrame(self.tab_main, text="Current Preset Info", padding=10)
        info_frame.pack(fill="x", padx=10, pady=5)
        self.lbl_preset_info = ttk.Label(info_frame, text="Select a genre to see details.", wrap=400)
        self.lbl_preset_info.pack(fill="x")

        # ─── Tab 2: FX Params (synced to Preset Editor pool) ───
        
        info_lbl = ttk.Label(self.tab_fx, text="Showing effects enabled in the Preset Editor's FX Pool. Check/uncheck effects there to update this list.", wraplength=600, foreground="gray")
        info_lbl.pack(fill="x", padx=10, pady=(5,2))
        
        # Header
        fx_header = ttk.Frame(self.tab_fx, padding=(5,5))
        fx_header.pack(fill="x")
        ttk.Label(fx_header, text="Effect", font=("bold"), width=20).grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(fx_header, text="Inc", font=("bold")).grid(row=0, column=1, padx=5)
        ttk.Label(fx_header, text="Exc", font=("bold")).grid(row=0, column=2, padx=5)
        ttk.Label(fx_header, text="Parameters (leave blank for default)", font=("bold")).grid(row=0, column=3, sticky="w", padx=20)

        # List
        self.fx_scroll = VerticalScrolledFrame(self.tab_fx)
        self.fx_scroll.pack(fill="both", expand=True)

        saved_effects = sorted(list(EFFECT_DISPATCH.keys()))
        for i, fx in enumerate(saved_effects):
            row = ttk.Frame(self.fx_scroll.scrollable_frame)
            row.pack(fill="x", pady=2, padx=5)
            self.fx_rows[fx] = row
            
            # Label
            lbl = ttk.Label(row, text=fx, width=20)
            lbl.grid(row=0, column=0, sticky="nw", padx=5, pady=2)
            self.fx_labels[fx] = lbl
            
            # Checkboxes
            inc_var = tk.IntVar()
            exc_var = tk.IntVar()
            param_vars = {}
            self.fx_vars[fx] = {'inc': inc_var, 'exc': exc_var, 'params': param_vars}
            
            # Filter callback
            def on_state_change(name=fx):
                self._update_preview()

            # Mutual exclusion logic
            def on_check(name=fx):
                if self.fx_vars[name]['inc'].get(): self.fx_vars[name]['exc'].set(0)
                on_state_change(name)
            def on_uncheck(name=fx):
                if self.fx_vars[name]['exc'].get(): self.fx_vars[name]['inc'].set(0)
                on_state_change(name)

            tk.Checkbutton(row, variable=inc_var, command=on_check).grid(row=0, column=1, sticky="n", padx=5)
            tk.Checkbutton(row, variable=exc_var, command=on_uncheck).grid(row=0, column=2, sticky="n", padx=5)
            
            # Parameters Frame
            p_frame = ttk.Frame(row)
            p_frame.grid(row=0, column=3, sticky="w", padx=20)
            
            # Introspection
            func = EFFECT_DISPATCH[fx]
            try:
                sig = inspect.signature(func)
                params = [p.name for p in sig.parameters.values() if p.name not in ('audio', 'sample_rate', 'kwargs')]
            except ValueError:
                params = [] # Built-in or wrapped weirdly
            
            if not params:
                ttk.Label(p_frame, text="(No params)", foreground="gray").pack(anchor="w")
            else:
                # Create grid for params (2 columns)
                for j, p_name in enumerate(params):
                    r, c = divmod(j, 3) # 3 per row
                    sub = ttk.Frame(p_frame)
                    sub.grid(row=r, column=c, padx=5, sticky="w")
                    
                    # Fixed width label for alignment
                    lbl = ttk.Label(sub, text=f"{p_name}=", font=("Consolas", 8), width=12, anchor="e")
                    lbl.pack(side="left")
                    
                    pv = tk.StringVar()
                    param_vars[p_name] = pv
                    ttk.Entry(sub, textvariable=pv, width=6).pack(side="left")
                    pv.trace_add("write", self._update_preview)

        # ─── Tab 3: Progression ───
        p_frame = ttk.Frame(self.tab_prog, padding=20)
        p_frame.pack(fill="both")
        
        ttk.Label(p_frame, text="Chord Progression (separated by | ):").pack(anchor="w")
        self.var_prog = tk.StringVar(value="Am|F|C|G")
        ttk.Entry(p_frame, textvariable=self.var_prog, width=40).pack(anchor="w", pady=5)
        
        ttk.Label(p_frame, text="Passes per Chord:").pack(anchor="w", pady=(10,0))
        self.var_passes = tk.StringVar(value="5")
        ttk.Entry(p_frame, textvariable=self.var_passes, width=10).pack(anchor="w", pady=5)
        
        ttk.Label(p_frame, text="Note: Progression mode overrides 'Count' and 'Note' from Main tab.", font=("italic")).pack(anchor="w", pady=20)

        # ─── Tab 4: Preset Editor ───
        self._init_preset_editor()

        # ─── Bottom Panel (Actions & Preview) ───
        bot_frame = ttk.Frame(self.root, padding=5)
        bot_frame.pack(side="bottom", fill="x")
        
        # Preview
        pv_frame = ttk.LabelFrame(bot_frame, text="Command Preview", padding=5)
        pv_frame.pack(fill="x", pady=5)
        self.txt_cmd = tk.Entry(pv_frame, state="readonly")
        self.txt_cmd.pack(fill="x")
        
        # Buttons
        btn_frame = ttk.Frame(bot_frame)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="GENERATE", command=self._run_generation).pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(btn_frame, text="Save Script", command=self._save_script).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Wizard", command=self._run_wizard).pack(side="left", padx=5)

        # Updates
        self._on_genre_change(None) # Init visual state
        
        # Trace for preview
        for v in [self.var_genre, self.var_out, self.var_note, self.var_dur, self.var_count, self.var_prog, self.var_passes]:
            v.trace_add("write", self._update_preview)
        self.notebook.bind("<<NotebookTabChanged>>", self._update_preview)

    def _sync_fx_to_pool(self):
        """Show/hide FX Params rows based on Preset Editor's FX Pool checkboxes."""
        for fx, row in self.fx_rows.items():
            in_pool = self.pe_fxpool_vars.get(fx, tk.IntVar()).get()
            if in_pool:
                row.pack(fill="x", pady=2, padx=5)
            else:
                row.pack_forget()

    def _on_genre_change(self, event):
        genre = self.var_genre.get()
        if not genre or genre not in self.presets: return
        
        data = self.presets[genre]
        pool = data.get('fx_pool', [])
        
        # Update Info Label
        txt = f"Default FX Pool: {', '.join(pool) if pool else 'None'}\n"
        txt += f"Oscillators: {data.get('osc_count', [1,1])}  |  Filter Prob: {data.get('filter_prob', 0)}"
        self.lbl_preset_info.config(text=txt)
        
        # Sync Preset Editor pool checkboxes
        for fx in self.pe_fxpool_vars:
            self.pe_fxpool_vars[fx].set(1 if fx in pool else 0)
        
        # Highlight in FX Params list
        for fx, lbl in self.fx_labels.items():
            if fx in pool:
                lbl.config(font=("TkDefaultFont", 9, "bold"), foreground="blue")
            else:
                lbl.config(font=("TkDefaultFont", 9), foreground="black")
        
        # Sync FX Params tab visibility
        self._sync_fx_to_pool()
        self._update_preview()

    def _build_cmd(self):
        cmd = ["python", "run.py"]
        # Global
        cmd.extend(["--duration", self.var_dur.get(), "--out", self.var_out.get(), "--genre", self.var_genre.get()])
        
        # FX with params
        inc_list = []
        for fx, v in self.fx_vars.items():
            if v['inc'].get():
                # Collect params
                p_strs = []
                for p_name, p_var in v['params'].items():
                    val = p_var.get().strip()
                    if val:
                        p_strs.append(f"{p_name}={val}")
                
                if p_strs:
                    inc_list.append(f"{fx}({','.join(p_strs)})")
                else:
                    inc_list.append(fx)

        exc_list = [fx for fx, v in self.fx_vars.items() if v['exc'].get()]
        
        if inc_list: cmd.extend(["--fx-include", ",".join(inc_list)])
        if exc_list: cmd.extend(["--fx-exclude", ",".join(exc_list)])
        
        # Mode
        if self.notebook.index("current") == 2: # Progression Tab
            cmd.extend(["--progression", f'"{self.var_prog.get()}"', "--passes", self.var_passes.get()])
        else:
            cmd.extend(["--count", self.var_count.get(), "--note", f'"{self.var_note.get()}"'])
            
        return cmd

    def _update_preview(self, *args):
        cmd = self._build_cmd()
        self.txt_cmd.config(state="normal")
        self.txt_cmd.delete(0, tk.END)
        self.txt_cmd.insert(0, " ".join(cmd))
        self.txt_cmd.config(state="readonly")

    def _run_generation(self):
        cmd_list = self._build_cmd()
        # Keep quotes for shell safety (e.g. | in progression)
        subprocess.Popen(["start", "cmd", "/k"] + cmd_list, shell=True) 

    def _save_script(self):
        path = filedialog.asksaveasfilename(defaultextension=".psy", filetypes=[("Script", "*.psy")])
        if not path: return
        # Simple save
        cmd = self._build_cmd()
        # Convert cmd list back to script format is annoying, 
        # but user asked for script saving.
        # I'll cheat and write a command line runner script? No, .psy is specific format.
        # I'll iterate vars again.
        lines = [f"set duration {self.var_dur.get()}",
                 f"set out {self.var_out.get()}",
                 f"set genre {self.var_genre.get()}"]
        
        inc_list = [] # Same logic as build_cmd
        for fx, v in self.fx_vars.items():
            if v['inc'].get():
                p_strs = []
                for p_name, p_var in v['params'].items():
                    val = p_var.get().strip()
                    if val: p_strs.append(f"{p_name}={val}")
                if p_strs: inc_list.append(f"{fx}({','.join(p_strs)})")
                else: inc_list.append(fx)
        
        exc_list = [fx for fx, v in self.fx_vars.items() if v['exc'].get()]
        
        if inc_list: lines.append(f"set fx-include {','.join(inc_list)}")
        if exc_list: lines.append(f"set fx-exclude {','.join(exc_list)}")

        if self.notebook.index("current") == 2:
            lines.append(f"set passes {self.var_passes.get()}")
            lines.append(f"progression {self.var_prog.get()}")
        else:
            lines.append(f"set count {self.var_count.get()}")
            lines.append(f"set note {self.var_note.get()}")
            lines.append("generate")
            
        with open(path, 'w') as f:
            f.write("\n".join(lines))

    def _run_wizard(self):
        os.system("start cmd /k python run.py --create-preset")

    # ─── Preset Editor ───────────────────────────────────────
    def _init_preset_editor(self):
        """Build the Preset Editor tab."""
        # Scrollable container for the whole editor
        editor_scroll = VerticalScrolledFrame(self.tab_preset)
        editor_scroll.pack(fill="both", expand=True)
        ef = editor_scroll.scrollable_frame

        # ── Load / Save Bar ──
        io_frame = ttk.LabelFrame(ef, text="Preset File", padding=5)
        io_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(io_frame, text="Load:").grid(row=0, column=0, sticky="w")
        self.pe_var_load = tk.StringVar()
        self.pe_cb_load = ttk.Combobox(io_frame, textvariable=self.pe_var_load, values=self.genre_list, state="readonly", width=15)
        self.pe_cb_load.grid(row=0, column=1, padx=5)
        ttk.Button(io_frame, text="Load", command=self._pe_load).grid(row=0, column=2, padx=5)

        ttk.Label(io_frame, text="Save As:").grid(row=0, column=3, sticky="w", padx=(15,0))
        self.pe_var_name = tk.StringVar()
        ttk.Entry(io_frame, textvariable=self.pe_var_name, width=15).grid(row=0, column=4, padx=5)
        ttk.Button(io_frame, text="Save", command=self._pe_save).grid(row=0, column=5, padx=5)

        # ── 1. Oscillators ──
        osc_frame = ttk.LabelFrame(ef, text="1. Oscillators", padding=5)
        osc_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(osc_frame, text="Waveforms:").grid(row=0, column=0, sticky="nw")
        wf_frame = ttk.Frame(osc_frame)
        wf_frame.grid(row=0, column=1, columnspan=5, sticky="w")
        self.pe_waveform_vars = {}
        for i, wf in enumerate(WAVEFORMS):
            v = tk.IntVar()
            self.pe_waveform_vars[wf] = v
            tk.Checkbutton(wf_frame, text=wf, variable=v).grid(row=i//5, column=i%5, sticky="w", padx=3)

        ttk.Label(osc_frame, text="Osc Count (min, max):").grid(row=2, column=0, sticky="w", pady=5)
        self.pe_osc_min = tk.StringVar(value="1")
        self.pe_osc_max = tk.StringVar(value="2")
        ttk.Entry(osc_frame, textvariable=self.pe_osc_min, width=5).grid(row=2, column=1, sticky="w")
        ttk.Entry(osc_frame, textvariable=self.pe_osc_max, width=5).grid(row=2, column=2, sticky="w")

        ttk.Label(osc_frame, text="Freq Range (Hz):").grid(row=3, column=0, sticky="w", pady=5)
        self.pe_freq_min = tk.StringVar(value="40")
        self.pe_freq_max = tk.StringVar(value="400")
        ttk.Entry(osc_frame, textvariable=self.pe_freq_min, width=6).grid(row=3, column=1, sticky="w")
        ttk.Entry(osc_frame, textvariable=self.pe_freq_max, width=6).grid(row=3, column=2, sticky="w")

        ttk.Label(osc_frame, text="Max Unison Voices:").grid(row=4, column=0, sticky="w", pady=5)
        self.pe_unison_max = tk.StringVar(value="3")
        ttk.Entry(osc_frame, textvariable=self.pe_unison_max, width=5).grid(row=4, column=1, sticky="w")

        ttk.Label(osc_frame, text="Max Unison Detune (cents):").grid(row=4, column=2, sticky="w", padx=(15,0))
        self.pe_detune_max = tk.StringVar(value="15")
        ttk.Entry(osc_frame, textvariable=self.pe_detune_max, width=5).grid(row=4, column=3, sticky="w")

        # ── 2. Filters ──
        filt_frame = ttk.LabelFrame(ef, text="2. Filters", padding=5)
        filt_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(filt_frame, text="Filter Probability:").grid(row=0, column=0, sticky="w")
        self.pe_filter_prob = tk.StringVar(value="0.7")
        ttk.Entry(filt_frame, textvariable=self.pe_filter_prob, width=6).grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(filt_frame, text="Filter Types:").grid(row=1, column=0, sticky="nw", pady=5)
        ft_frame = ttk.Frame(filt_frame)
        ft_frame.grid(row=1, column=1, columnspan=4, sticky="w")
        self.pe_filter_type_vars = {}
        for i, ft in enumerate(FILTER_TYPES):
            v = tk.IntVar()
            self.pe_filter_type_vars[ft] = v
            tk.Checkbutton(ft_frame, text=ft, variable=v).grid(row=0, column=i, sticky="w", padx=3)

        ttk.Label(filt_frame, text="Cutoff Range (Hz):").grid(row=2, column=0, sticky="w", pady=5)
        self.pe_cutoff_min = tk.StringVar(value="200")
        self.pe_cutoff_max = tk.StringVar(value="5000")
        ttk.Entry(filt_frame, textvariable=self.pe_cutoff_min, width=6).grid(row=2, column=1, sticky="w")
        ttk.Entry(filt_frame, textvariable=self.pe_cutoff_max, width=6).grid(row=2, column=2, sticky="w")

        # ── 3. Envelope (ADSR) ──
        env_frame = ttk.LabelFrame(ef, text="3. Envelope (ADSR)", padding=5)
        env_frame.pack(fill="x", padx=5, pady=5)

        self.pe_env_vars = {}
        env_params = ['attack', 'hold', 'decay', 'sustain', 'release']
        env_defaults = {'attack': (0.001, 0.05), 'hold': (0.0, 0.0), 'decay': (0.1, 0.5), 'sustain': (0.5, 1.0), 'release': (0.1, 0.5)}
        for i, ep in enumerate(env_params):
            ttk.Label(env_frame, text=f"{ep.title()}:").grid(row=i, column=0, sticky="w", pady=2)
            v_min = tk.StringVar(value=str(env_defaults[ep][0]))
            v_max = tk.StringVar(value=str(env_defaults[ep][1]))
            self.pe_env_vars[ep] = (v_min, v_max)
            ttk.Label(env_frame, text="min:").grid(row=i, column=1, sticky="e")
            ttk.Entry(env_frame, textvariable=v_min, width=6).grid(row=i, column=2, padx=3)
            ttk.Label(env_frame, text="max:").grid(row=i, column=3, sticky="e")
            ttk.Entry(env_frame, textvariable=v_max, width=6).grid(row=i, column=4, padx=3)

        # ── 4. LFO ──
        lfo_frame = ttk.LabelFrame(ef, text="4. LFO", padding=5)
        lfo_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(lfo_frame, text="LFO Probability:").grid(row=0, column=0, sticky="w")
        self.pe_lfo_prob = tk.StringVar(value="0.5")
        ttk.Entry(lfo_frame, textvariable=self.pe_lfo_prob, width=6).grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(lfo_frame, text="Targets:").grid(row=1, column=0, sticky="nw", pady=5)
        lt_frame = ttk.Frame(lfo_frame)
        lt_frame.grid(row=1, column=1, columnspan=4, sticky="w")
        self.pe_lfo_target_vars = {}
        for i, lt in enumerate(LFO_TARGETS):
            v = tk.IntVar()
            self.pe_lfo_target_vars[lt] = v
            tk.Checkbutton(lt_frame, text=lt, variable=v).grid(row=0, column=i, sticky="w", padx=3)

        ttk.Label(lfo_frame, text="Shapes:").grid(row=2, column=0, sticky="nw", pady=5)
        ls_frame = ttk.Frame(lfo_frame)
        ls_frame.grid(row=2, column=1, columnspan=4, sticky="w")
        self.pe_lfo_shape_vars = {}
        for i, ls in enumerate(LFO_SHAPES):
            v = tk.IntVar()
            self.pe_lfo_shape_vars[ls] = v
            tk.Checkbutton(ls_frame, text=ls, variable=v).grid(row=0, column=i, sticky="w", padx=3)

        ttk.Label(lfo_frame, text="Rate (Hz):").grid(row=3, column=0, sticky="w", pady=5)
        self.pe_lfo_rate_min = tk.StringVar(value="0.5")
        self.pe_lfo_rate_max = tk.StringVar(value="5.0")
        ttk.Entry(lfo_frame, textvariable=self.pe_lfo_rate_min, width=6).grid(row=3, column=1, sticky="w")
        ttk.Entry(lfo_frame, textvariable=self.pe_lfo_rate_max, width=6).grid(row=3, column=2, sticky="w")

        ttk.Label(lfo_frame, text="Max Amount:").grid(row=4, column=0, sticky="w", pady=5)
        self.pe_lfo_amount = tk.StringVar(value="0.5")
        ttk.Entry(lfo_frame, textvariable=self.pe_lfo_amount, width=6).grid(row=4, column=1, sticky="w")

        # ── 5. FX Pool ──
        fxp_frame = ttk.LabelFrame(ef, text="5. FX Pool (Effects allowed in this preset)", padding=5)
        fxp_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(fxp_frame, text="Checked effects appear on the FX Params tab for parameter editing.", foreground="gray").pack(anchor="w", pady=(0,5))

        fxp_grid = ttk.Frame(fxp_frame)
        fxp_grid.pack(fill="x")
        self.pe_fxpool_vars = {}
        all_fx = sorted(list(EFFECT_DISPATCH.keys()))
        for i, fx in enumerate(all_fx):
            v = tk.IntVar()
            self.pe_fxpool_vars[fx] = v
            tk.Checkbutton(fxp_grid, text=fx, variable=v, command=self._sync_fx_to_pool).grid(row=i//6, column=i%6, sticky="w", padx=3)

        # ── 6. Extra Probs ──
        extra_frame = ttk.LabelFrame(ef, text="6. Extra Probabilities", padding=5)
        extra_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(extra_frame, text="Reverb Prob:").grid(row=0, column=0, sticky="w")
        self.pe_reverb_prob = tk.StringVar(value="0.3")
        ttk.Entry(extra_frame, textvariable=self.pe_reverb_prob, width=6).grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(extra_frame, text="Delay Prob:").grid(row=0, column=2, sticky="w", padx=(15,0))
        self.pe_delay_prob = tk.StringVar(value="0.2")
        ttk.Entry(extra_frame, textvariable=self.pe_delay_prob, width=6).grid(row=0, column=3, sticky="w", padx=5)

    def _pe_load(self):
        """Load a preset into the editor."""
        name = self.pe_var_load.get()
        if not name or name not in self.presets:
            messagebox.showwarning("Load", "Select a preset to load.")
            return

        d = self.presets[name]
        self.pe_var_name.set(name)

        # Oscillators
        for wf in WAVEFORMS:
            self.pe_waveform_vars[wf].set(1 if wf in d.get('osc_waveforms', []) else 0)
        oc = d.get('osc_count', [1, 2])
        self.pe_osc_min.set(str(oc[0])); self.pe_osc_max.set(str(oc[1]))
        fr = d.get('freq_range', [40, 400])
        self.pe_freq_min.set(str(fr[0])); self.pe_freq_max.set(str(fr[1]))
        ur = d.get('unison_range', [1, 3])
        self.pe_unison_max.set(str(ur[1]) if len(ur) > 1 else "3")
        ud = d.get('unison_detune', [5, 15])
        self.pe_detune_max.set(str(ud[1]) if len(ud) > 1 else "15")

        # Filters
        self.pe_filter_prob.set(str(d.get('filter_prob', 0.7)))
        for ft in FILTER_TYPES:
            self.pe_filter_type_vars[ft].set(1 if ft in d.get('filter_types', []) else 0)
        cr = d.get('cutoff_range', [200, 5000])
        self.pe_cutoff_min.set(str(cr[0])); self.pe_cutoff_max.set(str(cr[1]))

        # Envelope
        env = d.get('envelope', {})
        for ep, (v_min, v_max) in self.pe_env_vars.items():
            er = env.get(ep, [0, 0])
            v_min.set(str(er[0]) if len(er) > 0 else "0")
            v_max.set(str(er[1]) if len(er) > 1 else "0")

        # LFO
        lfo = d.get('lfo', {})
        self.pe_lfo_prob.set(str(lfo.get('prob', 0)))
        for lt in LFO_TARGETS:
            self.pe_lfo_target_vars[lt].set(1 if lt in lfo.get('targets', []) else 0)
        for ls in LFO_SHAPES:
            self.pe_lfo_shape_vars[ls].set(1 if ls in lfo.get('shapes', []) else 0)
        lr = lfo.get('rate', [0.5, 5.0])
        self.pe_lfo_rate_min.set(str(lr[0])); self.pe_lfo_rate_max.set(str(lr[1]))
        la = lfo.get('amount', [0.1, 0.5])
        self.pe_lfo_amount.set(str(la[1]) if len(la) > 1 else "0.5")

        # FX Pool
        pool = d.get('fx_pool', [])
        for fx in self.pe_fxpool_vars:
            self.pe_fxpool_vars[fx].set(1 if fx in pool else 0)
        
        # Sync FX Params tab
        self._sync_fx_to_pool()

        # Extra probs
        self.pe_reverb_prob.set(str(d.get('reverb_prob', 0.3)))
        self.pe_delay_prob.set(str(d.get('delay_prob', 0.2)))

    def _pe_save(self):
        """Save the editor form to a .psi file."""
        name = self.pe_var_name.get().strip()
        if not name:
            messagebox.showwarning("Save", "Enter a preset name.")
            return

        safe_name = "".join(x for x in name if x.isalnum() or x in "_-").lower()
        filepath = os.path.join(os.path.dirname(__file__), '..', '..', 'presets', f"{safe_name}.psi")

        data = {}

        # Oscillators
        data['osc_waveforms'] = [wf for wf, v in self.pe_waveform_vars.items() if v.get()]
        data['osc_count'] = [int(self.pe_osc_min.get()), int(self.pe_osc_max.get())]
        data['freq_range'] = [int(self.pe_freq_min.get()), int(self.pe_freq_max.get())]
        data['unison_range'] = [1, int(self.pe_unison_max.get())]
        data['unison_detune'] = [5, int(self.pe_detune_max.get())]

        # Filters
        data['filter_prob'] = float(self.pe_filter_prob.get())
        data['filter_types'] = [ft for ft, v in self.pe_filter_type_vars.items() if v.get()]
        data['cutoff_range'] = [int(self.pe_cutoff_min.get()), int(self.pe_cutoff_max.get())]

        # Envelope
        data['envelope'] = {}
        for ep, (v_min, v_max) in self.pe_env_vars.items():
            data['envelope'][ep] = [float(v_min.get()), float(v_max.get())]

        # LFO
        data['lfo'] = {
            'prob': float(self.pe_lfo_prob.get()),
            'targets': [lt for lt, v in self.pe_lfo_target_vars.items() if v.get()],
            'shapes': [ls for ls, v in self.pe_lfo_shape_vars.items() if v.get()],
            'rate': [float(self.pe_lfo_rate_min.get()), float(self.pe_lfo_rate_max.get())],
            'amount': [0.1, float(self.pe_lfo_amount.get())],
        }

        # FX Pool
        data['fx_pool'] = [fx for fx, v in self.pe_fxpool_vars.items() if v.get()]

        # Extra
        data['reverb_prob'] = float(self.pe_reverb_prob.get())
        data['delay_prob'] = float(self.pe_delay_prob.get())

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            messagebox.showinfo("Saved", f"Preset saved to {filepath}")
            # Refresh presets
            self.presets = load_presets(os.path.join(os.path.dirname(__file__), '..', '..', 'presets'))
            self.genre_list = sorted(list(self.presets.keys()))
            self.cb_genre.config(values=self.genre_list)
            self.pe_cb_load.config(values=self.genre_list)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

def run_gui():
    root = tk.Tk()
    app = PySynthGUI(root)
    root.mainloop()

if __name__ == "__main__":
    run_gui()

