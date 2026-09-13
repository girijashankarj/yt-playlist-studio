---
description: Fetch a playlist, tag it, chunk it into moods and export everything
argument-hint: <playlist-url-or-id> [output-dir]
---

Run the full pipeline for the playlist: **$1**

Output directory: `${2:-out}`

1. `ytps fetch "$1" -o ${2:-out}/library.csv` — no credentials needed for public or
   unlisted playlists. Report the song count, and if YouTube states a higher count,
   report the gap as unavailable videos rather than glossing over it.
2. `ytps tag ${2:-out}/library.csv` — then show the fill rate and remind the user
   these tags are inferred, not official.
3. `ytps chunk ${2:-out}/library.csv -o ${2:-out}/moods` — show the per-mood counts
   and confirm coverage is complete.
4. `ytps export ${2:-out}/moods --format xlsx,html` — report where the files landed.

Finally, tell the user their two publishing options and which one suits this library:
`ytps publish links` (free, instant, manual clicks) or `ytps publish api --dry-run`
(automated but capped at ~200 song-adds per day). Price the API route with the dry run
before recommending it.
