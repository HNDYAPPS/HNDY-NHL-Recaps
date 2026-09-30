# Chromecast Native Cast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Cast button to the spoiler-free player so Chrome (desktop/Android) sends NHL recap streams to a Chromecast, with the queue chaining and all bar controls working while casting.

**Architecture:** The player already routes every control through `M()`, which returns a Brightcove adapter (`bcM`) or a YouTube adapter (`ytM`). We add a third mode `'cast'` with a `castM` adapter over the Google Cast `RemotePlayer`. `loadCurrent()` branches to `castLoad()` while casting; it reuses `player.catalog.getVideo()` (already used for local play) to get the HLS URL and hands it to Google's Default Media Receiver. Non-Chrome browsers never see anything: the SDK reports unavailable and the button stays hidden.

**Tech Stack:** Vanilla HTML/JS (single `index.html`), Google Cast Web Sender SDK (CAF, `cast_sender.js?loadCastFramework=1`), Brightcove Player catalog API. No build, no tests framework: verification is manual in a browser.

**Spec:** `docs/superpowers/specs/2026-09-30-chromecast-design.md`

## Global Constraints

- Single canonical `index.html` at repo root; `Handyy/index.html` must be a byte copy afterwards.
- Receiver: `chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID`. Auto-join: `ORIGIN_SCOPED`.
- Cast needs a secure context: test on `http://localhost:8000` or GitHub Pages. `file://` shows no button.
- Liiga (`youtubeId` games) never cast: toast `Liiga not castable`, index does not move.
- TV title: `teamsLabel(g) + ' · Game i/n'`. (Spec mentioned a hide-team-names setting; the code has none and the user confirmed none is needed, so the title always includes teams.)
- Stream choice: first `https` source with type matching `/mpegurl/i`; fallback first `https` MP4 (`container === 'MP4'` or type `/mp4/i`), content type `'video/mp4'` when the source has none.
- `END_MARGIN` (1.0 s) reused for auto-next.
- No behaviour change when not casting.
- Commit messages end with the attribution lines given in the session.

## Review Focus

1. Firefox / Safari / Edge user: no empty box in the bar, no cast screen, player identical. Pinned in Task 1 step 5 and Task 2 step 6 check A.
2. Page reload while casting: rejoins session, TV keeps playing, page shows "Casting to …" and does NOT restart the video. Pinned in Task 2 step 6 check H.
3. TV switched off or cast stopped from TV side mid-video: page returns to local mode, same game resumes near the TV position. Pinned in Task 2 step 6 check G.
4. Day arrow pressed while casting: new day's Game 1 loads on the TV. Pinned in Task 2 step 6 check E.
5. Liiga reached while casting (next or dropdown) or day with no NHL games: toast, no crash, previous/next still respond. Pinned in Task 2 step 6 check F.

---

### Task 1: Cast SDK, button and cast screen (HTML + CSS)

**Files:**
- Modify: `index.html` (CSS block before `</style>`; HTML `#videowrap`; `#controls`; script tags)

**Interfaces:**
- Produces: DOM ids `castBtn` (`<google-cast-launcher>`), `castScreen`, `castName`. Both `castBtn` and `castScreen` start with class `hidden`. Task 2 removes/adds `hidden` on them.

- [x] **Step 1: Add CSS** just before `</style>` (after the mobile `@media` block): `#castBtn` sized like a bar button (66×56, 40×40 under the existing `@media (max-width: 640px), (max-height: 640px)`), `--disconnected-color: #eee`, `--connected-color: #2a5`; `#castScreen` absolute, `inset: 0`, `z-index: 3`, black, flex column centred, svg 96px green.

- [x] **Step 2: Add cast screen markup** inside `#videowrap` right after `#ytwrap`:

```html
    <div id="castScreen" class="hidden">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="…cast icon…"/></svg>
      <div id="castName">Casting</div>
    </div>
```

- [x] **Step 3: Add the launcher** in the last `.group` of `#controls` after `#fs`:

```html
        <google-cast-launcher id="castBtn" class="hidden" title="Cast to TV"></google-cast-launcher>
```

- [x] **Step 4: Add the SDK script tag** right after the Brightcove script tag:

```html
<script src="https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1"></script>
```

- [x] **Step 5: Verify** — structural check ran (hidden classes present, script parses). Browser check (Firefox: no extra box; Chrome: no button yet) deferred to user.

