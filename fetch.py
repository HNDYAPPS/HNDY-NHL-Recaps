"""Fetch one day's NHL games and extract recap video IDs.

Usage:
    python fetch.py              # yesterday (North American time)
    python fetch.py 2026-09-22   # specific date
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

API = "https://api-web.nhle.com/v1/score/{date}"
CACHE_DIR = Path(__file__).parent / "cache"
FINAL_STATES = {"FINAL", "OFF"}
VIDEO_ID_RE = re.compile(r"(\d{10,})$")


def yesterday_na() -> str:
    """Yesterday's date in US Eastern time (approx: UTC-4)."""
    eastern = timezone(timedelta(hours=-4))
    return (datetime.now(eastern) - timedelta(days=1)).strftime("%Y-%m-%d")


def fetch_score(date: str) -> dict:
    """Return score JSON for date. Uses cache/ if present."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"score-{date}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    resp = requests.get(
        API.format(date=date),
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    resp.raise_for_status()
    cache_file.write_text(resp.text, encoding="utf-8")
    return resp.json()


def video_id(path: str | None) -> str | None:
    """'/video/cbj-at-buf-recap-6405459878112' -> '6405459878112'."""
    if not path:
        return None
    m = VIDEO_ID_RE.search(path)
    return m.group(1) if m else None


def extract_games(score: dict) -> list[dict]:
    """Keep finished games. Pull team names and video IDs."""
    games = []
    for g in score.get("games", []):
        if g.get("gameState") not in FINAL_STATES:
            continue
        games.append(
            {
                "gameId": g["id"],
                "away": g["awayTeam"]["abbrev"],
                "home": g["homeTeam"]["abbrev"],
                "shortVideoId": video_id(g.get("threeMinRecap")),
                "longVideoId": video_id(g.get("condensedGame")),
                "raw": g,
            }
        )
    return games


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else yesterday_na()
    score = fetch_score(date)
    games = extract_games(score)

    print(f"Date: {date}   finished games: {len(games)}")
    print(f"{'gameId':<12}{'away':<6}{'home':<6}{'short':<16}{'long':<16}")
    for g in games:
        print(
            f"{g['gameId']:<12}{g['away']:<6}{g['home']:<6}"
            f"{g['shortVideoId'] or '-':<16}{g['longVideoId'] or '-':<16}"
        )


if __name__ == "__main__":
    main()
