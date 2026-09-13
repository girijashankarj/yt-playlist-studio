"""Shared test doubles. No test in this suite may touch the network."""

import pytest


class _Exec:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class ExplodingService:
    """Any attribute access means a network call was attempted."""

    def __getattr__(self, name):
        raise AssertionError(f"dry run touched the network: service.{name}()")


class FakeService:
    """Records calls instead of making them."""

    def __init__(self, existing=()):
        self.inserted, self.created = [], []
        self._existing = list(existing)

    def playlists(self):
        return self

    def playlistItems(self):
        return self

    def insert(self, part, body):
        if "status" in part:
            self.created.append(body)
            return _Exec({"id": "PLfake123"})
        self.inserted.append(body["snippet"]["resourceId"]["videoId"])
        return _Exec({})

    def list(self, **kw):
        return _Exec({"items": [{"contentDetails": {"videoId": v}} for v in self._existing]})


@pytest.fixture
def fake_service():
    return FakeService()
