"""Initialize database tables.

Run this once to create all tables from models.
"""
from sqlalchemy.exc import ProgrammingError

from app.db.db import engine
from app.db.models import Base


def init_db():
    """Create all database tables."""
    print("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
    except ProgrammingError as exc:
        msg = str(exc).lower()
        # Existing index/table is safe here; keep startup idempotent.
        if "already exists" not in msg and "duplicatetable" not in msg:
            raise
        print("Database objects already exist, continuing...")
    print("✓ Database tables created successfully")


if __name__ == "__main__":
    init_db()
