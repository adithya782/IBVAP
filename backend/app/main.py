from fastapi import FastAPI
from app.api.camera import router as camera_router

app = FastAPI(title="SecureStack IBVAP")

app.include_router(camera_router)


@app.get("/")
def root():
    return {"message": "SecureStack IBVAP API is running!"}