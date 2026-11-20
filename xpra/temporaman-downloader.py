#!/usr/bin/env python3
import ctypes
import os
import queue
import signal
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import urlparse

APP_TITLE = "Temporaman Shrine Downloader"
IMPORTS = Path("/srv/audacity-studio/imports")
YTDLP = Path("/usr/local/bin/yt-dlp")
CHROME = Path("/usr/bin/google-chrome-stable")
CHROME_PROFILE = Path("/srv/audacity-studio/.config/temporaman-chrome")
ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}


def set_process_name() -> None:
    try:
        ctypes.CDLL(None).prctl(15, b"temporaman-dl", 0, 0, 0)
    except Exception:
        pass


class Downloader:
    def __init__(self) -> None:
        set_process_name()
        self.process: subprocess.Popen[str] | None = None
        self.youtube_signin_required = False
        self.events: queue.Queue[tuple[str, str | int]] = queue.Queue()

        self.root = tk.Tk(className="TemporamanDownloader")
        self.root.title(APP_TITLE)
        self.root.geometry("700x440")
        self.root.minsize(580, 360)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        frame = ttk.Frame(self.root, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="YouTube URL").grid(row=0, column=0, sticky="w")
        self.url = ttk.Entry(frame)
        self.url.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(3, 12))

        ttk.Label(frame, text="Audio format").grid(row=2, column=0, sticky="w")
        self.format = ttk.Combobox(frame, values=("MP3", "WAV", "FLAC"), state="readonly", width=12)
        self.format.set("MP3")
        self.format.grid(row=3, column=0, sticky="w", pady=(3, 12))

        self.download = ttk.Button(frame, text="Download audio", command=self.start)
        self.download.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=(3, 12))
        self.cancel = ttk.Button(frame, text="Cancel", command=self.stop, state="disabled")
        self.cancel.grid(row=3, column=2, sticky="w", padx=(8, 0), pady=(3, 12))
        self.sign_in = ttk.Button(frame, text="YouTube sign in", command=self.open_sign_in)
        self.sign_in.grid(row=3, column=3, sticky="w", padx=(8, 0), pady=(3, 12))

        self.status = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.status).grid(row=4, column=0, columnspan=4, sticky="w")

        self.log = tk.Text(frame, height=12, wrap="word", state="disabled", background="#f4f4f4")
        self.log.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=(6, 10))

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)
        self.url.focus_set()
        self.root.after(100, self.drain_events)

    def valid_url(self) -> str | None:
        value = self.url.get().strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
            messagebox.showerror(APP_TITLE, "Paste a valid YouTube or youtu.be URL.")
            return None
        return value

    def command(self, url: str) -> list[str]:
        audio_format = self.format.get().lower()
        quality = "0" if audio_format == "mp3" else "0"
        command = [
            str(YTDLP),
            "--no-playlist",
            "--no-live-from-start",
            "--max-filesize", "200M",
            "--match-filter", "!is_live & duration <= 7200",
            "--newline",
            "--no-colors",
            "--js-runtimes", "deno",
            "--extract-audio",
            "--audio-format", audio_format,
            "--audio-quality", quality,
            "--embed-metadata",
            "--output", str(IMPORTS / "%(title).180B [%(id)s].%(ext)s"),
        ]
        if any(CHROME_PROFILE.glob("**/Cookies")):
            command.extend(("--cookies-from-browser", f"chrome+basictext:{CHROME_PROFILE / 'Default'}"))
        command.append(url)
        return command

    def open_sign_in(self) -> None:
        if not CHROME.is_file():
            messagebox.showerror(APP_TITLE, "The sign-in browser is not installed.")
            return
        CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            [
                str(CHROME),
                f"--user-data-dir={CHROME_PROFILE}",
                "--profile-directory=Default",
                "--password-store=basic",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-mode",
                "--disable-extensions",
                "--disable-component-update",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--renderer-process-limit=2",
                "--window-size=1000,700",
                "https://www.youtube.com/",
            ],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.status.set("Make sure YouTube shows the throwaway account, then close Chrome before downloading")

    def start(self) -> None:
        if self.process is not None:
            return
        url = self.valid_url()
        if url is None:
            return
        if not YTDLP.is_file():
            messagebox.showerror(APP_TITLE, "yt-dlp is not installed.")
            return

        self.set_running(True)
        self.youtube_signin_required = False
        self.status.set("Starting download…")
        self.write_log("Starting audio download\n")
        threading.Thread(target=self.run_download, args=(url,), daemon=True).start()

    def run_download(self, url: str) -> None:
        try:
            self.process = subprocess.Popen(
                self.command(url),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.events.put(("line", line))
            code = self.process.wait()
            self.events.put(("done", code))
        except Exception as error:
            self.events.put(("line", f"Error: {error}\n"))
            self.events.put(("done", 1))

    def drain_events(self) -> None:
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "line":
                    line = str(value)
                    self.write_log(line)
                    if "Sign in to confirm you’re not a bot" in line or "Sign in to confirm you're not a bot" in line:
                        self.youtube_signin_required = True
                        self.status.set("YouTube requires sign-in from this server; no file was downloaded")
                    elif line.strip():
                        self.status.set(line.strip()[-100:])
                elif event == "done":
                    code = int(value)
                    self.process = None
                    self.set_running(False)
                    if code == 0:
                        self.status.set("Done — ready to import in Audacity")
                    elif self.youtube_signin_required:
                        self.status.set("YouTube requires sign-in from this server; no file was downloaded")
                    else:
                        self.status.set("Download failed — see details above")
        except queue.Empty:
            pass
        self.root.after(100, self.drain_events)

    def write_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_running(self, running: bool) -> None:
        self.download.configure(state="disabled" if running else "normal")
        self.cancel.configure(state="normal" if running else "disabled")
        self.sign_in.configure(state="disabled" if running else "normal")

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            self.status.set("Cancelling…")

    def close(self) -> None:
        self.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    Downloader().run()
