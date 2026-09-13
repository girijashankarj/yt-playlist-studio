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


PLACEHOLDER_HINTS = ("replacethis", "abcdefghijklmnop", "123456789012", "xxxx", "yyyy")


def mask(value: str | None) -> str:
    """Show enough to recognise a value, never enough to use it."""
    if not value:
        return "(not set)"
    if len(value) <= 12:
        return value[:2] + "…" + value[-2:]
    return value[:6] + "…" + value[-6:]


def check_credentials(cfg: Config) -> dict:
    """Validate credential *shape* offline. Makes no network calls.

    Exists so you can confirm a paste worked without showing the secret to anyone.
    """
    problems, warnings = [], []
    cid, sec = cfg.client_id, cfg.client_secret

    if not cid:
        problems.append("YT_OAUTH_CLIENT_ID is empty")
    else:
        if not cid.endswith(".apps.googleusercontent.com"):
            problems.append("YT_OAUTH_CLIENT_ID should end with .apps.googleusercontent.com")
        if any(h in cid.lower() for h in PLACEHOLDER_HINTS):
            problems.append("YT_OAUTH_CLIENT_ID still looks like the placeholder")

    if not sec:
        problems.append("YT_OAUTH_CLIENT_SECRET is empty")
    else:
        if any(h in sec.lower() for h in PLACEHOLDER_HINTS):
            problems.append("YT_OAUTH_CLIENT_SECRET still looks like the placeholder")
        elif not sec.startswith("GOCSPX-"):
            warnings.append(
                "YT_OAUTH_CLIENT_SECRET does not start with GOCSPX-. Older secrets differ, "
                "so this may be fine - but check you copied the secret, not the client ID."
            )
        if sec.endswith(".apps.googleusercontent.com"):
            problems.append("YT_OAUTH_CLIENT_SECRET holds a client ID - the two are swapped")

    if cfg.oauth_port:
        warnings.append(
            f"YT_OAUTH_PORT={cfg.oauth_port}: your client must list "
            f"http://localhost:{cfg.oauth_port}/ as an authorised redirect URI."
        )

    return {
        "client_id": mask(cid),
        "client_secret": mask(sec),
        "oauth_port": cfg.oauth_port or "random (Desktop-app client)",
        "token_cached": cfg.token_path.exists(),
        "token_path": str(cfg.token_path),
        "problems": problems,
        "warnings": warnings,
        "ready": not problems,
    }


def token_info(cfg: Config) -> dict:
    if not cfg.token_path.exists():
        return {"cached": False}
    try:
        data = json.loads(Path(cfg.token_path).read_text())
    except json.JSONDecodeError:
        return {"cached": False, "error": "token file is not valid JSON"}
    return {"cached": True, "scopes": data.get("scopes", []), "path": str(cfg.token_path)}
