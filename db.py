"""Read-only database access. Only queries from queries.QUERIES can be run."""

import os

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.types.numeric import FloatLoader

from queries import QUERIES

load_dotenv()


def run_query(name: str) -> pd.DataFrame:
    """Run a predefined query by name and return the result as a DataFrame."""
    if name not in QUERIES:
        raise ValueError(f"Unknown query: {name}")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")

    # read_only=True makes PostgreSQL reject any INSERT/UPDATE/DELETE/DDL.
    with psycopg.connect(database_url) as conn:
        conn.read_only = True
        # Load NUMERIC as float instead of Decimal, so pandas and charts work directly.
        conn.adapters.register_loader("numeric", FloatLoader)
        with conn.cursor() as cur:
            cur.execute(QUERIES[name]["sql"])
            columns = [col.name for col in cur.description]
            rows = cur.fetchall()

    return pd.DataFrame(rows, columns=columns)
