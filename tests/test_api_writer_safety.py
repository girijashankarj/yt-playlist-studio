"""The publish path touches someone's real account. These are the guard rails."""

import pytest
from conftest import ExplodingService, FakeService

from ytps.errors import QuotaExceeded
from ytps.models import Song
from ytps.publish.api_writer import publish
from ytps.quota import Quota


def songs(n):
    return [Song(position=i, video_id=f"{i:011d}", title=f"t{i}", duration="3:00")
            for i in range(1, n + 1)]


@pytest.fixture
def quota(tmp_path):
    return Quota(tmp_path / "q.json", daily=10_000)


def test_dry_run_makes_zero_network_calls(quota, tmp_path):
    out = publish("Gym", "d", songs(50), ExplodingService(), quota, tmp_path, dry_run=True)
    assert out["dry_run"] is True
    assert out["units"] == 50 * 50 + 50
    assert quota.used() == 0, "a dry run must not spend quota either"


def test_dry_run_is_the_default(quota, tmp_path):
    out = publish("Gym", "d", songs(3), ExplodingService(), quota, tmp_path)
    assert out["dry_run"] is True


def test_real_publish_creates_then_adds(quota, tmp_path):
    svc = FakeService()
    out = publish("Gym", "d", songs(4), svc, quota, tmp_path, dry_run=False)
    assert len(svc.created) == 1
    assert svc.inserted == [f"{i:011d}" for i in range(1, 5)]
    assert out["complete"] and out["added"] == 4
    assert quota.used() == 50 + 4 * 50


def test_privacy_defaults_to_private(quota, tmp_path):
    svc = FakeService()
    publish("Gym", "d", songs(1), svc, quota, tmp_path, dry_run=False)
    assert svc.created[0]["status"]["privacyStatus"] == "private"


def test_rejects_bad_privacy(quota, tmp_path):
    with pytest.raises(ValueError):
        publish("Gym", "d", songs(1), FakeService(), quota, tmp_path,
                privacy="everyone", dry_run=False)


def test_stops_cleanly_at_the_quota_cap_and_saves_resume(tmp_path):
    quota = Quota(tmp_path / "q.json", daily=200)  # create (50) + 3 adds (150)
    svc = FakeService()
    out = publish("Gym", "d", songs(10), svc, quota, tmp_path, dry_run=False)
    assert out["complete"] is False
    assert out["added"] == 3
    assert "resets at" in out["stopped_because"]
    assert out["resume_with"]
    assert (tmp_path / "Gym.json").exists()


def test_resume_skips_what_is_already_there(tmp_path):
    quota = Quota(tmp_path / "q.json", daily=10_000)
    state = tmp_path / "Gym.json"
    state.write_text('{"playlist_name":"Gym","playlist_id":"PLfake123","added":["00000000001"]}')
    svc = FakeService(existing=["00000000001", "00000000002"])
    out = publish("Gym", "d", songs(4), svc, quota, tmp_path, dry_run=False)
    assert svc.created == []                       # did not recreate the playlist
    assert svc.inserted == ["00000000003", "00000000004"]
    assert out["skipped_already_present"] == 2
    assert out["complete"]


def test_quota_error_names_the_free_alternative(tmp_path):
    quota = Quota(tmp_path / "q.json", daily=10)
    with pytest.raises(QuotaExceeded) as e:
        quota.charge("playlistItems.insert")
    assert "publish links" in str(e.value)


# --- transient failure handling -------------------------------------------------
class _Resp:
    def __init__(self, status):
        self.status = status


class _HttpError(Exception):
    def __init__(self, status):
        self.resp = _Resp(status)
        super().__init__(f"HTTP {status}")


class FlakyRequest:
    """Fails with `status` for the first `fail_times` calls, then succeeds."""

    def __init__(self, fail_times, status=409):
        self.fail_times, self.status, self.calls = fail_times, status, 0

    def execute(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise _HttpError(self.status)
        return {"ok": True}


@pytest.mark.parametrize("status", [409, 429, 500, 502, 503, 504])
def test_transient_errors_are_retried(status):
    from ytps.publish.api_writer import execute

    req = FlakyRequest(2, status)
    assert execute(req, sleep=lambda _: None) == {"ok": True}
    assert req.calls == 3


def test_permanent_errors_are_not_retried():
    from ytps.publish.api_writer import execute

    req = FlakyRequest(5, status=404)
    with pytest.raises(_HttpError):
        execute(req, sleep=lambda _: None)
    assert req.calls == 1, "a 404 must fail immediately, not burn retries"


def test_gives_up_after_the_attempt_limit():
    from ytps.publish.api_writer import execute

    req = FlakyRequest(99, status=409)
    with pytest.raises(_HttpError):
        execute(req, attempts=4, sleep=lambda _: None)
    assert req.calls == 4


class CrashingService(FakeService):
    """Succeeds for `ok_inserts` songs, then raises a non-retryable error."""

    def __init__(self, ok_inserts):
        super().__init__()
        self.ok_inserts = ok_inserts

    def insert(self, part, body):
        if "status" in part:
            return super().insert(part, body)
        if len(self.inserted) >= self.ok_inserts:
            raise _HttpError(404)
        return super().insert(part, body)


def test_progress_is_saved_even_when_publishing_crashes(quota, tmp_path):
    """Regression: a crash mid-loop used to discard up to 9 recorded adds."""
    from ytps.publish.api_writer import PublishState

    with pytest.raises(_HttpError):
        publish("Gym", "d", songs(20), CrashingService(7), quota, tmp_path, dry_run=False)
    saved = PublishState.load(tmp_path / "Gym.json", "Gym")
    assert len(saved.added) == 7, "every successful add must survive the crash"
    assert saved.playlist_id
