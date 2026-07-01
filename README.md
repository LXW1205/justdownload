# justdownload

A terminal YouTube downloader. `yt-dlp` + `ffmpeg`, no GUI, no Electron, no Docker. One Python package, one runtime dependency.

## Install

```bash
pip install -e .
```

Prereqs:
- **Python 3.10+**
- **`yt-dlp`** on PATH (`pip install yt-dlp`)
- **`ffmpeg`** on PATH for high-quality merges (`apt install ffmpeg` / `brew install ffmpeg`)
- **A JS runtime** for YouTube — `node` is fine (`apt install nodejs`)

If anything is missing, `justdownload --status` will tell you.

## Quick start

```bash
justdownload "https://www.youtube.com/watch?v=..."
```

That fetches the video metadata, shows a format picker, downloads, prints the output path.

Skip the picker for scripting:

```bash
justdownload "https://..." -f "bv*+ba/b"          # best (auto-merged, up to 4K)
justdownload "https://..." -f "bv*[height<=1080]+ba/b"   # capped at 1080p
justdownload "https://..." -f "ba/b"              # audio only
justdownload "https://..." -f 22                  # raw format id
```

## What the picker looks like

YouTube only serves up to 360p as a single combined video+audio stream. For higher quality, yt-dlp merges a video-only stream with an audio-only stream. The picker exposes both options:

```
Presets:
  [0] ★ Best (auto-merged, up to 4K)
  [1] 1080p max (merged)
  [2] 720p max (merged)
  [3] Best audio only
  [4] Best video only (no audio)

Individual streams (single stream, no merging — audio-only has no sound):
  [5] [m4a] audio only (Audio Only) - low  ~ 3.0MiB
  [6] [mp4] 1920x1080 (Video Only) - 1080p - 25fps  ~ 77.2MiB
  ...
```

Pick `[0]` for the default. The CLI runs `bv*+ba/b` under the hood, which lets yt-dlp pick the best video stream, the best audio stream, and merge them with ffmpeg. Single .mp4 (or .webm/.mkv) output, full quality.

For non-interactive shells (CI, scripts, pipes), the picker auto-picks `[0]` and the format passed via `-f` skips the menu.

## Progress bar

Downloads show a 10%-stepped progress bar that updates in place:

```
  [███████████░░░░░░░░░░░░░░░░░░░░]  40%  •  (38.7%)  •  1.2MiB/s  •  ETA 00:35
  [█████████████████░░░░░░░░░░░░░]  50%  •  (49.2%)  •  1.4MiB/s  •  ETA 00:28
  [███████████████████████████░░░]  90%  •  (88.1%)  •  1.3MiB/s  •  ETA 00:06
  [██████████████████████████████] 100%  •  (99.8%)  •  1.2MiB/s  •  ETA 00:00
```

The rounded percent is the bar, the `(38.7%)` is the raw percent from yt-dlp. Bar redraws only on 10% boundaries, so it stays calm.

## Commands

| Command | What it does |
|---|---|
| `justdownload URL` | Fetch info, pick a format, download |
| `justdownload URL -f FMT` | Download with a specific format, no picker |
| `justdownload URL -o DIR` | Download to a specific directory (saved as default) |
| `justdownload --status` | Show yt-dlp / ffmpeg / JS runtime versions + config |
| `justdownload --update` | Check + offer to update yt-dlp |
| `justdownload --update -y` | Update yt-dlp without prompting |
| `justdownload --help` | Show all options |

## Examples

```bash
# Interactive (TTY)
justdownload "https://..."

# Non-interactive — best quality, default
justdownload "https://..." -f "bv*+ba/b"

# 1080p max, save to a custom dir
justdownload "https://..." -f "bv*[height<=1080]+ba/b" -o ~/Videos

# Audio only (music)
justdownload "https://..." -f "ba/b" -o ~/Music

# Resume a partial download — re-run the same command.
# The CLI uses a URL+format hash as the output prefix, so yt-dlp
# picks up any existing .part file automatically.
justdownload "https://..." -f 22
# Already-downloaded files are detected and skipped.
```

