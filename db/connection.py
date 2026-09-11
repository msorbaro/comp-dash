import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    url = os.environ["DATABASE_URL"]
    # Supabase's "Transaction pooler" (PgBouncer, transaction mode) doesn't support
    # server-side prepared statements across pooled connections — disable them.
    return psycopg.connect(url, autocommit=False, prepare_threshold=None)
