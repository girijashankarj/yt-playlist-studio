# Writing mood rules

Rules are YAML. Adding a mood needs no Python.

## Shape

```yaml
- name: RainyDay                 # required; becomes the playlist name
  description: Slow and wistful  # shown in exports and the build console
  match: all                     # 'all' (default) or 'any' - see below
  any_of:                        # a row matches a field if its value is listed
    category: [Smooth, Love]
    sub_genre: [Melancholy, Acoustic]
  none_of:                       # a row is excluded if ANY of these hit
    genre: [Phonk, Metal]
  min_sec: 120                   # duration window, in seconds
  max_sec: 420
```

## `match: all` vs `match: any`

With **`all`** (default), every field group listed under `any_of` must hit:

> `category` is Smooth **or** Love — **and** `sub_genre` is Melancholy **or** Acoustic.

With **`any`**, one group hitting is enough:

> `category` is Workout — **or** `genre` is Phonk — **or** `sub_genre` is Rap.

Use `any` for broad, character-based moods (Gym, Love, Focus) and `all` for precise ones.

## Fields

`language`, `genre`, `sub_genre`, `category`, `artist`, `channel`

All matching is exact and case-sensitive, against the tag columns in your CSV. Run
`ytps tag` first — rules match tags, not raw titles.

## Overlap is the point

A song can land in several moods, and usually should. Gym and Walk sharing tracks is
correct behaviour, not a bug.

## The catch-all

`catch_all: Misc` collects anything matching no mode, so nothing is ever silently
dropped. Set it to `null` to disable — then check `coverage()` yourself.

## Duration windows

Most listening moods set `min_sec: 120, max_sec: 420`. This is what keeps 40-second
clips and hour-long album jukeboxes out of a commute playlist. Leave the window off for
moods where length is irrelevant (Instrumental, Retro, Remix).

## Checking your work

```bash
ytps rules --rules rules/moods.default.yml   # does it parse?
ytps chunk library.csv --rules rules/moods.default.yml
```

Watch the counts. A mood matching 90% of your library is too broad; one matching three
songs is too narrow.
