"""CLI entry point for justdownload. Pure stdlib. yt-dlp is the only runtime dep."""

import argparse
import os
import queue
import signal
import sys
from pathlib import Path

from justdownload.core import deps, settings, updater, ytdlp


BANNER = "justdownload · terminal YouTube downloader"


def _print_banner() -> None:
    print(BANNER)
    print()


def _format_size(n) -> str:
    if not n:
        return "?"
    try:
        size = float(n)
    except (TypeError, ValueError):
        return "?"
    for u in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or u == "TiB":
            return f"{size:.1f}{u}"
        size /= 1024
    return "?"


def _print_info(info: dict) -> None:
    print(f"  Title:    {info['title']}")
    print(f"  Channel:  {info['channel']}")
    print(f"  Duration: {info['duration_string']}  ·  uploaded {info['upload_date']}")
    print(f"  Formats:  {len(info['formats'])}")
    print()


# ponytail: YouTube serves video and audio as SEPARATE streams above 360p.
# The picker exposes preset format selectors (yt-dlp syntax) for merged output
# and the raw stream list for power users. Each preset maps to a yt-dlp format
# string that picks + merges the right streams. "bv" = best video, "ba" = best
# audio, "/" = fallback.
PRESETS = [
    ("★ Best (auto-merged, up to 4K)",  "bv*+ba/b"),
    ("1080p max (merged)",              "bv*[height<=1080]+ba/b"),
    ("720p max (merged)",               "bv*[height<=720]+ba/b"),
    ("Best audio only",                 "ba/b"),
    ("Best video only (no audio)",      "bv*"),
]


def _print_formats(formats: list[dict]) -> None:
    print("Presets:")
    for i, (label, _) in enumerate(PRESETS):
        print(f"  [{i}] {label}")
    print()
    print("Individual streams (single stream, no merging — audio-only has no sound):")
    n_presets = len(PRESETS)
    for i, f in enumerate(formats, start=n_presets):
        size = f"~ {_format_size(f.get('filesize'))}" if f.get("filesize") else ""
        print(f"  [{i}] {f['label']}  {size}")
    print()


def _pick_format(formats: list[dict], explicit: str | None) -> str:
    n_presets = len(PRESETS)
    total = n_presets + len(formats)
    if explicit:
        return explicit
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        # ponytail: non-interactive shell — skip the picker, use the first preset
        return PRESETS[0][1]
    while True:
        raw = input(f"  Pick [0-{total - 1}, default 0]: ").strip()
        if not raw:
            return PRESETS[0][1]
        try:
            idx = int(raw)
            if 0 <= idx < n_presets:
                return PRESETS[idx][1]
            if n_presets <= idx < total:
                return formats[idx - n_presets]["format_id"]
        except ValueError:
            pass
        print(f"  invalid, enter 0-{total - 1}")


def _format_friendly(fmt_id: str) -> str:
    for i, (label, selector) in enumerate(PRESETS):
        if selector == fmt_id:
            return f"[{i}] {label}"
    return fmt_id


def _render_bar(pct: float, width: int = 30) -> str:
    # ponytail: snap to 10% — user asked for stepped increments, and yt-dlp fires
    # 10+ events/sec which would just flicker the bar anyway.
    pct10 = max(0, min(100, round(pct / 10) * 10))
    filled = int(width * pct10 / 100)
    # ponytail: █ full block (U+2588), ░ light shade (U+2591). Renders well on
    # any UTF-8 terminal.
    bar = "█" * filled + "░" * (width - filled)
    return f"  [{bar}] {pct10:3d}%"


def _parse_speed_eta(line: str) -> tuple[str, str]:
    # ponytail: best-effort extraction from yt-dlp's "47.2% of 12.3MiB at 1.2MiB/s ETA 00:07" line.
    speed, eta = "", ""
    if " at " in line:
        speed = line.split(" at ", 1)[1].split(" ETA")[0].strip()
    if "ETA" in line:
        eta = "ETA " + line.split("ETA", 1)[1].strip()
    return speed, eta


