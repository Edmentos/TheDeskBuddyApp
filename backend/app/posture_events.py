"""handles posture event logging to database"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.db.db import SessionLocal
from app.db.models import PostureEvent
from app.posture import PostureState


class PostureEventLogger:
    """logs posture changes to database"""

    def __init__(self):
        self.current_event_id: Optional[int] = None

    def start_new_event(self, posture: PostureState, start_time: datetime):
        """start tracking a new posture event"""
        db = SessionLocal()
        try:
            # close previous event if exists
            if self.current_event_id:
                self._finish_current_event(db, start_time)

            # create new event
            event = PostureEvent(
                start_time=start_time,
                posture=posture,
                end_time=None,
                duration_seconds=None
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            self.current_event_id = event.id
        except (ValueError, RuntimeError) as e:
            print(f"Error starting posture event: {e}")
            db.rollback()
        finally:
            db.close()

    def _finish_current_event(self, db: Session, end_time: datetime):
        """close out the current event"""
        if not self.current_event_id:
            return

        event = db.query(PostureEvent).filter(
            PostureEvent.id == self.current_event_id
        ).first()

        if event and not event.end_time:
            event.end_time = end_time
            # calculate how long they were in this posture
            delta = end_time - event.start_time
            event.duration_seconds = delta.total_seconds()
            db.commit()

    def on_state_change(
        self, _old_state: PostureState, new_state: PostureState, timestamp: datetime
    ):
        """callback when posture changes"""
        self.start_new_event(new_state, timestamp)


# global logger instance
_event_logger: Optional[PostureEventLogger] = None


def get_event_logger() -> PostureEventLogger:
    """get the global event logger"""
    global _event_logger
    if _event_logger is None:
        _event_logger = PostureEventLogger()
    return _event_logger
