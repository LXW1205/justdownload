"""Persistent user settings + cookies auto-detection."""

import json
import os
import sys
from pathlib import Path


def settings_path() -> Path:
    # Windows: %APPDATA%/justdownload/settings.json
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "justdownload" / "settings.json"
    # Linux / macOS: ~/.config/justdownload/settings.json
    return Path.home() / ".config" / "justdownload" / "settings.json"


def default_download_dir() -> Path:
    return Path.home() / "Downloads" / "justdownload"


DEFAULT_SETTINGS = {
    "download_dir": str(default_download_dir()),
    "cookies_path": "",
}


def load() -> dict:
    p = settings_path()
    if not p.is_file():
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)
    merged = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        merged.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    return merged


def save(s: dict) -> None:
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s, indent=2), encoding="utf-8")


def detect_cookies() -> str | None:
    # First non-empty cookies.txt wins. XDG paths first so the lookup is
    # location-independent; CWD-relative is the last-resort fallback for
    # projects that keep cookies next to their working dir.
    config_base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    data_base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    candidates = [
        Path(config_base) / "justdownload" / "cookies.txt",
        Path(data_base) / "justdownload" / "cookies.txt",
        Path.home() / "justdownload" / "cookies.txt",
        Path.home() / "cookies.txt",
        Path.cwd() / "cookies.txt",
    ]
    for c in candidates:
        try:
            if c.is_file() and c.stat().st_size > 0:
                return str(c)
        except OSError:
            continue
    return None
