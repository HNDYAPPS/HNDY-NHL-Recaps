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

**This is an expected, ongoing pattern, not a one-off**: user intends
to add more users/customized pages over time (confirmed 2026-09-24).
Treat "add a profile for person X" as a small, well-trodden task using
the steps above, not a redesign.

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
GitHub Actions (cron, every 10 min, 03:00-11:50 UTC; runs before 06:00 Helsinki skipped)
  → fetch.py: hits api-web.nhle.com/v1/score/{date} (live, no cache)
  → score.py: for each finished game, fetches gamecenter landing JSON
              (cached per game — stable once game is FINAL) and player
              nationality (cached forever in cache/players.json) ONCE,
              shared across all profiles
  → per profile: writes days/{date}.json (rank, teams, video IDs, date,
              totalGames — NO scores/results, those go in
              debug/scores-{profile}-{date}.txt), rebuilds days/index.json,
              copies the NEWEST day to queue.json
  → liiga.py: reads @Liiga1975 YouTube feed, merges recaps into liiga.json,
              score.py adds each date's Liiga recaps to days/{date}.json
              under a separate "liiga" key (root: all, Handyy: JYP only)
  → commits all changed files (git add -A)
GitHub Pages serves index.html + queue.json + days/ per folder
  → browser loads queue.json (newest day), < > arrows load days/{date}.json;
    NHL plays via Brightcove, then Liiga via YouTube IFrame API
```

**Workflow commit step bug (fixed 2026-09-24)**: the commit step used
to `git add queue.json` — only the root file. Profile folders' own
`queue.json` files (e.g. `Handyy/queue.json`) were silently never
committed even though `score.py` generated them correctly every run.
Now uses `git add -A` (still respects `.gitignore`, so `cache/`/`debug/`
stay out) so every profile's files get committed automatically,
including any future ones.

### Why live fetch, no cache on the score endpoint
Recap video links (`threeMinRecap`, `condensedGame`) appear on games
progressively as NHL publishes them through the morning — West coast
games can finish very late (recap sometimes not ready until ~06:00-
07:00 UTC). The workflow runs every 10 min (raised from 30 min on
2026-09-24, at user's request — confirmed no real risk to NHL's API or
GitHub Actions at this volume) so games with recaps that weren't ready
earlier appear if you check the page again later. Caching the score
fetch would have blocked seeing new links appear.
(`fetch_score(date, force=True)` in score.py.)

### Video source: Brightcove, in-page embed
Account 6415718365001, player EXtG1xJ7H. No domain restriction —
confirmed working on GitHub Pages. Video ID = the trailing number in
`threeMinRecap`/`condensedGame` paths from the score API (regex
`(\d{10,})$`).

### Day archive + Liiga (added 2026-09-28)
- **days/**: every scored date is kept forever as `days/{date}.json`;
  `days/index.json` lists them. `queue.json` = copy of the newest day,
  so re-running an old date (`python score.py 2026-09-20`) is a safe
  backfill that never replaces today. Backfilled from 2026-09-20.
- **Liiga**: `liiga.py` reads the public channel feed (no key, channel
  `UCGxrUE2U-ncnBf4vDww-gAQ`). Feed only lists ~15 newest uploads, so
  every "Ottelukooste: Home − Away | D.M.YYYY" recap seen is stored in
  `liiga.json` and stays on its date. Titles carry no scores. Re-synced
  into day files every run, so late uploads still land. Profile filter
  = `liigaTeams` in its config (Handyy: `["JYP"]`); root gets all.
  Liiga lives in a separate `"liiga"` key, always played after NHL.

### Chromecast (added 2026-09-30)
Native cast, not tab mirroring. Google Cast web sender SDK
(`cast_sender.js?loadCastFramework=1`) + own `<button id="castBtn">` (Google's
`<google-cast-launcher>` hid itself with display:none; we call `requestSession()`)
in the bar, hidden until `__onGCastApiAvailable(true)`, so only Chrome
(desktop/Android) and Chromium browsers with Cast ever show it. Receiver is
Google's Default Media Receiver: no receiver code, no developer account.
Third playback mode `'cast'` with `castM` adapter behind `M()`; `loadCurrent()`
branches to `castLoad()`, which reuses `player.catalog.getVideo()` and sends
the first https HLS source (MP4 fallback) with title "AWAY @ HOME · Game i/n".
Auto-next on `CURRENT_TIME_CHANGED` (< `END_MARGIN` left) or IDLE/FINISHED.
Liiga (YouTube) cannot cast: next/dropdown into Liiga while casting toasts
"Liiga not castable" and stays. Disconnect returns to local play at the TV
position (`castResumeAt`). Page reload rejoins the session (`ORIGIN_SCOPED`)
without restarting the video. Cast needs https or localhost; `file://`
never shows the button. Verified facts: NHL streams are clear (no DRM), CORS
`*`, HLS with TS segments and separate audio rendition.
Alternative with zero code: on Chromecast with Google TV install a browser
(TV Bro) and open the profile URL directly with the remote (user does this too).

