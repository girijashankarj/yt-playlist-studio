"""Official YouTube Data API reader.

Slower to set up than the keyless reader and it costs quota, but it is stable,
supported, and the only way to read a private playlist.
"""

from __future__ import annotations

from ..models import Playlist, Song, seconds_to_duration
from ..quota import Quota


def _iso8601_to_seconds(s: str) -> int:
    import re

    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    h, mi, sec = (int(g or 0) for g in m.groups())
    return h * 3600 + mi * 60 + sec


def fetch(playlist_id: str, service, quota: Quota) -> Playlist:
    """`service` is a googleapiclient resource built by auth.build_service()."""
    quota.charge("playlists.list")
    meta = service.playlists().list(part="snippet,contentDetails", id=playlist_id).execute()
    items = meta.get("items") or []
    snip = (items[0].get("snippet") if items else {}) or {}
    pl = Playlist(
        playlist_id=playlist_id,
        title=snip.get("title", ""),
        owner=snip.get("channelTitle", ""),
        stated_count=(items[0]["contentDetails"]["itemCount"] if items else None),
    )

    page, ids = None, []
    while True:
        quota.charge("playlistItems.list")
        resp = (
            service.playlistItems()
            .list(part="snippet,contentDetails", playlistId=playlist_id, maxResults=50, pageToken=page)
            .execute()
        )
        for it in resp.get("items", []):
            sn, cd = it.get("snippet", {}), it.get("contentDetails", {})
            vid = cd.get("videoId") or sn.get("resourceId", {}).get("videoId")
            if not vid:
                continue
            ids.append(vid)
            pl.songs.append(
                Song(
                    position=len(pl.songs) + 1,
                    video_id=vid,
                    title=sn.get("title", ""),
                    channel=sn.get("videoOwnerChannelTitle", ""),
                    uploaded=(sn.get("publishedAt") or "")[:10],
                )
            )
        page = resp.get("nextPageToken")
        if not page:
            break

    # durations need a second, cheap pass (1 unit per 50 videos)
    by_id = {s.video_id: s for s in pl.songs}
    for i in range(0, len(ids), 50):
        quota.charge("videos.list")
        resp = (
            service.videos()
            .list(part="contentDetails,statistics", id=",".join(ids[i : i + 50]))
            .execute()
        )
        for v in resp.get("items", []):
            s = by_id.get(v["id"])
            if not s:
                continue
            s.duration_sec = _iso8601_to_seconds(v.get("contentDetails", {}).get("duration", ""))
            s.duration = seconds_to_duration(s.duration_sec)
            vc = v.get("statistics", {}).get("viewCount")
            s.views = int(vc) if vc and vc.isdigit() else None
    return pl
