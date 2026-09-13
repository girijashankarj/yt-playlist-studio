# Quota

The YouTube Data API bills every call in "units" against a daily allowance.

| Call | Units |
|---|---|
| `playlists.list`, `playlistItems.list`, `videos.list` | 1 |
| `playlists.insert` | 50 |
| `playlistItems.insert` | **50** |
| `playlistItems.delete` | 50 |
| `search.list` | 100 |

Default allowance: **10,000 units/day**, resetting at **midnight US/Pacific**.

## What that means in practice

- Reading a 700-song playlist: ~15 units. Free, effectively.
- Adding a song to a playlist: 50 units → **~200 song-adds per day**.
- A 3,000-song library: ~150,000 units → **about 17 days** of daily runs.

This is why `publish links` exists. It uses YouTube's `watch_videos` endpoint in your
browser, costs zero units, and can build a large library in an afternoon.

## How this tool handles it

- `ytps quota` shows what is left today and how many adds that buys.
- `ytps publish api --dry-run` (the default) prices the job and makes **zero** calls.
- The writer charges the ledger *before* each call and stops cleanly at the cap, saving
  a resume file. Re-run after the reset and it continues where it stopped.
- Already-present videos are skipped, so resuming never double-adds.

The ledger lives in `.ytps/quota.json`. It tracks what *this tool* spent — if you use the
same Google project elsewhere, your real remaining quota may be lower.

## Raising the ceiling

Google accepts [quota increase requests](https://support.google.com/youtube/contact/yt_api_form)
for the YouTube Data API. Expect to explain your use case; approval is not guaranteed.
