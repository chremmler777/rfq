"""Database connection handling with multi-user support."""

from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from config import get_database_url, ensure_directories
from .models import Base


# Global engine and session factory
_engine = None
_SessionFactory = None


def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL mode and other pragmas for better concurrent access."""
    cursor = dbapi_conn.cursor()
    # WAL mode allows concurrent reads while writing
    cursor.execute("PRAGMA journal_mode=WAL")
    # Increase busy timeout for multi-user access (30 seconds)
    cursor.execute("PRAGMA busy_timeout=30000")
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        ensure_directories()
        _engine = create_engine(
            get_database_url(),
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,  # Check connection validity
        )
        # Set SQLite pragmas on each connection
        event.listen(_engine, "connect", _set_sqlite_pragma)
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory


def init_db():
    """Initialize the database, creating all tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Get a new database session."""
    factory = get_session_factory()
    return factory()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations.

    Usage:
        with session_scope() as session:
            session.add(some_object)
            # Commits automatically on success, rolls back on exception
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_access() -> tuple[bool, str]:
    """Check if database is accessible.

    Returns:
        Tuple of (success, message)
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"
