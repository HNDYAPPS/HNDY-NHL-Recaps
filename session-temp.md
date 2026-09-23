# Session temp notes — multi-user profiles feature

Status: **planned, approved by user, NOT YET BUILT.** Read this +
`CLAUDE.md` + `DOCUMENTATION.md` to pick up.

## What's being added

Per-person customizable rankings, via named "profiles," each getting
its own folder + URL on the same GitHub Pages site. Pre-configured by
editing config files and pushing — no in-page settings UI, no login.

Final URLs:
- `https://hndyapps.github.io/HNDY-NHL-Recaps/` — main, no personal
  preferences (default profile)
- `https://hndyapps.github.io/HNDY-NHL-Recaps/Handyy/` — Hannu's
  profile (OTT favourite + current weights)
- `https://hndyapps.github.io/HNDY-NHL-Recaps/Berdu/` — friend's
  profile (STL favourite, weights start as a copy of Hannu's, friend
  can request tuning later)

## Why this design (don't re-litigate without cause)

- Ranking score is spoiler-adjacent (high score often implies OT,
  comeback, etc. happened), so it can NEVER be shipped to the browser
  for client-side re-ranking — that's why `queue.json` today has no
  scores at all. Profiles keep 100% of scoring server-side, so this
  constraint holds for every profile too.
- No user accounts/login/backend — two people, folders + static files
  are simplest, matches the project's static-site design.
- One canonical `index.html`, copied into each profile folder
  automatically. Never hand-maintain 3 copies. Each copy just fetches
  `queue.json` relative to its own folder — no routing/query-param
  logic needed in the JS at all, folder = profile.

## Assumption flagged to user, not yet explicitly confirmed

Main/default profile keeps today's tuned weights (goal count, margin,
overtime, lead changes, comeback, hat trick — the "general interesting
game" formula) but clears:
- `favouriteTeams: []`
- `finnishPoint: 0` (Finnish-player bonus — treated as Hannu's
  personal taste, not universal)

If wrong, fix `configs/default.json` weights before or after building.

## Implementation checklist (not started)

1. Create `configs/` folder:
   - `configs/default.json` — copy current `config.json`, set
     `favouriteTeams: []`, `finnishPoint: 0`
   - `configs/handyy.json` — copy current `config.json` as-is (OTT,
     current weights) — this is today's `config.json` unchanged
   - `configs/berdu.json` — copy current `config.json`, set
     `favouriteTeams: ["STL"]`
   - Decide: delete old root `config.json` once `configs/` is live, or
     keep it as an alias — pick whichever `score.py` ends up expecting
2. Add a profile → output-folder mapping in `score.py`, e.g.:
   ```python
   PROFILES = {
       "default": ".",      # root
       "handyy": "Handyy",
       "berdu": "Berdu",
   }
   ```
3. Refactor `score.py main()` to loop over `configs/*.json`:
   - fetch score/landing/player data ONCE (already cached, shared
     across profiles — don't refetch per profile)
   - for each profile: run `analyse()` with that profile's config,
     rank, `write_queue()` to `{output_folder}/queue.json`,
     `write_debug()` to `debug/scores-{profile}-{date}.txt`
4. Add a copy step (in `score.py` or a small separate script) that
   copies root `index.html` into `Handyy/index.html` and
   `Berdu/index.html` verbatim, every run — keep root `index.html` as
   the only file a human ever edits.
5. Make sure `.gitignore` still excludes `cache/` and `debug/` but NOT
   the new profile folders' `queue.json`/`index.html` (those must be
   committed, same as root `queue.json` today).
6. Test locally: run `python score.py 2026-09-22`, check
   `Handyy/queue.json` and `Berdu/queue.json` produce DIFFERENT game
   order (favourite-team bonus should visibly move OTT/STL games up),
   confirm root `queue.json` has no favourite-team bias.
7. Test the copied `index.html` files actually work via
   `python -m http.server 8000` — visit `/Handyy/` and `/Berdu/`
   locally, confirm each loads its own queue.
8. Commit + push. GitHub Actions workflow needs NO changes (it already
   just runs `python score.py`, which will now handle all profiles
   internally in one run).
9. Update `DOCUMENTATION.md` once built — add the profiles section,
   remove this file (or mark it done).

## Not yet decided / ask user if it comes up

- Exact weight tuning for `configs/berdu.json` beyond `favouriteTeams`
  — friend hasn't specified anything else yet.
- Whether root `queue.json` should keep being generated at all, or if
  "default" should just be an alias/copy of one profile — current plan
  assumes it stays its own neutral profile.
