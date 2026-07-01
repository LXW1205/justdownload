"""Parse a single yt-dlp output line into a queue event."""

import re
from typing import Literal

PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)%")

# Event tuple shapes (kept as plain tuples — no dataclass ceremony):
#   ("status",   str)
#   ("stdout",   str) | ("stderr", str)
#   ("progress", float, str)
#   ("file",     str)
#   ("error",    str)
#   ("done",     bool, str | None)


def parse_line(line: str, source: Literal["stdout", "stderr"] = "stdout") -> list[tuple]:
    if not line.strip():
        return []
    if "ERROR:" in line[:8]:
        return [("stderr", line)]
    m = PERCENT_RE.search(line)
    if m and "[download]" in line:
        pct = max(0.0, min(100.0, float(m.group(1))))
        return [("progress", pct, line)]
    return [(source, line)]
