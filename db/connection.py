import os
import threading
import time

import psycopg
from dotenv import load_dotenv

load_dotenv()

# Supabase's free-tier pooler has a real, fairly low ceiling on concurrent
# connections - confirmed directly: opening 30 raw connections at once from a
# single process already produced a couple of
# "failed to check out a connection after multiple retries" (ECHECKOUTRETRIES)
# failures. The backend's warm-cache thread pool (main.py) runs up to 9
# brand/channel computations concurrently, each able to open its own
# connection for a bulk-image query - bursty enough to blow past that
# ceiling. Nothing here retried, so losing that race became a PERMANENT
# cache miss for that one brand/channel until the next 8-minute cycle - which
# then reliably lost the SAME race again, since task submission order (and
# so which connections open first vs. under the most contention) is the same
# every cycle. This is why it was always the same handful of brands stuck on
# 503, not a random rotating set.
#
# A semaphore smooths the burst by queuing extra callers instead of letting
# them all hit the pooler at once - tied to the connection's own close(), not
# just the connect() call, so it actually bounds concurrently-OPEN
# connections rather than just concurrent connect attempts. The retry loop
# is a safety net for whatever contention still gets through.
_CONN_SEMAPHORE = threading.Semaphore(6)
_MAX_CONNECT_ATTEMPTS = 4


def get_conn():
    url = os.environ["DATABASE_URL"]
    # Supabase's "Transaction pooler" (PgBouncer, transaction mode) doesn't support
    # server-side prepared statements across pooled connections — disable them.
    _CONN_SEMAPHORE.acquire()
    conn = None
    last_err = None
    try:
        for attempt in range(_MAX_CONNECT_ATTEMPTS):
            try:
                conn = psycopg.connect(url, autocommit=False, prepare_threshold=None)
                break
            except psycopg.Error as e:
                last_err = e
                time.sleep(0.5 * (attempt + 1))
        if conn is None:
            raise last_err
    except BaseException:
        _CONN_SEMAPHORE.release()
        raise

    # Release the permit whenever this specific connection actually closes -
    # via `with get_conn() as conn:` (psycopg's own __exit__ calls close()),
    # or an explicit conn.close() - not merely when connect() returns, so the
    # semaphore bounds real concurrently-open connections.
    released = threading.Event()
    real_close = conn.close

    def _close_and_release(*args, **kwargs):
        try:
            return real_close(*args, **kwargs)
        finally:
            if not released.is_set():
                released.set()
                _CONN_SEMAPHORE.release()

    conn.close = _close_and_release
    return conn
