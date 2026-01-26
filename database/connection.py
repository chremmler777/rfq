"""Database connection handling with multi-user support."""

from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
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


def upgrade_schema():
    """Upgrade database schema with new columns and migrations.

    This function adds new columns that may have been added since initial schema creation.
    Safe to call multiple times - uses ALTER TABLE only if columns don't exist.
    """
    engine = get_engine()

    # Define the schema upgrades: column_name -> (sql_type, default_value)
    schema_upgrades = {
        'parts': [
            ('surface_finish', 'VARCHAR(30)'),
            ('surface_finish_detail', 'VARCHAR(200)'),
            ('surface_finish_estimated', 'BOOLEAN DEFAULT 0'),
            ('projected_area_source', "VARCHAR(20) DEFAULT 'data'"),
            ('wall_thickness_needs_improvement', 'BOOLEAN DEFAULT 0'),
        ]
    }

    with engine.connect() as conn:
        # Check if column exists before adding
        for table_name, columns in schema_upgrades.items():
            for col_name, col_type in columns:
                try:
                    # Query to check if column exists (SQLite specific)
                    result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                    existing_cols = [row[1] for row in result.fetchall()]

                    if col_name not in existing_cols:
                        # Column doesn't exist, add it
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                except Exception as e:
                    # Column might already exist or other error - log and continue
                    print(f"Migration note for {table_name}.{col_name}: {str(e)}")

        # Migrate existing wall_thickness_source="given" to "data"
        try:
            conn.execute(text("UPDATE parts SET wall_thickness_source = 'data' WHERE wall_thickness_source = 'given'"))
            conn.commit()
        except Exception as e:
            print(f"Migration note for wall_thickness_source migration: {str(e)}")


def init_db():
    """Initialize the database, creating all tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    upgrade_schema()  # Run schema upgrades after creating tables


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