**Quality (added 2026-09-30):** local player forces the sharpest rendition
(`forceMaxQuality()`: `player.qualityLevels()`, only the max-height levels
stay enabled; Brightcove otherwise picks by player size, a 660 px window got
360p). Cast: the TV's own ABR sat low, so `castLoad()` fetches the HLS
master, keeps only the top-resolution variant + audio/subtitle lines
(`maxQualityManifest()`), and sends it inline as a `data:` URL. Verified
working on Chromecast with Google TV. Fallback chain if the TV rejects a
source (loadMedia reject or IDLE/ERROR): 1080p data playlist → https MP4
(720p) → plain HLS (`castCandidates`, `castTryNext()`). Renditions seen:
270p–1080p, top is 1080p @ ~4 Mbps. Phone on mobile data: ~150 MB per
5-minute recap.

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
- **Click/tap video to pause/play** (added 2026-09-24): video.js's own
  built-in click-to-toggle is explicitly disabled
  (`player.userActions({ click: false })`) and replaced with our own
  handler on `#videowrap`, to avoid a double-toggle where one click
  both played and immediately re-paused.

- **Day arrows** (added 2026-09-28): plain clickable `<` `>` text
  either side of the date, same size as the date (user's choice, not
  buttons). Dimmed at oldest/newest day. New day starts at Game 1.
- **Empty day** shows "NO GAMES TODAY" (was "Game 1/0"), start
  buttons hidden.
- **Liiga via YouTube** (added 2026-09-28): `M()` adapter routes all
  controls to Brightcove or YouTube, whichever is showing. YouTube
  iframe sits over the video in `#ytwrap` (hidden with `visibility`,
  not `display:none`, so it keeps loading). `#ytShield` catches clicks
  so YouTube's own UI/links are never reachable. Switches 1 s before
  the end (250 ms poll) so the end screen with suggestions never shows.
  Subtitles forced off (`cc_load_policy: 0` + `unloadModule('captions')`
  on play). Long button does nothing on Liiga (one video per game).

## Known constraints / things NOT built

- Casting: TV shows Google's own overlay (title + progress bar) briefly at
  start and on pause; cannot be hidden with the Default Media Receiver.
  Sender tab must stay alive to chain videos. No AirPlay (no Apple device
  to test). Custom receiver (would fix both) not built.
