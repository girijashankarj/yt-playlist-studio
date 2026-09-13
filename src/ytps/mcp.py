"""MCP server - the same operations as the CLI, exposed as tools.

Safety stance: read tools run freely; anything that touches the user's YouTube
account requires an explicit confirm flag, and publish_api defaults to a dry run.
"""

from __future__ import annotations

import json
from pathlib import Path

from .chunking import RulePack, chunk, coverage
from .config import Config
from .models import Playlist
from .publish.api_writer import estimate
from .publish.bulk_links import build_links
from .quota import Quota
from .tagging import tag_coverage, tag_songs
from .writers.csv_out import write_csv
from .writers.html_console import write_console
from .writers.xlsx import write_xlsx

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "The MCP server needs the mcp package.\n  Fix: pip install 'yt-playlist-studio[mcp]'"
    ) from e

mcp = FastMCP("yt-playlist-studio")
DEFAULT_RULES = Path(__file__).resolve().parents[2] / "rules" / "moods.default.yml"


def _songs_from(path: str):
    from .cli import _load_songs

    return _load_songs(Path(path))


@mcp.tool()
def playlist_fetch(playlist: str, out: str = "out/playlist.csv", visibility: str = "public") -> str:
    """Read a YouTube playlist to CSV. Public and unlisted need no credentials."""
    from .fetch import fetch_playlist

    pl = fetch_playlist(playlist, Config.load(), visibility=visibility)
    write_csv(pl.songs, out)
    return json.dumps(
        {
            "title": pl.title,
            "songs": len(pl),
            "stated_count": pl.stated_count,
            "hidden_unavailable": pl.hidden_count,
            "runtime_sec": pl.runtime_sec,
            "out": out,
        },
        indent=2,
    )


@mcp.tool()
def playlist_tag(file: str, out: str = "", overwrite: bool = False) -> str:
    """Infer language/genre/sub-genre/mood tags. Tags are derived, not official."""
    songs = tag_songs(_songs_from(file), overwrite=overwrite)
    dest = out or file
    write_csv(songs, dest)
    return json.dumps(
        {"tagged": len(songs), "out": dest, "fill_rate_percent": tag_coverage(songs),
         "caveat": "Tags are inferred from titles and channels, not official YouTube metadata."},
        indent=2,
    )


@mcp.tool()
def playlist_chunk(file: str, out: str = "out/moods", rules: str = "", prefix: str = "") -> str:
    """Slice a tagged CSV into mood playlists. Songs may appear in several moods."""
    pack = RulePack.load(rules or DEFAULT_RULES)
    pl = Playlist(playlist_id="local", songs=_songs_from(file))
    chunks = chunk(pl, pack)
    Path(out).mkdir(parents=True, exist_ok=True)
    for ch in chunks:
        write_csv(ch.songs, Path(out) / f"{prefix}{ch.name}.csv")
    return json.dumps(
        {
            "playlists": [
                {"name": f"{prefix}{c.name}", "songs": len(c.songs), "runtime": c.runtime}
                for c in chunks
            ],
            "coverage": coverage(pl, chunks),
            "out": out,
        },
        indent=2,
    )


@mcp.tool()
def playlist_export(path: str, fmt: str = "xlsx", out: str = "", title: str = "Playlist Build Console") -> str:
    """Export CSV playlists as xlsx and/or an HTML build console."""
    from .chunking import Chunk

    src = Path(path)
    files = sorted(src.glob("*.csv")) if src.is_dir() else [src]
    outdir = Path(out or (src if src.is_dir() else src.parent))
    outdir.mkdir(parents=True, exist_ok=True)
    made, chunks = [], []
    for f in files:
        songs = _songs_from(str(f))
        chunks.append(Chunk(f.stem, "", songs))
        if "xlsx" in fmt:
            made.append(str(write_xlsx(songs, outdir / f"{f.stem}.xlsx", name=f.stem)))
    if "html" in fmt:
        made.append(str(write_console(chunks, outdir / "build-console.html", title)))
    return json.dumps({"written": made}, indent=2)


@mcp.tool()
def publish_links(path: str) -> str:
    """Generate YouTube bulk-import links. Costs no quota and needs no credentials."""
    src = Path(path)
    files = sorted(src.glob("*.csv")) if src.is_dir() else [src]
    out = {f.stem: build_links(_songs_from(str(f))) for f in files}
    return json.dumps(
        {"playlists": out, "total_links": sum(len(v) for v in out.values()),
         "quota_used": 0}, indent=2
    )


@mcp.tool()
def publish_api(file: str, name: str = "", privacy: str = "private", confirm: bool = False,
                description: str = "Created with yt-playlist-studio") -> str:
    """Create a playlist on the signed-in YouTube account.

    Defaults to a dry run. Set confirm=true to actually write - this changes the
    user's account and costs 50 quota units per song.
    """
    cfg = Config.load()
    songs = _songs_from(file)
    name = name or Path(file).stem
    quota = Quota(cfg.state_dir / "quota.json", cfg.daily_quota)
    if not confirm:
        return json.dumps(
            {"dry_run": True, "playlist": name, "privacy": privacy, **estimate(songs),
             "quota": quota.status(),
             "note": "No calls made. Re-run with confirm=true to publish for real."},
            indent=2,
        )
    from .auth import build_service, whoami
    from .config import Tier
    from .publish.api_writer import publish

    service = build_service(cfg, Tier.OAUTH, write=True)
    result = publish(name, description, songs, service, quota, cfg.state_dir / "state",
                     privacy=privacy, dry_run=False)
    result["account"] = whoami(cfg)
    return json.dumps(result, indent=2)


@mcp.tool()
def quota_status() -> str:
    """How much YouTube API quota is left today, and how many song-adds that buys."""
    cfg = Config.load()
    return json.dumps(Quota(cfg.state_dir / "quota.json", cfg.daily_quota).status(), indent=2)


@mcp.tool()
def list_modes(rules: str = "") -> str:
    """List the moods in a rule pack."""
    pack = RulePack.load(rules or DEFAULT_RULES)
    return json.dumps(
        {"pack": pack.name, "description": pack.description,
         "modes": [{"name": m.name, "description": m.description} for m in pack.modes],
         "catch_all": pack.catch_all}, indent=2,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
