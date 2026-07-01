"""Check whether yt-dlp and ffmpeg are usable, and whether yt-dlp is outdated."""

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from justdownload.core.updater import (
    UpdateInfo,
    check_yt_dlp_update,
    get_ffmpeg_version,
)


# ponytail: YouTube now requires a JS runtime for signature solving. Order = preference.
# node is the most common, deno is recommended by yt-dlp, bun/qjs are fallbacks.
_JS_RUNTIMES = ("node", "deno", "bun", "qjs")


def get_js_runtime() -> str | None:
    for r in _JS_RUNTIMES:
        if shutil.which(r):
            return r
    return None


@dataclass
class DepsReport:
    ytdlp_ok: bool
    ytdlp_path: str | None
    ffmpeg_ok: bool
    ffmpeg_path: str | None
    ytdlp_version: str | None
    ffmpeg_version: str | None
    js_runtime: str | None
    yt_dlp_update: UpdateInfo | None = None
    messages: list[str] = field(default_factory=list)


def _bundled_ffmpeg() -> str | None:
    # PyInstaller onefile drops ffmpeg(.exe) next to the running binary.
    name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    cand = Path(sys.executable).parent / name
    return str(cand) if cand.is_file() else None


def check() -> DepsReport:
    ytdlp_path = shutil.which("yt-dlp")
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        bundled = _bundled_ffmpeg()
        if bundled:
            ffmpeg_path = bundled

    ytdlp_version: str | None = None
    if ytdlp_path:
        try:
            r = subprocess.run(
                [ytdlp_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode == 0 and r.stdout:
                ytdlp_version = r.stdout.strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError):
            pass

    ffmpeg_version = get_ffmpeg_version() if ffmpeg_path else None
    js_runtime = get_js_runtime()
    yt_dlp_update = check_yt_dlp_update()

    messages: list[str] = []
    if not ytdlp_path:
        messages.append("yt-dlp not found on PATH. Install with: pip install yt-dlp")
    elif yt_dlp_update.outdated:
        messages.append(
            f"yt-dlp outdated: {yt_dlp_update.installed} → {yt_dlp_update.latest}"
        )
    if not ffmpeg_path:
        messages.append(
            "ffmpeg not found. Install via your package manager, "
            "or build with PyInstaller to bundle it."
        )
    if not js_runtime:
        # ponytail: only fatal-looking warning if yt-dlp itself is present.
        # Without a JS runtime, YouTube drops video formats silently.
        messages.append(
            "no JS runtime found (node/deno/bun). YouTube downloads may lose formats — "
            "install node: sudo apt install nodejs"
        )

    return DepsReport(
        ytdlp_ok=bool(ytdlp_path),
        ytdlp_path=ytdlp_path,
        ffmpeg_ok=bool(ffmpeg_path),
        ffmpeg_path=ffmpeg_path,
        ytdlp_version=ytdlp_version,
        ffmpeg_version=ffmpeg_version,
        js_runtime=js_runtime,
        yt_dlp_update=yt_dlp_update,
        messages=messages,
    )
