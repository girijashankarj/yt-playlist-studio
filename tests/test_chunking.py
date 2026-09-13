from pathlib import Path

import pytest

from ytps.chunking import Chunk, Mode, RulePack, chunk, coverage
from ytps.cli import _load_songs
from ytps.errors import RuleError
from ytps.models import Playlist, Song

RULES = Path(__file__).resolve().parents[1] / "rules" / "moods.default.yml"
FIXTURE = Path(__file__).parent / "fixtures" / "sample_tagged.csv"


@pytest.fixture
def pl():
    return Playlist(playlist_id="test", songs=_load_songs(FIXTURE))


def test_default_pack_parses():
    pack = RulePack.load(RULES)
    assert {m.name for m in pack.modes} >= {"ToWork", "Gym", "Love", "Focus"}
    assert pack.catch_all == "Misc"


def test_unknown_field_is_rejected_with_a_helpful_message():
    m = Mode(name="Bad", any_of={"tempo": ["fast"]})
    with pytest.raises(RuleError) as e:
        m.validate()
    assert "tempo" in str(e.value) and "Valid fields" in str(e.value)


def test_bad_match_mode_rejected():
    with pytest.raises(RuleError):
        Mode(name="Bad", match="sometimes").validate()


def test_duration_window_excludes_clips_and_jukeboxes():
    m = Mode(name="M", min_sec=120, max_sec=420)
    short = Song(position=1, video_id="a" * 11, title="t", duration="0:45")
    long = Song(position=2, video_id="b" * 11, title="t", duration="15:00")
    ok = Song(position=3, video_id="c" * 11, title="t", duration="3:30")
    assert not m.matches(short) and not m.matches(long) and m.matches(ok)


def test_none_of_excludes():
    m = Mode(name="M", any_of={"category": ["Party"]}, none_of={"genre": ["Phonk"]})
    party_phonk = Song(position=1, video_id="a" * 11, title="t", duration="3:00",
                       category="Party", genre="Phonk")
    party_pop = Song(position=2, video_id="b" * 11, title="t", duration="3:00",
                     category="Party", genre="Pop")
    assert not m.matches(party_phonk) and m.matches(party_pop)


def test_match_any_ors_the_groups():
    any_m = Mode(name="A", match="any", any_of={"category": ["Workout"], "genre": ["Phonk"]})
    all_m = Mode(name="B", match="all", any_of={"category": ["Workout"], "genre": ["Phonk"]})
    s = Song(position=1, video_id="a" * 11, title="t", duration="3:00",
             category="Workout", genre="Pop")
    assert any_m.matches(s)
    assert not all_m.matches(s)


def test_every_song_lands_somewhere(pl):
    chunks = chunk(pl, RulePack.load(RULES))
    cov = coverage(pl, chunks)
    assert cov["complete"], f"orphans: {cov['orphans'][:5]}"


def test_no_empty_playlists_are_written(pl):
    assert all(len(c.songs) > 0 for c in chunk(pl, RulePack.load(RULES)))


def test_songs_repeat_across_moods_on_purpose(pl):
    chunks = chunk(pl, RulePack.load(RULES))
    seen = [s.video_id for c in chunks for s in c.songs]
    assert len(seen) > len(set(seen))


def test_ordered_by_views_descending(pl):
    for c in chunk(pl, RulePack.load(RULES), order_by="views"):
        views = [s.views or 0 for s in c.songs]
        assert views == sorted(views, reverse=True)


def test_coverage_counts_unique_videos_not_rows():
    s = Song(position=1, video_id="dup01234567", title="t", duration="3:00", category="Party")
    pl = Playlist("x", songs=[s, s])
    chunks = [Chunk("Party", "", [s])]
    cov = coverage(pl, chunks)
    assert cov["rows"] == 2 and cov["total"] == 1 and cov["duplicate_rows"] == 1
