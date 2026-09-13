from ytps.models import Song
from ytps.tagging import clean_song_name, guess_language, split_artist, tag_coverage, tag_songs


def s(title, channel="", duration="3:30"):
    return Song(position=1, video_id="a" * 11, title=title, channel=channel, duration=duration)


def test_artist_dash_convention():
    assert split_artist("Guru Randhawa - SIRRA ( Official Video )") == "Guru Randhawa"
    assert split_artist("KORDHELL - MURDER IN MY MIND") == "KORDHELL"


def test_does_not_mistake_a_song_title_for_an_artist():
    # 'X - Video Song | Movie' names the song before the dash, not the artist
    assert split_artist("Kiliye Kiliye - Video Song | Lokah") == ""
    assert split_artist("Aayat - Lyrical Video | Bajirao") == ""


def test_clean_strips_promo_cruft_and_artist_prefix():
    assert clean_song_name("Guru Randhawa - SIRRA ( Official Video )", "Guru Randhawa") == "SIRRA"
    assert clean_song_name("Track | Movie | Composer") == "Track"


def test_language_from_script():
    assert guess_language(s("रामा रामा रटते रटते")) == "Hindi"
    assert guess_language(s("ഉയിരിൽ തൊടും Uyiril Thodum")) == "Malayalam"


def test_language_from_channel_beats_nothing():
    assert guess_language(s("Some Song", "Saregama Malayalam")) == "Malayalam"


def test_instrumental_detected_from_title():
    assert guess_language(s("Mangalavaram BGM")) == "Instrumental"


def test_topic_channels_are_cleaned_up():
    song = s("Aahatein", "Agnee - Topic")
    tag_songs([song])
    assert song.artist == "Agnee"


def test_tagger_leaves_unknowns_blank_rather_than_guessing():
    song = s("Untitled 4", "Some Channel")
    tag_songs([song])
    assert song.genre == "" and song.category == ""


def test_existing_tags_are_preserved_unless_overwrite():
    song = s("Lorde - Royals")
    song.category = "Love"
    tag_songs([song])
    assert song.category == "Love", "an existing tag must survive a re-tag"
    tag_songs([song], overwrite=True)
    assert song.song_name == "Royals"


def test_single_character_artist_is_not_matched():
    # the >=2 char guard is deliberate: 'A - B' is far more often a title than an artist
    assert split_artist("A - B") == ""


def test_coverage_reports_percentages():
    songs = [s("Lorde - Royals"), s("Djo - End of Beginning")]
    tag_songs(songs)
    cov = tag_coverage(songs)
    assert set(cov) == {"artist", "language", "genre", "sub_genre", "category"}
    assert cov["artist"] == 100.0
