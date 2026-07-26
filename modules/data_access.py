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


# NOTE: full-table SELECT; revisit with WHERE-clause pushdown once event_data
# grows beyond one season. Not cached since each session/tab filters it differently.
def load_event_data() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM event_data", get_engine())


def load_team_player_duels() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM team_player_match_duels", get_engine())
