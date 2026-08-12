import os
from functools import lru_cache

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


@lru_cache(maxsize=1)
def get_engine():
    database_url = os.environ["DATABASE_URL"]
    return create_engine(database_url, pool_pre_ping=True)


def record_sync(engine, resource_type, when):
    """Stamps etl_sync_state so the app's data_access cache can detect that
    a write happened -- called by both the backfill and incremental scripts
    on success. The app doesn't care which script wrote it, only the latest
    timestamp across all resource_types (see get_last_sync_time)."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO etl_sync_state (resource_type, last_synced_at)
            VALUES (:rt, :ts)
            ON CONFLICT (resource_type) DO UPDATE SET last_synced_at = :ts
        """), {"rt": resource_type, "ts": when})


def get_last_sync_time(engine):
    """Latest last_synced_at across every ETL resource_type, or None if
    etl_sync_state is empty (e.g. a freshly reset schema with no recorded
    sync yet). Used by data_access.py to decide whether cached DataFrames
    are still current."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT MAX(last_synced_at) FROM etl_sync_state")).scalar()


def normalize_ids(df):
    """Wyscout uses 0 as a sentinel for "no player"/"unknown" across every
    *_id column (seen in both the CSV exports and the live API) -- treat it
    as NULL rather than a bogus foreign key target. Also coerces to nullable
    Int64 in case a column arrived as float (e.g. "61585.0")."""
    for col in df.columns:
        if col.endswith("_id") and pd.api.types.is_numeric_dtype(df[col]):
            values = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            df[col] = values.mask(values == 0)
    return df


def write_table(table_name, rows, **to_sql_kwargs):
    """Shared insert helper for ETL scripts (seed_db.py's CSV path and the
    Wyscout backfill/incremental scripts): normalizes *_id sentinels, then
    appends to Postgres."""
    if not rows:
        print(f"  {table_name}: nothing to write")
        return
    df = pd.DataFrame(rows)
    df = normalize_ids(df)
    df.to_sql(table_name, get_engine(), if_exists="append", index=False, **to_sql_kwargs)
    print(f"  {table_name}: wrote {len(df)} rows")
