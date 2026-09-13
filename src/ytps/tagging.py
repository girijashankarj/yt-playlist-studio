"""Derive Language / Genre / Sub-Genre / Category from what YouTube gives us.

Be clear-eyed about this: YouTube exposes an uploading channel and a title, not a
singer, a mood, or a genre. Everything here is *inferred*. The heuristics below are
deliberately conservative - they leave a field blank rather than guess badly, because
a wrong tag silently poisons every mood playlist downstream.

For better tags, plug in an LLM via `set_llm_provider()` and run `ytps tag --llm`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from .models import Song

# --- language --------------------------------------------------------------
SCRIPTS = [
    ("Hindi", r"[ऀ-ॿ]"),      # Devanagari - also Marathi, disambiguated below
    ("Malayalam", r"[ഀ-ൿ]"),
    ("Tamil", r"[஀-௿]"),
    ("Telugu", r"[ఀ-౿]"),
    ("Kannada", r"[ಀ-೿]"),
    ("Bengali", r"[ঀ-৿]"),
    ("Gujarati", r"[઀-૿]"),
    ("Punjabi", r"[਀-੿]"),
    ("Urdu", r"[؀-ۿ]"),
    ("Korean", r"[가-힯]"),
    ("Japanese", r"[぀-ヿ]"),
]
CHANNEL_LANG = {
    "Malayalam": ["malayalam", "muzik247", "manorama"],
    "Telugu": ["telugu", "aditya music", "mango music"],
    "Tamil": ["tamil", "think music", "sony music south"],
    "Marathi": ["marathi"],
    "Punjabi": ["punjabi", "speed records", "geet mp3", "desi melodies"],
}
INSTRUMENTAL_HINTS = ["instrumental", "bgm", "theme", "(ost)", "soundtrack", "no copyright", "ncs"]


def guess_language(s: Song) -> str:
    text, chan = s.title, (s.channel or "").lower()
    for lang, keys in CHANNEL_LANG.items():
        if any(k in chan for k in keys):
            return lang
    for lang, pat in SCRIPTS:
        if re.search(pat, text):
            return lang
    if any(h in text.lower() for h in INSTRUMENTAL_HINTS):
        return "Instrumental"
    return ""


# --- genre / sub-genre / category ------------------------------------------
GENRE_HINTS = {
    "Phonk": ["phonk", "slowed", "drift", "sped up"],
    "Hip-Hop / Rap": ["rap", "hip hop", "hip-hop", "cypher", "freestyle", "diss"],
    "Electronic / EDM": ["remix", "edm", "house", "dubstep", "bass boosted", "dj "],
    "Devotional": ["bhajan", "aarti", "stotra", "mantra", "shloka", "kirtan", "sankeertan"],
    "Soundtrack": ["ost", "original soundtrack", "score", "theme"],
    "Rock": ["rock", "metal", "acoustic session"],
}
SUB_HINTS = {
    "Remix": ["remix", "mashup", "sped up", "slowed", "lofi", "lo-fi"],
    "Acoustic": ["acoustic", "unplugged", "cover", "stripped"],
    "Dance": ["dance", "party", "club"],
    "Rap": ["rap", "hip hop", "cypher"],
}
CATEGORY_HINTS = {
    "Remix": ["remix", "mashup", "sped up", "slowed", "lofi", "lo-fi"],
    "Devotional": ["bhajan", "aarti", "stotra", "mantra", "kirtan"],
    "Love": ["love song", "romantic", "pyaar", "ishq", "mohabbat"],
}


def _first_hint(text: str, table: dict[str, list[str]]) -> str:
    low = text.lower()
    for label, keys in table.items():
        if any(k in low for k in keys):
            return label
    return ""


CRUFT_AFTER_DASH = re.compile(
    r"^(video|full|official|lyric|lyrics|lyrical|audio|song|topic|4k|hd)\b", re.I
)


def clean_song_name(title: str, drop_artist: str = "") -> str:
    """Strip the promo cruft YouTube titles are stuffed with."""
    t = re.split(r"\s*[|(\[]", title, maxsplit=1)[0]
    if drop_artist and t.lower().startswith(drop_artist.lower()):
        t = t[len(drop_artist):].lstrip(" -–—:")
    t = re.sub(
        r"\b(official|full|video|song|lyrical|lyric|audio|music|4k|hd|视频)\b", "", t, flags=re.I
    )
    t = re.sub(r"\s{2,}", " ", t).strip(" -–—:·")
    return t or title.strip()


def split_artist(title: str) -> str:
    """'Artist - Song (Official Video)' is the one reliable convention.

    Guard against the common false positive 'Song Name - Video Song | Movie',
    where the text before the dash is the song, not the artist.
    """
    m = re.match(r"^\s*([^|\[(]{2,40}?)\s+[-–]\s+(.*)$", title)
    if not m:
        return ""
    if CRUFT_AFTER_DASH.match(m.group(2).strip()):
        return ""
    return m.group(1).strip()


_llm: Callable[[list[Song]], list[dict]] | None = None


def set_llm_provider(fn: Callable[[list[Song]], list[dict]]) -> None:
    """Register a callable taking Songs and returning per-song tag dicts.

    Keeps the package dependency-free: bring whichever model you like.
    """
    global _llm
    _llm = fn


def tag_songs(songs: Iterable[Song], use_llm: bool = False, overwrite: bool = False) -> list[Song]:
    songs = list(songs)
    for s in songs:
        artist = split_artist(s.title) or (
            s.channel.replace(" - Topic", "") if " - Topic" in s.channel else s.channel
        )
        if overwrite or not s.song_name or s.song_name == s.title:
            s.song_name = clean_song_name(s.title, drop_artist=split_artist(s.title))
        if overwrite or not s.artist:
            s.artist = artist
        if overwrite or not s.language:
            s.language = guess_language(s)
        if overwrite or not s.genre:
            s.genre = _first_hint(f"{s.title} {s.channel}", GENRE_HINTS)
        if overwrite or not s.sub_genre:
            s.sub_genre = _first_hint(s.title, SUB_HINTS)
        if overwrite or not s.category:
            s.category = _first_hint(s.title, CATEGORY_HINTS)

    if use_llm:
        if _llm is None:
            raise RuntimeError(
                "No LLM provider registered. Call tagging.set_llm_provider(fn) first, "
                "or run without --llm to use heuristics only."
            )
        for s, tags in zip(songs, _llm(songs), strict=False):
            for k, v in (tags or {}).items():
                if v and hasattr(s, k):
                    setattr(s, k, v)
    return songs


def tag_coverage(songs: Iterable[Song]) -> dict[str, float]:
    """What fraction of each tag field got filled - honesty metric for the user."""
    songs = list(songs)
    n = len(songs) or 1
    return {
        f: round(sum(1 for s in songs if getattr(s, f)) / n * 100, 1)
        for f in ("artist", "language", "genre", "sub_genre", "category")
    }
