import pytest

from ytps.errors import QuotaExceeded
from ytps.quota import COSTS, Quota


@pytest.fixture
def q(tmp_path):
    return Quota(tmp_path / "quota.json", daily=10_000)


def test_documented_costs():
    # verified against developers.google.com/youtube/v3/determine_quota_cost
    assert COSTS["playlistItems.insert"] == 50
    assert COSTS["playlistItems.list"] == 1
    assert COSTS["playlists.insert"] == 50


def test_default_allowance_is_about_200_adds(q):
    assert q.status()["adds_left_today"] == 200


def test_estimate_matches_hand_math(q):
    assert q.estimate({"playlistItems.insert": 3341, "playlists.insert": 29}) == 168_500


def test_charge_accumulates_and_persists(q):
    q.charge("playlistItems.insert", 3)
    assert q.used() == 150
    assert Quota(q.path, daily=10_000).used() == 150  # survives reload


def test_refuses_to_overspend(q):
    q.charge("playlistItems.insert", 200)  # exactly the daily cap
    assert q.remaining() == 0
    with pytest.raises(QuotaExceeded) as e:
        q.charge("playlistItems.insert")
    assert "resets at" in str(e.value)
    assert "publish links" in str(e.value)  # points at the free alternative


def test_unknown_method_is_loud(q):
    with pytest.raises(KeyError):
        q.cost("playlists.teleport")
