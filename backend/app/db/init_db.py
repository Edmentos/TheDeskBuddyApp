"""Initialize database tables.

Run this once to create all tables from models.
"""
import time
from sqlalchemy.exc import ProgrammingError, OperationalError

from app.db.db import engine
from app.db.models import Base


def init_db(max_retries: int = 8, retry_delay_sec: float = 5.0):
    """Create all database tables.

    Retries on OperationalError because on a cold Docker start Postgres can take
    10-20s to finish initialising its data directory before it accepts connections.
    """
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Connecting to database (attempt {attempt}/{max_retries})...")
            Base.metadata.create_all(bind=engine)
            print("✓ Database tables created successfully")
            return
        except OperationalError:
            if attempt == max_retries:
                print("ERROR: Could not connect to database after all retries.")
                raise
            print(f"Database not ready yet, retrying in {retry_delay_sec:.0f}s...")
            time.sleep(retry_delay_sec)
        except ProgrammingError as exc:
            msg = str(exc).lower()
            # Existing index/table is safe here; keep startup idempotent.
            if "already exists" not in msg and "duplicatetable" not in msg:
                raise
            print("Database objects already exist, continuing...")
            return


if __name__ == "__main__":
    init_db()
