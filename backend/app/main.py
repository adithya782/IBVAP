from fastapi import FastAPI

from app.api.camera import router as camera_router
from app.api.event import router as event_router


app = FastAPI(
    title="SecureStack IBVAP"
)


# ==========================================
# API ROUTES
# ==========================================

app.include_router(camera_router)

app.include_router(event_router)


# ==========================================
# ROOT
# ==========================================

@app.get("/")
def root():

    return {
        "message": "SecureStack IBVAP API is running!"
    }