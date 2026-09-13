"""OAuth and API-key plumbing.

The repo ships no credentials. Every user brings their own Google Cloud project,
which is the only honest model for an open-source tool that writes to accounts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import Config, Tier
from .errors import CredentialsRequired

READONLY = "https://www.googleapis.com/auth/youtube.readonly"
WRITE = "https://www.googleapis.com/auth/youtube.force-ssl"

_IMPORT_HINT = (
    "The Data API path needs extra packages.\n"
    "  Fix: pip install 'yt-playlist-studio[api]'\n"
    "  Or avoid it entirely: reading public/unlisted playlists needs no API at all."
)


def _require_google():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:
        raise CredentialsRequired(
            operation="the YouTube Data API", missing=["python packages"],
            reason=str(e), how=_IMPORT_HINT,
        ) from e
    return Request, Credentials, InstalledAppFlow, build


def load_credentials(cfg: Config, scopes: list[str]):
    """Load cached OAuth creds, refresh them, or run the consent flow once.

    The flow opens a browser on the user's own machine - we never handle a password.
    """
    Request, Credentials, InstalledAppFlow, _ = _require_google()
    if not cfg.has_oauth:
        raise CredentialsRequired(
            operation="OAuth", missing=["YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET"],
            reason="no OAuth client configured.", how="see docs/auth-setup.md",
        )

    creds = None
    if cfg.token_path.exists():
        creds = Credentials.from_authorized_user_file(str(cfg.token_path), scopes)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": cfg.client_id,
                    "client_secret": cfg.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            },
            scopes,
        )
        if cfg.oauth_port:
            # A "Web application" client only accepts redirect URIs registered in the
            # console, so the port cannot be random. Pin it and tell the user what to add.
            print(
                f"Using a fixed callback port. Your OAuth client must list this exact "
                f"redirect URI:\n    http://localhost:{cfg.oauth_port}/\n"
                "(Google Cloud console -> Clients -> your client -> Authorised redirect URIs)",
                file=sys.stderr,
            )
        try:
            creds = flow.run_local_server(port=cfg.oauth_port)
        except OSError as e:
            raise CredentialsRequired(
                operation="OAuth consent",
                missing=["a free local port"],
                reason=f"could not open a local callback server on port {cfg.oauth_port}: {e}",
                how="pick another port with YT_OAUTH_PORT, or unset it to use a random one "
                    "(random ports work only with a Desktop-app client).",
            ) from e

    cfg.token_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.token_path.write_text(creds.to_json())
    cfg.token_path.chmod(0o600)
    return creds


def build_service(cfg: Config, tier: Tier, write: bool = False):
    _, _, _, build = _require_google()
    if tier is Tier.API_KEY:
        if not cfg.api_key:
            raise CredentialsRequired(
                operation="API-key read", missing=["YT_API_KEY"],
                reason="YTPS_PREFER_API is on but no key is set.",
                how="add YT_API_KEY to .env, or unset YTPS_PREFER_API to use the keyless reader.",
            )
        return build("youtube", "v3", developerKey=cfg.api_key, cache_discovery=False)
    creds = load_credentials(cfg, [WRITE] if write else [READONLY])
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def whoami(cfg: Config) -> dict:
    """Which account are we about to write to? Worth showing before any write."""
    service = build_service(cfg, Tier.OAUTH, write=True)
    resp = service.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items") or []
    if not items:
        return {"channel": None}
    return {"channel": items[0]["snippet"]["title"], "channel_id": items[0]["id"]}


def token_info(cfg: Config) -> dict:
    if not cfg.token_path.exists():
        return {"cached": False}
    try:
        data = json.loads(Path(cfg.token_path).read_text())
    except json.JSONDecodeError:
        return {"cached": False, "error": "token file is not valid JSON"}
    return {"cached": True, "scopes": data.get("scopes", []), "path": str(cfg.token_path)}
