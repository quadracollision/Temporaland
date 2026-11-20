"""
PSY2 Parser — Recursive descent parser that turns a token stream into an AST.

Grammar (simplified):
    program     → statement* EOF
    statement   → bus_def | config_block | connection | let_decl | for_loop | ui_block | generate | NEWLINE
    bus_def     → BUS IDENT params? LBRACE bus_body RBRACE
    params      → LPAREN param_list RPAREN
    param_list  → IDENT EQUALS value (COMMA IDENT EQUALS value)*
    bus_body    → (osc_decl | fx_decl | volume_decl | sample_decl | connect_decl | NEWLINE)*
    osc_decl    → OSC ident_list
    fx_decl     → FX IDENT params?
    volume_decl → VOLUME NUMBER
    sample_decl → SAMPLE STRING
    connect_decl→ CONNECT IDENT
    connection  → IDENT ARROW IDENT
    config_block→ CONFIG LBRACE config_body RBRACE
    config_body → (IDENT value NEWLINE)*
    let_decl    → LET IDENT EQUALS expr
    for_loop    → FOR IDENT IN NUMBER DOTDOT NUMBER LBRACE statement* RBRACE
    ui_block    → UI LBRACE widget_decl* RBRACE
    widget_decl → (KNOB|SLIDER|TEXTBOX|TOGGLE|BUTTON) arg* NEWLINE (RANGE NUMBER NUMBER)?
    generate    → GENERATE NUMBER?
"""
from .lexer import Token, TokenType, Lexer, LexerError
from .ast_nodes import (
    Program, BusDef, OscDecl, FxDecl, VolumeDecl, SampleDecl, ConnectDecl,
    Connection, ConfigBlock, LetDecl, ForLoop, UIBlock, WidgetDecl, Generate,
)


