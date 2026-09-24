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

**Main URL** (no preferences): https://hndyapps.github.io/HNDY-NHL-Recaps/
**Hannu's profile** (weighted): https://hndyapps.github.io/HNDY-NHL-Recaps/Handyy/
**Repo**: https://github.com/HNDYAPPS/HNDY-NHL-Recaps (public — required
for free GitHub Pages; nothing sensitive in the repo)

## Status: all phases (0–4) built and working, confirmed on desktop +
mobile (Android/Firefox), plus a multi-profile split, as of 2026-09-24.

## Architecture

### Profiles (added 2026-09-24)
Two "profiles" today, each its own URL/folder, no login, pre-configured
by editing files and pushing:
- **Root `/`** — the default, no personal preferences at all. Games
  ordered purely by `startTimeUTC` (chronological) — no scoring, no
  weights applied whatsoever.
- **`/Handyy/`** — Hannu's weighted profile (OTT favourite, Finnish-
  player bonus, the tuned weights in `config.json`).

`score.py` has a `PROFILES` dict mapping profile name → (output
folder, config filename). Game/landing/player data is fetched **once**
per run and reused across every profile (no extra API load per
profile). For each profile it computes its own ranking and writes that
profile's own `queue.json`; `sync_player_html()` copies the single
canonical root `index.html` into every non-root profile folder
verbatim on every run — **only ever hand-edit the root `index.html`**,
the copies are generated, never edited directly.

Adding a new profile (e.g. a friend's): add one line to `PROFILES` in
`score.py`, add a config file, run `score.py` once locally to generate
that folder, commit. No other code changes needed. See
`session-temp.md` for the still-open "Berdu" (friend's) profile.

**Important**: the profile-folder copy of `index.html` only refreshes
when `score.py` actually runs (the cron, or a manual trigger) — it does
NOT happen just because root `index.html` was edited and pushed. This
caused a real bug (2026-09-24): a fix landed on the main page but was
missing on `/Handyy/` for a while. Rule going forward, per user
instruction — **fixes to `index.html` go to every profile folder in
the same commit** (`cp index.html Handyy/index.html`, etc.), not left
to wait for the next scheduled run.

Why not client-side re-ranking instead (ship one dataset, let the
browser sort it per person): the ranking score itself is spoiler-
adjacent (a high score usually means OT/comeback/etc. happened), which
is exactly why `queue.json` never sends scores to the browser. Profiles
keep 100% of scoring server-side so that guarantee holds for every
profile, not just the original one.

### Data flow
```
GitHub Actions (cron, every 30 min, 04:00-11:00 UTC)
  → fetch.py: hits api-web.nhle.com/v1/score/{date} (live, no cache)
  → score.py: for each finished game, fetches gamecenter landing JSON
              (cached per game — stable once game is FINAL) and player
              nationality (cached forever in cache/players.json) ONCE,
              shared across all profiles
  → per profile: writes queue.json (rank, teams, video IDs, date,
              totalGames — NO scores/results, those go in
              debug/scores-{profile}-{date}.txt) to that profile's folder
  → commits changed queue.json files (and any regenerated index.html copies)
GitHub Pages serves index.html + queue.json per folder
  → browser fetches that folder's queue.json, plays videos via Brightcove embed
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

### Scoring (config.json — used by the Handyy profile only)
Weighted sum of: goal count, margin (1-goal and 2-goal bonuses),
overtime, shootout (negative weight — user dislikes them), lead
changes, 3rd-period comeback, hat tricks, penalty minutes, favourite
team bonus (currently `["OTT"]`), Finnish player points (birthCountry
looked up via player API, cached forever). Fights weight is 0 (user:
"never shown in highlights"). **No threshold — all games are kept**,
user wants time to watch everything, just ranked by score. Debug
breakdown (spoilers) written to `debug/scores-{profile}-{date}.txt`.
The root/default profile applies none of this — see Profiles above.

## Player UI decisions (the "why" behind index.html)

- **Two start buttons** ("Short highlights" / "Long highlights"),
  stacked in 3 rows with the logo above them on the start overlay.
  Originally the bottom bar was disabled (`.not-started`, greyed out)
  until one was clicked — **removed 2026-09-24**: user wanted the
  dropdown (and every other control) usable immediately, without
  forcing the overlay choice first. Now `ensureStarted()` is called
  from `go()`, `jumpTo()`, `togglePause()`, `toggleLong()` etc. — the
  first control used, whichever it is, implicitly starts playback
  (default: short highlights, current `idx`).
- **Brand logo**: `logo_hndyapps_black.png` (dark rounded-square badge,
  white/orange text — designed for dark backgrounds, matches this UI).
  Shown in the bar next to the game counter (desktop only, hidden on
  mobile — no room) and above the two start buttons on the overlay.
  Replaced an earlier plain-text "HNDYAPPS / NHL RECAPS" badge.
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
- DST is not handled precisely — cron window (04:00-11:00 UTC) is a
  fixed compromise covering both Finnish winter and summer time
  reasonably, not exact.
- Berdu (friend's) profile not built yet — see `session-temp.md`.

## Files

| File | Purpose |
|---|---|
| `fetch.py` | Fetches/caches score JSON, extracts finished games + video IDs |
| `score.py` | Scores games per profile, writes each profile's `queue.json` + `debug/scores-{profile}-{date}.txt`, copies `index.html` into non-root profile folders |
| `config.json` | Weights + favourite teams — currently the Handyy profile's config |
| `index.html` | The **canonical** player (single file, vanilla JS, no build step) — only ever edit this copy, at the repo root |
| `Handyy/` | Generated: `index.html` (copy, don't edit) + `queue.json` (Hannu's weighted profile) |
| `logo_hndyapps_black.png` / `logo_hndyapps_white.png` | Brand logo; black (dark-background) version is the one used in the UI |
| `test.html` | Phase 0 scratch file, Brightcove embed proof-of-concept — not used by the real player, kept for reference |
| `requirements.txt` | Python deps (`requests`) |
| `.github/workflows/daily.yml` | The cron job (runs `score.py` once, which handles every profile internally) |
| `cache/` | gitignored — score JSON, per-game landing JSON, player nationality lookups |
| `debug/` | gitignored — score breakdowns with spoilers, one file per profile |
| `queue.json` (root) | Committed — the default/no-preference profile's queue, chronological order |

## Session history

- **2026-09-23/24**: Built phases 0-4 end to end, deployed to GitHub
  Pages, iterated on player UI (fonts, layout, mobile bugs) based on
  live device testing since local testing can't cover mobile. Fixed:
  video-fill-container, mobile-vs-desktop detection using width alone,
  Brightcove's inline-style sizing override, single-line mobile info
  bar, cron start time moved to 04:00 UTC. Then split into profiles:
  root is now unweighted/chronological/no-preferences, the original
  weighted experience moved to `/Handyy/`; replaced the text brand
  badge with the actual logo; removed the disabled-bar-until-start
  behavior so the dropdown/any control works immediately.

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
