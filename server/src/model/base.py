from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config.db_config import get_database_url

DATABASE_URL = get_database_url()

# echo=True is handy while debugging, False in production
engine = create_engine(DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

Base = declarative_base()


def init_db():
    """
    Import all models here so that Base.metadata.create_all sees them.
    Call init_db() once on server startup.
    """
    from model import task  # noqa: F401  (import for side effect)

    Base.metadata.create_all(bind=engine)

