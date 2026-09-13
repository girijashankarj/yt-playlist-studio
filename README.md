# yt-playlist-studio

**Your playlist is one long list. This turns it into the playlists you actually reach for** — a workout set, a commute set, something for the drive — then helps you put them back on YouTube.

Reading a public playlist needs **no API key, no OAuth, no quota, no Google Cloud project**. Credentials only enter the picture when you read something private or write to your account.

```bash
pip install yt-playlist-studio

# no credentials needed for this
ytps fetch "https://youtube.com/playlist?list=PL..." -o out/library.csv
ytps tag    out/library.csv
ytps chunk  out/library.csv --rules rules/moods.default.yml -o out/moods/
ytps export out/moods/ --format xlsx,html
```

You get a spreadsheet per mood and an HTML console with one-click import links.

---

## Why it exists

Large playlists rot. A 700-song list is unusable by the time you want *something for the gym* — you scroll, give up, and play the same six songs. Splitting by mood is the fix, but doing it by hand for hundreds of songs is the reason nobody does it.

## What it does

| | |
|---|---|
| **Fetch** | Read any public or unlisted playlist with zero credentials. Private lists via OAuth. |
| **Tag** | Infer language, genre, sub-genre and mood category per song. |
| **Chunk** | Slice into mood playlists using declarative YAML rules. Songs may appear in several. |
| **Export** | XLSX (formatted, filterable), CSV, M3U, or an HTML build console. |
| **Publish** | Create the playlists on YouTube — via the API, or via free browser import links. |
| **MCP** | Every operation is also an MCP tool, so Claude Code can drive the whole thing. |

## Credentials: only when you actually need them

This is the part most tools get wrong. What you need depends on **what you are doing**:

| Operation | Playlist | You need |
|---|---|---|
| Read | public / unlisted | **nothing** |
| Read | private | OAuth (`youtube.readonly`) |
| Create / edit / delete | any | OAuth (`youtube.force-ssl`) |

> **Tip:** setting a playlist to **Unlisted** rather than Private keeps it out of search while staying readable with no credentials at all. Easiest path if you just want to share a list with this tool.

Everything lives in `.env` (copy `.env.example`, then `ytps auth check` to confirm your paste without revealing it). You bring your own Google Cloud project — this repo ships no keys. See [docs/auth-setup.md](docs/auth-setup.md).

> **Already have a Google Cloud project?** Reuse it — you only need a client of type *Desktop app*, or set `YT_OAUTH_PORT` to reuse a *Web application* one. [Details](docs/auth-setup.md).

> **If you plan to publish, set your OAuth consent screen to "In production" first.** Apps left in *Testing* get a refresh token that expires after **7 days** — long enough to break any sizeable publish job halfway through. [Details](docs/auth-setup.md).

## The quota reality

If you publish via the official API, know this before you start:

| | |
|---|---|
| Daily allowance | **10,000 units** (resets midnight US/Pacific) |
| Adding one song | **50 units** |
| **Songs you can add per day** | **~200** |
| Reading a whole playlist | ~1 unit per 50 songs |

Reading is basically free. **Writing is the bottleneck** — a 3,000-song library would take about 17 days of daily API runs.

So there are two publish paths, and neither is a second-class citizen:

```bash
ytps publish api   out/moods/Gym.csv --dry-run   # prices the job, makes zero calls
ytps publish links out/moods/                    # free, instant, no OAuth
```

`publish queue` walks a whole folder of playlists, publishes what the day's quota allows and resumes tomorrow — schedule it and a multi-day job runs itself. `publish api` is quota-aware and resumable — it stops cleanly at the cap and tells you when it can continue. `publish links` generates YouTube import links (50 videos each) plus an HTML console; you click through and save them yourself. For a big library, that is an hour instead of a fortnight.

## Writing your own moods

Rules are YAML, not code. Add a mood, open a PR:

```yaml
- name: RainyDay
  description: Slow, wistful, good with weather
  any_of:
    category: [Smooth, Love]
    sub_genre: [Melancholy, Acoustic]
  none_of:
    genre: [Phonk, Metal]
  min_sec: 120
  max_sec: 420
```

Fields: `language`, `genre`, `sub_genre`, `category`, `artist`, `channel`. See [docs/rules.md](docs/rules.md).

## Use it from Claude Code

`.mcp.json` registers the MCP server, exposing `playlist_fetch`, `playlist_tag`, `playlist_chunk`, `playlist_export`, `publish_links`, `publish_api` and `quota_status`. Write tools refuse to run without explicit confirmation, and `publish_api` defaults to a dry run.

## Honest limitations

- **The built-in tagger is weak on its own, and says so.** YouTube gives a title and a channel — not a singer, a genre or a mood. On a real 543-song playlist the heuristics filled `artist` for 100% of rows but `genre`/`category` for only ~8%, which pushed most songs into the `Misc` catch-all. `ytps tag` and `ytps chunk` both warn you when this happens. **Good mood tagging needs judgement, not regexes** — register an LLM provider and run `ytps tag --llm`, or fill the tag columns yourself. The heuristics are a starting point, not the product.
- **The keyless reader uses an internal YouTube endpoint.** It can break when YouTube changes its response shape; `--via api` is the supported fallback.
- **Hidden videos cannot be recovered.** Deleted and private entries are counted by YouTube but not shown, so a "757 video" playlist may read as 715.
- **This tool will never ask for your Google password.** OAuth happens in your own browser.

## Install

```bash
pip install yt-playlist-studio          # core
pip install "yt-playlist-studio[api]"   # + official Data API
pip install "yt-playlist-studio[mcp]"   # + MCP server
```

## Contributing

New mood rules, better tagging heuristics and language support are the most useful contributions. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE). Not affiliated with or endorsed by YouTube or Google.
