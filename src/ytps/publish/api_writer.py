"""Data API publish path: fully automated, quota-bound, resumable.

Costs 50 units per song. With the default 10,000/day allowance that is ~200 adds a
day, so this writer is built to stop cleanly at the cap and pick up tomorrow rather
than fail halfway through.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import QuotaExceeded
from ..models import Song
from ..quota import Quota, next_reset

# YouTube returns these for load shedding, not for anything the caller did wrong.
# 409 in particular is common on playlistItems.insert and simply needs retrying.
RETRYABLE = {409, 429, 500, 502, 503, 504}


def is_quota_error(e: Exception) -> bool:
    """Google's 403 quotaExceeded is authoritative - our local ledger is only an estimate.

    A sibling app sharing the Cloud project, or retries we did not count, can burn the
    real allowance while the ledger still looks healthy.
    """
    if getattr(getattr(e, "resp", None), "status", None) != 403:
        return False
    blob = str(getattr(e, "content", "")) + str(e)
    return "quotaExceeded" in blob or "exceeded your" in blob


def execute(request, attempts: int = 6, sleep=time.sleep):
    """Run an API request, retrying transient failures with exponential backoff.

    Without this a single 409 - which YouTube hands out freely during bulk inserts -
    aborts a multi-hundred-song publish.
    """
    last = None
    for attempt in range(attempts):
        try:
            return request.execute()
        except Exception as e:  # googleapiclient.errors.HttpError, kept loose for testability
            status = getattr(getattr(e, "resp", None), "status", None)
            if status == 403 and is_quota_error(e):
                raise QuotaExceeded(0, 0, next_reset()) from e
            if status not in RETRYABLE:
                raise
            last = e
            if attempt == attempts - 1:
                break
            sleep(min(2**attempt, 16) + random.uniform(0, 0.75))
    raise last  # type: ignore[misc]


@dataclass
class PublishState:
    """Resume file - which ids already made it in."""

    path: Path
    playlist_name: str = ""
    playlist_id: str = ""
    added: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path, name: str) -> PublishState:
        try:
            d = json.loads(path.read_text())
            return cls(path, d.get("playlist_name", name), d.get("playlist_id", ""), d.get("added", []))
        except (FileNotFoundError, json.JSONDecodeError):
            return cls(path, name)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "playlist_name": self.playlist_name,
                    "playlist_id": self.playlist_id,
                    "added": self.added,
                },
                indent=1,
            )
        )


def estimate(songs: list[Song], create_new: bool = True) -> dict:
    q = {"playlistItems.insert": len(songs)}
    if create_new:
        q["playlists.insert"] = 1
    units = sum(Quota.cost(m, n) for m, n in q.items())
    return {
        "songs": len(songs),
        "units": units,
        "days_at_default_quota": round(units / 10_000, 1),
        "breakdown": q,
    }


def publish(
    name: str,
    description: str,
    songs: list[Song],
    service,
    quota: Quota,
    state_dir: Path,
    privacy: str = "private",
    dry_run: bool = True,
) -> dict:
    """Create (or resume) a playlist and add songs until done or out of quota.

    Defaults to dry_run and privacy='private' - both deliberately the safe choice.
    """
    est = estimate(songs, create_new=True)
    if dry_run:
        return {
            "dry_run": True,
            "playlist": name,
            "privacy": privacy,
            **est,
            "quota": quota.status(),
            "note": "No network calls were made. Re-run with dry_run=False to publish.",
        }

    if privacy not in {"private", "unlisted", "public"}:
        raise ValueError("privacy must be private, unlisted or public")

    state = PublishState.load(state_dir / f"{name}.json", name)
    already = set(state.added)

    if not state.playlist_id:
        quota.charge("playlists.insert")
        resp = execute(
            service.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {"title": name, "description": description},
                    "status": {"privacyStatus": privacy},
                },
            )
        )
        state.playlist_id = resp["id"]
        state.save()
    else:
        # resuming: one cheap call tells us what is already in there
        page = None
        while True:
            quota.charge("playlistItems.list")
            r = execute(
                service.playlistItems().list(
                    part="contentDetails", playlistId=state.playlist_id,
                    maxResults=50, pageToken=page,
                )
            )
            already |= {i["contentDetails"]["videoId"] for i in r.get("items", [])}
            page = r.get("nextPageToken")
            if not page:
                break

    added, skipped, stopped = 0, 0, None
    try:
        for s in songs:
            if s.video_id in already:
                skipped += 1
                continue
            try:
                quota.charge("playlistItems.insert")
            except QuotaExceeded as e:
                stopped = str(e)
                break
            try:
                execute(
                    service.playlistItems().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "playlistId": state.playlist_id,
                                "resourceId": {"kind": "youtube#video", "videoId": s.video_id},
                            }
                        },
                    )
                )
            except QuotaExceeded:
                # Google says we are done for today even if our ledger disagrees.
                quota.exhaust()
                stopped = (
                    "Google reported the daily quota as exhausted. The local ledger is an "
                    f"estimate and was behind. Resume after {next_reset()}."
                )
                break
            state.added.append(s.video_id)
            already.add(s.video_id)
            added += 1
            if added % 10 == 0:
                state.save()
    finally:
        # never lose progress: an exception here still costs quota, and re-adding
        # songs we already paid for would waste another day of allowance
        state.save()
    remaining = len(songs) - len(already & {s.video_id for s in songs})
    return {
        "dry_run": False,
        "playlist": name,
        "playlist_id": state.playlist_id,
        "url": f"https://www.youtube.com/playlist?list={state.playlist_id}",
        "privacy": privacy,
        "added": added,
        "skipped_already_present": skipped,
        "remaining": remaining,
        "complete": remaining == 0,
        "stopped_because": stopped,
        "quota": quota.status(),
        "resume_with": None if remaining == 0 else f"ytps publish api --name {name!r} --resume",
    }
