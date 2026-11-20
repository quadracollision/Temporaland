"""Convenience script to run pySynth from the project root."""
import sys
import os

# In PyInstaller bundle, _MEIPASS contains the extracted modules.
# In dev, pySynth is under src/.
if getattr(sys, '_MEIPASS', None):
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pySynth.cli import main
import pySynth
print(f"DEBUG: pySynth loaded from {pySynth.__file__}")

if __name__ == '__main__':
    main()