- [x] **Step 6: Commit** — `c5ff8c9 Player: Chromecast scaffold`.

---

### Task 2: Cast logic (JS)

**Files:**
- Modify: `index.html` script: `M()`; `loadYouTube`; `loadCurrent`; `go`; `jumpTo`; new block after `showBrightcove()`.

**Interfaces:**
- Consumes: DOM ids from Task 1 (`castBtn`, `castScreen`, `castName`); existing `player`, `games`, `idx`, `mode`, `switching`, `started`, `END_MARGIN`, `toast()`, `render()`, `saveState()`, `teamsLabel()`, `currentVideoId()`, `ensureStarted()`, `go()`, `loadCurrent()`.
- Produces: `castM` adapter (same shape as `bcM`), `castLoad(g)`, `castSource(video)`, `castConnected()`, `castDisconnected()`, `castResumeAt` (seconds), `mode === 'cast'`.

- [ ] **Step 1: Add state + adapter + `M()`.** Replace

```js
  function M() { return mode === 'yt' ? ytM : bcM; }
```

with

```js
  // ---- Chromecast (Google Cast web sender; Chrome only) ----
  // Third mode 'cast': the TV plays, this page is only the remote.
  var castCtx = null;      // cast.framework.CastContext
  var remotePlayer = null; // cast.framework.RemotePlayer (mirror of TV state)
  var remoteCtl = null;    // cast.framework.RemotePlayerController
  var castResumeAt = 0;    // TV position to resume locally after disconnect

  var castM = {
    play: function () { if (remotePlayer && remotePlayer.isMediaLoaded && remotePlayer.isPaused) remoteCtl.playOrPause(); },
    pause: function () { if (remotePlayer && remotePlayer.isMediaLoaded && !remotePlayer.isPaused) remoteCtl.playOrPause(); },
    paused: function () { return !remotePlayer || !remotePlayer.isMediaLoaded || remotePlayer.isPaused; },
    time: function (t) {
      if (!remotePlayer || !remotePlayer.isMediaLoaded) return 0;
      if (t === undefined) return remotePlayer.currentTime;
      remotePlayer.currentTime = t;
      remoteCtl.seek();
    },
    duration: function () { return (remotePlayer && remotePlayer.isMediaLoaded) ? remotePlayer.duration : 0; }
  };
  function M() { return mode === 'cast' ? castM : mode === 'yt' ? ytM : bcM; }
```

- [ ] **Step 2: Add SDK init, session and remote-player listeners** right after `showBrightcove()`:

