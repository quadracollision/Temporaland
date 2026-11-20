"""
PSY2 Lexer — Tokenizes .psy2 source into a token stream.

Handles: keywords, identifiers, numbers, strings, symbols, ranges, comments.
"""
from enum import Enum, auto
from dataclasses import dataclass
from typing import Any


class TokenType(Enum):
    # Keywords
    BUS = auto()
    CONFIG = auto()
    GENERATE = auto()
    CONNECT = auto()
    OSC = auto()
    FX = auto()
    VOLUME = auto()
    SAMPLE = auto()
    RANGE = auto()
    LET = auto()
    FOR = auto()
    IN = auto()
    MASTER = auto()
    UI = auto()          # @ui

    # UI widget keywords
    KNOB = auto()
    SLIDER = auto()
    TEXTBOX = auto()
    TOGGLE = auto()
    BUTTON = auto()

    # Literals
    IDENT = auto()       # e.g. Lead, myVar
    NUMBER = auto()      # e.g. 0.5, 42
    STRING = auto()      # e.g. "./output"
    EXPR = auto()        # e.g. $(waveforms[i])
    RANGE_LIT = auto()   # e.g. 0.2-0.8, 1..3

    # Symbols
    LBRACE = auto()      # {
    RBRACE = auto()      # }
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    LBRACKET = auto()    # [
    RBRACKET = auto()    # ]
    COMMA = auto()       # ,
    ARROW = auto()       # ->
    EQUALS = auto()      # =
    DOTDOT = auto()      # ..
    PLUS = auto()        # +
    MINUS = auto()       # -
    STAR = auto()        # *
    SLASH = auto()       # /

    # Structural
    NEWLINE = auto()
    EOF = auto()


KEYWORDS = {
    'bus':      TokenType.BUS,
    'config':   TokenType.CONFIG,
    'generate': TokenType.GENERATE,
    'connect':  TokenType.CONNECT,
    'osc':      TokenType.OSC,
    'fx':       TokenType.FX,
    'volume':   TokenType.VOLUME,
    'sample':   TokenType.SAMPLE,
    'range':    TokenType.RANGE,
    'let':      TokenType.LET,
    'for':      TokenType.FOR,
    'in':       TokenType.IN,
    'master':   TokenType.MASTER,
    # UI
    'knob':     TokenType.KNOB,
    'slider':   TokenType.SLIDER,
    'textbox':  TokenType.TEXTBOX,
    'toggle':   TokenType.TOGGLE,
    'button':   TokenType.BUTTON,
}


@dataclass
class Token:
    type: TokenType
    value: Any
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:{self.col})"


