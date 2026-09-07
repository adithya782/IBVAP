import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base
from app.Model import models

from app.api.camera import router as camera_router
from app.api.event import router as event_router
from app.api.zone import router as zone_router
from app.api.human_detection import router as human_detection_router
from app.api.vehicle_detection import router as vehicle_detection_router
from app.api.intrusion import router as intrusion_router
from app.api.stream import router as stream_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SecureStack IBVAP API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Mount snapshots directory as static files
# Ensure 'snapshots' folder exists relative to where you run main.py
if not os.path.exists("snapshots"):
    os.makedirs("snapshots")

app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")

# Include Routers
app.include_router(camera_router, prefix="/api")
app.include_router(event_router, prefix="/api")
app.include_router(zone_router, prefix="/api")
app.include_router(human_detection_router, prefix="/api")
app.include_router(vehicle_detection_router, prefix="/api")
app.include_router(intrusion_router, prefix="/api")
app.include_router(stream_router)

@app.get("/")
def root():
    return {"message": "SecureStack IBVAP API is running!"}