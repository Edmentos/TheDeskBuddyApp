from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.db.db import engine


def check_db_connection() -> bool:
    """test if we can actually connect to postgres"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
