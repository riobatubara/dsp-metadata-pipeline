from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from src.common.config import settings
from src.common.logging import logger


def create_database_engine() -> Engine:
    """Create a SQLAlchemy engine for PostgreSQL."""

    database_url = (
        f"postgresql+psycopg2://"
        f"{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}"
        f"/{settings.postgres_db}"
    )

    logger.info(
        "Creating database engine: %s:%s/%s",
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_db,
    )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
    )


engine = create_database_engine()


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    """
    Provide a database connection.

    The connection is automatically closed after use.
    Transactions are committed on success and rolled back on failure.
    """
    connection = engine.connect()

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        logger.exception("Database transaction failed")
        raise
    finally:
        connection.close()


def test_connection() -> bool:
    """Test Database connectivity."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        logger.info("Database connection successful")
        return True

    except Exception:
        logger.exception("Database connection failed")
        return False