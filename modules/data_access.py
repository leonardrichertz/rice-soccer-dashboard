from functools import wraps

import pandas as pd

from .db import get_engine, get_last_sync_time

_cache = {}


def _versioned_cache(fn):
    """Like @lru_cache(maxsize=1), but invalidates when etl_sync_state's
    latest timestamp moves forward, instead of only on process restart --
    lets a long-running app pick up fresh ETL writes (backfill or
    incremental sync) without needing to be restarted. The version check
    itself is a cheap single-row lookup, so it's worth paying on every call
    to avoid re-querying the big tables (event_data especially) unless the
    data actually changed."""
    @wraps(fn)
    def wrapper():
        version = get_last_sync_time(get_engine())
        cached = _cache.get(fn.__name__)
        if cached is not None and cached[0] == version:
            return cached[1]
        result = fn()
        _cache[fn.__name__] = (version, result)
        return result
    return wrapper


@_versioned_cache
def load_team_data() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM team_data", get_engine())


@_versioned_cache
def load_match_data() -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM match_data", get_engine())
    # Postgres returns label_date as datetime.date; every UI call site uses it
    # as a plain dropdown label string, same as the old CSV reads did.
    df["label_date"] = df["label_date"].astype(str)
    return df


@_versioned_cache
def load_player_data() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM player_data", get_engine())


@_versioned_cache
def load_player_match_map() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM player_match_mapping", get_engine())


# Cached like the reference tables above: every tab filters this same full
# table down to its own matches/players afterward in-memory, so caching the
# raw load doesn't cost per-session flexibility -- it just avoids re-querying
# the same ~100k-row table once per tab, per session (previously this alone
# added 10+ seconds to every new session's startup).
# NOTE: revisit with WHERE-clause pushdown if event_data grows past one season.
@_versioned_cache
def load_event_data() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM event_data", get_engine())


@_versioned_cache
def load_team_player_duels() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM team_player_match_duels", get_engine())


# Friendly display names for known season IDs -- match_data only stores the
# raw Wyscout season ID, not a human-readable name. Update this alongside
# scripts/wyscout_backfill.py's SEASON_IDS when a new season gets backfilled.
SEASON_NAMES = {
    191846: "2025 Fall",
    190993: "2024 Fall",
    190152: "2023 Fall",
}


def get_season_choices():
    """Distinct seasons actually present in match_data, newest first. Falls
    back to showing the raw ID for any season not in SEASON_NAMES yet."""
    df = load_match_data()
    season_ids = sorted(df["wy_season_id"].dropna().unique().astype(int), reverse=True)
    return {str(sid): SEASON_NAMES.get(sid, str(sid)) for sid in season_ids}
