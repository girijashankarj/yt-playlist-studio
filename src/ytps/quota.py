"""Quota ledger.

The YouTube Data API gives 10,000 units/day and charges 50 units for every single
song added to a playlist. That is ~200 adds per day. Writers must know the bill
before they start, so nothing dies halfway through a 300-song playlist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import QuotaExceeded

# Verified against developers.google.com/youtube/v3/determine_quota_cost
COSTS = {
    "playlists.list": 1,
    "playlistItems.list": 1,
    "videos.list": 1,
    "playlists.insert": 50,
    "playlists.update": 50,
    "playlists.delete": 50,
    "playlistItems.insert": 50,
    "playlistItems.update": 50,
    "playlistItems.delete": 50,
    "search.list": 100,
}

# Quota resets at midnight US/Pacific. Pacific is UTC-8 (-7 in DST); we use -8 so the
# reset we report is never earlier than the real one - better to under-promise.
_PACIFIC = timezone(timedelta(hours=-8))


def quota_day(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(_PACIFIC).strftime("%Y-%m-%d")


def next_reset(now: datetime | None = None) -> str:
    pac = (now or datetime.now(timezone.utc)).astimezone(_PACIFIC)
    nxt = (pac + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt.strftime("%Y-%m-%d %H:%M %Z")


@dataclass
class Quota:
    path: Path
    daily: int = 10_000

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def used(self, day: str | None = None) -> int:
        return int(self._read().get(day or quota_day(), 0))

    def remaining(self, day: str | None = None) -> int:
        return max(0, self.daily - self.used(day))

    @staticmethod
    def cost(method: str, calls: int = 1) -> int:
        if method not in COSTS:
            raise KeyError(f"unknown API method {method!r}; add it to quota.COSTS")
        return COSTS[method] * calls

    def estimate(self, plan: dict[str, int]) -> int:
        """plan: {'playlistItems.insert': 300, ...} -> total units."""
        return sum(self.cost(m, n) for m, n in plan.items())

    def check(self, units: int) -> None:
        if units > self.remaining():
            raise QuotaExceeded(units, self.remaining(), next_reset())

    def charge(self, method: str, calls: int = 1) -> int:
        units = self.cost(method, calls)
        self.check(units)
        day = quota_day()
        data = self._read()
        data[day] = int(data.get(day, 0)) + units
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=1, sort_keys=True))
        return units

    def exhaust(self) -> None:
        """Record today as fully spent, because Google said so.

        Keeps later runs from hammering an API that will only refuse them.
        """
        day = quota_day()
        data = self._read()
        data[day] = max(int(data.get(day, 0)), self.daily)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=1, sort_keys=True))

    def status(self) -> dict:
        return {
            "day": quota_day(),
            "used": self.used(),
            "remaining": self.remaining(),
            "daily_allowance": self.daily,
            "resets_at": next_reset(),
            "adds_left_today": self.remaining() // COSTS["playlistItems.insert"],
        }
