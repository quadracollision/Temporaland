"""
PSY2 Evaluator — Walks the AST and produces figlib-compatible output.

Output:
  - state: dict compatible with pySynth's get_default_state()
  - bus_rules: list of bus rule dicts for Randomizer.generate_patch()
  - ui_commands: list of WidgetDecl nodes for the IDE to render
  - connections: list of (source, target) tuples for the audio graph
"""
from .ast_nodes import (
    Program, BusDef, OscDecl, FxDecl, VolumeDecl, SampleDecl, ConnectDecl,
    Connection, ConfigBlock, LetDecl, ForLoop, UIBlock, WidgetDecl, Generate,
)


class EvalError(Exception):
    pass


class PsyEvaluator:
    def __init__(self):
        self.buses = {}           # name → BusDef node
        self.connections = []     # [(source, target), ...]
        self.variables = {}       # let bindings
        self.config = {}          # config block settings
        self.ui_widgets = []      # WidgetDecl list for IDE
        self.generate_count = None
        self._should_generate = False

    def evaluate(self, program: Program) -> dict:
        """
        Walk the program AST and return a result dict:
        {
            'state': {...},          # figlib-compatible state
            'bus_rules': [...],      # bus rule dicts
            'ui_widgets': [...],     # WidgetDecl nodes
            'connections': [...],    # (source, target) tuples
            'should_generate': bool, # True if 'generate' was called
        }
        """
        for stmt in program.statements:
            self._eval_statement(stmt)

        return {
            'state': self._build_state(),
            'bus_rules': self._build_bus_rules(),
            'ui_widgets': self.ui_widgets,
            'variables': self.variables,
            'connections': self.connections,
            'should_generate': self._should_generate,
        }

    def _eval_statement(self, node):
        if isinstance(node, BusDef):
            self._eval_bus_def(node)
        elif isinstance(node, Connection):
            self._eval_connection(node)
        elif isinstance(node, ConfigBlock):
            self._eval_config(node)
        elif isinstance(node, LetDecl):
            self._eval_let(node)
        elif isinstance(node, ForLoop):
            self._eval_for(node)
        elif isinstance(node, UIBlock):
            self._eval_ui_block(node)
        elif isinstance(node, Generate):
            self._eval_generate(node)
        else:
            raise EvalError(f"Unknown statement type: {type(node).__name__}")

    # ── Bus ──

    def _eval_bus_def(self, node: BusDef):
        name = self._resolve_string(node.name)
        self.buses[name] = node

    # ── Connection ──

    def _eval_connection(self, node: Connection):
        self.connections.append((node.source, node.target))

    # ── Config ──

    def _eval_config(self, node: ConfigBlock):
        for key, val in node.settings.items():
            self.config[key] = self._resolve_value(val)

    # ── Let ──

    def _eval_let(self, node: LetDecl):
        name = node.name
        if name.startswith('$'):
            name = name[1:]
        self.variables[name] = self._resolve_value(node.value)

    # ── For ──

    def _eval_for(self, node: ForLoop):
        var_name = node.var
        if var_name.startswith('$'):
            var_name = var_name[1:]
            
        start_v = self._resolve_value(node.start)
        end_v = self._resolve_value(node.end)
        
        try:
            start_v = int(float(start_v))
            end_v = int(float(end_v))
        except ValueError:
            raise EvalError(f"For loop bounds must resolve to integers, got {start_v}..{end_v}")
            
        for i in range(start_v, end_v + 1):
            self.variables[var_name] = i
            for stmt in node.body:
                # Pass all variables to substitute_node to capture local 'let' assignments
                self._eval_statement(self._substitute_node(stmt, node.var, i, self.variables))

    # ── UI ──

    def _eval_ui_block(self, node: UIBlock):
        for w in node.widgets:
            if isinstance(w, ForLoop):
                self._eval_for_ui(w)
            else:
                self.ui_widgets.append(w)

    def _eval_for_ui(self, node: ForLoop):
        var_name = node.var
        if var_name.startswith('$'):
            var_name = var_name[1:]
            
        start_v = self._resolve_value(node.start)
        end_v = self._resolve_value(node.end)
        
        try:
            start_v = int(float(start_v))
            end_v = int(float(end_v))
        except ValueError:
            raise EvalError(f"For loop bounds must resolve to integers, got {start_v}..{end_v}")
            
        for i in range(start_v, end_v + 1):
            self.variables[var_name] = i
            for stmt in node.body:
                if isinstance(stmt, ForLoop):
                    self._eval_for_ui(self._substitute_node(stmt, node.var, i))
                else:
                    # It's a WidgetDecl
                    sub_widget = self._substitute_node(stmt, node.var, i)
                    # We also need to resolve args for the widget
                    sub_widget.args = [self._resolve_value(arg) for arg in sub_widget.args]
                    # Also resolve ranges if present
                    if sub_widget.range_bounds is not None:
                        b1 = self._resolve_value(sub_widget.range_bounds[0])
                        b2 = self._resolve_value(sub_widget.range_bounds[1])
                        sub_widget.range_bounds = (b1, b2)
                    self.ui_widgets.append(sub_widget)

    # ── Generate ──

    def _eval_generate(self, node: Generate):
        self._should_generate = True
        if node.count is not None:
            self.generate_count = node.count

    # ── Build State ──

    def _build_state(self) -> dict:
        """Convert config + variables into the state dict pySynth expects."""
        from pySynth.main import get_default_state
        state = get_default_state()

        # Map config keys to state keys
        key_map = {
            'out': 'out',
            'output': 'out',
            'genre': 'genre',
            'note': 'note',
            'duration': 'duration',
            'count': 'count',
            'passes': 'passes',
            'exact': 'exact',
            'loop': 'loop',
            'zeroc': 'zeroc',
            'scale': 'scale',
            'fxpreset': 'fxpreset',
            'sample': 'sample',
            'wavetable': 'wavetable',
            'destructive': 'destructive',
            'nitro': 'nitro',
            'progression': 'progression',
            # New keys
            'seed': 'seed',
            'round-robin': 'round_robin',
            'round_robin': 'round_robin',
            'sample-folder': 'sample_folder',
            'sample_folder': 'sample_folder',
            'macro': 'macro',
            'lfo-rate': 'lfo_rate',
            'lfo_rate': 'lfo_rate',
            'lfo-depth': 'lfo_depth',
            'lfo_depth': 'lfo_depth',
        }

        for key, val in self.config.items():
            target_key = key_map.get(key, key)
            if target_key in state or target_key in ('lfo_rate', 'lfo_depth', 'macro', 'progression'):
                # Type coercion
                if target_key in ('count', 'passes', 'seed'):
                    state[target_key] = int(val)
                elif target_key in ('duration',):
                    state[target_key] = float(val)
                elif target_key in ('exact', 'loop', 'zeroc', 'wavetable', 'destructive', 'round_robin'):
                    if isinstance(val, str):
                        state[target_key] = val.lower() == 'true'
                    else:
                        state[target_key] = bool(val)
                elif target_key in ('lfo_rate', 'lfo_depth'):
                    # e.g., "0.5,2.0" -> (0.5, 2.0)
                    try:
                        parts = [float(x.strip()) for x in str(val).split(',')]
                        state['lfo_rules'][target_key.split('_')[1]] = tuple(parts) if len(parts) > 1 else (parts[0], parts[0])
                    except ValueError:
                        pass
                else:
                    state[target_key] = val

        # Override count from generate if specified
        if self.generate_count is not None:
            state['count'] = self.generate_count

        return state

    def _build_bus_rules(self) -> list:
        """Convert bus definitions into the bus_rules list pySynth expects."""
        rules = []
        for name, bus_node in self.buses.items():
            rule = {
                'id': str(name),
                'oscillators': [],
                'effects': [],
            }

            # Apply bus-level params
            if 'volume' in bus_node.params:
                rule['volume'] = self._resolve_value(bus_node.params['volume'])

            for item in bus_node.body:
                if isinstance(item, OscDecl):
                    resolved_oscs = [self._resolve_value(osc) for osc in item.waveforms]
                    rule['oscillators'].extend(resolved_oscs)
                elif isinstance(item, FxDecl):
                    fx_entry = {
                        'type': str(item.name),
                        'params': {k: self._resolve_value(v) for k, v in item.params.items()}
                    }
                    rule['effects'].append(fx_entry)
                elif isinstance(item, VolumeDecl):
                    rule['volume'] = self._resolve_value(item.value)
                elif isinstance(item, SampleDecl):
                    rule['sample'] = item.path
                elif isinstance(item, ConnectDecl):
                    # Sub-bus connection — resolve later in routing
                    if item.target not in rule:
                        rule.setdefault('sub_buses', [])
                    rule.setdefault('sub_buses', []).append(item.target)

            rules.append(rule)
        return rules

    # ── Helpers ──

    def _resolve_value(self, val):
        """Resolve variable references in values and auto-resolve random ranges if string."""
        import random, re
        
        if isinstance(val, list):
            return [self._resolve_value(v) for v in val]
            
        if isinstance(val, str):
            # Check for exactly $(...) for full Python expression evaluation
            if val.startswith('$(') and val.endswith(')'):
                expr = val[2:-1]
                try:
                    return eval(expr, {}, self.variables)
                except Exception as e:
                    raise EvalError(f"Error evaluating expression '{expr}': {e}")
            
            # Check for EXACT variable match ($var) -> preserves type
            if val.startswith('$') and re.match(r'^\$[a-zA-Z_]\w*$', val):
                var_name = val[1:]
                if var_name in self.variables:
                    return self._resolve_value(self.variables[var_name])
                raise EvalError(f"Undefined variable '${var_name}'")

            # Check for variable interpolation and math expressions
            if '$' in val or any(op in val for op in '+-*/()'):
                def replace_var(match):
                    v_name = match.group(1)
                    if v_name in self.variables:
                        return str(self._resolve_value(self.variables[v_name]))
                    raise EvalError(f"Undefined variable '${v_name}'")
                    
                # 1. Substitute $var if present
                resolved_str = re.sub(r'\$([a-zA-Z_]\w*)', replace_var, val)
                
                # 2. Math evaluation (including raw variables if no $ was present but math ops are)
                # Ensure it's a safe-ish math string
                if re.match(r'^[a-zA-Z_0-9\.\+\-\*\/\s\(\)]+$', resolved_str):
                    try:
                        # Pass self.variables as local context to allow bare 'i', 'cutoff' etc.
                        return eval(resolved_str, {"__builtins__": {}}, self.variables)
                    except Exception:
                        pass
                
                val = resolved_str
            
            # Auto-resolve random ranges like "0.2-0.8" or "10-50"
            if '-' in val and not val.startswith('-'):
                parts = val.split('-')
                if len(parts) == 2:
                    try:
                        # Try parsing as float first
                        min_v = float(parts[0])
                        max_v = float(parts[1])
                        # If both are ints without decimals, return int, else float
                        if '.' not in parts[0] and '.' not in parts[1]:
                            return random.randint(int(min_v), int(max_v))
                        return random.uniform(min_v, max_v)
                    except ValueError:
                        pass
        return val

    def _resolve_string(self, s: str) -> str:
        """Resolve $var substitutions in strings."""
        if '$' not in s:
            return s
        result = s
        for var, val in self.variables.items():
            result = result.replace(f'${var}', str(val))
        return result

    def _substitute_node(self, node, var_name, value, all_vars=None):
        """
        Deep-substitute $var in a node for for-loops.
        Returns a new node with substitutions applied.
        """
        import copy
        new_node = copy.deepcopy(node)

        sub_map = {f'${var_name}': str(value)}
        if all_vars:
            for k, v in all_vars.items():
                sub_map[f'${k}'] = str(v)

        def do_sub(s):
            if not isinstance(s, str): return s
            res = s
            for k, v in sub_map.items():
                res = res.replace(k, v)
            
            # Eagerly resolve expressions $(...) now if we are in a loop context
            if res.startswith('$(') and res.endswith(')'):
                try:
                    return self._resolve_value(res)
                except:
                    pass
            return res

        if isinstance(new_node, BusDef):
            new_node.name = do_sub(new_node.name)
            for k in list(new_node.params.keys()):
                new_v = do_sub(new_node.params[k])
                new_node.params[k] = new_v
            # Inner body substitution
            for item in new_node.body:
                if isinstance(item, OscDecl):
                    item.waveforms = [do_sub(w) for w in item.waveforms]
                elif isinstance(item, FxDecl):
                    for pk in list(item.params.keys()):
                        item.params[pk] = do_sub(item.params[pk])
                elif isinstance(item, VolumeDecl):
                    item.value = do_sub(item.value)
        elif isinstance(new_node, Connection):
            new_node.source = do_sub(new_node.source)
            new_node.target = do_sub(new_node.target)
        elif isinstance(new_node, WidgetDecl):
            for idx in range(len(new_node.args)):
                new_node.args[idx] = do_sub(new_node.args[idx])

        return new_node


def evaluate(source: str) -> dict:
    """Convenience: lex + parse + evaluate in one call."""
    from .parser import parse
    program = parse(source)
    evaluator = PsyEvaluator()
    return evaluator.evaluate(program)

