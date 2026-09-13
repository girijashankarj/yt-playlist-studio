"""One entry point for reading a playlist, whatever the tier."""

from __future__ import annotations

from .config import Config, Tier, Visibility
from .models import Playlist
from .quota import Quota
from .sources import api as api_source
from .sources import scrape as scrape_source


def fetch_playlist(
    url_or_id: str,
    cfg: Config | None = None,
    visibility: str = "public",
    via: str | None = None,
) -> Playlist:
    """Read a playlist using the cheapest credential tier that can do the job.

    via: None (auto), 'scrape' to force keyless, or 'api' to force the Data API.
    """
    cfg = cfg or Config.load()
    pid = scrape_source.extract_playlist_id(url_or_id)

    if via == "scrape":
        return scrape_source.fetch(pid)

    tier = Tier.OAUTH if via == "api" else cfg.resolve_tier("fetch", Visibility(visibility))
    if tier is Tier.NONE:
        return scrape_source.fetch(pid)

    quota = Quota(cfg.state_dir / "quota.json", cfg.daily_quota)
    from .auth import build_service

    service = build_service(cfg, tier, write=False)
    return api_source.fetch(pid, service, quota)
