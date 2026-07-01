# -*- mode: python ; coding: utf-8 -*-
#
# Build a onefile, windowed binary for justdownload.
#
# At spec-eval time we import imageio_ffmpeg and copy the ffmpeg binary
# that ships in its wheel into dist/justdownload/ next to the resulting
# exe. This is the only step that needs network access (pip downloads
# the wheel on first build).
#
# Resulting dist layout (after `pyinstaller build.spec`):
#   dist/
#     justdownload(.exe)         single-file binary
#     ffmpeg(.exe)               bundled ffmpeg, picked up by core/deps.py
#
# Run with:  pyinstaller build.spec

import shutil
import sys
from pathlib import Path

import imageio_ffmpeg

# --- Bundle ffmpeg next to the binary ----------------------------------------
FFMPEG_NAME = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
DIST_DIR = Path("dist") / "justdownload"
DIST_DIR.mkdir(parents=True, exist_ok=True)
try:
    src = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if src.is_file():
        shutil.copy2(src, DIST_DIR / FFMPEG_NAME)
except Exception as e:
    print(f"warning: could not bundle ffmpeg: {e}", file=sys.stderr)

# --- PyInstaller build --------------------------------------------------------
a = Analysis(['src/justdownload/__main__.py'])
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='justdownload',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
)
