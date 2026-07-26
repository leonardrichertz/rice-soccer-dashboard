"""Seeding tool: creates the schema and loads whatever CSVs are currently in
data/ into Postgres. Not part of the running app, and not the future
automated Wyscout pipeline -- this is the manual load step for whatever
export you've dropped in data/ locally.

Usage:
    python scripts/seed_db.py [--reset]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.db import get_engine  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data"
SCHEMA_FILE = Path(__file__).parent.parent / "db" / "schema.sql"
CSV_PREFIX = "american_athletic_womens_soccer_fall_2025_"

BOOL_COLUMNS = [
    "pass_accurate",
    "shot_is_goal",
    "shot_on_target",
    "ground_duel_kept_possession",
    "ground_duel_progressed_with_ball",
    "ground_duel_recovered_possession",
    "ground_duel_stopped_progress",
    "ground_duel_take_on",
    "aerial_duel_first_touch",
    "infraction_yellow_card",
    "infraction_red_card",
    "possession_attack_with_goal",
    "possession_attack_with_shot",
    "possession_attack_with_shot_on_goal",
]

# (csv suffix, table name), in FK-safe load order
TABLES = [
    ("team_data", "team_data"),
    ("match_data", "match_data"),
    ("player_data", "player_data"),
    ("player_match_mapping", "player_match_mapping"),
    ("team_player_match_duels", "team_player_match_duels"),
    ("event_data_selected_cols", "event_data"),
]


def reset_schema(engine):
    table_names = [table for _, table in reversed(TABLES)]
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {', '.join(table_names)} CASCADE"))


def apply_schema(engine):
    ddl = SCHEMA_FILE.read_text()
    with engine.begin() as conn:
        conn.execute(text(ddl))


def normalize_booleans(df: pd.DataFrame) -> pd.DataFrame:
    for col in BOOL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: None if pd.isna(v) else str(v).upper() == "TRUE"
            )
    return df


def normalize_ids(df: pd.DataFrame) -> pd.DataFrame:
    # Source exports are inconsistent about whether *_id columns come through
    # as int64 or float64 (e.g. team_data.wy_team_id arrives as "61585.0").
    # Every *_id column in this schema is an integer column, so coerce them
    # all the same way -- pandas' nullable Int64 keeps missing IDs as real
    # NULLs instead of NaN, which plain int64 can't represent.
    #
    # Wyscout also uses 0 as a sentinel for "no player"/"unknown" across every
    # *_id column observed (wy_player_id, pass_recipient_id, ground_duel_opponent_id,
    # etc.) -- treat it as a real NULL rather than a bogus foreign key target.
    for col in df.columns:
        if col.endswith("_id") and pd.api.types.is_numeric_dtype(df[col]):
            values = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            df[col] = values.mask(values == 0)
    return df


def load_tables(engine):
    for csv_suffix, table_name in TABLES:
        csv_path = DATA_DIR / f"{CSV_PREFIX}{csv_suffix}.csv"
        df = pd.read_csv(csv_path)
        df = normalize_booleans(df)
        df = normalize_ids(df)

        if table_name == "event_data" and "wy_event_id" in df.columns:
            if not df["wy_event_id"].is_unique:
                raise ValueError(
                    "wy_event_id is not unique in the source CSV -- schema.sql "
                    "assumes it as a primary key. Switch event_data.wy_event_id "
                    "to a generated surrogate key before seeding this data."
                )

        # chunksize keeps (rows * columns) per INSERT under Postgres's 65535
        # bound-parameter limit -- event_data alone is ~100k rows x 98 cols.
        df.to_sql(
            table_name, engine, if_exists="append", index=False,
            chunksize=500, method="multi",
        )
        print(f"  {table_name}: loaded {len(df)} rows from {csv_path.name}")


def print_row_counts(engine):
    print("\nRow counts:")
    with engine.connect() as conn:
        for _, table_name in TABLES:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            print(f"  {table_name}: {count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing tables before recreating/seeding them.",
    )
    args = parser.parse_args()

    engine = get_engine()

    if args.reset:
        print("Dropping existing tables...")
        reset_schema(engine)

    print("Applying schema...")
    apply_schema(engine)

    print("Loading CSVs into tables...")
    load_tables(engine)

    print_row_counts(engine)


if __name__ == "__main__":
    main()
