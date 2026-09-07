from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.Model.models import Detection


router = APIRouter(
    prefix="/detections",
    tags=["Human Detection"]
)


@router.get("/human")
def get_human_detections(
    db: Session = Depends(get_db)
):
    detections = (
        db.query(Detection)
        .filter(Detection.object_type == "HUMAN")
        .order_by(Detection.timestamp.desc())
        .all()
    )

    return [
        {
            "id": detection.id,
            "camera_id": detection.camera_id,
            "track_id": detection.track_id,
            "object_type": detection.object_type,
            "confidence": detection.confidence,
            "bounding_box": detection.bounding_box,
            "timestamp": detection.timestamp
        }
        for detection in detections
    ]