from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.Model.models import Event

router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


@router.get("/")
def get_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()

    return [
        {
            "id": event.id,
            "camera_id": event.camera_id,
            "zone_id": event.zone_id,
            "event_type": event.event_type,
            "track_id": event.track_id,
            "confidence": event.confidence,
            "severity": event.severity.value,
            "timestamp": event.timestamp.isoformat(),
            "snapshot_path": event.snapshot_path,
            "status": event.status.value
        }
        for event in events
    ]


@router.get("/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    return {
        "id": event.id,
        "camera_id": event.camera_id,
        "zone_id": event.zone_id,
        "event_type": event.event_type,
        "track_id": event.track_id,
        "confidence": event.confidence,
        "severity": event.severity.value,
        "timestamp": event.timestamp.isoformat(),
        "snapshot_path": event.snapshot_path,
        "status": event.status.value
    }