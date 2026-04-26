"""Shared runtime handle for webcam worker.

Small module so API endpoints can talk to the active worker without circular imports.
"""
from threading import Lock
from typing import Optional

from app.webcam_worker import WebcamSlouchWorker

_lock = Lock()
_state: dict[str, Optional[WebcamSlouchWorker]] = {"active_worker": None}


def set_active_webcam_worker(worker: Optional[WebcamSlouchWorker]):
    """Set the currently running webcam worker reference."""
    with _lock:
        _state["active_worker"] = worker


def get_active_webcam_worker() -> Optional[WebcamSlouchWorker]:
    """Get the currently running webcam worker reference."""
    with _lock:
        return _state["active_worker"]
