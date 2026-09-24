"""Score one day's NHL games and write queue.json.

Usage:
    python score.py              # yesterday (North American time)
    python score.py 2026-09-22   # specific date

Outputs:
    queue.json          - spoiler-free watch list for the player
    debug/scores-DATE.txt - full score breakdown (SPOILERS)
"""

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import requests

from fetch import CACHE_DIR, extract_games, fetch_score, yesterday_na

ROOT = Path(__file__).parent

# profile name -> (output folder, config file). Root "." is the default,
# no-preference profile: chronological order, no scoring at all. Every
# other profile gets its own folder + a copy of index.html, and is
# ranked by config.json's weights.
PROFILES = {
    "handyy": ("Handyy", "config.json"),
}
LANDING_API = "https://api-web.nhle.com/v1/gamecenter/{game_id}/landing"
PLAYER_API = "https://api-web.nhle.com/v1/player/{player_id}/landing"
PLAYERS_CACHE = CACHE_DIR / "players.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def load_config(filename: str = "config.json") -> dict:
    return json.loads((ROOT / filename).read_text(encoding="utf-8"))


def fetch_landing(game_id: int) -> dict:
    """Gamecenter landing JSON. Cached per game."""
    cache_file = CACHE_DIR / f"landing-{game_id}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    resp = requests.get(
        LANDING_API.format(game_id=game_id), headers=HEADERS, timeout=30
    )
    resp.raise_for_status()
    cache_file.write_text(resp.text, encoding="utf-8")
    return resp.json()


def load_players() -> dict:
    if PLAYERS_CACHE.exists():
        return json.loads(PLAYERS_CACHE.read_text(encoding="utf-8"))
    return {}


def save_players(players: dict) -> None:
    PLAYERS_CACHE.write_text(
        json.dumps(players, indent=1, sort_keys=True), encoding="utf-8"
    )


def player_country(player_id: int, players: dict) -> str:
    """Birth country code. Fetched once, then cached forever."""
    key = str(player_id)
    if key in players:
        return players[key]["country"]
    try:
        resp = requests.get(
            PLAYER_API.format(player_id=player_id), headers=HEADERS, timeout=30
        )
        resp.raise_for_status()
        p = resp.json()
        country = p.get("birthCountry") or "?"
        name = (
            f"{p.get('firstName', {}).get('default', '')} "
            f"{p.get('lastName', {}).get('default', '')}"
        ).strip()
    except requests.RequestException:
        country, name = "?", ""
    players[key] = {"country": country, "name": name}
    return country


def all_goals(landing: dict) -> list[dict]:
    """Flat list of goals with period number attached. Excludes shootout."""
    goals = []
    for period in landing.get("summary", {}).get("scoring", []):
        pd = period.get("periodDescriptor", {})
        if pd.get("periodType") == "SO":
            continue
        for goal in period.get("goals", []):
            goal = dict(goal)
            goal["_period"] = pd.get("number", 0)
            goals.append(goal)
    return goals


def analyse(game: dict, landing: dict, players: dict, cfg: dict) -> dict:
    """Compute attributes and weighted score for one game."""
    w = cfg["weights"]
    raw = game["raw"]
    goals = all_goals(landing)

    away_score = raw["awayTeam"].get("score", 0)
    home_score = raw["homeTeam"].get("score", 0)
    period_type = raw.get("periodDescriptor", {}).get("periodType", "REG")

    # Lead changes: leader flips from one team to other (not from tie).
    lead_changes = 0
    prev_leader = None
    for g in goals:
        a, h = g.get("awayScore", 0), g.get("homeScore", 0)
        leader = "away" if a > h else "home" if h > a else None
        if leader and prev_leader and leader != prev_leader:
            lead_changes += 1
        if leader:
            prev_leader = leader

    # Third-period comeback: team trailing after 2nd period wins.
    a2 = h2 = 0
    for g in goals:
        if g["_period"] <= 2:
            a2, h2 = g.get("awayScore", a2), g.get("homeScore", h2)
    trailing_after_2 = "away" if a2 < h2 else "home" if h2 < a2 else None
    winner = "away" if away_score > home_score else "home"
    comeback = trailing_after_2 is not None and winner == trailing_after_2

    # Hat trick: 3+ goals by one player.
    scorer_counts = Counter(g["playerId"] for g in goals)
    hat_tricks = sum(1 for n in scorer_counts.values() if n >= 3)

    # Penalties.
    fights = 0
    pim = 0
    for period in landing.get("summary", {}).get("penalties", []):
        for p in period.get("penalties", []):
            pim += p.get("duration") or 0
            if p.get("descKey") == "fighting":
                fights += 1
    fights //= 2  # both fighters get a major

    # Finnish points.
    finnish_points = 0
    finnish_names = set()
    for g in goals:
        ids = [g["playerId"]] + [a["playerId"] for a in g.get("assists", [])]
        for pid in ids:
            if player_country(pid, players) == "FIN":
                finnish_points += 1
                finnish_names.add(players[str(pid)]["name"])

    # Favourite team.
    fav = [t for t in (game["away"], game["home"]) if t in cfg["favouriteTeams"]]

    total_goals = away_score + home_score
    margin = abs(away_score - home_score)

    parts = {
        "goals": total_goals * w["goal"],
        "margin": w["margin1"] if margin == 1 else w["margin2"] if margin == 2 else 0,
        "overtime": w["overtime"] if period_type in ("OT", "SO") else 0,
        "shootout": w["shootout"] if period_type == "SO" else 0,
        "leadChanges": lead_changes * w["leadChange"],
        "comeback": w["thirdPeriodComeback"] if comeback else 0,
        "hatTrick": hat_tricks * w["hatTrick"],
        "fights": fights * w["fight"],
        "pim": pim * w["penaltyMinute"],
        "favourite": len(fav) * w["favouriteTeam"],
        "finnish": finnish_points * w["finnishPoint"],
    }
    score = round(sum(parts.values()), 2)

    return {
        "score": score,
        "parts": parts,
        "result": f"{game['away']} {away_score} - {home_score} {game['home']} ({period_type})",
        "leadChanges": lead_changes,
        "comeback": comeback,
        "hatTricks": hat_tricks,
        "fights": fights,
        "pim": pim,
        "finnish": sorted(finnish_names),
        "favourite": fav,
    }


