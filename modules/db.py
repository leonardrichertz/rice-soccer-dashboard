import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()


@lru_cache(maxsize=1)
def get_engine():
    database_url = os.environ["DATABASE_URL"]
    return create_engine(database_url, pool_pre_ping=True)