# ponytail: friendly message overrides for common yt-dlp failures. Matched
# case-insensitively against the raw error line. Keyed on the most distinctive
# phrase so we don't false-positive on unrelated output.
_FRIENDLY_ERRORS = [
    (r"Sign in to confirm you'?re not a bot",
     "YouTube flagged this as a bot. Add a cookies.txt or try again later."),
    (r"HTTP Error 403|Forbidden",
     "Access denied. Check cookies.txt and the video's region/age restrictions."),
    (r"Unable to extract.*signature|Some formats may be missing",
     "JS runtime missing or outdated. Install node and update yt-dlp."),
    (r"No video formats found|Requested format is not available",
     "Format unavailable. Pick another from the list, or run with --format best."),
    (r"Unsupported URL",
     "This URL isn't supported by yt-dlp. Check the link."),
    (r"Video unavailable|Private video|This video is no longer available",
     "Video is private, deleted, or region-locked."),
    (r"Sign in to view this video|age-restricted",
     "Age-restricted. Add a cookies.txt to your account's session."),
]


def _friendly_error(line: str) -> str | None:
    import re
    for pattern, friendly in _FRIENDLY_ERRORS:
        if re.search(pattern, line, re.IGNORECASE):
            return friendly
    return None


def _drain_events(q: queue.Queue, handle) -> tuple[str, str | None]:
    # ponytail: SIGINT (Ctrl-C) cancels the yt-dlp subprocess; we restore the
    # previous handler when the download finishes. Returns (status, filename):
    # status in {"success", "cancelled", "error"}, filename only on success.
    cancelled = {"flag": False}

    def _cancel(_signum, _frame):
        cancelled["flag"] = True
        handle.cancel()
        print("\n! cancelled", file=sys.stderr)

    prev = signal.signal(signal.SIGINT, _cancel)
    last_pct10 = -1
    try:
        while True:
            ev = q.get()
            kind = ev[0]
            if kind == "progress":
                # ponytail: only redraw when the 10%-rounded bucket changes —
                # keeps the bar calm instead of jittery on every yt-dlp event.
                _, pct, line = ev
                pct10 = max(0, min(100, round(pct / 10) * 10))
                if pct10 == last_pct10:
                    continue
                last_pct10 = pct10
                speed, eta = _parse_speed_eta(line)
                parts = [_render_bar(pct), f"({pct:.1f}%)"]
                if speed:
                    parts.append(speed)
                if eta:
                    parts.append(eta)
                # \r = return to start of line, \033[2K = clear entire line so
                # leftover chars from a longer previous render don't bleed.
                sys.stdout.write("\r\033[2K" + "  •  ".join(parts) + "\n")
                sys.stdout.flush()
            else:
                # ponytail: any non-progress event ends the bar's line so the
                # next output starts on a fresh line.
                sys.stdout.write("\n")
                sys.stdout.flush()
                if kind in ("status", "stdout", "stderr"):
                    line = ev[1] if len(ev) > 1 else ""
                    print(line)
                elif kind == "error":
                    line = ev[1] if len(ev) > 1 else ""
                    friendly = _friendly_error(line)
                    print(f"ERROR: {friendly or line}", file=sys.stderr)
                elif kind == "done":
                    # (ok, filename)
                    if ev[1]:
                        return "success", ev[2]
                    return ("cancelled", None) if cancelled["flag"] else ("error", None)
    finally:
        signal.signal(signal.SIGINT, prev)


def _run_download(url: str, fmt_id: str, download_dir: str, cookies: str | None) -> tuple[str, str | None]:
    print()
    q: queue.Queue = queue.Queue()
    handle = ytdlp.start_download(url, fmt_id, download_dir, cookies, q)
    if handle is None:
        return "error", None
    return _drain_events(q, handle)


def _cmd_status() -> int:
    _print_banner()
    report = deps.check()
    ytdlp_line = f"yt-dlp:    {report.ytdlp_version or 'not installed'}"
    if report.yt_dlp_update:
        if report.yt_dlp_update.outdated:
            ytdlp_line += f"  (outdated, latest: {report.yt_dlp_update.latest})"
        elif report.yt_dlp_update.latest:
            ytdlp_line += f"  (latest: {report.yt_dlp_update.latest})"
    print(f"  {ytdlp_line}")
    ffmpeg_line = f"ffmpeg:    {report.ffmpeg_version or 'not installed'}"
    print(f"  {ffmpeg_line}")
    print(f"  js:       {report.js_runtime or 'not installed (YouTube may drop formats)'}")
    cfg = settings.load()
    print(f"  output:   {cfg.get('download_dir') or settings.default_download_dir()}")
    cookies = settings.detect_cookies()
    print(f"  cookies:  {cookies or 'none'}")
    return 0


