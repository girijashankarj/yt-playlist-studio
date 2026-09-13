"""Core data shapes. Deliberately plain so they serialise to CSV/JSON/XLSX cleanly."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

_DUR = re.compile(r"^(?:(\d+):)?(\d+):(\d{2})$")


def duration_to_seconds(text: str) -> int:
    """'3:45' or '1:02:03' -> seconds. Raises ValueError on anything else."""
    m = _DUR.match((text or "").strip())
    if not m:
        raise ValueError(f"unrecognised duration: {text!r}")
    h, mi, s = m.group(1), m.group(2), m.group(3)
    return int(h or 0) * 3600 + int(mi) * 60 + int(s)


def seconds_to_duration(total: int) -> str:
    h, rem = divmod(int(total), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_views(text: str | None) -> int | None:
    """'242m views' -> 242000000. Approximate by nature; None when unparseable."""
    if not text:
        return None
    m = re.match(r"^([\d.]+)\s*([kmb]?)\s*views?$", text.strip(), re.I)
    if not m:
        return None
    mult = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[m.group(2).lower()]
    return int(float(m.group(1)) * mult)


@dataclass
class Song:
    position: int
    video_id: str
    title: str
    channel: str = ""
    channel_url: str = ""
    duration: str = "0:00"
    duration_sec: int = 0
    views: int | None = None
    uploaded: str = ""
    # derived tags - never official YouTube metadata
    song_name: str = ""
    artist: str = ""
    album: str = ""
    language: str = ""
    genre: str = ""
    sub_genre: str = ""
    category: str = ""

    def __post_init__(self) -> None:
        if not self.duration_sec and self.duration:
            try:
                self.duration_sec = duration_to_seconds(self.duration)
            except ValueError:
                self.duration_sec = 0
        if not self.song_name:
            self.song_name = self.title

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["url"] = self.url
        return d


@dataclass
class Playlist:
    playlist_id: str
    title: str = ""
    owner: str = ""
    songs: list[Song] = field(default_factory=list)
    stated_count: int | None = None

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/playlist?list={self.playlist_id}"

    @property
    def runtime_sec(self) -> int:
        return sum(s.duration_sec for s in self.songs)

    @property
    def hidden_count(self) -> int:
        """Videos YouTube counts but will not show (deleted/private)."""
        if self.stated_count is None:
            return 0
        return max(0, self.stated_count - len(self.songs))

    def __len__(self) -> int:
        return len(self.songs)