```js
  // Called by cast_sender.js once it knows whether Cast works here.
  // Non-Chrome browsers: ok === false (or never called) → nothing happens.
  window.__onGCastApiAvailable = function (ok) {
    if (!ok || !window.cast || !cast.framework) return;
    castCtx = cast.framework.CastContext.getInstance();
    castCtx.setOptions({
      receiverApplicationId: chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID,
      autoJoinPolicy: chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED
    });
    remotePlayer = new cast.framework.RemotePlayer();
    remoteCtl = new cast.framework.RemotePlayerController(remotePlayer);
    $('castBtn').classList.remove('hidden');

    castCtx.addEventListener(cast.framework.CastContextEventType.SESSION_STATE_CHANGED, function (e) {
      var S = cast.framework.SessionState;
      if (e.sessionState === S.SESSION_STARTED || e.sessionState === S.SESSION_RESUMED) castConnected();
      else if (e.sessionState === S.SESSION_ENDED) castDisconnected();
    });

    var E = cast.framework.RemotePlayerEventType;
    remoteCtl.addEventListener(E.IS_PAUSED_CHANGED, function () {
      if (mode !== 'cast') return;
      $('pause').textContent = remotePlayer.isPaused ? '▶' : '⏸';
    });
    // Auto-next, same rule as the local players: switch just before the end.
    remoteCtl.addEventListener(E.CURRENT_TIME_CHANGED, function () {
      if (mode !== 'cast' || switching || !started || !remotePlayer.isMediaLoaded) return;
      var d = remotePlayer.duration, t = remotePlayer.currentTime;
      if (d && t && d - t < END_MARGIN) go(1);
    });
    // Belt and braces: TV reports FINISHED (time events are only ~1/s).
    remoteCtl.addEventListener(E.PLAYER_STATE_CHANGED, function () {
      if (mode !== 'cast' || switching || !started) return;
      if (remotePlayer.playerState !== chrome.cast.media.PlayerState.IDLE) return;
      var s = castCtx.getCurrentSession();
      var ms = s && s.getMediaSession();
      if (ms && ms.idleReason === chrome.cast.media.IdleReason.FINISHED) go(1);
    });
  };

  function castConnected() {
    var s = castCtx.getCurrentSession();
    var name = (s && s.getCastDevice() && s.getCastDevice().friendlyName) || 'TV';
    if (mode === 'bc' && player) player.pause();
    if (mode === 'yt' && ytReady) ytPlayer.stopVideo();
    ytPending = null;
    $('ytwrap').classList.add('ythide');
    mode = 'cast';
    $('castName').textContent = 'Casting to ' + name;
    $('castScreen').classList.remove('hidden');
    ensureStarted(false);
    // Rejoined after a page reload while the TV is already playing:
    // leave it alone, just show the state. Otherwise start current game.
    if (remotePlayer.isMediaLoaded) { render(); return; }
    if (games.length) loadCurrent();
  }

  function castDisconnected() {
    if (mode !== 'cast') return;
    castResumeAt = (remotePlayer && remotePlayer.isMediaLoaded) ? (remotePlayer.currentTime || 0) : 0;
    $('castScreen').classList.add('hidden');
    $('pause').textContent = '⏸';
    mode = 'bc';
    if (started && games.length) loadCurrent();
  }

  // Pick a stream URL the TV can play from the Brightcove catalog entry.
  function castSource(video) {
    var list = (video && video.sources) || [];
    var pick = function (test) {
      for (var i = 0; i < list.length; i++) {
        var s = list[i];
        if (s.src && s.src.indexOf('https://') === 0 && test(s)) return s;
      }
      return null;
    };
    var hls = pick(function (s) { return /mpegurl/i.test(s.type || ''); });
    if (hls) return { src: hls.src, type: 'application/x-mpegURL' };
    var mp4 = pick(function (s) { return s.container === 'MP4' || /mp4/i.test(s.type || ''); });
    if (mp4) return { src: mp4.src, type: mp4.type || 'video/mp4' };
    return null;
  }

  function castLoad(g) {
    if (!g) return;
    if (g.youtubeId) { toast('Liiga not castable'); return; }
    var vid = currentVideoId();
    if (!vid) { toast('No video'); return; }
    var session = castCtx && castCtx.getCurrentSession();
    if (!session) return;
    switching = true;
    player.catalog.getVideo(vid, function (error, video) {
      if (mode !== 'cast') return; // cast ended while fetching
      if (error) { toast('Video load failed, skipping'); switching = false; go(1); return; }
      var src = castSource(video);
      if (!src) { toast('No castable stream, skipping'); switching = false; go(1); return; }
      var info = new chrome.cast.media.MediaInfo(src.src, src.type);
      info.streamType = chrome.cast.media.StreamType.BUFFERED;
      info.metadata = new chrome.cast.media.GenericMediaMetadata();
      info.metadata.title = teamsLabel(g) + ' · Game ' + (idx + 1) + '/' + games.length;
      var req = new chrome.cast.media.LoadRequest(info);
      req.autoplay = true;
      session.loadMedia(req).then(
        function () { switching = false; },
        function (err) {
          console.error('cast loadMedia', err);
          switching = false;
          toast('Cast load failed, skipping');
          go(1);
        }
      );
    });
  }
```

- [ ] **Step 3: Route `loadCurrent()` and resume position.** In `loadCurrent`, after `saveState();` add `if (mode === 'cast') { castLoad(g); return; }`. Inside the catalog callback, just before `player.catalog.load(video);` add:

```js
      // Coming back from a cast: pick up where the TV was.
      if (castResumeAt) {
        var at = castResumeAt;
        castResumeAt = 0;
        player.one('loadedmetadata', function () { try { player.currentTime(at); } catch (e) {} });
      }
```

In `loadYouTube(id)` add as first line: `castResumeAt = 0; // position belonged to an NHL video, not this one`.

- [ ] **Step 4: Liiga boundary.** In `go()`, after the `n >= games.length` check add:

