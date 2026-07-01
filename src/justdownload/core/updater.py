"""Check whether yt-dlp and ffmpeg are up to date; offer to update yt-dlp."""

import json
import queue
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class UpdateInfo:
    installed: str | None  # e.g. "2024.10.7", None if yt-dlp missing
    latest: str | None     # e.g. "2024.12.13", None if PyPI unreachable
    outdated: bool         # True iff installed and latest both known and installed < latest


def _parse_version(s: str) -> tuple[int, ...] | None:
    parts: list[int] = []
    for piece in (s or "").split("."):
        m = re.match(r"^\d+", piece)
        if not m:
            break
        parts.append(int(m.group(0)))
    return tuple(parts) if parts else None


def is_outdated(installed: str, latest: str) -> bool:
    a, b = _parse_version(installed), _parse_version(latest)
    if not a or not b:
        return False
    return a < b


def get_yt_dlp_version() -> str | None:
    try:
        r = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout.strip().splitlines()[0] or None


def get_ffmpeg_version() -> str | None:
    try:
        r = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    # First line: "ffmpeg version 6.1.1 Copyright ..."
    first = r.stdout.splitlines()[0] if r.stdout else ""
    m = re.search(r"ffmpeg version (\S+)", first)
    return m.group(1) if m else None


def check_yt_dlp_update(timeout: float = 5.0) -> UpdateInfo:
    installed = get_yt_dlp_version()
    latest: str | None = None
    try:
        req = urllib.request.Request(
            "https://pypi.org/pypi/yt-dlp/json",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        latest = (payload.get("info") or {}).get("version")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        # ponytail: silent on network failure, user can manually update from the Help menu
        latest = None

    outdated = bool(
        installed and latest and is_outdated(installed, latest)
    )
    return UpdateInfo(installed=installed, latest=latest, outdated=outdated)


# ponytail: python -m pip works in venvs and PyInstaller onefile; bare pip wouldn't
def update_yt_dlp(q: queue.Queue) -> None:
    q.put(("status", "$ python -m pip install -U yt-dlp"))
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        q.put(("error", "pip not found: could not launch sys.executable -m pip"))
        return

    def _pump(stream, kind: str) -> None:
        if stream is None:
            return
        for raw in stream:
            for line in raw.splitlines():
                line = line.rstrip()
                if line:
                    q.put((kind, line))

    # Stream in parallel-ish: drain stderr to completion while stdout runs.
    # Simpler: read both sequentially after process finishes, but we want live
    # progress. Use threads.
    import threading
    out_t = threading.Thread(target=_pump, args=(proc.stdout, "stdout"), daemon=True)
    err_t = threading.Thread(target=_pump, args=(proc.stderr, "stderr"), daemon=True)
    out_t.start()
    err_t.start()
    code = proc.wait()
    out_t.join(timeout=2)
    err_t.join(timeout=2)

    if code == 0:
        new_version = get_yt_dlp_version()
        if new_version:
            q.put(("status", f"yt-dlp updated to {new_version}"))
    else:
        q.put(("error", f"pip exited with code {code}"))