## Cookies (optional)

For age-restricted, members-only, or private videos, drop a Netscape-format `cookies.txt` anywhere the CLI looks. Export from your browser with the "Get cookies.txt LOCALLY" extension.

Lookup order (first non-empty file wins):

```
1. $XDG_CONFIG_HOME/justdownload/cookies.txt   # canonical
2. $XDG_DATA_HOME/justdownload/cookies.txt
3. ~/justdownload/cookies.txt
4. ~/cookies.txt
5. ./cookies.txt                               # CWD fallback
```

The recommended location is `~/.config/justdownload/cookies.txt`. The CLI will tell you which file it found in the `cookies:` line at the top of the output.

## Why you need a JS runtime

YouTube now requires a JavaScript runtime (node, deno, bun, or qjs) to solve their signature challenges. Without it, downloads fail or silently lose most formats. The CLI warns on startup if no runtime is found. Install one with `apt install nodejs` (Linux) or `brew install node` (macOS).

The CLI also passes `--remote-components ejs:github` to yt-dlp, which downloads yt-dlp's challenge solver script on first use. It's cached after that.

## Output & settings

Default output: `~/Downloads/justdownload/`. Override with `-o PATH`. The first `-o` value gets saved as the new default.

Config persists at:
- Linux/macOS: `~/.config/justdownload/settings.json`
- Windows: `%APPDATA%\justdownload\settings.json`

The file currently stores one thing: the default output directory.

## Updating yt-dlp

YouTube breaks things often. `yt-dlp` ships fixes daily.

```bash
justdownload --update        # check + prompt
justdownload --update -y     # update without prompting
```

Or pin a version: `pip install yt-dlp==2024.12.13`.

## Tests

127 unit tests, ~0.1s runtime, stdlib only (no pytest needed):

```bash
python -m unittest discover -s tests
```

The suite covers:
- `core/progress.py` — every yt-dlp line variant
- `core/settings.py` — XDG paths, corrupt files, cookies detection
- `core/deps.py` — runtime detection, version fetch
- `core/updater.py` — version parsing, network failure handling
- `core/ytdlp.py` — deterministic stem (for resume), format parsing, subprocess mocks
- `cli.py` — bar rendering, error mapping, preset invariants, arg routing, drain flow

Subprocess and network calls are mocked, so tests don't need yt-dlp installed or internet access.

## Build a single binary

```bash
pip install pyinstaller imageio-ffmpeg
pyinstaller build.spec
# → dist/justdownload(.exe)  (~30-40 MB, ffmpeg bundled next to it)
```

Double-click the result. yt-dlp and ffmpeg are bundled.

## Project layout

```
justdownload/
├── pyproject.toml          # hatchling, deps: [yt-dlp]
├── build.spec              # PyInstaller onefile
├── README.md
├── src/justdownload/
│   ├── __main__.py
│   ├── cli.py              # argparse + main loop
│   └── core/
│       ├── ytdlp.py        # subprocess wrapper, format parsing
│       ├── progress.py     # yt-dlp line parser
│       ├── settings.py     # XDG-aware config + cookies
│       ├── deps.py         # runtime detection
│       └── updater.py      # PyPI version check + pip install -U
└── tests/                  # 127 tests, stdlib only
    ├── test_progress.py
    ├── test_settings.py
    ├── test_deps.py
    ├── test_updater.py
    ├── test_ytdlp.py
    └── test_cli.py
```

## Stack

- **Python 3.10+** · stdlib only (argparse, subprocess, queue, signal, urllib, json)
- **yt-dlp** — the only runtime dependency
- **ffmpeg** — system-level, for merging video + audio streams
- **node / deno / bun** — system-level, for YouTube's JS challenges
