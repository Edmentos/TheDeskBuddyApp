"""endpoints for querying sensor readings"""
import csv
from io import StringIO
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.db import get_db
from app.db.models import Reading, PostureEvent
from app.posture import get_posture_tracker

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("/latest")
async def get_latest():
    """placeholder for getting latest reading"""
    return {}


@router.get("/query")
async def query_readings(
    sensor_name: str = Query(...),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    get sensor readings with filters
    you can filter by sensor name and time range, plus pagination
    """
    # start with base filter for sensor name
    filters = [Reading.sensor == sensor_name]

    if start_time:
        filters.append(Reading.ts >= start_time)
    if end_time:
        filters.append(Reading.ts <= end_time)

    # need total count for pagination stuff
    total_count = db.query(Reading).filter(and_(*filters)).count()

    # skip to the right page
    offset = (page - 1) * page_size

    # actually grab the data now
    readings = (
        db.query(Reading)
        .filter(and_(*filters))
        .order_by(Reading.ts.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # put together response with page info
    total_pages = (total_count + page_size - 1) // page_size

    return {
        "data": [{
            "id": r.id,
            "timestamp": r.ts.isoformat(),
            "sensor": r.sensor,
            "value": r.value,
            "unit": r.unit,
            "device_ts_ms": r.device_ts_ms
        } for r in readings],
        "page": page,
        "page_size": page_size,
        "total": total_count,
        "total_pages": total_pages
    }


@router.get("/export/csv")
async def export_to_csv(
    sensor_name: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """
    dump sensor data to CSV file
    filter by sensor and/or date range if you want
    """
    # add filters if they exist
    filters = []
    if sensor_name:
        filters.append(Reading.sensor == sensor_name)
    if start_time:
        filters.append(Reading.ts >= start_time)
    if end_time:
        filters.append(Reading.ts <= end_time)

    # get everything that matches
    query = db.query(Reading).order_by(Reading.ts.asc())
    if filters:
        query = query.filter(and_(*filters))

    readings = query.all()

    # setup csv writer
    output = StringIO()
    writer = csv.writer(output)

    # headers first
    writer.writerow(['id', 'timestamp', 'sensor', 'value', 'unit', 'device_ts_ms'])

    # dump all the data
    for r in readings:
        writer.writerow([
            r.id,
            r.ts.isoformat(),
            r.sensor,
            r.value,
            r.unit if r.unit else '',
            r.device_ts_ms if r.device_ts_ms else ''
        ])

    # ready to send
    output.seek(0)
    filename = f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/posture/stats")
async def get_posture_stats(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """
    get sitting/standing time stats for date range
    """
    # default to today if no dates provided
    if not start_date:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if not end_date:
        end_date = datetime.now()

    # query posture events in range
    events = db.query(PostureEvent).filter(
        and_(
            PostureEvent.start_time >= start_date,
            PostureEvent.start_time <= end_date
        )
    ).all()

    sitting_time = 0.0
    standing_time = 0.0

    for event in events:
        if event.duration_seconds:
            if event.posture == "sitting":
                sitting_time += event.duration_seconds
            elif event.posture == "standing":
                standing_time += event.duration_seconds

    total_time = sitting_time + standing_time

    # calculate percentages
    sitting_pct = (sitting_time / total_time * 100) if total_time > 0 else 0
    standing_pct = (standing_time / total_time * 100) if total_time > 0 else 0

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "sitting_seconds": sitting_time,
        "standing_seconds": standing_time,
        "sitting_hours": sitting_time / 3600,
        "standing_hours": standing_time / 3600,
        "sitting_percentage": round(sitting_pct, 1),
        "standing_percentage": round(standing_pct, 1),
        "total_tracked_seconds": total_time
    }


@router.get("/posture/current")
async def get_current_posture():
    """get current posture state"""
    tracker = get_posture_tracker()
    return {
        "current_state": tracker.current_state,
        "smoothed_distance_cm": tracker.get_smoothed_distance(),
        "candidate_state": tracker.candidate_state
    }
