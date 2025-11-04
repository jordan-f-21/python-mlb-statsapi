from __future__ import annotations

from typing import Optional, List, Dict, Any
from flask import Flask, render_template, request, redirect, url_for, flash

# Try primary library first
try:
    import mlbstatsapi
    mlb = mlbstatsapi.Mlb()
except Exception:
    mlbstatsapi = None
    mlb = None

# Fallback library (dict-based, resilient to new fields)
try:
    import statsapi
except Exception:
    statsapi = None  # type: ignore


app = Flask(__name__)
app.secret_key = "change-me"  # replace in production


# -----------------------------
# Helpers: player resolution
# -----------------------------
def resolve_player_id(name: str) -> Optional[int]:
    """Return a single player ID for a given name (first match)."""
    # Prefer mlbstatsapi if available
    if mlbstatsapi and mlb:
        try:
            ids = mlb.get_people_id(name)  # list[int]
            if ids:
                return int(ids[0])
        except Exception:
            pass

    # Fallback to statsapi
    if statsapi:
        try:
            # returns list of dicts with keys like 'id' / 'player_id' / 'fullName'
            matches = statsapi.lookup_player(name)
            if matches:
                candidate = matches[0]
                # statsapi has used 'id' historically; keep both just in case
                return int(candidate.get("id") or candidate.get("player_id"))
        except Exception:
            pass

    return None


def get_display_name(player_id: int) -> str:
    """Nice display name for the player."""
    # Try mlbstatsapi
    if mlbstatsapi and mlb:
        try:
            people = mlb.get_people(personIds=[player_id])
            if people and hasattr(people[0], "fullName"):
                return people[0].fullName
        except Exception:
            pass

    # Fallback to statsapi
    if statsapi:
        try:
            recs = statsapi.lookup_player(player_id)
            if recs:
                return recs[0].get("fullName") or recs[0].get("name_display_first_last") or str(player_id)
        except Exception:
            pass

    return str(player_id)


# -----------------------------
# Stats fetchers (primary + fallback)
# -----------------------------
def _get_hitting_stats_mlbstatsapi(player_id: int, season: Optional[int]) -> List[Dict[str, Any]]:
    """Primary path using python-mlb-statsapi. May raise exceptions if schema changes."""
    if not (mlbstatsapi and mlb):
        raise RuntimeError("mlbstatsapi not available")

    scope = "career" if season is None else "season"
    if season is None:
        stat_dict = mlb.get_player_stats(player_id, stats=["career"], groups=["hitting"])
    else:
        stat_dict = mlb.get_player_stats(player_id, stats=["season"], groups=["hitting"], season=season)

    group_block = stat_dict.get("hitting", {}).get(scope)
    if not group_block:
        return []

    rows: List[Dict[str, Any]] = []
    for split in group_block.splits:
        # Convert dataclass-ish object to dict safely
        row = {}
        for k, v in split.stat.__dict__.items():
            if not k.startswith("_"):
                row[k] = v
        if getattr(split, "team", None):
            row["team_name"] = getattr(split.team, "name", None)
        if getattr(split, "season", None):
            row["season"] = split.season
        rows.append(row)
    return rows


