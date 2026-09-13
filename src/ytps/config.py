"""Configuration and the auth-tier decision.

The whole point: the credential you need depends on *what you are doing*, not on a
global setting. Reading a public playlist needs nothing at all.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .errors import CredentialsRequired

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is a convenience, not a requirement
    def load_dotenv(*_a, **_k):  # type: ignore[misc]
        return False


class Tier(str, Enum):
    NONE = "none"      # keyless InnerTube reader - no credential, no quota
    API_KEY = "api_key"
    OAUTH = "oauth"


class Visibility(str, Enum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


READ_OPS = {"fetch", "list", "read"}
WRITE_OPS = {"create", "edit", "delete", "publish"}

CONSOLE = "https://console.cloud.google.com/apis/credentials"
SETUP_DOC = "see docs/auth-setup.md"


@dataclass
class Config:
    api_key: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    token_path: Path = Path(".tokens/token.json")
    oauth_port: int = 0
    daily_quota: int = 10_000
    state_dir: Path = Path(".ytps")
    output_dir: Path = Path("out")
    prefer_api_for_reads: bool = False

    @classmethod
    def load(cls, env_file: str | os.PathLike | None = ".env") -> Config:
        if env_file and Path(env_file).exists():
            load_dotenv(env_file)
        g = os.getenv
        return cls(
            api_key=g("YT_API_KEY") or None,
            client_id=g("YT_OAUTH_CLIENT_ID") or None,
            client_secret=g("YT_OAUTH_CLIENT_SECRET") or None,
            token_path=Path(g("YT_OAUTH_TOKEN_PATH", ".tokens/token.json")),
            oauth_port=int(g("YT_OAUTH_PORT", "0")),
            daily_quota=int(g("YTPS_DAILY_QUOTA", "10000")),
            state_dir=Path(g("YTPS_STATE_DIR", ".ytps")),
            output_dir=Path(g("YTPS_OUTPUT_DIR", "out")),
            prefer_api_for_reads=g("YTPS_PREFER_API", "").lower() in {"1", "true", "yes"},
        )

    @property
    def has_oauth(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def resolve_tier(self, operation: str, visibility: Visibility | str = Visibility.PUBLIC) -> Tier:
        """Pick the cheapest credential tier that can do this job.

        Reads of public/unlisted playlists need nothing. Private reads and every
        write need OAuth. Raises CredentialsRequired naming the exact missing var.
        """
        vis = Visibility(visibility)
        op = operation.lower()

        if op in WRITE_OPS:
            if not self.has_oauth:
                raise CredentialsRequired(
                    operation=f"'{op}'",
                    missing=["YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET"],
                    reason="creating or changing a playlist acts on your account, "
                           "so Google requires a signed-in OAuth consent - an API key cannot do it.",
                    how=f"create a Desktop-app OAuth client at {CONSOLE}, then {SETUP_DOC}",
                )
            return Tier.OAUTH

        if op not in READ_OPS:
            raise ValueError(f"unknown operation: {operation!r}")

        if vis is Visibility.PRIVATE:
            if not self.has_oauth:
                raise CredentialsRequired(
                    operation="reading a private playlist",
                    missing=["YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET"],
                    reason="a private playlist is only visible to its owner, so the request "
                           "must be signed in as that owner.",
                    how=f"create a Desktop-app OAuth client at {CONSOLE}, then {SETUP_DOC}. "
                        "Or set the playlist to Unlisted, which stays off search but reads with "
                        "no credentials at all.",
                )
            return Tier.OAUTH

        # public or unlisted read
        if self.prefer_api_for_reads and self.api_key:
            return Tier.API_KEY
        return Tier.NONE
