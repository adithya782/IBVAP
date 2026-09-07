from fastapi import FastAPI

from app.database import engine, Base
from app.Model import models

from app.api.camera import router as camera_router
from app.api.event import router as event_router
from app.api.zone import router as zone_router
from app.api.human_detection import router as human_detection_router
from app.api.vehicle_detection import router as vehicle_detection_router
from app.api.face_detection import router as face_detection_router
from app.api.intrusion import router as intrusion_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="SecureStack IBVAP API"
)


app.include_router(camera_router)
app.include_router(event_router)
app.include_router(zone_router)
app.include_router(human_detection_router)
app.include_router(vehicle_detection_router)
app.include_router(face_detection_router)
app.include_router(intrusion_router)


@app.get("/")
def root():
    return {
        "message": "SecureStack IBVAP API is running!"
    }