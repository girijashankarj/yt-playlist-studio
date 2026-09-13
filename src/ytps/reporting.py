"""Human-readable terminal output.

A publish run ends with a list of things that now exist on someone's account. That
deserves a readable summary, not a JSON dump - you should be able to see what was
created, how full each playlist is and where to click, at a glance.
"""

from __future__ import annotations

import os
import sys

DONE, PARTIAL, PENDING = "done", "partial", "pending"
MARK = {DONE: "✓", PARTIAL: "◐", PENDING: "·"}


def _use_colour(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


class Style:
    def __init__(self, enabled: bool):
        self.on = enabled

    def _w(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.on else text

    def bold(self, t):  return self._w("1", t)
    def dim(self, t):   return self._w("2", t)
    def green(self, t): return self._w("32", t)
    def amber(self, t): return self._w("33", t)
    def blue(self, t):  return self._w("36", t)


def bar(done: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return " " * width
    filled = round(width * done / total)
    return "█" * filled + "░" * (width - filled)


def _fmt(n: int) -> str:
    return f"{n:,}"


def render(
    entries: list,
    summary: dict,
    quota: dict,
    channel: str | None = None,
    stopped: str | None = None,
    next_run: str | None = None,
    stream=None,
) -> str:
    """entries: objects with .name .status .added .total .url"""
    stream = stream or sys.stdout
    s = Style(_use_colour(stream))
    out: list[str] = []
    width = 74

    out.append("")
    title = "Playlists on YouTube"
    out.append(s.bold(title) + (s.dim(f"   {channel}") if channel else ""))
    out.append(s.dim("─" * width))

    groups: dict[str, list] = {}
    for e in entries:
        groups.setdefault(e.name.split("-")[0] if "-" in e.name else "", []).append(e)

    for prefix in sorted(groups):
        rows = sorted(groups[prefix], key=lambda e: (e.status != DONE, -e.total))
        if prefix:
            live = sum(1 for r in rows if r.status == DONE)
            out.append("")
            out.append(s.dim(f"  {prefix}  ({live}/{len(rows)} complete)"))
        for e in rows:
            mark = MARK[e.status]
            mark = (s.green(mark) if e.status == DONE
                    else s.amber(mark) if e.status == PARTIAL else s.dim(mark))
            count = f"{e.added}/{e.total}"
            name = e.name if e.status != PENDING else s.dim(e.name)
            link = s.blue(e.url) if e.url else s.dim("not created yet")
            out.append(f"  {mark} {name:<{22 + (len(name) - len(e.name))}}{count:>9}   {link}")

    out.append("")
    out.append(s.dim("─" * width))
    pct = round(summary["songs_added"] / max(1, summary["songs_total"]) * 100)
    out.append(
        f"  {s.bold(str(summary['playlists_done']))} of {summary['playlists_total']} playlists"
        f"   ·   {s.bold(_fmt(summary['songs_added']))} of {_fmt(summary['songs_total'])} songs"
        f"   ·   {pct}%"
    )
    out.append(f"  {bar(summary['songs_added'], summary['songs_total'])}")
    out.append("")

    used, allowance = quota["used"], quota["daily_allowance"]
    out.append(
        s.dim(f"  Quota today   {_fmt(used)}/{_fmt(allowance)} units used"
              f"  ·  resets {quota['resets_at']}")
    )
    if summary["songs_remaining"]:
        days = -(-summary["songs_remaining"] // max(1, allowance // 50))
        out.append(
            s.dim(f"  Remaining     {_fmt(summary['songs_remaining'])} songs"
                  f"  ·  about {days} more daily run{'s' if days != 1 else ''}")
        )
        if next_run:
            out.append(s.dim(f"  Next run      {next_run}"))
    else:
        out.append("  " + s.green("Everything published."))
    if stopped:
        out.append("")
        out.append(s.amber(f"  Stopped: {stopped}"))
    out.append("")
    return "\n".join(out)
