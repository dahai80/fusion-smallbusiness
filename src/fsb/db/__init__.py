import logging

from fsb.config import fsb_config

logger = logging.getLogger(__name__)


def make_store():
    backend = (fsb_config.DB_BACKEND or "sqlite").lower()
    if backend == "postgres":
        from fsb.db.pg_store import PostgresStore

        if not fsb_config.PG_DSN:
            raise ValueError("FSB_DB_BACKEND=postgres requires FSB_PG_DSN")
        logger.info("store backend: postgres (pool=%d)", fsb_config.PG_POOL_SIZE)
        return PostgresStore(dsn=fsb_config.PG_DSN, pool_size=fsb_config.PG_POOL_SIZE)
    from fsb.db.store import Store

    logger.info("store backend: sqlite (path=%s pool=%d)", fsb_config.DB_PATH, fsb_config.DB_POOL_SIZE)
    return Store(db_path=fsb_config.DB_PATH)
