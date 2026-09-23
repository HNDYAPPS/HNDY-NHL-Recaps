# NHL Spoiler-Free Recap Queue

## Session rules
- Working language: English.
- Load and use the caveman skill for all responses in this project.
  Terse output, no filler.

## Goal
Two-part tool:
1. Python bot: fetches previous day's NHL games, scores them with
   configurable weights, writes a watch queue to queue.json.
2. Static HTML player: plays queued recaps back-to-back with no spoilers.

Stack: Python 3.11+ (requests), vanilla HTML/JS player, no build tools.
Hosting: GitHub Pages + GitHub Actions cron (~08:00 UTC).

## Phase 0 – Brightcove embed test (DO FIRST, do not proceed until it works)

NHL recaps are hosted on Brightcove. Account 6415718365001, player EXtG1xJ7H.
Direct link format:
https://players.brightcove.net/6415718365001/EXtG1xJ7H_default/index.html?videoId=6405337939112&applicationId=nhl&autoplay=play

Build test.html with the Brightcove in-page embed (script tag
https://players.brightcove.net/6415718365001/EXtG1xJ7H_default/index.min.js
plus <video-js data-account data-player data-video-id>), two video IDs
6405337939112 and 6405344930112 (preseason games, 20 Sep), and video.js API:
player.on('ended') → player.catalog.getVideo + load next.
Hide via CSS: .vjs-progress-control, .vjs-duration, .vjs-remaining-time,
.vjs-current-time. Tell me what to verify in the browser.

If the in-page embed refuses on a foreign domain (domain restriction),
report it and propose iframe fallback + YouTube IFrame API alternative
(Sportsnet/NHL channels). Do not implement yet.

## Phase 1 – Data fetch

NHL web API is public, no key, undocumented:
- https://api-web.nhle.com/v1/score/YYYY-MM-DD  (day's games and results)
- https://api-web.nhle.com/v1/gamecenter/{gameId}/landing
- https://api-web.nhle.com/v1/gamecenter/{gameId}/play-by-play

Start by dumping /v1/score/2026-09-22 JSON and locate the fields holding
Brightcove video IDs (expected: threeMinRecap and condensedGame, possibly
as nhl.com/video paths requiring ID extraction). Handle missing recaps
gracefully – not every game gets a video or a long version. Only include
gameState FINAL/OFF. Cache responses in cache/ to avoid hammering the API
during development.

## Phase 2 – Scoring

config.json with weights and a score threshold. Suggested attributes:
- total goals, goal margin (smaller = better), overtime, shootout
- lead changes, third-period comeback, hat trick
- fights / penalty minutes
- favourite teams (list), Finnish players' points (list of names)
- playoffs / standings significance
Weighted sum, no LLM. Games below threshold are dropped from the queue.
Write queue.json: list of {rank, gameId, home, away, shortVideoId,
longVideoId}. NO scores, results or tags in the file the player reads –
those go to a separate debug log.

## Phase 3 – Player (index.html)

- Reads queue.json, plays short recaps in order, ended → next
  (load next ~1 s before end so no end screen is shown).
- Shows only "Game 3/9"; team names hideable via a setting.
- No progress bar, no duration. Own controls: pause, next, previous,
  -10 s, toggle short/long. Keyboard shortcuts: space / arrow keys.
- Works in a TV browser and as a Chromecast tab (large buttons, dark bg).
- Remember last watched position in localStorage.

## Phase 4 – Scheduling

GitHub Actions workflow running the bot ~10:00 Finnish time and committing
queue.json. Date = yesterday in North American time.

# context-mode — MANDATORY routing rules

You have context-mode MCP tools available. These rules are NOT optional — they protect your context window from flooding. A single unrouted command can dump 56 KB into context and waste the entire session.

## BLOCKED commands — do NOT attempt these

### curl / wget — BLOCKED
Any Bash command containing `curl` or `wget` is intercepted and replaced with an error message. Do NOT retry.
Instead use:
- `ctx_fetch_and_index(url, source)` to fetch and index web pages
- `ctx_execute(language: "javascript", code: "const r = await fetch(...)")` to run HTTP calls in sandbox

### Inline HTTP — BLOCKED
Any Bash command containing `fetch('http`, `requests.get(`, `requests.post(`, `http.get(`, or `http.request(` is intercepted and replaced with an error message. Do NOT retry with Bash.
Instead use:
- `ctx_execute(language, code)` to run HTTP calls in sandbox — only stdout enters context

### WebFetch — BLOCKED
WebFetch calls are denied entirely. The URL is extracted and you are told to use `ctx_fetch_and_index` instead.
Instead use:
- `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` to query the indexed content

## REDIRECTED tools — use sandbox equivalents

### Bash (>20 lines output)
Bash is ONLY for: `git`, `mkdir`, `rm`, `mv`, `cd`, `ls`, `npm install`, `pip install`, and other short-output commands.
For everything else, use:
- `ctx_batch_execute(commands, queries)` — run multiple commands + search in ONE call
- `ctx_execute(language: "shell", code: "...")` — run in sandbox, only stdout enters context

### Read (for analysis)
If you are reading a file to **Edit** it → Read is correct (Edit needs content in context).
If you are reading to **analyze, explore, or summarize** → use `ctx_execute_file(path, language, code)` instead. Only your printed summary enters context. The raw file content stays in the sandbox.

### Grep (large results)
Grep results can flood context. Use `ctx_execute(language: "shell", code: "grep ...")` to run searches in sandbox. Only your printed summary enters context.

## Tool selection hierarchy

1. **GATHER**: `ctx_batch_execute(commands, queries)` — Primary tool. Runs all commands, auto-indexes output, returns search results. ONE call replaces 30+ individual calls.
2. **FOLLOW-UP**: `ctx_search(queries: ["q1", "q2", ...])` — Query indexed content. Pass ALL questions as array in ONE call.
3. **PROCESSING**: `ctx_execute(language, code)` | `ctx_execute_file(path, language, code)` — Sandbox execution. Only stdout enters context.
4. **WEB**: `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` — Fetch, chunk, index, query. Raw HTML never enters context.
5. **INDEX**: `ctx_index(content, source)` — Store content in FTS5 knowledge base for later search.

## Subagent routing

When spawning subagents (Agent/Task tool), the routing block is automatically injected into their prompt. Bash-type subagents are upgraded to general-purpose so they have access to MCP tools. You do NOT need to manually instruct subagents about context-mode.

## Output constraints

- Keep responses under 500 words.
- Write artifacts (code, configs, PRDs) to FILES — never return them as inline text. Return only: file path + 1-line description.
- When indexing content, use descriptive source labels so others can `ctx_search(source: "label")` later.

## ctx commands

| Command | Action |
|---------|--------|
| `ctx stats` | Call the `ctx_stats` MCP tool and display the full output verbatim |
| `ctx doctor` | Call the `ctx_doctor` MCP tool, run the returned shell command, display as checklist |
| `ctx upgrade` | Call the `ctx_upgrade` MCP tool, run the returned shell command, display as checklist |
