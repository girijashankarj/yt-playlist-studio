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

## Planning a large job

Because the cap is per day, a big library is a scheduling problem. Price it first:

```bash
ytps publish api out/moods/GH-ToWork.csv --dry-run
```

Worked example — 29 playlists, 3,341 songs (the library this tool was built on):

| | |
|---|---|
| Creating 29 playlists | 29 × 50 = 1,450 units |
| Adding 3,341 songs | 3,341 × 50 = 167,050 units |
| **Total** | **168,500 units ≈ 16 days** |

### What actually fits in one day

10,000 units buys one of:

- **200 song-adds** into an existing playlist, or
- ~10 small playlists created *and* filled (e.g. 6 + 7 + 12 + 20 + 20 + 21 + 22 + 28 songs ≈ 9,400 units).

Any playlist over **199 songs cannot be completed in a single day**, no matter what — it
will span two or more runs. That is fine: the writer saves a resume file and skips what
is already there, so you just run it again after the reset.

### The hybrid approach

Splitting by size is usually fastest:

| Playlist size | Best path | Why |
|---|---|---|
| Under ~180 songs | `publish api` | Completes in one run, fully automated |
| Over ~180 songs | `publish links` | One browser sitting instead of days of waiting |

For the 29-playlist example this turns **16 days into about 3 days plus one 45-minute
sitting** — the API handles the ~18 smaller playlists unattended while you click
through the 11 big ones.

> Remember the interaction with auth: at ~200 adds/day, a job over roughly 1,400 songs
> runs longer than a **Testing**-status refresh token survives. Set the consent screen to
> **In production** before starting — see [auth-setup.md](auth-setup.md).

## Raising the ceiling

Google accepts [quota increase requests](https://support.google.com/youtube/contact/yt_api_form)
for the YouTube Data API. Expect to explain your use case; approval is not guaranteed.
