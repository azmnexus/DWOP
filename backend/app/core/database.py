import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

logger = logging.getLogger("dwop.database")

# Configure database engine with fallback for local dev when Postgres is not yet spun up
db_url = settings.DATABASE_URL
connect_args = {}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    # Test if configured DB is reachable
    temp_engine = create_engine(db_url, connect_args=connect_args)
    with temp_engine.connect() as conn:
        pass
    engine = temp_engine
    logger.info(f"Connected to primary database: {db_url}")
except Exception as e:
    logger.warning(
        f"Primary database connection failed ({e}). "
        "Falling back to local SQLite database 'sqlite:///./dwop.db' for local development."
    )
    fallback_url = "sqlite:///./dwop.db"
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency to yield a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
