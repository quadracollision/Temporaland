#!/usr/bin/env python3
"""Render speech samples from the shared studio without opening a shell."""

import os
import secrets
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

IMPORTS = Path("/srv/audacity-studio/imports")
ESPEAK = Path("/usr/bin/espeak-ng")
PIPER = Path("/opt/temporaman-piper-1.8.0/bin/python")
MODEL = Path("/usr/local/share/temporaman/speech/en_US-libritts_r-medium.onnx")
PAPLAY = Path("/usr/bin/paplay")
PREVIEW_VOLUME = 49152
DEMO_TEXT = "This is a voice preview from Temporaman. How does it sound?"
SYNTHETIC_VOICES = {
    "plain": "en-us",
    "bright": "en-us+f3",
    "deep": "en-us+m3",
    "whisper": "en-us+whisper",
    "retro": "en-us+klatt",
    "british": "en-gb",
}
SHORTCUTS = {
    "1": "text", "2": "engine", "3": "voice", "4": "speed",
    "5": "pitch", "6": "preview", "7": "save", "0": "quit",
}


def show_commands(voices: int) -> None:
    print("Type a command and press Enter.")
    if voices:
        print(f"  engine piper    Switch to Piper (voices 0–{voices - 1})")
        print(f"  voice {min(42, voices - 1):<10}Pick a Piper voice")
    else:
        print("  voice           Show eSpeak voices")
    print("  preview         Play through Listen (demo if text is blank)")
    print("  text Hello      Set the words to speak")
    print("  save            Save a WAV to Audacity imports")
    print("  help            Show all commands")


def piper_speakers() -> int:
    import json

    if not PIPER.is_file() or not MODEL.is_file():
        return 0
    try:
        config = json.loads(MODEL.with_suffix(".onnx.json").read_text())
        return int(config["num_speakers"])
    except (OSError, KeyError, TypeError, ValueError):
        return 0


def synthesize(text: str, engine: str, voice: str, speed: float, pitch: int, output: Path):
    if engine == "espeak":
        command = [
            str(ESPEAK), "--stdin", "-v", SYNTHETIC_VOICES[voice],
            "-s", str(round(175 * speed)), "-p", str(pitch), "-w", str(output),
        ]
    else:
        # Let the studio's audio capture run ahead of neural inference.
        command = [
            "/usr/bin/nice", "-n", "10", str(PIPER), "-m", "piper", "--model", str(MODEL),
            "--speaker", voice, "--length-scale", str(1 / speed),
            "--output-file", str(output),
        ]
    result = subprocess.run(
        command, input=text + "\n", text=True, capture_output=True,
        timeout=55, env={**os.environ, "OMP_NUM_THREADS": "1"},
    )
    if result.returncode:
        error = "".join(char for char in result.stderr.strip() if char.isprintable())
        raise ValueError(error[-250:] or "The speech engine did not render the sample.")
    with wave.open(str(output), "rb") as audio:
        if audio.getnframes() == 0:
            raise ValueError("The speech engine produced no audio.")


def save_audio(source: Path, engine: str, voice: str) -> Path:
    destination = IMPORTS / f"speech-{engine}-{voice}-{secrets.token_hex(4)}.wav"
    with tempfile.NamedTemporaryFile(prefix=".speech-", dir=IMPORTS) as temporary:
        with source.open("rb") as audio:
            shutil.copyfileobj(audio, temporary)
        temporary.flush()
        # Hard-link the completed file so a name collision cannot overwrite a take.
        os.link(temporary.name, destination)
    return destination


def main() -> None:
    voices = piper_speakers()
    engine, voice, speed, pitch = "espeak", "plain", 1.0, 50
    phrase = ""
    rendered = None
    show_commands(voices)
    with tempfile.TemporaryDirectory(prefix="temporaman-speech-") as directory:
        path = Path(directory) / "speech.wav"
        while True:
            try:
                line = input(f"\n{engine}/{voice}> ").strip()
                command, _, argument = line.partition(" ")
                command = command.lower()
                command = SHORTCUTS.get(command, command)
                argument = argument.strip()
                if command == "text":
                    phrase = (argument or input("Text: ").strip())[:1500]
                elif command == "engine":
                    engines = "espeak or piper" if voices else "espeak"
                    choice = (argument or input(f"Engine ({engines}): ")).strip().lower()
                    if choice not in {"espeak", "piper"}:
                        raise ValueError(f"Choose {engines}.")
                    if choice == "piper" and not voices:
                        raise ValueError("Piper's voice model is unavailable.")
                    engine, voice = choice, "0" if choice == "piper" else "plain"
                elif command == "voice":
                    if engine == "espeak":
                        if not argument:
                            print("Voices: " + ", ".join(SYNTHETIC_VOICES))
                        choice = (argument or input("Voice: ")).strip().lower()
                        if choice not in SYNTHETIC_VOICES:
                            raise ValueError("Choose a voice from the list.")
                        voice = choice
                    else:
                        choice = int(argument or input(f"Voice (0–{voices - 1}): "))
                        if not 0 <= choice < voices:
                            raise ValueError("Speaker number is outside the available range.")
                        voice = str(choice)
                elif command == "speed":
                    choice = float(argument or input("Speed multiplier (0.5–2.0): "))
                    if not 0.5 <= choice <= 2.0:
                        raise ValueError("Choose a speed from 0.5 to 2.0.")
                    speed = choice
                elif command == "pitch":
                    if engine != "espeak":
                        raise ValueError("Pitch control is available in eSpeak.")
                    choice = int(argument or input("Pitch (0–99): "))
                    if not 0 <= choice <= 99:
                        raise ValueError("Choose a pitch from 0 to 99.")
                    pitch = choice
                elif command in {"preview", "save"}:
                    if command == "save" and not phrase:
                        raise ValueError("Use text to enter a phrase first.")
                    settings = (phrase or DEMO_TEXT, engine, voice, speed, pitch)
                    if settings != rendered:
                        rendered = None
                        path.unlink(missing_ok=True)
                        if engine == "piper":
                            print("Rendering…", flush=True)
                        synthesize(*settings, path)
                        rendered = settings
                    if command == "preview":
                        # Leave headroom when the preview is mixed with other studio audio.
                        subprocess.run(
                            [str(PAPLAY), "--device=studio", "--stream-name=Speech Preview",
                             f"--volume={PREVIEW_VOLUME}", str(path)],
                            check=True, timeout=90,
                        )
                    else:
                        destination = save_audio(path, engine, voice)
                        print(f"Saved {destination.name} to imports.")
                elif command == "quit":
                    return
                elif command == "help":
                    show_commands(voices)
                    print("  engine espeak   Switch to eSpeak, then type voice for its voice list")
                    print("  speed 1.0       Set speed (0.5–2.0)")
                    print("  pitch 50        Set eSpeak pitch (0–99)")
                    print("  quit            Close Speech")
                elif command:
                    print("Unknown command. Type help.")
            except EOFError:
                return
            except KeyboardInterrupt:
                print()
            except (OSError, ValueError, wave.Error, subprocess.SubprocessError) as error:
                print(error)


if __name__ == "__main__":
    main()
