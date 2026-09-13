---
name: mood-tagging
description: Tag songs with language, genre, sub-genre and mood category for chunking. Use when tagging a fetched playlist, filling blank tag columns, or deciding which mood a song belongs to.
---

# Mood tagging

YouTube gives you a title and an uploading channel. It does not give you a singer, a
genre, or a mood. Everything here is inference — so the first rule is: **a blank field
beats a wrong one.** A bad tag silently corrupts every mood playlist downstream.

## Controlled vocabulary

Stay inside these values so filters and rules keep working.

**Category (the listening mood)** — `Party`, `Workout`, `Smooth`, `Love`, `Old`,
`Focus`, `Remix`, `Devotional`

**Sub-Genre** — `Dance`, `Anthem`, `Synth`, `Rap`, `Melancholy`, `Romantic`,
`Acoustic`, `Ballad`, `Ambient`, `Classical-Fusion`, `Cover`

**Genre** — pick the vocabulary that fits the library:
- South-Asian: `Bollywood`, `Punjabi Pop`, `Regional Film`, `Sufi-Folk`, `Devotional`,
  `Indie / Alt`, `Hip-Hop / Rap`, `Pop`, `Classical`
- Western: `Pop`, `Rock`, `Hip-Hop / Rap`, `R&B / Soul`, `Electronic / EDM`, `Phonk`,
  `Indie / Alt`, `Soundtrack`, `Country`, `Latin / Reggae`, `Jazz / Blues`, `Metal`

**Language** — the language *sung*, not the channel's country. Use `Instrumental` for
tracks with no vocals and `Mixed` for genuine multi-language tracks.

## Method

1. **Language** — script in the title is the strongest signal, then the channel name
   (`Saregama Malayalam` → Malayalam). "BGM", "OST", "Theme", "NCS" → `Instrumental`.
2. **Artist** — `Artist - Song (Official Video)` is the one reliable convention. Beware
   `Song - Video Song | Movie`, where the text before the dash is the *song*.
   `X - Topic` channels are auto-generated: the artist is `X`.
3. **Genre** then **Sub-Genre** — genre from the musical style, sub-genre from how it
   *feels* to listen to.
4. **Category** — ask "when would someone put this on?" That question, not the genre,
   is what makes the mood playlists useful.

## Judgement calls

- A song can be `Love` and `Smooth`; pick the dominant use, the rules handle overlap.
- Remixes, lofi edits and sped-up versions are `Remix` regardless of the original.
- `Old` means the track is a throwback, not that the upload is old — a 2024 upload of a
  1975 song is `Old`.
- Album jukeboxes and BGM compilations usually belong nowhere; let them fall to `Misc`.

## Always say this

When reporting tagging results, state the fill rate per field and remind the user the
tags are derived. Never present them as YouTube metadata.
