"""DB connection stuff and session management"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config.settings import settings

# setup db engine
engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """dependency for getting db session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
