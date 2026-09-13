"""Daily dispatcher.

The API allows roughly 200 song-adds a day, so publishing a large library is a
multi-day job. This walks a directory of playlist CSVs, publishes as much as today's
quota allows, and stops cleanly. Run it again tomorrow and it picks up exactly where
it left off - including part-way through a playlist.

Safe to run unattended: it never re-adds a song that is already in a playlist.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..errors import QuotaExceeded
from ..quota import Quota, next_reset
from .api_writer import estimate, publish


@dataclass
class Entry:
    name: str
    source: str
    total: int
    added: int = 0
    status: str = "pending"       # pending | partial | done
    playlist_id: str = ""
    url: str = ""
    finished_at: str = ""

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.added)


@dataclass
class QueueState:
    path: Path
    entries: dict[str, Entry] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> QueueState:
        try:
            raw = json.loads(path.read_text())
            return cls(path, {k: Entry(**v) for k, v in raw.get("entries", {}).items()})
        except (FileNotFoundError, json.JSONDecodeError):
            return cls(path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "entries": {k: asdict(v) for k, v in self.entries.items()},
                },
                indent=1,
            )
        )

    def summary(self) -> dict:
        e = list(self.entries.values())
        return {
            "playlists_total": len(e),
            "playlists_done": sum(1 for x in e if x.status == "done"),
            "playlists_partial": sum(1 for x in e if x.status == "partial"),
            "songs_total": sum(x.total for x in e),
            "songs_added": sum(x.added for x in e),
            "songs_remaining": sum(x.remaining for x in e),
        }


def _count(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def discover(directory: Path, state: QueueState, state_dir: Path | None = None) -> None:
    """Add any CSV not already tracked, then reconcile against per-playlist state.

    A crash can create a playlist on YouTube before the queue records it, leaving the
    queue claiming "not created yet" for something that exists. The per-playlist files
    written by the publisher are the more reliable record, so adopt them - it costs no
    quota, unlike asking YouTube.
    """
    for p in sorted(directory.glob("*.csv")):
        if p.stem not in state.entries:
            state.entries[p.stem] = Entry(name=p.stem, source=str(p), total=_count(p))

    if state_dir is None:
        return
    for entry in state.entries.values():
        if entry.status == "done":
            continue                      # never downgrade a finished playlist
        f = state_dir / "state" / f"{entry.name}.json"
        try:
            data = json.loads(f.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        pid = data.get("playlist_id")
        if not pid:
            continue
        entry.playlist_id = pid
        entry.url = f"https://www.youtube.com/playlist?list={pid}"
        entry.added = max(entry.added, len(data.get("added", [])))
        entry.status = "done" if entry.added >= entry.total else "partial"


def run_queue(
    directory: Path,
    service,
    quota: Quota,
    state_dir: Path,
    privacy: str = "private",
    order: str = "smallest",
    description: str = "Created with yt-playlist-studio",
    load_songs=None,
) -> dict:
    """Publish as much of the directory as today's quota allows.

    order='smallest' finishes the most playlists per day; 'largest' chips away at the
    big ones first; 'name' is alphabetical.
    """
    state = QueueState.load(state_dir / "queue.json")
    discover(directory, state, state_dir)
    state.save()

    pending = [e for e in state.entries.values() if e.status != "done"]
    key = {
        "smallest": lambda e: e.remaining,
        "largest": lambda e: -e.remaining,
        "name": lambda e: e.name,
    }[order]
    pending.sort(key=key)

    log, stopped = [], None
    for entry in pending:
        need = estimate(
            [None] * entry.remaining, create_new=not entry.playlist_id  # type: ignore[list-item]
        )["units"]
        if quota.remaining() < 100:            # not even one add plus overhead
            stopped = "daily quota exhausted"
            break

        songs = load_songs(Path(entry.source))
        try:
            result = publish(
                entry.name, description, songs, service, quota,
                state_dir / "state", privacy=privacy, dry_run=False,
            )
        except QuotaExceeded as e:
            # the playlist may exist with some songs already in it; keep what we know
            entry.status = "partial" if entry.playlist_id else "pending"
            state.save()
            stopped = str(e)
            break

        entry.playlist_id = result["playlist_id"]
        entry.url = result["url"]
        entry.added = entry.total - result["remaining"]
        entry.status = "done" if result["complete"] else "partial"
        if result["complete"]:
            entry.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        state.save()
        log.append(
            {"playlist": entry.name, "added": result["added"],
             "skipped": result["skipped_already_present"], "status": entry.status,
             "url": entry.url, "needed_units": need}
        )
        if not result["complete"]:
            stopped = result["stopped_because"] or "daily quota exhausted"
            break

    s = state.summary()
    return {
        "ran": log,
        "stopped_because": stopped,
        "quota": quota.status(),
        "resume_after": next_reset() if s["songs_remaining"] else None,
        **s,
        "all_done": s["songs_remaining"] == 0,
    }
