# NHL Spoiler-Free Recap Queue — Documentation

For a new AI session picking this up: read this file first, then
`CLAUDE.md` for the original spec/phases. This file tracks what's
actually built and why, since the spec describes intent and this
describes reality.

## What this is

A personal tool for hannu.tuomainen@handyy.org (GitHub: HNDYAPPS) to
watch NHL game recaps without seeing scores/spoilers beforehand.

Two parts:
1. **Python bot** (`fetch.py` + `score.py`) — runs on GitHub Actions,
   no local machine needed. Fetches yesterday's NHL games, scores them
   by "how interesting is this game" using configurable weights, writes
   `queue.json`.
2. **Static HTML player** (`index.html`) — hosted on GitHub Pages,
   reads `queue.json`, plays recap videos back-to-back with a
   custom spoiler-free UI (no progress bar, no scores shown).

**Live URL**: https://hndyapps.github.io/HNDY-NHL-Recaps/
**Repo**: https://github.com/HNDYAPPS/HNDY-NHL-Recaps (public — required
for free GitHub Pages; nothing sensitive in the repo)

## Status: all phases (0–4) built and working, confirmed on desktop +
mobile (Android/Firefox) as of 2026-09-24.

## Architecture

### Data flow
```
GitHub Actions (cron, every 30 min, 05:00-11:00 UTC)
  → fetch.py: hits api-web.nhle.com/v1/score/{date} (live, no cache)
  → score.py: for each finished game, fetches gamecenter landing JSON
              (cached per game — stable once game is FINAL) and player
              nationality (cached forever in cache/players.json)
  → writes queue.json (rank, teams, video IDs, date, totalGames — NO
              scores/results, those go in debug/scores-{date}.txt)
  → commits queue.json if changed
GitHub Pages serves index.html + queue.json
  → browser fetches queue.json, plays videos via Brightcove embed
```

### Why live fetch, no cache on the score endpoint
Recap video links (`threeMinRecap`, `condensedGame`) appear on games
progressively as NHL publishes them through the morning — West coast
games can finish very late (recap sometimes not ready until ~06:00-
07:00 UTC). The workflow runs every 30 min specifically so games with
recaps that weren't ready at 8am Finnish time appear if you check the
page again later. Caching the score fetch would have blocked seeing
new links appear. (`fetch_score(date, force=True)` in score.py.)

### Video source: Brightcove, in-page embed
Account 6415718365001, player EXtG1xJ7H. No domain restriction —
confirmed working on GitHub Pages. Video ID = the trailing number in
`threeMinRecap`/`condensedGame` paths from the score API (regex
`(\d{10,})$`).

### Scoring (config.json)
Weighted sum of: goal count, margin (1-goal and 2-goal bonuses),
overtime, shootout (negative weight — user dislikes them), lead
changes, 3rd-period comeback, hat tricks, penalty minutes, favourite
team bonus (currently `["OTT"]`), Finnish player points (birthCountry
looked up via player API, cached forever). Fights weight is 0 (user:
"never shown in highlights"). **No threshold — all games are kept**,
user wants time to watch everything, just ranked by score. Debug
breakdown (spoilers) written to `debug/scores-{date}.txt`.

## Player UI decisions (the "why" behind index.html)

- **Two start buttons** ("Short highlights" / "Long highlights")
  instead of one generic Start — avoids a bug where picking Long
  before dismissing an overlay left playback running behind it.
  Bottom bar is inert (`.not-started`) until one is clicked.
- **Brand badge** ("HNDYAPPS / NHL RECAPS") — placeholder logo, user
  plans to design a real one later. Shown on desktop only; hidden on
  mobile (decoration, not worth the space there).
- **Mobile vs desktop detection**: uses `matchMedia('(pointer: coarse)')`
  AND the **shorter** of width/height < 640px — NOT raw width. Raw
  width breaks on phone landscape (width exceeds any phone threshold
  once rotated), which was a real bug, fixed in commit `09e1e06`.