def chronological_order(games: list[dict]) -> list[dict]:
    """Sort by actual start time, no scoring/weighting at all."""
    return sorted(games, key=lambda g: g["raw"].get("startTimeUTC", ""))


def write_queue(out_dir: Path, date: str, total_games: int, ordered: list[dict]) -> None:
    queue = {
        "date": date,
        "totalGames": total_games,
        "games": [
            {
                "rank": i + 1,
                "gameId": g["gameId"],
                "home": g["home"],
                "away": g["away"],
                "shortVideoId": g["shortVideoId"],
                "longVideoId": g["longVideoId"],
            }
            for i, g in enumerate(ordered)
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "queue.json").write_text(
        json.dumps(queue, indent=2), encoding="utf-8"
    )


def sync_player_html(out_dir: Path) -> None:
    """Copy the one canonical index.html into a profile folder verbatim.
    Only ever edit the root index.html by hand."""
    if out_dir == ROOT:
        return
    shutil.copyfile(ROOT / "index.html", out_dir / "index.html")


def write_debug(profile: str, date: str, ranked: list[dict]) -> None:
    debug_dir = ROOT / "debug"
    debug_dir.mkdir(exist_ok=True)
    lines = [f"Scores for {date} ({profile})", ""]
    for i, g in enumerate(ranked):
        d = g["debug"]
        lines.append(f"#{i + 1}  {d['score']:>6}  {d['result']}")
        detail = ", ".join(f"{k}={v:g}" for k, v in d["parts"].items() if v)
        lines.append(f"      {detail}")
        extras = []
        if d["finnish"]:
            extras.append("FIN: " + ", ".join(d["finnish"]))
        if d["favourite"]:
            extras.append("fav: " + ", ".join(d["favourite"]))
        if extras:
            lines.append("      " + " | ".join(extras))
        lines.append("")
    (debug_dir / f"scores-{profile}-{date}.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else yesterday_na()
    players = load_players()

    # Fetch/cache the shared game data ONCE, reused by every profile below.
    score = fetch_score(date, force=True)
    total_games = len(score.get("games", []))
    games = extract_games(score)
    games = [g for g in games if g["shortVideoId"]]  # no recap = nothing to watch
    for g in games:
        g["landing"] = fetch_landing(g["gameId"])

    # Default profile (root): no preferences, no scoring at all — just
    # the order games were actually played in.
    ordered = chronological_order(games)
    write_queue(ROOT, date, total_games, ordered)
    print(f"Date: {date}   default: {len(ordered)} of {total_games} games, chronological, no scoring")

    # Every other named profile: weighted ranking, its own folder + config.
    for profile, (folder, config_file) in PROFILES.items():
        cfg = load_config(config_file)
        for g in games:
            g["debug"] = analyse(g, g["landing"], players, cfg)
        ranked = sorted(games, key=lambda g: g["debug"]["score"], reverse=True)
        out_dir = ROOT / folder
        write_queue(out_dir, date, total_games, ranked)
        write_debug(profile, date, ranked)
        sync_player_html(out_dir)
        print(f"Date: {date}   {profile}: {len(ranked)} of {total_games} games, ranked -> {folder}/")

    save_players(players)
    print("queue.json files written (no spoilers); debug/*.txt has the breakdowns (SPOILERS)")


if __name__ == "__main__":
    main()
