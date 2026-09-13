"""Extra doubles that model Google's error responses.

googleapiclient raises on .execute(), not when the request is built - the doubles
here mirror that, otherwise they test a code path that cannot happen in production.
"""

from conftest import FakeService


class _Resp:
    def __init__(self, status):
        self.status = status


class _HttpError(Exception):
    def __init__(self, status, content=b""):
        self.resp = _Resp(status)
        self.content = content
        super().__init__(f"HTTP {status}")


class _RaisingExec:
    def __init__(self, error):
        self.error = error

    def execute(self):
        raise self.error


class QuotaBlockedService(FakeService):
    """Succeeds for `ok_inserts` adds, then returns Google's 403 quotaExceeded."""

    def __init__(self, ok_inserts=1):
        super().__init__()
        self.ok_inserts = ok_inserts
        self.raised = None

    def insert(self, part, body):
        if "status" in part:
            return super().insert(part, body)
        if len(self.inserted) >= self.ok_inserts:
            self.raised = _HttpError(403, b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}')
            return _RaisingExec(self.raised)
        return super().insert(part, body)
