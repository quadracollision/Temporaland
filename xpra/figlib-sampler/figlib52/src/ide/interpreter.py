import tkinter as tk
import sys
import threading
from pySynth.main import get_default_state, execute_interpreter_command, execute_generation, execute_progression
from pySynth.parsing import resolve_rand_note, resolve_rand_float, resolve_rand_int
import time
from .widgets import CanvasSlider, CanvasKnob, CanvasButton, CanvasToggle

class StdoutRedirector:
    """Redirects sys.stdout to a callback function (e.g., PsyInterpreter.log)."""
    def __init__(self, log_func):
        self.log_func = log_func
        self._buf = ""

    def write(self, message):
        # Always write to the real stdout as well
        sys.__stdout__.write(message)
        sys.__stdout__.flush()
        
        self._buf += message
        if "\n" in self._buf:
            lines = self._buf.split("\n")
            for line in lines[:-1]:
                if line.strip():
                    self.log_func(line.strip())
            self._buf = lines[-1]

    def flush(self):
        sys.__stdout__.flush()

class PsyInterpreter:
    """
    An interpreter for extended .psy scripts that supports:
    - Standard pySynth commands (set, generate, etc.)
    - Variables (e.g., $x = 10, $y = $x + 5)
    - Loops (loop N block... end)
    - UI Drawing commands (rect, circle, text, clear)
    - Interactive UI elements (slider, knob, button) with bidirectional sync
    """
    def __init__(self, canvas=None, editor=None, console=None, highlight_callback=None):
        self.canvas = canvas
        self.editor = editor
        self.console = console # Integrated console widget
        self.highlight_callback = highlight_callback
        self.variables = {}
        self.state = get_default_state()
        
        self.widgets = []
        self.lock_layout = False
        
        # These are used for auto-layout if coordinates are missing
        self._next_widget_y = 20
        self._next_widget_x = 20
        self.ui_only_mode = False
        self.script_mode = 'psy'  # 'psy' or 'psy2'

        if self.console:
            sys.stdout = StdoutRedirector(self.log)

    def toggle_lock(self, locked):
        self.lock_layout = locked

    def log(self, message):
        """Log a message to the internal console widget (thread-safe)."""
        output = str(message)
        if self.console:
            def append():
                try:
                    self.console.config(state=tk.NORMAL)
                    self.console.insert(tk.END, output + "\n")
                    self.console.see(tk.END)
                    self.console.config(state=tk.DISABLED)
                except tk.TclError:
                    pass # Console might have been destroyed
            self.console.after(0, append)

    def get_display_label(self, target):
        """Return the leaf part of a dotted target for cleaner UI labels."""
        if '.' in target:
            return target.split('.')[-1]
        return target

    def resolve_value(self, val_str):
        if isinstance(val_str, bool):
            return val_str
        if not isinstance(val_str, str):
            return val_str
        val_str = val_str.strip()
        if val_str.startswith('$'):
            var_name = val_str[1:]
            if var_name in self.variables:
                return self.variables[var_name]
            elif var_name in self.state:
                return self.state[var_name]
            else:
                return 0 # Default undefined variable to 0
        try:
            return float(val_str) if '.' in val_str else int(val_str)
        except ValueError:
            return val_str
            
    def evaluate_expression(self, expr_str):
        # Basic parsing for $x + 10 type expressions
        parts = expr_str.split()
        if len(parts) == 3:
            left = self.resolve_value(parts[0])
            op = parts[1]
            right = self.resolve_value(parts[2])
            
            try: left = float(left) if '.' in str(left) else int(left)
            except: pass
            try: right = float(right) if '.' in str(right) else int(right)
            except: pass
            
            if op == '+': return left + right
            elif op == '-': return left - right
            elif op == '*': return left * right
            elif op == '/': return left / right if right != 0 else 0
        return self.resolve_value(expr_str)

    def execute(self, code, clear_widgets=True, ui_only=False):
        """
        Execute the provided code. 
        If clear_widgets is True (full run), reset state and canvas.
        If False (partial/event execution), preserve state.
        """
        if clear_widgets:
            self.variables.clear()
            self.state = get_default_state()
            self.widgets = []
            self.last_widget = None # Track for range command
            self._next_widget_y = 20
            self._next_widget_x = 20
            if self.canvas:
                 self.canvas.delete("all")
        
        self.ui_only_mode = ui_only

        # Auto-detect PSY2 syntax: uses curly braces for blocks instead of end
        stripped = code.strip()
        if ('{' in stripped and '}' in stripped) or stripped.startswith('@'):
            self.script_mode = 'psy2'
            self._execute_psy2(code)
            return

        self.script_mode = 'psy'
        lines = code.splitlines()
        
        # Pre-process blocks (loops, buttons, buses)
        parsed_blocks = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('#'):
                i += 1
                continue
                
            if any(line.startswith(kw) for kw in ['loop', 'button', 'bus']):
                try:
                    parts = line.split(maxsplit=2)
                    block_type = parts[0]
                    # bus "id" [x y] w h [color]
                    args_str = " ".join(parts[1:]) if len(parts) > 1 else ""
                    
                    block_lines = []
                    i += 1
                    nested = 0
                    while i < len(lines):
                        inner_line = lines[i].strip()
                        if any(inner_line.startswith(kw) for kw in ['loop', 'button', 'bus']):
                            nested += 1
                        elif inner_line == 'end':
                            if nested == 0:
                                break
                            nested -= 1
                        block_lines.append(inner_line)
                        i += 1
                    parsed_blocks.append((block_type, args_str, block_lines))
                except IndexError:
                    pass
            else:
                parsed_blocks.append(('line', line))
            i += 1

        self.execute_blocks(parsed_blocks)

    # ── PSY2 Execution ──

    def _execute_psy2(self, code):
        """
        Execute .psy2 code through the new lexer → parser → AST → evaluator pipeline.
        Maps evaluator output to canvas widgets and figlib generation.
        """
        try:
            from psy2.parser import parse, ParseError
            from psy2.evaluator import PsyEvaluator, EvalError
            from psy2.lexer import LexerError
        except ImportError as e:
            self.log(f"[PSY2] Import error: {e}")
            return

        try:
            program = parse(code)
        except (LexerError, ParseError) as e:
            self.log(f"[PSY2] {e}")
            return

        try:
            evaluator = PsyEvaluator()
            result = evaluator.evaluate(program)
        except EvalError as e:
            self.log(f"[PSY2] Eval error: {e}")
            return

        # Apply state
        self.state = result['state']
        self.variables.update(result.get('variables', {}))
        self._last_psy2_result = result  # Store for button callbacks

        # Render UI widgets
        for w in result.get('ui_widgets', []):
            self._render_psy2_widget(w)

        # Log bus info
        for bus_rule in result.get('bus_rules', []):
            self.log(f"[PSY2] Bus '{bus_rule['id']}': osc={bus_rule.get('oscillators', [])}, fx=[{', '.join(e['type'] for e in bus_rule.get('effects', []))}]")

        # Log connections
        for src, tgt in result.get('connections', []):
            self.log(f"[PSY2] Route: {src} -> {tgt}")

        # Generate if requested (and not in ui_only mode)
        if result.get('should_generate') and not self.ui_only_mode:
            self._collect_widget_values()  # Read live widget values from canvas
            self._run_psy2_generation(result)

    def _render_psy2_widget(self, widget_decl):
        """Map a PSY2 WidgetDecl AST node to a canvas widget."""
        kind = widget_decl.kind
        args = widget_decl.args

        # Evaluate math expressions in args
        import re
        for i in range(len(args)):
            if isinstance(args[i], str) and re.match(r'^[\d\.\+\-\*\/\s\(\)]+$', args[i]):
                try:
                    args[i] = eval(args[i])
                except Exception:
                    pass

        if kind == 'knob':
            # knob "target" x y radius min max default
            if len(args) >= 7:
                target, x, y, radius, min_v, max_v, default = args[0], int(args[1]), int(args[2]), int(args[3]), float(args[4]), float(args[5]), float(self.resolve_value(args[6]))
            elif len(args) >= 1:
                target = args[0]
                radius = int(args[1]) if len(args) > 1 else 15
                
                # Check for "bus macro" expansion: knob bus.Lead (no parameter)
                if target.startswith('bus.') and '.' not in target[4:]:
                    bus_id = target[4:]
                    # Find this bus in rules
                    bus_rule = next((b for b in self._last_psy2_result.get('bus_rules', []) if b['id'] == bus_id), None)
                    if bus_rule:
                        from pySynth.parsing import FX_PARAM_RANGES
                        for fx in bus_rule.get('effects', []):
                            fx_type = fx['type']
                            ranges = FX_PARAM_RANGES.get(fx_type, {})
                            for p_name, p_val in fx.get('params', {}).items():
                                p_min, p_max = ranges.get(p_name, (0.0, 1.0))
                                p_radius = radius
                                p_x, p_y = self.get_next_widget_pos(p_radius*2, p_radius*2 + 20)
                                p_target = f"{bus_id}.{fx_type}.{p_name}"
                                if self.canvas:
                                    w = CanvasKnob(self.canvas, p_x, p_y, p_radius, p_target, p_min, p_max, float(p_val),
                                                   self.on_widget_moved, display_name=self.get_display_label(p_target))
                                    w.lock_check = lambda: self.lock_layout
                                    self.widgets.append(w)
                                    self.last_widget = w
                        return
                    else:
                        return # Bus not found
                
                if len(args) >= 5:
                    min_v, max_v, default = float(args[2]), float(args[3]), float(self.resolve_value(args[4]))
                else:
                    # Generic fallback: knob target radius
                    min_v, max_v, default = 0.0, 1.0, 0.0
                x, y = self.get_next_widget_pos(radius*2, radius*2 + 20)
            else:
                return
            if self.canvas:
                w = CanvasKnob(self.canvas, x, y, radius, target, min_v, max_v, default,
                               self.on_widget_moved, display_name=self.get_display_label(target))
                w.lock_check = lambda: self.lock_layout
                if widget_decl.range_bounds:
                    w.rand_range = widget_decl.range_bounds
                self.widgets.append(w)
                self.last_widget = w

        elif kind == 'slider':
            # slider "target" x y width min max default
            if len(args) >= 7:
                target, x, y, width, min_v, max_v, default = args[0], int(args[1]), int(args[2]), int(args[3]), float(args[4]), float(args[5]), float(self.resolve_value(args[6]))
            else:
                return
            if self.canvas:
                w = CanvasSlider(self.canvas, x, y, width, target, min_v, max_v, default,
                                 self.on_widget_moved, display_name=self.get_display_label(target))
                w.lock_check = lambda: self.lock_layout
                if widget_decl.range_bounds:
                    w.rand_range = widget_decl.range_bounds
                self.widgets.append(w)
                self.last_widget = w

        elif kind == 'textbox':
            # textbox "target" x y width height default
            if len(args) >= 6:
                target, x, y, width, height, default = args[0], int(args[1]), int(args[2]), int(args[3]), int(args[4]), str(self.resolve_value(args[5]))
            elif len(args) >= 2:
                target = args[0]
                default = str(self.resolve_value(args[1])) if len(args) > 1 else ""
                width, height = 150, 25
                x, y = self.get_next_widget_pos(width, height + 20)
            else:
                return
            # Sync textbox defaults ↔ config values
            # If config explicitly set something different from textbox default, use config.
            # Otherwise, textbox default flows into state.
            if target in self.state:
                config_val = self.state[target]
                if config_val is not None and str(config_val) != '' and default and str(config_val) != str(default):
                    # Config set a value — use it as textbox text
                    default = str(config_val)
                elif default:
                    # Textbox default flows into state
                    self.state[target] = default
            elif default:
                # Key not in state yet (like 'scale' which defaults to None)
                self.state[target] = default
            if self.canvas:
                from .widgets import CanvasTextbox
                w = CanvasTextbox(self.canvas, x, y, width, height, target, default,
                                  self.on_widget_moved, display_name=self.get_display_label(target))
                w.lock_check = lambda: self.lock_layout
                self.widgets.append(w)
                self.last_widget = w

        elif kind == 'toggle':
            # toggle "target" x y size default
            if len(args) >= 5:
                target, x, y, size, default = args[0], int(args[1]), int(args[2]), int(args[3]), self.resolve_value(args[4])
            elif len(args) >= 2:
                target = args[0]
                default = self.resolve_value(args[1]) if len(args) > 1 else False
                size = 15
                x, y = self.get_next_widget_pos(size, size + 20)
            else:
                return
            if self.canvas:
                w = CanvasToggle(self.canvas, x, y, size, target, default,
                                  self.on_widget_moved, display_name=self.get_display_label(target))
                w.lock_check = lambda: self.lock_layout
                self.widgets.append(w)
                self.last_widget = w

        elif kind == 'button':
            # button "label" x y width height
            if len(args) >= 5:
                label, x, y, width, height = str(args[0]), int(args[1]), int(args[2]), int(args[3]), int(args[4])
            elif len(args) >= 3:
                label, width, height = str(args[0]), int(args[1]), int(args[2])
                x, y = self.get_next_widget_pos(width, height + 10)
            else:
                return
            if self.canvas:
                def make_psy2_button_cb(lbl):
                    def cb():
                        self.log(f"[PSY2] Button '{lbl}' Pressed.")
                        # Collect current widget values and generate
                        # Do NOT re-parse — that would reset all widgets
                        def run():
                            self.ui_only_mode = False
                            self._collect_widget_values()
                            if hasattr(self, '_last_psy2_result') and self._last_psy2_result:
                                self._run_psy2_generation(self._last_psy2_result)
                            else:
                                self.log("[PSY2] No script has been parsed yet. Press Run first.")
                        threading.Thread(target=run, daemon=True).start()
                    return cb
                w = CanvasButton(self.canvas, x, y, width, height, label,
                                  command=make_psy2_button_cb(label), move_callback=self.on_widget_moved)
                w.lock_check = lambda: self.lock_layout
                self.widgets.append(w)
                self.last_widget = w

    def _collect_widget_values(self):
        """Read current widget values from the canvas into self.state and FX overrides."""
        self._fx_overrides = {}  # e.g. {'distortion.drive': 1.0, 'delay.time': 0.5}
        for w in self.widgets:
            target = getattr(w, 'target', None)
            if target is None:
                continue
            # Textboxes
            if hasattr(w, 'get_text'):
                val = w.get_text()
                if val:
                    if target in ('count', 'passes', 'seed'):
                        try: val = int(val)
                        except ValueError: pass
                    elif target in ('duration',):
                        try: val = float(val)
                        except ValueError: pass
                    elif target in ('exact', 'loop', 'zeroc', 'wavetable', 'destructive', 'round_robin', 'nitro'):
                        val = str(val).lower() == 'true'
                    self.state[target] = val
            # Knobs / Sliders — dotted targets like "chorus.depth"
            elif hasattr(w, 'value'):
                self._fx_overrides[target] = w.value
            # Toggles
            elif hasattr(w, 'is_on'):
                if target in self.state:
                    self.state[target] = w.is_on
                elif '.' in target:
                    self._fx_overrides[target] = w.is_on

    def _apply_random_seed(self):
        """Apply random seed if specified in state."""
        seed = self.state.get('seed')
        if seed is not None:
            import random
            import numpy as np
            self.log(f"[PSY2] Seeding RNG with {seed}")
            random.seed(seed)
            np.random.seed(seed)

    def _run_psy2_generation(self, result):
        """Run figlib generation from PSY2 evaluator output."""
        # self.state has been updated by _collect_widget_values already
        state = self.state
        bus_rules = result.get('bus_rules', [])

        # Apply knob/slider overrides to bus_rules FX params
        import copy
        bus_rules = copy.deepcopy(bus_rules)  # Don't mutate the original
        for bus_rule in bus_rules:
            bus_id = bus_rule.get('id', '')
            
            mute_key = f"bus.{bus_id}.mute"
            if mute_key in self._fx_overrides:
                bus_rule['mute'] = self._fx_overrides[mute_key]
            
            solo_key = f"bus.{bus_id}.solo"
            if solo_key in self._fx_overrides:
                bus_rule['solo'] = self._fx_overrides[solo_key]

            # Structural Overrides (e.g., from Textboxes in self.state)
            # bus.Lead.osc = "saw,square"
            osc_target = f"bus.{bus_id}.osc"
            if osc_target in self.state:
                val = self.state[osc_target]
                if val and isinstance(val, str):
                    bus_rule['oscillators'] = [o.strip() for o in val.split(',') if o.strip()]

            # bus.Lead.fx = "moog(cutoff=0.4),reverb(mix=0.5)"
            fx_target = f"bus.{bus_id}.fx"
            if fx_target in self.state:
                val = self.state[fx_target]
                if val and isinstance(val, str):
                    from pySynth.parsing import parse_fx_string
                    bus_rule['effects'] = parse_fx_string(val)

            # bus.Lead.volume override from textbox or slider
            vol_target = f"bus.{bus_id}.volume"
            if vol_target in self.state:
                try: bus_rule['volume'] = float(self.state[vol_target])
                except: pass
            elif vol_target in self._fx_overrides:
                bus_rule['volume'] = self._fx_overrides[vol_target]

            for fx in bus_rule.get('effects', []):
                fx_name = fx['type']
                for param_key, param_val in list(fx.get('params', {}).items()):
                    # Exact bus match: e.g. "ChipLead.distortion.drive"
                    bus_override_key = f"{bus_id}.{fx_name}.{param_key}"
                    # Global fallback match: e.g. "distortion.drive"
                    global_override_key = f"{fx_name}.{param_key}"
                    
                    if bus_override_key in self._fx_overrides:
                        fx['params'][param_key] = self._fx_overrides[bus_override_key]
                    elif global_override_key in self._fx_overrides:
                        fx['params'][param_key] = self._fx_overrides[global_override_key]

        # Build fx_rules in the format execute_generation expects:
        # {'only': [{'type': 'chorus', 'params': {...}}, ...]}
        all_fx = []
        all_osc = set()
        for bus_rule in bus_rules:
            for fx in bus_rule.get('effects', []):
                all_fx.append({'type': fx['type'], 'params': fx.get('params', {})})
            for osc in bus_rule.get('oscillators', []):
                all_osc.add(osc)

        fx_rules = {'only': all_fx} if all_fx else {}
        osc_rules = {'only': list(all_osc)} if all_osc else {}
        lfo_rules = state.get('lfo_rules', {})

        self._apply_random_seed()

        progression = state.get('progression', None)
        if progression and str(progression).strip():
            # Progression mode — call execute_progression instead
            self.log(f"[PSY2] Generating progression: {progression}, genre={state.get('genre', 'pad')}, out={state.get('out', './output')}")
            try:
                # Robustly resolve passes (avoiding None if key exists in state)
                passes_val = state.get('passes')
                if passes_val is None:
                    passes_val = state.get('count', 1)
                    
                execute_progression(
                    progression=str(progression),
                    passes=passes_val,
                    out=state.get('out', './output'),
                    duration=state.get('duration', 4.0),
                    genre=state.get('genre', 'pad'),
                    fx_rules=fx_rules,
                    osc_rules=osc_rules,
                    lfo_rules=lfo_rules,
                    bus_rules=bus_rules,
                    scale=state.get('scale', None),
                    loop=state.get('loop', False),
                    zeroc=state.get('zeroc', False),
                    nitro=state.get('nitro', False),
                    exact=state.get('exact', False),
                )
                self.log("[PSY2] Progression complete.")
            except Exception as e:
                self.log(f"[PSY2] Progression error: {e}")
        elif state.get('scale') and state.get('passes'):
            # Scale Sweep Mode
            self.log(f"[PSY2] Generating scale sweep: {state['scale']}, {state['passes']} passes")
            from pySynth.main import execute_scale_sweep
            try:
                execute_scale_sweep(
                    scale=state['scale'],
                    passes=state['passes'],
                    out=state.get('out', './output'),
                    duration=state.get('duration', 4.0),
                    genre=state.get('genre', 'pad'),
                    note=state.get('note', 'C4'),
                    fx_rules=fx_rules,
                    osc_rules=osc_rules,
                    lfo_rules=lfo_rules,
                    bus_rules=bus_rules,
                    loop=state.get('loop', False),
                    zeroc=state.get('zeroc', False),
                    nitro=state.get('nitro', False),
                    exact=state.get('exact', False),
                )
                self.log("[PSY2] Scale sweep complete.")
            except Exception as e:
                self.log(f"[PSY2] Scale sweep error: {e}")
        else:
            # Standard generation
            self.log(f"[PSY2] Generating: count={state.get('count', 1)}, genre={state.get('genre', 'pad')}, note={state.get('note')}, out={state.get('out', './output')}")
            try:
                execute_generation(
                    count=state.get('count', 1),
                    out=state.get('out', './output'),
                    note=state.get('note', None),
                    duration=state.get('duration', 4.0),
                    genre=state.get('genre', 'pad'),
                    fx_rules=fx_rules,
                    osc_rules=osc_rules,
                    lfo_rules=lfo_rules,
                    bus_rules=bus_rules,
                    scale=state.get('scale', None),
                    loop=state.get('loop', False),
                    zeroc=state.get('zeroc', False),
                    round_robin=state.get('round_robin', False),
                    macro_spec=state.get('macro', None),
                    wavetable_export=state.get('wavetable', False),
                    sample_path=state.get('sample', None),
                    sample_folder=state.get('sample_folder', None),
                    destructive=state.get('destructive', False),
                    fxpreset=state.get('fxpreset', None),
                    nitro=state.get('nitro', False),
                    exact=state.get('exact', False),
                )
                self.log("[PSY2] Generation complete.")
            except Exception as e:
                self.log(f"[PSY2] Generation error: {e}")

    def execute_blocks(self, blocks, parent_bus=None):
        for block_type, *args in blocks:
            if block_type == 'line':
                self.execute_line(args[0], parent_bus=parent_bus)
            elif block_type == 'loop':
                count_str, block_lines = args
                count = int(self.resolve_value(count_str))
                
                # Parse internal blocks
                parsed_inner = []
                j = 0
                while j < len(block_lines):
                    inner_line = block_lines[j].strip()
                    if any(inner_line.startswith(kw) for kw in ['loop', 'button', 'bus']):
                        p = inner_line.split(maxsplit=2)
                        c_str = " ".join(p[1:]) if len(p) > 1 else ""
                        inner_block = []
                        j += 1
                        nested = 0
                        while j < len(block_lines):
                            deep_line = block_lines[j].strip()
                            if any(deep_line.startswith(kw) for kw in ['loop', 'button', 'bus']): nested += 1
                            elif deep_line == 'end':
                                if nested == 0: break
                                nested -= 1
                            inner_block.append(deep_line)
                            j += 1
                        parsed_inner.append((inner_line.split()[0], c_str, inner_block))
                    else:
                        parsed_inner.append(('line', inner_line))
                    j += 1

                for _ in range(count):
                    self.execute_blocks(parsed_inner, parent_bus=parent_bus)
            elif block_type == 'button':
                args_str, block_lines = args
                self.create_button(args_str, block_lines, parent_bus=parent_bus)
            elif block_type == 'bus':
                args_str, block_lines = args
                self.create_bus(args_str, block_lines, parent_bus=parent_bus)

    def create_bus(self, args_str, block_lines, parent_bus=None):
        import shlex
        parts = shlex.split(args_str)
        if not parts: return
        bus_header = parts[0]
        bus_id = bus_header.split(':', 1)[0] if ':' in bus_header else bus_header
        
        # bus id [x y] [w h] [color]
        # We allow omitting w, h to trigger auto-sizing
        if len(parts) >= 5:
            x = int(self.resolve_value(parts[1]))
            y = int(self.resolve_value(parts[2]))
            w = int(self.resolve_value(parts[3]))
            h = int(self.resolve_value(parts[4]))
            color = parts[5] if len(parts) > 5 else "#34495e"
        elif len(parts) >= 3:
            # target x y [color] -> auto-size dimensions
            x = int(self.resolve_value(parts[1]))
            y = int(self.resolve_value(parts[2]))
            w, h = 100, 100 # Initial, will be resized
            color = parts[3] if len(parts) > 3 else "#34495e"
        else:
            # target [color] -> auto-layout everything
            color = parts[1] if len(parts) > 1 else "#34495e"
            w, h = 200, 150
            x, y = self.get_next_widget_pos(w, h, margin=30)

        from .widgets import BusContainer
        bus = None
        if self.canvas:
            try:
                bus = BusContainer(self.canvas, x, y, w, h, bus_id, color, self.on_widget_moved)
                bus.lock_check = lambda: self.lock_layout
                bus.parent_bus = parent_bus
                bus.children = []
                if parent_bus: parent_bus.children.append(bus)
                self.widgets.append(bus)
            except: pass

        # Register audio bus in the engine
        # Support full CLI syntax: id:osc>fx
        execute_interpreter_command("bus", parts[0], self.state, context="IDE")
        
        # Execute inner commands
        parsed_inner = []
        for line in block_lines:
            parsed_inner.append(('line', line))
        self.execute_blocks(parsed_inner, parent_bus=bus)
        
        # Auto-Size if coordinates were not fully provided
        if self.canvas and bus and len(parts) < 5 and bus.children:
            min_x = min_y = float('inf')
            max_x = max_y = float('-inf')
            
            for child in bus.children:
                # Get bbox on canvas for accuracy
                bbox = self.canvas.bbox(child.widget_id)
                if bbox:
                    min_x = min(min_x, bbox[0])
                    min_y = min(min_y, bbox[1])
                    max_x = max(max_x, bbox[2])
                    max_y = max(max_y, bbox[3])
            
            if min_x != float('inf'):
                padding = 20
                header_h = 25
                new_x = min_x - padding
                new_y = min_y - header_h - padding
                new_w = (max_x - min_x) + 2 * padding
                new_h = (max_y - min_y) + header_h + 2 * padding
                
                bus.resize(new_x, new_y, new_w, new_h)
                
                # Update script with auto-sized coords
                self.on_widget_moved(bus_id, new_x, new_y)

    def create_button(self, args_str, block_lines, parent_bus=None):
        import shlex
        parts = shlex.split(args_str)
        if not parts: return
        
        label = parts[0]
        
        # Check if coordinates are provided: label [x y] w h
        if len(parts) >= 5:
            x = int(self.resolve_value(parts[1]))
            y = int(self.resolve_value(parts[2]))
            w = int(self.resolve_value(parts[3]))
            h = int(self.resolve_value(parts[4]))
        else:
            w = int(self.resolve_value(parts[1])) if len(parts) > 1 else 120
            h = int(self.resolve_value(parts[2])) if len(parts) > 2 else 40
            x, y = self.get_next_widget_pos(w, h, margin=20)
        
        def button_callback():
            import threading
            def run_logic():
                # For button execution, we don't reset state
                # Re-parse block_lines with support for nested structures
                parsed_inner = []
                j = 0
                while j < len(block_lines):
                    inner_line = block_lines[j].strip()
                    if inner_line.startswith('loop') or inner_line.startswith('button') or inner_line.startswith('bus') or inner_line.startswith('textbox'):
                        p = inner_line.split(maxsplit=2)
                        c_str = " ".join(p[1:]) if len(p) > 1 else ""
                        inner_block = []
                        j += 1
                        nested = 0
                        while j < len(block_lines):
                            deep_line = block_lines[j].strip()
                            if deep_line.startswith('loop') or deep_line.startswith('button') or deep_line.startswith('bus') or deep_line.startswith('textbox'): nested += 1
                            elif deep_line == 'end':
                                if nested == 0: break
                                nested -= 1
                            inner_block.append(deep_line)
                            j += 1
                        parsed_inner.append((inner_line.split()[0], c_str, inner_block))
                    elif inner_line and not inner_line.startswith('#'):
                        parsed_inner.append(('line', inner_line))
                    j += 1
                
                self.log(f"\n[IDE] Button '{label}' Pressed.")
                
                # Temporarily disable UI-only mode for button-triggered execution
                old_ui = self.ui_only_mode
                self.ui_only_mode = False
                try:
                    self.execute_blocks(parsed_inner, parent_bus=parent_bus)
                finally:
                    self.ui_only_mode = old_ui
            
            t = threading.Thread(target=run_logic, daemon=True)
            t.start()
                
        if self.canvas:
            from .widgets import CanvasButton
            btn = CanvasButton(self.canvas, x, y, w, h, label, button_callback, self.on_widget_moved)
            btn.lock_check = lambda: self.lock_layout
            btn.parent_bus = parent_bus
            if parent_bus: parent_bus.children.append(btn)
            self.widgets.append(btn)
            

    def execute_line(self, line, parent_bus=None):
        line = line.strip()
        if not line or line.startswith('#'):
             return

        parts = line.split(maxsplit=1)
        if not parts: return
        
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        # Variable Assignment / Expression
        if cmd.startswith('$'):
            var_name = cmd[1:]
            if arg.startswith('='):
                expr = arg[1:].strip()
                val = self.evaluate_expression(expr)
                self.variables[var_name] = val
            return

        # UI Commands
        if self.canvas:
            if cmd == 'rect':
                self.draw_rect(arg)
                return
            elif cmd == 'circle':
                self.draw_circle(arg)
                return
            elif cmd == 'text':
                self.draw_text(arg)
                return
            elif cmd == 'slider':
                self.last_widget = self.create_slider(arg, parent_bus=parent_bus)
                return
            elif cmd == 'knob':
                self.last_widget = self.create_knob(arg, parent_bus=parent_bus)
                return
            elif cmd == 'textbox':
                self.last_widget = self.create_textbox(arg, parent_bus=parent_bus)
                return
            elif cmd == 'toggle':
                self.last_widget = self.create_toggle(arg, parent_bus=parent_bus)
                return
            elif cmd == 'range':
                if self.last_widget:
                    try:
                        p = arg.split()
                        if len(p) >= 2:
                            min_v = float(p[0])
                            max_v = float(p[1])
                            self.last_widget.rand_range = (min_v, max_v)
                    except ValueError: pass
                return
            elif cmd == 'clear':
                self.canvas.delete("all")
                self.widgets.clear()
                self._next_widget_y = 20
                self._next_widget_x = 20
                return

        # Handle implicit FX targeting prior to generate
        if cmd in ['generate', 'progression', 'pad']:
            self.apply_implicit_fx()
            
        # Resolve variables in the argument
        resolved_arg = arg
        if '$' in arg:
            sorted_vars = sorted(self.variables.keys(), key=len, reverse=True)
            for var in sorted_vars:
                val = self.variables[var]
                resolved_arg = resolved_arg.replace(f"${var}", str(val))

        # Fallback to pySynth standard commands
        if self.ui_only_mode and cmd in ['generate', 'progression', 'pad']:
            return

        execute_interpreter_command(cmd, resolved_arg, self.state, context="IDE")
        
    def get_next_widget_pos(self, w, h, margin=20):
        max_width = 400 # Default
        if self.canvas:
            try: max_width = int(self.canvas.winfo_width())
            except: pass
            
        if self._next_widget_x + w > max_width and self._next_widget_x > 20:
             self._next_widget_x = 20
             self._next_widget_y += h + margin + 10
             
        x, y = self._next_widget_x, self._next_widget_y
        self._next_widget_x += w + margin
        return x, y

    def sync_to_editor(self):
        """Syncs all current widget positions back to the script code."""
        if not self.editor: return
        targets_to_update = {w.target: (w.x, w.y) for w in self.widgets}
        self._update_editor_content(targets_to_update)

    def on_widget_moved(self, target, x, y):
        """Callback from widget when dragged. Updates code in editor."""
        if not self.editor: return
        
        # Find the widget object that moved
        moved_widget = None
        for w in self.widgets:
            if w.target == target:
                moved_widget = w
                break
        
        if not moved_widget: return
        
        # Calculate deltas for child movement if it's a bus
        dx = x - moved_widget.x
        dy = y - moved_widget.y
        
        # Update moved widget's internal state
        moved_widget.x = x
        moved_widget.y = y
        
        # Recursively update children visually and gather all targets that moved
        targets_to_update = {target: (x, y)}
        
        if hasattr(moved_widget, "children"):
            self._move_children_recursive(moved_widget, dx, dy, targets_to_update)

        self._update_editor_content(targets_to_update)

    def _update_editor_content(self, targets_to_update):
        """Internal helper to refresh editor text with new coordinates."""
        content = self.editor.get("1.0", tk.END).splitlines()
        new_content = []
        import shlex
        
        for line in content:
            stripped = line.strip()
            try:
                parts = shlex.split(stripped)
                if len(parts) > 1 and parts[0] in ['knob', 'slider', 'button', 'bus', 'textbox', 'toggle']:
                    t_id = parts[1]
                    if t_id in targets_to_update:
                        new_x, new_y = targets_to_update[t_id]
                        cmd = parts[0]
                        
                        # Find the actual widget to get w/h or other properties
                        mu = next((w for w in self.widgets if w.target == t_id), None)

                        if cmd in ['knob', 'slider', 'textbox']:
                            # mu is the widget instance
                            if cmd == 'knob':
                                r = int(mu.r) if mu and hasattr(mu, 'r') else 30
                                if len(parts) >= 7: # target x y r min max [val]
                                    parts[2] = str(int(new_x))
                                    parts[3] = str(int(new_y))
                                    parts[4] = str(r)
                                elif len(parts) == 6: # target x y min max val
                                    parts[2] = str(int(new_x))
                                    parts[3] = str(int(new_y))
                                else: # lacked coords
                                    parts.insert(2, str(int(new_x)))
                                    parts.insert(3, str(int(new_y)))
                                    if r != 30: parts.insert(4, str(r))
                            elif cmd == 'slider':
                                w = int(mu.w) if mu and hasattr(mu, 'w') else 200
                                if len(parts) >= 7: # target x y w min max [val]
                                    parts[2] = str(int(new_x))
                                    parts[3] = str(int(new_y))
                                    parts[4] = str(w)
                                elif len(parts) == 6: # target x y min max val
                                    parts[2] = str(int(new_x))
                                    parts[3] = str(int(new_y))
                                else: # lacked coords
                                    parts.insert(2, str(int(new_x)))
                                    parts.insert(3, str(int(new_y)))
                                    if w != 200: parts.insert(4, str(w))
                            elif cmd == 'toggle':
                                size = int(mu.size) if mu and hasattr(mu, 'size') else 20
                                if len(parts) >= 5: # target x y size val
                                    parts[2] = str(int(new_x))
                                    parts[3] = str(int(new_y))
                                else:
                                    parts.insert(2, str(int(new_x)))
                                    parts.insert(3, str(int(new_y)))
                            elif cmd == 'textbox':
                                w = int(mu.w) if mu and hasattr(mu, 'w') else 100
                                h = int(mu.h) if mu and hasattr(mu, 'h') else 20
                                if len(parts) >= 6: # target x y w h [def]
                                    parts[2] = str(int(new_x))
                                    parts[3] = str(int(new_y))
                                else:
                                    parts.insert(2, str(int(new_x)))
                                    parts.insert(3, str(int(new_y)))

                        elif cmd == 'button':
                            if len(parts) >= 5: # target x y w h [cmd]
                                parts[2] = str(int(new_x))
                                parts[3] = str(int(new_y))
                            else:
                                parts.insert(2, str(int(new_x)))
                                parts.insert(3, str(int(new_y)))

                        elif cmd == 'bus':
                            if mu and hasattr(mu, 'w'):
                                # bus id x y w h [color]
                                if len(parts) >= 5:
                                    parts[2] = str(int(new_x))
                                    parts[3] = str(int(new_y))
                                    parts[4] = str(int(mu.w))
                                    parts[5] = str(int(mu.h))
                                elif len(parts) >= 3: # id x y [color]
                                    parts[2] = str(int(new_x))
                                    parts[3] = str(int(new_y))
                                else: # Lack coords
                                    parts.insert(2, str(int(new_x)))
                                    parts.insert(3, str(int(new_y)))
                                    # If it was auto-resized, we should probably record the new size too if we want it to stick
                                    # But user might want it to stay auto-sizing.
                                    # We'll stick to target x y for now if they only provide target.
                        
                        # Re-quote consistently
                        reconstructed = [cmd]
                        # Re-quote the target/label if it has spaces
                        t_val = parts[1]
                        if ' ' in t_val: reconstructed.append(f'"{t_val}"')
                        else: reconstructed.append(t_val)
                        
                        for p in parts[2:]:
                            if ' ' in str(p): reconstructed.append(f'"{p}"')
                            else: reconstructed.append(str(p))
                        
                        line = "  " * (len(line) - len(line.lstrip())) + " ".join(reconstructed)
            except:
                pass
            new_content.append(line)
        
        current_cursor = self.editor.index(tk.INSERT)
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", "\n".join(new_content))
        try: self.editor.mark_set(tk.INSERT, current_cursor)
        except: pass
        
        if self.highlight_callback:
            self.highlight_callback()

    def _move_children_recursive(self, parent, dx, dy, targets_to_update):
        for child in parent.children:
            # Move on canvas
            self.canvas.move(child.widget_id, dx, dy)
            # Update internal state
            child.x += dx
            child.y += dy
            # Record for script update
            targets_to_update[child.target] = (child.x, child.y)
            # Recurse if needed
            if hasattr(child, "children"):
                self._move_children_recursive(child, dx, dy, targets_to_update)

    def apply_implicit_fx(self):
        """Build an --fx-include string utilizing targets dynamically from UI Widgets."""
        active_fx = {}
        for widget in self.widgets:
            if not getattr(widget, 'target', None): continue
            target = widget.target
            val = widget.value
            if val is None: continue # Skip buttons/buses for FX mapping if no value
            
            # Resolve variable tokens
            if isinstance(val, str) and val.startswith('$'):
                var_name = val[1:]
                val = self.variables.get(var_name, val)
            
            # Support deep targeting: bus.id.fx.param or fx.param
            if '.' in target:
                parts = target.split('.')
                if parts[0] == 'bus' and len(parts) >= 3:
                    bus_id = parts[1]
                    
                    # Handle bus property toggles like `bus.Drone.mute`
                    if len(parts) == 3 and parts[2] in ('mute', 'solo'):
                        for b in self.state['bus_rules']:
                            if b['id'] == bus_id:
                                b[parts[2]] = str(val).lower() == 'true'
                                break
                        continue
                        
                    if len(parts) >= 4:
                        # bus.id.fx.param
                        fx_name = parts[2]
                        fx_param = parts[3]
                    
                    # Find or create bus
                    bus_rule = None
                    for b in self.state['bus_rules']:
                         if b['id'] == bus_id:
                              bus_rule = b
                              break
                    if not bus_rule:
                         bus_rule = {'id': bus_id, 'oscillators': ['saw'], 'effects': []}
                         self.state['bus_rules'].append(bus_rule)
                         self.log(f"[IDE] Auto-created audio bus '{bus_id}'")
                    
                    # Find or create effect
                    fx_rule = None
                    for f in bus_rule['effects']:
                         if f['type'] == fx_name:
                              fx_rule = f
                              break
                    if not fx_rule:
                         fx_rule = {'type': fx_name, 'params': {}}
                         bus_rule['effects'].append(fx_rule)
                         self.log(f"[IDE] Auto-added effect '{fx_name}' to bus '{bus_id}'")
                    
                    # Set param
                    fx_rule['params'][fx_param] = float(val)
                else:
                    # fx.param (standard global fx-include)
                    fx_name = parts[0]
                    fx_param = parts[1]
                    if fx_name not in active_fx:
                        active_fx[fx_name] = []
                    active_fx[fx_name].append(f"{fx_param}={float(val):.2f}")
        # Construct fx-include string overrides for global FX
        global_sets = {}
        for widget in self.widgets:
            if not getattr(widget, 'target', None): continue
            target = widget.target
            val = widget.value
            if val is None: continue
            if '.' not in target:
                # Resolve value before passing to core
                resolved_val = val
                if isinstance(val, str) and val.startswith('$'):
                    var_name = val[1:]
                    resolved_val = self.variables.get(var_name, val)
                
                global_sets[target] = resolved_val
                self.variables[target] = resolved_val # Sync to local variables for $token support
                execute_interpreter_command("set", f"{target} {resolved_val}", self.state, context="IDE")

        if active_fx:
            fx_strings = []
            for fx_name, params in active_fx.items():
                params_str = ",".join(params)
                fx_strings.append(f"{fx_name}({params_str})")
            
            override_str = ",".join(fx_strings)
            execute_interpreter_command("set", f"fx-include {override_str}", self.state, context="IDE")

        # --- Patch Report ---
        self.log("\n[IDE] --- Patch Report ---")
        # 1. Global Overrides (Textboxes)
        if global_sets:
            ov_str = ", ".join([f"{k}={v}" for k, v in global_sets.items()])
            self.log(f"[IDE] Global Overrides: {ov_str}")

        # 2. Global FX
        if active_fx:
            for fx_name, params in active_fx.items():
                self.log(f"[IDE] Global FX: {fx_name}({', '.join(params)})")
        
        # 2. Bus Rules
        for bus in self.state['bus_rules']:
            oscs = ",".join(bus.get('oscillators', []))
            fx_list = []
            for fx in bus.get('effects', []):
                p_list = [f"{k}={v:.2f}" for k, v in fx.get('params', {}).items()]
                fx_list.append(f"{fx['type']}({', '.join(p_list)})")
            
            fx_str = f" → {', '.join(fx_list)}" if fx_list else ""
            self.log(f"[IDE] Bus '{bus['id']}': {oscs}{fx_str}")
        self.log("[IDE] --------------------\n")

            
    def create_slider(self, arg, parent_bus=None):
        import shlex
        parts = shlex.split(arg)
        if not parts: return
        target = parts[0]
        # Contextual Targeting: Prefix with bus.ID. if inside a bus and not absolute
        if parent_bus and not target.startswith("bus."):
             target = f"bus.{parent_bus.target}.{target}"
        
        # target [x y] w min max def
        if len(parts) >= 6:
            x = int(self.resolve_value(parts[1]))
            y = int(self.resolve_value(parts[2]))
            w = int(self.resolve_value(parts[3]))
            min_val = float(self.resolve_value(parts[4]))
            max_val = float(self.resolve_value(parts[5]))
            default_val = float(self.resolve_value(parts[6])) if len(parts) > 6 else min_val
        else:
            w = int(self.resolve_value(parts[1])) if len(parts) > 1 else 200
            min_val = float(self.resolve_value(parts[2])) if len(parts) > 2 else 0.0
            max_val = float(self.resolve_value(parts[3])) if len(parts) > 3 else 1.0
            default_val = float(self.resolve_value(parts[4])) if len(parts) > 4 else min_val
            x, y = self.get_next_widget_pos(w, 40)
        
        if self.canvas:
            from .widgets import CanvasSlider
            slider = CanvasSlider(self.canvas, x, y, w, target, min_val, max_val, default_val, self.on_widget_moved, display_name=self.get_display_label(target))
            slider.lock_check = lambda: self.lock_layout
            slider.parent_bus = parent_bus
            if parent_bus: parent_bus.children.append(slider)
            self.widgets.append(slider)

    def create_knob(self, arg, parent_bus=None):
        import shlex
        parts = shlex.split(arg)
        if not parts: return
        target = parts[0]
        
        # Macro Expansion: "[effect].all" -> create knobs for all params
        if target.endswith(".all"):
            prefix = target[:-4] # e.g. "moog" or "bus.Pads.moog"
            fx_type = prefix.split('.')[-1]
            
            from pySynth.routing import EFFECT_DISPATCH
            from pySynth.parsing import FX_PARAM_RANGES
            import inspect
            
            func = EFFECT_DISPATCH.get(fx_type)
            if not func:
                print(f"[IDE] Error: Unknown effect '{fx_type}' for .all macro")
                return
                
            sig = inspect.signature(func)
            # Use ranges if available, otherwise default 0-1
            ranges = FX_PARAM_RANGES.get(fx_type, {})
            
            # Extract radii if provided
            r = int(self.resolve_value(parts[1])) if len(parts) > 1 else 30
            
            for name, param in sig.parameters.items():
                if name in ('audio', 'sample_rate', 'kwargs'): continue
                if param.kind == param.VAR_KEYWORD: continue
                # Skip non-numeric or complex params for now if possible? 
                # Most are float/int.
                
                p_min, p_max = ranges.get(name, (0.0, 1.0))
                # Re-invoke recursively. 
                # We DON'T prefix with bus here because the recursive call will handle it
                # OR we pass the absolute target.
                # If we pass prefix.name, and parent_bus is present, it might double-prefix?
                # Actually if prefix = "bus.Pads.moog", and we call f"{prefix}.{name}", 
                # target will start with "bus.", so recursive call won't prefix. Correct.
                sub_arg = f'"{prefix}.{name}" {r} {p_min} {p_max} {p_min}'
                self.create_knob(sub_arg, parent_bus=parent_bus)
            return

        # Contextual Targeting: Prefix with bus.ID. if inside a bus and not absolute
        if parent_bus and not target.startswith("bus."):
             target = f"bus.{parent_bus.target}.{target}"
        
        # target [x y] [r] min max [def]
        if len(parts) >= 6:
            # Check if likely coordinate-based: target x y ...
            # length >= 6 could be:
            # T X Y R Min Max [Val] (length 7+)
            # T X Y Min Max Val (length 6)
            if len(parts) >= 7:
                x = int(self.resolve_value(parts[1]))
                y = int(self.resolve_value(parts[2]))
                r = int(self.resolve_value(parts[3]))
                min_val = float(self.resolve_value(parts[4]))
                max_val = float(self.resolve_value(parts[5]))
                default_val = float(self.resolve_value(parts[6])) if len(parts) > 6 else min_val
            else:
                # length 6: T X Y Min Max Val (no radius)
                # OR length 6: T R Min Max Val (auto-layout)?
                # We assume if parts[1] is > 150, it's a coordinate. Radius is usually small.
                p1_val = float(self.resolve_value(parts[1]))
                p2_val = float(self.resolve_value(parts[2]))
                if p1_val > 150 or p2_val > 150:
                    x = int(p1_val)
                    y = int(p2_val)
                    r = 30
                    min_val = float(self.resolve_value(parts[3]))
                    max_val = float(self.resolve_value(parts[4]))
                    default_val = float(self.resolve_value(parts[5]))
                else:
                    # T R Min Max Val -> Auto-layout
                    r = int(p1_val)
                    min_val = float(p2_val)
                    max_val = float(self.resolve_value(parts[3]))
                    default_val = float(self.resolve_value(parts[4])) if len(parts) > 4 else min_val
                    x_aut, y_aut = self.get_next_widget_pos(r*2 + 20, r*2 + 50)
                    x, y = x_aut + r, y_aut + r + 20
        else:
            # length < 6: T R Min Max [def] -> Auto-layout
            r = int(self.resolve_value(parts[1])) if len(parts) > 1 else 30
            min_val = float(self.resolve_value(parts[2])) if len(parts) > 2 else 0.0
            max_val = float(self.resolve_value(parts[3])) if len(parts) > 3 else 1.0
            default_val = float(self.resolve_value(parts[4])) if len(parts) > 4 else min_val
            x_aut, y_aut = self.get_next_widget_pos(r*2 + 20, r*2 + 50)
            x, y = x_aut + r, y_aut + r + 20
        
        if self.canvas:
            from .widgets import CanvasKnob
            knob = CanvasKnob(self.canvas, x, y, r, target, min_val, max_val, default_val, self.on_widget_moved, display_name=self.get_display_label(target))
            knob.lock_check = lambda: self.lock_layout
            knob.parent_bus = parent_bus
            if parent_bus: parent_bus.children.append(knob)
            self.widgets.append(knob)

    def create_textbox(self, arg, parent_bus=None):
        import shlex
        parts = shlex.split(arg)
        if not parts: return
        target = parts[0]
        
        # Contextual Targeting: Prefix with bus.ID. if inside a bus and not absolute
        if parent_bus and not target.startswith("bus."):
             target = f"bus.{parent_bus.target}.{target}"
             
        # target "text" [x y] [w h]
        # Length 6+: target text x y w h
        # Length 5:  target text x y w
        # Length 4:  target text w h (auto-layout x, y)
        # Length 3:  target text w   (auto-layout x, y)
        # Length 2:  target text     (auto-layout x, y)

        if len(parts) >= 6:
            x = int(self.resolve_value(parts[1]))
            y = int(self.resolve_value(parts[2]))
            w = int(self.resolve_value(parts[3]))
            h = int(self.resolve_value(parts[4]))
            default_val = self.resolve_value(parts[5])
        elif len(parts) == 5:
            x = int(self.resolve_value(parts[1]))
            y = int(self.resolve_value(parts[2]))
            w = int(self.resolve_value(parts[3]))
            h = 25
            default_val = self.resolve_value(parts[4])
        elif len(parts) == 4:
            w = int(self.resolve_value(parts[1]))
            h = int(self.resolve_value(parts[2]))
            default_val = self.resolve_value(parts[3])
            x, y = self.get_next_widget_pos(w, h + 20)
        elif len(parts) == 3:
            w = int(self.resolve_value(parts[1]))
            default_val = self.resolve_value(parts[2])
            h = 25
            x, y = self.get_next_widget_pos(w, h + 20)
        else: # target [text]
            default_val = self.resolve_value(parts[1]) if len(parts) > 1 else ""
            w, h = 150, 25
            x, y = self.get_next_widget_pos(w, h + 20)
            
        choices = None
        if default_val == "all" and "genre" in target:
            from pySynth.main import GENRE_CHOICES
            choices = GENRE_CHOICES
            default_val = choices[0] if choices else "pad"
        elif "," in default_val:
            choices = [c.strip() for c in default_val.split(",")]
            default_val = choices[0]

        if self.canvas:
            if choices:
                from .widgets import CanvasDropdown
                txt = CanvasDropdown(self.canvas, x, y, w, h, target, default_val, choices, self.on_widget_moved, display_name=self.get_display_label(target))
            else:
                from .widgets import CanvasTextbox
                txt = CanvasTextbox(self.canvas, x, y, w, h, target, default_val, self.on_widget_moved, display_name=self.get_display_label(target))
            
            txt.lock_check = lambda: self.lock_layout
            txt.parent_bus = parent_bus
            if parent_bus: parent_bus.children.append(txt)
            self.widgets.append(txt)

    def create_toggle(self, arg, parent_bus=None):
        import shlex
        parts = shlex.split(arg)
        if not parts: return
        target = parts[0]
        
        # Contextual Targeting: Prefix with bus.ID. if inside a bus and not absolute
        if parent_bus and not target.startswith("bus."):
             target = f"bus.{parent_bus.target}.{target}"
             
        # target [x y] [size] [val]
        if len(parts) >= 5:
            x = int(self.resolve_value(parts[1]))
            y = int(self.resolve_value(parts[2]))
            size = int(self.resolve_value(parts[3]))
            default_val = self.resolve_value(parts[4])
        elif len(parts) == 4:
            x = int(self.resolve_value(parts[1]))
            y = int(self.resolve_value(parts[2]))
            size = 20
            default_val = self.resolve_value(parts[3])
        elif len(parts) == 3:
            size = int(self.resolve_value(parts[1]))
            default_val = self.resolve_value(parts[2])
            x, y = self.get_next_widget_pos(size + 20, size + 20)
        elif len(parts) == 2:
            default_val = self.resolve_value(parts[1])
            size = 20
            x, y = self.get_next_widget_pos(size + 20, size + 20)
        else:
            default_val = "False"
            size = 20
            x, y = self.get_next_widget_pos(size + 20, size + 20)
            
        if self.canvas:
            from .widgets import CanvasToggle
            tog = CanvasToggle(self.canvas, x, y, size, target, default_val, self.on_widget_moved, display_name=self.get_display_label(target))
            tog.lock_check = lambda: self.lock_layout
            tog.parent_bus = parent_bus
            if parent_bus: parent_bus.children.append(tog)
            self.widgets.append(tog)

    def draw_rect(self, arg):
        try:
            parts = arg.split()
            x = int(self.resolve_value(parts[0]))
            y = int(self.resolve_value(parts[1]))
            w = int(self.resolve_value(parts[2]))
            h = int(self.resolve_value(parts[3]))
            color = parts[4] if len(parts) > 4 else "white"
            self.canvas.create_rectangle(x, y, x+w, y+h, fill=color, outline="")
        except Exception as e:
            print(f"Error drawing rect: {e}")

    def draw_circle(self, arg):
        try:
            parts = arg.split()
            x = int(self.resolve_value(parts[0]))
            y = int(self.resolve_value(parts[1]))
            r = int(self.resolve_value(parts[2]))
            color = parts[3] if len(parts) > 3 else "white"
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="")
        except Exception as e:
            print(f"Error drawing circle: {e}")
            
    def draw_text(self, arg):
        try:
            import shlex
            parts = shlex.split(arg)
            if not parts: return
            
            # Heuristic: Find coordinates
            # Case A: x y text [color]
            # Case B: text x y [color]
            try:
                x = int(self.resolve_value(parts[0]))
                y = int(self.resolve_value(parts[1]))
                text_str = parts[2]
                color = parts[3] if len(parts) > 3 else "black"
            except (ValueError, IndexError):
                # Try Case B: text x y [color]
                text_str = parts[0]
                x = int(self.resolve_value(parts[1]))
                y = int(self.resolve_value(parts[2]))
                color = parts[3] if len(parts) > 3 else "black"
                
            for var_name, var_val in self.variables.items():
                text_str = text_str.replace(f"${var_name}", str(var_val))
                
            if self.canvas:
                self.canvas.create_text(x, y, text=text_str, fill=color, anchor=tk.NW, font=("Consolas", 10))
        except Exception as e:
            print(f"Error drawing text: {e}")