- **Mobile layout**: bar is `position: absolute` overlaying the bottom
  of the video (not in normal flow) so auto-hiding it doesn't leave a
  gap — video fills the full screen underneath. Auto-hides 2s after
  playback starts, tap-to-reveal uses `pointerdown` (not `click`,
  which can get swallowed by the video's own touch handling). Info
  line collapses to a single centered line (date · game counter ·
  teams · total games) instead of desktop's two-line layout, since
  there's no room for the brand badge + two lines + a control row on a
  phone. Bar background is semi-transparent by design (user preference
  — tried opaque, user wanted it reverted).
- **Video sizing quirk (important if it recurs)**: Brightcove's
  player sets its own inline sizing (aspect-ratio locked box) on both
  the player root element and the video tag, which beats a plain CSS
  rule since inline style normally wins. Fixed by forcing our sizing
  with `!important` via `el.style.setProperty(prop, val, 'important')`
  in `fixPlayerSize()`, re-applied on video load, resize, orientation
  change, and `play`. This was NOT a recurring/timer-based issue
  (an earlier fix attempt assumed it was and added a 2s setInterval —
  reverted, wasn't needed, keep it simple).
- **-5s / +5s** buttons (not -10s — user preference). Keyboard: space
  = pause, ←/→ = prev/next game, ↓/↑ = -5s/+5s, L = long/short toggle,
  F = fullscreen.
- **New-games badge**: per-device only (localStorage), compares game
  count seen last visit vs now for the same date. Explicitly NOT
  cross-device — user confirmed per-device is enough, decided against
  building a shared backend for this.

## Known constraints / things NOT built

- No threshold/filtering — every game with a recap goes in the queue.
- No cross-device "last watched" sync (per-device localStorage only,
  by user's choice).
- Sportsnet highlights as an alternative source were discussed and
  explicitly rejected (no public API, fragile title-matching, NHL's
  own Brightcove recap already works reliably).
- GitHub Pages is public (free-tier private repos can't publish
  Pages) — repo was made public for this reason, confirmed nothing
  sensitive in it.
- DST is not handled precisely — cron window (05:00-11:00 UTC) is a
  fixed compromise covering both Finnish winter and summer time
  reasonably, not exact.

## Files

| File | Purpose |
|---|---|
| `fetch.py` | Fetches/caches score JSON, extracts finished games + video IDs |
| `score.py` | Scores games, writes `queue.json` + `debug/scores-{date}.txt` |
| `config.json` | Weights + favourite teams |
| `index.html` | The player (single file, vanilla JS, no build step) |
| `test.html` | Phase 0 scratch file, Brightcove embed proof-of-concept — not used by the real player, kept for reference |
| `requirements.txt` | Python deps (`requests`) |
| `.github/workflows/daily.yml` | The cron job |
| `cache/` | gitignored — score JSON, per-game landing JSON, player nationality lookups |
| `debug/` | gitignored — score breakdowns with spoilers |
| `queue.json` | Committed — what the player actually reads |

## Session history

- **2026-09-23/24**: Built phases 0-4 end to end, deployed to GitHub
  Pages, iterated on player UI (fonts, layout, mobile bugs) based on
  live device testing since local testing can't cover mobile. Fixed:
  video-fill-container, mobile-vs-desktop detection using width alone,
  Brightcove's inline-style sizing override, single-line mobile info
  bar. Current queue.json has real data from 2026-09-22 games.

## Picking this up next session

1. Read this file + `CLAUDE.md` (spec) first.
2. Repo is already public, pushed, Pages enabled, workflow running on
   its own — nothing to set up.
3. If continuing UI work: remember local testing can't catch
   mobile-only bugs (orientation, touch, `pointer: coarse`) — expect
   to push and have the user test on their actual phone.
4. If touching scoring: weights are in `config.json`, no code changes
   needed for weight tuning, just re-run `python score.py {date}`
   locally (cached landing/player data makes re-runs fast).
5. Follow the user's CLAUDE.md workflow rules: explain plan in plain
   English, wait for "yes" before coding, one change at a time when
   fixing bugs, always give a plain-language test plan after changes.
