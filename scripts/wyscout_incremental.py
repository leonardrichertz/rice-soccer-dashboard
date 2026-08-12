"""Incremental sync from the Wyscout API.

/updatedobjects (the officially documented "what changed" endpoint) returns
403 Forbidden for this account's API key -- a permissions/subscription-tier
limitation, not something fixable in code. Instead, this script polls each
tracked season's match list on every run and diffs it against what's already
in the database: a match gets (re-)pulled if it's brand new, or if it just
transitioned to "Played" since the last check.

Known limitation from not having /updatedobjects: a score/stat *correction*
to a match that was already "Played" the last time this ran won't be
detected (there's no cheap way to tell "did this specific match change"
without the real changed-objects endpoint). If broader API access is granted
later, swap _find_changed_match_ids() for a real /updatedobjects poll and
this limitation goes away.

A single run_incremental_sync() function with no CLI-specific logic, so it's
directly reusable as a future Lambda handler -- only the __main__ CLI wrapper
and scripts/run_wyscout_scheduler.py are throwaway once that exists.

Usage:
    python scripts/wyscout_incremental.py [--matches 5786657,5786002]
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import bindparam, text

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules import wyscout_client, wyscout_transform as wt  # noqa: E402
from modules.db import get_engine, record_sync, write_table  # noqa: E402

COMPETITION_ID = 43229  # NCAA D1 American Athletic (W)
# Same seasons tracked by wyscout_backfill.py. Update this (or add the new
# season's ID) once a new season actually starts producing matches --
# 2026 Fall (192811) returns an empty match list today, so including it
# early would just be a harmless no-op call, but it's left out for now to
# keep this script's tracked seasons explicit and matching the backfill.
SEASON_IDS = [191846, 190993, 190152]

SYNC_RESOURCE = "wyscout_incremental"

# Tables scoped by wy_match_id, safe to delete-then-reinsert for just the
# matches being refreshed (nothing else has a hard FK dependency on their rows).
MATCH_SCOPED_TABLES = ["event_data", "team_player_match_duels", "player_match_mapping", "match_data"]


def _dedupe(rows, key_cols):
    seen = set()
    result = []
    for row in rows:
        key = tuple(row[c] for c in key_cols)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def _record_run(engine, when):
    record_sync(engine, SYNC_RESOURCE, when)


def _existing_match_status(engine, match_ids):
    if not match_ids:
        return {}
    stmt = text("SELECT wy_match_id, status FROM match_data WHERE wy_match_id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt, {"ids": list(match_ids)}).fetchall()
    return dict(rows)


def _find_changed_match_ids(engine, season_ids):
    """A match needs (re-)pulling if it's Played now but wasn't already
    on file as Played -- covers brand-new matches and matches that just
    finished since the last run. Cheap: only ever calls the season match
    list, never per-match detail, during detection."""
    changed = []
    for season_id in season_ids:
        matches = wyscout_client.get_all_pages(f"/seasons/{season_id}/matches", "matches")
        match_ids = [m["matchId"] for m in matches]
        existing_status = _existing_match_status(engine, match_ids)

        season_changed = [
            m["matchId"] for m in matches
            if m.get("status") == "Played" and existing_status.get(m["matchId"]) != "Played"
        ]
        changed.extend(season_changed)
        print(f"Season {season_id}: {len(matches)} matches, {len(season_changed)} newly Played")

    return changed


def run_incremental_sync(match_ids_override=None):
    """If match_ids_override is given, skips the match-list diff and
    force-refreshes exactly those matches instead -- used for testing this
    path without waiting for a real match to complete."""
    engine = get_engine()
    run_started_at = datetime.utcnow()

    if match_ids_override is not None:
        changed_match_ids = set(match_ids_override)
        print(f"Forced refresh of {len(changed_match_ids)} match(es): {sorted(changed_match_ids)}")
    else:
        changed_match_ids = set(_find_changed_match_ids(engine, SEASON_IDS))
        print(f"{len(changed_match_ids)} changed match(es) total: {sorted(changed_match_ids)}")

    if not changed_match_ids:
        _record_run(engine, run_started_at)
        print("No changes.")
        return

    match_rows, mapping_rows, duel_rows, event_rows = [], [], [], []
    player_team_observations = []

    for match_id in changed_match_ids:
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
            print(f"  match {match_id}: SKIPPED ({exc})")
            continue

        match_rows.append(match_row)
        mapping_rows.extend(lineup_rows)
        player_team_observations.extend(observations)
        duel_rows.extend(match_duel_rows)
        event_rows.extend(match_event_rows)
        print(f"  match {match_id}: refreshed ({len(match_event_rows)} events)")

    if not match_rows:
        print("Every changed match failed to refresh -- leaving etl_sync_state unrecorded so they're retried next run.")
        return

    # Harvest player names directly from the events already fetched above
    # (every event carries player_name/pass_recipient_name) rather than an
    # extra per-player /players/{id} call -- that individual endpoint 400s
    # for some players (observed directly), and this way needs no extra
    # requests at all for anyone who touched the ball.
    player_names_by_id = {}
    for row in event_rows:
        if row.get("wy_player_id") and row.get("player_name"):
            player_names_by_id[row["wy_player_id"]] = row["player_name"]
        if row.get("pass_recipient_id") and row.get("pass_recipient_name"):
            player_names_by_id[row["pass_recipient_id"]] = row["pass_recipient_name"]

    latest_team_by_player = dict(player_team_observations)

    # Anyone still unnamed (e.g. an unused substitute who never touched the
    # ball) falls back to whatever name is already on file for them.
    still_unnamed = [pid for pid in latest_team_by_player if pid not in player_names_by_id]
    if still_unnamed:
        stmt = text("SELECT wy_player_id, wy_player_name FROM player_data WHERE wy_player_id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        )
        with engine.connect() as conn:
            for pid, name in conn.execute(stmt, {"ids": still_unnamed}):
                player_names_by_id[pid] = name

    player_rows = [
        {"wy_player_id": pid, "wy_player_name": player_names_by_id.get(pid), "wy_team_id": tid}
        for pid, tid in latest_team_by_player.items()
        if player_names_by_id.get(pid) is not None
    ]
    skipped_unnamed = [pid for pid in latest_team_by_player if player_names_by_id.get(pid) is None]
    if skipped_unnamed:
        print(f"  player_data: no name available for {skipped_unnamed}, skipping those rows (existing rows, if any, are left as-is)")

    successfully_touched_ids = {r["wy_match_id"] for r in match_rows}

    print("Replacing existing rows for refreshed matches...")
    for table_name in MATCH_SCOPED_TABLES:
        _delete_match_rows(engine, table_name, successfully_touched_ids)

    print("Writing refreshed data...")
    _upsert_player_rows(engine, player_rows)
    write_table("match_data", match_rows)
    write_table("player_match_mapping", _dedupe(mapping_rows, ["wy_player_id", "wy_match_id"]))
    write_table("team_player_match_duels", _dedupe(duel_rows, ["wy_team_id", "wy_match_id", "wy_player_id"]))
    write_table("event_data", event_rows, chunksize=500, method="multi")

    _record_run(engine, run_started_at)
    print("Incremental sync complete.")


def _delete_match_rows(engine, table_name, match_ids):
    if not match_ids:
        return
    stmt = text(f"DELETE FROM {table_name} WHERE wy_match_id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    with engine.begin() as conn:
        conn.execute(stmt, {"ids": list(match_ids)})


def _upsert_player_rows(engine, rows):
    if not rows:
        return
    stmt = text("""
        INSERT INTO player_data (wy_player_id, wy_player_name, wy_team_id)
        VALUES (:wy_player_id, :wy_player_name, :wy_team_id)
        ON CONFLICT (wy_player_id) DO UPDATE SET
            wy_player_name = EXCLUDED.wy_player_name,
            wy_team_id = EXCLUDED.wy_team_id
    """)
    with engine.begin() as conn:
        conn.execute(stmt, rows)
    print(f"  player_data: upserted {len(rows)} rows")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches", type=str, default=None,
                         help="Comma-separated match IDs to force-refresh, bypassing the match-list diff (for testing).")
    args = parser.parse_args()

    match_ids_override = [int(m) for m in args.matches.split(",")] if args.matches else None
    run_incremental_sync(match_ids_override=match_ids_override)


if __name__ == "__main__":
    main()
