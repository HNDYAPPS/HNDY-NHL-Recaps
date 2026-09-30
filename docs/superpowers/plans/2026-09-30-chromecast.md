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
- TV title: `teamsLabel(g) + ' · Game i/n'`. (Spec mentioned a hide-team-names setting; the code has none, so the title always includes teams.)
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
- Modify: `index.html` (CSS block before `</style>` ~line 264; HTML `#videowrap` ~line 277; `#controls` ~line 314; script tags ~line 320)

**Interfaces:**
- Produces: DOM ids `castBtn` (`<google-cast-launcher>`), `castScreen`, `castName`. Both `castBtn` and `castScreen` start with class `hidden`. Task 2 removes/adds `hidden` on them.

- [ ] **Step 1: Add CSS** (insert just before the closing `</style>` on line 264, i.e. after the mobile `@media` block)

```css
  /* Chromecast: SDK renders <google-cast-launcher> as an icon; we size
     it like a bar button. Hidden until the SDK says Cast is available,
     so non-Chrome browsers never see an empty box. */
  #castBtn {
    display: inline-block;
    width: 66px;
    height: 56px;
    padding: 10px 14px;
    box-sizing: border-box;
    background: #1c1c1c;
    border: 2px solid #3a3a3a;
    border-radius: 10px;
    cursor: pointer;
    --disconnected-color: #eee;
    --connected-color: #2a5;
  }
  #castBtn:hover { background: #333; border-color: #888; }
  /* Shown over the video area while casting. Above ytwrap (2), below
     the start overlay (10) and toast (5). */
  #castScreen {
    position: absolute;
    inset: 0;
    z-index: 3;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 18px;
    background: #000;
    color: #ccc;
    font-size: 28px;
    text-align: center;
    padding: 0 24px;
  }
  #castScreen svg { width: 96px; height: 96px; fill: #2a5; }
  @media (max-width: 640px), (max-height: 640px) {
    #castBtn { width: 40px; height: 40px; padding: 7px 8px; }
    #castScreen { font-size: 18px; }
    #castScreen svg { width: 56px; height: 56px; }
  }
```

