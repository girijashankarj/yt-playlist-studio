# Contributing

Thanks for helping out. The most useful contributions, roughly in order:

1. **New mood rules** — add a block to `rules/moods.default.yml` or ship a new pack
   in `rules/`. No Python needed. Include the counts you get on a real playlist.
2. **Better tagging heuristics** — especially non-English languages. `tagging.py` is
   deliberately conservative; a heuristic that guesses wrong is worse than one that
   returns blank.
3. **Bug reports** with the playlist URL (if public) and the full command you ran.

## Setup

```bash
git clone https://github.com/girijashankarj/yt-playlist-studio
cd yt-playlist-studio
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check .
```

## Ground rules

- **Never commit a real API key, token or client secret.** `.env` and `.tokens/` are
  gitignored; keep it that way.
- **Tests must not hit the network.** Add a fixture under `tests/fixtures/`.
- **Don't change the write defaults.** `publish api` is dry-run by default and the
  MCP tool needs `confirm=true`. Those defaults protect people's accounts.
- Run `ruff check .` before opening a PR.

## Testing against a real playlist

Use a public playlist you own. The keyless reader needs no credentials:

```bash
ytps fetch "https://youtube.com/playlist?list=..." -o /tmp/t.csv
ytps tag /tmp/t.csv && ytps chunk /tmp/t.csv -o /tmp/moods
```

For write paths, create a throwaway playlist and test with `--privacy private`.
