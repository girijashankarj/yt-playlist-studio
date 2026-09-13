"""The dispatcher runs unattended across days, so resume correctness is critical."""

import csv
from pathlib import Path

import pytest
from conftest import FakeService

from ytps.models import Song
from ytps.publish.queue import QueueState, discover, run_queue
from ytps.quota import Quota


def make_csv(d: Path, name: str, n: int) -> Path:
    p = d / f"{name}.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["position", "video_id", "title", "duration"])
        w.writeheader()
        for i in range(1, n + 1):
            w.writerow({"position": i, "video_id": f"{name[:3]}{i:08d}"[:11],
                        "title": f"t{i}", "duration": "3:00"})
    return p


def loader(path: Path):
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    return [Song(position=int(r["position"]), video_id=r["video_id"], title=r["title"],
                 duration=r["duration"]) for r in rows]


@pytest.fixture
def workdir(tmp_path):
    d = tmp_path / "moods"
    d.mkdir()
    make_csv(d, "Small", 2)
    make_csv(d, "Medium", 5)
    make_csv(d, "Large", 10)
    return d


def test_discover_counts_every_playlist(workdir, tmp_path):
    st = QueueState.load(tmp_path / "q.json")
    discover(workdir, st)
    assert st.summary()["playlists_total"] == 3
    assert st.summary()["songs_total"] == 17


def test_smallest_first_finishes_the_most_playlists(workdir, tmp_path):
    quota = Quota(tmp_path / "quota.json", daily=10_000)
    out = run_queue(workdir, FakeService(), quota, tmp_path, load_songs=loader)
    assert out["all_done"]
    assert [r["playlist"] for r in out["ran"]] == ["Small", "Medium", "Large"]


def test_stops_at_quota_and_reports_how_to_resume(workdir, tmp_path):
    # 50 create + 2 adds = 150 for Small; then Medium creates (50) and adds 1 (50) = 250
    quota = Quota(tmp_path / "quota.json", daily=250)
    out = run_queue(workdir, FakeService(), quota, tmp_path, load_songs=loader)
    assert not out["all_done"]
    assert out["stopped_because"]
    assert out["resume_after"]
    assert out["songs_remaining"] > 0


def test_resuming_tomorrow_continues_and_never_double_adds(workdir, tmp_path):
    day1 = Quota(tmp_path / "q1.json", daily=250)
    first = run_queue(workdir, FakeService(), day1, tmp_path, load_songs=loader)
    added_day1 = first["songs_added"]
    assert added_day1 > 0

    day2 = Quota(tmp_path / "q2.json", daily=10_000)
    svc = FakeService()
    second = run_queue(workdir, svc, day2, tmp_path, load_songs=loader)
    assert second["all_done"]
    # nothing published twice
    assert len(svc.inserted) == len(set(svc.inserted))
    assert second["songs_added"] == 17


def test_state_survives_reload(workdir, tmp_path):
    quota = Quota(tmp_path / "quota.json", daily=10_000)
    run_queue(workdir, FakeService(), quota, tmp_path, load_songs=loader)
    reloaded = QueueState.load(tmp_path / "queue.json")
    assert reloaded.summary()["playlists_done"] == 3
    assert all(e.url for e in reloaded.entries.values())


def test_rerun_after_completion_is_a_no_op(workdir, tmp_path):
    quota = Quota(tmp_path / "quota.json", daily=10_000)
    run_queue(workdir, FakeService(), quota, tmp_path, load_songs=loader)
    used = quota.used()
    again = run_queue(workdir, FakeService(), quota, tmp_path, load_songs=loader)
    assert again["all_done"] and again["ran"] == []
    assert quota.used() == used, "a finished queue must not spend more quota"


def test_googles_quota_error_stops_the_queue_cleanly(workdir, tmp_path):
    """Google's 403 is authoritative even when our ledger still looks healthy."""
    from tests_helpers import QuotaBlockedService  # noqa: F401

    from ytps.publish.api_writer import is_quota_error

    quota = Quota(tmp_path / "quota.json", daily=10_000)
    svc = QuotaBlockedService(ok_inserts=1)
    out = run_queue(workdir, svc, quota, tmp_path, load_songs=loader)
    assert not out["all_done"]
    assert "quota" in out["stopped_because"].lower()
    assert quota.remaining() == 0, "ledger must sync to Google's verdict"
    assert is_quota_error(svc.raised)


def test_discover_adopts_playlists_a_crash_left_behind(workdir, tmp_path):
    """A crash can create the playlist before the queue records it - don't lose it."""
    import json

    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "Large.json").write_text(json.dumps(
        {"playlist_name": "Large", "playlist_id": "PLcrash123",
         "added": ["Lar00000001", "Lar00000002"]}))

    st = QueueState.load(tmp_path / "q.json")
    discover(workdir, st, tmp_path)
    e = st.entries["Large"]
    assert e.playlist_id == "PLcrash123"
    assert e.added == 2 and e.status == "partial"
    assert e.url.endswith("PLcrash123")


def test_reconcile_never_downgrades_a_finished_playlist(workdir, tmp_path):
    import json

    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "Small.json").write_text(json.dumps(
        {"playlist_name": "Small", "playlist_id": "PLx", "added": ["only-one-x"]}))
    st = QueueState.load(tmp_path / "q.json")
    discover(workdir, st)
    st.entries["Small"].status = "done"
    st.entries["Small"].added = 2
    discover(workdir, st, tmp_path)
    assert st.entries["Small"].status == "done" and st.entries["Small"].added == 2
