from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.db.db import engine


def check_db_connection() -> bool:
    """Check if database connection is working"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
