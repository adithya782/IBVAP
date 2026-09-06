from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.Model.models import Camera

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("/")
def get_cameras(db: Session = Depends(get_db)):
    cameras = db.query(Camera).all()

    return cameras


@router.post("/")
def add_camera(camera: dict, db: Session = Depends(get_db)):
    new_camera = Camera(
        name=camera["name"],
        location=camera["location"],
        rtsp_url=camera["rtsp_url"],
        status=camera["status"]
    )

    db.add(new_camera)
    db.commit()
    db.refresh(new_camera)

    return {
        "message": "Camera added successfully",
        "camera": new_camera
    }