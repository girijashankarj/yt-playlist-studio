"""Keyless reader.

Reads a public or unlisted playlist straight from YouTube's own web endpoint, the
way a browser does. No API key, no OAuth, no quota - which is why it is the default
read path. It cannot see private playlists and cannot write anything.

Note: this rides an internal endpoint, so it can break if YouTube changes its
response shape. When it does, `ytps fetch --via api` is the stable fallback.
"""

from __future__ import annotations

import json
import re
import urllib.request

from ..errors import PlaylistNotFound
from ..models import Playlist, Song, parse_views

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
BROWSE = "https://www.youtube.com/youtubei/v1/browse"


def extract_playlist_id(url_or_id: str) -> str:
    """Accepts a full URL, a `list=` param, or a bare id."""
    s = url_or_id.strip()
    m = re.search(r"[?&]list=([A-Za-z0-9_-]+)", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{2,}", s):
        return s
    raise ValueError(f"could not find a playlist id in {url_or_id!r}")


def _get(url: str, data: dict | None = None) -> str:
    headers = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed https host
        return r.read().decode("utf-8", "replace")


def find_key(obj, key: str, out: list | None = None, depth: int = 0) -> list:
    """Depth-first search for every value stored under `key`.

    Deliberately structure-agnostic: YouTube reshuffles its response tree often, and
    searching by key survives that far better than a hardcoded path.
    """
    if out is None:
        out = []
    if depth > 30 or not isinstance(obj, (dict, list)):
        return out
    if isinstance(obj, list):
        for o in obj:
            find_key(o, key, out, depth + 1)
        return out
    for k, v in obj.items():
        if k == key:
            out.append(v)
        find_key(v, key, out, depth + 1)
    return out


def _parse_lockup(lk: dict) -> Song | None:
    vid = lk.get("contentId")
    if not vid:
        return None
    md = (lk.get("metadata") or {}).get("lockupMetadataViewModel") or {}
    title = (md.get("title") or {}).get("content") or ""
    rows = ((md.get("metadata") or {}).get("contentMetadataViewModel") or {}).get("metadataRows") or []
    parts = [
        [p.get("text", {}).get("content") for p in (r.get("metadataParts") or []) if p.get("text")]
        for r in rows
    ]
    channel = parts[0][0] if parts and parts[0] else ""
    views = parts[1][0] if len(parts) > 1 and parts[1] else ""
    uploaded = parts[1][1] if len(parts) > 1 and len(parts[1]) > 1 else ""
    handles = find_key(md, "canonicalBaseUrl")
    duration = ""
    for b in find_key(lk, "thumbnailBadgeViewModel"):
        t = (b or {}).get("text") or ""
        if re.match(r"^\d+:\d\d", t):
            duration = t
            break
    clean = lambda s: re.sub(r"[\t\r\n]+", " ", s or "").strip()  # noqa: E731
    return Song(
        position=0,
        video_id=vid,
        title=clean(title),
        channel=clean(channel),
        channel_url=("https://www.youtube.com" + handles[0]) if handles else "",
        duration=clean(duration) or "0:00",
        views=parse_views(views),
        uploaded=clean(uploaded),
    )


def fetch(url_or_id: str, max_pages: int = 200) -> Playlist:
    pid = extract_playlist_id(url_or_id)
    html = _get(f"https://www.youtube.com/playlist?list={pid}&hl=en")

    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", html, re.S) or re.search(
        r'ytInitialData"\]\s*=\s*(\{.*?\});</script>', html, re.S
    )
    if not m:
        raise PlaylistNotFound(
            f"No playlist data at {pid}. It may be private, deleted, or the URL is wrong. "
            "Private playlists need OAuth - see docs/auth-setup.md."
        )
    data = json.loads(m.group(1))

    title_m = re.search(r"<title>(.*?)( - YouTube)?</title>", html)
    count_m = re.search(r"(\d[\d,]*) videos", html)
    pl = Playlist(
        playlist_id=pid,
        title=(title_m.group(1).strip() if title_m else ""),
        stated_count=int(count_m.group(1).replace(",", "")) if count_m else None,
    )

    api_key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
    client_ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
    ctx = {
        "client": {
            "clientName": "WEB",
            "clientVersion": client_ver.group(1) if client_ver else "2.20240101.00.00",
            "hl": "en",
            "gl": "US",
        }
    }

    used: set[str] = set()

    def ingest(root) -> str | None:
        for lk in find_key(root, "lockupViewModel"):
            if isinstance(lk, dict):
                song = _parse_lockup(lk)
                if song:
                    pl.songs.append(song)
        tokens = [
            c.get("token")
            for c in find_key(root, "continuationCommand")
            if isinstance(c, dict) and c.get("token")
        ]
        return next((t for t in tokens if t not in used), None)

    token = ingest(data)
    pages = 0
    while token and pages < max_pages:
        used.add(token)
        pages += 1
        before = len(pl.songs)
        resp = json.loads(
            _get(
                f"{BROWSE}?key={api_key.group(1) if api_key else ''}&prettyPrint=false",
                {"context": ctx, "continuation": token},
            )
        )
        token = ingest(resp)
        if len(pl.songs) == before:
            break

    for i, s in enumerate(pl.songs, 1):
        s.position = i
    return pl
