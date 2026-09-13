"""Errors that tell the user what to do next, not just what broke."""


class YtpsError(Exception):
    """Base class. Message should always name the fix, not only the fault."""


class PlaylistNotFound(YtpsError):
    pass


class CredentialsRequired(YtpsError):
    """Raised when an operation needs credentials the user has not supplied."""

    def __init__(self, operation: str, missing: list[str], reason: str, how: str):
        self.operation, self.missing = operation, missing
        super().__init__(
            f"{operation} needs {', '.join(missing)} in your .env.\n"
            f"  Why: {reason}\n"
            f"  How: {how}"
        )


class QuotaExceeded(YtpsError):
    """Raised before a call that would exceed the daily allowance."""

    def __init__(self, needed: int, remaining: int, resets_at: str):
        self.needed, self.remaining = needed, remaining
        super().__init__(
            f"This step needs {needed} quota units but only {remaining} remain today.\n"
            f"  Quota resets at {resets_at} (midnight US/Pacific).\n"
            f"  Run again after the reset to resume, or use `ytps publish links` "
            f"which costs no quota at all."
        )


class RuleError(YtpsError):
    pass
