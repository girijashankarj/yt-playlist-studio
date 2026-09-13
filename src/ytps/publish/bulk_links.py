"""Browser publish path: free, instant, no OAuth, no quota.

YouTube's watch_videos endpoint builds a temporary playlist from up to 50 video ids.
The user saves it to their account in two clicks. This is the only path that can
create a 3,000-song library in an afternoon - the Data API would need ~17 days.
"""

from __future__ import annotations

from ..models import Song

MAX_IDS = 50
BASE = "https://www.youtube.com/watch_videos?video_ids="


def chunk_ids(ids: list[str], size: int = MAX_IDS) -> list[list[str]]:
    if size > MAX_IDS:
        raise ValueError(f"YouTube accepts at most {MAX_IDS} ids per link")
    return [ids[i : i + size] for i in range(0, len(ids), size)]


def build_links(songs: list[Song], size: int = MAX_IDS) -> list[dict]:
    """One dict per block: the url, how many videos, and which positions it covers."""
    ids = [s.video_id for s in songs]
    out = []
    for i, block in enumerate(chunk_ids(ids, size)):
        lo = i * size + 1
        out.append(
            {
                "index": i + 1,
                "url": BASE + ",".join(block),
                "count": len(block),
                "positions": f"{lo}-{lo + len(block) - 1}",
                "action": "Save as new playlist" if i == 0 else "Add all to existing playlist",
            }
        )
    return out


STEPS = [
    "Sign in to the YouTube account that should own the playlist.",
    "Open link 1. YouTube builds a temporary queue from those videos.",
    "Click the queue title, then Save playlist to keep it on your account.",
    "Rename it to the playlist name shown above.",
    "For links 2 and up, use 'Add all to playlist' and pick that same playlist.",
]
