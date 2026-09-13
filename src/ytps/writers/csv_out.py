"""CSV + M3U export. The plain formats other tools can actually read."""

from __future__ import annotations

import csv
from pathlib import Path

from ..models import Song

COLUMNS = [
    "position", "song_name", "title", "artist", "album", "language", "genre",
    "sub_genre", "category", "duration", "duration_sec", "views", "channel",
    "channel_url", "uploaded", "video_id", "url",
]


def write_csv(songs: list[Song], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for s in songs:
            w.writerow(s.as_dict())
    return path


def write_m3u(songs: list[Song], path: str | Path, name: str = "") -> Path:
    """Extended M3U - opens in VLC and most players."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#EXTM3U"]
    if name:
        lines.append(f"#PLAYLIST:{name}")
    for s in songs:
        who = s.artist or s.channel
        lines.append(f"#EXTINF:{s.duration_sec},{who} - {s.song_name}".rstrip())
        lines.append(s.url)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
