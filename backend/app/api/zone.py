from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.Model.models import Zone

router = APIRouter(
    prefix="/zones",
    tags=["Zones"]
)


@router.get("/")
def get_zones(db: Session = Depends(get_db)):
    zones = db.query(Zone).all()

    return [
        {
            "id": zone.id,
            "camera_id": zone.camera_id,
            "name": zone.name,
            "zone_type": zone.zone_type,
            "coordinates": zone.coordinates,
            "created_at": zone.created_at.isoformat()
        }
        for zone in zones
    ]


@router.post("/")
def add_zone(zone: dict, db: Session = Depends(get_db)):
    new_zone = Zone(
        camera_id=zone["camera_id"],
        name=zone["name"],
        zone_type=zone["zone_type"],
        coordinates=zone["coordinates"]
    )

    db.add(new_zone)
    db.commit()
    db.refresh(new_zone)

    return {
        "message": "Zone added successfully",
        "zone": {
            "id": new_zone.id,
            "camera_id": new_zone.camera_id,
            "name": new_zone.name,
            "zone_type": new_zone.zone_type,
            "coordinates": new_zone.coordinates,
            "created_at": new_zone.created_at.isoformat()
        }
    }