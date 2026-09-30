# Chromecast native cast — design (2026-09-30)

## Goal
Cast button in the player. Phone/computer (Chrome) sends the NHL recap
stream to a Chromecast. TV plays it directly at full quality. Sender
device stays free for other use. Queue chaining (ended → next) keeps
working while casting. Works identically in root and every profile
folder (single `index.html`, copied as today).

## Verified facts (2026-09-30)
- NHL Brightcove videos: no DRM, HLS + MP4, CORS `*`. Castable.
- `player.catalog.getVideo(id)` already returns `video.sources` with
  stream URLs. No API key, no extra request.
- Google Cast web sender works only in Chrome (desktop + Android) and
  Chromium browsers with Cast (Brave, Opera). Not Firefox, Edge, Safari,
  any iOS browser. Accepted. No hint shown to unsupported browsers.
- YouTube (Liiga) cannot play on the Default Media Receiver. Accepted:
  skip.
- AirPlay dropped: no Apple devices available to test.

## Architecture
- Third playback mode `'cast'` beside `'bc'` and `'yt'`. New adapter
  `castM` implementing the same interface as `bcM`/`ytM`:
  `play, pause, paused, time(t?), duration`. `M()` returns it while
  casting. Existing controls untouched.
- Cast SDK: `<script src="https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1">`
  + `window.__onGCastApiAvailable`. Receiver:
  `chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID`. Auto-join
  `ORIGIN_SCOPED` so a page reload rejoins the running session.
- Button: `<google-cast-launcher>` inside `#controls` next to
  fullscreen, styled to match existing buttons. SDK renders it only
  when Cast is available; otherwise nothing appears.

## Behaviour
1. **Connect** (SESSION_STARTED / RESUMED): pause Brightcove, stop
   YouTube, `mode = 'cast'`, show dark cast screen over the video area
   with cast icon + "Casting to {deviceName}". Bar/controls unchanged.
   Then `loadCurrent()`.
2. **Load** (`loadCurrent` in cast mode): if game has `youtubeId` →
   toast "Liiga not castable", do not move, TV idles. Else
   `catalog.getVideo(currentVideoId())` → choose first `https` source
   with type `application/x-mpegURL`; fallback first `https` MP4;
   none → toast "No castable stream, skipping", `go(1)`. Build
   `MediaInfo(url, type)` with `GenericMediaMetadata.title =
   "{AWAY} @ {HOME} · Game i/n"` (always with teams; there is no
   hide-team-names setting and none is wanted). `LoadRequest.autoplay = true`,
   `session.loadMedia`. Failure → toast, `go(1)`.
3. **Auto-next**: `CURRENT_TIME_CHANGED` event; when
   `duration - currentTime < END_MARGIN` and not `switching` → `go(1)`.
   Also `PLAYER_STATE_CHANGED` → IDLE with idleReason FINISHED → `go(1)`
   (belt and braces). `switching` guard reused as in YouTube path.
4. **Controls** through `castM`: play/pause via
   `RemotePlayerController.playOrPause()`, seek via
   `remotePlayer.currentTime = t; controller.seek()`, prev/next/jump/
   day arrows/long toggle all end in `loadCurrent()` → step 2. Pause
   button glyph follows `IS_PAUSED_CHANGED`.
5. **Liiga boundary**: `go(1)` from last NHL game while casting →
   toast "Liiga not castable — end of queue", index does not move.
   Jump dropdown to a Liiga game → same toast, no load.
6. **Disconnect** (SESSION_ENDED, any reason): remember remote time,
   `mode = 'bc'`, hide cast screen, `loadCurrent()` locally, seek to
   remembered time once metadata loads (best effort).
7. **SDK unavailable**: `__onGCastApiAvailable(false)` or script fails
   → nothing happens. Player identical to today.

## State
- `idx`, `useLong`, day selection: existing localStorage, unchanged.
- New in-memory only: `castSession`, `remotePlayer`, `controller`,
  `castDevice`, `resumeAt`.

## Files
- `index.html` (root): all changes. Target ≈150 lines added.
- `Handyy/index.html`: byte copy of root after change (same as
  `sync_player_html()`).
- `DOCUMENTATION.md`: "Chromecast" subsection under Architecture,
  Known constraints update, Session history line.

## Testing (manual; no test framework in this repo)
Cast SDK needs a secure context: `https://` or `http://localhost`.
`file://` will not show the button.
1. Local: `python -m http.server 8000` in repo root → Chrome desktop
   `http://localhost:8000/` → cast icon visible in bar → click → pick
   TV → TV plays, page shows "Casting to …" → pause/play, ±5 s,
   next/prev, long toggle, jump, day arrows → let a recap end → next
   starts alone → step to Liiga → toast, TV idle → disconnect → phone/
   PC resumes same game.
2. Same on `http://localhost:8000/Handyy/`.
3. Push → GitHub Pages → Android Chrome, repeat core checks.
4. Firefox desktop/Android: no cast icon, everything else as before.

## Known limits (accepted)
- TV shows Google's own overlay (title + progress bar) briefly at start
  and on pause. Cannot be hidden with the default receiver.
- Sender tab must stay alive to chain videos. Android may kill a long-
  idle background tab → chain stops; reopen page, it rejoins.
- Liiga never plays on the TV while casting.
- Future option if limits hurt: custom receiver (Cast developer
  console, USD 5 one-time) running the whole queue on the TV.

## Out of scope
AirPlay, custom receiver, YouTube casting, cross-device position sync.