class LexerError(Exception):
    def __init__(self, message, line, col):
        super().__init__(f"Syntax error at L{line}:{col}: {message}")
        self.line = line
        self.col = col


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    def peek(self) -> str:
        if self.pos >= len(self.source):
            return '\0'
        return self.source[self.pos]

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def match(self, expected: str) -> bool:
        if self.pos < len(self.source) and self.source[self.pos] == expected:
            self.advance()
            return True
        return False

    def _emit(self, ttype: TokenType, value: Any = None):
        self.tokens.append(Token(ttype, value, self.line, self.col))

    def tokenize(self) -> list[Token]:
        """Tokenize the entire source and return the token list."""
        while self.pos < len(self.source):
            ch = self.peek()

            # Skip whitespace (but not newlines)
            if ch in (' ', '\t', '\r'):
                self.advance()
                continue

            # Newlines (significant for statement separation)
            if ch == '\n':
                # Collapse multiple newlines into one
                if not self.tokens or self.tokens[-1].type != TokenType.NEWLINE:
                    self._emit(TokenType.NEWLINE, '\\n')
                self.advance()
                continue

            # Comments
            if ch == '#':
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
                continue

            # @ui keyword
            if ch == '@':
                self.advance()
                word = self._read_ident()
                if word == 'ui':
                    self._emit(TokenType.UI, '@ui')
                else:
                    raise LexerError(f"Unknown directive '@{word}'", self.line, self.col)
                continue

            # Symbols
            if ch == '{':
                self._emit(TokenType.LBRACE, '{'); self.advance(); continue
            if ch == '}':
                self._emit(TokenType.RBRACE, '}'); self.advance(); continue
            if ch == '(':
                self._emit(TokenType.LPAREN, '('); self.advance(); continue
            if ch == ')':
                self._emit(TokenType.RPAREN, ')'); self.advance(); continue
            if ch == '[':
                self._emit(TokenType.LBRACKET, '['); self.advance(); continue
            if ch == ']':
                self._emit(TokenType.RBRACKET, ']'); self.advance(); continue
            if ch == ',':
                self._emit(TokenType.COMMA, ','); self.advance(); continue
            if ch == '=':
                self._emit(TokenType.EQUALS, '='); self.advance(); continue
            if ch == '+':
                self._emit(TokenType.PLUS, '+'); self.advance(); continue
            if ch == '*':
                self._emit(TokenType.STAR, '*'); self.advance(); continue
            if ch == '/':
                # Check for path-like starting with /
                if self.pos + 1 < len(self.source) and (self.source[self.pos+1].isalnum() or self.source[self.pos+1] == '_'):
                    # Path-like, or at least start of path
                    path = self._read_path()
                    self._emit(TokenType.IDENT, path)
                else:
                    self._emit(TokenType.SLASH, '/'); self.advance()
                continue

            # Arrow -> or minus (part of negative number or range)
            if ch == '-':
                self.advance()  # consume -
                if self.peek() == '>':
                    self.advance()
                    self._emit(TokenType.ARROW, '->')
                elif self.peek().isdigit() or self.peek() == '.':
                    num = self._read_number(negative=True)
                    self._emit(TokenType.NUMBER, num)
                else:
                    self._emit(TokenType.MINUS, '-')
                continue

            # Dot-dot .. or path-like identifiers (./output)
            if ch == '.':
                self.advance()
                if self.peek() == '.':
                    self.advance()
                    self._emit(TokenType.DOTDOT, '..')
                elif self.peek() == '/' or self.peek().isalnum() or self.peek() == '_':
                    # Path like ./output or .hidden — read as identifier
                    self.pos -= 1  # back up to include the dot
                    self.col -= 1
                    path = self._read_path()
                    self._emit(TokenType.IDENT, path)
                else:
                    raise LexerError("Unexpected '.' (did you mean '..'?)", self.line, self.col)
                continue

            # Strings
            if ch == '"' or ch == "'":
                s = self._read_string(ch)
                self._emit(TokenType.STRING, s)
                continue

            # Numbers (and potential ranges like 0.2-0.8)
            if ch.isdigit():
                start_pos = self.pos
                num = self._read_number()
                # Check for range literal: 0.2-0.8
                if self.peek() == '-' and self.pos < len(self.source) - 1:
                    next_after = self.source[self.pos + 1] if self.pos + 1 < len(self.source) else '\0'
                    if next_after.isdigit() or next_after == '.':
                        self.advance()  # consume -
                        num2 = self._read_number()
                        self._emit(TokenType.RANGE_LIT, f"{num}-{num2}")
                        continue
                self._emit(TokenType.NUMBER, num)
                continue

            # Identifiers, keywords, and expressions
            if ch == '$':
                if self.pos + 1 < len(self.source) and self.source[self.pos+1] == '(':
                    # Expression inline $(...)
                    self.advance() # skip $
                    self.advance() # skip (
                    expr_start = self.pos
                    parens = 1
                    while self.pos < len(self.source):
                        if self.source[self.pos] == '(':
                            parens += 1
                        elif self.source[self.pos] == ')':
                            parens -= 1
                            if parens == 0:
                                break
                        self.pos += 1
                        self.col += 1
                    if self.pos >= len(self.source):
                        raise LexerError("Unterminated $(...) expression", self.line, self.col)
                    expr_val = self.source[expr_start:self.pos]
                    self.advance() # skip )
                    self._emit(TokenType.EXPR, f"$({expr_val})")
                    continue
                # Otherwise, it's just a variable ident like $var
                word = self._read_ident()
                self._emit(TokenType.IDENT, word)
                continue

            if ch.isalpha() or ch == '_':
                word = self._read_ident()
                # Check keywords
                if word in KEYWORDS:
                    self._emit(KEYWORDS[word], word)
                elif word == 'true' or word == 'false':
                    self._emit(TokenType.NUMBER, True if word == 'true' else False)
                else:
                    self._emit(TokenType.IDENT, word)
                continue

            raise LexerError(f"Unexpected character '{ch}'", self.line, self.col)

        self._emit(TokenType.EOF, None)
        return self.tokens

    def _read_ident(self) -> str:
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] in ('_', '$', '.')):
            self.pos += 1
            self.col += 1
        return self.source[start:self.pos]

    def _read_path(self) -> str:
        """Read a path-like token: ./output, ../foo, .hidden etc."""
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos] not in (' ', '\t', '\n', '\r', '{', '}', '(', ')', ',', '=', '#', '\0'):
            self.pos += 1
            self.col += 1
        return self.source[start:self.pos]

    def _read_number(self, negative=False) -> float | int:
        start = self.pos
        has_dot = False
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == '.'):
            if self.source[self.pos] == '.':
                # Check for .. (dot-dot range)
                if self.pos + 1 < len(self.source) and self.source[self.pos + 1] == '.':
                    break
                has_dot = True
            self.pos += 1
            self.col += 1
        text = self.source[start:self.pos]
        if negative:
            text = '-' + text
        if has_dot:
            return float(text)
        return int(text)

    def _read_string(self, quote_char: str) -> str:
        self.advance()  # skip opening quote
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos] != quote_char:
            if self.source[self.pos] == '\\':
                self.pos += 1  # skip escape
                self.col += 1
            self.pos += 1
            self.col += 1
        if self.pos >= len(self.source):
            raise LexerError("Unterminated string", self.line, self.col)
        result = self.source[start:self.pos]
        self.advance()  # skip closing quote
        return result

