"""
PSY2 AST Node Definitions.

Every construct in the language maps to a dataclass here.
The parser produces a tree of these nodes; the evaluator walks it.
"""
from dataclasses import dataclass, field
from typing import Any


# ── Top-level ──

@dataclass
class Program:
    """Root node — a list of top-level statements."""
    statements: list = field(default_factory=list)


# ── Bus ──

@dataclass
class BusDef:
    """
    bus Lead(volume=0.8, detune=0.05) {
      osc saw, square
      fx chorus(depth=0.5)
    }
    """
    name: str
    params: dict = field(default_factory=dict)   # keyword params on the bus itself
    body: list = field(default_factory=list)      # [OscDecl | FxDecl | VolumeDecl | ConnectDecl | SampleDecl]


@dataclass
class OscDecl:
    """osc saw, square"""
    waveforms: list = field(default_factory=list)


@dataclass
class FxDecl:
    """fx chorus(depth=0.5, rate=1.2)"""
    name: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class VolumeDecl:
    """volume 0.8"""
    value: Any = 1.0


@dataclass
class SampleDecl:
    """sample \"./kicks/\" """
    path: str = ""


@dataclass
class ConnectDecl:
    """connect Lead  (inside a bus body)"""
    target: str = ""


# ── Routing ──

@dataclass
class Connection:
    """Lead -> master"""
    source: str = ""
    target: str = ""


# ── Config ──

@dataclass
class ConfigBlock:
    """
    config {
      out "./output"
      count 5
    }
    """
    settings: dict = field(default_factory=dict)


# ── Variables & Control Flow ──

@dataclass
class LetDecl:
    """let depth = 0.5"""
    name: str = ""
    value: Any = None


@dataclass
class ForLoop:
    """
    for i in 1..3 {
      ...
    }
    """
    var: str = ""
    start: Any = 0
    end: Any = 0
    body: list = field(default_factory=list)


# ── UI ──

@dataclass
class UIBlock:
    """
    @ui {
      knob "chorus.depth" 420 80 25 0.0 1.0 0.8
      slider ...
    }
    """
    widgets: list = field(default_factory=list)


@dataclass
class WidgetDecl:
    """A single UI widget declaration inside @ui."""
    kind: str = ""       # knob, slider, textbox, toggle, button
    args: list = field(default_factory=list)
    range_bounds: tuple = None  # optional (min, max) from a following 'range' line


# ── Generate ──

@dataclass
class Generate:
    """generate or generate 5"""
    count: int = None

