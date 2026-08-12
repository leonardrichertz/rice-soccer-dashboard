"""Full pull from the Wyscout API for a competition's seasons: teams,
players, matches, lineups, advanced-stats duels, and events. Structured as a
single run_backfill() function with no CLI-specific logic, so it's directly
reusable as a future Lambda handler -- only the __main__ CLI wrapper below
is throwaway (that part gets replaced by an EventBridge-triggered invocation
later, per the original ETL handover doc's intent).

Usage:
    python scripts/wyscout_backfill.py [--reset] [--seasons 191846,190993,190152] [--matches 5786657]
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules import wyscout_client, wyscout_transform as wt  # noqa: E402
from modules.db import get_engine, record_sync, write_table  # noqa: E402

COMPETITION_ID = 43229  # NCAA D1 American Athletic (W)
# The 3 most recently *completed* seasons -- 2026 Fall exists but hasn't
# started yet, so there's nothing to pull for it.
SEASON_IDS = [191846, 190993, 190152]  # 2025 Fall, 2024 Fall, 2023 Fall

SYNC_RESOURCE = "wyscout_backfill"

SCHEMA_FILE = Path(__file__).parent.parent / "db" / "schema.sql"

TABLES_IN_RESET_ORDER = [
    "event_data", "team_player_match_duels", "player_match_mapping",
    "player_data", "match_data", "team_data", "etl_sync_state",
]


def reset_schema(engine):
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {', '.join(TABLES_IN_RESET_ORDER)} CASCADE"))


def apply_schema(engine):
    ddl = SCHEMA_FILE.read_text()
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _dedupe(rows, key_cols):
    seen = set()
    result = []
    for row in rows:
        key = tuple(row[c] for c in key_cols)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def run_backfill(competition_id, season_ids, match_ids_filter=None):
    """Pulls teams, players, matches, lineups, duels, and events for every
    given season of a competition, and writes them into Postgres. If
    match_ids_filter is given (a set of match IDs), only those matches are
    pulled -- used for a small-subset test before a full run.

    Seasons are processed oldest-to-newest so that a player's resolved team
    (last lineup observation wins) reflects their most recent team, not
    whichever season happens to be iterated last.
    """
    teams_by_id = {}
    player_names_by_id = {}
    player_team_observations = []  # [(player_id, team_id), ...], appended in chronological order
    match_rows = []
    mapping_rows = []
    duel_rows = []
    event_rows = []

    for season_id in sorted(season_ids):
        print(f"Season {season_id}: fetching teams/players/matches...")
        teams = wyscout_client.get_all_pages(f"/seasons/{season_id}/teams", "teams")
        for t in teams:
            row = wt.transform_team(t)
            teams_by_id[row["wy_team_id"]] = row

        players = wyscout_client.get_all_pages(f"/seasons/{season_id}/players", "players")
        for p in players:
            row = wt.transform_player(p)
            player_names_by_id[row["wy_player_id"]] = row["wy_player_name"]

        matches = wyscout_client.get_all_pages(f"/seasons/{season_id}/matches", "matches")
        match_ids = [m["matchId"] for m in matches if m.get("status") == "Played"]
        if match_ids_filter is not None:
            match_ids = [m for m in match_ids if m in match_ids_filter]

        print(f"Season {season_id}: {len(match_ids)} played matches to pull")

        for i, match_id in enumerate(match_ids):
            # One bad match (Wyscout returns "temporary unavailable" for a
            # small fraction of played matches) must not lose every other
            # match's worth of API calls already made this run -- fetch and
            # transform everything for this match first, and only merge it
            # into the accumulators if the whole match succeeds.
            try:
                raw_match = wyscout_client.get(f"/matches/{match_id}")
                match_row = wt.transform_match(raw_match)

                lineup_rows, observations = wt.transform_lineup_rows(raw_match)

                team_of_player = dict(observations)
                adv = wyscout_client.get(f"/matches/{match_id}/advancedstats/players")
                match_duel_rows = wt.transform_duels(adv, team_of_player)

                raw_events = wyscout_client.get(f"/matches/{match_id}/events")["events"]
                match_event_rows = [wt.transform_event(e, match_row) for e in raw_events]
            except Exception as exc:
                print(f"  [{i + 1}/{len(match_ids)}] match {match_id}: SKIPPED ({exc})")
                continue

            match_rows.append(match_row)
            mapping_rows.extend(lineup_rows)
            player_team_observations.extend(observations)
            duel_rows.extend(match_duel_rows)
            event_rows.extend(match_event_rows)

            print(f"  [{i + 1}/{len(match_ids)}] match {match_id}: "
                  f"{len(raw_events)} events, {len(lineup_rows)} lineup rows")

    # player_data is derived from actual lineup/bench observations, not from
    # the season's registered-players list directly -- this guarantees every
    # wy_player_id/pass_recipient_id referenced by an event or duel row (both
    # FK-constrained to player_data) is covered, since anyone who generates
    # an event was necessarily in a lineup. Last observation wins per player
    # (seasons processed oldest-to-newest above), giving their most recent team.
    latest_team_by_player = dict(player_team_observations)
    player_rows = [
        {
            "wy_player_id": player_id,
            "wy_player_name": player_names_by_id.get(player_id),
            "wy_team_id": team_id,
        }
        for player_id, team_id in latest_team_by_player.items()
    ]

    for row in mapping_rows:
        row["wy_player_name"] = player_names_by_id.get(row["wy_player_id"])

    print("\nWriting to database...")
    write_table("team_data", list(teams_by_id.values()))
    write_table("match_data", match_rows)
    write_table("player_data", player_rows)
    write_table("player_match_mapping", _dedupe(mapping_rows, ["wy_player_id", "wy_match_id"]))
    write_table("team_player_match_duels", _dedupe(duel_rows, ["wy_team_id", "wy_match_id", "wy_player_id"]))
    write_table("event_data", event_rows, chunksize=500, method="multi")

    print("\nBackfill complete.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop and recreate tables before backfilling.")
    parser.add_argument("--seasons", type=str, default=None, help="Comma-separated season IDs to override the default 3.")
    parser.add_argument("--matches", type=str, default=None, help="Comma-separated match IDs to limit the pull to (for testing).")
    args = parser.parse_args()

    season_ids = [int(s) for s in args.seasons.split(",")] if args.seasons else SEASON_IDS
    match_ids_filter = {int(m) for m in args.matches.split(",")} if args.matches else None

    engine = get_engine()
    run_started_at = datetime.utcnow()
    if args.reset:
        print("Dropping existing tables...")
        reset_schema(engine)
    print("Applying schema...")
    apply_schema(engine)

    run_backfill(COMPETITION_ID, season_ids, match_ids_filter=match_ids_filter)
    record_sync(engine, SYNC_RESOURCE, run_started_at)


if __name__ == "__main__":
    main()
