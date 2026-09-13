"""Rule engine that slices a playlist into mood playlists.

Rules are data, not code, so contributors extend the tool by editing YAML.
Songs may land in several moods on purpose - that is the point of moods.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import RuleError
from .models import Playlist, Song

FIELDS = {"language", "genre", "sub_genre", "category", "artist", "channel"}


@dataclass
class Mode:
    name: str
    description: str = ""
    any_of: dict[str, list[str]] | None = None
    none_of: dict[str, list[str]] | None = None
    min_sec: int | None = None
    max_sec: int | None = None
    match: str = "all"  # 'all' = every field group must hit; 'any' = one is enough

    def validate(self) -> None:
        for grp in (self.any_of or {}, self.none_of or {}):
            for f in grp:
                if f not in FIELDS:
                    raise RuleError(
                        f"mode {self.name!r} uses unknown field {f!r}. "
                        f"Valid fields: {', '.join(sorted(FIELDS))}"
                    )
        if self.match not in {"all", "any"}:
            raise RuleError(f"mode {self.name!r}: match must be 'all' or 'any'")

    def matches(self, s: Song) -> bool:
        if self.min_sec is not None and s.duration_sec < self.min_sec:
            return False
        if self.max_sec is not None and s.duration_sec > self.max_sec:
            return False
        for field, values in (self.none_of or {}).items():
            if getattr(s, field, "") in values:
                return False
        groups = self.any_of or {}
        if not groups:
            return True
        hits = [getattr(s, f, "") in v for f, v in groups.items()]
        return any(hits) if self.match == "any" else all(hits)


@dataclass
class RulePack:
    name: str
    modes: list[Mode]
    description: str = ""
    catch_all: str | None = "Misc"
    catch_all_description: str = "Everything that fits no other mode"

    @classmethod
    def load(cls, path: str | Path) -> RulePack:
        data = yaml.safe_load(Path(path).read_text())
        if not data or "modes" not in data:
            raise RuleError(f"{path} has no 'modes:' list")
        modes = []
        for raw in data["modes"]:
            if "name" not in raw:
                raise RuleError(f"a mode in {path} is missing 'name'")
            m = Mode(**{k: v for k, v in raw.items() if k in Mode.__annotations__})
            m.validate()
            modes.append(m)
        names = [m.name for m in modes]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise RuleError(f"duplicate mode names in {path}: {', '.join(sorted(dupes))}")
        return cls(
            name=data.get("name", Path(path).stem),
            description=data.get("description", ""),
            modes=modes,
            catch_all=data.get("catch_all", "Misc"),
            catch_all_description=data.get("catch_all_description", cls.catch_all_description),
        )


@dataclass
class Chunk:
    name: str
    description: str
    songs: list[Song]

    @property
    def runtime_sec(self) -> int:
        return sum(s.duration_sec for s in self.songs)

    @property
    def runtime(self) -> str:
        h, rem = divmod(self.runtime_sec, 3600)
        return f"{h}h {rem // 60:02d}m"


def chunk(pl: Playlist, pack: RulePack, order_by: str = "views") -> list[Chunk]:
    """Slice a playlist into one Chunk per mode, plus the catch-all.

    Empty modes are dropped - an empty playlist file helps nobody.
    """
    def key(s: Song):
        return {"views": lambda x: x.views or 0,
                "duration": lambda x: x.duration_sec,
                "position": lambda x: -x.position}[order_by](s)

    out: list[Chunk] = []
    assigned: set[str] = set()
    for m in pack.modes:
        sel = [s for s in pl.songs if m.matches(s)]
        if not sel:
            continue
        assigned |= {s.video_id for s in sel}
        out.append(Chunk(m.name, m.description, sorted(sel, key=key, reverse=True)))

    if pack.catch_all:
        left = [s for s in pl.songs if s.video_id not in assigned]
        if left:
            out.append(
                Chunk(pack.catch_all, pack.catch_all_description, sorted(left, key=key, reverse=True))
            )
    return out


def coverage(pl: Playlist, chunks: list[Chunk]) -> dict:
    """Did every song land somewhere? The catch-all should make this always true.

    Counted by unique video id, so a playlist that lists the same video twice
    reports one video - `rows` keeps the raw count so the difference is visible.
    """
    covered = {s.video_id for c in chunks for s in c.songs}
    all_ids = {s.video_id for s in pl.songs}
    return {
        "rows": len(pl.songs),
        "total": len(all_ids),
        "covered": len(covered),
        "duplicate_rows": len(pl.songs) - len(all_ids),
        "orphans": sorted(all_ids - covered),
        "complete": covered == all_ids,
    }
