from functools import lru_cache

import pandas as pd

from .db import get_engine


@lru_cache(maxsize=1)
def load_team_data() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM team_data", get_engine())


@lru_cache(maxsize=1)
def load_match_data() -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM match_data", get_engine())
    # Postgres returns label_date as datetime.date; every UI call site uses it
    # as a plain dropdown label string, same as the old CSV reads did.
    df["label_date"] = df["label_date"].astype(str)
    return df


@lru_cache(maxsize=1)
def load_player_data() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM player_data", get_engine())


@lru_cache(maxsize=1)
def load_player_match_map() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM player_match_mapping", get_engine())


# Cached like the reference tables above: every tab filters this same full
# table down to its own matches/players afterward in-memory, so caching the
# raw load doesn't cost per-session flexibility -- it just avoids re-querying
# the same ~100k-row table once per tab, per session (previously this alone
# added 10+ seconds to every new session's startup).
# NOTE: revisit with WHERE-clause pushdown if event_data grows past one season.
@lru_cache(maxsize=1)
def load_event_data() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM event_data", get_engine())


@lru_cache(maxsize=1)
def load_team_player_duels() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM team_player_match_duels", get_engine())