def _cmd_update(yes: bool) -> int:
    _print_banner()
    report = deps.check()
    if not report.yt_dlp_update:
        print("  ! couldn't reach PyPI; check your network", file=sys.stderr)
        return 1
    if not report.yt_dlp_update.outdated and report.ytdlp_ok:
        print(f"  yt-dlp {report.ytdlp_version} is up to date")
        return 0
    print(f"  yt-dlp {report.yt_dlp_update.installed} → {report.yt_dlp_update.latest} available")
    if not yes:
        if not sys.stdin.isatty():
            print("  (non-interactive, use --yes to update)", file=sys.stderr)
            return 1
        if input("  Update now? [y/N] ").strip().lower() != "y":
            return 0
    print()
    q: queue.Queue = queue.Queue()
    updater.update_yt_dlp(q)
    while True:
        try:
            ev = q.get_nowait()
        except queue.Empty:
            break
        kind = ev[0]
        if kind in ("status", "stdout", "stderr"):
            print(ev[1] if len(ev) > 1 else "")
        elif kind == "error":
            print(f"ERROR: {ev[1]}", file=sys.stderr)
    print()
    new_report = deps.check()
    if new_report.ytdlp_version:
        print(f"  ✓ yt-dlp is now {new_report.ytdlp_version}")
    return 0


def _cmd_download(args) -> int:
    _print_banner()
    report = deps.check()
    if not report.ytdlp_ok:
        print("  ✗ yt-dlp not found on PATH.", file=sys.stderr)
        print("    Install with: pip install yt-dlp", file=sys.stderr)
        return 1
    if not report.ffmpeg_ok:
        print("  ⚠ ffmpeg not found — best-quality merges may fail.")
        print("    Install via your package manager, or build with PyInstaller to bundle it.")
    if not report.js_runtime:
        # ponytail: only warn, don't fail — downloads still work for some sites.
        # YouTube specifically needs this; the warning lives in the deps report.
        print("  ⚠ no JS runtime (node/deno) — YouTube may drop formats.")
        print("    Install: sudo apt install nodejs")

    cfg = settings.load()
    download_dir = args.output_dir or cfg.get("download_dir") or str(settings.default_download_dir())
    if args.output_dir:
        # ponytail: validate the path is writable BEFORE saving it as the new default.
        # Otherwise a typo'd --output-dir poisons ~/.config/justdownload/settings.json.
        try:
            os.makedirs(download_dir, exist_ok=True)
            probe = Path(download_dir) / ".justdownload_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as e:
            print(f"  ✗ output dir not writable: {download_dir}", file=sys.stderr)
            print(f"    {e}", file=sys.stderr)
            return 1
        cfg["download_dir"] = download_dir
        settings.save(cfg)
    else:
        os.makedirs(download_dir, exist_ok=True)

    cookies = settings.detect_cookies()
    if cookies:
        print(f"  cookies:  {cookies}")
    print(f"  output:   {download_dir}")
    print()
    print("[fetching info...]")
    try:
        info = ytdlp.fetch_info(args.url, cookies)
    except Exception as e:
        friendly = _friendly_error(str(e))
        print(f"  ✗ {friendly or e}", file=sys.stderr)
        return 1

    _print_info(info)
    _print_formats(info["formats"])
    fmt_id = _pick_format(info["formats"], args.format)
    if not args.format and not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(f"  (non-interactive, using preset: {_format_friendly(fmt_id)})")
    print(f"  → format {_format_friendly(fmt_id)}")
    print()

    status, output = _run_download(args.url, fmt_id, download_dir, cookies)
    if status == "success":
        print()
        print(f"  ✓ saved to: {output}")
        return 0
    if status == "cancelled":
        # SIGINT handler already printed "! cancelled" — don't print again.
        return 130  # ponytail: 128 + SIGINT(2), standard Unix convention
    print()
    print("  ✗ download failed", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="justdownload",
        description="Terminal YouTube downloader. yt-dlp + ffmpeg. No GUI.",
    )
    parser.add_argument("url", nargs="?", help="YouTube URL to download")
    parser.add_argument("-f", "--format", help="Format ID (skip the picker)")
    parser.add_argument("-o", "--output-dir", help="Output directory (saved as default)")
    parser.add_argument("--status", action="store_true", help="Show dependency + config status")
    parser.add_argument("--update", action="store_true", help="Update yt-dlp to the latest version")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompts")

    args = parser.parse_args(argv)

    if args.status:
        return _cmd_status()
    if args.update:
        return _cmd_update(yes=args.yes)
    if not args.url:
        parser.print_help()
        return 1
    return _cmd_download(args)


if __name__ == "__main__":
    sys.exit(main())