class ParseError(Exception):
    def __init__(self, message, token=None):
        loc = f" at L{token.line}:{token.col}" if token else ""
        super().__init__(f"Parse error{loc}: {message}")
        self.token = token


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        if self.pos >= len(self.tokens):
            return Token(TokenType.EOF, None, 0, 0)
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.peek()
        self.pos += 1
        return tok

    def expect(self, ttype: TokenType) -> Token:
        tok = self.peek()
        if tok.type != ttype:
            raise ParseError(f"Expected {ttype.name}, got {tok.type.name} ({tok.value!r})", tok)
        return self.advance()

    def match(self, *ttypes: TokenType) -> Token | None:
        if self.peek().type in ttypes:
            return self.advance()
        return None

    def expect_ident_or_expr(self) -> Token:
        tok = self.peek()
        if tok.type in (TokenType.IDENT, TokenType.EXPR, TokenType.STRING, TokenType.NUMBER):
            return self.advance()
        raise ParseError(f"Expected name or expression, got {tok.type.name} ({tok.value!r})", tok)

    def skip_newlines(self):
        while self.peek().type == TokenType.NEWLINE:
            self.advance()

    # ── Top-Level ──

    def parse(self) -> Program:
        """Entry point: parse the full program."""
        prog = Program()
        self.skip_newlines()
        while self.peek().type != TokenType.EOF:
            stmt = self._parse_statement()
            if stmt is not None:
                prog.statements.append(stmt)
            self.skip_newlines()
        return prog

    def _parse_statement(self):
        tok = self.peek()

        if tok.type == TokenType.BUS:
            return self._parse_bus_def()
        if tok.type == TokenType.CONFIG:
            return self._parse_config_block()
        if tok.type == TokenType.LET:
            return self._parse_let_decl()
        if tok.type == TokenType.FOR:
            return self._parse_for_loop()
        if tok.type == TokenType.UI:
            return self._parse_ui_block()
        if tok.type == TokenType.GENERATE:
            return self._parse_generate()
        if tok.type == TokenType.NEWLINE:
            self.advance()
            return None

        # Check for connection: IDENT -> IDENT
        if tok.type == TokenType.IDENT:
            # Look ahead for ARROW
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TokenType.ARROW:
                return self._parse_connection()
            # Unknown identifier at top level
            raise ParseError(f"Unexpected identifier '{tok.value}'", tok)

        raise ParseError(f"Unexpected token {tok.type.name} ({tok.value!r})", tok)

    # ── Bus Definition ──

    def _parse_bus_def(self) -> BusDef:
        self.expect(TokenType.BUS)
        name_tok = self.expect_ident_or_expr()
        bus = BusDef(name=name_tok.value)

        # Optional params: (volume=0.8, detune=0.05)
        if self.match(TokenType.LPAREN):
            bus.params = self._parse_param_list()
            self.expect(TokenType.RPAREN)

        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        # Parse body
        while self.peek().type != TokenType.RBRACE:
            if self.peek().type == TokenType.EOF:
                raise ParseError("Unexpected EOF — missing closing '}'")
            node = self._parse_bus_body_item()
            if node is not None:
                bus.body.append(node)
            self.skip_newlines()

        self.expect(TokenType.RBRACE)
        return bus

    def _parse_bus_body_item(self):
        tok = self.peek()
        if tok.type == TokenType.OSC:
            return self._parse_osc_decl()
        if tok.type == TokenType.FX:
            return self._parse_fx_decl()
        if tok.type == TokenType.VOLUME:
            return self._parse_volume_decl()
        if tok.type == TokenType.SAMPLE:
            return self._parse_sample_decl()
        if tok.type == TokenType.CONNECT:
            return self._parse_connect_decl()
        if tok.type == TokenType.NEWLINE:
            self.advance()
            return None
        raise ParseError(f"Unexpected token in bus body: {tok.type.name} ({tok.value!r})", tok)

    def _parse_osc_decl(self) -> OscDecl:
        self.expect(TokenType.OSC)
        tok = self.peek()
        if tok.type in (TokenType.IDENT, TokenType.EXPR, TokenType.STRING):
            waveforms = [self.advance().value]
        else:
            waveforms = [self.expect(TokenType.IDENT).value]
            
        while self.match(TokenType.COMMA):
            tok = self.peek()
            if tok.type in (TokenType.IDENT, TokenType.EXPR, TokenType.STRING):
                waveforms.append(self.advance().value)
            else:
                waveforms.append(self.expect(TokenType.IDENT).value)
        return OscDecl(waveforms=waveforms)

    def _parse_fx_decl(self) -> FxDecl:
        self.expect(TokenType.FX)
        name_tok = self.expect_ident_or_expr()
        fx = FxDecl(name=name_tok.value)
        if self.match(TokenType.LPAREN):
            fx.params = self._parse_param_list()
            self.expect(TokenType.RPAREN)
        return fx

    def _parse_volume_decl(self) -> VolumeDecl:
        self.expect(TokenType.VOLUME)
        val = self._parse_value()
        return VolumeDecl(value=val)

    def _parse_sample_decl(self) -> SampleDecl:
        self.expect(TokenType.SAMPLE)
        path = self.expect(TokenType.STRING).value
        return SampleDecl(path=path)

    def _parse_connect_decl(self) -> ConnectDecl:
        self.expect(TokenType.CONNECT)
        target = self.expect_ident_or_expr().value
        return ConnectDecl(target=target)

    # ── Connection ──

    def _parse_connection(self) -> Connection:
        source = self.expect_ident_or_expr().value
        self.expect(TokenType.ARROW)
        # Target can be IDENT, EXPR, or MASTER keyword
        if self.peek().type == TokenType.MASTER:
            target = self.advance().value
        else:
            target = self.expect_ident_or_expr().value
        return Connection(source=source, target=target)

    # ── Config ──

    def _parse_config_block(self) -> ConfigBlock:
        self.expect(TokenType.CONFIG)
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        settings = {}
        while self.peek().type != TokenType.RBRACE:
            if self.peek().type == TokenType.EOF:
                raise ParseError("Unexpected EOF in config block — missing '}'")
            if self.peek().type == TokenType.NEWLINE:
                self.advance()
                continue
            # key value
            key_tok = self.peek()
            if key_tok.type in (TokenType.IDENT, TokenType.GENERATE, TokenType.VOLUME,
                                TokenType.SAMPLE, TokenType.RANGE, TokenType.FX, TokenType.OSC):
                key = self.advance().value
            else:
                key = self.expect(TokenType.IDENT).value
            val = self._parse_value()
            settings[key] = val
            self.skip_newlines()

        self.expect(TokenType.RBRACE)
        return ConfigBlock(settings=settings)

    # ── Let / For ──

    def _parse_let_decl(self) -> LetDecl:
        self.expect(TokenType.LET)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.EQUALS)
        value = self._parse_value()
        return LetDecl(name=name, value=value)

    def _parse_for_loop(self, context="stmt") -> ForLoop:
        self.expect(TokenType.FOR)
        var = self.expect(TokenType.IDENT).value
        self.expect(TokenType.IN)
        start_val = self._parse_value()
        self.expect(TokenType.DOTDOT)
        end_val = self._parse_value()
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        body = []
        while self.peek().type != TokenType.RBRACE:
            if self.peek().type == TokenType.EOF:
                raise ParseError("Unexpected EOF in for loop — missing '}'")
            if context == "ui":
                if self.peek().type == TokenType.FOR:
                    stmt = self._parse_for_loop(context="ui")
                else:
                    stmt = self._parse_widget_decl()
            else:
                stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
            self.skip_newlines()

        self.expect(TokenType.RBRACE)
        return ForLoop(var=var, start=start_val, end=end_val, body=body)

    # ── UI Block ──

    def _parse_ui_block(self) -> UIBlock:
        self.expect(TokenType.UI)
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        widgets = []
        while self.peek().type != TokenType.RBRACE:
            if self.peek().type == TokenType.EOF:
                raise ParseError("Unexpected EOF in @ui block — missing '}'")
            if self.peek().type == TokenType.NEWLINE:
                self.advance()
                continue
            if self.peek().type == TokenType.FOR:
                w = self._parse_for_loop(context="ui")
            else:
                w = self._parse_widget_decl()
            if w:
                widgets.append(w)
            self.skip_newlines()

        self.expect(TokenType.RBRACE)
        return UIBlock(widgets=widgets)

    def _parse_widget_decl(self) -> WidgetDecl | None:
        tok = self.peek()
        if tok.type not in (TokenType.KNOB, TokenType.SLIDER, TokenType.TEXTBOX,
                            TokenType.TOGGLE, TokenType.BUTTON):
            raise ParseError(f"Expected widget type (knob/slider/textbox/toggle/button), got {tok.type.name}", tok)

        kind = self.advance().value
        args = []

        # Read all args until newline, RBRACE, or RANGE
        while self.peek().type not in (TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF, TokenType.RANGE):
            val = self._parse_value()
            args.append(val)

        widget = WidgetDecl(kind=kind, args=args)

        # Check for optional range on next line
        self.skip_newlines()
        if self.peek().type == TokenType.RANGE:
            self.advance()
            min_v = self._parse_value()
            max_v = self._parse_value()
            widget.range_bounds = (min_v, max_v)

        return widget

    # ── Generate ──

    def _parse_generate(self) -> Generate:
        self.expect(TokenType.GENERATE)
        count = None
        if self.peek().type == TokenType.NUMBER:
            count = int(self.advance().value)
        return Generate(count=count)

    # ── Helpers ──

    def _parse_param_list(self) -> dict:
        """Parse: key=value, key=value, ..."""
        params = {}
        while self.peek().type not in (TokenType.RPAREN, TokenType.EOF):
            # Key can be IDENT or a keyword used as param name
            key_tok = self.peek()
            if key_tok.type == TokenType.IDENT:
                key = self.advance().value
            elif key_tok.type in KEYWORDS_AS_PARAM_NAMES:
                key = self.advance().value
            else:
                break
            self.expect(TokenType.EQUALS)
            val = self._parse_value()
            params[key] = val
            self.match(TokenType.COMMA)
        return params

    def _parse_value(self):
        """Parse a literal value: NUMBER, STRING, RANGE_LIT, IDENT, EXPR, List, or boolean."""
        tok = self.peek()
        if tok.type == TokenType.LBRACKET:
            self.advance() # skip [
            items = []
            while self.peek().type != TokenType.RBRACKET:
                items.append(self._parse_value())
                if self.peek().type == TokenType.COMMA:
                    self.advance()
                elif self.peek().type == TokenType.EOF:
                    raise ParseError("Unterminated list literal", self.peek())
            self.expect(TokenType.RBRACKET)
            return items

        if tok.type == TokenType.LPAREN:
            self.advance() # skip (
            val = self._parse_value()
            self.expect(TokenType.RPAREN)
            val = f"({val})" # keep parens for eval
            # Continue checking for binary ops after parens
            while self.peek().type in (TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH):
                 op = self.advance().value
                 next_val = self._parse_value()
                 val = f"{val}{op}{next_val}"
            return val

        # Handle unary minus
        if tok.type == TokenType.MINUS:
            self.advance()
            val = f"-{self._parse_value()}"
            return val

        # Read base value
        if tok.type == TokenType.NUMBER:
            val = self.advance().value
        elif tok.type in (TokenType.STRING, TokenType.EXPR):
            val = self.advance().value
        elif tok.type == TokenType.RANGE_LIT:
            val = self.advance().value  # e.g. "0.2-0.8" as string
        elif tok.type in (TokenType.IDENT, TokenType.MASTER, TokenType.VOLUME, TokenType.GENERATE,
                        TokenType.OSC, TokenType.FX, TokenType.SAMPLE, TokenType.RANGE,
                        TokenType.CONFIG, TokenType.BUS):
            val = self.advance().value
        else:
            raise ParseError(f"Expected value, got {tok.type.name} ({tok.value!r})", tok)

        # Check for binary operators (Expressions)
        # Avoid greedy consumption if we are inside a list or params (checked by delimiter peek)
        while self.peek().type in (TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH):
             op = self.advance().value
             next_val = self._parse_value() # recursive for chain
             val = f"({val}{op}{next_val})"
             
        return val


# Keywords that can also appear as parameter names (e.g. fx chorus(range=0.5))
KEYWORDS_AS_PARAM_NAMES = {
    TokenType.RANGE, TokenType.VOLUME, TokenType.SAMPLE,
}


def parse(source: str) -> Program:
    """Convenience: lex + parse in one call."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()

