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
