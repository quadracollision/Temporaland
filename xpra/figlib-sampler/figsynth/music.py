"""Musical note and chord definitions used by FigSynth2."""

KEY_NOTES = {
    "z": 48, "s": 49, "x": 50, "d": 51, "c": 52, "v": 53, "g": 54,
    "b": 55, "h": 56, "n": 57, "j": 58, "m": 59, ",": 60,
    "q": 60, "2": 61, "w": 62, "3": 63, "e": 64, "r": 65, "5": 66,
    "t": 67, "6": 68, "y": 69, "7": 70, "u": 71, "i": 72,
}

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

CHORDS = {
    "Major": (0, 4, 7),
    "Minor": (0, 3, 7),
    "Major 6": (0, 4, 7, 9),
    "Minor 6": (0, 3, 7, 9),
    "6/9": (0, 4, 7, 9, 14),
    "Major 7": (0, 4, 7, 11),
    "Minor 7": (0, 3, 7, 10),
    "Minor major 7": (0, 3, 7, 11),
    "Dominant 7": (0, 4, 7, 10),
    "Major 9": (0, 4, 7, 11, 14),
    "Diminished": (0, 3, 6),
    "Diminished 7": (0, 3, 6, 9),
    "Half-diminished 7": (0, 3, 6, 10),
    "Augmented": (0, 4, 8),
    "Augmented 7": (0, 4, 8, 10),
    "Sus 2": (0, 2, 7),
    "Sus 4": (0, 5, 7),
    "7 sus 4": (0, 5, 7, 10),
    "Power": (0, 7, 12),
    "Add 9": (0, 4, 7, 14),
    "Minor add 9": (0, 3, 7, 14),
    "Minor 9": (0, 3, 7, 10, 14),
    "Dominant 9": (0, 4, 7, 10, 14),
    "Major 11": (0, 4, 7, 11, 14, 17),
    "Minor 11": (0, 3, 7, 10, 14, 17),
    "Dominant 11": (0, 4, 7, 10, 14, 17),
    "Major 13": (0, 4, 7, 11, 14, 21),
    "Minor 13": (0, 3, 7, 10, 14, 21),
    "Dominant 13": (0, 4, 7, 10, 14, 21),
    "Quartal": (0, 5, 10, 15),
    "Quintal": (0, 7, 14, 21),
}


def note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def notes_label(notes):
    return " + ".join(note_name(int(round(note))) for note in notes)
