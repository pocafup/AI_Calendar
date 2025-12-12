import os

# Default: SQLite file in the /db directory at project root
DEFAULT_DB_URL = "sqlite:////db/calendar.db"

def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DB_URL)
