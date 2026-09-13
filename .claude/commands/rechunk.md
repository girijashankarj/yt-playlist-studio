---
description: Re-slice an already-tagged library after editing the mood rules
argument-hint: <library.csv> [rules.yml]
---

The user has changed mood rules and wants to see the effect on **$1**.

1. `ytps rules --rules ${2:-rules/moods.default.yml}` to confirm the pack parses.
2. `ytps chunk "$1" --rules ${2:-rules/moods.default.yml} -o out/moods`
3. Compare the new per-mood counts against the previous run if it is in context.

Flag anything that looks off: a mood matching more than about half the library is too
broad, one matching a handful is too narrow, and a mood that is a strict subset of
another is worth mentioning (it may be intentional, as Walk is inside ToWork).