def _get_hitting_stats_statsapi(player_id: int, season: Optional[int]) -> List[Dict[str, Any]]:
    """Fallback path using MLB-StatsAPI (dict-based)."""
    if not statsapi:
        raise RuntimeError("statsapi not available")
    # Call the stats API using the current parameter name
    if season is None:
        data = statsapi.player_stat_data(personId=player_id, group="hitting", type="career")
    else:
        data = statsapi.player_stat_data(personId=player_id, group="hitting", type="season", season=season)

    rows: List[Dict[str, Any]] = []

    # Two possible shapes are returned by different statsapi versions:
    # 1) dict-style with keys like stats -> {career: {splits: [...]}, season: {...}}
    # 2) list-style: stats -> [ { 'type': 'Season', 'group': 'Hitting', 'season': '2022', 'stats': {...} }, ...]

    stats_block = data.get("stats")

    # Handle older dict-based shape first
    if isinstance(stats_block, dict):
        if season is None:
            splits = stats_block.get("career", {}).get("splits", [])
        else:
            splits = stats_block.get("season", {}).get("splits", [])

        for s in splits:
            stat = s.get("stat", {}) or {}
            row = dict(stat)
            team = s.get("team")
            if isinstance(team, dict):
                row["team_name"] = team.get("name")
            if "season" in s:
                row["season"] = s["season"]
            rows.append(row)

        return rows

    # Handle list-style shape
    if isinstance(stats_block, list):
        for sg in stats_block:
            # sg is expected to be a dict with keys like 'type', 'group', 'season', 'stats'
            grp = str(sg.get("group") or "").lower()
            typ = str(sg.get("type") or "").lower()

            # Only consider hitting group entries
            if "hitting" not in grp:
                continue

            # For career mode, accept entries where type contains 'career'
            if season is None and "career" not in typ:
                continue

            # For season mode, accept entries where type contains 'season' and season matches (if provided)
            if season is not None and "season" not in typ:
                continue
            if season is not None:
                sg_season = sg.get("season")
                # Some responses may store season as int or string
                if sg_season is not None and int(sg_season) != int(season):
                    continue

            stat = sg.get("stats") or {}
            # stat may already be a dict of stat fields
            row = dict(stat)
            if sg.get("season") is not None:
                row["season"] = sg.get("season")
            # team info may be nested in sg under currentTeam or similar; try common keys
            team_name = None
            if isinstance(sg.get("currentTeam"), dict):
                team_name = sg.get("currentTeam", {}).get("name")
            if not team_name and isinstance(sg.get("team"), dict):
                team_name = sg.get("team", {}).get("name")
            if team_name:
                row["team_name"] = team_name

            rows.append(row)

        return rows

    # Unknown shape -> return empty
    return rows


def get_hitting_stats(player_id: int, season: Optional[int]) -> List[Dict[str, Any]]:
    """
    Unified entry point:
      1) try python-mlb-statsapi (fast/structured)
      2) on error, fall back to MLB-StatsAPI (dicts, resilient)
    """
    # Try primary
    try:
        return _get_hitting_stats_mlbstatsapi(player_id, season)
    except Exception as e_primary:
        # Fall back if we can
        try:
            return _get_hitting_stats_statsapi(player_id, season)
        except Exception as e_fallback:
            # Raise combined error so the UI can show something helpful
            raise RuntimeError(f"Primary failed: {e_primary}; Fallback failed: {e_fallback}")


# -----------------------------
# Flask routes
# -----------------------------
@app.get("/")
def index():
    return render_template("index.html")


@app.post("/player")
def player_lookup():
    name = request.form.get("name", "").strip()
    mode = request.form.get("mode", "career")
    year_raw = request.form.get("year", "").strip()

    if not name:
        flash("Please enter a player name.")
        return redirect(url_for("index"))

    season: Optional[int] = None
    if mode == "season":
        if not year_raw.isdigit():
            flash("Please enter a valid season year (e.g., 2022) or choose Career.")
            return redirect(url_for("index"))
        season = int(year_raw)

    player_id = resolve_player_id(name)
    if not player_id:
        flash(f"No player found for '{name}'. Try a more specific name.")
        return redirect(url_for("index"))

    try:
        rows = get_hitting_stats(player_id, season)
    except Exception as e:
        flash(f"Could not fetch stats: {e}")
        return redirect(url_for("index"))

    if not rows:
        flash("No stats found for that selection.")
        return redirect(url_for("index"))

    display_name = get_display_name(player_id)

    return render_template(
        "player.html",
        player_name=display_name,
        player_id=player_id,
        mode=mode,
        season=season,
        rows=rows,
    )


if __name__ == "__main__":
    # Tip: set host="0.0.0.0" if you want to reach it from your phone on the LAN
    app.run(debug=True)