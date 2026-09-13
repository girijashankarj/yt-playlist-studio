import pytest

from ytps.models import Playlist, Song, duration_to_seconds, parse_views, seconds_to_duration


@pytest.mark.parametrize(
    "text,secs", [("0:45", 45), ("3:30", 210), ("10:00", 600), ("1:02:03", 3723)]
)
def test_duration_roundtrip(text, secs):
    assert duration_to_seconds(text) == secs
    assert duration_to_seconds(seconds_to_duration(secs)) == secs


def test_duration_rejects_garbage():
    with pytest.raises(ValueError):
        duration_to_seconds("soon")


@pytest.mark.parametrize(
    "text,n",
    [("242m views", 242_000_000), ("16k views", 16_000), ("137 views", 137),
     ("1.4m views", 1_400_000), ("1 view", 1), ("", None), ("lots", None)],
)
def test_parse_views(text, n):
    assert parse_views(text) == n


def test_song_derives_seconds_and_url():
    s = Song(position=1, video_id="abcdefghijk", title="A - B", duration="2:30")
    assert s.duration_sec == 150
    assert s.url.endswith("watch?v=abcdefghijk")
    assert s.song_name == "A - B"


def test_hidden_count_is_the_gap_youtube_will_not_show():
    pl = Playlist("PL1", stated_count=596,
                  songs=[Song(position=i, video_id=f"{i:011d}", title="t") for i in range(543)])
    assert pl.hidden_count == 53


def test_hidden_count_never_negative():
    pl = Playlist("PL1", stated_count=1,
                  songs=[Song(position=i, video_id=f"{i:011d}", title="t") for i in range(5)])
    assert pl.hidden_count == 0
