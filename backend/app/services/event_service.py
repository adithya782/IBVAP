from datetime import datetime

from app.database import SessionLocal
from app.Model.models import Event, EventStatus, Severity


def create_intrusion_event(
    camera_id,
    track_id,
    confidence,
    snapshot_path,
    zone_id = None
):
    """
    Create an intrusion event and store it in PostgreSQL.
    """

    db = SessionLocal()

    try:
        event = Event(
            camera_id=camera_id,
            track_id=int(track_id),
            event_type="INTRUSION",
            severity=Severity.CRITICAL,
            confidence=round(float(confidence), 2),
            snapshot_path=snapshot_path,
            status=EventStatus.ACTIVE,
            timestamp=datetime.now().astimezone(),
            zone_id=zone_id
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        return {
            "id": event.id,
            "camera_id": event.camera_id,
            "zone_id": event.zone_id,
            "track_id": event.track_id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type,
            "severity": event.severity.value,
            "confidence": event.confidence,
            "snapshot_path": event.snapshot_path,
            "status": event.status.value
        }

    finally:
        db.close()
