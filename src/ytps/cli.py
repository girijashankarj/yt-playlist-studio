"""Command line interface."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import __version__
from .chunking import RulePack, chunk, coverage
from .config import Config
from .errors import YtpsError
from .models import Playlist, Song
from .publish.api_writer import estimate
from .publish.bulk_links import build_links
from .quota import Quota
from .tagging import tag_coverage, tag_songs
from .writers.csv_out import write_csv, write_m3u
from .writers.html_console import write_console
from .writers.xlsx import write_index_xlsx, write_xlsx

DEFAULT_RULES = Path(__file__).resolve().parents[2] / "rules" / "moods.default.yml"


def _load_songs(path: Path) -> list[Song]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    out = []
    for i, r in enumerate(rows, 1):
        out.append(
            Song(
                position=int(r.get("position") or i),
                video_id=r["video_id"],
                title=r.get("title", ""),
                channel=r.get("channel", ""),
                channel_url=r.get("channel_url", ""),
                duration=r.get("duration", "0:00"),
                duration_sec=int(r.get("duration_sec") or 0),
                views=int(r["views"]) if (r.get("views") or "").isdigit() else None,
                uploaded=r.get("uploaded", ""),
                song_name=r.get("song_name", ""),
                artist=r.get("artist", ""),
                album=r.get("album", ""),
                language=r.get("language", ""),
                genre=r.get("genre", ""),
                sub_genre=r.get("sub_genre", ""),
                category=r.get("category", ""),
            )
        )
    return out


def cmd_fetch(a) -> int:
    from .fetch import fetch_playlist

    pl = fetch_playlist(a.playlist, Config.load(), visibility=a.visibility, via=a.via)
    print(f"{pl.title or pl.playlist_id}: {len(pl)} songs", file=sys.stderr)
    if pl.hidden_count:
        print(
            f"  note: YouTube states {pl.stated_count}; {pl.hidden_count} are unavailable "
            "(deleted or private) and cannot be read.",
            file=sys.stderr,
        )
    out = Path(a.out or "out/playlist.csv")
    write_csv(pl.songs, out)
    print(f"wrote {out}", file=sys.stderr)
    return 0


def cmd_tag(a) -> int:
    path = Path(a.file)
    songs = tag_songs(_load_songs(path), use_llm=a.llm, overwrite=a.overwrite)
    write_csv(songs, a.out or path)
    cov = tag_coverage(songs)
    print(f"tagged {len(songs)} songs -> {a.out or path}", file=sys.stderr)
    print("  fill rate: " + ", ".join(f"{k} {v}%" for k, v in cov.items()), file=sys.stderr)
    print("  reminder: tags are inferred from titles, not official metadata.", file=sys.stderr)
    weak = [k for k, v in cov.items() if v < 50 and k != "artist"]
    if weak:
        print(
            f"  heads up: {', '.join(weak)} came out mostly blank. Title text alone rarely "
            "reveals\n            genre or mood - use `ytps tag --llm` or edit the CSV before "
            "chunking.",
            file=sys.stderr,
        )
    return 0


def cmd_chunk(a) -> int:
    songs = _load_songs(Path(a.file))
    pack = RulePack.load(a.rules or DEFAULT_RULES)
    pl = Playlist(playlist_id="local", songs=songs)
    chunks = chunk(pl, pack, order_by=a.order_by)
    outdir = Path(a.out or "out/moods")
    outdir.mkdir(parents=True, exist_ok=True)
    for ch in chunks:
        write_csv(ch.songs, outdir / f"{a.prefix}{ch.name}.csv")
        print(f"  {a.prefix}{ch.name:<14}{len(ch.songs):>5} songs  {ch.runtime}", file=sys.stderr)
    cov = coverage(pl, chunks)
    catch = next((c for c in chunks if c.name == pack.catch_all), None)
    if catch and len(catch.songs) > len(songs) * 0.4:
        pct = round(len(catch.songs) / len(songs) * 100)
        print(
            f"\n  warning: {pct}% of songs fell into {pack.catch_all}. That usually means the "
            "tags are too sparse to chunk on,\n           not that the rules are wrong. The "
            "built-in heuristics only read titles and channel names.\n           Run `ytps tag "
            "--llm` with a registered provider, or fill the Genre/Sub-Genre/Category\n           "
            "columns yourself, then re-run chunk.",
            file=sys.stderr,
        )
    dup = f" ({cov['duplicate_rows']} duplicate row(s) in source)" if cov["duplicate_rows"] else ""
    print(
        f"{len(chunks)} playlists -> {outdir} | "
        f"coverage {cov['covered']}/{cov['total']} unique videos{dup}"
        + ("" if cov["complete"] else f" | ORPHANS: {len(cov['orphans'])}"),
        file=sys.stderr,
    )
    return 0 if cov["complete"] else 1


def cmd_export(a) -> int:
    src = Path(a.path)
    files = sorted(src.glob("*.csv")) if src.is_dir() else [src]
    if not files:
        print(f"no CSV files in {src}", file=sys.stderr)
        return 1
    fmts = {f.strip() for f in a.format.split(",")}
    outdir = Path(a.out or (src if src.is_dir() else src.parent))
    outdir.mkdir(parents=True, exist_ok=True)
    from .chunking import Chunk

    chunks = []
    for f in files:
        songs = _load_songs(f)
        name = f.stem
        chunks.append(Chunk(name, "", songs))
        if "xlsx" in fmts:
            write_xlsx(songs, outdir / f"{name}.xlsx", name=name)
        if "m3u" in fmts:
            write_m3u(songs, outdir / f"{name}.m3u", name=name)
    if "html" in fmts:
        write_console(chunks, outdir / "build-console.html", a.title)
    if "xlsx" in fmts and len(chunks) > 1:
        write_index_xlsx(chunks, outdir / "Index.xlsx", a.title)
    print(f"exported {len(files)} playlist(s) as {', '.join(sorted(fmts))} -> {outdir}", file=sys.stderr)
    return 0


def cmd_publish_links(a) -> int:
    src = Path(a.path)
    files = sorted(src.glob("*.csv")) if src.is_dir() else [src]
    total = 0
    for f in files:
        links = build_links(_load_songs(f))
        total += len(links)
        print(f"\n# {f.stem}  ({len(links)} link{'s' if len(links) != 1 else ''})")
        for link in links:
            print(f"  {link['index']:>2}. [{link['positions']:>7}] {link['action']}\n      {link['url']}")
    print(f"\n{total} links across {len(files)} playlist(s). No quota used.", file=sys.stderr)
    return 0


def cmd_publish_api(a) -> int:
    cfg = Config.load()
    songs = _load_songs(Path(a.file))
    name = a.name or Path(a.file).stem
    quota = Quota(cfg.state_dir / "quota.json", cfg.daily_quota)
    if a.dry_run:
        est = estimate(songs)
        print(json.dumps({"playlist": name, **est, "quota": quota.status()}, indent=2))
        print("\nDry run: no network calls were made.", file=sys.stderr)
        if est["units"] > quota.remaining():
            print(
                f"Heads up: this needs {est['units']} units but only {quota.remaining()} remain "
                f"today. It will publish in stages across ~{est['days_at_default_quota']} days, "
                "or use `ytps publish links` to do it in one sitting for free.",
                file=sys.stderr,
            )
        return 0

    from .auth import build_service, whoami
    from .config import Tier
    from .publish.api_writer import publish

    who = whoami(cfg)
    print(f"Publishing to YouTube channel: {who.get('channel')}", file=sys.stderr)
    if not a.yes:
        reply = input(f"Create playlist {name!r} ({len(songs)} songs, {a.privacy}) there? [y/N] ")
        if reply.strip().lower() not in {"y", "yes"}:
            print("Aborted.", file=sys.stderr)
            return 1
    service = build_service(cfg, Tier.OAUTH, write=True)
    result = publish(
        name, a.description, songs, service, quota, cfg.state_dir / "state",
        privacy=a.privacy, dry_run=False,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["complete"] else 2


def cmd_quota(a) -> int:
    cfg = Config.load()
    print(json.dumps(Quota(cfg.state_dir / "quota.json", cfg.daily_quota).status(), indent=2))
    return 0


def cmd_rules(a) -> int:
    pack = RulePack.load(a.rules or DEFAULT_RULES)
    print(f"{pack.name}: {pack.description}\n")
    for m in pack.modes:
        print(f"  {m.name:<14} {m.description}")
    print(f"\n  {pack.catch_all:<14} {pack.catch_all_description}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ytps", description="Fetch, tag, chunk and publish YouTube playlists.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="read a playlist (no credentials for public/unlisted)")
    f.add_argument("playlist", help="playlist URL or id")
    f.add_argument("-o", "--out")
    f.add_argument("--visibility", default="public", choices=["public", "unlisted", "private"])
    f.add_argument("--via", choices=["scrape", "api"], help="force a read path")
    f.set_defaults(func=cmd_fetch)

    t = sub.add_parser("tag", help="infer language/genre/mood tags")
    t.add_argument("file")
    t.add_argument("-o", "--out")
    t.add_argument("--llm", action="store_true", help="use a registered LLM provider")
    t.add_argument("--overwrite", action="store_true", help="replace existing tags")
    t.set_defaults(func=cmd_tag)

    c = sub.add_parser("chunk", help="slice into mood playlists")
    c.add_argument("file")
    c.add_argument("-o", "--out")
    c.add_argument("--rules")
    c.add_argument("--prefix", default="", help="e.g. GB- to name files GB-Gym.csv")
    c.add_argument("--order-by", default="views", choices=["views", "duration", "position"])
    c.set_defaults(func=cmd_chunk)

    e = sub.add_parser("export", help="write xlsx / m3u / html console")
    e.add_argument("path", help="a CSV file or a directory of them")
    e.add_argument("-o", "--out")
    e.add_argument("--format", default="xlsx", help="comma list: xlsx,m3u,html")
    e.add_argument("--title", default="Playlist Build Console")
    e.set_defaults(func=cmd_export)

    pub = sub.add_parser("publish", help="create playlists on YouTube")
    psub = pub.add_subparsers(dest="how", required=True)

    pl = psub.add_parser("links", help="free browser import links - no quota, no OAuth")
    pl.add_argument("path")
    pl.set_defaults(func=cmd_publish_links)

    pa = psub.add_parser("api", help="official Data API - automated, quota-bound")
    pa.add_argument("file")
    pa.add_argument("--name")
    pa.add_argument("--description", default="Created with yt-playlist-studio")
    pa.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    pa.add_argument("--dry-run", action="store_true", default=True)
    pa.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="actually publish")
    pa.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    pa.set_defaults(func=cmd_publish_api)

    q = sub.add_parser("quota", help="show today's API quota")
    q.set_defaults(func=cmd_quota)

    r = sub.add_parser("rules", help="list the modes in a rule pack")
    r.add_argument("--rules")
    r.set_defaults(func=cmd_rules)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except YtpsError as e:
        print(f"\nerror: {e}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted - progress is saved, re-run to resume.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
