import pytest

from ytps.models import Song
from ytps.publish.api_writer import PublishState, estimate
from ytps.publish.bulk_links import MAX_IDS, build_links, chunk_ids


def songs(n):
    return [Song(position=i, video_id=f"{i:011d}", title=f"t{i}", duration="3:00")
            for i in range(1, n + 1)]


def test_links_never_exceed_youtube_limit():
    for n in (1, 50, 51, 120, 715):
        for block in build_links(songs(n)):
            ids = block["url"].split("video_ids=")[1].split(",")
            assert len(ids) <= MAX_IDS


def test_links_reproduce_exact_order_with_nothing_lost():
    s = songs(715)
    rebuilt = []
    for block in build_links(s):
        rebuilt += block["url"].split("video_ids=")[1].split(",")
    assert rebuilt == [x.video_id for x in s]


def test_first_block_creates_rest_append():
    blocks = build_links(songs(120))
    assert blocks[0]["action"].startswith("Save as new")
    assert all(b["action"].startswith("Add all") for b in blocks[1:])


def test_positions_are_contiguous():
    assert [b["positions"] for b in build_links(songs(120))] == ["1-50", "51-100", "101-120"]


def test_oversize_chunk_rejected():
    with pytest.raises(ValueError):
        chunk_ids(["a"], 51)


def test_estimate_prices_the_real_job():
    est = estimate(songs(3341))
    assert est["units"] == 3341 * 50 + 50
    assert est["days_at_default_quota"] > 16


def test_publish_state_roundtrip(tmp_path):
    st = PublishState.load(tmp_path / "s.json", "Gym")
    st.playlist_id = "PLxyz"
    st.added = ["a" * 11, "b" * 11]
    st.save()
    again = PublishState.load(tmp_path / "s.json", "Gym")
    assert again.playlist_id == "PLxyz" and len(again.added) == 2


def test_publish_state_survives_corruption(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json")
    assert PublishState.load(p, "Gym").added == []
