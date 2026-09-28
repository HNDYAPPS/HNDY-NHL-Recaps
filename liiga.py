"""Finnish Liiga game recaps from the @Liiga1975 YouTube channel.

YouTube's public channel feed only lists the ~15 newest uploads, so
every recap we ever see is kept in liiga.json. Once caught, a video
stays saved for its date even after it drops out of the feed.

Only "Ottelukooste: Home − Away | D.M.YYYY" titles are used. Titles
carry teams + date only, never scores, so nothing here is a spoiler.
"""

import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).parent
STORE = ROOT / "liiga.json"
CHANNEL_ID = "UCGxrUE2U-ncnBf4vDww-gAQ"  # @Liiga1975
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=" + CHANNEL_ID

ENTRY_RE = re.compile(
    r"<entry>.*?<yt:videoId>(.*?)</yt:videoId>.*?<title>(.*?)</title>"
    r".*?<published>(.*?)</published>",
    re.S,
)
# Team names can contain a hyphen (K-Espoo), so the separator must
# have spaces around it.
TITLE_RE = re.compile(
    r"^Ottelukooste:\s*(.+?)\s+[−–-]\s+(.+?)\s*\|\s*(\d{1,2})\.(\d{1,2})\.(\d{4})"
)


def load_store() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {}


def fetch_recaps() -> list[dict]:
    r = requests.get(FEED, timeout=30)
    r.raise_for_status()
    recaps = []
    for vid, title, published in ENTRY_RE.findall(r.text):
        m = TITLE_RE.match(title.strip())
        if not m:
            continue  # press conference, clip, top 5 etc.
        home, away, d, mth, y = m.groups()
        recaps.append({
            "youtubeId": vid,
            "home": home,
            "away": away,
            "date": f"{y}-{int(mth):02d}-{int(d):02d}",
            "published": published,
        })
    return recaps


def update_store() -> dict:
    """Merge newly seen recaps into liiga.json. Feed failure is not
    fatal: NHL output must still happen, stored videos still used."""
    store = load_store()
    try:
        fresh = fetch_recaps()
    except Exception as e:  # noqa: BLE001
        print(f"Liiga feed failed, using saved list only: {e}")
        return store
    added = 0
    for v in fresh:
        if v["youtubeId"] not in store:
            store[v["youtubeId"]] = v
            added += 1
    STORE.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Liiga: {added} new recap(s), {len(store)} saved in total")
    return store


def recaps_by_date(store: dict, teams: list[str] | None = None) -> dict:
    """date -> list of {youtubeId, home, away}, upload order.
    teams=None means every game; otherwise only games involving one
    of the listed teams."""
    out: dict[str, list] = {}
    for v in sorted(store.values(), key=lambda v: v["published"]):
        if teams and v["home"] not in teams and v["away"] not in teams:
            continue
        out.setdefault(v["date"], []).append(
            {"youtubeId": v["youtubeId"], "home": v["home"], "away": v["away"]}
        )
    return out
