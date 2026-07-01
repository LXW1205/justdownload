"""Spawn yt-dlp, format results, stream progress events into a queue."""

import hashlib
import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass

from justdownload.core.progress import parse_line


def _format_duration(seconds) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "--:--"
    if seconds <= 0:
        return "--:--"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_upload_date(raw) -> str:
    if not raw or len(str(raw)) != 8:
        return str(raw or "")
    s = str(raw)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _build_label(f: dict) -> tuple[str, str]:
    has_video = bool(f.get("vcodec")) and f["vcodec"] != "none"
    has_audio = bool(f.get("acodec")) and f["acodec"] != "none"
    if has_video and has_audio:
        kind = "Video+Audio"
    elif has_video:
        kind = "Video Only"
    else:
        kind = "Audio Only"
    ext = f.get("ext") or "?"
    res = f.get("resolution") or (f"{f['height']}p" if f.get("height") else "audio")
    note = f.get("format_note") or ""
    fps = f"{f['fps']}fps" if f.get("fps") else ""
    parts = [f"[{ext}]", res, f"({kind})"]
    if note:
        parts.append(f"- {note}")
    if fps:
        parts.append(f"- {fps}")
    return kind, " ".join(parts)


def fetch_info(url: str, cookies_path: str | None) -> dict:
    args = ["yt-dlp", "--dump-json", "--no-playlist", "--js-runtimes", "node"]
    if cookies_path:
        args += ["--cookies", cookies_path]
    args.append(url)

    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or f"yt-dlp exited with code {proc.returncode}"
        raise RuntimeError(msg)

    first_line = next((l for l in proc.stdout.splitlines() if l.strip().startswith("{")), None)
    if not first_line:
        raise RuntimeError("Empty response from yt-dlp")
    raw = json.loads(first_line)

    formats = []
    for f in raw.get("formats") or []:
        vcodec = f.get("vcodec") or "none"
        acodec = f.get("acodec") or "none"
        if vcodec == "none" and acodec == "none":
            continue
        kind, label = _build_label(f)
        formats.append({
            "format_id": str(f.get("format_id", "")),
            "ext": f.get("ext", "") or "",
            "resolution": f.get("resolution") or (f"{f['height']}p" if f.get("height") else "audio"),
            "fps": f.get("fps"),
            "vcodec": vcodec,
            "acodec": acodec,
            "filesize": f.get("filesize") or f.get("filesize_approx"),
            "note": f.get("format_note") or "",
            "kind": kind,
            "label": label,
        })

    return {
        "id": str(raw.get("id", "")),
        "title": str(raw.get("title") or "Untitled"),
        "channel": str(raw.get("channel") or raw.get("uploader") or "Unknown"),
        "duration": int(raw.get("duration") or 0),
        "duration_string": _format_duration(raw.get("duration") or 0),
        "upload_date": _format_upload_date(raw.get("upload_date")),
        "thumbnail": str(raw.get("thumbnail") or ""),
        "webpage_url": str(raw.get("webpage_url") or url),
        "formats": formats,
    }


@dataclass
class Download:
    proc: subprocess.Popen
    stem: str
    download_dir: str

    def cancel(self) -> None:
        try:
            self.proc.terminate()
        except (OSError, ProcessLookupError):
            pass


def _stem_for(url: str, fmt_id: str | None) -> str:
    # ponytail: deterministic stem — same URL + format = same prefix = yt-dlp
    # can resume any partial download. Timestamp+random would defeat resume.
    key = f"{url}|{fmt_id or 'best'}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _pump(proc: subprocess.Popen, q: queue.Queue, stem: str, download_dir: str) -> None:
    try:
        if proc.stdout is not None:
            for raw in proc.stdout:
                for line in raw.splitlines():
                    line = line.rstrip()
                    for ev in parse_line(line, source="stdout"):
                        q.put(ev)
        if proc.stderr is not None:
            for raw in proc.stderr:
                for line in raw.splitlines():
                    line = line.rstrip()
                    for ev in parse_line(line, source="stderr"):
                        q.put(ev)
    except OSError as e:
        # ponytail: only catch OS-level stream errors. Don't swallow
        # KeyboardInterrupt / SystemExit / CancelledError.
        q.put(("error", f"stream read failed: {e}"))

    code = proc.wait()

    if code == 0:
        try:
            entries = os.listdir(download_dir)
        except OSError as e:
            q.put(("error", f"could not list {download_dir}: {e}"))
            q.put(("done", False, None))
            return
        match = next((n for n in entries if n.startswith(stem + "__")), None)
        if match:
            q.put(("file", match))
            q.put(("done", True, match))
        else:
            q.put(("error", "Download finished but output file not found."))
            q.put(("done", False, None))
    else:
        q.put(("error", f"yt-dlp exited with code {code}"))
        q.put(("done", False, None))


def start_download(
    url: str,
    format_id: str | None,
    download_dir: str,
    cookies_path: str | None,
    q: queue.Queue,
) -> Download | None:
    args = [
        "yt-dlp",
        "--no-playlist",
        "--newline",
        "--progress",
        "--no-colors",
        "--restrict-filenames",
        "--js-runtimes", "node",
        # ponytail: YouTube now requires yt-dlp's EJS challenge solver. Without
        # this, downloads fail with "Some formats may be missing" or "No video
        # formats found". Downloads the solver script on first use, cached after.
        "--remote-components", "ejs:github",
    ]
    if format_id and format_id != "best":
        args += ["--format", format_id]
    if cookies_path:
        args += ["--cookies", cookies_path]

    download_dir = str(download_dir)
    os.makedirs(download_dir, exist_ok=True)
    stem = _stem_for(url, format_id)
    template = os.path.join(download_dir, f"{stem}__%(title).200B.%(ext)s")
    args += ["-o", template, url]

    # Pretty banner, mirroring the original Next.js route.
    pretty = " ".join(a if " " not in a and "\t" not in a else f'"{a}"' for a in args[1:])
    q.put(("status", f"$ yt-dlp {pretty}"))

    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        q.put(("error", "yt-dlp not found. Install with: pip install yt-dlp"))
        q.put(("done", False, None))
        return None

    handle = Download(proc=proc, stem=stem, download_dir=download_dir)
    threading.Thread(target=_pump, args=(proc, q, stem, download_dir), daemon=True).start()
    return handle
