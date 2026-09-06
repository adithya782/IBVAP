from fastapi import FastAPI

from app.database import engine, Base
from app.Model import models

from app.api.camera import router as camera_router
from app.api.event import router as event_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="SecureStack IBVAP API"
)


app.include_router(camera_router)
app.include_router(event_router)


@app.get("/")
def root():
    return {
        "message": "SecureStack IBVAP API is running!"
    }