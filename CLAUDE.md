# yt-playlist-studio — working notes for Claude Code

## What this is

A CLI + MCP server that reads a YouTube playlist, infers tags, slices it into mood
playlists, and helps publish them back to YouTube.

Pipeline: **fetch → tag → chunk → export → publish**

## Hard rules

1. **Never commit secrets.** `.env`, `.tokens/`, `.ytps/` are gitignored. Before any
   commit touching config, run `git check-ignore -v .env .tokens/`. Never paste a real
   key, token or client secret into source, tests, docs or commit messages.
2. **Never ask the user for a Google password.** OAuth runs `flow.run_local_server()`
   in the user's own browser. If a flow fails, fix the client config — never work
   around it by requesting credentials.
3. **Writes are opt-in.** `publish api` defaults to `--dry-run`; the MCP `publish_api`
   tool defaults to `confirm=false`. Never flip those defaults, and never publish to a
   user's account without an explicit, current confirmation.
4. **Respect the quota ceiling.** Every write costs 50 units against a 10,000/day
   allowance — about 200 song-adds a day. Always price a job with `estimate()` before
   running it, and suggest `publish links` when the job exceeds the day's remaining budget.
5. **Don't overstate the tags.** Language/genre/mood are *inferred* from titles and
   channel names. Say so in any user-facing output. Prefer leaving a field blank over
   guessing.

## Layout

```
src/ytps/
  config.py     Config.load() + resolve_tier(op, visibility) -> the auth decision
  auth.py       OAuth flow, token cache, build_service()
  quota.py      cost table, daily ledger, estimate/check/charge
  models.py     Song, Playlist + duration/views parsing
  sources/      scrape.py (keyless InnerTube) | api.py (Data API)
  fetch.py      one entry point; picks the tier
  tagging.py    heuristics + optional LLM hook
  chunking.py   RulePack/Mode/Chunk - rules live in rules/*.yml, not here
  writers/      xlsx.py, csv_out.py, html_console.py
  publish/      bulk_links.py (free) | api_writer.py (quota-bound, resumable)
  cli.py mcp.py
```

## Conventions

- Python ≥3.10, `from __future__ import annotations`, type hints on public functions.
- `ruff check .` and `pytest` must pass before any commit.
- **No network in tests.** Use `tests/fixtures/*.json`; mock the API service object.
- Errors subclass `YtpsError` and must name the fix, not just the fault — see
  `CredentialsRequired` and `QuotaExceeded` for the tone to match.
- New moods go in `rules/*.yml`. Only add Python if a rule needs a genuinely new
  *field*; then extend `chunking.FIELDS` and document it in `docs/rules.md`.

## Adding a mood

Edit `rules/moods.default.yml`, run `ytps rules` to confirm it parses, then
`ytps chunk <csv>` and check the count is sane. No code change needed.

## Gotchas

- The keyless reader rides YouTube's internal InnerTube endpoint. When YouTube
  reshuffles its response, fix `sources/scrape.py::_parse_lockup` — it searches by
  key (`find_key`) rather than a fixed path precisely so this stays cheap.
- Playlists report a video count that includes deleted/private entries you cannot
  read. `Playlist.hidden_count` is that gap; surface it, don't hide it.
- `coverage()` counts unique video ids — a playlist may legitimately list the same
  video twice.
