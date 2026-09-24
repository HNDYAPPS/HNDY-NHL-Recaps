# Session temp notes — multi-user profiles feature

Status: **BUILT** (commit `7fae1f6`, 2026-09-24). See
`DOCUMENTATION.md`'s Profiles section for the actual shipped
architecture — it differs slightly from the original plan below
(no `configs/` folder was needed; default profile is fully
unweighted/chronological, not "current weights minus favourite team").

## What shipped

- `https://hndyapps.github.io/HNDY-NHL-Recaps/` — no preferences,
  games in the order actually played (chronological, `startTimeUTC`),
  zero scoring/weighting applied at all.
- `https://hndyapps.github.io/HNDY-NHL-Recaps/Handyy/` — Hannu's
  weighted profile (OTT favourite, Finnish-player bonus, the existing
  tuned weights), using the existing `config.json`.
- `score.py` has a `PROFILES` dict (profile name -> output folder +
  config filename). Fetches game/landing/player data once, reused
  across all profiles. Copies root `index.html` into each profile's
  folder automatically (`sync_player_html()`) — only ever hand-edit
  the root `index.html`.

## Not yet built

- **Berdu (friend's) profile** — was in the original ask but dropped
  from this round. To add: add an entry to `PROFILES` in `score.py`
  (e.g. `"berdu": ("Berdu", "configs/berdu.json")`), create that config
  file (copy `config.json`, change `favouriteTeams`), run `score.py`
  once locally to generate `Berdu/queue.json` + `Berdu/index.html`,
  commit. No other code changes needed — the loop already handles any
  number of profiles.
- Friend hasn't specified any weight preferences beyond a favourite
  team.
