"""Effect-parameter metadata and value conversion helpers."""

import inspect
import math


def numeric_defaults(func):
    values = {}
    for parameter in inspect.signature(func).parameters.values():
        if (parameter.name in ("audio", "sample_rate", "kwargs")
                or parameter.default is inspect.Parameter.empty):
            continue
        values[parameter.name] = parameter.default
    return values


def parameter_range(name, default):
    """Return a useful UI range for a FigLib numeric parameter."""
    key = name.lower()
    if key == "gain_db" or key.endswith("_db"):
        return (-24.0, 24.0, "linear")
    if key in ("cutoff", "freq", "frequency", "high_freq", "low_freq"):
        return (20.0, 20000.0, "log")
    if "threshold" in key or key == "ceiling":
        return (-60.0, 0.0, "linear")
    if "semitone" in key or "interval" in key or "detune" in key:
        return (-24.0, 24.0, "linear")
    if "ratio" in key:
        return (1.0, 20.0, "linear")
    if any(word in key for word in (
            "mix", "depth", "feedback", "amount", "resonance", "sustain",
            "warmth", "width", "drive", "gain", "tone", "presence", "bias",
            "position", "height", "density", "spray", "strike", "crackle", "hiss")):
        return (0.0, 1.0, "linear")
    if any(word in key for word in ("time", "decay", "release", "attack", "delay")):
        high = max(1.0, float(default) * 4.0) if isinstance(default, (int, float)) else 5.0
        return (0.0, min(10.0, high), "linear")
    if isinstance(default, (int, float)):
        high = max(1.0, abs(float(default)) * 2.0)
        low = -high if float(default) < 0 else 0.0
        return (low, high, "linear")
    return (0.0, 1.0, "linear")


def macro_to_parameter(value, limits):
    low, high, scale = limits
    if scale == "log":
        return low * ((high / low) ** value)
    return low + (high - low) * value


def parameter_to_macro(value, limits):
    low, high, scale = limits
    value = max(low, min(high, float(value)))
    if scale == "log":
        return math.log(value / low) / math.log(high / low)
    return (value - low) / max(1e-12, high - low)


ENUM_OPTIONS = {
    ("ams_reverb", "program"): ("nonlin", "ambience", "plate"),
    ("buchla_lpg", "mode"): ("filter", "vca", "both"),
    ("distortion", "dist_type"): (
        "tanh", "hard_clip", "soft_clip", "sine_fold",
        "rectify", "half_rectify", "waveshape"),
    ("filter", "filter_type"): (
        "lowpass", "highpass", "bandpass", "notch",
        "peaking", "low_shelf", "high_shelf", "allpass"),
    ("formant", "vowel"): ("a", "e", "i", "o", "u"),
    ("haas", "side"): ("left", "right"),
    ("la2a", "mode"): ("compress", "limit"),
    ("obxa", "mode"): ("lowpass", "bandpass", "highpass"),
    ("sem", "mode"): ("lowpass", "highpass", "bandpass", "notch"),
}

INTEGER_BOUNDS = {
    "bit_depth": (2, 16), "sample_rate_reduction": (1, 16),
    "voices": (1, 8), "stages": (1, 12), "repeats": (1, 16),
    "mode": (0, 4), "speed": (0, 2), "ratio": (1, 20),
}


def parameter_control_spec(name, default):
    key = name.lower()
    if isinstance(default, bool):
        return {"kind": "bool"}
    if not isinstance(default, (int, float)):
        return {"kind": "text"}
    if isinstance(default, int) and key in INTEGER_BOUNDS:
        low, high = INTEGER_BOUNDS[key]
        return {"kind": "knob", "low": low, "high": high, "integer": True}
    bounded_words = (
        "mix", "depth", "feedback", "amount", "resonance", "sustain",
        "warmth", "width", "drive", "gain", "tone", "presence", "bias",
        "position", "height", "density", "spray", "strike", "crackle",
        "hiss", "cutoff", "freq", "threshold", "ceiling", "ratio",
        "time", "decay", "release", "attack", "delay", "semitone",
        "interval", "detune",
    )
    if any(word in key for word in bounded_words):
        low, high, scale = parameter_range(name, default)
        return {
            "kind": "knob", "low": low, "high": high,
            "scale": scale, "integer": isinstance(default, int),
        }
    step = 1.0 if isinstance(default, int) else max(.01, abs(float(default)) * .02)
    return {"kind": "encoder", "step": step, "integer": isinstance(default, int)}
