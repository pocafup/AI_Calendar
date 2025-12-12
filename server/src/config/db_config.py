import os

# Default: SQLite file in the /db directory at project root
DEFAULT_DB_URL = "sqlite:////db/calendar.db"


def get_database_url() -> str:
    """
    Return the database URL for SQLAlchemy.
    Can be overridden with the DATABASE_URL environment variable.
    """
    return os.getenv("DATABASE_URL", DEFAULT_DB_URL)


