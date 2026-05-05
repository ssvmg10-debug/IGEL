import psycopg2
import psycopg2.pool
from contextlib import contextmanager
from knowledge_base.config import cfg

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool(minconn: int = 2, maxconn: int = 10) -> None:
    global _pool
    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn, maxconn,
        host=cfg.DB_HOST,
        port=cfg.DB_PORT,
        dbname=cfg.DB_NAME,
        user=cfg.DB_USER,
        password=cfg.DB_PASSWORD,
        connect_timeout=10,
    )


@contextmanager
def get_conn():
    if _pool is None:
        init_pool()
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def test_connection() -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"  Connected: {version[:60]}")
        return True
    except Exception as e:
        print(f"  DB connection failed: {e}")
        return False


def close_pool() -> None:
    if _pool:
        _pool.closeall()
