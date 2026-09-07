from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.Model.models import Event


router = APIRouter(
    prefix="/intrusion",
    tags=["Virtual Fence / Intrusion"]
)


@router.get("/")
def get_intrusion_events(
    db: Session = Depends(get_db)
):
    events = (
        db.query(Event)
        .filter(Event.event_type == "INTRUSION")
        .order_by(Event.timestamp.desc())
        .all()
    )

    return [
        {
            "id": event.id,
            "camera_id": event.camera_id,
            "zone_id": event.zone_id,
            "track_id": event.track_id,
            "event_type": event.event_type,
            "severity": event.severity.value,
            "confidence": event.confidence,
            "snapshot_path": event.snapshot_path,
            "status": event.status.value,
            "timestamp": event.timestamp
        }
        for event in events
    ]