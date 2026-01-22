"""Add device_ts_ms column to readings table.

To run this migration:
1. Make sure PostgreSQL is running: docker-compose up -d
2. cd backend
3. source .venv/bin/activate
4. python -m app.db.migrations.add_device_ts_ms
"""
import sys
from pathlib import Path

from sqlalchemy import text

from app.db.db import engine

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))


def upgrade():
    """Add device_ts_ms column if it doesn't exist."""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='readings' AND column_name='device_ts_ms'
        """))

        if result.fetchone() is None:
            # Add column if it doesn't exist
            conn.execute(text("ALTER TABLE readings ADD COLUMN device_ts_ms INTEGER"))
            conn.commit()
            print("✓ Added device_ts_ms column to readings table")
        else:
            print("✓ device_ts_ms column already exists")

if __name__ == "__main__":
    upgrade()