- No threshold/filtering — every game with a recap goes in the queue.
- No cross-device "last watched" sync (per-device localStorage only,
  by user's choice).
- Sportsnet highlights as an alternative source were discussed and
  explicitly rejected (no public API, fragile title-matching, NHL's
  own Brightcove recap already works reliably).
- GitHub Pages is public (free-tier private repos can't publish
  Pages) — repo was made public for this reason, confirmed nothing
  sensitive in it.
- DST handled: cron 03:00-11:50 UTC every 10 min; first step checks
  Helsinki time and skips scheduled runs before 06:00 (winter only).
  Manual dispatch always runs. First real run = 06:00 Finnish, all year.
- Day arrows are text, not focusable — no TV-remote navigation.
- Liiga recaps older than the feed's ~15 newest can't be backfilled.
- A pause every ~1 s on the user's PC turned out to be a Bluetooth
  speaker sending pause, not the code — check that first if it recurs.
- Berdu (friend's) profile not built yet — see `session-temp.md`. More
  profiles beyond that are expected over time (user's stated plan).

## Files

| File | Purpose |
|---|---|
| `fetch.py` | Fetches/caches score JSON, extracts finished games + video IDs |
| `score.py` | Scores games per profile, writes each profile's `queue.json` + `debug/scores-{profile}-{date}.txt`, copies `index.html` into non-root profile folders |
| `config.json` | Weights + favourite teams + `liigaTeams` — currently the Handyy profile's config |
| `liiga.py` | Reads Liiga YouTube feed, keeps `liiga.json`, groups recaps by date + team filter |
| `liiga.json` | Committed — every Liiga recap ever seen (videoId, teams, date) |
| `days/` (each profile folder) | Committed — one file per date + `index.json`; `queue.json` = newest day |
| `index.html` | The **canonical** player (single file, vanilla JS, no build step) — only ever edit this copy, at the repo root |
| `Handyy/` | Generated: `index.html` (copy, don't edit) + `queue.json` (Hannu's weighted profile) |
| `logo_hndyapps_black.png` / `logo_hndyapps_white.png` | Brand logo; black (dark-background) version is the one used in the UI |
| `favicon-32.png` / `icon-192.png` / `apple-touch-icon.png` | Site icons (tab, bookmarks, home screen), made by user; copied to profiles via `PLAYER_ASSETS` |
| `test.html` | Phase 0 scratch file, Brightcove embed proof-of-concept — not used by the real player, kept for reference |
| `requirements.txt` | Python deps (`requests`) |
| `.github/workflows/daily.yml` | The cron job (runs `score.py` once, which handles every profile internally) |
| `cache/` | gitignored — score JSON, per-game landing JSON, player nationality lookups |
| `debug/` | gitignored — score breakdowns with spoilers, one file per profile |
| `queue.json` (root) | Committed — the default/no-preference profile's queue, chronological order |

## Session history

- 2026-09-30: native Chromecast casting in player (cast mode, castM,
  Liiga skip, resume on disconnect); own cast button (Google's launcher
  element stayed display:none); max quality locally (qualityLevels) and on
  cast (1080p-only inline playlist, MP4/HLS fallback). Spec + plan under
  docs/superpowers/. Tested OK on desktop Chrome + Chromecast with Google TV.
- **2026-09-23/24**: Built phases 0-4 end to end, deployed to GitHub
  Pages, iterated on player UI (fonts, layout, mobile bugs) based on
  live device testing since local testing can't cover mobile. Fixed:
  video-fill-container, mobile-vs-desktop detection using width alone,
  Brightcove's inline-style sizing override, single-line mobile info
  bar, cron start time moved to 04:00 UTC. Then split into profiles:
  root is now unweighted/chronological/no-preferences, the original
  weighted experience moved to `/Handyy/`; replaced the text brand
  badge with the actual logo; removed the disabled-bar-until-start
  behavior so the dropdown/any control works immediately. Later the
  same day: fixed the logo missing on `/Handyy/` (asset wasn't copied,
  only the HTML was); fixed the workflow only ever committing the root
  `queue.json` (profile folders' queues were silently never committed
  — `git add -A` now); raised the cron frequency to every 10 minutes;
  added click/tap-to-pause on the video; fixed `Handyy/index.html`
  lagging behind root after a code push (established the going-forward
  rule: sync every profile's `index.html` in the same commit as any
  root `index.html` change). User confirmed more profiles are coming.
- **2026-09-28**: Day archive (`days/`, backfilled from 20 Sep) + `<` `>`
  day arrows; "NO GAMES TODAY" on empty days; Liiga recaps via YouTube
  after NHL (all on root, JYP only on Handyy), subtitles off; workflow
  actions bumped to checkout@v5 / setup-python@v6 (Node 24 warning); HNDYAPPS site icons.
- 2026-10-02: workflow first run 06:00 Finnish all year (cron 03 UTC + Helsinki time-check step).

## Picking this up next session

1. Read this file + `CLAUDE.md` (spec) first.
2. Repo is already public, pushed, Pages enabled, workflow running on
   its own — nothing to set up.
3. If continuing UI work: remember local testing can't catch
   mobile-only bugs (orientation, touch, `pointer: coarse`) — expect
   to push and have the user test on their actual phone.
4. If touching scoring: weights are in `config.json` (Handyy's), no
   code changes needed for weight tuning, just re-run
   `python score.py {date}` locally (cached landing/player data makes
   re-runs fast). Local runs also write `days/` and `liiga.json`: for a
   pure test, use a scratch copy of the repo, or `git checkout --` those
   files before committing. An old date arg no longer replaces
   `queue.json` (only the newest day does).
5. If editing `index.html`: copy it into every profile folder
   (`Handyy/`, and any others) in the SAME commit. It does not sync
   itself — see the "Important" note under Profiles above. Forgetting
   this caused a real bug once already.
6. Adding another person's profile (expected, ongoing — user plans
   more): follow the steps under Profiles above, it's a small task.
7. Follow the user's CLAUDE.md workflow rules: explain plan in plain
   English, wait for "yes" before coding, one change at a time when
   fixing bugs, always give a plain-language test plan after changes.