```js
    if (mode === 'cast' && games[n].youtubeId) { toast('Liiga not castable — end of queue'); return; }
```

In `jumpTo()`, after the range check add:

```js
    if (mode === 'cast' && games[n].youtubeId) { toast('Liiga not castable'); render(); return; }
```

(`render()` snaps the dropdown back to the current game.) `toggleLong` needs no change.

- [ ] **Step 5: Syntax check**

```bash
node -e "const s=require('fs').readFileSync('index.html','utf8');new Function(s.match(/<script>([\s\S]*)<\/script>/)[1]);console.log('parse OK')"
```

Expected: `parse OK`.

- [ ] **Step 6: Manual verification** (`python -m http.server 8000`, Chromecast on same network)

- A. Firefox: no cast icon, no black cast screen, plays as before.
- B. Chrome: cast icon after ⛶. Click → device picker → choose TV. Page shows black area "Casting to <name>". TV starts current game within a few seconds. Local video silent.
- C. Pause/space toggles TV; glyph follows. -5s/+5s seek TV. Prev/next change TV video. Long toggles to long recap on TV. Dropdown jumps.
- D. Let a recap run out: next game starts on TV by itself, counter advances.
- E. Day arrow `<`: previous day loads, TV plays its Game 1.
- F. Step next past last NHL game: toast "Liiga not castable — end of queue", counter stays. Dropdown → Liiga game: toast, dropdown snaps back. Prev still works.
- G. Turn TV off (or stop cast from TV): page returns to local play of the same game, roughly at TV position.
- H. While casting, reload page: icon shows connected (green), "Casting to …" appears, TV keeps playing without restart. Next still works.
- I. Click cast icon → Stop casting: local playback resumes.
- Repeat B, C, D on `/Handyy/` after Task 3 copy.

If anything in B–I fails: stop, report what was seen, fix one thing.

- [ ] **Step 7: Commit**

```bash
git add index.html
git commit -m "Player: native Chromecast casting (cast mode, castM adapter, Liiga skip, resume on disconnect)"
```

---

### Task 3: Profile copy, docs, publish

**Files:**
- Modify: `Handyy/index.html` (overwrite with root copy)
- Modify: `DOCUMENTATION.md` (Architecture subsection after "Day archive + Liiga"; "Known constraints"; Session history)
- Modify: `CLAUDE.md` (one line under "Additions after Phase 4")

**Interfaces:** none.

- [ ] **Step 1: Copy player to profile**

```bash
cp index.html Handyy/index.html
git diff --stat
```

Expected: `Handyy/index.html` changed, diff identical to root change.

- [ ] **Step 2: DOCUMENTATION.md additions**

After the "Day archive + Liiga" subsection add:

```markdown
### Chromecast (added 2026-09-30)
Native cast, not tab mirroring. Google Cast web sender SDK
(`cast_sender.js?loadCastFramework=1`) + `<google-cast-launcher id="castBtn">`
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
(TV Bro) and open the profile URL directly with the remote.
```

Under "Known constraints / things NOT built" add:

```markdown
- Casting: TV shows Google's own overlay (title + progress bar) briefly at
  start and on pause; cannot be hidden with the Default Media Receiver.
  Sender tab must stay alive to chain videos. No AirPlay (no Apple device
  to test). Custom receiver (would fix both) not built.
```

Under "Session history" add one line:

```markdown
- 2026-09-30: native Chromecast casting in player (cast mode, castM,
  Liiga skip, resume on disconnect); spec + plan under docs/superpowers/.
```

- [ ] **Step 3: CLAUDE.md** — under "Additions after Phase 4" add:

```markdown
- Chromecast native cast button (Chrome only), 2026-09-30. Details in
  DOCUMENTATION.md.
```

- [ ] **Step 4: Commit and publish**

```bash
git add Handyy/index.html DOCUMENTATION.md CLAUDE.md docs/superpowers/plans/2026-09-30-chromecast.md
git commit -m "Chromecast: profile copy + docs"
git push
```

- [ ] **Step 5: Verify on GitHub Pages** (after Pages finishes, ~1–2 min)

- Android Chrome → `https://hndyapps.github.io/HNDY-NHL-Recaps/Handyy/`: cast icon in bar → cast → TV plays → next/pause work → lock phone briefly → TV keeps playing.
- Android Firefox: no icon, unchanged.
