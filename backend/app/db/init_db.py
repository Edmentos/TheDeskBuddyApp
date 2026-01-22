"""Initialize database tables.

Run this once to create all tables from models.
"""
from app.db.db import engine
from app.db.models import Base


def init_db():
    """Create all database tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully")


if __name__ == "__main__":
    init_db()
